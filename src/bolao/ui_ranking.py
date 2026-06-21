from __future__ import annotations

import html
import streamlit as st
import pandas as pd
import logging
from typing import Any

try:
    import plotly.express as px
    import plotly.graph_objects as go
    _HAS_PLOTLY = True
except ImportError:
    _HAS_PLOTLY = False

from .storage import load_matches, load_live_predictions, load_submissions, load_official, load_config, load_app_data_cached, sync_official_results_to_matches
from .scoring import rank_predictions, ScoreConfig
from .live_scoring import calculate_live_ranking, calculate_live_prediction_points
from .ui_components import render_empty_state
from .utils import normalize_participant_key, avatar_url
from .achievements import calculate_achievements

# ─── Streamlit Cache Decorators for Performance ──────────────────────────────

@st.cache_data(ttl=60)
def get_classic_scores_cached(submissions, official, _score_config):
    """Calcula e cacheia o ranking clássico por 60 segundos."""
    return rank_predictions(submissions, official, _score_config)

@st.cache_data(ttl=60)
def get_live_scores_cached(live_preds, matches, config):
    """Calcula e cacheia o ranking jogo a jogo por 60 segundos."""
    return calculate_live_ranking(live_preds, matches, config)

# ─── Responsive HTML/CSS Podium Component ─────────────────────────────────────

def render_podio_html(top_scores: list, modo: str = "live") -> None:
    """
    Renderiza o pódio Top 3 com visual premium e responsivo.
    A ordem física no HTML é 2º, 1º, 3º. O CSS order garante o empilhamento correto no mobile (1º, 2º, 3º).
    """
    if not top_scores:
        return

    cards = []
    order_positions = [2, 1, 3]  # Ordem visual no desktop (2º à esquerda, 1º no centro, 3º à direita)

    for pos in order_positions:
        if len(top_scores) >= pos:
            score = top_scores[pos - 1]
            
            # Extração de campos correspondentes ao modo
            if modo == "classic":
                name = score.participant
                pts = score.total
                detail = f"🎯 {score.exact_scores} exatos · Grupos: {score.group_points} pts"
            elif modo == "combined":
                name = score["participant"]
                pts = score["total"]
                detail = f"🏆 Clássico: {score['classic_points']} pts | 🎯 Jogo a Jogo: {score['live_points']} pts"
            elif modo == "canarinho":
                name = score["name"]
                pts = score["total"]
                detail = f"⚽ Gols: {score['gols_acertados']} · 🅰️ Assist: {score['assists_acertadas']}"
            else:  # live ou rodada/fase
                name = score.get("participant", score.get("name", "Participante"))
                pts = score.get("total", 0)
                detail = f"🎯 {score.get('exact_scores', 0)} exatos · 🏁 Vencedores: {score.get('outcomes', 0)}"

            medal = {1: "🥇", 2: "🥈", 3: "🥉"}[pos]
            css_class = {1: "first", 2: "second", 3: "third"}[pos]
            p_avatar = avatar_url(name)

            cards.append(f"""
            <div class="custom-podium-card {css_class}">
                <div class="medal">{medal}</div>
                <div class="podium-rank">{pos}º lugar</div>
                <div style="display: flex; align-items: center; justify-content: center; gap: 8px; margin: 10px 0;">
                    <img src="{p_avatar}" style="width: 32px; height: 32px; border-radius: 50%; border: 1px solid rgba(255,255,255,0.15);" />
                    <span class="podium-name">{html.escape(name)}</span>
                </div>
                <div class="podium-points">{pts} pts</div>
                <div class="podium-note">{html.escape(detail)}</div>
            </div>
            """)
        else:
            cards.append('<div class="custom-podium-card-placeholder"></div>')

    st.markdown(f"""
    <style>
    .custom-podium {{
      display: flex;
      flex-direction: row;
      justify-content: center;
      align-items: flex-end;
      gap: 16px;
      margin: 24px 0 32px;
      width: 100%;
    }}
    .custom-podium-card {{
      background: linear-gradient(135deg, var(--panel-strong) 0%, var(--panel) 100%);
      border-radius: 20px;
      padding: 20px 16px;
      text-align: center;
      flex: 1;
      box-shadow: var(--shadow);
      transition: transform 0.2s ease;
      border: 1px solid var(--line);
    }}
    .custom-podium-card.first {{
      background: linear-gradient(135deg, var(--panel-strong) 0%, var(--gold-bg) 100%);
      border: 2px solid var(--gold) !important;
      padding: 36px 20px;
      transform: scale(1.06);
      z-index: 2;
      order: 2;
    }}
    .custom-podium-card.second {{
      border: 2px solid rgba(180, 180, 180, 0.4) !important;
      order: 1;
    }}
    .custom-podium-card.third {{
      border: 2px solid rgba(196, 126, 60, 0.35) !important;
      order: 3;
    }}
    .custom-podium-card-placeholder {{
      flex: 1;
      visibility: hidden;
      order: 3;
    }}
    .medal {{
      font-size: 38px;
      margin-bottom: 4px;
    }}
    .podium-rank {{
      font-size: 11px;
      font-weight: 800;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      color: var(--gold);
    }}
    .podium-name {{
      font-size: 16px;
      font-weight: 700;
      color: var(--ink);
    }}
    .podium-points {{
      font-size: 26px;
      font-weight: 900;
      color: var(--green);
      margin: 4px 0;
    }}
    .podium-note {{
      font-size: 12px;
      color: var(--muted);
    }}
    @media (max-width: 600px) {{
      .custom-podium {{
        flex-direction: column;
        align-items: stretch;
        gap: 12px;
      }}
      .custom-podium-card.first {{
        transform: none;
        order: 1;
        padding: 24px 20px;
      }}
      .custom-podium-card.second {{
        order: 2;
      }}
      .custom-podium-card.third {{
        order: 3;
      }}
      .custom-podium-card-placeholder {{
        display: none;
      }}
    }}
    </style>
    <div class="custom-podium">
        {"".join(cards)}
    </div>
    """, unsafe_allow_html=True)


# ─── Participant Details Helper ──────────────────────────────────────────────

TIPO_ACERTO_DISPLAY = {
    "exato": "🎯 Exato",
    "vencedor": "✅ Vencedor",
    "empate": "➖ Empate",
    "saldo": "📊 Saldo de Gols",
    "gols": "⚽ Gols",
    "erro": "❌ Errou",
    "Aguardando resultado oficial": "⏳ Pendente",
    "Palpite atrasado (inválido)": "🚫 Atrasado",
}

def render_detalhe_participante_card(user_name: str, live_preds: list, matches: list, config: dict) -> None:
    """Renderiza a ficha detalhada e análise de palpites de um participante."""
    user_key = normalize_participant_key(user_name)
    user_preds = [p for p in live_preds if (p.participant_key or normalize_participant_key(p.participant_name)) == user_key]

    if not user_preds:
        st.info("Nenhum palpite enviado por este participante ainda.")
        return

    det_rows = []
    correct_outcomes = 0
    exact_scores = 0
    gols_mandante = 0
    gols_visitante = 0
    saldo_gols = 0
    total_jogos = 0

    for p in user_preds:
        m = next((mm for mm in matches if mm.match_id == p.match_id), None)
        if m:
            res = calculate_live_prediction_points(p, m, config)
            pts = res["points"]
            flags = res["flags"]
            
            tipo_acerto = "⏳ Pendente"
            if m.status == "result_approved":
                total_jogos += 1
                if flags.get("exact"):
                    tipo_acerto = "🎯 Exato"
                    exact_scores += 1
                elif flags.get("outcome"):
                    tipo_acerto = "✅ Vencedor"
                    correct_outcomes += 1
                else:
                    tipo_acerto = "❌ Errou"
                
                if p.predicted_home_goals == m.official_home_goals:
                    gols_mandante += 1
                if p.predicted_away_goals == m.official_away_goals:
                    gols_visitante += 1
                if (p.predicted_home_goals - p.predicted_away_goals) == (m.official_home_goals - m.official_away_goals):
                    saldo_gols += 1

            det_rows.append({
                "jogo": f"{m.home_team} x {m.away_team}",
                "Fase": m.round_label,
                "palpite": f"{p.predicted_home_goals} x {p.predicted_away_goals}",
                "resultado": f"{m.official_home_goals} x {m.official_away_goals}" if m.status == "result_approved" else "Aguardando",
                "tipo_acerto": tipo_acerto,
                "pontos": pts if m.status == "result_approved" else 0
            })

    # Resumo com metrics
    st.markdown("##### 📊 Resumo de Desempenho")
    col_a, col_b, col_c, col_d = st.columns(4)
    col_a.metric("Jogos Palpitados", len(user_preds))
    col_b.metric("🎯 Placares Exatos", exact_scores)
    col_c.metric("🏁 Vencedor Correto", correct_outcomes)
    col_d.metric("⚽ Aproveitamento", f"{int(exact_scores + correct_outcomes) / total_jogos * 100:.0f}%" if total_jogos > 0 else "0%")

    st.markdown("##### 📝 Detalhamento por Jogo")
    if det_rows:
        df_det = pd.DataFrame(det_rows)
        st.dataframe(
            df_det,
            use_container_width=True,
            hide_index=True,
            column_config={
                "jogo": st.column_config.TextColumn("Partida", width="medium"),
                "Fase": st.column_config.TextColumn("Fase/Rodada", width="small"),
                "palpite": st.column_config.TextColumn("Seu Palpite", width="small"),
                "resultado": st.column_config.TextColumn("Resultado Real", width="small"),
                "tipo_acerto": st.column_config.TextColumn("Tipo de Acerto", width="small"),
                "pontos": st.column_config.NumberColumn("Pontos Ganhos", width="small"),
            }
        )

        # Gráfico Radar e Forças/Fraquezas
        if _HAS_PLOTLY and total_jogos > 0:
            st.markdown("##### 🎯 Perfil Estatístico do Participante")
            
            radar_vals = {
                "Placares Exatos": exact_scores,
                "Vencedores": correct_outcomes,
                "Gols Mandante": gols_mandante,
                "Gols Visitante": gols_visitante,
                "Saldo de Gols": saldo_gols,
            }
            max_val = max(radar_vals.values()) if any(radar_vals.values()) else 1
            
            fig_radar = go.Figure()
            fig_radar.add_trace(go.Scatterpolar(
                r=list(radar_vals.values()),
                theta=list(radar_vals.keys()),
                fill="toself",
                name=user_name,
                line_color="#2dd67b",
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
                margin=dict(t=20, b=20),
            )
            st.plotly_chart(fig_radar, use_container_width=True)


# ─── Main Interface Function ──────────────────────────────────────────────────

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
    
    # Calcular conquistas sociais
    achievements = calculate_achievements(ctx)

    st.markdown("### 🏆 Rankings do Bolão")
    st.caption("Classificação geral e estatísticas em tempo real nos diferentes modos da Copa.")

    # Instanciar ScoreConfig se necessário
    if score_config is None:
        from .constants import DEFAULT_WEIGHTED_RULES, DEFAULT_UNIFORM_RULES, DEFAULT_V2_RULES
        score_config = ScoreConfig(
            mode=config.get("scoring_mode", "v2"),
            weighted_rules=config.get("weighted_rules", dict(DEFAULT_WEIGHTED_RULES)),
            uniform_rules=config.get("uniform_rules", dict(DEFAULT_UNIFORM_RULES)),
            v2_rules=config.get("v2_rules", dict(DEFAULT_V2_RULES)),
        )

    # Grid de KPIs no topo
    col_k1, col_k2, col_k3 = st.columns(3)
    with col_k1:
        st.metric("Total Participantes (Clássico)", len(submissions))
    with col_k2:
        unique_live = len(set(lp.participant_key or normalize_participant_key(lp.participant_name) for lp in live_preds))
        st.metric("Total Participantes (Jogo a Jogo)", unique_live)
    with col_k3:
        approved_count = len([m for m in matches if m.status == "result_approved"])
        st.metric("Jogos Concluídos", f"{approved_count}/{len(matches)}")

    ranking_tabs = st.tabs([
        "🎯 Jogo a Jogo",
        "🏆 Clássico",
        "🔗 Combinado",
        "📅 Por Rodada / Fase",
        "🇧🇷 Canarinho",
        "📈 Evolução",
        "📊 Estatísticas"
    ])

    # ─────────────────────────────────────────────────────────────────────────
    # Tab 0: Jogo a Jogo
    # ─────────────────────────────────────────────────────────────────────────
    with ranking_tabs[0]:
        st.markdown("#### 🎯 Modo Jogo a Jogo — Classificação Geral")
        st.caption("Ranking baseado no acúmulo de pontos rodada a rodada ao longo da Copa.")

        live_scores = get_live_scores_cached(live_preds, matches, config)
        if not live_scores:
            st.info("Nenhum palpite computado ou jogos ainda não encerrados.")
        else:
            # 1. Pódio visual
            st.markdown("##### 🎖️ Pódio do Bolão")
            render_podio_html(live_scores, "live")

            # 2. Filtro de Busca Textual
            search_live = st.text_input("🔍 Buscar participante (Jogo a Jogo)", placeholder="Digite o nome...", key="search_live_name")
            filtered_live = [s for s in live_scores if search_live.lower() in s["participant"].lower()] if search_live else live_scores

            # Montagem das linhas para st.dataframe
            live_rows = []
            for s in filtered_live:
                pkey = s["participant_key"]
                user_badges = achievements.get(pkey, [])
                badge_str = " ".join([f"{b['icon']}" for b in user_badges]) if user_badges else "—"
                
                live_rows.append({
                    "Posição": s["position"],
                    "Participante": s["participant"],
                    "Pontos": s["total"],
                    "Pontos de Jogos": s.get("match_points", 0),
                    "Goleadores Brasil": s.get("brasil_points", 0),
                    "Artilheiro Dia": s.get("artilheiro_dia_points", 0),
                    "Artilheiro Rodada": s.get("artilheiro_rodada_points", 0),
                    "🎯 Exatos": s["exact_scores"],
                    "🏁 Vencedor": s["outcomes"],
                    "Palpites": s["predictions_count"],
                    "Aproveitamento": f"{int(s['hit_rate'] * 100)}%",
                    "Conquistas": badge_str
                })

            df_live = pd.DataFrame(live_rows)
            
            # 3. Tabela Completa (ProgressColumn)
            st.markdown("##### 📋 Classificação Completa")
            st.dataframe(
                df_live,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Posição": st.column_config.NumberColumn("Pos.", width="small"),
                    "Participante": st.column_config.TextColumn("Participante", width="medium"),
                    "Pontos": st.column_config.ProgressColumn(
                        "Total Pontos",
                        min_value=0,
                        max_value=int(df_live["Pontos"].max()) if not df_live.empty else 1,
                        format="%d"
                    ),
                    "Pontos de Jogos": st.column_config.NumberColumn("🎮 Jogos", width="small"),
                    "Goleadores Brasil": st.column_config.NumberColumn("🇧🇷 Brasil", width="small"),
                    "Artilheiro Dia": st.column_config.NumberColumn("☀️ Dia", width="small"),
                    "Artilheiro Rodada": st.column_config.NumberColumn("📅 Rodada", width="small"),
                    "🎯 Exatos": st.column_config.NumberColumn("🎯 Exatos", width="small"),
                    "🏁 Vencedor": st.column_config.NumberColumn("🏁 Vencedor", width="small"),
                    "Palpites": st.column_config.NumberColumn("⚽ Palpites", width="small"),
                    "Aproveitamento": st.column_config.TextColumn("📈 Aprov.", width="small"),
                    "Conquistas": st.column_config.TextColumn("🎖️ Conquistas", width="medium"),
                }
            )

            # 4. Detalhes por Participante
            st.markdown("---")
            st.markdown("#### 🔍 Ficha Detalhada do Participante")
            selected_user = st.selectbox(
                "Escolha um participante para ver o histórico detalhado:",
                options=[s["participant"] for s in live_scores],
                key="live_detail_user"
            )
            render_detalhe_participante_card(selected_user, live_preds, matches, config)

    # ─────────────────────────────────────────────────────────────────────────
    # Tab 1: Clássico
    # ─────────────────────────────────────────────────────────────────────────
    with ranking_tabs[1]:
        st.markdown("#### 🏆 Modo Clássico — Palpites pré-Copa")
        st.caption("Classificação baseada nos palpites de cartela completa preenchidos antes do início da Copa.")

        if not official:
            st.info("O resultado oficial do Modo Clássico ainda não foi cadastrado. Exibindo inscritos por data de envio.")
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
                st.dataframe(pd.DataFrame(classic_list), use_container_width=True, hide_index=True)
        else:
            classic_scores = get_classic_scores_cached(submissions, official, score_config)
            
            # 1. Pódio
            st.markdown("##### 🎖️ Pódio - Modo Clássico")
            render_podio_html(classic_scores, "classic")

            # 2. Busca e Tabela
            search_name = st.text_input("🔍 Buscar participante (Clássico)", placeholder="Digite o nome...", key="search_classic_name")
            filtered = [s for s in classic_scores if search_name.lower() in s.participant.lower()] if search_name else classic_scores

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

            df_classic = pd.DataFrame(rows)
            st.markdown("##### 📋 Tabela Geral - Clássico")
            st.dataframe(
                df_classic,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Posição": st.column_config.NumberColumn("Pos.", width="small"),
                    "Participante": st.column_config.TextColumn("Participante", width="medium"),
                    "Pontos": st.column_config.ProgressColumn(
                        "Total Pontos",
                        min_value=0,
                        max_value=int(df_classic["Pontos"].max()) if not df_classic.empty else 1,
                        format="%d"
                    ),
                    "Fase de Grupos": st.column_config.NumberColumn("📋 Grupos", width="small"),
                    "Mata-Mata": st.column_config.NumberColumn("⚔️ Mata-Mata", width="small"),
                    "Campeão correto": st.column_config.TextColumn("🏆 Campeão", width="small"),
                    "Placares Exatos": st.column_config.NumberColumn("🎯 Exatos", width="small"),
                    "Conquistas": st.column_config.TextColumn("🎖️ Conquistas", width="medium"),
                }
            )

    # ─────────────────────────────────────────────────────────────────────────
    # Tab 2: Combinado
    # ─────────────────────────────────────────────────────────────────────────
    with ranking_tabs[2]:
        st.markdown("#### 🔗 Ranking Geral Combinado")
        st.caption("Classificação geral ponderada unificando os pontos do Modo Clássico e do Modo Jogo a Jogo.")
        
        combined_enabled = config.get("combined_ranking_enabled", False)
        if not combined_enabled:
            st.warning("⚠️ O Ranking Geral Combinado ainda não está ativado. O administrador pode ativá-lo nas Configurações.")
        elif not official:
            st.info("O resultado oficial clássico é necessário para computar o ranking geral.")
        else:
            classic_scores = get_classic_scores_cached(submissions, official, score_config)
            live_scores = get_live_scores_cached(live_preds, matches, config)
            
            combined_rules = config.get("combined_ranking", {})
            classic_weight = combined_rules.get("classic_weight", 1.0)
            live_weight = combined_rules.get("live_weight", 1.0)
            include_classic_only = combined_rules.get("include_classic_only_players", True)
            include_live_only = combined_rules.get("include_live_only_players", True)
            
            classic_dict = {normalize_participant_key(s.participant): s for s in classic_scores}
            live_dict = {s["participant_key"]: s for s in live_scores}
            all_keys = set(classic_dict.keys()).union(live_dict.keys())
            
            combined_list = []
            for pkey in all_keys:
                c_score = classic_dict.get(pkey)
                l_score = live_dict.get(pkey)
                
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
                
            combined_list.sort(key=lambda s: (-s["total"], -s["classic_points"], -s["live_points"], s["participant"].lower()))
            
            # Pódio
            render_podio_html(combined_list, "combined")

            # Tabela
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
            
            df_comb = pd.DataFrame(comb_rows)
            st.markdown("##### 📋 Tabela Geral - Combinado")
            st.dataframe(
                df_comb,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Posição": st.column_config.NumberColumn("Pos.", width="small"),
                    "Participante": st.column_config.TextColumn("Participante", width="medium"),
                    "Pontos Combinados": st.column_config.ProgressColumn(
                        "Pontos Combinados",
                        min_value=0,
                        max_value=int(df_comb["Pontos Combinados"].max()) if not df_comb.empty else 1,
                        format="%d"
                    ),
                    "Pontos Clássico": st.column_config.NumberColumn("🏆 Clássico", width="small"),
                    "Pontos Jogo a Jogo": st.column_config.NumberColumn("🎯 Jogo a Jogo", width="small"),
                    "Conquistas": st.column_config.TextColumn("🎖️ Conquistas", width="medium"),
                }
            )

            # Stories Share
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
                        st.download_button("⬇️ Baixar imagem", data=img_bytes, file_name="podio_bolao.png", mime="image/png", use_container_width=True)

    # ─────────────────────────────────────────────────────────────────────────
    # Tab 3: Por Rodada / Fase
    # ─────────────────────────────────────────────────────────────────────────
    with ranking_tabs[3]:
        st.markdown("#### 📅 Classificação Filtrada — Jogo a Jogo")
        st.caption("Consulte a pontuação específica e pódio de uma rodada ou fase do mata-mata.")
        
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
            if filter_type == "Por Rodada":
                selected_matches = [m for m in matches if m.round_label == filter_option and m.status == "result_approved"]
            else:
                selected_matches = [m for m in matches if m.phase == filter_option and m.status == "result_approved"]
                
            selected_match_ids = {m.match_id for m in selected_matches}
            filtered_preds = [lp for lp in live_preds if lp.match_id in selected_match_ids]
            
            sub_live_scores = calculate_live_ranking(filtered_preds, selected_matches, config)
            
            if not sub_live_scores:
                st.info("Nenhum palpite para esta seleção de jogos.")
            else:
                st.markdown(f"##### 🎖️ Pódio: {filter_option}")
                render_podio_html(sub_live_scores, "live")
                
                sub_rows = []
                for s in sub_live_scores:
                    pkey = s["participant_key"]
                    user_badges = achievements.get(pkey, [])
                    badge_str = " ".join([b['icon'] for b in user_badges]) if user_badges else "—"
                    
                    sub_rows.append({
                        "Posição": s["position"],
                        "Participante": s["participant"],
                        "Pontos": s["total"],
                        "🎯 Exatos": s["exact_scores"],
                        "Conquistas": badge_str
                    })
                
                df_sub = pd.DataFrame(sub_rows)
                st.markdown(f"##### 📋 Classificação Filtrada: {filter_option}")
                st.dataframe(
                    df_sub,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Posição": st.column_config.NumberColumn("Pos.", width="small"),
                        "Participante": st.column_config.TextColumn("Participante", width="medium"),
                        "Pontos": st.column_config.ProgressColumn(
                            "Pontos Obtidos",
                            min_value=0,
                            max_value=int(df_sub["Pontos"].max()) if not df_sub.empty else 1,
                            format="%d"
                        ),
                        "🎯 Exatos": st.column_config.NumberColumn("🎯 Exatos", width="small"),
                        "Conquistas": st.column_config.TextColumn("🎖️ Conquistas", width="medium"),
                    }
                )

    # ─────────────────────────────────────────────────────────────────────────
    # Tab 4: Canarinho
    # ─────────────────────────────────────────────────────────────────────────
    with ranking_tabs[4]:
        st.markdown("#### 🇧🇷 Ranking Canarinho")
        st.caption("Classificação baseada apenas nas partidas e pontos extras da Seleção Brasileira.")
        
        def calculate_ranking_canarinho(live_predictions: list, matches: list, config: dict) -> list[dict]:
            from src.bolao.storage import load_brasil_palpites_goleadores, load_brasil_resultados_goleadores
            from src.bolao.live_scoring import calculate_live_prediction_points, calcular_pontos_goleadores
            
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
            # Pódio
            render_podio_html(canarinho_ranking, "canarinho")

            # Tabela
            can_rows = []
            for s in canarinho_ranking:
                can_rows.append({
                    "Posição": s["position"],
                    "Participante": s["name"],
                    "Pts": s["total"],
                    "Placar Pts": s["placar_points"],
                    "Goleador Pts": s["goleador_points"],
                    "Assist Pts": s["assist_points"],
                    "Gols": s["gols_acertados"],
                    "Assists": s["assists_acertadas"]
                })
            
            df_can = pd.DataFrame(can_rows)
            st.markdown("##### 📋 Tabela Geral - Canarinho")
            st.dataframe(
                df_can,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Posição": st.column_config.NumberColumn("Pos.", width="small"),
                    "Participante": st.column_config.TextColumn("Participante", width="medium"),
                    "Pts": st.column_config.ProgressColumn(
                        "Total Pontos",
                        min_value=0,
                        max_value=int(df_can["Pts"].max()) if not df_can.empty else 1,
                        format="%d"
                    ),
                    "Placar Pts": st.column_config.NumberColumn("🎮 Jogos", width="small"),
                    "Goleador Pts": st.column_config.NumberColumn("⚽ Scorer", width="small"),
                    "Assist Pts": st.column_config.NumberColumn("🅰️ Assist", width="small"),
                    "Gols": st.column_config.NumberColumn("🥅 Gols", width="small"),
                    "Assists": st.column_config.NumberColumn("🅰️ Assists", width="small"),
                }
            )

    # ─────────────────────────────────────────────────────────────────────────
    # Tab 5: Evolução (Gráfico de Linha de Pontos Acumulados)
    # ─────────────────────────────────────────────────────────────────────────
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
            st.info("Gráfico de evolução requer Plotly.")
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

            df_evo = pd.DataFrame([item for pts_list in evolution.values() for item in pts_list])
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

        # Snapshots
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

    # ─────────────────────────────────────────────────────────────────────────
    # Tab 6: Estatísticas Gerais do Grupo
    # ─────────────────────────────────────────────────────────────────────────
    with ranking_tabs[6]:
        st.markdown("#### 📊 Estatísticas Gerais do Grupo")
        st.caption("Visão agregada e insights dos palpites enviados para a Copa do Mundo 2026.")

        total_live_preds = len(live_preds)
        approved_match_ids = {m.match_id for m in matches if m.status == "result_approved"}

        exact_count = 0
        outcome_count = 0
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

        # Pie Chart: Acerto vs Erro
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

        # Palpites por Jogo
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
            
        # Nosso Craque
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
                    
        # Ranking de Azar
        def calcular_ranking_azar(live_predictions: list, matches: list, config: dict) -> list:
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


# ─── Navigation & Session State Functions ────────────────────────────────────

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
