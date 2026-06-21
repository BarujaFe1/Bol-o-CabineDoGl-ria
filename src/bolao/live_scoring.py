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
    goal_one_team_points = int(scoring_rules.get("one_team_goals", 1))
    goal_diff_points = int(scoring_rules.get("goal_difference", 1))
    
    hit_exact = (p_h == o_h) and (p_a == o_a)
    hit_outcome = ((p_h > p_a) == (o_h > o_a)) and ((p_h < p_a) == (o_h < o_a)) and ((p_h == p_a) == (o_h == o_a))
    hit_home_goals = (p_h == o_h)
    hit_away_goals = (p_a == o_a)
    hit_diff = (p_h - p_a) == (o_h - o_a)
    
    breakdown = []
    points = 0
    
    exact_mode = config.get("live_scoring", {}).get("exact_score_mode", "isolated_max")
    
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
            
    # Lightning Mode (F19)
    if (getattr(match, "placar_intervalo_mandante", None) is not None and 
        getattr(match, "placar_intervalo_visitante", None) is not None and 
        getattr(prediction, "predicted_second_half_home_goals", None) is not None and 
        getattr(prediction, "predicted_second_half_away_goals", None) is not None):
        
        pi_h, pi_a = match.placar_intervalo_mandante, match.placar_intervalo_visitante
        psh_h, psh_a = prediction.predicted_second_half_home_goals, prediction.predicted_second_half_away_goals
        
        # Real goals in 2nd half
        real_sh_h = o_h - pi_h
        real_sh_a = o_a - pi_a
        
        # Calculate points
        sh_hit_exact = (psh_h == real_sh_h) and (psh_a == real_sh_a)
        sh_hit_outcome = ((psh_h > psh_a) == (real_sh_h > real_sh_a)) and ((psh_h < psh_a) == (real_sh_h < real_sh_a)) and ((psh_h == psh_a) == (real_sh_h == real_sh_a))
        
        pts_exact_rel = int(config.get("live_scoring", {}).get("pts_relampago_exato", 4))
        pts_outcome_rel = int(config.get("live_scoring", {}).get("pts_relampago_resultado", 2))
        
        if sh_hit_exact:
            points += pts_exact_rel
            breakdown.append(f"⚡ Relâmpago Exato (2ºT): +{pts_exact_rel} pts")
        elif sh_hit_outcome:
            points += pts_outcome_rel
            breakdown.append(f"⚡ Relâmpago Resultado (2ºT): +{pts_outcome_rel} pts")
        else:
            breakdown.append("⚡ Relâmpago (2ºT): 0 pts")

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
    Inclui pontos de artilheiro e assistente do módulo Brasil.
    """
    from .storage import load_brasil_palpites_goleadores

    approved_matches = {m.match_id: m for m in matches if m.status == "result_approved"}

    # Build goleadores lookup: (normalized_key, jogo_id) -> pontos_ganhos
    goleadores_map = {}
    for gp in load_brasil_palpites_goleadores():
        gk = normalize_participant_key(gp["participante_nome"])
        gid = gp["jogo_id"]
        pts = gp.get("pontos_ganhos", 0) or 0
        goleadores_map[(gk, gid)] = pts

    # Identify Brazil match IDs (any match with "Brasil" as home or away)
    brazil_match_ids = set()
    for m in matches:
        if "Brasil" in (m.home_team or "") or "Brasil" in (m.away_team or ""):
            brazil_match_ids.add(m.match_id)

    # Build artilheiro dia/rodada lookup: normalized_key -> pontos
    artilheiro_dia_entries = calculate_artilheiro_dia_points(config)
    artilheiro_rodada_entries = calculate_artilheiro_rodada_points(config)
    artilheiro_dia_map = {}
    for e in artilheiro_dia_entries:
        nk = normalize_participant_key(e["participante_nome"])
        artilheiro_dia_map[nk] = artilheiro_dia_map.get(nk, 0) + e["pontos"]
    artilheiro_rodada_map = {}
    for e in artilheiro_rodada_entries:
        nk = normalize_participant_key(e["participante_nome"])
        artilheiro_rodada_map[nk] = artilheiro_rodada_map.get(nk, 0) + e["pontos"]
    
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
        match_points = 0
        brasil_points = 0
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
                match_points += points
                total_points += points
                
                if res["flags"].get("exact"):
                    exact_scores += 1
                if res["flags"].get("outcome"):
                    outcomes += 1

                # Add artilheiro/assistente points for Brazil matches
                if p.match_id in brazil_match_ids:
                    gk = p.participant_key or normalize_participant_key(p.participant_name)
                    gol_pts = goleadores_map.get((gk, p.match_id), 0)
                    if gol_pts:
                        brasil_points += gol_pts
                        total_points += gol_pts

        # Add artilheiro do dia / rodada points
        art_dia = artilheiro_dia_map.get(pkey, 0)
        art_rod = artilheiro_rodada_map.get(pkey, 0)
        total_points += art_dia + art_rod

        missed_predictions = max(0, possible_count - len(guessed_match_ids))
        
        hit_rate = 0.0
        if predictions_count > 0:
            hit_rate = outcomes / predictions_count

        ranking_list.append({
            "participant": info["name"],
            "participant_key": pkey,
            "total": total_points,
            "match_points": match_points,
            "brasil_points": brasil_points,
            "artilheiro_dia_points": art_dia,
            "artilheiro_rodada_points": art_rod,
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

from collections import Counter

def calcular_pontos_goleadores(
    goleadores_palpitados: list,
    assistentes_palpitados: list,
    goleadores_reais: list,
    assistentes_reais: list,
    config: dict,
    reservas_palpitadas: list | None = None
) -> dict:
    # Safely get rules from config, fallback to default if not found
    live_rules = config.get("live_scoring", {})
    pts_gol    = int(live_rules.get("pts_acertar_goleador", config.get("pts_acertar_goleador", 4)))
    pts_assist = int(live_rules.get("pts_acertar_assistente", config.get("pts_acertar_assistente", 2)))
    pts_bonus_todos     = int(live_rules.get("pts_todos_goleadores", config.get("pts_todos_goleadores", 5)))

    pontos = 0
    detalhes = []
    
    suspended_players = config.get("suspended_players", [])
    
    gols_palp = list(goleadores_palpitados)
    res_palp = list(reservas_palpitadas) if reservas_palpitadas is not None else []
    while len(res_palp) < len(gols_palp):
        res_palp.append("Nenhum")
        
    goleadores_reais_copy = list(goleadores_reais)
    goleadores_reais_counter = Counter(goleadores_reais_copy)
    
    # First pass: match non-suspended titulars
    non_susp_palp = []
    susp_pairs = []
    for g, r in zip(gols_palp, res_palp):
        if g in suspended_players:
            susp_pairs.append((g, r))
        else:
            non_susp_palp.append(g)
            
    matched_titulars = []
    # Match non-suspended titulars
    non_susp_counter = Counter(non_susp_palp)
    for jogador, count in non_susp_counter.items():
        real_count = goleadores_reais_counter.get(jogador, 0)
        hits = min(count, real_count)
        if hits > 0:
            pontos += hits * pts_gol
            goleadores_reais_counter[jogador] -= hits
            detalhes.append(f"⚽ {jogador} ×{hits}: +{hits * pts_gol}pts")
            matched_titulars.extend([jogador] * hits)
            
    # Second pass: check reserves for suspended titulars
    for g, r in susp_pairs:
        if r and r != "Nenhum" and r not in suspended_players:
            real_count = goleadores_reais_counter.get(r, 0)
            if real_count > 0:
                pts_half = pts_gol // 2
                pontos += pts_half
                goleadores_reais_counter[r] -= 1
                detalhes.append(f"⚽ {r} (Reserva de {g}): +{pts_half}pts")
                matched_titulars.append(r)
                
    # Assistances
    real_assist_count = Counter(assistentes_reais)
    palp_assist_count = Counter(assistentes_palpitados)
    for jogador, qtd_real in real_assist_count.items():
        acertos = min(palp_assist_count.get(jogador, 0), qtd_real)
        pontos += acertos * pts_assist
        if acertos:
            detalhes.append(f"🅰️ {jogador} ×{acertos}: +{acertos * pts_assist}pts")

    # Bônus: todos os goleadores
    if len(goleadores_reais) > 1 and Counter(matched_titulars) == Counter(goleadores_reais):
        pontos += pts_bonus_todos
        detalhes.append(f"🔥 Todos os goleadores: +{pts_bonus_todos}pts")

    return {"total": pontos, "detalhes": detalhes}

def calcular_pontos_artilheiro_classico(
    palpitado: str,
    artilheiros_reais: list[str],
    config: dict,
    is_geral: bool = False
) -> int:
    if not palpitado or not artilheiros_reais:
        return 0
    
    # Normalize comparison
    from .utils import norm_team
    p_norm = norm_team(palpitado)
    reais_norm = [norm_team(x) for x in artilheiros_reais]
    
    if not reais_norm:
        return 0
        
    pts_exact = int(config.get("pts_artilheiro_geral_copa", 20)) if is_geral else int(config.get("pts_artilheiro_brasil_copa", 15))
    pts_top3 = int(config.get("pts_top3_artilheiros_gerais", 7)) if is_geral else int(config.get("pts_top3_artilheiros_brasil", 5))
    
    if p_norm == reais_norm[0]:
        return pts_exact
    if p_norm in reais_norm[:3]:
        return pts_top3
    return 0


def calculate_artilheiro_dia_points(config: dict) -> list[dict]:
    """
    Calcula pontos de artilheiro do dia para cada participante.
    Compara palpites (artilheiro_palpites_dia.json) com resultados oficiais
    (artilheiro_resultado_dia.json). Retorna lista de dicts com
    participante, data, pontos e breakdown.
    """
    from .storage import load_artilheiro_palpites_dia, load_artilheiro_resultado_dia

    palpites = load_artilheiro_palpites_dia()
    resultados = load_artilheiro_resultado_dia()

    pts_acertou = int(config.get("pts_artilheiro_dia", 5))

    resultado_por_data = {r["data"]: r for r in resultados}

    entries = []
    for p in palpites:
        data = p["data"]
        resultado = resultado_por_data.get(data)
        if not resultado:
            continue

        palpite_jogador = (p.get("selecao", ""), p.get("jogador", ""))
        real_jogador = (resultado.get("selecao", ""), resultado.get("jogador", ""))

        pontos = pts_acertou if palpite_jogador == real_jogador else 0

        entries.append({
            "participante_nome": p["participante_nome"],
            "data": data,
            "jogador_palpite": p.get("jogador", ""),
            "selecao_palpite": p.get("selecao", ""),
            "jogador_real": resultado.get("jogador", ""),
            "selecao_real": resultado.get("selecao", ""),
            "pontos": pontos,
            "acertou": pontos > 0,
        })

    return entries


def calculate_artilheiro_rodada_points(config: dict) -> list[dict]:
    """
    Calcula pontos de artilheiro da rodada para cada participante.
    Compara palpites (artilheiro_palpites_rodada.json) com resultados oficiais
    (artilheiro_resultado_rodada.json).
    """
    from .storage import load_artilheiro_palpites_rodada, load_artilheiro_resultado_rodada

    palpites = load_artilheiro_palpites_rodada()
    resultados = load_artilheiro_resultado_rodada()

    pts_acertou = int(config.get("pts_artilheiro_rodada", 10))

    resultado_por_rodada = {r["rodada"]: r for r in resultados}

    entries = []
    for p in palpites:
        rodada = p["rodada"]
        resultado = resultado_por_rodada.get(rodada)
        if not resultado:
            continue

        palpite_jogador = (p.get("selecao", ""), p.get("jogador", ""))
        real_jogador = (resultado.get("selecao", ""), resultado.get("jogador", ""))

        pontos = pts_acertou if palpite_jogador == real_jogador else 0

        entries.append({
            "participante_nome": p["participante_nome"],
            "rodada": rodada,
            "jogador_palpite": p.get("jogador", ""),
            "selecao_palpite": p.get("selecao", ""),
            "jogador_real": resultado.get("jogador", ""),
            "selecao_real": resultado.get("selecao", ""),
            "pontos": pontos,
            "acertou": pontos > 0,
        })

    return entries
