from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .constants import DEFAULT_UNIFORM_RULES, DEFAULT_WEIGHTED_RULES, DEFAULT_V2_RULES, GROUPS, PHASE_LABELS, PHASES
from .models import Prediction, ScoreBreakdown
from .utils import norm_team
from .worldcup_2026_data import GROUP_MATCHES, TEAMS
import streamlit as st


@dataclass
class ScoreConfig:
    mode: str = "v2"
    weighted_rules: dict[str, int] = None
    uniform_rules: dict[str, int] = None
    v2_rules: dict[str, int] = None

    def __post_init__(self):
        if self.weighted_rules is None:
            self.weighted_rules = dict(DEFAULT_WEIGHTED_RULES)
        if self.uniform_rules is None:
            self.uniform_rules = dict(DEFAULT_UNIFORM_RULES)
        if self.v2_rules is None:
            self.v2_rules = dict(DEFAULT_V2_RULES)


def _eq(a: str | None, b: str | None) -> bool:
    return bool(a and b and norm_team(a) == norm_team(b))


def get_phase_teams(pred: Prediction, phase: str) -> set[str]:
    teams = set()
    for m in pred.knockout.get(phase, []):
        if m.a:
            teams.add(norm_team(m.a))
        if m.b:
            teams.add(norm_team(m.b))
    return teams


def score_prediction(pred: Prediction, official: Prediction, config: ScoreConfig) -> ScoreBreakdown:
    mode = config.mode
    sb = ScoreBreakdown(participant=pred.participant)
    sb.submitted_at = pred.submitted_at or ""

    if mode == "v2":
        rules = config.v2_rules or DEFAULT_V2_RULES
        
        # 1. Group Stage Match Scores
        pred_matches = pred.meta.get("group_matches", {})
        off_matches = official.meta.get("group_matches", {})
        
        for gm in GROUP_MATCHES:
            m_id = gm["id"]
            p_score = pred_matches.get(m_id)
            o_score = off_matches.get(m_id)
            
            # If not filled/simulated, 0 points
            if p_score is None or o_score is None or len(p_score) < 2 or len(o_score) < 2:
                points = 0
                hit = False
                p_text = "—"
                o_text = f"{o_score[0]}x{o_score[1]}" if o_score else "—"
            else:
                p_h, p_a = int(p_score[0]), int(p_score[1])
                o_h, o_a = int(o_score[0]), int(o_score[1])
                p_text = f"{p_h}x{p_a}"
                o_text = f"{o_h}x{o_a}"
                
                # Primary points (highest of exact / result+GD / result / team_goals)
                primary_points = 0
                if p_h == o_h and p_a == o_a:
                    primary_points = int(rules.get("group_exact", 5))
                    sb.exact_scores += 1
                    sb.group_hits += 1
                    hit = True
                elif ((p_h > p_a) == (o_h > o_a) and (p_h < p_a) == (o_h < o_a) and (p_h == p_a) == (o_h == o_a)) and (p_h - p_a == o_h - o_a):
                    primary_points = int(rules.get("group_result_gd", 3))
                    sb.group_hits += 1
                    hit = True
                elif (p_h > p_a) == (o_h > o_a) and (p_h < p_a) == (o_h < o_a) and (p_h == p_a) == (o_h == o_a):
                    primary_points = int(rules.get("group_result", 2))
                    sb.group_hits += 1
                    hit = True
                elif p_h == o_h or p_a == o_a:
                    primary_points = int(rules.get("group_team_goals", 1))
                    hit = False
                else:
                    primary_points = 0
                    hit = False

                # Auxiliary points (cumulative bonus points)
                aux_points = 0
                # 1. Sum of goals correct
                if (p_h + p_a) == (o_h + o_a):
                    aux_points += int(rules.get("group_sum_goals", 0))
                # 2. Both teams scored correct
                if ((p_h > 0) and (p_a > 0)) == ((o_h > 0) and (o_a > 0)):
                    aux_points += int(rules.get("group_both_scored", 0))
                # 3. Over 2.5 goals correct
                if ((p_h + p_a) > 2.5) == ((o_h + o_a) > 2.5):
                    aux_points += int(rules.get("group_over_2_5", 0))

                points = primary_points + aux_points
            
            sb.group_points += points
            t_home = TEAMS.get(gm["home_id"], {}).get("name", "Mandante")
            t_away = TEAMS.get(gm["away_id"], {}).get("name", "Visitante")
            sb.details.append({
                "seção": "Grupos",
                "fase": f"Grupo {gm['group']}",
                "item": f"{t_home} x {t_away}",
                "palpite": p_text,
                "oficial": o_text,
                "acertou": hit,
                "pontos": points,
            })
            
        # 2. Knockout Stage Progression (no best thirds points in V2)
        # Check teams that advanced to Oitavas, Quartas, Semifinais, Final
        phases_to_score = [
            ("oitavas", "ko_oitavas", 3),
            ("quartas", "ko_quartas", 5),
            ("semifinais", "ko_semifinais", 8),
            ("final", "ko_final", 12)
        ]
        
        for phase, rule_key, def_val in phases_to_score:
            pred_teams = get_phase_teams(pred, phase)
            off_teams = get_phase_teams(official, phase)
            
            # For each team that officially made it, check if user predicted it
            for team_id in off_teams:
                team_name = TEAMS.get(team_id, {}).get("name", team_id)
                hit = team_id in pred_teams
                points = int(rules.get(rule_key, def_val)) if hit else 0
                if hit:
                    sb.knockout_hits += 1
                    sb.knockout_points += points
                
                sb.details.append({
                    "seção": "Mata-mata",
                    "fase": PHASE_LABELS.get(phase, phase),
                    "item": f"Classificação: {team_name}",
                    "palpite": "classificado" if hit else "não classificado",
                    "oficial": "classificado",
                    "acertou": hit,
                    "pontos": points,
                })
                
        # 3. Champion
        champion_hit = _eq(pred.champion, official.champion)
        points = int(rules.get("ko_champion", 20)) if champion_hit else 0
        if champion_hit:
            sb.champion_hit = 1
            sb.champion_points += points
            
        sb.details.append({
            "seção": "Campeã",
            "fase": "Campeã",
            "item": "Campeã",
            "palpite": pred.champion,
            "oficial": official.champion,
            "acertou": champion_hit,
            "pontos": points,
        })
        
        sb.total = sb.group_points + sb.knockout_points + sb.champion_points
        sb.tie_breaker = f"Mata-mata {sb.knockout_points} pts · campeã {'sim' if sb.champion_hit else 'não'}"
        return sb

    else:
        # LEGACY/OLD SCORING MODES (ponderado / uniforme)
        weighted = config.weighted_rules
        uniform = config.uniform_rules

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

    import hashlib
    import json

    # Serialize to make a stable hash key
    pred_data = [p.to_dict() for p in predictions]
    # Sort by participant to ensure order changes don't affect hash
    pred_data = sorted(pred_data, key=lambda x: x.get("participant", ""))
    off_data = official.to_dict() if official else None
    config_data = {
        "mode": config.mode,
        "weighted": config.weighted_rules,
        "uniform": config.uniform_rules,
        "v2": config.v2_rules
    }
    hash_payload = {"preds": pred_data, "off": off_data, "config": config_data}
    hash_str = hashlib.sha256(json.dumps(hash_payload, sort_keys=True, default=str).encode()).hexdigest()

    return _rank_predictions_cached(hash_str, predictions, official, config)


@st.cache_data(show_spinner=False)
def _rank_predictions_cached(hash_key: str, _predictions: list[Prediction], _official: Prediction | None, _config: ScoreConfig) -> list[ScoreBreakdown]:
    scores = [score_prediction(pred, _official, _config) for pred in _predictions]
    
    if _config.mode == "v2":
        # Tiebreakers V2:
        # 1. Total Points (descending)
        # 2. Champion hit (descending)
        # 3. Knockout Points (descending)
        # 4. Group Exact Scores Count (descending)
        # 5. Group Points (descending)
        # 6. Submission timestamp (ascending: older is better). If empty/None, put at the end
        # 7. Alphabetical order of participant name (case-insensitive)
        return sorted(
            scores,
            key=lambda s: (
                -s.total,
                -s.champion_hit,
                -s.knockout_points,
                -s.exact_scores,
                -s.group_points,
                s.submitted_at or "9999-99-99T99:99:99",
                s.participant.lower(),
            )
        )
    else:
        # Legacy sorting
        return sorted(scores, key=lambda s: (-s.total, -s.knockout_points, -s.champion_hit, s.participant.lower()))


def ranking_rows(scores: list[ScoreBreakdown]) -> list[dict[str, Any]]:
    return [score.to_row(i) for i, score in enumerate(scores, start=1)]
