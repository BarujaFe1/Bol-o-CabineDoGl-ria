from __future__ import annotations

import streamlit as st
import pandas as pd
from .storage import load_matches, load_live_predictions, load_submissions, load_official, load_config, load_app_data_cached, sync_official_results_to_matches
from .scoring import rank_predictions
from .live_scoring import calculate_live_ranking, calculate_live_prediction_points
from .ui_components import podium, render_badge, render_empty_state
from .utils import normalize_participant_key
from .achievements import calculate_achievements

def render_rankings_tabs(is_admin: bool = False, score_config = None) -> None:
    synced = sync_official_results_to_matches()
    if synced > 0:
        st.cache_data.clear()

    config = load_config()
    ctx = load_app_data_cached()
    submissions = ctx.submissions
    official = ctx.official
    matches = ctx.matches
    live_preds = ctx.live_predictions
    
    if synced > 0:
        st.toast(f"✅ Resultados oficiais sincronizados: {synced} jogos atualizados!", icon="⚽")
    
    # Calcular conquistas sociais em tempo real
    achievements = calculate_achievements(ctx)

    st.markdown("### 🏆 Rankings do Bolão")
    st.caption("Acompanhe a classificação em tempo real nos diferentes modos da Copa.")

    # KPI Summary Grid
    col_k1, col_k2, col_k3 = st.columns(3)
    with col_k1:
        st.metric("Total Participantes (Clássico)", len(submissions))
    with col_k2:
        unique_live = len(set(lp.participant_key or normalize_participant_key(lp.participant_name) for lp in live_preds))
        st.metric("Total Participantes (Jogo a Jogo)", unique_live)
    with col_k3:
        approved_count = len([m for m in matches if m.status == "result_approved"])
        st.metric("Jogos Concluídos (Jogo a Jogo)", f"{approved_count}/{len(matches)}")

    ranking_tabs = st.tabs([
        "Classic Cup (Modo Clássico)", 
        "Match Day (Jogo a Jogo)", 
        "Ranking Geral Combinado",
        "Por Rodada / Fase",
        "Estatísticas"
    ])

    # Se precisar instanciar a configuração de score
    if score_config is None:
        from .scoring import ScoreConfig
        from .constants import DEFAULT_WEIGHTED_RULES, DEFAULT_UNIFORM_RULES, DEFAULT_V2_RULES
        score_config = ScoreConfig(
            mode=config.get("scoring_mode", "v2"),
            weighted_rules=config.get("weighted_rules", dict(DEFAULT_WEIGHTED_RULES)),
            uniform_rules=config.get("uniform_rules", dict(DEFAULT_UNIFORM_RULES)),
            v2_rules=config.get("v2_rules", dict(DEFAULT_V2_RULES)),
        )

    # 1. Classic Cup Tab
    with ranking_tabs[0]:
        st.markdown("#### 🏆 Classic Cup — Palpite pré-Copa")
        st.caption("Participantes que preencheram a cartela inteira antes do início do torneio.")
        
        if not official:
            st.info("O resultado oficial do Modo Clássico ainda não foi cadastrado. Exibindo apenas a lista de inscritos por ordem de envio.")
            if submissions:
                classic_list = []
                for p in submissions:
                    pkey = normalize_participant_key(p.participant)
                    user_badges = achievements.get(pkey, [])
                    badge_str = " ".join([b['icon'] for b in user_badges]) if user_badges else "—"
                    classic_list.append({
                        "Participante": p.participant, 
                        "Enviado em": p.submitted_at.replace("T", " ") if p.submitted_at else "—", 
                        "Código": p.submission_id[:8] if p.submission_id else "—",
                        "Conquistas": badge_str
                    })
                
                # Desktop view
                st.markdown('<div class="desktop-only">', unsafe_allow_html=True)
                st.dataframe(pd.DataFrame(classic_list), width="stretch", hide_index=True)
                st.markdown('</div>', unsafe_allow_html=True)

                # Mobile view
                st.markdown('<div class="mobile-only mobile-card-grid">', unsafe_allow_html=True)
                for item in classic_list:
                    st.markdown(
                        f"""
                        <div class="card" style="margin-bottom: 12px; padding: 16px;">
                            <div style="font-weight: bold; font-size: 15px; color: var(--ink);">{item['Participante']}</div>
                            <div style="font-size: 13px; color: var(--muted); margin-top: 4px;">
                                ⏱️ Enviado: {item['Enviado em']} | 🔑 Código: {item['Código']}
                                <br>🎖️ Conquistas: {item['Conquistas']}
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
                st.markdown('</div>', unsafe_allow_html=True)
            else:
                st.info("Nenhum palpite clássico enviado ainda.")
        else:
            classic_scores = rank_predictions(submissions, official, score_config)
            podium(classic_scores)
            
            search_name = st.text_input("🔍 Buscar participante (Clássico)", placeholder="Digite o nome...", key="search_classic_name")
            filtered = [s for s in classic_scores if search_name.lower() in s.participant.lower()] if search_name else classic_scores
            
            # Render Classic Ranking DataFrame
            rows = []
            for idx, s in enumerate(filtered, start=1):
                pkey = normalize_participant_key(s.participant)
                user_badges = achievements.get(pkey, [])
                badge_str = " ".join([b['icon'] for b in user_badges]) if user_badges else "—"
                rows.append({
                    "Posição": idx,
                    "Participante": s.participant,
                    "Pontos": s.total,
                    "Fase de Grupos": s.group_points,
                    "Mata-Mata": s.knockout_points,
                    "Campeão correto": "Sim" if s.champion_hit else "Não",
                    "Placares Exatos": s.exact_scores,
                    "Conquistas": badge_str
                })
            
            # Desktop view
            st.markdown('<div class="desktop-only">', unsafe_allow_html=True)
            st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
            st.markdown('</div>', unsafe_allow_html=True)

            # Mobile view
            st.markdown('<div class="mobile-only mobile-card-grid">', unsafe_allow_html=True)
            for r in rows:
                st.markdown(
                    f"""
                    <div class="card" style="margin-bottom: 12px; padding: 16px; border-left: 5px solid var(--green);">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                            <span style="font-weight: 800; font-size: 16px; color: var(--ink);">{r['Posição']}º. {r['Participante']}</span>
                            <span class="badge success" style="font-size:12px; font-weight: bold; padding: 4px 8px;">{r['Pontos']} pts</span>
                        </div>
                        <div style="font-size: 13px; color: var(--muted); line-height: 1.4;">
                            📋 Grupos: {r['Fase de Grupos']} pts | ⚔️ Mata-Mata: {r['Mata-Mata']} pts
                            <br>🏆 Campeã Correta: {r['Campeão correto']} | 🎯 Exatos: {r['Placares Exatos']}
                            <br>🎖️ Conquistas: {r['Conquistas']}
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
            st.markdown('</div>', unsafe_allow_html=True)

    # 2. Match Day Tab
    with ranking_tabs[1]:
        st.markdown("#### 🎯 Match Day — Jogo a Jogo")
        st.caption("Ranking baseado no acerto individual de placares rodada a rodada.")

        live_scores = calculate_live_ranking(live_preds, matches, config)
        if not live_scores:
            st.info("Nenhum palpite computado ou jogos ainda não foram encerrados no Modo Jogo a Jogo.")
        else:
            # Render Podium
            st.markdown("##### 🎖️ Top 3 — Jogo a Jogo")
            podium(live_scores)

            st.markdown("<br>", unsafe_allow_html=True)
            search_live = st.text_input("🔍 Buscar participante (Jogo a Jogo)", placeholder="Digite o nome...", key="search_live_name")
            filtered_live = [s for s in live_scores if search_live.lower() in s["participant"].lower()] if search_live else live_scores

            # Build table with achievements
            live_rows = []
            for s in filtered_live:
                pkey = s["participant_key"]
                user_badges = achievements.get(pkey, [])
                badge_str = " ".join([f"{b['icon']} {b['name']}" for b in user_badges]) if user_badges else "—"
                
                live_rows.append({
                    "Posição": s["position"],
                    "Participante": s["participant"],
                    "Pontos": s["total"],
                    "Placares Exatos": s["exact_scores"],
                    "Acertos Vencedor": s["outcomes"],
                    "Palpites Salvos": s["predictions_count"],
                    "Palpites Perdidos": s["missed_predictions"],
                    "Aproveitamento": f"{int(s['hit_rate'] * 100)}%",
                    "Conquistas": badge_str
                })
            
            # Desktop view
            st.markdown('<div class="desktop-only">', unsafe_allow_html=True)
            st.dataframe(pd.DataFrame(live_rows), width="stretch", hide_index=True)
            st.markdown('</div>', unsafe_allow_html=True)

            # Mobile view
            st.markdown('<div class="mobile-only mobile-card-grid">', unsafe_allow_html=True)
            for r in live_rows:
                st.markdown(
                    f"""
                    <div class="card" style="margin-bottom: 12px; padding: 16px; border-left: 5px solid var(--green);">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                            <span style="font-weight: 800; font-size: 16px; color: var(--ink);">{r['Posição']}º. {r['Participante']}</span>
                            <span class="badge success" style="font-size:12px; font-weight: bold; padding: 4px 8px;">{r['Pontos']} pts</span>
                        </div>
                        <div style="font-size: 13px; color: var(--muted); line-height: 1.4;">
                            🎯 Placares Exatos: {r['Placares Exatos']} | 🏁 Acertos Vencedor: {r['Acertos Vencedor']}
                            <br>📊 Palpites: {r['Palpites Salvos']} salvos / {r['Palpites Perdidos']} perdidos
                            <br>📈 Aproveitamento: {r['Aproveitamento']}
                            <br>🎖️ Conquistas: {r['Conquistas']}
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
            st.markdown('</div>', unsafe_allow_html=True)

            # Details expansion
            st.markdown("<br>", unsafe_allow_html=True)
            selected_user = st.selectbox("Selecione um participante para ver o detalhamento de palpites jogo a jogo:", options=[s["participant"] for s in live_scores], key="live_detail_user")
            user_key = normalize_participant_key(selected_user)
            
            user_preds = [p for p in live_preds if (p.participant_key or normalize_participant_key(p.participant_name)) == user_key]
            
            det_rows = []
            for p in user_preds:
                m = next((m for m in matches if m.match_id == p.match_id), None)
                if m:
                    res = calculate_live_prediction_points(p, m, config)
                    det_rows.append({
                        "Jogo": f"{m.home_team} x {m.away_team}",
                        "Fase/Rodada": m.round_label,
                        "Palpite": f"{p.predicted_home_goals} x {p.predicted_away_goals}",
                        "Resultado Oficial": f"{m.official_home_goals} x {m.official_away_goals}" if m.status == "result_approved" else "Aguardando",
                        "Pontos Ganhos": res["points"] if m.status == "result_approved" else None,
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
            classic_scores = rank_predictions(submissions, official, score_config)
            live_scores = calculate_live_ranking(live_preds, matches, config)
            
            combined_rules = config.get("combined_ranking", {})
            classic_weight = combined_rules.get("classic_weight", 1.0)
            live_weight = combined_rules.get("live_weight", 1.0)
            include_classic_only = combined_rules.get("include_classic_only_players", True)
            include_live_only = combined_rules.get("include_live_only_players", True)
            
            # Combine metrics by key
            classic_dict = {normalize_participant_key(s.participant): s for s in classic_scores}
            live_dict = {s["participant_key"]: s for s in live_scores}
            
            all_keys = set(classic_dict.keys()).union(live_dict.keys())
            
            combined_list = []
            for pkey in all_keys:
                c_score = classic_dict.get(pkey)
                l_score = live_dict.get(pkey)
                
                # Regras de inclusão baseadas em config
                if c_score and not l_score and not include_classic_only:
                    continue
                if l_score and not c_score and not include_live_only:
                    continue
                    
                name = c_score.participant if c_score else (l_score["participant"] if l_score else "—")
                c_pts = c_score.total if c_score else 0
                l_pts = l_score["total"] if l_score else 0
                
                combined_pts = c_pts * classic_weight + l_pts * live_weight
                
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
                pkey = s["participant_key"]
                user_badges = achievements.get(pkey, [])
                badge_str = " ".join([b['icon'] for b in user_badges]) if user_badges else "—"
                
                comb_rows.append({
                    "Posição": idx,
                    "Participante": s["participant"],
                    "Pontos Clássico": s["classic_points"],
                    "Pontos Jogo a Jogo": s["live_points"],
                    "Pontos Combinados": s["total"],
                    "Conquistas": badge_str
                })
            
            # Desktop view
            st.markdown('<div class="desktop-only">', unsafe_allow_html=True)
            st.dataframe(pd.DataFrame(comb_rows), width="stretch", hide_index=True)
            st.markdown('</div>', unsafe_allow_html=True)

            # Mobile view
            st.markdown('<div class="mobile-only mobile-card-grid">', unsafe_allow_html=True)
            for r in comb_rows:
                st.markdown(
                    f"""
                    <div class="card" style="margin-bottom: 12px; padding: 16px; border-left: 5px solid var(--gold);">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                            <span style="font-weight: 800; font-size: 16px; color: var(--ink);">{r['Posição']}º. {r['Participante']}</span>
                            <span class="badge success" style="font-size:12px; font-weight: bold; padding: 4px 8px;">{r['Pontos Combinados']} pts</span>
                        </div>
                        <div style="font-size: 13px; color: var(--muted); line-height: 1.4;">
                            📋 Pontos Clássico: {r['Pontos Clássico']} pts | 🎯 Pontos Jogo a Jogo: {r['Pontos Jogo a Jogo']} pts
                            <br>🎖️ Conquistas: {r['Conquistas']}
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
            st.markdown('</div>', unsafe_allow_html=True)

    # 4. Por Rodada / Fase Tab
    with ranking_tabs[3]:
        st.markdown("#### 📅 Classificação Filtrada — Jogo a Jogo")
        st.caption("Visualize a classificação específica de uma rodada ou fase do mata-mata no Jogo a Jogo.")
        
        # Filtros de rodadas existentes
        all_rounds = sorted(list(set(m.round_label for m in matches if m.status == "result_approved")))
        all_phases = sorted(list(set(m.phase for m in matches if m.status == "result_approved")))
        
        filter_type = st.radio("Escolha o filtro", ["Por Rodada", "Por Fase"], horizontal=True, key="filter_round_phase_type")
        
        filter_option = "Nenhuma"
        if filter_type == "Por Rodada":
            if not all_rounds:
                st.info("Nenhuma rodada concluída com resultados oficiais aprovados ainda.")
            else:
                filter_option = st.selectbox("Selecione a Rodada", all_rounds, key="filter_round_selection")
        else:
            if not all_phases:
                st.info("Nenhuma fase concluída com resultados oficiais aprovados ainda.")
            else:
                filter_option = st.selectbox("Selecione a Fase", all_phases, key="filter_phase_selection")
                
        if filter_option != "Nenhuma" and (all_rounds or all_phases):
            # Filtrar jogos correspondentes
            if filter_type == "Por Rodada":
                selected_matches = [m for m in matches if m.round_label == filter_option and m.status == "result_approved"]
            else:
                selected_matches = [m for m in matches if m.phase == filter_option and m.status == "result_approved"]
                
            selected_match_ids = {m.match_id for m in selected_matches}
            
            # Recalcular ranking apenas para esses palpites
            filtered_preds = [lp for lp in live_preds if lp.match_id in selected_match_ids]
            
            sub_live_scores = calculate_live_ranking(filtered_preds, selected_matches, config)
            
            if not sub_live_scores:
                st.info("Nenhum palpite para esta seleção de jogos.")
            else:
                st.markdown(f"##### Ranking filtrado: {filter_option}")
                sub_rows = []
                for s in sub_live_scores:
                    pkey = s["participant_key"]
                    user_badges = achievements.get(pkey, [])
                    badge_str = " ".join([b['icon'] for b in user_badges]) if user_badges else "—"
                    
                    sub_rows.append({
                        "Posição": s["position"],
                        "Participante": s["participant"],
                        "Pontos": s["total"],
                        "Placares Exatos": s["exact_scores"],
                        "Conquistas": badge_str
                    })
                
                # Desktop view
                st.markdown('<div class="desktop-only">', unsafe_allow_html=True)
                st.dataframe(pd.DataFrame(sub_rows), width="stretch", hide_index=True)
                st.markdown('</div>', unsafe_allow_html=True)

                # Mobile view
                st.markdown('<div class="mobile-only mobile-card-grid">', unsafe_allow_html=True)
                for r in sub_rows:
                    st.markdown(
                        f"""
                        <div class="card" style="margin-bottom: 12px; padding: 16px; border-left: 5px solid var(--green);">
                            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                                <span style="font-weight: 800; font-size: 16px; color: var(--ink);">{r['Posição']}º. {r['Participante']}</span>
                                <span class="badge success" style="font-size:12px; font-weight: bold; padding: 4px 8px;">{r['Pontos']} pts</span>
                            </div>
                            <div style="font-size: 13px; color: var(--muted); line-height: 1.4;">
                                🎯 Placares Exatos: {r['Placares Exatos']}
                                <br>🎖️ Conquistas: {r['Conquistas']}
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
                st.markdown('</div>', unsafe_allow_html=True)

    # 5. Estatísticas Tab
    with ranking_tabs[4]:
        st.markdown("#### 📊 Estatísticas Gerais do Grupo")
        st.caption("Visão agregada e insights dos palpites enviados para a Copa do Mundo 2026.")
        
        col_s1, col_s2, col_s3 = st.columns(3)
        with col_s1:
            total_live_preds = len(live_preds)
            st.metric("Total de palpites individuais", total_live_preds)
        with col_s2:
            exact_count = 0
            for lp in live_preds:
                m = next((m for m in matches if m.match_id == lp.match_id), None)
                if m and m.status == "result_approved" and m.official_home_goals is not None and m.official_away_goals is not None:
                    res = calculate_live_prediction_points(lp, m, config)
                    if res["flags"].get("exact"):
                        exact_count += 1
            pct_exatos = (exact_count / len([lp for lp in live_preds if next((m for m in matches if m.match_id == lp.match_id), None) and next((m for m in matches if m.match_id == lp.match_id)).status == "result_approved"])) * 100 if len(live_preds) > 0 and exact_count > 0 else 0
            st.metric("Total de Placares Exatos cravados", f"{exact_count} ({pct_exatos:.1f}%)")
        with col_s3:
            # Média de gols palpitados
            avg_goals = sum(lp.predicted_home_goals + lp.predicted_away_goals for lp in live_preds) / total_live_preds if total_live_preds > 0 else 0
            st.metric("Média de gols por palpite", f"{avg_goals:.2f}")
            
        st.markdown("#### 🏆 Campeão mais apostado (Modo Clássico)")
        champs_list = [p.champion for p in submissions if p.champion]
        if champs_list:
            champ_counts = pd.Series(champs_list).value_counts()
            champ_df = pd.DataFrame({"Seleção": champ_counts.index, "Palpites": champ_counts.values})
            st.dataframe(champ_df, width="stretch", hide_index=True)
        else:
            st.info("Nenhuma campeã selecionada pelos participantes ainda.")
