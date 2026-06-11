from __future__ import annotations

import streamlit as st
import pandas as pd
from .storage import load_matches, load_live_predictions, load_submissions, load_official, load_config
from .scoring import rank_predictions
from .live_scoring import calculate_live_ranking, calculate_live_prediction_points
from .ui_components import podium, render_badge
from .utils import normalize_participant_key

def render_rankings_tabs(is_admin: bool = False, score_config = None) -> None:
    config = load_config()
    submissions = load_submissions()
    official = load_official()
    matches = load_matches()
    live_preds = load_live_predictions()

    st.markdown("### 🏆 Rankings do Bolão")
    st.caption("Acompanhe a classificação em tempo real nos diferentes modos da Copa.")

    # KPI Summary Grid
    col_k1, col_k2, col_k3 = st.columns(3)
    with col_k1:
        st.metric("Total Participantes (Clássico)", len(submissions))
    with col_k2:
        st.metric("Total Participantes (Jogo a Jogo)", len(set(p.participant_key for p in live_preds)))
    with col_k3:
        approved_count = len([m for m in matches if m.status == "result_approved"])
        st.metric("Jogos Concluídos (Jogo a Jogo)", f"{approved_count}/{len(matches)}")

    ranking_tabs = st.tabs(["Classic Cup (Modo Clássico)", "Match Day (Jogo a Jogo)", "Ranking Geral Combinado"])

    # 1. Classic Cup Tab
    with ranking_tabs[0]:
        st.markdown("#### 🏆 Classic Cup — Palpite pré-Copa")
        st.caption("Participantes que preencheram a cartela inteira antes do início do torneio.")
        
        if not official:
            st.info("O resultado oficial do Modo Clássico ainda não foi cadastrado. Exibindo apenas a lista de inscritos por ordem de envio.")
            if submissions:
                classic_list = [{"Participante": p.participant, "Enviado em": p.submitted_at.replace("T", " ") if p.submitted_at else "—", "Código": p.submission_id[:8]} for p in submissions]
                st.dataframe(pd.DataFrame(classic_list), width="stretch", hide_index=True)
            else:
                st.info("Nenhum palpite clássico enviado ainda.")
        else:
            if score_config is None:
                from .scoring import ScoreConfig
                from .constants import DEFAULT_WEIGHTED_RULES, DEFAULT_UNIFORM_RULES, DEFAULT_V2_RULES
                cfg = load_config()
                score_config = ScoreConfig(
                    mode=cfg.get("scoring_mode", "v2"),
                    weighted_rules=cfg.get("weighted_rules", dict(DEFAULT_WEIGHTED_RULES)),
                    uniform_rules=cfg.get("uniform_rules", dict(DEFAULT_UNIFORM_RULES)),
                    v2_rules=cfg.get("v2_rules", dict(DEFAULT_V2_RULES)),
                )
            
            classic_scores = rank_predictions(submissions, official, score_config)
            podium(classic_scores)
            
            search_name = st.text_input("🔍 Buscar participante (Clássico)", placeholder="Digite o nome...", key="search_classic_name")
            filtered = [s for s in classic_scores if search_name.lower() in s.participant.lower()] if search_name else classic_scores
            
            # Render Classic Ranking DataFrame
            rows = []
            for idx, s in enumerate(filtered, start=1):
                rows.append({
                    "Posição": idx,
                    "Participante": s.participant,
                    "Pontos": s.total,
                    "Fase de Grupos": s.group_points,
                    "Mata-Mata": s.knockout_points,
                    "Campeão correto": "Sim" if s.champion_hit else "Não",
                    "Placares Exatos": s.exact_scores
                })
            st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)

    # 2. Match Day Tab
    with ranking_tabs[1]:
        st.markdown("#### 🎯 Match Day — Jogo a Jogo")
        st.caption("Ranking baseado no acerto individual de placares rodada a rodada.")
        
        live_scores = calculate_live_ranking(live_preds, matches, config)
        if not live_scores:
            st.info("Nenhum palpite computado ou jogos ainda não foram encerrados no Modo Jogo a Jogo.")
        else:
            # Render Podium (custom implementation for list of dicts)
            st.markdown("##### 🎖️ Top 3 — Jogo a Jogo")
            pod1, pod2, pod3 = st.columns(3)
            with pod2:
                if len(live_scores) >= 1:
                    st.markdown(f"<div style='text-align:center; padding: 15px; border-radius:12px; background: #FFF8E7; border: 2px solid #D8A94A;'>🥇 <b>{live_scores[0]['participant']}</b><br><span style='font-size:20px; font-weight:bold; color:#176B4D;'>{live_scores[0]['total']} pts</span><br><small>{live_scores[0]['tie_breaker']}</small></div>", unsafe_allow_html=True)
            with pod1:
                if len(live_scores) >= 2:
                    st.markdown(f"<div style='text-align:center; padding: 15px; border-radius:12px; background: #F2F2F2; border: 1px solid #CCCCCC;'>🥈 <b>{live_scores[1]['participant']}</b><br><span style='font-size:18px; font-weight:bold; color:#176B4D;'>{live_scores[1]['total']} pts</span><br><small>{live_scores[1]['tie_breaker']}</small></div>", unsafe_allow_html=True)
            with pod3:
                if len(live_scores) >= 3:
                    st.markdown(f"<div style='text-align:center; padding: 15px; border-radius:12px; background: #FDF1E6; border: 1px solid #E6A23C;'>🥉 <b>{live_scores[2]['participant']}</b><br><span style='font-size:16px; font-weight:bold; color:#176B4D;'>{live_scores[2]['total']} pts</span><br><small>{live_scores[2]['tie_breaker']}</small></div>", unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)
            search_live = st.text_input("🔍 Buscar participante (Jogo a Jogo)", placeholder="Digite o nome...", key="search_live_name")
            filtered_live = [s for s in live_scores if search_live.lower() in s["participant"].lower()] if search_live else live_scores

            # Build table with badges
            live_rows = []
            for s in filtered_live:
                # Award badges
                badges = []
                if s["position"] == 1:
                    badges.append("🥇 Líder")
                if s["exact_scores"] >= 5:
                    badges.append("🎯 Rei do Exato")
                if s["hit_rate"] >= 0.65 and s["predictions_count"] >= 5:
                    badges.append("🔥 Mão Quente")
                if s["missed_predictions"] >= 3:
                    badges.append("😭 Esqueceu")
                
                badge_str = " ".join(badges) if badges else "—"
                
                live_rows.append({
                    "Posição": s["position"],
                    "Participante": s["participant"],
                    "Pontos": s["total"],
                    "Placares Exatos": s["exact_scores"],
                    "Acertos Vencedor": s["outcomes"],
                    "Palpites Salvos": s["predictions_count"],
                    "Palpites Perdidos": s["missed_predictions"],
                    "Aproveitamento": f"{int(s['hit_rate'] * 100)}%",
                    "Estatutos / Conquistas": badge_str
                })
            
            st.dataframe(pd.DataFrame(live_rows), width="stretch", hide_index=True)

            # Details expansion
            st.markdown("<br>", unsafe_allow_html=True)
            selected_user = st.selectbox("Selecione um participante para ver o detalhamento de palpites jogo a jogo:", options=[s["participant"] for s in live_scores])
            user_key = normalize_participant_key(selected_user)
            
            user_preds = [p for p in live_preds if p.participant_key == user_key]
            
            det_rows = []
            approved_matches = {m.match_id: m for m in matches if m.status == "result_approved"}
            for p in user_preds:
                m = next((m for m in matches if m.match_id == p.match_id), None)
                if m:
                    res = calculate_live_prediction_points(p, m, config)
                    det_rows.append({
                        "Jogo": f"{m.home_team} x {m.away_team}",
                        "Palpite": f"{p.predicted_home_goals} x {p.predicted_away_goals}",
                        "Resultado Oficial": f"{m.official_home_goals} x {m.official_away_goals}" if m.status == "result_approved" else "Aguardando",
                        "Pontos Ganhos": res["points"] if m.status == "result_approved" else "—",
                        "Breakdown": " · ".join(res["breakdown"]) if m.status == "result_approved" else "Pendente"
                    })
            if det_rows:
                st.dataframe(pd.DataFrame(det_rows), width="stretch", hide_index=True)
            else:
                st.info("Nenhum palpite enviado por este participante ainda.")

    # 3. Combined Ranking Tab
    with ranking_tabs[2]:
        st.markdown("#### 🌟 Ranking Geral Combinado")
        st.caption("Classificação geral que unifica os pontos do Modo Clássico e do Modo Jogo a Jogo.")
        
        combined_enabled = config.get("combined_ranking_enabled", False)
        if not combined_enabled:
            st.warning("⚠️ O Ranking Geral Combinado ainda não está ativado. O administrador pode ativá-lo e configurar os pesos nas Configurações.")
        elif not official:
            st.info("O resultado oficial clássico é necessário para computar o ranking geral.")
        else:
            # Load rankings
            if score_config is None:
                from .scoring import ScoreConfig
                from .constants import DEFAULT_WEIGHTED_RULES, DEFAULT_UNIFORM_RULES, DEFAULT_V2_RULES
                score_config = ScoreConfig(
                    mode=config.get("scoring_mode", "v2"),
                    weighted_rules=config.get("weighted_rules", dict(DEFAULT_WEIGHTED_RULES)),
                    uniform_rules=config.get("uniform_rules", dict(DEFAULT_UNIFORM_RULES)),
                    v2_rules=config.get("v2_rules", dict(DEFAULT_V2_RULES)),
                )
            classic_scores = rank_predictions(submissions, official, score_config)
            live_scores = calculate_live_ranking(live_preds, matches, config)
            
            classic_weights = config.get("combined_ranking_weights", {}).get("classic", 1.0)
            live_weights = config.get("combined_ranking_weights", {}).get("live", 1.0)
            
            # Combine metrics by key
            classic_dict = {normalize_participant_key(s.participant): s for s in classic_scores}
            live_dict = {s["participant_key"]: s for s in live_scores}
            
            all_keys = set(classic_dict.keys()).union(live_dict.keys())
            
            combined_list = []
            for pkey in all_keys:
                c_score = classic_dict.get(pkey)
                l_score = live_dict.get(pkey)
                
                name = c_score.participant if c_score else (l_score["participant"] if l_score else "—")
                c_pts = c_score.total if c_score else 0
                l_pts = l_score["total"] if l_score else 0
                
                combined_pts = c_pts * classic_weights + l_pts * live_weights
                
                combined_list.append({
                    "participant": name,
                    "participant_key": pkey,
                    "classic_points": c_pts,
                    "live_points": l_pts,
                    "total": combined_pts
                })
                
            # Sort combined ranking
            combined_list.sort(key=lambda s: (
                -s["total"],
                -s["classic_points"],
                -s["live_points"],
                s["participant"].lower()
            ))
            
            # Build combined table rows
            comb_rows = []
            for idx, s in enumerate(combined_list, start=1):
                comb_rows.append({
                    "Posição": idx,
                    "Participante": s["participant"],
                    "Pontos Clássico": s["classic_points"],
                    "Pontos Jogo a Jogo": s["live_points"],
                    "Pontos Combinados": s["total"]
                })
            
            st.dataframe(pd.DataFrame(comb_rows), width="stretch", hide_index=True)
