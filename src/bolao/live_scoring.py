from __future__ import annotations

from .models import LiveMatch, LivePrediction
from .utils import normalize_participant_key

def calculate_live_prediction_points(prediction: LivePrediction, match: LiveMatch, config: dict) -> dict:
    """
    Retorna:
    {
      "points": int,
      "breakdown": list[str],
      "flags": dict
    }
    """
    if match.status != "result_approved" or match.official_home_goals is None or match.official_away_goals is None:
        return {"points": 0, "breakdown": ["Aguardando resultado oficial"], "flags": {"pending": True}}
    
    if prediction.is_late:
        return {"points": 0, "breakdown": ["Palpite atrasado (inválido)"], "flags": {"late": True}}
        
    p_h, p_a = prediction.predicted_home_goals, prediction.predicted_away_goals
    o_h, o_a = match.official_home_goals, match.official_away_goals
    
    scoring_rules = config.get("live_scoring", {})
    exact_score_points = int(scoring_rules.get("exact_score", 5))
    outcome_points = int(scoring_rules.get("outcome", 3))
    goal_one_team_points = int(scoring_rules.get("goal_one_team", 1))
    goal_diff_points = int(scoring_rules.get("goal_difference", 1))
    
    hit_exact = (p_h == o_h) and (p_a == o_a)
    hit_outcome = ((p_h > p_a) == (o_h > o_a)) and ((p_h < p_a) == (o_h < o_a)) and ((p_h == p_a) == (o_h == o_a))
    hit_home_goals = (p_h == o_h)
    hit_away_goals = (p_a == o_a)
    hit_diff = (p_h - p_a) == (o_h - o_a)
    
    breakdown = []
    points = 0
    
    exact_mode = config.get("exact_score_mode", "isolated_max")
    
    if hit_exact:
        if exact_mode == "isolated_max":
            points = exact_score_points
            breakdown.append(f"Placar exato: +{exact_score_points} pts")
        else:
            points += exact_score_points
            breakdown.append(f"Placar exato: +{exact_score_points} pts")
            points += outcome_points
            breakdown.append(f"Resultado correto: +{outcome_points} pts")
            if hit_home_goals:
                points += goal_one_team_points
                breakdown.append(f"Gols do mandante: +{goal_one_team_points} pts")
            if hit_away_goals:
                points += goal_one_team_points
                breakdown.append(f"Gols do visitante: +{goal_one_team_points} pts")
            if hit_diff:
                points += goal_diff_points
                breakdown.append(f"Saldo de gols: +{goal_diff_points} pts")
    else:
        if hit_outcome:
            points += outcome_points
            breakdown.append(f"Resultado correto: +{outcome_points} pts")
        if hit_home_goals:
            points += goal_one_team_points
            breakdown.append(f"Gols do mandante: +{goal_one_team_points} pts")
        if hit_away_goals:
            points += goal_one_team_points
            breakdown.append(f"Gols do visitante: +{goal_one_team_points} pts")
        if hit_diff:
            points += goal_diff_points
            breakdown.append(f"Saldo de gols: +{goal_diff_points} pts")
            
    if points == 0:
        breakdown.append("Nenhum acerto")
        
    return {
        "points": points,
        "breakdown": breakdown,
        "flags": {
            "exact": hit_exact,
            "outcome": hit_outcome,
            "home_goals": hit_home_goals,
            "away_goals": hit_away_goals,
            "diff": hit_diff
        }
    }


def calculate_live_ranking(live_predictions: list[LivePrediction], matches: list[LiveMatch], config: dict) -> list[dict]:
    """
    Ranking jogo a jogo.
    Considerar apenas jogos com resultado aprovado.
    """
    approved_matches = {m.match_id: m for m in matches if m.status == "result_approved"}
    
    # Agrupa palpites por participante
    by_participant = {}
    for p in live_predictions:
        pkey = p.participant_key or normalize_participant_key(p.participant_name)
        if pkey not in by_participant:
            by_participant[pkey] = {
                "name": p.participant_name,
                "key": pkey,
                "predictions": []
            }
        by_participant[pkey]["predictions"].append(p)

    ranking_list = []
    possible_count = len(approved_matches)

    for pkey, info in by_participant.items():
        total_points = 0
        exact_scores = 0
        outcomes = 0
        predictions_count = 0
        missed_predictions = 0
        
        # Process predictions for approved matches
        guessed_match_ids = set()
        for p in info["predictions"]:
            if p.match_id in approved_matches:
                m = approved_matches[p.match_id]
                guessed_match_ids.add(p.match_id)
                predictions_count += 1
                
                res = calculate_live_prediction_points(p, m, config)
                points = res["points"]
                total_points += points
                
                if res["flags"].get("exact"):
                    exact_scores += 1
                if res["flags"].get("outcome"):
                    outcomes += 1

        missed_predictions = max(0, possible_count - len(guessed_match_ids))
        
        hit_rate = 0.0
        if predictions_count > 0:
            hit_rate = outcomes / predictions_count

        ranking_list.append({
            "participant": info["name"],
            "participant_key": pkey,
            "total": total_points,
            "exact_scores": exact_scores,
            "outcomes": outcomes,
            "predictions_count": predictions_count,
            "missed_predictions": missed_predictions,
            "possible_matches": possible_count,
            "hit_rate": hit_rate,
            "tie_breaker": f"{exact_scores} exatos · {int(hit_rate * 100)}% aprov. · {missed_predictions} perdidos"
        })

    # Ordenação: pontos (desc), exatos (desc), hit_rate (desc), palpites perdidos (asc), nome (asc)
    ranking_list.sort(key=lambda s: (
        -s["total"],
        -s["exact_scores"],
        -s["hit_rate"],
        s["missed_predictions"],
        s["participant"].lower()
    ))

    # Adiciona a posição do pódio
    for idx, row in enumerate(ranking_list, start=1):
        row["position"] = idx

    return ranking_list
