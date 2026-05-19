
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .constants import DEFAULT_UNIFORM_RULES, DEFAULT_WEIGHTED_RULES, GROUPS, PHASE_LABELS, PHASES
from .models import Prediction, ScoreBreakdown
from .utils import norm_team


@dataclass
class ScoreConfig:
    mode: str = "ponderado"
    weighted_rules: dict[str, int] = None
    uniform_rules: dict[str, int] = None

    def __post_init__(self):
        if self.weighted_rules is None:
            self.weighted_rules = dict(DEFAULT_WEIGHTED_RULES)
        if self.uniform_rules is None:
            self.uniform_rules = dict(DEFAULT_UNIFORM_RULES)


def _eq(a: str | None, b: str | None) -> bool:
    return bool(a and b and norm_team(a) == norm_team(b))


def score_prediction(pred: Prediction, official: Prediction, config: ScoreConfig) -> ScoreBreakdown:
    mode = config.mode
    weighted = config.weighted_rules
    uniform = config.uniform_rules
    sb = ScoreBreakdown(participant=pred.participant)

    # Groups
    for g in GROUPS:
        pred_group = pred.groups.get(g, [None, None, None, None])
        off_group = official.groups.get(g, [None, None, None, None])
        for pos in range(4):
            hit = _eq(pred_group[pos] if pos < len(pred_group) else None, off_group[pos] if pos < len(off_group) else None)
            points = 0
            if hit:
                sb.group_hits += 1
                if mode == "ponderado":
                    if pos == 0:
                        points = int(weighted.get("group_1", 5))
                    elif pos == 1:
                        points = int(weighted.get("group_2", 3))
                    elif pos == 2 and any(_eq(off_group[pos], t) for t in official.best_thirds):
                        points = int(weighted.get("group_3_best", 2))
                    else:
                        points = 0
                else:
                    points = int(uniform.get("decision_points", 1))
            sb.group_points += points
            sb.details.append({
                "seção": "Grupos",
                "fase": f"Grupo {g}",
                "item": f"{pos+1}º colocado",
                "palpite": pred_group[pos] if pos < len(pred_group) else None,
                "oficial": off_group[pos] if pos < len(off_group) else None,
                "acertou": hit,
                "pontos": points,
            })

    # Best thirds
    official_thirds_norm = {norm_team(x) for x in official.best_thirds if x}
    pred_thirds_norm = {norm_team(x) for x in pred.best_thirds if x}
    for third in official.best_thirds:
        hit = norm_team(third) in pred_thirds_norm
        points = 0
        if hit:
            sb.best_third_hits += 1
            points = int(weighted.get("best_third", 2)) if mode == "ponderado" else int(uniform.get("decision_points", 1))
        sb.best_third_points += points
        sb.details.append({
            "seção": "Terceiros",
            "fase": "Melhores terceiros",
            "item": third,
            "palpite": "marcado" if norm_team(third) in pred_thirds_norm else "não marcado",
            "oficial": "classificado",
            "acertou": hit,
            "pontos": points,
        })

    # Knockout
    for phase in PHASES:
        p_matches = pred.knockout.get(phase, [])
        o_matches = official.knockout.get(phase, [])
        max_len = max(len(p_matches), len(o_matches))
        for idx in range(max_len):
            pm = p_matches[idx] if idx < len(p_matches) else None
            om = o_matches[idx] if idx < len(o_matches) else None
            p_winner = pm.winner if pm else None
            o_winner = om.winner if om else None
            hit = _eq(p_winner, o_winner)
            points = 0
            if hit:
                sb.knockout_hits += 1
                points = int(weighted.get(phase, 5)) if mode == "ponderado" else int(uniform.get("decision_points", 1))
            sb.knockout_points += points
            sb.details.append({
                "seção": "Mata-mata",
                "fase": PHASE_LABELS[phase],
                "item": f"Jogo {idx+1}",
                "palpite": p_winner,
                "oficial": o_winner,
                "acertou": hit,
                "pontos": points,
            })

    champion_hit = _eq(pred.champion, official.champion)
    if champion_hit:
        sb.champion_hit = 1
        bonus = int(weighted.get("champion_bonus", 0)) if mode == "ponderado" else int(uniform.get("champion_bonus", 0))
        sb.champion_points += bonus
    else:
        bonus = 0
    sb.details.append({
        "seção": "Campeã",
        "fase": "Campeã",
        "item": "Campeã",
        "palpite": pred.champion,
        "oficial": official.champion,
        "acertou": champion_hit,
        "pontos": bonus,
    })

    sb.total = sb.group_points + sb.best_third_points + sb.knockout_points + sb.champion_points
    sb.tie_breaker = f"Mata-mata {sb.knockout_points} pts · campeã {'sim' if sb.champion_hit else 'não'}"
    return sb


def rank_predictions(predictions: list[Prediction], official: Prediction | None, config: ScoreConfig) -> list[ScoreBreakdown]:
    if official is None:
        return []
    scores = [score_prediction(pred, official, config) for pred in predictions]
    return sorted(scores, key=lambda s: (-s.total, -s.knockout_points, -s.champion_hit, s.participant.lower()))


def ranking_rows(scores: list[ScoreBreakdown]) -> list[dict[str, Any]]:
    return [score.to_row(i) for i, score in enumerate(scores, start=1)]
