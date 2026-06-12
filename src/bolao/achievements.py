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
            
        achievements[pkey] = badges_list
        
    return achievements
