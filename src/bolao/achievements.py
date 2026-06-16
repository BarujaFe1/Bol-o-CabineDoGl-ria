from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from .storage import AppDataContext
from .utils import normalize_participant_key
from .live_scoring import calculate_live_prediction_points
from .scoring import rank_predictions

@dataclass
class Badge:
    icon: str
    name: str
    description: str

    def to_dict(self) -> dict[str, str]:
        return {
            "icon": self.icon,
            "name": self.name,
            "description": self.description
        }

def calculate_achievements(ctx: AppDataContext) -> dict[str, list[dict[str, str]]]:
    """
    Calcula e retorna as conquistas/badges sociais de todos os participantes.
    Retorna um dicionário mapeando participant_key para uma lista de dicionários de conquistas.
    """
    achievements = {}
    
    # 1. Obter participantes dos dois modos
    submissions = ctx.submissions or []
    live_predictions = ctx.live_predictions or []
    matches = ctx.matches or []
    official = ctx.official
    
    # Mapear participant_key para nome legível
    participant_names = {}
    for pred in submissions:
        pkey = normalize_participant_key(pred.participant)
        participant_names[pkey] = pred.participant
    for lp in live_predictions:
        pkey = lp.participant_key or normalize_participant_key(lp.participant_name)
        participant_names[pkey] = lp.participant_name
        
    for pkey in participant_names.keys():
        achievements[pkey] = []
        
    if not participant_names:
        return achievements

    # Agrupar live predictions por participante e por match_id
    live_by_participant = {pkey: [] for pkey in participant_names.keys()}
    for lp in live_predictions:
        pkey = lp.participant_key or normalize_participant_key(lp.participant_name)
        if pkey in live_by_participant:
            live_by_participant[pkey].append(lp)
            
    # Agrupar live predictions por jogo
    live_by_match = {}
    for lp in live_predictions:
        if lp.match_id not in live_by_match:
            live_by_match[lp.match_id] = []
        live_by_match[lp.match_id].append(lp)

    approved_matches = [m for m in matches if m.status == "result_approved" and m.official_home_goals is not None and m.official_away_goals is not None]
    approved_match_ids = {m.match_id for m in approved_matches}

    # 2. Computar estatísticas por participante
    stats = {}
    for pkey, name in participant_names.items():
        stats[pkey] = {
            "exact_count": 0,
            "outcome_count": 0,
            "draw_count": 0,
            "missed_count": 0,
            "zebra_hits": 0,
            "underdog_hits": 0,
            "streak": 0,
            "current_streak": 0,
            "points_per_approved_match": {}, # match_id: points
        }
        
    # Calcular pontos de live prediction por jogo aprovado
    for m in approved_matches:
        # Calcular proporções de palpites do grupo para identificar Zebras
        match_preds = live_by_match.get(m.match_id, [])
        total_preds = len(match_preds)
        
        home_votes = 0
        away_votes = 0
        draw_votes = 0
        
        for lp in match_preds:
            if lp.predicted_home_goals > lp.predicted_away_goals:
                home_votes += 1
            elif lp.predicted_home_goals < lp.predicted_away_goals:
                away_votes += 1
            else:
                draw_votes += 1
                
        # Identificar resultado vencedor real
        real_outcome = "draw"
        if m.official_home_goals > m.official_away_goals:
            real_outcome = "home"
        elif m.official_home_goals < m.official_away_goals:
            real_outcome = "away"
            
        # Verificar se o resultado real é "zebra" (escolhido por < 30% do grupo)
        is_zebra = False
        if total_preds > 0:
            if real_outcome == "home" and (home_votes / total_preds) < 0.30:
                is_zebra = True
            elif real_outcome == "away" and (away_votes / total_preds) < 0.30:
                is_zebra = True
            elif real_outcome == "draw" and (draw_votes / total_preds) < 0.30:
                is_zebra = True
                
        # Verificar se havia um super favorito (> 70% de votos) e deu o oposto
        is_underdog_win = False
        if total_preds > 0:
            if home_votes / total_preds >= 0.70 and real_outcome in ("away", "draw"):
                is_underdog_win = True
            elif away_votes / total_preds >= 0.70 and real_outcome in ("home", "draw"):
                is_underdog_win = True

        for lp in match_preds:
            pkey = lp.participant_key or normalize_participant_key(lp.participant_name)
            if pkey not in stats:
                continue
                
            res = calculate_live_prediction_points(lp, m, ctx.config)
            pts = res["points"]
            stats[pkey]["points_per_approved_match"][m.match_id] = pts
            
            if res["flags"].get("exact"):
                stats[pkey]["exact_count"] += 1
            if res["flags"].get("outcome"):
                stats[pkey]["outcome_count"] += 1
                if is_zebra:
                    stats[pkey]["zebra_hits"] += 1
                if is_underdog_win:
                    stats[pkey]["underdog_hits"] += 1
                    
            if lp.predicted_home_goals == lp.predicted_away_goals:
                stats[pkey]["draw_count"] += 1

    # Calcular palpites perdidos e sequências de pontuação
    # Ordenar jogos aprovados por data ou ordem para calcular streak
    sorted_approved_matches = sorted(approved_matches, key=lambda x: x.starts_at)
    
    for pkey, p_stats in stats.items():
        # Palpites perdidos
        guessed_ids = {lp.match_id for lp in live_by_participant.get(pkey, []) if lp.match_id in approved_match_ids}
        p_stats["missed_count"] = len(approved_match_ids) - len(guessed_ids)
        
        # Streak (sequência quente)
        max_streak = 0
        current_streak = 0
        for m in sorted_approved_matches:
            pts = p_stats["points_per_approved_match"].get(m.match_id, 0)
            # Se pontuou (mais de 0 pontos), incrementa a sequência
            if pts > 0:
                current_streak += 1
                if current_streak > max_streak:
                    max_streak = current_streak
            else:
                current_streak = 0
        p_stats["streak"] = max_streak

    # 3. Determinar Líderes de Rankings
    # Ranking Clássico
    leader_classic = None
    top3_classic = set()
    try:
        if submissions and official:
            classic_ranks = rank_predictions(submissions, official, ctx.config)
            if classic_ranks:
                leader_classic = normalize_participant_key(classic_ranks[0].participant)
                for r in classic_ranks[1:3]:
                    top3_classic.add(normalize_participant_key(r.participant))
    except Exception:
        pass

    # Ranking Live
    leader_live = None
    top3_live = set()
    try:
        from .live_scoring import calculate_live_ranking
        live_ranks = calculate_live_ranking(live_predictions, matches, ctx.config)
        if live_ranks:
            leader_live = live_ranks[0]["participant_key"]
            for r in live_ranks[1:3]:
                top3_live.add(r["participant_key"])
    except Exception:
        pass

    # 4. Atribuir Badges
    max_exacts = max([s["exact_count"] for s in stats.values()] or [0])
    max_draws = max([s["draw_count"] for s in stats.values()] or [0])
    max_streak_group = max([s["streak"] for s in stats.values()] or [0])
    
    # Campeão Oficial aprovado
    official_champion = official.champion if (official and official.champion) else None

    for pkey, p_stats in stats.items():
        badges_list = []
        
        # 🥇 Líder Atual
        if pkey == leader_classic or pkey == leader_live:
            badges_list.append(Badge("🥇", "Líder Atual", "Está no topo de um dos rankings do bolão!").to_dict())
            
        # 🥉 Top 3
        elif pkey in top3_classic or pkey in top3_live:
            badges_list.append(Badge("🥉", "Pódio do Bolão", "Firme na disputa entre os 3 melhores colocados.").to_dict())
            
        # 🎯 Rei do Placar Exato
        if p_stats["exact_count"] == max_exacts and max_exacts > 0:
            badges_list.append(Badge("🎯", "Rei do Placar Exato", f"Líder de acertos exatos do grupo com {max_exacts} cravadas!").to_dict())
            
        # 🔥 Sequência Quente
        if p_stats["streak"] == max_streak_group and max_streak_group >= 3:
            badges_list.append(Badge("🔥", "Sequência Quente", f"Maior sequência pontuando no grupo: {max_streak_group} jogos seguidos!").to_dict())
            
        # 🐴 Caçador de Zebra
        if p_stats["zebra_hits"] > 0:
            badges_list.append(Badge("🐴", "Caçador de Zebra", f"Acertou {p_stats['zebra_hits']} zebra(s) que quase ninguém no grupo previu!").to_dict())
            
        # 💀 Matador de Favoritos
        if p_stats["underdog_hits"] > 0:
            badges_list.append(Badge("💀", "Matador de Favoritos", "Acertou vitória/empate de zebra derrubando o favoritismo absoluto do grupo.").to_dict())
            
        # 🧊 Frio e Calculista
        if p_stats["draw_count"] == max_draws and max_draws >= 4:
            badges_list.append(Badge("🧊", "Frio e Calculista", f"Estrategista do empate: previu {max_draws} empates no Jogo a Jogo.").to_dict())
            
        # 🏆 Campeão Cravado
        # Procurar submission clássica correspondente
        classic_sub = next((s for s in submissions if normalize_participant_key(s.participant) == pkey), None)
        if official_champion and classic_sub and classic_sub.champion == official_champion:
            badges_list.append(Badge("🏆", "Campeão Cravado", f"Visão de águia! Cravou que {official_champion} seria a seleção campeã.").to_dict())
            
        # 🧙 Profeta do Mata-Mata
        # Se for o maior pontuador de mata-mata no clássico
        # Para simplificar, colocamos para quem tem pontuação de mata-mata no clássico acima de 20 pontos
        if classic_sub and classic_sub.meta.get("knockout_points", 0) > 20:
            badges_list.append(Badge("🧙", "Profeta do Mata-Mata", "Dominou a fase final no clássico com acertos precisos.").to_dict())
            
        # 😭 Esqueceu de Palpitar
        if p_stats["missed_count"] > 0:
            badges_list.append(Badge("😭", "Esqueceu de Palpitar", f"Deixou de enviar palpite em {p_stats['missed_count']} jogo(s) encerrado(s).").to_dict())
            
        # ⚔️ Rei dos Duelos
        # Para quem acertou o maior número de resultados (outcomes) no Jogo a Jogo
        if p_stats["outcome_count"] > 15:
            badges_list.append(Badge("⚔️", "Rei dos Duelos", f"Comprovou consistência com {p_stats['outcome_count']} resultados corretos no live.").to_dict())
            
        # Módulo Brasil Badges (F11)
        from src.bolao.storage import load_brasil_palpites_classicos, load_brasil_palpites_goleadores, load_brasil_resultados_goleadores, load_config
        raw_config = load_config()
        classic_brasil_guesses = load_brasil_palpites_classicos()
        goleadores_palpites = load_brasil_palpites_goleadores()
        goleadores_resultados = load_brasil_resultados_goleadores()
        
        gol_de_ouro_real = None
        for row in goleadores_resultados.values():
            if row.get("primeiro_gol_copa"):
                gol_de_ouro_real = row["primeiro_gol_copa"]
                break
                
        art_br_reais = [x.strip() for x in raw_config.get("artilheiros_reais_brasil", "").split(",") if x.strip()]
        art_ge_reais = [x.strip() for x in raw_config.get("artilheiros_reais_geral", "").split(",") if x.strip()]
        art_ge_reais_clean = [x.split("(")[0].strip() for x in art_ge_reais]
        
        my_classic_br = next((g for g in classic_brasil_guesses if normalize_participant_key(g["participante_nome"]) == pkey), None)
        
        has_gold_hit = False
        if my_classic_br and gol_de_ouro_real and gol_de_ouro_real.lower() not in ("contra", "anulado"):
            from src.bolao.utils import norm_team
            pred_gold = my_classic_br.get("gol_de_ouro")
            if pred_gold and norm_team(pred_gold) == norm_team(gol_de_ouro_real):
                has_gold_hit = True
                
        if has_gold_hit:
            badges_list.append(Badge("🥇", "Gol de Ouro", "Acertou o 1º goleador do Brasil na Copa!").to_dict())
            badges_list.append(Badge("🟢", "Olheiro da CBF", "Acertou o marcador do 1º gol do Brasil na Copa.").to_dict())
            
        has_art_br_hit = False
        if my_classic_br and art_br_reais:
            from src.bolao.live_scoring import calcular_pontos_artilheiro_classico
            pred_art_br = my_classic_br.get("artilheiro_brasil_copa")
            pts_art_br = calcular_pontos_artilheiro_classico(pred_art_br, art_br_reais, raw_config, is_geral=False)
            if pts_art_br > 0:
                has_art_br_hit = True
                
        if has_art_br_hit:
            badges_list.append(Badge("🏅", "Chutômetro de Ouro", "Acertou artilheiro do Brasil na Copa (clássico).").to_dict())
            
        has_art_ge_hit = False
        if my_classic_br and art_ge_reais:
            from src.bolao.live_scoring import calcular_pontos_artilheiro_classico
            pred_art_ge = my_classic_br.get("artilheiro_geral_copa")
            if pred_art_ge and "(" in pred_art_ge:
                pred_art_ge = pred_art_ge.split("(")[0].strip()
            pts_art_ge = calcular_pontos_artilheiro_classico(pred_art_ge, art_ge_reais_clean, raw_config, is_geral=True)
            if pts_art_ge > 0:
                has_art_ge_hit = True
                
        if has_art_br_hit and has_art_ge_hit:
            badges_list.append(Badge("🟣", "Vidente Hexagonal", "Acertou artilheiro geral E artilheiro do Brasil!").to_dict())
            
        g_hits_per_match = {}
        has_craque_palpite = False
        
        my_gps = [gp for gp in goleadores_palpites if normalize_participant_key(gp["participante_nome"]) == pkey]
        for gp in my_gps:
            real_res = goleadores_resultados.get(gp["jogo_id"])
            if real_res:
                from collections import Counter
                real_g = Counter(real_res.get("goleadores_reais", []))
                palp_g = Counter(gp.get("goleadores", []))
                g_hits = sum(min(palp_g.get(k, 0), v) for k, v in real_g.items())
                
                real_a = Counter(real_res.get("assistentes_reais", []))
                palp_a = Counter(gp.get("assistentes", []))
                a_hits = sum(min(palp_a.get(k, 0), v) for k, v in real_a.items())
                
                if g_hits >= 1:
                    g_hits_per_match[gp["jogo_id"]] = g_hits
                if g_hits >= 1 and a_hits >= 1:
                    has_craque_palpite = True
                    
        if has_craque_palpite:
            badges_list.append(Badge("🟡", "Craque do Palpite", "Acertou goleador + assistente no mesmo jogo!").to_dict())
            
        if len(g_hits_per_match) >= 3:
            badges_list.append(Badge("🔵", "Analista da Canarinha", "Acertou ≥1 goleador nos 3 jogos do grupo.").to_dict())
            
        leader_canarinho = None
        try:
            brazil_matches = [m for m in matches if ("Brasil" in m.home_team or "Brasil" in m.away_team) and m.status == "result_approved"]
            if len(brazil_matches) >= 3:
                can_points = {}
                for lp in live_predictions:
                    if lp.match_id in {m.match_id for m in brazil_matches}:
                        pk = lp.participant_key or normalize_participant_key(lp.participant_name)
                        m = next(x for x in brazil_matches if x.match_id == lp.match_id)
                        res = calculate_live_prediction_points(lp, m, ctx.config)
                        can_points[pk] = can_points.get(pk, 0) + res["points"]
                for gp in goleadores_palpites:
                    if gp["jogo_id"] in {m.match_id for m in brazil_matches}:
                        pk = normalize_participant_key(gp["participante_nome"])
                        real_res = goleadores_resultados.get(gp["jogo_id"])
                        if real_res:
                            from src.bolao.live_scoring import calcular_pontos_goleadores
                            pts = calcular_pontos_goleadores(
                                gp.get("goleadores", []),
                                gp.get("assistentes", []),
                                real_res.get("goleadores_reais", []),
                                real_res.get("assistentes_reais", []),
                                ctx.config
                            )["total"]
                            can_points[pk] = can_points.get(pk, 0) + pts
                if can_points:
                    leader_canarinho = max(can_points, key=can_points.get)
        except Exception:
            pass
            
        if leader_canarinho and pkey == leader_canarinho:
            badges_list.append(Badge("🥈", "Canarinho de Prata", "Ficou em 1º no Ranking Canarinho!").to_dict())
            
        achievements[pkey] = badges_list
        
    return achievements
