from __future__ import annotations

import streamlit as st
import pandas as pd
try:
    import plotly.express as px
    import plotly.graph_objects as go
    _HAS_PLOTLY = True
except ImportError:
    _HAS_PLOTLY = False
from .storage import load_matches, load_live_predictions, load_submissions, load_official, load_config, load_app_data_cached, sync_official_results_to_matches
from .scoring import rank_predictions
from .live_scoring import calculate_live_ranking, calculate_live_prediction_points
from .ui_components import podium, render_badge, render_empty_state, render_responsive_table
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
        "Match Day (Jogo a Jogo)", 
        "Classic Cup (Modo Clássico)", 
        "Ranking Geral Combinado",
        "Por Rodada / Fase",
        "🇧🇷 Canarinho",
        "📈 Evolução",
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
    with ranking_tabs[1]:
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
                
                def render_classic_inscrito_card(item):
                    from src.bolao.utils import avatar_url
                    p_avatar = avatar_url(item['Participante'])
                    st.markdown(
                        f"""
                        <div class="card" style="margin-bottom: 12px; padding: 16px;">
                            <div style="display: flex; align-items: center; gap: 8px; font-weight: bold; font-size: 15px; color: var(--ink);">
                                <img src="{p_avatar}" style="width: 32px; height: 32px; border-radius: 50%;" />
                                {item['Participante']}
                            </div>
                            <div style="font-size: 13px; color: var(--muted); margin-top: 4px;">
                                ⏱️ Enviado: {item['Enviado em']} | 🔑 Código: {item['Código']}
                                <br>🎖️ Conquistas: {item['Conquistas']}
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
                render_responsive_table(pd.DataFrame(classic_list), render_classic_inscrito_card, "classic_inscritos")
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
            
            def render_classic_ranking_card(r):
                from src.bolao.utils import avatar_url
                p_avatar = avatar_url(r['Participante'])
                st.markdown(
                    f"""
                    <div class="card" style="margin-bottom: 12px; padding: 16px; border-left: 5px solid var(--green);">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                            <div style="display: flex; align-items: center; gap: 8px;">
                                <img src="{p_avatar}" style="width: 32px; height: 32px; border-radius: 50%;" />
                                <span style="font-weight: 800; font-size: 16px; color: var(--ink);">{r['Posição']}º. {r['Participante']}</span>
                            </div>
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
            render_responsive_table(pd.DataFrame(rows), render_classic_ranking_card, "classic_ranking")

    # 2. Match Day Tab
    with ranking_tabs[0]:
        st.markdown("#### 🎯 Match Day — Jogo a Jogo")
        st.caption("Ranking baseado no acerto individual de placares rodada a rodada.")

        live_scores = calculate_live_ranking(live_preds, matches, config)
        if not live_scores:
            st.info("Nenhum palpite computado ou jogos ainda não foram encerrados no Modo Jogo a Jogo.")
        else:
            # Render Podium
            st.markdown("##### 🎖️ Top 3 — Jogo a Jogo")
            podium(live_scores)

            # ── Bar Chart: Points Distribution ──
            st.markdown("##### 📊 Distribuição de Pontos")
            df_chart = pd.DataFrame(live_scores)
            if _HAS_PLOTLY:
                fig_bar = px.bar(
                    df_chart,
                    x="participant",
                    y="total",
                    color="total",
                    color_continuous_scale="viridis",
                    labels={"participant": "Participante", "total": "Pontos"},
                    text="total",
                    height=350,
                )
                fig_bar.update_traces(textposition="outside")
                fig_bar.update_layout(
                    plot_bgcolor="rgba(0,0,0,0)",
                    paper_bgcolor="rgba(0,0,0,0)",
                    font_color="#e0e0e0",
                    xaxis_tickangle=-45,
                    showlegend=False,
                )
                st.plotly_chart(fig_bar, use_container_width=True)
            else:
                st.dataframe(df_chart[["participant", "total"]].rename(columns={"participant": "Participante", "total": "Pontos"}), width="stretch", hide_index=True)

            # ── Detailed Stats per participant ──
            st.markdown("##### 📈 Estatísticas por Participante")
            stats_rows = []
            for s in live_scores:
                pkey = s["participant_key"]
                user_preds = [p for p in live_preds if (p.participant_key or normalize_participant_key(p.participant_name)) == pkey]
                total_pred_goals = sum(p.predicted_home_goals + p.predicted_away_goals for p in user_preds)
                correct_outcomes = s["outcomes"]
                approved_count = s["possible_matches"]
                user_badges = achievements.get(pkey, [])
                badge_str = " ".join([f"{b['icon']}" for b in user_badges[:3]]) if user_badges else "—"

                # Count how many predictions were correct in different categories
                gols_mandante_certos = 0
                gols_visitante_certos = 0
                diff_certos = 0
                for p in user_preds:
                    m = next((mm for mm in matches if mm.match_id == p.match_id), None)
                    if m and m.status == "result_approved" and m.official_home_goals is not None:
                        if p.predicted_home_goals == m.official_home_goals:
                            gols_mandante_certos += 1
                        if p.predicted_away_goals == m.official_away_goals:
                            gols_visitante_certos += 1
                        if (p.predicted_home_goals - p.predicted_away_goals) == (m.official_home_goals - m.official_away_goals):
                            diff_certos += 1

                stats_rows.append({
                    "Participante": s["participant"],
                    "Pontos": s["total"],
                    "🎯 Exatos": s["exact_scores"],
                    "🏁 Vencedor": correct_outcomes,
                    "🥅 Gols Mandante": gols_mandante_certos,
                    "🥅 Gols Visitante": gols_visitante_certos,
                    "📊 Saldo": diff_certos,
                    "📈 Aprov.": f"{int(s['hit_rate'] * 100)}%",
                    "🎖️": badge_str,
                })

            def render_stats_card(r):
                st.markdown(
                    f"""<div class="card" style="margin-bottom:10px;padding:14px;border-left:5px solid var(--green);">
                        <div style="display:flex;justify-content:space-between;align-items:center;">
                            <b style="font-size:15px;color:var(--ink);">{r['Participante']}</b>
                            <span class="badge success">{r['Pontos']} pts</span>
                        </div>
                        <div style="font-size:13px;color:var(--muted);margin-top:6px;line-height:1.5;">
                            🎯 Placares Exatos: {r['🎯 Exatos']} · 🏁 Vencedores: {r['🏁 Vencedor']}
                            <br>🥅 Gols Mandante: {r['🥅 Gols Mandante']} · Gols Visitante: {r['🥅 Gols Visitante']}
                            <br>📊 Saldo de Gols: {r['📊 Saldo']} · 📈 Aproveitamento: {r['📈 Aprov.']}
                            <br>🎖️ {r['🎖️']}
                        </div>
                    </div>""",
                    unsafe_allow_html=True,
                )
            render_responsive_table(pd.DataFrame(stats_rows), render_stats_card, "live_stats_ranking")

            # ── Match hits chart ──
            st.markdown("##### 🎯 Acertos por Categoria")
            cat_df = pd.DataFrame(stats_rows)
            if not cat_df.empty:
                cat_melt = cat_df.melt(
                    id_vars=["Participante"],
                    value_vars=["🎯 Exatos", "🏁 Vencedor", "🥅 Gols Mandante", "🥅 Gols Visitante", "📊 Saldo"],
                    var_name="Categoria",
                    value_name="Acertos",
                )
                if _HAS_PLOTLY:
                    fig_cat = px.bar(
                        cat_melt,
                        x="Participante",
                        y="Acertos",
                        color="Categoria",
                        barmode="group",
                        height=400,
                        color_discrete_sequence=px.colors.qualitative.Set2,
                    )
                    fig_cat.update_layout(
                        plot_bgcolor="rgba(0,0,0,0)",
                        paper_bgcolor="rgba(0,0,0,0)",
                        font_color="#e0e0e0",
                        legend=dict(orientation="h", yanchor="bottom", y=1.02),
                    )
                    st.plotly_chart(fig_cat, use_container_width=True)
                else:
                    st.dataframe(cat_melt.pivot_table(index="Participante", columns="Categoria", values="Acertos", fill_value=0), width="stretch")

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
            
            def render_live_ranking_card(r):
                from src.bolao.utils import avatar_url
                p_avatar = avatar_url(r['Participante'])
                st.markdown(
                    f"""
                    <div class="card" style="margin-bottom: 12px; padding: 16px; border-left: 5px solid var(--green);">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                            <div style="display: flex; align-items: center; gap: 8px;">
                                <img src="{p_avatar}" style="width: 32px; height: 32px; border-radius: 50%;" />
                                <span style="font-weight: 800; font-size: 16px; color: var(--ink);">{r['Posição']}º. {r['Participante']}</span>
                            </div>
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
            render_responsive_table(pd.DataFrame(live_rows), render_live_ranking_card, "live_ranking")

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
            user_score = None
            u_gm = 0
            u_gv = 0
            u_sd = 0
            if det_rows:
                st.dataframe(pd.DataFrame(det_rows), width="stretch", hide_index=True)

                # Compute per-participant metrics for the selected user
                user_score = next((s for s in live_scores if s["participant_key"] == user_key), None)
                for p in user_preds:
                    m = next((mm for mm in matches if mm.match_id == p.match_id), None)
                    if m and m.status == "result_approved" and m.official_home_goals is not None:
                        if p.predicted_home_goals == m.official_home_goals:
                            u_gm += 1
                        if p.predicted_away_goals == m.official_away_goals:
                            u_gv += 1
                        if (p.predicted_home_goals - p.predicted_away_goals) == (m.official_home_goals - m.official_away_goals):
                            u_sd += 1

                # ── Radar chart: per-participant profile ──
                if _HAS_PLOTLY and user_score:
                    radar_vals = {
                        "Placares Exatos": user_score["exact_scores"],
                        "Vencedores": user_score["outcomes"],
                        "Gols Mandante": u_gm,
                        "Gols Visitante": u_gv,
                        "Saldo de Gols": u_sd,
                    }
                    max_val = max(radar_vals.values()) if any(radar_vals.values()) else 1
                    fig_radar = go.Figure()
                    fig_radar.add_trace(go.Scatterpolar(
                        r=list(radar_vals.values()),
                        theta=list(radar_vals.keys()),
                        fill="toself",
                        name=selected_user,
                        line_color="#22c55e",
                    ))
                    fig_radar.update_layout(
                        polar=dict(
                            radialaxis=dict(visible=True, range=[0, max_val + 1]),
                            bgcolor="rgba(0,0,0,0)",
                        ),
                        plot_bgcolor="rgba(0,0,0,0)",
                        paper_bgcolor="rgba(0,0,0,0)",
                        font_color="#e0e0e0",
                        height=350,
                        margin=dict(t=10, b=10),
                    )
                    st.plotly_chart(fig_radar, use_container_width=True)

                # ── Strengths & Weaknesses analysis ──
                st.markdown("###### 💪 Forças & Fraquezas")
                if user_score:
                    metrics = {
                        "Placares Exatos": user_score["exact_scores"],
                        "Acertar Vencedor": user_score["outcomes"],
                        "Gols do Mandante": u_gm,
                        "Gols do Visitante": u_gv,
                        "Saldo de Gols": u_sd,
                    }
                    avg_metrics = {}
                    all_live = list(live_scores)
                    for key in metrics:
                        vals = []
                        for s in all_live:
                            sk = s["participant_key"]
                            sp = [p for p in live_preds if (p.participant_key or normalize_participant_key(p.participant_name)) == sk]
                            gm = sum(
                                1 for p in sp
                                if (m := next((mm for mm in matches if mm.match_id == p.match_id), None))
                                and m.status == "result_approved" and m.official_home_goals is not None
                                and p.predicted_home_goals == m.official_home_goals
                            )
                            gv = sum(
                                1 for p in sp
                                if (m := next((mm for mm in matches if mm.match_id == p.match_id), None))
                                and m.status == "result_approved" and m.official_away_goals is not None
                                and p.predicted_away_goals == m.official_away_goals
                            )
                            sd = sum(
                                1 for p in sp
                                if (m := next((mm for mm in matches if mm.match_id == p.match_id), None))
                                and m.status == "result_approved" and m.official_home_goals is not None
                                and (p.predicted_home_goals - p.predicted_away_goals) == (m.official_home_goals - m.official_away_goals)
                            )
                            if key == "Placares Exatos":
                                vals.append(s["exact_scores"])
                            elif key == "Acertar Vencedor":
                                vals.append(s["outcomes"])
                            elif key == "Gols do Mandante":
                                vals.append(gm)
                            elif key == "Gols do Visitante":
                                vals.append(gv)
                            elif key == "Saldo de Gols":
                                vals.append(sd)
                        avg_metrics[key] = sum(vals) / len(vals) if vals else 0

                    strengths = []
                    weaknesses = []
                    for cat, val in metrics.items():
                        avg = avg_metrics.get(cat, 0)
                        if avg > 0 and val > avg * 1.2:
                            strengths.append(cat)
                        elif avg > 0 and val < avg * 0.8:
                            weaknesses.append(cat)
                        elif avg == 0 and val > 0:
                            strengths.append(cat)

                    if strengths:
                        st.success(f"💪 **Forças:** {' · '.join(strengths)}")
                    if weaknesses:
                        st.warning(f"⚠️ **Fraquezas:** {' · '.join(weaknesses)}")
                    if not strengths and not weaknesses:
                        st.info("📊 Desempenho próximo da média do grupo em todas as categorias.")
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
            
            def render_combined_ranking_card(r):
                from src.bolao.utils import avatar_url
                p_avatar = avatar_url(r['Participante'])
                st.markdown(
                    f"""
                    <div class="card" style="margin-bottom: 12px; padding: 16px; border-left: 5px solid var(--gold);">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                            <div style="display: flex; align-items: center; gap: 8px;">
                                <img src="{p_avatar}" style="width: 32px; height: 32px; border-radius: 50%;" />
                                <span style="font-weight: 800; font-size: 16px; color: var(--ink);">{r['Posição']}º. {r['Participante']}</span>
                            </div>
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
            render_responsive_table(pd.DataFrame(comb_rows), render_combined_ranking_card, "combined_ranking")
            
            if len(combined_list) >= 3:
                st.markdown("---")
                col_story, _ = st.columns([2, 2])
                with col_story:
                    if st.button("🖼️ Gerar imagem para Stories", key="btn_generate_stories_combined"):
                        from PIL import Image, ImageDraw, ImageFont
                        import io
                        
                        def gerar_imagem_podio(top3: list) -> bytes:
                            img = Image.new("RGB", (1080, 1920), color="#0d2818")
                            draw = ImageDraw.Draw(img)
                            try:
                                font_title = ImageFont.truetype("arial.ttf", 60)
                                font_name = ImageFont.truetype("arial.ttf", 48)
                                font_pts = ImageFont.truetype("arial.ttf", 72)
                            except OSError:
                                font_title = font_name = font_pts = ImageFont.load_default()

                            draw.text((540, 100), "🏆 BOLÃO DA CABINE DO GLÓRIA", font=font_title, fill="#ffd700", anchor="mm")
                            draw.text((540, 200), "Copa do Mundo 2026", font=font_name, fill="#ffffff", anchor="mm")

                            posicoes_y = [600, 1000, 1400]
                            medalhas = ["🥇", "🥈", "🥉"]
                            for i, (y, p) in enumerate(zip(posicoes_y, top3)):
                                draw.text((540, y), f"{medalhas[i]} {p['participant']}", font=font_name, fill="#ffffff", anchor="mm")
                                draw.text((540, y + 80), f"{int(p['total'])} pts", font=font_pts, fill="#22c55e", anchor="mm")

                            buf = io.BytesIO()
                            img.save(buf, format="PNG")
                            return buf.getvalue()
                            
                        img_bytes = gerar_imagem_podio(combined_list[:3])
                        st.download_button("⬇️ Baixar imagem", data=img_bytes, file_name="podio_bolao.png", mime="image/png", width="stretch")

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
                
                def render_filtered_ranking_card(r):
                    from src.bolao.utils import avatar_url
                    p_avatar = avatar_url(r['Participante'])
                    st.markdown(
                        f"""
                        <div class="card" style="margin-bottom: 12px; padding: 16px; border-left: 5px solid var(--green);">
                            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                                <div style="display: flex; align-items: center; gap: 8px;">
                                    <img src="{p_avatar}" style="width: 32px; height: 32px; border-radius: 50%;" />
                                    <span style="font-weight: 800; font-size: 16px; color: var(--ink);">{r['Posição']}º. {r['Participante']}</span>
                                </div>
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
                render_responsive_table(pd.DataFrame(sub_rows), render_filtered_ranking_card, f"filtered_ranking_{filter_option}")

    # 5. Canarinho Tab
    with ranking_tabs[4]:
        st.markdown("#### 🇧🇷 Ranking Canarinho")
        st.caption("Classificação baseada apenas nas partidas da Seleção Brasileira (Placar + Goleadores + Assistências).")
        
        def calculate_ranking_canarinho(live_predictions: list, matches: list, config: dict) -> list[dict]:
            from src.bolao.storage import load_brasil_palpites_goleadores, load_brasil_resultados_goleadores
            from src.bolao.live_scoring import calculate_live_prediction_points, calcular_pontos_goleadores
            from src.bolao.utils import normalize_participant_key
            
            brazil_matches = {m.match_id: m for m in matches if ("Brasil" in m.home_team or "Brasil" in m.away_team) and m.status == "result_approved"}
            goleadores_palpites = load_brasil_palpites_goleadores()
            goleadores_resultados = load_brasil_resultados_goleadores()
            
            by_participant = {}
            for p in live_predictions:
                pkey = p.participant_key or normalize_participant_key(p.participant_name)
                if pkey not in by_participant:
                    by_participant[pkey] = {
                        "name": p.participant_name,
                        "key": pkey,
                        "placar_points": 0,
                        "goleador_points": 0,
                        "assist_points": 0,
                        "total": 0,
                        "gols_acertados": 0,
                        "assists_acertadas": 0
                    }
                
                if p.match_id in brazil_matches:
                    m = brazil_matches[p.match_id]
                    res = calculate_live_prediction_points(p, m, config)
                    by_participant[pkey]["placar_points"] += res["points"]
                    by_participant[pkey]["total"] += res["points"]
                    
            for gp in goleadores_palpites:
                pkey = normalize_participant_key(gp["participante_nome"])
                if gp["jogo_id"] in brazil_matches:
                    m = brazil_matches[gp["jogo_id"]]
                    real_res = goleadores_resultados.get(m.match_id)
                    if real_res:
                        pts_breakdown = calcular_pontos_goleadores(
                            gp.get("goleadores", []),
                            gp.get("assistentes", []),
                            real_res.get("goleadores_reais", []),
                            real_res.get("assistentes_reais", []),
                            config
                        )
                        pts = pts_breakdown["total"]
                        
                        if pkey not in by_participant:
                            by_participant[pkey] = {
                                "name": gp["participante_nome"],
                                "key": pkey,
                                "placar_points": 0,
                                "goleador_points": 0,
                                "assist_points": 0,
                                "total": 0,
                                "gols_acertados": 0,
                                "assists_acertadas": 0
                            }
                        
                        from collections import Counter
                        real_g = Counter(real_res.get("goleadores_reais", []))
                        palp_g = Counter(gp.get("goleadores", []))
                        g_hits = sum(min(palp_g.get(k, 0), v) for k, v in real_g.items())
                        
                        real_a = Counter(real_res.get("assistentes_reais", []))
                        palp_a = Counter(gp.get("assistentes", []))
                        a_hits = sum(min(palp_a.get(k, 0), v) for k, v in real_a.items())
                        
                        live_rules = config.get("live_scoring", {})
                        pts_gol = int(live_rules.get("pts_acertar_goleador", config.get("pts_acertar_goleador", 4)))
                        pts_assist = int(live_rules.get("pts_acertar_assistente", config.get("pts_acertar_assistente", 2)))
                        
                        by_participant[pkey]["goleador_points"] += g_hits * pts_gol
                        by_participant[pkey]["assist_points"] += a_hits * pts_assist
                        
                        bonuses = pts - (g_hits * pts_gol + a_hits * pts_assist)
                        by_participant[pkey]["goleador_points"] += bonuses
                        
                        by_participant[pkey]["total"] += pts
                        by_participant[pkey]["gols_acertados"] += g_hits
                        by_participant[pkey]["assists_acertadas"] += a_hits
                        
            ranking = list(by_participant.values())
            ranking.sort(key=lambda s: (-s["total"], -s["placar_points"], s["name"].lower()))
            for idx, row in enumerate(ranking, start=1):
                row["position"] = idx
            return ranking
            
        canarinho_ranking = calculate_ranking_canarinho(live_preds, matches, config)
        if not canarinho_ranking:
            st.info("Nenhum jogo do Brasil com resultado aprovado ainda.")
        else:
            can_rows = []
            for s in canarinho_ranking:
                can_rows.append({
                    "Posição": s["position"],
                    "Participante": s["name"],
                    "Pts": s["total"],
                    "Placar Pts": s["placar_points"],
                    "Goleador Pts": s["goleador_points"],
                    "Assist Pts": s["assist_points"],
                    "Gols acertados": s["gols_acertados"],
                    "Assists acertadas": s["assists_acertadas"]
                })
            
            def render_canarinho_card(r):
                from src.bolao.utils import avatar_url
                p_avatar = avatar_url(r['Participante'])
                st.markdown(
                    f"""
                    <div class="card" style="margin-bottom: 12px; padding: 16px; border-left: 5px solid var(--green);">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                            <div style="display: flex; align-items: center; gap: 8px;">
                                <img src="{p_avatar}" style="width: 32px; height: 32px; border-radius: 50%;" />
                                <span style="font-weight: 800; font-size: 16px; color: var(--ink);">{r['Posição']}º. {r['Participante']}</span>
                            </div>
                            <span class="badge success" style="font-size:12px; font-weight: bold; padding: 4px 8px;">{r['Pts']} pts</span>
                        </div>
                        <div style="font-size: 13px; color: var(--muted); line-height: 1.4;">
                            ⚽ Gols Acertados: {r['Gols acertados']} | 🅰️ Assists Acertadas: {r['Assists acertadas']}
                            <br>📋 Placar Pts: {r['Placar Pts']} | Scorer Pts: {r['Goleador Pts']} | Assist Pts: {r['Assist Pts']}
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
            render_responsive_table(pd.DataFrame(can_rows), render_canarinho_card, "canarinho_ranking_table")

    # 6. Evolução Tab
    with ranking_tabs[5]:
        st.markdown("#### 📈 Evolução da Pontuação")
        st.caption("Gráfico mostrando o acúmulo de pontos ao longo dos jogos concluídos.")

        approved_by_date = sorted(
            [m for m in matches if m.status == "result_approved"],
            key=lambda m: (m.starts_at or "", m.match_id or 0)
        )

        if not approved_by_date:
            st.info("Nenhum jogo concluído com resultado aprovado ainda.")
        elif not _HAS_PLOTLY:
            st.info("Gráfico de evolução requer Plotly (pip install plotly).")
        else:
            pkeys_in_ranking = {s["participant_key"] for s in live_scores}
            evolution = {}
            for pkey in pkeys_in_ranking:
                p_preds = [p for p in live_preds if (p.participant_key or normalize_participant_key(p.participant_name)) == pkey]
                p_name = next((s["participant"] for s in live_scores if s["participant_key"] == pkey), pkey)
                cumulative = 0
                points_per_match = []
                for m in approved_by_date:
                    lp = next((p for p in p_preds if p.match_id == m.match_id), None)
                    if lp:
                        res = calculate_live_prediction_points(lp, m, config)
                        cumulative += res["points"]
                    points_per_match.append({"match": f"{m.home_team[:3]}x{m.away_team[:3]}", "points": cumulative, "participant": p_name})
                evolution[pkey] = points_per_match

            df_evo = pd.DataFrame(
                [item for pts_list in evolution.values() for item in pts_list]
            )
            if not df_evo.empty:
                fig_evo = px.line(
                    df_evo, x="match", y="points", color="participant",
                    markers=True,
                    labels={"match": "Jogo", "points": "Pontos Acumulados", "participant": ""},
                    color_discrete_sequence=px.colors.qualitative.Set2,
                )
                fig_evo.update_layout(
                    plot_bgcolor="rgba(0,0,0,0)",
                    paper_bgcolor="rgba(0,0,0,0)",
                    font_color="#e0e0e0",
                    legend=dict(orientation="h", yanchor="bottom", y=1.02),
                    xaxis_tickangle=-45,
                    hovermode="x unified",
                )
                st.plotly_chart(fig_evo, use_container_width=True)

            st.markdown("##### 📋 Evolução do Ranking (Posições por Jogo)")
            approved_count = len(approved_by_date)
            if approved_count >= 2:
                pos_evolution = {}
                for game_idx in range(approved_count):
                    games_so_far = approved_by_date[:game_idx + 1]
                    game_ids_so_far = {g.match_id for g in games_so_far}

                    round_scores = []
                    for pkey in pkeys_in_ranking:
                        p_preds = [p for p in live_preds if (p.participant_key or normalize_participant_key(p.participant_name)) == pkey]
                        p_name = next((s["participant"] for s in live_scores if s["participant_key"] == pkey), pkey)
                        total = 0
                        for lp in p_preds:
                            if lp.match_id in game_ids_so_far:
                                m = next((mm for mm in games_so_far if mm.match_id == lp.match_id), None)
                                if m:
                                    total += calculate_live_prediction_points(lp, m, config)["points"]
                        round_scores.append({"participant": p_name, "participant_key": pkey, "total": total})

                    round_scores.sort(key=lambda r: (-r["total"], r["participant"].lower()))
                    for pos, rs in enumerate(round_scores, 1):
                        label = f"Jogo {game_idx + 1}"
                        if pkey not in pos_evolution:
                            pos_evolution[pkey] = {"participant": rs["participant"]}
                        pos_evolution[pkey][label] = pos

                pos_df = pd.DataFrame.from_dict(pos_evolution, orient="index").reset_index(drop=True)
                pos_cols = [c for c in pos_df.columns if c.startswith("Jogo")]
                if not pos_df.empty and len(pos_cols) >= 2:
                    fig_pos = go.Figure()
                    for _, row in pos_df.iterrows():
                        fig_pos.add_trace(go.Scatter(
                            x=pos_cols, y=[row[c] for c in pos_cols],
                            mode="lines+markers",
                            name=row["participant"],
                            connectgaps=False,
                        ))
                    fig_pos.update_yaxes(autorange="reversed", dtick=1)
                    fig_pos.update_layout(
                        plot_bgcolor="rgba(0,0,0,0)",
                        paper_bgcolor="rgba(0,0,0,0)",
                        font_color="#e0e0e0",
                        legend=dict(orientation="h", yanchor="bottom", y=1.02),
                        height=400,
                        hovermode="x unified",
                    )
                    st.plotly_chart(fig_pos, use_container_width=True)

        # Still load snapshots if they exist
        from src.bolao.storage import load_ranking_snapshots
        df_snapshots = pd.DataFrame(load_ranking_snapshots())
        if not df_snapshots.empty:
            st.markdown("##### 📸 Snapshots Salvos")
            st.caption("Registros manuais salvos pelo administrador ao final de cada rodada.")
            df_snapshots = df_snapshots.sort_values(by=["rodada", "posicao"])
            fig_snap = px.line(
                df_snapshots, x="rodada", y="posicao",
                color="participante_nome", markers=True,
                labels={"posicao": "Posição", "rodada": "Rodada", "participante_nome": ""},
                color_discrete_sequence=px.colors.qualitative.Set2
            )
            fig_snap.update_yaxes(autorange="reversed", dtick=1)
            fig_snap.update_layout(
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                font_color="#e0e0e0",
                legend=dict(orientation="h", yanchor="bottom", y=1.02)
            )
            st.plotly_chart(fig_snap, use_container_width=True)

    # 7. Estatísticas Tab
    with ranking_tabs[6]:
        st.markdown("#### 📊 Estatísticas Gerais do Grupo")
        st.caption("Visão agregada e insights dos palpites enviados para a Copa do Mundo 2026.")

        total_live_preds = len(live_preds)
        approved_match_ids = {m.match_id for m in matches if m.status == "result_approved"}

        # Aggregate stats
        exact_count = 0
        outcome_count = 0
        total_pontos = 0
        total_gols_palpitados = 0
        gols_mandante_acertados = 0
        gols_visitante_acertados = 0
        saldos_acertados = 0
        palpites_por_jogo = {}

        for lp in live_preds:
            m = next((mm for mm in matches if mm.match_id == lp.match_id), None)
            if not m or m.match_id not in approved_match_ids:
                continue
            total_gols_palpitados += lp.predicted_home_goals + lp.predicted_away_goals
            res = calculate_live_prediction_points(lp, m, config)
            pts = res["points"]
            total_pontos += pts
            if res["flags"].get("exact"):
                exact_count += 1
            if res["flags"].get("outcome"):
                outcome_count += 1
            if lp.predicted_home_goals == m.official_home_goals:
                gols_mandante_acertados += 1
            if lp.predicted_away_goals == m.official_away_goals:
                gols_visitante_acertados += 1
            if (lp.predicted_home_goals - lp.predicted_away_goals) == (m.official_home_goals - m.official_away_goals):
                saldos_acertados += 1
            palpites_por_jogo[lp.match_id] = palpites_por_jogo.get(lp.match_id, 0) + 1

        palpites_para_aprovados = len([lp for lp in live_preds if lp.match_id in approved_match_ids])
        pct_exatos = (exact_count / palpites_para_aprovados * 100) if palpites_para_aprovados > 0 else 0

        col_s1, col_s2, col_s3, col_s4 = st.columns(4)
        with col_s1:
            st.metric("Total Palpites", total_live_preds)
        with col_s2:
            st.metric("Placares Exatos", f"{exact_count} ({pct_exatos:.1f}%)")
        with col_s3:
            st.metric("Vencedores Corretos", outcome_count)
        with col_s4:
            st.metric("Média de Gols/Palpite", f"{total_gols_palpitados / palpites_para_aprovados:.2f}" if palpites_para_aprovados > 0 else "0")

        col_t1, col_t2, col_t3 = st.columns(3)
        with col_t1:
            st.metric("🥅 Gols Mandante Certos", gols_mandante_acertados)
        with col_t2:
            st.metric("🥅 Gols Visitante Certos", gols_visitante_acertados)
        with col_t3:
            st.metric("📊 Saldos de Gols Certos", saldos_acertados)

        # ── Pie Chart: Acerto vs Erro ──
        st.markdown("##### 🎯 Proporção de Acertos")
        labels = ["Exatos", "Só Vencedor", "Erros"]
        values = [
            exact_count,
            outcome_count - exact_count,
            palpites_para_aprovados - outcome_count,
        ]
        if sum(values) > 0:
            if _HAS_PLOTLY:
                fig_pie = go.Figure(data=[go.Pie(labels=labels, values=values, hole=0.4)])
                fig_pie.update_layout(
                    plot_bgcolor="rgba(0,0,0,0)",
                    paper_bgcolor="rgba(0,0,0,0)",
                    font_color="#e0e0e0",
                    height=300,
                    showlegend=True,
                    legend=dict(orientation="h", yanchor="bottom", y=1.02),
                )
                fig_pie.update_traces(textposition="inside", textinfo="percent+label")
                st.plotly_chart(fig_pie, use_container_width=True)
            else:
                total = sum(values)
                for lbl, val in zip(labels, values):
                    pct = val / total * 100 if total else 0
                    st.write(f"**{lbl}:** {val} ({pct:.1f}%)")

        # ── Palpites por Jogo ──
        st.markdown("##### 📋 Palpites por Jogo")
        jogo_rows = []
        for mid, count in sorted(palpites_por_jogo.items(), key=lambda x: -x[1]):
            m = next((mm for mm in matches if mm.match_id == mid), None)
            if m:
                jogo_rows.append({"Jogo": f"{m.home_team} x {m.away_team}", "Palpites": count, "Rodada": m.round_label, "Grupo": m.group or "—"})
        if jogo_rows:
            df_jogos = pd.DataFrame(jogo_rows)
            if _HAS_PLOTLY:
                fig_jogos = px.bar(
                    df_jogos.head(20),
                    x="Jogo",
                    y="Palpites",
                    color="Palpites",
                    color_continuous_scale="blues",
                    labels={"Jogo": "", "Palpites": "Palpites"},
                    height=350,
                )
                fig_jogos.update_layout(
                    plot_bgcolor="rgba(0,0,0,0)",
                    paper_bgcolor="rgba(0,0,0,0)",
                    font_color="#e0e0e0",
                    xaxis_tickangle=-45,
                    showlegend=False,
                )
                st.plotly_chart(fig_jogos, use_container_width=True)
            else:
                st.dataframe(df_jogos.head(20), width="stretch", hide_index=True)

        st.markdown("#### 🏆 Campeão mais apostado (Modo Clássico)")
        champs_list = [p.champion for p in submissions if p.champion]
        if champs_list:
            champ_counts = pd.Series(champs_list).value_counts()
            champ_df = pd.DataFrame({"Seleção": champ_counts.index, "Palpites": champ_counts.values})
            st.dataframe(champ_df, width="stretch", hide_index=True)
        else:
            st.info("Nenhuma campeã selecionada pelos participantes ainda.")
            
        # F12 — "Nosso Craque"
        from src.bolao.storage import load_brasil_palpites_classicos
        classic_br = load_brasil_palpites_classicos()
        if classic_br:
            art_br_list = [g.get("artilheiro_brasil_copa") for g in classic_br if g.get("artilheiro_brasil_copa")]
            art_ge_list = [g.get("artilheiro_geral_copa") for g in classic_br if g.get("artilheiro_geral_copa")]
            
            st.markdown("---")
            st.markdown("### ⭐ NOSSO CRAQUE — a aposta do bolão")
            col_cr1, col_cr2 = st.columns(2)
            with col_cr1:
                st.markdown("**Artilheiro do Brasil mais apostado:**")
                if art_br_list:
                    counts = pd.Series(art_br_list).value_counts()
                    total = len(art_br_list)
                    for player, cnt in counts.items():
                        pct = (cnt / total) * 100
                        bar = "█" * int(pct / 10)
                        st.write(f"**{player}** {bar} {pct:.0f}% ({cnt} {'voto' if cnt == 1 else 'votos'})")
                else:
                    st.caption("Nenhum palpite para artilheiro do Brasil ainda.")
            with col_cr2:
                st.markdown("**Artilheiro Geral mais apostado:**")
                if art_ge_list:
                    counts_ge = pd.Series(art_ge_list).value_counts()
                    total_ge = len(art_ge_list)
                    for player, cnt in counts_ge.items():
                        pct = (cnt / total_ge) * 100
                        bar = "█" * int(pct / 10)
                        st.write(f"**{player}** {bar} {pct:.0f}% ({cnt} {'voto' if cnt == 1 else 'votos'})")
                else:
                    st.caption("Nenhum palpite para artilheiro geral ainda.")
                    
        # F18 — Ranking de Azar
        def calcular_ranking_azar(live_predictions: list, matches: list, config: dict) -> list:
            from src.bolao.live_scoring import calculate_live_prediction_points
            approved_matches = {m.match_id: m for m in matches if m.status == "result_approved"}
            contador = {}
            for lp in live_predictions:
                if lp.match_id in approved_matches:
                    m = approved_matches[lp.match_id]
                    res = calculate_live_prediction_points(lp, m, config)
                    if res["flags"].get("outcome") and not res["flags"].get("exact"):
                        diff_h = abs(lp.predicted_home_goals - m.official_home_goals)
                        diff_a = abs(lp.predicted_away_goals - m.official_away_goals)
                        if (diff_h == 1 and diff_a == 0) or (diff_h == 0 and diff_a == 1):
                            nome = lp.participant_name
                            contador[nome] = contador.get(nome, 0) + 1
            return sorted(contador.items(), key=lambda x: -x[1])
            
        st.markdown("---")
        st.markdown("### 😭 Achei que Ia Dar — Ranking de Azar")
        st.caption("Participantes que mais acertaram o vencedor mas erraram o placar por exatamente 1 gol de diferença.")
        azar_ranking = calcular_ranking_azar(live_preds, matches, config)
        if azar_ranking:
            for idx, (nome, quases) in enumerate(azar_ranking[:5], start=1):
                st.write(f"{idx}º. **{nome}**: {quases} quases 😭")
        else:
            st.caption("Ninguém ficou no quase ainda.")

def obter_posicao_atual(nome: str) -> int | None:
    from .storage import load_config, load_app_data_cached
    from .live_scoring import calculate_live_ranking
    from .scoring import rank_predictions, ScoreConfig
    from .constants import DEFAULT_WEIGHTED_RULES, DEFAULT_UNIFORM_RULES, DEFAULT_V2_RULES
    from .utils import normalize_participant_key
    
    config = load_config()
    ctx = load_app_data_cached()
    submissions = ctx.submissions
    official = ctx.official
    matches = ctx.matches
    live_preds = ctx.live_predictions
    
    pkey = normalize_participant_key(nome)
    
    combined_enabled = config.get("combined_ranking_enabled", False)
    if combined_enabled and official:
        score_config = ScoreConfig(
            mode=config.get("scoring_mode", "v2"),
            weighted_rules=config.get("weighted_rules", dict(DEFAULT_WEIGHTED_RULES)),
            uniform_rules=config.get("uniform_rules", dict(DEFAULT_UNIFORM_RULES)),
            v2_rules=config.get("v2_rules", dict(DEFAULT_V2_RULES)),
        )
        classic_scores = rank_predictions(submissions, official, score_config)
        live_scores = calculate_live_ranking(live_preds, matches, config)
        
        combined_rules = config.get("combined_ranking", {})
        classic_weight = combined_rules.get("classic_weight", 1.0)
        live_weight = combined_rules.get("live_weight", 1.0)
        include_classic_only = combined_rules.get("include_classic_only_players", True)
        include_live_only = combined_rules.get("include_live_only_players", True)
        
        classic_dict = {normalize_participant_key(s.participant): s for s in classic_scores}
        live_dict = {s["participant_key"]: s for s in live_scores}
        
        all_keys = set(classic_dict.keys()).union(live_dict.keys())
        combined_list = []
        for pk in all_keys:
            c_score = classic_dict.get(pk)
            l_score = live_dict.get(pk)
            
            if c_score and not l_score and not include_classic_only:
                continue
            if l_score and not c_score and not include_live_only:
                continue
                
            p_name = c_score.participant if c_score else (l_score["participant"] if l_score else "—")
            c_pts = c_score.total if c_score else 0
            l_pts = l_score["total"] if l_score else 0
            combined_pts = c_pts * classic_weight + l_pts * live_weight
            
            combined_list.append({
                "participant_key": pk,
                "classic_points": c_pts,
                "live_points": l_pts,
                "total": combined_pts,
                "participant": p_name
            })
            
        combined_list.sort(key=lambda s: (
            -s["total"],
            -s["classic_points"],
            -s["live_points"],
            s["participant"].lower()
        ))
        
        for idx, item in enumerate(combined_list, start=1):
            if item["participant_key"] == pkey:
                return idx
    else:
        live_scores = calculate_live_ranking(live_preds, matches, config)
        for row in live_scores:
            if row["participant_key"] == pkey:
                return row["position"]
                
    return None

def verificar_mudanca_posicao(nome: str) -> dict | None:
    posicao_atual = obter_posicao_atual(nome)
    if posicao_atual is None:
        return None
        
    from .utils import normalize_participant_key
    pos_key = f"posicao_anterior_{normalize_participant_key(nome)}"
    posicao_anterior = st.session_state.get(pos_key)
    
    if posicao_anterior is None:
        st.session_state[pos_key] = posicao_atual
        return None
        
    delta = posicao_anterior - posicao_atual  # positivo = subiu, negativo = caiu
    if delta == 0:
        return None
        
    st.session_state[pos_key] = posicao_atual
    return {"delta": delta, "posicao_atual": posicao_atual}
