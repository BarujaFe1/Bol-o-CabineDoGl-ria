
from __future__ import annotations

import html
import json
import os
from copy import deepcopy
from pathlib import Path

import pandas as pd
import streamlit as st


from src.bolao.constants import (
    ALL_TEAMS,
    APP_NAME,
    APP_SUBTITLE,
    DEFAULT_UNIFORM_RULES,
    DEFAULT_WEIGHTED_RULES,
    DEFAULT_V2_RULES,
    GE_SIMULATOR_URL,
    GROUPS,
    PHASE_LABELS,
    PHASES,
)
from src.bolao.exporters import details_dataframe, discord_ranking, podium_html, ranking_csv, ranking_json, ranking_to_dataframe
from src.bolao.models import Match, Prediction

from src.bolao.parser_ge import knockout_to_rows, parse_ge_knockout_text, rows_to_knockout
from src.bolao.scoring import ScoreConfig, rank_predictions
from src.bolao.storage import (
    delete_submission,
    export_all_state,
    load_config,
    load_demo_state,
    load_official,
    load_submissions,
    reset_state,
    save_config,
    save_official,
    save_submission,
    load_app_data_cached,
    load_events,
    register_participant,
    load_registered_participants,
    delete_registered_participant,
)
from src.bolao.navigation import navigate_to
from src.bolao.ui_components import (
    badges,
    dataframe_to_groups,
    groups_dataframe,
    hero,
    inject_css,
    issues_box,
    kpi_grid,
    podium,
    step_cards,
    render_page_header,
    render_empty_state,
    render_badge,
    render_player_single_select,
    render_theme_selector,
)
from src.bolao.utils import decode_uploaded_file, norm_team, now_iso, stable_id
from src.bolao.validation import validate_prediction, has_blocking_errors
from src.bolao.simulator_engine import validate_prediction_complete
from src.bolao.ui_artilheiro import render_page_artilheiro
from src.bolao.ui_simulator import render_simulator, init_simulator_state, get_guess_completion_state
from src.bolao.migrations import migrate_existing_submissions_to_classic_schema

# Static UI modules imports to prevent Streamlit hot-reload ImportErrors
from src.bolao.ui_cartela import render_minha_cartela
from src.bolao.ui_live_matches import render_jogos_de_hoje, render_match_center, is_match_open_for_prediction, render_jogos_do_brasil
from src.bolao.ui_ranking import render_rankings_tabs
from src.bolao.ui_social_pages import (
    render_central_do_bolao,
    render_palpites_do_grupo,
    render_analise_dos_palpites,
    render_duelo_de_palpites,
    render_regras_do_bolao,
)
from src.bolao.ui_admin_matches import admin_matches_agenda, admin_palpites_jogo_a_jogo
from src.bolao.ui_admin_brasil import admin_selecao_brasileira
from src.bolao.storage import load_archived_participants


st.set_page_config(
    page_title=f"{APP_NAME} · {APP_SUBTITLE}",
    page_icon="🏆",
    layout="wide",
    initial_sidebar_state="expanded",
)
inject_css()


def get_score_config() -> ScoreConfig:
    config = load_app_data_cached().config
    return ScoreConfig(
        mode=config.get("scoring_mode", "v2"),
        weighted_rules=config.get("weighted_rules", dict(DEFAULT_WEIGHTED_RULES)),
        uniform_rules=config.get("uniform_rules", dict(DEFAULT_UNIFORM_RULES)),
        v2_rules=config.get("v2_rules", dict(DEFAULT_V2_RULES)),
    )


def apply_review_form(prefix: str, pred: Prediction) -> Prediction:
    st.markdown("#### Grupos detectados")
    st.caption("Revise todos os campos. O OCR ajuda, mas a confirmação humana é obrigatória.")
    df = groups_dataframe(pred.groups)
    edited_df = st.data_editor(
        df,
        key=f"{prefix}_groups_editor",
        num_rows="fixed",
        width="stretch",
        column_config={
            "Grupo": st.column_config.TextColumn("Grupo", disabled=True),
            "1º": st.column_config.SelectboxColumn("1º", options=[""] + ALL_TEAMS),
            "2º": st.column_config.SelectboxColumn("2º", options=[""] + ALL_TEAMS),
            "3º": st.column_config.SelectboxColumn("3º", options=[""] + ALL_TEAMS),
            "4º": st.column_config.SelectboxColumn("4º", options=[""] + ALL_TEAMS),
        },
    )
    pred.groups = dataframe_to_groups(edited_df)

    thirds_seed = ", ".join(pred.best_thirds or [])
    thirds_value = st.text_input(
        "Melhores terceiros classificados",
        value=thirds_seed,
        key=f"{prefix}_thirds",
        help="Opcional. Separe por vírgula. Exemplo: Coreia do Sul, Bósnia, Escócia.",
    )
    pred.best_thirds = [x.strip() for x in thirds_value.split(",") if x.strip()]

    st.markdown("#### Mata-mata detectado")
    rows = knockout_to_rows(pred.knockout)
    if rows:
        ko_df = pd.DataFrame(rows)
    else:
        ko_df = pd.DataFrame(columns=["fase", "fase_nome", "jogo", "time_a", "time_b", "vencedor"])

    edited_ko = st.data_editor(
        ko_df,
        key=f"{prefix}_ko_editor",
        num_rows="dynamic",
        width="stretch",
        column_config={
            "fase": st.column_config.SelectboxColumn("fase", options=PHASES, required=True),
            "fase_nome": st.column_config.TextColumn("fase_nome", disabled=True),
            "jogo": st.column_config.NumberColumn("jogo", min_value=1, step=1),
            "time_a": st.column_config.TextColumn("time_a"),
            "time_b": st.column_config.TextColumn("time_b"),
            "vencedor": st.column_config.TextColumn("vencedor"),
        },
    )
    rows = edited_ko.to_dict(orient="records")
    for row in rows:
        row["fase_nome"] = PHASE_LABELS.get(row.get("fase"), row.get("fase_nome", ""))
    pred.knockout = rows_to_knockout(rows)

    pred.champion = st.text_input("Campeã", value=pred.champion or "", key=f"{prefix}_champion").strip() or None
    return pred



# Removed unused OCR/GE parsing functions to clean up the codebase.


def public_home() -> None:
    from src.bolao.storage import load_app_data_cached, load_events
    from src.bolao.ui_live_matches import is_match_open_for_prediction
    import datetime
    import html
    import re

    ctx = load_app_data_cached()
    config = ctx.config
    matches = ctx.matches

    # F20 — Animated Podium Pós-Copa
    if config.get("copa_encerrada", False):
        from src.bolao.live_scoring import calculate_live_ranking
        from src.bolao.utils import avatar_url
        import urllib.parse
        import streamlit.components.v1 as components
        
        # Confetes nas cores do Brasil
        components.html("""
        <script src="https://cdn.jsdelivr.net/npm/canvas-confetti@1.6.0/dist/confetti.browser.min.js"></script>
        <script>
        (function(){
            var end = Date.now() + 4000;
            var colors = ['#009c3b', '#ffdf00', '#002776', '#ffffff'];
            (function frame(){
                confetti({particleCount:3, angle:60, spread:55, origin:{x:0}, colors:colors});
                confetti({particleCount:3, angle:120, spread:55, origin:{x:1}, colors:colors});
                if (Date.now() < end) requestAnimationFrame(frame);
            })();
        })();
        </script>
        """, height=0)

        st.markdown("<h1 style='text-align: center; color: var(--gold);'>🏆 A Copa Acabou!</h1>", unsafe_allow_html=True)
        st.markdown("<h3 style='text-align: center; color: var(--ink); text-align: center;'>Parabéns ao bolão da Cabine do Glória!</h3>", unsafe_allow_html=True)
        
        top3 = []
        combined_enabled = config.get("combined_ranking_enabled", False)
        official = ctx.official
        submissions = ctx.submissions
        live_preds = ctx.live_predictions
        
        if combined_enabled and official:
            from src.bolao.scoring import rank_predictions, ScoreConfig
            from src.bolao.constants import DEFAULT_WEIGHTED_RULES, DEFAULT_UNIFORM_RULES, DEFAULT_V2_RULES
            from src.bolao.utils import normalize_participant_key
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
                    "nome": p_name,
                    "pontos": combined_pts,
                    "classic_points": c_pts,
                    "live_points": l_pts
                })
            combined_list.sort(key=lambda s: (
                -s["pontos"],
                -s["classic_points"],
                -s["live_points"],
                s["nome"].lower()
            ))
            top3 = combined_list[:3]
        else:
            live_scores = calculate_live_ranking(live_preds, matches, config)
            for row in live_scores[:3]:
                top3.append({
                    "nome": row["participant"],
                    "pontos": row["total"]
                })
                
        if top3:
            st.markdown("<br>", unsafe_allow_html=True)
            cols = st.columns(3)
            emojis = ["🥇", "🥈", "🥉"]
            
            if len(top3) == 3:
                with cols[0]:
                    p = top3[1]
                    st.markdown(f"<div style='text-align: center;'>", unsafe_allow_html=True)
                    st.image(avatar_url(p["nome"]), width=80)
                    st.markdown(f"### 🥈 {p['nome']}")
                    st.markdown(f"**{p['pontos']} pts**")
                    st.markdown(f"</div>", unsafe_allow_html=True)
                with cols[1]:
                    p = top3[0]
                    st.markdown(f"<div style='text-align: center; border: 2px solid var(--gold); border-radius: 12px; padding: 10px; background-color: rgba(255,215,0,0.05);'>", unsafe_allow_html=True)
                    st.image(avatar_url(p["nome"]), width=110)
                    st.markdown(f"## 🥇 {p['nome']}")
                    st.markdown(f"**{p['pontos']} pts**")
                    st.markdown(f"</div>", unsafe_allow_html=True)
                with cols[2]:
                    p = top3[2]
                    st.markdown(f"<div style='text-align: center;'>", unsafe_allow_html=True)
                    st.image(avatar_url(p["nome"]), width=80)
                    st.markdown(f"### 🥉 {p['nome']}")
                    st.markdown(f"**{p['pontos']} pts**")
                    st.markdown(f"</div>", unsafe_allow_html=True)
            else:
                for i, p in enumerate(top3):
                    with cols[i]:
                        st.markdown(f"<div style='text-align: center;'>", unsafe_allow_html=True)
                        st.image(avatar_url(p["nome"]), width=90)
                        st.markdown(f"### {emojis[i]} {p['nome']}")
                        st.markdown(f"**{p['pontos']} pts**")
                        st.markdown(f"</div>", unsafe_allow_html=True)

            p_text = f"🏆 *Bolão da Cabine do Glória — Copa 2026 encerrado!*\n\n"
            for i, p in enumerate(top3):
                p_text += f"{emojis[i]} {p['nome']} — {p['pontos']} pts\n"
            p_text += f"\nParabéns aos campeões! 🎉"
            
            st.markdown("<br><br>", unsafe_allow_html=True)
            st.link_button("📲 Compartilhar no WhatsApp", f"https://wa.me/?text={urllib.parse.quote(p_text)}", width="stretch")
            
        return

    hero(
        title="Bolão da Copa 2026",
        subtitle="Cabine do Glória",
        description="Palpite jogo a jogo, acompanhe o ranking em tempo real e provoque a galera."
    )

    # Banner principal com CTAs rápidos
    col_hero_cta1, col_hero_cta2 = st.columns(2)
    with col_hero_cta1:
        if st.button("⚽ Palpitar nos Jogos de Hoje", type="primary", key="home_hero_cta_jogos", width="stretch"):
            navigate_to("Jogos de Hoje")
    with col_hero_cta2:
        if st.button("🏆 Ver Ranking Jogo a Jogo", key="home_hero_cta_ranking", width="stretch"):
            navigate_to("Ranking")

    st.markdown("<br>", unsafe_allow_html=True)

    # BANNER DINÂMICO
    now = datetime.datetime.now().isoformat()
    open_today = []
    next_close_m = None
    for m in matches:
        if is_match_open_for_prediction(m, now):
            try:
                starts_dt = datetime.datetime.fromisoformat(m.starts_at)
                today_dt = datetime.datetime.now()
                if starts_dt.date() == today_dt.date():
                    open_today.append(m)
                    if next_close_m is None or m.lock_at < next_close_m.lock_at:
                        next_close_m = m
            except Exception:
                pass
    
    if open_today:
        next_close_time = next_close_m.lock_at.split("T")[1][:5] if next_close_m and next_close_m.lock_at else "—"
        st.markdown(
            f"""
            <div class="callout warning" style="margin-bottom: 25px; width: 100%;">
                <h4 style="margin: 0;">🔥 Há jogos abertos hoje!</h4>
                <p style="margin: 5px 0 0; font-size: 14px;">Você tem <b>{len(open_today)}</b> partida(s) abertas hoje no Jogo a Jogo. O próximo palpite fecha às <b>{next_close_time}</b> para <b>{next_close_m.home_team} x {next_close_m.away_team}</b>.</p>
            </div>
            """,
            unsafe_allow_html=True
        )
    else:
        # Encontrar próximo jogo agendado futuro
        future_matches = [m for m in matches if m.starts_at and m.starts_at > now and m.status != "result_approved"]
        future_matches.sort(key=lambda m: m.starts_at)
        if future_matches:
            next_m = future_matches[0]
            st.markdown(
                f"""
                <div class="callout info" style="margin-bottom: 20px; width: 100%;">
                    <h5 style="margin: 0;">⏳ Próxima Partida</h5>
                    <p style="margin: 5px 0 0; font-size: 14px;">
                        <b>{next_m.home_team} x {next_m.away_team}</b> ({next_m.round_label}) em <b>{next_m.starts_at.replace('T', ' ')}</b>.
                    </p>
                </div>
                """,
                unsafe_allow_html=True
            )

    # Se há jogos bloqueados, mostra link do Match Center
    blocked_matches = [m for m in matches if m.status != "result_approved" and not is_match_open_for_prediction(m, now)]
    if blocked_matches:
        blocked_matches.sort(key=lambda m: m.starts_at, reverse=True)
        recent_blocked = blocked_matches[0]
        st.markdown(
            f"""
            <div class="callout success" style="margin-bottom: 20px; width: 100%;">
                <h5 style="margin: 0;">🏟️ Match Center em Andamento</h5>
                <p style="margin: 5px 0 0; font-size: 14px;">
                    O palpite para <b>{recent_blocked.home_team} x {recent_blocked.away_team}</b> fechou! Acompanhe as apostas e secadas em tempo real.
                </p>
            </div>
            """,
            unsafe_allow_html=True
        )
        if st.button(f"👁️ Abrir Match Center: {recent_blocked.home_team} x {recent_blocked.away_team}", key="btn_home_match_center_banner", width="stretch"):
            st.session_state["match_center_selected_match_id"] = recent_blocked.match_id
            navigate_to("Match Center")

    # N2 - Resumo "O que rolou hoje"
    from datetime import timezone, timedelta
    tz_br = timezone(timedelta(hours=-3))
    now_br = datetime.datetime.now(tz_br)
    
    today_str = now_br.strftime("%Y-%m-%d")
    jogos_hoje = [m for m in matches if m.starts_at and m.starts_at.startswith(today_str)]
    jogos_concluidos_hoje = [m for m in jogos_hoje if m.status == "result_approved"]
    
    if now_br.hour >= 23 and jogos_concluidos_hoje:
        st.markdown("<br>", unsafe_allow_html=True)
        with st.container(border=True):
            st.markdown(
                """
                <div style="border-left: 5px solid var(--gold); padding-left: 15px;">
                    <h3 style="margin: 0; color: var(--gold);">🌙 O que rolou hoje</h3>
                    <p style="color: var(--muted); font-size: 14px; margin: 4px 0 15px 0;">Resumo das partidas concluídas na data de hoje e as principais zebras do bolão.</p>
                </div>
                """,
                unsafe_allow_html=True
            )
            
            for m in jogos_concluidos_hoje:
                st.markdown(f"⚽ **{m.home_team} {m.official_home_goals} × {m.official_away_goals} {m.away_team}** ({m.round_label})")
                
            from src.bolao.storage import load_live_predictions
            live_preds_for_summary = load_live_predictions()
            
            def calcular_zebra_do_dia(jogos: list, predictions: list) -> dict | None:
                pior_acerto = None
                for jogo in jogos:
                    palpites_jogo = [p for p in predictions if p.match_id == jogo.match_id]
                    if not palpites_jogo:
                        continue
                    
                    acertos = 0
                    for p in palpites_jogo:
                        real_home, real_away = jogo.official_home_goals, jogo.official_away_goals
                        pred_home, pred_away = p.predicted_home_goals, p.predicted_away_goals
                        
                        real_outcome = "home" if real_home > real_away else ("away" if real_home < real_away else "draw")
                        pred_outcome = "home" if pred_home > pred_away else ("away" if pred_home < pred_away else "draw")
                        
                        if real_outcome == pred_outcome:
                            acertos += 1
                            
                    pct_acerto = acertos / len(palpites_jogo)
                    if pior_acerto is None or pct_acerto < pior_acerto["pct"]:
                        pior_acerto = {"jogo": jogo, "pct": pct_acerto, "total_palpites": len(palpites_jogo), "acertos": acertos}
                return pior_acerto

            zebra = calcular_zebra_do_dia(jogos_concluidos_hoje, live_preds_for_summary)
            
            texto_wa = f"🌙 *BOLÃO DA CABINE DO GLÓRIA - Resumo do Dia*\n\n"
            for m in jogos_concluidos_hoje:
                texto_wa += f"👉 {m.home_team} {m.official_home_goals} x {m.official_away_goals} {m.away_team}\n"
                
            if zebra:
                pct_val = zebra['pct'] * 100
                st.markdown(
                    f"""
                    <div style="background-color: var(--gold-bg); padding: 12px; border-radius: 8px; margin-top: 15px; border: 1px solid var(--gold); color: var(--ink);">
                        🦓 <b>Zebra do dia:</b> {zebra['jogo'].home_team} × {zebra['jogo'].away_team}
                        (apenas {pct_val:.0f}% do grupo acertou o vencedor!)
                    </div>
                    """,
                    unsafe_allow_html=True
                )
                texto_wa += f"\n🦓 *Zebra do Dia:* {zebra['jogo'].home_team} x {zebra['jogo'].away_team} (apenas {pct_val:.0f}% acertaram o vencedor!)\n"
            
            texto_wa += f"\n👉 Acompanhe o ranking completo em: https://bolaodogloria.streamlit.app/"
            
            import urllib.parse
            st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
            st.link_button("📲 Compartilhar Resumo do Dia no WhatsApp", f"https://wa.me/?text={urllib.parse.quote(texto_wa)}", key="btn_share_daily_summary", width="stretch")

    # CARDS E SEÇÕES DO BOLÃO
    st.markdown("### ⚽ Atividades e Modos do Bolão")
    
    col_main1, col_main2 = st.columns([3, 2])
    with col_main1:
        with st.container(border=True):
            st.markdown(
                f"""
                <div style="font-size: 36px; margin-bottom: 8px;">🎯</div>
                <h3 style="margin: 0 0 8px 0; color: var(--ink);">Novo Modo Jogo a Jogo</h3>
                <p style="font-size: 14px; margin-bottom: 12px; color: var(--muted);">
                    Palpite nos placares de cada partida individualmente ao longo de toda a Copa do Mundo! Envie seus palpites até 10 minutos antes de cada jogo.
                </p>
                <div style="margin-bottom: 16px;">
                    <span style="font-weight: bold; font-size: 13px;">Status:</span>
                    {'<span class="badge success">🟢 Disponível</span>' if config.get("live_mode_enabled", True) else '<span class="badge error">🔒 Suspenso</span>'}
                </div>
                """,
                unsafe_allow_html=True
            )
            if config.get("live_mode_enabled", True):
                if st.button("⚡ Ir para Jogos de Hoje", key="btn_home_live_guess_new", type="primary", width="stretch"):
                    navigate_to("Jogos de Hoje")
                    
        # C2 - Módulo Brasil Card
        with st.container(border=True):
            st.markdown("""
            <div style="background: linear-gradient(135deg, #1a472a, #0d2818);
                         border-radius: 12px; padding: 20px; border: 1px solid #ffd700; margin-bottom: 15px; box-shadow: 0 4px 15px rgba(26,71,42,0.3);">
                <div style="font-size: 32px; margin-bottom: 8px;">🇧🇷</div>
                <h3 style="margin: 0 0 8px 0; color: #ffd700;">Módulo Brasil</h3>
                <p style="color: #e0e0e0; font-size: 14px; margin-bottom: 12px; line-height: 1.4;">
                    Escale os goleadores e assistentes da Seleção, aposte no
                    artilheiro da Copa e acompanhe o Ranking Canarinho!
                </p>
                <div style="margin-bottom: 12px;">
                    <span style="font-weight: bold; font-size: 13px; color: white;">Status:</span>
                    <span style="background-color: #22c55e; color: white; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: bold;">🟢 ABERTO</span>
                </div>
            </div>
            """, unsafe_allow_html=True)
            if st.button("⚽ Ir para Módulo Brasil", key="home_modulo_brasil", width="stretch"):
                navigate_to("🇧🇷 Jogos do Brasil")
                    
        with st.container(border=True):
            st.markdown(
                f"""
                <div style="font-size: 32px; margin-bottom: 8px;">👤</div>
                <h4 style="margin: 0 0 8px 0; color: var(--ink);">Minha Cartela Pessoal</h4>
                <p style="font-size: 13.5px; margin-bottom: 12px; color: var(--muted);">
                    Veja todos os seus palpites clássicos, jogo a jogo, suas conquistas (insígnias) e compartilhe seu desempenho no WhatsApp!
                </p>
                """,
                unsafe_allow_html=True
            )
            if st.button("📋 Acessar Minha Cartela", key="btn_home_my_cartela_new", width="stretch"):
                navigate_to("Minha Cartela")

    with col_main2:
        with st.container(border=True):
            st.markdown(
                f"""
                <div style="font-size: 32px; margin-bottom: 8px;">🏆</div>
                <h4 style="margin: 0 0 8px 0; color: var(--ink);">Ranking Jogo a Jogo</h4>
                <p style="font-size: 13.5px; margin-bottom: 12px; color: var(--muted);">
                    Acompanhe a classificação em tempo real e o pódio de líderes da Copa no Jogo a Jogo!
                </p>
                """,
                unsafe_allow_html=True
            )
            if st.button("🥇 Ver Rankings", key="btn_home_rankings_new", width="stretch"):
                navigate_to("Ranking")
                
        with st.container(border=True):
            st.markdown(
                f"""
                <div style="font-size: 28px; margin-bottom: 8px;">🏛️</div>
                <h4 style="margin: 0 0 8px 0; color: var(--ink);">Modo Clássico (Secundário)</h4>
                <p style="font-size: 13px; margin-bottom: 12px; color: var(--muted);">
                    Preenchimento único da cartela pré-Copa (fase de grupos e mata-mata).
                </p>
                <div style="margin-bottom: 12px; font-size: 12px;">
                    <span style="font-weight: bold;">Status:</span>
                    {'<span class="badge error">🔒 Encerrado</span>' if config.get("is_bolao_locked", False) else '<span class="badge success">🟢 Aberto</span>'}
                </div>
                """,
                unsafe_allow_html=True
            )
            if not config.get("is_bolao_locked", False):
                if st.button("🚀 Preencher Clássico", key="btn_home_classic_guess_new", width="stretch"):
                    navigate_to("Palpite Clássico")
            else:
                if st.button("🔍 Ver Palpites Clássicos", key="btn_home_classic_view_new", width="stretch"):
                    navigate_to("Ranking")

    # Feed de Atividades
    if config.get("public_features", {}).get("show_public_activity_feed", True):
        st.markdown("---")
        st.markdown("### 📣 Feed de Atividades")
        from src.bolao.storage import get_archived_keys
        archived_keys = get_archived_keys()
        
        events = load_events(limit=25, visibility="public")
        filtered_events = []
        for ev in events:
            # 1. Skip if archived
            meta = ev.get("metadata", {})
            pkey = meta.get("participant_key")
            if pkey and pkey in archived_keys:
                continue
                
            # 2. Sanitizar a mensagem (esconder confirmation codes ou hashes longos)
            message = ev.get("message", "")
            message_clean = re.sub(r'\b[a-f0-9]{12,}\b', '[CÓDIGO OCULTO]', message)
            
            ts = ev["timestamp"].split("T")[0]
            time = ev["timestamp"].split("T")[1][:5]
            filtered_events.append(f"🗓️ `{ts} {time}` · {message_clean}")
            if len(filtered_events) >= 5:
                break
                
        if filtered_events:
            for item in filtered_events:
                st.markdown(item)
        else:
            st.caption("Nenhum evento registrado ainda.")

    st.markdown("---")
    col_adm_left, col_adm_mid, col_adm_right = st.columns([2, 1, 2])
    with col_adm_mid:
        if st.button("🔒 Área Admin", key="home_admin_login_btn", width="stretch"):
            navigate_to("Admin Login")





def public_submission() -> None:
    if st.button("⬅️ Voltar ao Início", key="back_to_home_submission", width="stretch"):
        navigate_to("Início")
    if st.session_state.get("last_submitted_prediction"):
        pred = st.session_state["last_submitted_prediction"]
        champion = pred.champion or "Indefinido"
        
        finalists = []
        ko_final = pred.knockout.get("final", [])
        if ko_final and len(ko_final) > 0:
            if ko_final[0].a:
                finalists.append(ko_final[0].a)
            if ko_final[0].b:
                finalists.append(ko_final[0].b)
        
        finalist_1 = finalists[0] if len(finalists) > 0 else "Indefinido"
        finalist_2 = finalists[1] if len(finalists) > 1 else "Indefinido"
        
        st.markdown(
            f"""
            <div class="success-card" style="margin-bottom: 25px; padding: 25px; border-radius: 12px; background-color: var(--panel); border: 2px solid var(--gold); color: var(--ink);">
                <div style="font-size: 48px; text-align: center;">🏆</div>
                <h3 style="text-align: center; color: var(--ink); margin-top: 10px;">Palpite Enviado com Sucesso!</h3>
                <p style="text-align: center; color: var(--muted);">Seu palpite foi registrado no sistema. O ranking será atualizado quando a organização aprovar os resultados oficiais.</p>
                <hr style="border: 0; border-top: 1px solid var(--line); margin: 20px 0;">
                <div style="text-align: center; margin-bottom: 15px;">
                    <span style="font-size: 14px; color: var(--muted); text-transform: uppercase; letter-spacing: 1px;">Código de Confirmação</span>
                    <h2 style="color: var(--gold); margin: 5px 0; font-family: monospace; letter-spacing: 2px; font-size: 28px;">{pred.submission_id}</h2>
                </div>
                <div style="display: flex; justify-content: space-around; background: var(--bg); padding: 15px; border-radius: 8px; border: 1px dashed var(--gold); margin-bottom: 20px; color: var(--ink);">
                    <div style="text-align: center; flex: 1;">
                        <span style="font-size: 12px; color: var(--muted);">Campeão</span>
                        <div style="font-weight: bold; color: var(--ink);">{champion}</div>
                    </div>
                    <div style="text-align: center; border-left: 1px solid var(--line); padding-left: 20px; flex: 1;">
                        <span style="font-size: 12px; color: var(--muted);">Grande Final</span>
                        <div style="font-weight: bold; color: var(--ink);">{finalist_1} x {finalist_2}</div>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )
        
        share_text = f"🏆 Meu palpite no Bolão da Cabine do Glória está feito!\nCampeão: {champion}\nFinal: {finalist_1} x {finalist_2}\nCódigo: {pred.submission_id}\nAcompanhe o ranking no app."
        
        st.markdown("#### 📱 Compartilhar no WhatsApp")
        st.text_area("Texto de compartilhamento", value=share_text, height=120, key="share_text_area", disabled=True)
        
        import urllib.parse
        encoded_text = urllib.parse.quote(share_text)
        whatsapp_url = f"https://api.whatsapp.com/send?text={encoded_text}"
        
        col_sh1, col_sh2, col_sh3 = st.columns(3)
        with col_sh1:
            st.link_button("💬 Enviar no WhatsApp", whatsapp_url, width="stretch", type="primary")
        with col_sh2:
            st.code(share_text, language="text", line_numbers=False)
            
        with col_sh3:
            if st.button("📊 Ir para o Ranking", width="stretch"):
                st.session_state.pop("last_submitted_prediction", None)
                navigate_to("Ranking")
                
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🆕 Fazer outro palpite", width="stretch"):
            st.session_state.pop("last_submitted_prediction", None)
            st.rerun()
        return

    hero("Palpite Clássico", "Fluxo do participante", "Monte seu palpite completo da Copa do Mundo 2026 pelo simulador interativo.")

    st.markdown("### 1. Identificação")
    name = st.text_input("Seu nome no bolão", placeholder="Ex.: César", key="public_sim_name")
    
    if not name.strip():
        st.info("Informe seu nome para começar a simulação.")
        st.session_state.pop("sim_prediction", None)
        st.session_state.pop("sim_public", None)
        st.session_state.pop("edit_mode", None)
        st.session_state.pop("show_delete_confirm", None)
        return

    name_clean = name.strip()
    ctx = load_app_data_cached()
    config = ctx.config
    is_locked = config.get("is_bolao_locked", False)
    
    submissions = ctx.submissions
    existing = [p for p in submissions if p.participant.strip().lower() == name_clean.lower()]
    
    if existing and "edit_mode" not in st.session_state:
        existing_pred = existing[0]
        
        if is_locked:
            st.warning(f"🔒 Os palpites estão bloqueados. Existe um palpite cadastrado para **{existing_pred.participant}**, mas novas submissões ou edições estão desabilitadas.")
            if st.button(f"🔍 Visualizar o palpite de {existing_pred.participant}", width="stretch"):
                st.session_state["sim_prediction"] = existing_pred
                init_simulator_state(existing_pred, force_reset=True)
                st.session_state["edit_mode"] = "view"
                st.rerun()
        else:
            st.info(f"💡 Encontramos um palpite já enviado para **{existing_pred.participant}**.")
            col_btn1, col_btn2, col_btn3 = st.columns(3)
            with col_btn1:
                if st.button("✏️ Editar palpite existente", type="primary", width="stretch"):
                    st.session_state["sim_prediction"] = existing_pred
                    init_simulator_state(existing_pred, force_reset=True)
                    st.session_state["edit_mode"] = "edit"
                    st.rerun()
            with col_btn2:
                if st.button("❌ Excluir meu palpite", width="stretch"):
                    st.session_state["show_delete_confirm"] = True
                    st.rerun()
            with col_btn3:
                if st.button("🆕 Iniciar novo do zero", width="stretch"):
                    new_pred = Prediction(
                        participant=existing_pred.participant,
                        submission_id=existing_pred.submission_id,
                        submitted_at=existing_pred.submitted_at,
                        status="rascunho"
                    )
                    st.session_state["sim_prediction"] = new_pred
                    init_simulator_state(new_pred, force_reset=True)
                    st.session_state["edit_mode"] = "edit"
                    st.rerun()
                    
        if st.session_state.get("show_delete_confirm", False):
            st.markdown("---")
            st.warning(f"⚠️ Tem certeza que deseja excluir permanentemente o palpite de **{existing_pred.participant}**? Esta ação não pode ser desfeita.")
            c_del1, c_del2 = st.columns(2)
            with c_del1:
                if st.button("Sim, excluir permanentemente", type="primary", width="stretch"):
                    delete_submission(existing_pred.submission_id)
                    st.success("Seu palpite foi excluído do sistema.")
                    st.session_state.pop("sim_prediction", None)
                    st.session_state.pop("sim_public", None)
                    st.session_state.pop("edit_mode", None)
                    st.session_state.pop("show_delete_confirm", None)
                    st.balloons()
                    st.rerun()
            with c_del2:
                if st.button("Cancelar", width="stretch"):
                    st.session_state.pop("show_delete_confirm", None)
                    st.rerun()
        return

    if not existing and is_locked:
        st.error("🔒 Os palpites estão encerrados pelo administrador. Não é possível enviar novos palpites.")
        return

    if "sim_prediction" not in st.session_state or st.session_state["sim_prediction"].participant.lower() != name_clean.lower():
        new_pred = Prediction(
            participant=name_clean,
            submission_id=stable_id(name_clean, now_iso()),
            submitted_at=now_iso(),
            status="rascunho"
        )
        st.session_state["sim_prediction"] = new_pred
        init_simulator_state(new_pred, force_reset=True)
        st.session_state["edit_mode"] = "new"

    pred = st.session_state["sim_prediction"]
    edit_mode = st.session_state.get("edit_mode", "new")

    if edit_mode == "view":
        st.info("👁️ Você está visualizando o palpite enviado. Alterações não serão salvas.")
        render_simulator(pred)
        from src.bolao.storage import load_brasil_palpites_classicos
        classic_brasil_guesses = load_brasil_palpites_classicos()
        my_brasil_guess = next((g for g in classic_brasil_guesses if g["participante_nome"].lower() == name_clean.lower()), None)
        if my_brasil_guess:
            st.markdown("### 🇧🇷 Palpites do Módulo Brasil")
            st.write(f"⚽ **Artilheiro do Brasil:** {my_brasil_guess.get('artilheiro_brasil_copa') or 'Nenhum'}")
            st.write(f"🌍 **Artilheiro Geral:** {my_brasil_guess.get('artilheiro_geral_copa') or 'Nenhum'}")
            st.write(f"🥇 **Gol de Ouro (1º gol do BR):** {my_brasil_guess.get('gol_de_ouro') or 'Nenhum'}")
        if st.button("Voltar", width="stretch"):
            st.session_state.pop("sim_prediction", None)
            st.session_state.pop("sim_public", None)
            st.session_state.pop("edit_mode", None)
            st.rerun()
    else:
        if edit_mode == "edit":
            st.info(f"✏️ Você está editando o palpite de **{pred.participant}**.")
            
        updated_pred = render_simulator(pred)
        
        # Load or initialize Módulo Brasil selections
        if "selected_artilheiro_brasil" not in st.session_state or "selected_artilheiro_geral" not in st.session_state or "selected_gol_de_ouro" not in st.session_state or st.session_state.get("last_checked_participant_name") != name_clean:
            st.session_state["last_checked_participant_name"] = name_clean
            from src.bolao.storage import load_brasil_palpites_classicos
            classic_brasil_guesses = load_brasil_palpites_classicos()
            my_brasil_guess = next((g for g in classic_brasil_guesses if g["participante_nome"].lower() == name_clean.lower()), None)
            if my_brasil_guess:
                st.session_state["selected_artilheiro_brasil"] = my_brasil_guess.get("artilheiro_brasil_copa")
                st.session_state["selected_artilheiro_geral"] = my_brasil_guess.get("artilheiro_geral_copa")
                st.session_state["selected_gol_de_ouro"] = my_brasil_guess.get("gol_de_ouro")
            else:
                st.session_state["selected_artilheiro_brasil"] = None
                st.session_state["selected_artilheiro_geral"] = None
                st.session_state["selected_gol_de_ouro"] = None
        
        if updated_pred:
            st.markdown("---")
            st.markdown("### 5. Palpites Extras (Artilharia e Gol de Ouro) 🇧🇷")
            st.caption("Responda estas 3 perguntas especiais do Módulo Brasil para finalizar o preenchimento.")
            
            from src.bolao.constants import ELENCO_BRASIL_2026
            from src.bolao.utils import buscar_jogador_copa
            
            tab_art_br, tab_art_ge, tab_gold = st.tabs(["🇧🇷 Artilheiro do Brasil", "🌍 Artilheiro Geral", "🥇 Gol de Ouro"])
            
            with tab_art_br:
                st.write("Quem será o maior artilheiro do Brasil na Copa inteira?")
                if is_locked:
                    from src.bolao.storage import load_brasil_palpites_classicos
                    classic_brasil_guesses = load_brasil_palpites_classicos()
                    votes = [g.get("artilheiro_brasil_copa") for g in classic_brasil_guesses if g.get("artilheiro_brasil_copa")]
                    from collections import Counter
                    counts = Counter(votes)
                    top_votes = counts.most_common(3)
                    medals = ["🥇", "🥈", "🥉"]
                    vote_strs = []
                    for i, (player, cnt) in enumerate(top_votes):
                        vote_strs.append(f"{medals[i]} {player} — {cnt} {'voto' if cnt == 1 else 'votos'}")
                    if vote_strs:
                        st.markdown(f"📊 **O grupo apostou:** {' · '.join(vote_strs)}")
                
                curr_sel = st.session_state.get("selected_artilheiro_brasil")
                st.write(f"Selecionado atualmente: **{curr_sel or 'Nenhum'}**")
                new_sel = render_player_single_select("art_br", ELENCO_BRASIL_2026, curr_sel, disabled=is_locked)
                if new_sel != curr_sel:
                    st.session_state["selected_artilheiro_brasil"] = new_sel
                    st.rerun()
                    
            with tab_art_ge:
                st.write("Quem será o Artilheiro Geral de toda a Copa 2026?")
                curr_sel_ge = st.session_state.get("selected_artilheiro_geral")
                st.write(f"Selecionado atualmente: **{curr_sel_ge or 'Nenhum'}**")
                
                if not is_locked:
                    query = st.text_input("Digite o nome do jogador para buscar:", key="artilheiro_geral_query")
                    if query:
                        results = buscar_jogador_copa(query)
                        if results:
                            st.write("🔍 Resultados da busca (clique para escolher):")
                            cols_sug = st.columns(min(len(results), 4))
                            for r_idx, r in enumerate(results):
                                col_suggestion = cols_sug[r_idx % len(cols_sug)]
                                with col_suggestion:
                                    if st.button(f"{r['nome']} ({r['selecao']})", key=f"sug_ge_{r['nome']}_{r_idx}", width="stretch"):
                                        st.session_state["selected_artilheiro_geral"] = f"{r['nome']} ({r['selecao']})"
                                        st.rerun()
                        else:
                            st.info("Nenhum jogador encontrado.")
                    else:
                        st.write("🔥 Sugestões de Favoritos (clique para escolher):")
                        favorites = [
                            {"nome": "Mbappé", "selecao": "França"},
                            {"nome": "Haaland", "selecao": "Noruega"},
                            {"nome": "Salah", "selecao": "Egito"},
                            {"nome": "Kane", "selecao": "Inglaterra"},
                            {"nome": "Lewandowski", "selecao": "Polônia"},
                            {"nome": "Lamine Yamal", "selecao": "Espanha"},
                            {"nome": "Vini Jr.", "selecao": "Brasil"},
                            {"nome": "Messi", "selecao": "Argentina"},
                            {"nome": "Osimhen", "selecao": "Nigéria"},
                            {"nome": "Bellingham", "selecao": "Inglaterra"}
                        ]
                        cols_fav = st.columns(5)
                        for f_idx, fav in enumerate(favorites):
                            col_fav = cols_fav[f_idx % 5]
                            with col_fav:
                                if st.button(f"{fav['nome']}\n({fav['selecao']})", key=f"fav_{fav['nome']}", width="stretch"):
                                    st.session_state["selected_artilheiro_geral"] = f"{fav['nome']} ({fav['selecao']})"
                                    st.rerun()
                else:
                    st.info("Palpites bloqueados.")
                    
            with tab_gold:
                st.write("Qual jogador marcará o primeiro gol do Brasil na Copa inteira?")
                curr_sel_gold = st.session_state.get("selected_gol_de_ouro")
                st.write(f"Selecionado atualmente: **{curr_sel_gold or 'Nenhum'}**")
                new_sel_gold = render_player_single_select("gold_de_ouro", ELENCO_BRASIL_2026, curr_sel_gold, disabled=is_locked)
                if new_sel_gold != curr_sel_gold:
                    st.session_state["selected_gol_de_ouro"] = new_sel_gold
                    st.rerun()

            brasil_complete = (
                st.session_state.get("selected_artilheiro_brasil") is not None and
                st.session_state.get("selected_artilheiro_geral") is not None and
                st.session_state.get("selected_gol_de_ouro") is not None
            )
            
            st.markdown("---")
            st.markdown("### 6. Confirmar e enviar")
            if edit_mode == "edit":
                st.caption("Ao confirmar, o palpite existente será atualizado com os novos resultados.")
                save_btn_text = "Salvar alterações no meu palpite"
            else:
                st.caption("Ao confirmar, o palpite será salvo no sistema.")
                save_btn_text = "Confirmar e salvar meu palpite"
                
            if not brasil_complete:
                st.warning("⚠️ Selecione o Artilheiro do Brasil, o Artilheiro Geral e o Gol de Ouro nas abas acima para habilitar o envio.")
                
            col_save1, col_save2 = st.columns(2)
            with col_save1:
                if st.button(save_btn_text, type="primary", key="btn_save_sim_prediction", width="stretch", disabled=not brasil_complete):
                    # Final check for locking status
                    config = load_config()
                    if config.get("is_bolao_locked", False):
                        st.error("🔒 O bolão foi bloqueado recentemente. Não é mais possível salvar ou editar palpites.")
                        return
                    
                    # Validate completeness
                    is_complete, missing = validate_prediction_complete(updated_pred)
                    if not is_complete:
                        st.error("⚠️ Palpite incompleto. Verifique os itens abaixo:")
                        for item in missing:
                            st.markdown(f"- {item}")
                        return
                        
                    updated_pred.status = "confirmado"
                    updated_pred.submitted_at = now_iso()
                    save_submission(updated_pred)
                    
                    # Save Módulo Brasil classic predictions
                    from src.bolao.storage import save_brasil_palpite_classico
                    save_brasil_palpite_classico({
                        "participante_nome": updated_pred.participant,
                        "artilheiro_brasil_copa": st.session_state.get("selected_artilheiro_brasil"),
                        "artilheiro_geral_copa": st.session_state.get("selected_artilheiro_geral"),
                        "gol_de_ouro": st.session_state.get("selected_gol_de_ouro"),
                        "pontos_artilheiro_brasil": 0,
                        "pontos_artilheiro_geral": 0,
                        "pontos_gol_de_ouro": 0
                    })
                    
                    st.session_state["last_submitted_prediction"] = updated_pred
                    
                    st.session_state.pop("sim_prediction", None)
                    st.session_state.pop("sim_public", None)
                    st.session_state.pop("edit_mode", None)
                    
                    st.toast("Palpite enviado com sucesso!")
                    st.balloons()
                    st.rerun()
            with col_save2:
                if st.button("Descartar e voltar", width="stretch"):
                    st.session_state.pop("sim_prediction", None)
                    st.session_state.pop("sim_public", None)
                    st.session_state.pop("edit_mode", None)
                    st.rerun()


def public_ranking() -> None:
    if st.button("⬅️ Voltar ao Início", key="back_to_home_ranking", width="stretch"):
        navigate_to("Início")
    render_rankings_tabs(is_admin=False)


def admin_dashboard() -> None:
    hero("Painel do admin", "Controle do bolão", "Gerencie participantes, resultados, palpites jogo a jogo, auditoria e configurações.")
    ctx = load_app_data_cached()
    import datetime
    
    matches = ctx.matches
    submissions = ctx.submissions
    live_preds = ctx.live_predictions
    official = ctx.official
    now = datetime.datetime.now().isoformat()
    
    # KPIs Jogo a Jogo e Clássico
    open_count = len([m for m in matches if is_match_open_for_prediction(m, now)])
    blocked_count = len([m for m in matches if m.status != "result_approved" and not is_match_open_for_prediction(m, now)])
    pending_count = len([m for m in matches if m.status != "result_approved"])
    total_live_preds = len(live_preds)
    
    active_parts = load_registered_participants(include_archived=False)
    archived_parts = load_archived_participants()
    
    st.markdown("#### 📊 KPIs Operacionais (Jogo a Jogo & Clássico)")
    kpi_grid([
        ("Jogos Abertos", str(open_count)),
        ("Jogos Bloqueados", str(blocked_count)),
        ("Resultados Pendentes", str(pending_count)),
        ("Palpites Jogo a Jogo", str(total_live_preds)),
    ])
    
    kpi_grid([
        ("Participantes Ativos", str(len(active_parts))),
        ("Participantes Arquivados", str(len(archived_parts))),
    ])

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Carregar dados de demonstração", width="stretch"):
            load_demo_state()
            st.success("Demonstração carregada.")
            st.rerun()
    with col2:
        if st.checkbox("⚠️ Desbloquear limpeza de estado", key="confirm_reset_state_chk"):
            st.markdown('<div class="error-box"><strong>Atenção:</strong> Isso apagará permanentemente todos os palpites, resultado oficial e configurações. Esta ação é irreversível e exige backup obrigatório!</div>', unsafe_allow_html=True)
            confirm_word = st.text_input("Digite LIMPAR para confirmar:", key="confirm_reset_state_word")
            if st.button("🚨 Apagar todos os dados", type="primary", disabled=confirm_word != "LIMPAR", width="stretch"):
                try:
                    from tools.make_backup import make_backup
                    backup_dir = make_backup()
                    st.info(f"📦 Backup de segurança gerado: {backup_dir}")
                except Exception as e:
                    st.error(f"Erro ao gerar backup: {e}. Operação abortada por segurança.")
                    return
                reset_state()
                st.toast("Todo o estado foi reiniciado com sucesso.")
                st.rerun()

    st.markdown("---")
    st.markdown("### 🎛️ Painel de Controle (Navegação Rápida)")
    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("👥 Participantes", key="nav_admin_part", width="stretch"):
            navigate_to("Participantes")
    with c2:
        if st.button("🏟️ Palpites Jogo a Jogo", key="nav_admin_palpites_live", width="stretch"):
            navigate_to("Palpites Jogo a Jogo")
    with c3:
        if st.button("📅 Jogos e Agenda", key="nav_admin_matches", width="stretch"):
            navigate_to("Jogos e Agenda")

    c4, c5, c6 = st.columns(3)
    with c4:
        if st.button("⚽ Resultados Oficiais", key="nav_admin_results", width="stretch"):
            navigate_to("Resultados Oficiais")
    with c5:
        if st.button("🏆 Ranking", key="nav_admin_ranking", width="stretch"):
            navigate_to("Ranking")
    with c6:
        if st.button("📦 Exportações", key="nav_admin_exports", width="stretch"):
            navigate_to("Exportações")

    c7, c8, c9 = st.columns(3)
    with c7:
        if st.button("⚙️ Configurações", key="nav_admin_settings", width="stretch"):
            navigate_to("Configurações")
    with c8:
        if st.button("🛡️ Auditoria", key="nav_admin_auditoria", width="stretch"):
            navigate_to("Auditoria")
    with c9:
        if st.button("📖 Ajuda", key="nav_admin_help", width="stretch"):
            navigate_to("Ajuda")

    st.markdown("<br>", unsafe_allow_html=True)
    c10, c11, c12 = st.columns(3)
    with c10:
        if st.button("🇧🇷 Seleção Brasileira", key="nav_admin_brasil", width="stretch"):
            navigate_to("🇧🇷 Seleção Brasileira")

    st.markdown("---")
    st.markdown("### 📋 Histórico de Auditoria (Últimos Eventos)")
    events = load_events(20)
    if events:
        for ev in events:
            ts = ev["timestamp"].replace("T", " ")[:19]
            st.markdown(f"⏱️ `{ts}` — {ev['message']}")
    else:
        st.caption("Nenhum evento registrado ainda.")


def admin_participants() -> None:
    if st.button("⬅️ Voltar ao Painel Admin", key="back_to_dashboard_participants", width="stretch"):
        navigate_to("Dashboard")
    render_page_header("Admin", "Participantes", "Gerencie os palpites enviados pelos participantes.", "👥")
    submissions = load_app_data_cached().submissions
    from src.bolao.storage import load_live_predictions, save_live_predictions, load_matches, load_registered_participants, delete_registered_participant, register_participant
    from src.bolao.utils import normalize_participant_key
    from src.bolao.ui_simulator import init_simulator_state
    
    from src.bolao.storage import load_submissions, load_live_predictions, load_registered_participants, load_archived_participants, archive_participant, restore_participant
    
    submissions = load_submissions(include_archived=True)
    live_preds = load_live_predictions(include_archived=True)
    registered = load_registered_participants(include_archived=True)
    
    all_names_set = set()
    for s in submissions:
        all_names_set.add(s.participant)
    for lp in live_preds:
        all_names_set.add(lp.participant_name)
    for r in registered:
        all_names_set.add(r)
        
    all_names = sorted(list(all_names_set), key=lambda x: x.lower())

    tabs = st.tabs(["👥 Participantes Ativos", "🗄️ Participantes Arquivados"])

    with tabs[0]:
        # Form to register a new participant from admin panel
        with st.expander("➕ Cadastrar Novo Participante no Bolão"):
            new_name = st.text_input("Nome do novo participante:", key="admin_register_new_part")
            if st.button("➕ Cadastrar Participante", key="btn_admin_register_new_part", width="stretch"):
                if not new_name.strip():
                    st.error("Por favor, digite um nome válido.")
                else:
                    register_participant(new_name.strip())
                    st.success(f"Participante '{new_name.strip()}' cadastrado com sucesso!")
                    st.cache_data.clear()
                    st.rerun()
    
        if all_names:
            search_term = st.text_input("🔍 Buscar por nome", placeholder="Digite parte do nome...", key="part_search")
            filtered = [name for name in all_names if search_term.lower() in name.lower()] if search_term else all_names
    
            if filtered:
                p_data = []
                for name in filtered:
                    classic_pred = next((s for s in submissions if s.participant.lower() == name.lower()), None)
                    user_key = normalize_participant_key(name)
                    lp_count = sum(1 for lp in live_preds if lp.participant_key == user_key or normalize_participant_key(lp.participant_name) == user_key)
                    p_data.append({
                        "Nome": name,
                        "Palpite Clássico": "Cadastrado" if classic_pred else "Não enviado",
                        "Palpites Jogo a Jogo": f"{lp_count} palpites",
                        "Código Clássico": classic_pred.submission_id[:8] + "..." if classic_pred else "—"
                    })
                st.dataframe(pd.DataFrame(p_data), width="stretch", hide_index=True)
    
                with st.expander("Ver/editar um participante"):
                    selected_name = st.selectbox("Selecione o participante:", options=filtered, key="part_select")
                    
                    # Load existing classic prediction
                    classic_pred = next((s for s in submissions if s.participant.lower() == selected_name.lower()), None)
                    
                    st.markdown("##### 📋 Palpite Clássico")
                    if classic_pred:
                        st.json(classic_pred.to_dict(), expanded=False)
                        
                        # Edit Classic button
                        if st.button("✏️ Editar Palpite Clássico", key=f"btn_edit_classic_{classic_pred.submission_id}", width="stretch"):
                            st.session_state["admin_editing_classic_prediction"] = classic_pred
                            init_simulator_state(classic_pred, force_reset=True, is_admin=False)
                            navigate_to("Editar Palpite Clássico")
                            
                        # Danger zone for classic prediction deletion
                        st.markdown(f'<div class="error-box" style="margin-top: 15px;"><strong>🚨 Zona de Perigo:</strong> Excluir o palpite clássico de <strong>{selected_name}</strong> é irreversível.</div>', unsafe_allow_html=True)
                        confirm_word = st.text_input(f"Digite EXCLUIR para confirmar a exclusão do palpite clássico de {selected_name}:", key=f"confirm_word_{classic_pred.submission_id}")
                        if st.button("🚨 Excluir palpite clássico", type="primary", disabled=confirm_word != "EXCLUIR", width="stretch"):
                            delete_submission(classic_pred.submission_id)
                            st.success(f"Palpite clássico de {selected_name} excluído com sucesso.")
                            st.cache_data.clear()
                            st.rerun()
                    else:
                        st.info("Este participante não possui palpite clássico cadastrado.")
                        if st.button("➕ Criar Palpite Clássico", key=f"btn_create_classic_{selected_name}", width="stretch"):
                            new_pred = Prediction(
                                participant=selected_name,
                                submission_id=stable_id(selected_name, now_iso()),
                                submitted_at=now_iso(),
                                status="rascunho"
                            )
                            st.session_state["admin_editing_classic_prediction"] = new_pred
                            init_simulator_state(new_pred, force_reset=True, is_admin=False)
                            navigate_to("Editar Palpite Clássico")
                        
                    # Edit Jogo a Jogo predictions
                    st.markdown("---")
                    st.markdown("##### 🎯 Palpites Jogo a Jogo")
                    user_key = normalize_participant_key(selected_name)
                    user_live_preds = [lp for lp in live_preds if lp.participant_key == user_key or normalize_participant_key(lp.participant_name) == user_key]
                    
                    matches = load_matches()
                    match_opts = []
                    lp_by_match_id = {lp.match_id: lp for lp in user_live_preds}
                    match_opts_map = {}
                    
                    for m in matches:
                        lp = lp_by_match_id.get(m.match_id)
                        if lp:
                            lbl = f"✅ Match {m.match_id}: {m.home_team} {int(lp.predicted_home_goals)}x{int(lp.predicted_away_goals)} {m.away_team}"
                        else:
                            lbl = f"⚪ Match {m.match_id}: {m.home_team} x {m.away_team} (Sem palpite)"
                        match_opts.append(lbl)
                        match_opts_map[lbl] = (lp, m)
                    
                    if match_opts:
                        selected_lp_lbl = st.selectbox("Escolha a partida para palpitar/editar:", options=match_opts, key=f"lp_select_{selected_name}")
                        selected_lp, selected_m = match_opts_map[selected_lp_lbl]
                        
                        val_h = int(selected_lp.predicted_home_goals) if selected_lp else 0
                        val_a = int(selected_lp.predicted_away_goals) if selected_lp else 0
                        
                        col_edit1, col_edit2 = st.columns(2)
                        with col_edit1:
                             new_h = st.number_input(f"Gols {selected_m.home_team}", min_value=0, max_value=20, value=val_h, step=1, key=f"edit_lp_h_{selected_m.match_id}_{selected_name}")
                        with col_edit2:
                             new_a = st.number_input(f"Gols {selected_m.away_team}", min_value=0, max_value=20, value=val_a, step=1, key=f"edit_lp_a_{selected_m.match_id}_{selected_name}")
                             
                        btn_label = "💾 Salvar Alterações Jogo a Jogo" if selected_lp else "➕ Criar Palpite Jogo a Jogo"
                        if st.button(btn_label, key=f"btn_edit_lp_{selected_m.match_id}_{selected_name}", type="primary", width="stretch"):
                             if selected_lp:
                                 selected_lp.predicted_home_goals = int(new_h)
                                 selected_lp.predicted_away_goals = int(new_a)
                                 selected_lp.updated_at = now_iso()
                                 
                                 if selected_m.status == "result_approved":
                                     from src.bolao.live_scoring import calculate_live_prediction_points
                                     config = load_config()
                                     res = calculate_live_prediction_points(selected_lp, selected_m, config)
                                     selected_lp.points = res["points"]
                                     selected_lp.scoring_breakdown = res["breakdown"]
                             else:
                                 from src.bolao.models import LivePrediction
                                 new_lp_id = f"{user_key}_{selected_m.match_id}"
    
                                 new_lp = LivePrediction(
                                     id=new_lp_id,
                                     participant_key=user_key,
                                     participant_name=selected_name,
                                     match_id=selected_m.match_id,
                                     predicted_home_goals=int(new_h),
                                     predicted_away_goals=int(new_a),
                                     points=0,
                                     submitted_at=now_iso(),
                                     updated_at=now_iso(),
                                     scoring_breakdown=[]
                                 )
    
                                 if selected_m.status == "result_approved":
                                     from src.bolao.live_scoring import calculate_live_prediction_points
                                     config = load_config()
                                     res = calculate_live_prediction_points(new_lp, selected_m, config)
                                     new_lp.points = res["points"]
                                     new_lp.scoring_breakdown = res["breakdown"]
    
                                 live_preds.append(new_lp)
                                 
                             save_live_predictions(live_preds)
                             
                             from src.bolao.events import append_event
                             append_event(
                                 kind="live_prediction_edited_by_admin",
                                 message=f"O administrador editou/criou o palpite jogo a jogo de {selected_name} no jogo {selected_m.home_team} x {selected_m.away_team} para {new_h}x{new_a}."
                             )
                             
                             st.success(f"Palpite jogo a jogo para {selected_m.home_team} x {selected_m.away_team} atualizado com sucesso!")
                             st.cache_data.clear()
                             st.rerun()
                    
                    # Danger Zone: delete entire participant
                    st.markdown("---")
                    st.markdown("##### 🚨 Zona de Perigo do Participante")
                    st.markdown(f'<div class="error-box"><strong>Atenção:</strong> Excluir o participante <strong>{selected_name}</strong> é definitivo. Todos os seus palpites (Clássico e Jogo a Jogo) serão eliminados e o perfil será descadastrado.</div>', unsafe_allow_html=True)
                    confirm_all_word = st.text_input(f"Digite APAGAR TUDO para confirmar a exclusão definitiva de {selected_name}:", key=f"confirm_all_word_{selected_name}")
                    if st.button("🚨 Excluir Participante Completamente", type="primary", disabled=confirm_all_word != "APAGAR TUDO", key=f"btn_delete_all_{selected_name}", width="stretch"):
                        if classic_pred:
                            delete_submission(classic_pred.submission_id)
                        remaining_live = [lp for lp in live_preds if not (lp.participant_key == user_key or normalize_participant_key(lp.participant_name) == user_key)]
                        save_live_predictions(remaining_live)
                        delete_registered_participant(selected_name)
                        st.success(f"Participante {selected_name} e todos os seus dados foram excluídos com sucesso.")
                        st.cache_data.clear()
                        st.rerun()
    
            else:
                st.info(f"Nenhum participante encontrado para \"{search_term}\".")
        else:
            render_empty_state("Nenhum participante ativo", "Não há palpites ativos cadastrados no sistema no momento.", "Ir para Resultados", "cta_participants_empty")
    
        st.markdown("---")
    
        # 1. Expander para limpeza de participantes (allowlist)
        with st.expander("🧹 Limpeza de Participantes Ativos (Allowlist)"):
            st.markdown(
                """
                <div class="callout warning" style="margin-top:0;">
                    ⚠️ <strong>Atenção:</strong> Esta ação removerá do bolão ativo todos os participantes que NÃO pertençam à allowlist de participantes oficiais:
                    <br>• <strong>Baruja</strong>
                    <br>• <strong>Henrique O Terrível</strong>
                    <br>• <strong>Fantato</strong>
                    <br><br>Todos os outros participantes e seus palpites (tanto do Modo Clássico quanto do Jogo a Jogo) serão <strong>arquivados com segurança</strong> antes de serem removidos das exibições ativas.
                </div>
                """,
                unsafe_allow_html=True
            )
            
            confirm_cleanup = st.checkbox("Estou ciente e confirmo que desejo arquivar e limpar os demais participantes", key="confirm_cleanup_checkbox")
            confirm_text = st.text_input("Digite LIMPAR para confirmar a ação:", key="confirm_cleanup_text")
            
            btn_cleanup = st.button("🧹 Executar arquivamento e limpeza", type="primary", disabled=not confirm_cleanup or confirm_text != "LIMPAR", key="btn_run_participants_cleanup", width="stretch")
            
            if btn_cleanup:
                with st.spinner("Executando limpeza e gerando backups..."):
                    from src.bolao.migrations import cleanup_active_participants
                    res = cleanup_active_participants({"baruja", "henrique-o-terrivel", "fantato"})
                    if res["status"] == "success":
                        st.success(
                            f"Faxina executada com sucesso! "
                            f"Removidos: {len(res['removed_participants'])} participante(s). "
                            f"Backup salvo em: {res['backup_path']}"
                        )
                        st.rerun()
                    else:
                        st.error("Erro desconhecido ao executar a migração de limpeza.")
    
    # 2. Seção de Participantes Arquivados
    with tabs[1]:
        st.markdown("#### 🗄️ Participantes Arquivados (Histórico)")
        st.caption("Abaixo estão listados os participantes antigos cujos dados foram preservados. Você pode restaurá-los a qualquer momento.")
        
        archived_list = load_archived_participants()
        if not archived_list:
            st.info("Nenhum participante arquivado no momento nos registros históricos.")
        else:
            archived_rows = []
            for p in archived_list:
                archived_rows.append({
                    "Participante": p.get("name"),
                    "Arquivado em": p.get("archived_at", "—").replace("T", " ")[:19],
                    "Motivo": p.get("reason", "—"),
                    "Palpite Clássico": "Sim" if p.get("had_classic_prediction") else "Não",
                    "Palpites Jogo a Jogo": f"{p.get('live_predictions_count', 0)} palpites",
                    "Chave": p.get("participant_key")
                })
                
            st.dataframe(pd.DataFrame(archived_rows), width="stretch", hide_index=True)
            
            st.markdown("##### ⏪ Restaurar Participante")
            selected_pkey = st.selectbox(
                "Selecione o participante a restaurar:",
                options=[p["Chave"] for p in archived_rows],
                format_func=lambda k: next(r["Participante"] for r in archived_rows if r["Chave"] == k),
                key="restore_archived_select"
            )
            
            confirm_restore = st.checkbox("Confirmo que desejo restaurar este participante e torná-lo ativo novamente", key="confirm_restore_chk")
            if st.button("⏪ Restaurar Participante Selecionado", type="primary", disabled=not confirm_restore, key="btn_restore_archived", width="stretch"):
                if restore_participant(selected_pkey):
                    st.success("Participante restaurado com sucesso no bolão ativo!")
                    st.cache_data.clear()
                    st.rerun()
                else:
                    st.error("Erro ao tentar restaurar o participante.")



def make_prediction_from_text(name: str, text: str) -> Prediction:
    knockout, champion, issues, meta = parse_ge_knockout_text(text)
    pred = Prediction(participant=name, knockout=knockout, champion=champion, submission_id=stable_id(name, now_iso()), submitted_at=now_iso())
    pred.meta = {"knockout_parser": meta, "issues": [i.__dict__ for i in issues]}
    return pred


def admin_official_results() -> None:
    if st.button("⬅️ Voltar ao Painel Admin", key="back_to_dashboard_results", width="stretch"):
        navigate_to("Dashboard")
    render_page_header("Admin", "Resultados Oficiais", "Preencha os resultados conforme a competição avança — salve o progresso a qualquer momento.", "⚽")
    st.caption("Fluxo recomendado: preencher jogos realizados → Salvar Progresso → voltar depois e continuar de onde parou → Aprovar quando completo.")

    tabs = st.tabs(["Simulador Oficial", "Texto/manual", "API", "Resultado salvo"])

    with tabs[0]:
        st.markdown("### Preencher via Simulador")
        st.caption("Preencha os placares dos jogos já realizados e os vencedores do mata-mata. O simulador carrega os dados previamente salvos.")

        if "official_save_msg" in st.session_state:
            st.success(st.session_state.pop("official_save_msg"))

        ctx = load_app_data_cached()
        official_draft = ctx.official or Prediction(participant="Resultado oficial")
        updated_official = render_simulator(official_draft, is_admin=True)

        if updated_official:
            st.markdown("---")
            st.markdown("#### Salvar ou Aprovar")

            is_complete, missing = validate_prediction_complete(updated_official)
            if not is_complete:
                st.markdown(f'<div class="warn-box">📋 <strong>Pendências ({len(missing)}):</strong><br>' + "<br>".join(f"• {m}" for m in missing) + "</div>", unsafe_allow_html=True)

            col_save, col_approve = st.columns(2)

            # Save draft / progress
            with col_save:
                if st.button("💾 Salvar Progresso (rascunho)", type="secondary", key="btn_save_official_draft", width="stretch"):
                    updated_official.status = "rascunho"
                    updated_official.submitted_at = now_iso()
                    save_official(updated_official)
                    st.session_state["official_save_msg"] = "✅ Progresso salvo! Os dados já estão salvos — volte depois para continuar de onde parou."
                    st.session_state.pop("sim_public", None)
                    st.rerun()

            # Approve (full save with confirmation)
            with col_approve:
                st.markdown('<div class="warn-box" style="font-size:13px;"><strong>⚠️ Aprovar</strong> substitui o ranking anterior e vale como resultado oficial definitivo.</div>', unsafe_allow_html=True)
                confirm_approve = st.text_input("Digite APROVAR para aprovação definitiva:", key="confirm_sim_word", placeholder="APROVAR")
                if st.button("✅ Aprovar Resultado Oficial", type="primary", key="btn_save_official_sim", disabled=confirm_approve != "APROVAR", width="stretch"):
                    if missing:
                        st.warning("⚠️ Resultado incompleto. Itens pendentes:")
                        for m in missing:
                            st.markdown(f"- {m}")
                        st.info("💡 Se a competição ainda está rolando, use 'Salvar Progresso' para salvar dados parciais sem aprovar.")
                        return
                    updated_official.status = "aprovado"
                    updated_official.submitted_at = now_iso()
                    save_official(updated_official)
                    st.session_state["official_save_msg"] = "🏆 Resultado oficial aprovado! Ranking recalculado automaticamente."
                    st.session_state.pop("sim_public", None)
                    st.rerun()

    with tabs[1]:
        name = "Resultado oficial"
        official_text = st.text_area("Cole o texto oficial do mata-mata ou do simulador final", height=220, key="official_text")
        if st.button("Interpretar texto oficial", width="stretch", disabled=not official_text.strip()):
            st.session_state["official_draft"] = make_prediction_from_text(name, official_text)
            st.rerun()

        draft = st.session_state.get("official_draft") or ctx.official or Prediction(participant="Resultado oficial")
        st.markdown("### Revisar resultado oficial")
        draft = apply_review_form("official_review", deepcopy(draft))
        st.markdown('<div class="warn-box"><strong>⚠️ Atenção:</strong> Aprovar o resultado oficial recalculará o ranking de todos os participantes. Esta ação substitui qualquer resultado anterior.</div>', unsafe_allow_html=True)
        confirm_word_text = st.text_input("Digite APROVAR para confirmar a aprovação:", key="confirm_text_word")
        if st.button("Aprovar e salvar resultado oficial", type="primary", disabled=confirm_word_text != "APROVAR", width="stretch"):
            draft.status = "aprovado"
            save_official(draft)
            st.success("Resultado oficial aprovado e salvo.")
            st.rerun()

    with tabs[2]:
        from src.bolao.api_service import APIFootballService
        service = APIFootballService()
        if not service.enabled():
            st.warning("APIFOOTBALL_KEY não configurada. Configure em variável de ambiente ou nos secrets do Streamlit Cloud.")
        if st.button("Sincronizar API-FOOTBALL", width="stretch"):
            with st.spinner("Consultando API..."):
                response = service.fetch_world_cup_2026()
            if response.ok:
                st.success(response.message)
                st.session_state["official_draft"] = response.prediction
            else:
                st.error(response.message)
            if response.raw:
                st.json(response.raw, expanded=False)

    with tabs[3]:
        official = ctx.official
        if not official:
            st.info("Nenhum resultado oficial salvo.")
        else:
            status_tag = "🏆 Aprovado" if official.status == "aprovado" else "📝 Rascunho"
            st.markdown(f'**Status:** <span class="badge {"success" if official.status == "aprovado" else "warning"}">{status_tag}</span>', unsafe_allow_html=True)
            st.markdown(f"**Última atualização:** `{official.submitted_at or '—'}`")
            if official.meta.get("group_matches"):
                total = len(official.meta["group_matches"])
                filled = sum(1 for v in official.meta["group_matches"].values() if v[0] is not None and v[1] is not None)
                st.markdown(f"**Jogos preenchidos:** {filled}/{total}")
            if official.meta.get("slots"):
                ko_filled = sum(1 for v in official.meta["slots"].values() if v is not None)
                st.markdown(f"**Chave do mata-mata preenchida:** {ko_filled}/63")
            with st.expander("Ver JSON completo", expanded=False):
                st.json(official.to_dict(), expanded=False)


def admin_ranking() -> None:
    if st.button("⬅️ Voltar ao Painel Admin", key="back_to_dashboard_ranking", width="stretch"):
        navigate_to("Dashboard")
    from src.bolao.ui_ranking import render_rankings_tabs
    render_rankings_tabs(is_admin=True)


def admin_exports() -> None:
    if st.button("⬅️ Voltar ao Painel Admin", key="back_to_dashboard_exports", width="stretch"):
        navigate_to("Dashboard")
    render_page_header("Admin", "Exportações", "Baixe dados do bolão em vários formatos.", "📦")
    
    from src.bolao.storage import load_app_data_cached, export_all_state
    from src.bolao.live_scoring import calculate_live_ranking
    from src.bolao.utils import normalize_participant_key
    from src.bolao.social import build_ranking_share_text, build_live_daily_share_text
    from src.bolao.exporters import live_podium_html
    from src.bolao.ui_live_matches import is_match_open_for_prediction

    ctx = load_app_data_cached()
    submissions = ctx.submissions
    official = ctx.official
    
    scores = rank_predictions(submissions, official, get_score_config()) if official else []
    live_scores = calculate_live_ranking(ctx.live_predictions, ctx.matches, ctx.config)

    # Combined ranking calculation
    classic_weights = ctx.config.get("combined_ranking_weights", {}).get("classic", 1.0)
    live_weights = ctx.config.get("combined_ranking_weights", {}).get("live", 1.0)
    
    classic_dict = {normalize_participant_key(s.participant): s for s in scores}
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
            "classic_points": c_pts,
            "live_points": l_pts,
            "total": combined_pts
        })
    combined_list.sort(key=lambda s: (-s["total"], -s["classic_points"], -s["live_points"], s["participant"].lower()))

    # Build DataFrames
    live_df = pd.DataFrame([{
        "Posição": s["position"],
        "Participante": s["participant"],
        "Pontos": s["total"],
        "Placares Exatos": s["exact_scores"],
        "Acertos Vencedor": s["outcomes"],
        "Palpites Salvos": s["predictions_count"],
        "Palpites Perdidos": s["missed_predictions"],
        "Aproveitamento": f"{int(s['hit_rate'] * 100)}%"
    } for s in live_scores]) if live_scores else pd.DataFrame()

    comb_df = pd.DataFrame([{
        "Posição": idx,
        "Participante": s["participant"],
        "Pontos Clássico": s["classic_points"],
        "Pontos Jogo a Jogo": s["live_points"],
        "Pontos Combinados": s["total"]
    } for idx, s in enumerate(combined_list, start=1)]) if combined_list else pd.DataFrame()

    exp_tabs = st.tabs(["📥 Planilhas e Dados", "🏆 Pódios HTML", "💬 WhatsApp / Social"])

    with exp_tabs[0]:
        with st.container(border=True):
            st.markdown("### 📊 Exportar Planilhas (CSV)")
            st.caption("Arquivos formatados para abertura no Excel ou Google Sheets.")
            st.markdown("<br>", unsafe_allow_html=True)
            c_cols = st.columns(3)
            with c_cols[0]:
                st.download_button(
                    "Baixar Ranking Clássico (CSV)",
                    data=ranking_csv(scores),
                    file_name="ranking_classico.csv",
                    mime="text/csv",
                    disabled=not bool(scores),
                    width="stretch"
                )
            with c_cols[1]:
                st.download_button(
                    "Baixar Ranking Jogo a Jogo (CSV)",
                    data=live_df.to_csv(index=False) if not live_df.empty else "",
                    file_name="ranking_jogo_a_jogo.csv",
                    mime="text/csv",
                    disabled=live_df.empty,
                    width="stretch"
                )
            with c_cols[2]:
                st.download_button(
                    "Baixar Ranking Geral Combinado (CSV)",
                    data=comb_df.to_csv(index=False) if not comb_df.empty else "",
                    file_name="ranking_geral_combinado.csv",
                    mime="text/csv",
                    disabled=comb_df.empty,
                    width="stretch"
                )

        st.markdown("<br>", unsafe_allow_html=True)

        with st.container(border=True):
            st.markdown("### 💾 Backups de Segurança (JSON)")
            st.caption("Arquivos de dados estruturados contendo todo o estado atual para restauração ou migração.")
            st.markdown("<br>", unsafe_allow_html=True)
            j_cols = st.columns(3)
            with j_cols[0]:
                st.download_button(
                    "Baixar Backup Geral Completo (JSON)",
                    data=json.dumps(export_all_state(), ensure_ascii=False, indent=2),
                    file_name="backup_geral_completo.json",
                    mime="application/json",
                    width="stretch"
                )
            with j_cols[1]:
                st.download_button(
                    "Baixar Palpites Jogo a Jogo (JSON)",
                    data=json.dumps([p.to_dict() for p in ctx.live_predictions], ensure_ascii=False, indent=2),
                    file_name="live_predictions.json",
                    mime="application/json",
                    width="stretch"
                )
            with j_cols[2]:
                st.download_button(
                    "Baixar Agenda de Jogos (JSON)",
                    data=json.dumps([m.to_dict() for m in ctx.matches], ensure_ascii=False, indent=2),
                    file_name="matches_agenda.json",
                    mime="application/json",
                    width="stretch"
                )

        st.markdown("<br>", unsafe_allow_html=True)

        with st.container(border=True):
            st.markdown("### 📥 Restaurar Backup Geral (JSON)")
            st.caption("Faça upload de um arquivo de backup geral completo para restaurar todas as configurações, palpites e perfis cadastrados.")
            uploaded_backup = st.file_uploader("Selecione o arquivo de backup (.json)", type=["json"], key="uploader_backup_geral")
            if uploaded_backup is not None:
                st.warning("⚠️ Atenção: A restauração irá substituir todos os dados atuais (configurações, palpites clássicos, palpites jogo a jogo, perfis cadastrados) pelos dados contidos no backup.")
                word_confirm = st.text_input("Digite RESTAURAR para confirmar a ação:", key="word_restore_confirm")
                if st.button("Executar Restauração de Dados", type="primary", key="btn_run_restore_backup", disabled=word_confirm != "RESTAURAR", width="stretch"):
                    try:
                        backup_data = json.load(uploaded_backup)
                        from src.bolao.storage import import_all_state
                        import_all_state(backup_data)
                        st.success("Backup restaurado com sucesso! Recarregando aplicação...")
                        import time
                        time.sleep(1.0)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao restaurar backup: {e}")


    with exp_tabs[1]:
        with st.container(border=True):
            st.markdown("### 🏆 Compartilhar Cartazes de Pódio (HTML)")
            st.caption("Baixe arquivos HTML com visual moderno e premium para impressão ou print de redes sociais.")
            st.markdown("<br>", unsafe_allow_html=True)
            p_cols = st.columns(2)
            with p_cols[0]:
                status_lbl = ctx.config.get("status_label", "Aprovado")
                html_classic = podium_html(scores, status_label=status_lbl) if scores else ""
                st.download_button(
                    "Baixar Pódio Clássico (HTML)",
                    data=html_classic,
                    file_name="podio_classico.html",
                    mime="text/html",
                    disabled=not bool(scores),
                    width="stretch"
                )
            with p_cols[1]:
                html_live = live_podium_html(live_scores, status_label=status_lbl) if live_scores else ""
                st.download_button(
                    "Baixar Pódio Jogo a Jogo (HTML)",
                    data=html_live,
                    file_name="podio_jogo_a_jogo.html",
                    mime="text/html",
                    disabled=not bool(live_scores),
                    width="stretch"
                )

    with exp_tabs[2]:
        with st.container(border=True):
            st.markdown("### 💬 Textos Prontos para WhatsApp")
            st.caption("Copie e envie nos grupos sociais para atualizar a galera do bolão.")
            st.markdown("<br>", unsafe_allow_html=True)
            
            st.markdown("#### 🏆 Classificação de Rankings")
            ranking_text = build_ranking_share_text(scores, live_scores)
            st.text_area("Texto Classificação", value=ranking_text, height=150, key="txt_area_rank_whatsapp")
            
            st.markdown("<br>", unsafe_allow_html=True)
            
            st.markdown("#### 📅 Próximos Jogos de Hoje")
            import datetime
            now_str = datetime.datetime.now().isoformat()
            today_open_matches = [m for m in ctx.matches if m.status != "result_approved" and is_match_open_for_prediction(m, now_str)]
            today_open_matches.sort(key=lambda m: m.starts_at)
            daily_text = build_live_daily_share_text(today_open_matches)
            st.text_area("Texto Jogos do Dia", value=daily_text, height=150, key="txt_area_daily_whatsapp")


def admin_settings() -> None:
    if st.button("⬅️ Voltar ao Painel Admin", key="back_to_dashboard_settings", width="stretch"):
        navigate_to("Dashboard")
    render_page_header("Admin", "Configurações", "Controle geral do bolão: status, pontuação e prazos.", "⚙️")
    config = load_app_data_cached().config
    
    # Accordion 1: Status & Acesso
    with st.expander("🔐 Status & Acesso", expanded=True):
        config["is_bolao_locked"] = st.checkbox(
            "🔒 Bloquear envios e alterações de palpites clássicos",
            value=config.get("is_bolao_locked", False),
            help="Se marcado, novos palpites clássicos não poderão ser enviados, e palpites existentes não poderão ser editados ou excluídos."
        )
        config["status_label"] = st.text_input("Status público do bolão", value=config.get("status_label", "Recebendo palpites"))
        config["submission_deadline"] = st.text_input(
            "Prazo Limite para Envios Clássicos (Opcional)",
            value=config.get("submission_deadline", ""),
            help="Exemplo: 11/06/2026 15:00 ou deixe em branco se não houver prazo rígido."
        )
        
        mode_options = ["v2", "ponderado", "uniforme"]
        current_mode = config.get("scoring_mode", "v2")
        if current_mode not in mode_options:
            current_mode = "v2"
        mode_idx = mode_options.index(current_mode)
        config["scoring_mode"] = st.radio("Modo de pontuação do Clássico", mode_options, index=mode_idx, horizontal=True)

    # Accordion 2: Configurações do Jogo a Jogo
    with st.expander("🎯 Configurações do Jogo a Jogo", expanded=False):
        config["classic_enabled"] = st.checkbox("Modo Clássico Ativado", value=config.get("classic_enabled", True))
        config["live_mode_enabled"] = st.checkbox("Modo Jogo a Jogo Ativado", value=config.get("live_mode_enabled", True))
        config["combined_ranking_enabled"] = st.checkbox("Ranking Geral Combinado Ativado", value=config.get("combined_ranking_enabled", False))
        config["live_lock_minutes_before_match"] = st.number_input(
            "Bloquear palpites jogo a jogo X minutos antes do início do jogo",
            min_value=0, max_value=1440,
            value=int(config.get("live_lock_minutes_before_match", 10)),
            step=1
        )
        
        st.markdown("#### Pontuação Modo Jogo a Jogo")
        live_scoring = config.get("live_scoring", {})
        col_l1, col_l2, col_l3 = st.columns(3)
        with col_l1:
            exact_score_val = st.number_input("Placar Exato", min_value=0, max_value=50, value=int(live_scoring.get("exact_score", 5)), step=1)
            outcome_val = st.number_input("Acertar Vencedor/Empate", min_value=0, max_value=50, value=int(live_scoring.get("outcome", 3)), step=1)
        with col_l2:
            goal_one_team_val = st.number_input("Acertar Gols de um Time", min_value=0, max_value=50, value=int(live_scoring.get("goal_one_team", 1)), step=1)
            goal_difference_val = st.number_input("Acertar Saldo de Gols", min_value=0, max_value=50, value=int(live_scoring.get("goal_difference", 1)), step=1)
        with col_l3:
            exact_score_mode = st.radio(
                "Modo do Placar Exato",
                options=["isolated_max", "additive"],
                index=0 if config.get("exact_score_mode", "isolated_max") == "isolated_max" else 1,
                help="isolated_max: ganha apenas os pontos do placar exato se acertar tudo. additive: ganha os pontos de placar exato + todos os outros bônus que coincidam."
            )
        
        config["live_scoring"] = {
            "exact_score": exact_score_val,
            "outcome": outcome_val,
            "goal_one_team": goal_one_team_val,
            "goal_difference": goal_difference_val,
            "late_prediction": 0
        }
        config["exact_score_mode"] = exact_score_mode

        st.markdown("#### Pesos do Ranking Geral Combinado")
        weights = config.get("combined_ranking_weights", {"classic": 1.0, "live": 1.0})
        col_w1, col_w2 = st.columns(2)
        with col_w1:
            classic_w = st.number_input("Peso do Modo Clássico", min_value=0.0, max_value=10.0, value=float(weights.get("classic", 1.0)), step=0.1)
        with col_w2:
            live_w = st.number_input("Peso do Modo Jogo a Jogo", min_value=0.0, max_value=10.0, value=float(weights.get("live", 1.0)), step=0.1)
        config["combined_ranking_weights"] = {"classic": classic_w, "live": live_w}

        st.markdown("#### Privacidade & Feed")
        config["reveal_live_predictions_after_lock"] = st.checkbox("Revelar palpites dos outros após o lock do jogo", value=config.get("reveal_live_predictions_after_lock", True))
        config["allow_live_prediction_edit_until_lock"] = st.checkbox("Permitir editar palpite jogo a jogo até o lock", value=config.get("allow_live_prediction_edit_until_lock", True))
        config["public_show_activity_feed"] = st.checkbox("Exibir feed de atividades público", value=config.get("public_show_activity_feed", True))

    # Accordion 3: Pontuação V2 (Fase de Grupos & Mata-mata) [Modo Clássico]
    with st.expander("🏆 Pontuação Modo Clássico (V2)", expanded=False):
        v2_rules = config.get("v2_rules", dict(DEFAULT_V2_RULES))
        col1, col2, col3 = st.columns(3)
        with col1:
            v2_rules["group_exact"] = st.number_input(
                "Grupo: Placar Exato",
                min_value=0,
                max_value=50,
                value=int(v2_rules.get("group_exact", DEFAULT_V2_RULES["group_exact"])),
                step=1,
                help="Pontos para previsão exata de placar de grupo (ex. palpite 2x1, oficial 2x1)."
            )
            v2_rules["group_result_gd"] = st.number_input(
                "Grupo: Resultado + Saldo",
                min_value=0,
                max_value=50,
                value=int(v2_rules.get("group_result_gd", DEFAULT_V2_RULES["group_result_gd"])),
                step=1,
                help="Pontos para acertar vencedor/empate e saldo de gols, mas não o placar exato (ex. palpite 2x0, oficial 3x1)."
            )
            v2_rules["group_result"] = st.number_input(
                "Grupo: Apenas Resultado",
                min_value=0,
                max_value=50,
                value=int(v2_rules.get("group_result", DEFAULT_V2_RULES["group_result"])),
                step=1,
                help="Pontos para acertar apenas o vencedor ou empate (ex. palpite 1x0, oficial 3x0)."
            )
        with col2:
            v2_rules["group_team_goals"] = st.number_input(
                "Grupo: Gols de um Time",
                min_value=0,
                max_value=50,
                value=int(v2_rules.get("group_team_goals", DEFAULT_V2_RULES["group_team_goals"])),
                step=1,
                help="Pontos para acertar a quantidade de gols de pelo menos uma das equipes (ex. palpite 1x2, oficial 1x0)."
            )
            v2_rules["ko_oitavas"] = st.number_input(
                "Mata-mata: Classificar Oitavas",
                min_value=0,
                max_value=50,
                value=int(v2_rules.get("ko_oitavas", DEFAULT_V2_RULES["ko_oitavas"])),
                step=1,
                help="Pontos por time classificado para as Oitavas de final."
            )
            v2_rules["ko_quartas"] = st.number_input(
                "Mata-mata: Classificar Quartas",
                min_value=0,
                max_value=50,
                value=int(v2_rules.get("ko_quartas", DEFAULT_V2_RULES["ko_quartas"])),
                step=1,
                help="Pontos por time classificado para as Quartas de final."
            )
        with col3:
            v2_rules["ko_semifinais"] = st.number_input(
                "Mata-mata: Classificar Semi",
                min_value=0,
                max_value=50,
                value=int(v2_rules.get("ko_semifinais", DEFAULT_V2_RULES["ko_semifinais"])),
                step=1,
                help="Pontos por time classificado para as Semifinais."
            )
            v2_rules["ko_final"] = st.number_input(
                "Mata-mata: Classificar Final",
                min_value=0,
                max_value=50,
                value=int(v2_rules.get("ko_final", DEFAULT_V2_RULES["ko_final"])),
                step=1,
                help="Pontos por time classificado para a Final."
            )
            v2_rules["ko_champion"] = st.number_input(
                "Mata-mata: Campeão",
                min_value=0,
                max_value=50,
                value=int(v2_rules.get("ko_champion", DEFAULT_V2_RULES["ko_champion"])),
                step=1,
                help="Pontos por acertar o Campeão."
            )

        st.markdown("#### Regras Criativas (Bônus Cumulativos) [Modo Clássico]")
        col_cr1, col_cr2, col_cr3 = st.columns(3)
        with col_cr1:
            v2_rules["group_sum_goals"] = st.number_input(
                "Grupo: Soma Total de Gols",
                min_value=0,
                max_value=20,
                value=int(v2_rules.get("group_sum_goals", 0)),
                step=1,
                help="Bônus por prever a soma total exata de gols na partida (ex. palpite 2x2 e oficial 3x1; ambos somam 4)."
            )
        with col_cr2:
            v2_rules["group_both_scored"] = st.number_input(
                "Grupo: Ambas Equipes Marcam",
                min_value=0,
                max_value=20,
                value=int(v2_rules.get("group_both_scored", 0)),
                step=1,
                help="Bônus por acertar se ambas as equipes marcaram gol (ambas > 0) ou não."
            )
        with col_cr3:
            v2_rules["group_over_2_5"] = st.number_input(
                "Grupo: Mais de 2.5 Gols",
                min_value=0,
                max_value=20,
                value=int(v2_rules.get("group_over_2_5", 0)),
                step=1,
                help="Bônus por acertar se a partida teve mais de 2.5 gols (soma > 2) ou não."
            )
            
        config["v2_rules"] = v2_rules

    # Accordion 4: Pontuações Legadas (Ponderado e Uniforme)
    with st.expander("⏳ Pontuações Legadas (Ponderado e Uniforme)", expanded=False):
        st.markdown("#### Pontuação ponderada (Legado) [Modo Clássico]")
        weighted = config.get("weighted_rules", dict(DEFAULT_WEIGHTED_RULES))
        cols = st.columns(3)
        for idx, key in enumerate(DEFAULT_WEIGHTED_RULES.keys()):
            with cols[idx % 3]:
                weighted[key] = st.number_input(key, min_value=0, max_value=50, value=int(weighted.get(key, DEFAULT_WEIGHTED_RULES[key])), step=1)
        config["weighted_rules"] = weighted

        st.markdown("---")
        st.markdown("#### Pontuação uniforme (Legado) [Modo Clássico]")
        uniform = config.get("uniform_rules", dict(DEFAULT_UNIFORM_RULES))
        uniform["decision_points"] = st.number_input("Pontos por decisão", min_value=1, max_value=50, value=int(uniform.get("decision_points", 1)), step=1)
        uniform["champion_bonus"] = st.number_input("Bônus da campeã", min_value=0, max_value=100, value=int(uniform.get("champion_bonus", 0)), step=1)
        config["uniform_rules"] = uniform

    # Accordion: Módulo Brasil & Modo Relâmpago (F05-F08, F19, F20)
    with st.expander("🇧🇷 Configurações do Módulo Brasil & Modo Relâmpago", expanded=False):
        st.markdown("#### Pontuação do Módulo Brasil (Copa 2026)")
        config["copa_encerrada"] = st.checkbox("🏆 Marcar Copa como Encerrada (Exibe Pódio e Confetes na Home)", value=config.get("copa_encerrada", False))
        
        col_b1, col_b2, col_b3 = st.columns(3)
        with col_b1:
            pts_acertar_goleador = st.number_input("Pts por goleador acertado", min_value=0, max_value=50, value=int(config.get("pts_acertar_goleador", 4)), step=1)
            pts_acertar_assistente = st.number_input("Pts por assistente acertado", min_value=0, max_value=50, value=int(config.get("pts_acertar_assistente", 2)), step=1)
            pts_goleador_mais_assist = st.number_input("Pts goleador + assist mesmo gol", min_value=0, max_value=50, value=int(config.get("pts_goleador_mais_assist", 8)), step=1)
        with col_b2:
            pts_todos_goleadores = st.number_input("Pts acertar todos os goleadores", min_value=0, max_value=50, value=int(config.get("pts_todos_goleadores", 5)), step=1)
            pts_artilheiro_brasil = st.number_input("Pts artilheiro Brasil (clássico)", min_value=0, max_value=50, value=int(config.get("pts_artilheiro_brasil", 15)), step=1)
            pts_top3_artilheiros_brasil = st.number_input("Pts top 3 artilheiros Brasil", min_value=0, max_value=50, value=int(config.get("pts_top3_artilheiros_brasil", 5)), step=1)
        with col_b3:
            pts_artilheiro_geral = st.number_input("Pts artilheiro geral (clássico)", min_value=0, max_value=50, value=int(config.get("pts_artilheiro_geral", 20)), step=1)
            pts_top3_artilheiros_geral = st.number_input("Pts top 3 artilheiros gerais", min_value=0, max_value=50, value=int(config.get("pts_top3_artilheiros_geral", 7)), step=1)
            pts_gol_de_ouro = st.number_input("Pts Gol de Ouro (1º gol Brasil)", min_value=0, max_value=50, value=int(config.get("pts_gol_de_ouro", 10)), step=1)
            
        config["pts_acertar_goleador"] = pts_acertar_goleador
        config["pts_acertar_assistente"] = pts_acertar_assistente
        config["pts_goleador_mais_assist"] = pts_goleador_mais_assist
        config["pts_todos_goleadores"] = pts_todos_goleadores
        config["pts_artilheiro_brasil"] = pts_artilheiro_brasil
        config["pts_top3_artilheiros_brasil"] = pts_top3_artilheiros_brasil
        config["pts_artilheiro_geral"] = pts_artilheiro_geral
        config["pts_top3_artilheiros_geral"] = pts_top3_artilheiros_geral
        config["pts_gol_de_ouro"] = pts_gol_de_ouro

        st.markdown("#### Pontuação do Modo Relâmpago (2º Tempo)")
        live_scoring = config.get("live_scoring", {})
        col_r1, col_r2 = st.columns(2)
        with col_r1:
            pts_relampago_exato = st.number_input("Pts Modo Relâmpago Placar Exato", min_value=0, max_value=50, value=int(live_scoring.get("pts_relampago_exato", 4)), step=1)
        with col_r2:
            pts_relampago_resultado = st.number_input("Pts Modo Relâmpago Apenas Resultado", min_value=0, max_value=50, value=int(live_scoring.get("pts_relampago_resultado", 2)), step=1)
            
        live_scoring["pts_relampago_exato"] = pts_relampago_exato
        live_scoring["pts_relampago_resultado"] = pts_relampago_resultado
        config["live_scoring"] = live_scoring

    # Botão de salvar fora dos expanders
    if st.button("💾 Salvar todas as configurações", type="primary", key="btn_save_settings", width="stretch"):
        save_config(config)
        st.success("Configurações salvas com sucesso.")

    st.markdown("---")
    st.markdown("### ⚠️ Zona de Perigo")
    st.caption("Ações irreversíveis que alteram ou excluem dados do sistema.")
    
    with st.expander("Expandir Zona de Perigo", expanded=False):
        st.markdown("#### 1. Restaurar dados de demonstração (Modo Clássico)")
        check_demo = st.checkbox("Desejo carregar os dados de demonstração", key="check_demo")
        word_demo = st.text_input("Digite CONFIRMAR para habilitar a ação de demonstração:", key="word_demo")
        if st.button("Restaurar dados demo", type="secondary", key="btn_reset_demo_state", disabled=not (check_demo and word_demo == "CONFIRMAR"), width="stretch"):
            from src.bolao.storage import load_demo_state
            load_demo_state()
            st.success("Dados de demonstração carregados com sucesso!")
            st.rerun()

        st.markdown("#### 2. Excluir palpites do Modo Jogo a Jogo")
        check_live = st.checkbox("Estou ciente que todos os palpites jogo a jogo salvos serão deletados permanentemente.", key="check_live")
        word_live = st.text_input("Digite LIMPAR JOGO A JOGO para confirmar:", key="word_live")
        if st.button("Excluir palpites Jogo a Jogo", type="secondary", key="btn_clear_live_guesses", disabled=not (check_live and word_live == "LIMPAR JOGO A JOGO"), width="stretch"):
            from src.bolao.storage import save_live_predictions
            save_live_predictions([])
            from src.bolao.events import append_event
            append_event("live_predictions_cleared", "Todos os palpites do modo jogo a jogo foram excluídos pelo administrador.")
            st.success("Todos os palpites jogo a jogo foram excluídos.")
            st.rerun()

        st.markdown("#### 3. Limpar Feed de Atividades")
        check_events = st.checkbox("Estou ciente de que todo o histórico de eventos será apagado permanentemente.", key="check_events")
        word_events = st.text_input("Digite LIMPAR EVENTOS para confirmar:", key="word_events")
        if st.button("Excluir Feed de Atividades", type="secondary", key="btn_clear_events_feed", disabled=not (check_events and word_events == "LIMPAR EVENTOS"), width="stretch"):
            from src.bolao.utils import write_json
            from src.bolao.storage import EVENTS_PATH
            write_json(EVENTS_PATH, [])
            st.success("Feed de atividades limpo.")
            st.rerun()

        st.markdown("#### 4. Reset Geral do Estado")
        check_reset = st.checkbox("Estou ciente de que todos os palpites clássicos, jogo a jogo, eventos e resultados serão excluídos permanentemente.", key="check_reset")
        word_reset = st.text_input("Digite RESET TOTAL para confirmar:", key="word_reset")
        if st.button("Executar Reset Total", type="primary", key="btn_full_reset_state", disabled=not (check_reset and word_reset == "RESET TOTAL"), width="stretch"):
            from src.bolao.storage import reset_state, save_matches
            reset_state()
            from src.bolao.storage import load_matches
            load_matches()
            st.success("Geral limpo e re-inicializado com sucesso!")
            st.rerun()


def admin_edit_classic_page() -> None:
    from src.bolao.ui_simulator import render_simulator, validate_prediction_complete
    
    if st.button("⬅️ Voltar para Participantes", key="btn_back_from_edit_classic", width="stretch"):
        navigate_to("Participantes")

    pred = st.session_state.get("admin_editing_classic_prediction")
    if not pred:
        st.warning("Nenhum palpite selecionado para edição.")
        return

    st.markdown(f"### ✏️ Editando Palpite Clássico de **{pred.participant}**")
    st.caption("Altere os placares da fase de grupos e o chaveamento do mata-mata no simulador abaixo.")

    updated_pred = render_simulator(pred)
    if updated_pred:
        st.markdown("---")
        st.markdown("#### Salvar Alterações")
        if st.button("💾 Salvar Alterações do Participante", type="primary", width="stretch"):
            # Final validation check
            is_complete, missing = validate_prediction_complete(updated_pred)
            if not is_complete:
                st.error("⚠️ Palpite incompleto. Verifique os itens abaixo:")
                for item in missing:
                    st.markdown(f"- {item}")
                return
            
            # Save the updated prediction
            from src.bolao.storage import save_submission
            from src.bolao.events import append_event
            
            updated_pred.submitted_at = now_iso()
            save_submission(updated_pred)
            
            append_event(
                kind="submission_edited_by_admin",
                message=f"O administrador editou o palpite clássico do participante {pred.participant}."
            )
            
            st.success(f"Alterações no palpite de {pred.participant} salvas com sucesso!")
            st.session_state.pop("admin_editing_classic_prediction", None)
            st.cache_data.clear()
            navigate_to("Participantes")


def admin_help() -> None:
    if st.button("⬅️ Voltar ao Painel Admin", key="back_to_dashboard_help", width="stretch"):
        navigate_to("Dashboard")
    render_page_header("Admin", "Ajuda Rápida", "Fluxos e instruções do sistema.", "📖")
    st.markdown(
        """
**Fluxo do participante**

1. Acessa o sistema e informa seu nome.
2. Preenche os placares da fase de grupos diretamente no simulador interativo.
3. Confere a classificação em tempo real e a definição dos classificados.
4. Clica nas seleções no chaveamento do mata-mata para avançá-las até o campeão.
5. Revisa e envia o palpite de forma totalmente digital, sem prints, arquivos ou OCR.

**Fluxo do admin**

1. Recebe e gerencia os palpites dos participantes.
2. Define o resultado oficial na Central de Resultados Oficial através do mesmo simulador ou importando via API.
3. Acompanha o cálculo automático do ranking público (Modo V2 como padrão).
4. Exporta backups ou texto formatado para o Discord.
        """
    )


def admin_auditoria() -> None:
    if st.button("⬅️ Voltar ao Painel Admin", key="back_to_dashboard_auditoria", width="stretch"):
        navigate_to("Dashboard")
    render_page_header("Admin", "Auditoria e Moderação", "Histórico de eventos e moderação de comentários.", "🛡️")
    
    tab_eventos, tab_comentarios = st.tabs(["📋 Eventos de Auditoria", "💬 Moderação de Comentários"])
    
    with tab_eventos:
        events = load_events(100)
        if events:
            for ev in events:
                ts = ev["timestamp"].replace("T", " ")[:19]
                st.markdown(f"⏱️ `{ts}` — {ev['message']}")
        else:
            st.caption("Nenhum evento registrado ainda.")
            
    with tab_comentarios:
        st.markdown("### 💬 Comentários Recentes no Mural")
        st.caption("Aqui você pode visualizar e excluir provocações inadequadas do mural de comentários.")
        from src.bolao.storage import load_all_comentarios, delete_comentario_jogo
        comments = load_all_comentarios()
        
        # Filtro para mostrar deletados ou não
        show_deleted = st.checkbox("Mostrar comentários já excluídos", value=False)
        
        active_comments = [c for c in comments if show_deleted or not c.get("deletado", False)]
        
        if not active_comments:
            st.caption("Nenhum comentário para exibir.")
        else:
            for c in active_comments:
                is_del = c.get("deletado", False)
                del_badge = " [EXCLUÍDO]" if is_del else ""
                
                with st.container(border=True):
                    col_det, col_btn = st.columns([8, 2])
                    with col_det:
                        st.markdown(f"**Jogo ID:** `{c['jogo_id']}` · **Participante:** {c['participante_nome']} {del_badge}")
                        st.markdown(f"*{c['texto']}*")
                        st.caption(f"Enviado em: {c['created_at']}")
                    with col_btn:
                        if not is_del:
                            if st.button("🗑️ Deletar", key=f"mod_del_{c['id']}", type="secondary", width="stretch"):
                                delete_comentario_jogo(c["id"])
                                st.success("Comentário excluído!")
                                st.rerun()


def render_login_screen() -> None:
    from src.bolao.storage import load_submissions, load_live_predictions, load_registered_participants, register_participant
    from src.bolao.utils import normalize_participant_key

    st.markdown(
        """
        <div style='text-align: center; margin-bottom: 30px;'>
            <h1 style='color: var(--ink); font-weight: 900; font-size: 36px; margin-bottom: 10px;'>🏆 Bem-vindo ao Bolão</h1>
            <p style='color: var(--muted); font-size: 16px;'>Identifique-se para palpitar e acompanhar os rankings em tempo real!</p>
        </div>
        """, 
        unsafe_allow_html=True
    )

    # Obter todos os participantes cadastrados
    try:
        subs = load_submissions()
        live_preds = load_live_predictions()
        registered = load_registered_participants()
        
        all_names_set = set()
        for s in subs:
            if s.participant:
                all_names_set.add(s.participant.strip())
        for lp in live_preds:
            if lp.participant_name:
                all_names_set.add(lp.participant_name.strip())
        for r in registered:
            if r:
                all_names_set.add(r.strip())
                
        all_names = sorted(list(all_names_set), key=lambda x: x.lower())
    except Exception:
        all_names = []

    # Display form in a nice card
    st.markdown("<div class='card' style='max-width: 500px; margin: 0 auto; padding: 30px;'>", unsafe_allow_html=True)
    st.markdown("### 👤 Entrar no Bolão")
    
    # Opções
    login_type = st.radio("Como deseja entrar?", ["Selecionar perfil existente", "Criar novo perfil"], horizontal=True, key="login_profile_type")
    
    selected_name = None
    if login_type == "Selecionar perfil existente":
        if not all_names:
            st.info("Nenhum perfil cadastrado ainda. Selecione 'Criar novo perfil' para começar!")
        else:
            selected_name = st.selectbox("Escolha seu nome:", ["-- Selecione --"] + all_names, key="login_select_selectbox")
    else:
        selected_name = st.text_input("Seu nome completo ou apelido:", placeholder="Ex: César", key="login_new_text_input")
        
    btn_enter = st.button("🚀 Entrar no Bolão", type="primary", key="login_submit_btn", width="stretch")
    
    if btn_enter:
        if not selected_name or selected_name == "-- Selecione --" or not selected_name.strip():
            st.error("Por favor, selecione ou digite seu nome.")
        else:
            name_clean = selected_name.strip()
            pkey = normalize_participant_key(name_clean)
            
            # Registrar participante no sistema
            register_participant(name_clean)
            
            # Verificar se já existe palpite clássico para este usuário
            try:
                classic_subs = load_submissions()
                existing_classic = [s for s in classic_subs if s.participant.strip().lower() == name_clean.lower()]
                conf_code = existing_classic[0].submission_id if existing_classic else None
            except Exception:
                conf_code = None
            
            # Definir sessão
            st.session_state["live_user_name"] = name_clean
            st.session_state["live_user_key"] = pkey
            st.session_state["public_sim_name"] = name_clean
            if conf_code:
                st.session_state["live_confirmation_code"] = conf_code
            
            st.query_params["user"] = name_clean
            st.success(f"Entrando como {name_clean}...")
            st.rerun()
            
    st.markdown("</div>", unsafe_allow_html=True)
    
    st.markdown("<br><br>", unsafe_allow_html=True)
    col_login_spacer1, col_login_btn, col_login_spacer2 = st.columns([2, 1.2, 2])
def on_public_nav_change() -> None:
    val = st.session_state.get("public_nav_radio_key")
    if val:
        st.session_state["nav_page"] = val

def on_admin_nav_change() -> None:
    val = st.session_state.get("admin_nav_radio_key")
    if val:
        st.session_state["nav_page"] = val

def on_mobile_nav_change() -> None:
    val = st.session_state.get("mobile_nav_selectbox_key")
    if val:
        st.session_state["nav_page"] = val


def render_global_countdown() -> None:
    from datetime import datetime, timezone, timedelta
    from src.bolao.storage import load_matches
    from src.bolao.ui_live_matches import is_match_open_for_prediction
    
    tz_sp = timezone(timedelta(hours=-3))
    now_sp = datetime.now(tz_sp).replace(tzinfo=None)
    
    matches = load_matches()
    open_future_matches = []
    
    for m in matches:
        if m.starts_at:
            try:
                m_dt = datetime.fromisoformat(m.starts_at)
                if m_dt > now_sp and is_match_open_for_prediction(m):
                    open_future_matches.append((m, m_dt))
            except Exception:
                pass
                
    open_future_matches.sort(key=lambda x: x[1])
    
    try:
        from streamlit_autorefresh import st_autorefresh
        st_autorefresh(interval=10000, key="global_timer_refresh")
    except Exception:
        pass
        
    st.markdown(
        f"""
        <style>
        @keyframes pulse-glow {{
            0% {{ box-shadow: 0 8px 16px rgba(0,0,0,0.3), 0 0 2px rgba(255, 215, 0, 0.2); }}
            50% {{ box-shadow: 0 8px 24px rgba(0,0,0,0.4), 0 0 10px rgba(255, 215, 0, 0.6); }}
            100% {{ box-shadow: 0 8px 16px rgba(0,0,0,0.3), 0 0 2px rgba(255, 215, 0, 0.2); }}
        }}
        @keyframes pulse-green {{
            0% {{ transform: scale(0.9); opacity: 0.7; }}
            50% {{ transform: scale(1.15); opacity: 1; }}
            100% {{ transform: scale(0.9); opacity: 0.7; }}
        }}
        .premium-clock {{
            background: linear-gradient(135deg, #1b4d22 0%, #0c2612 100%);
            border: 2px solid #ffd700;
            border-radius: 14px;
            padding: 16px;
            margin-bottom: 20px;
            text-align: center;
            color: #ffffff;
            animation: pulse-glow 4s infinite ease-in-out;
        }}
        .live-dot {{
            display: inline-block;
            width: 8px;
            height: 8px;
            background-color: #22c55e;
            border-radius: 50%;
            margin-right: 4px;
            box-shadow: 0 0 8px #22c55e;
            animation: pulse-green 2s infinite ease-in-out;
            vertical-align: middle;
        }}
        </style>
        <div class="premium-clock">
            <div style="font-size: 11px; color: #ffd700; font-weight: bold; text-transform: uppercase; letter-spacing: 1.5px; margin-bottom: 6px; display: flex; align-items: center; justify-content: center; gap: 6px;">
                <span class="live-dot"></span> HORA OFICIAL DE BRASÍLIA
            </div>
            <div style="font-size: 28px; font-weight: 900; color: #ffffff; letter-spacing: 1px; font-family: 'Courier New', Courier, monospace; margin-bottom: 4px; text-shadow: 0 2px 4px rgba(0,0,0,0.5);">
                {now_sp.strftime('%H:%M:%S')}
            </div>
        """,
        unsafe_allow_html=True
    )
    
    if open_future_matches:
        next_m, next_dt = open_future_matches[0]
        delta = next_dt - now_sp
        tot_sec = int(delta.total_seconds())
        h, rem = divmod(tot_sec, 3600)
        m, s = divmod(rem, 60)
        
        if h > 24:
            days = h // 24
            time_str = f"⌛ {days} dia(s)"
            color = "#ffd700"
        else:
            time_str = f"⏰ {h:02d}:{m:02d}:{s:02d}"
            color = "#ff4b4b" if h < 1 else "#ffbd03"
            
        st.markdown(
            f"""
            <hr style="margin: 10px 0; border: 0; border-top: 1px solid rgba(255,255,255,0.15);" />
            <div style="font-size: 10px; color: #b2cbb6; font-weight: bold; text-transform: uppercase; letter-spacing: 1px;">⏳ PRÓXIMO BLOQUEIO</div>
            <div style="font-size: 14px; font-weight: 800; margin-top: 4px; color: #ffffff;">{next_m.home_team} × {next_m.away_team}</div>
            <div style="font-size: 10px; color: #b2cbb6; margin-top: 1px;">{next_dt.strftime('%d/%m às %H:%M')}</div>
            <div style="margin-top: 10px; font-size: 18px; font-weight: 900; color: {color}; text-shadow: 0 1px 2px rgba(0,0,0,0.3); font-family: monospace;">{time_str}</div>
            """,
            unsafe_allow_html=True
        )
    else:
        st.markdown(
            f"""
            <hr style="margin: 10px 0; border: 0; border-top: 1px solid rgba(255,255,255,0.15);" />
            <div style="font-size: 10px; color: #b2cbb6; font-weight: bold; text-transform: uppercase; letter-spacing: 1px;">⏳ PRÓXIMO BLOQUEIO</div>
            <div style="margin-top: 8px; font-size: 13px; font-weight: bold; color: #b2cbb6;">Sem jogos abertos</div>
            """,
            unsafe_allow_html=True
        )
        
    st.markdown("</div>", unsafe_allow_html=True)



def main() -> None:
    # Rodar migrações seguras
    try:
        migrate_existing_submissions_to_classic_schema()
        from src.bolao.migrations import sync_classic_to_live_predictions, run_participant_cleanup_migration
        sync_classic_to_live_predictions()
        run_participant_cleanup_migration()
    except Exception:
        pass

    from src.bolao.utils import normalize_participant_key
    # Auto-login via query parameter if session state is empty
    if not st.session_state.get("live_user_name") and "user" in st.query_params:
        username = st.query_params["user"]
        if username:
            pkey = normalize_participant_key(username)
            st.session_state["live_user_name"] = username
            st.session_state["live_user_key"] = pkey
            st.session_state["public_sim_name"] = username
            
            # Find and set classic confirmation code if exists
            try:
                classic_subs = load_submissions()
                existing_classic = [s for s in classic_subs if s.participant.strip().lower() == username.lower()]
                if existing_classic:
                    st.session_state["live_confirmation_code"] = existing_classic[0].submission_id
            except Exception:
                pass

    if "nav_page" not in st.session_state:
        st.session_state["nav_page"] = "Início"
    if "admin_mode" not in st.session_state:
        st.session_state["admin_mode"] = False

    is_logged_in = bool(st.session_state.get("live_user_name"))
    is_admin_flow = st.session_state.get("admin_mode", False) or st.session_state.get("nav_page") == "Admin Login"

    if not is_logged_in and not is_admin_flow:
        with st.sidebar:
            render_global_countdown()
            st.markdown(f"## 🏆 {APP_NAME}")
            st.caption(APP_SUBTITLE)
            st.markdown("---")
            st.info("Por favor, identifique-se na tela principal para navegar pelo site.")
            st.markdown("---")
            render_theme_selector()
            st.markdown("---")
            if st.button("🔒 Área Admin", width="stretch", key="sidebar_admin_login_btn"):
                navigate_to("Admin Login")
        
        render_login_screen()
        return

    with st.sidebar:
        render_global_countdown()
        st.markdown(f"## 🏆 {APP_NAME}")
        st.caption(APP_SUBTITLE)
        st.markdown("---")

        user_name = st.session_state.get("live_user_name")
        if user_name:
            conf_code = st.session_state.get("live_confirmation_code")
            st.markdown(
                f"""
                <div style="background-color: var(--panel-strong); border: 1px solid var(--line); border-radius: 12px; padding: 10px 14px; margin-bottom: 15px; color: var(--ink);">
                    👤 Logado como:<br><b>{user_name}</b>
                    {f'<br><span class="badge success" style="margin-top:5px; font-size:10px; color:#ffffff; background-color:var(--green);">Cartela Vinculada</span>' if conf_code else ''}
                </div>
                """,
                unsafe_allow_html=True
            )
            if st.button("🚪 Sair / Trocar Conta", key="sidebar_logout_btn", width="stretch"):
                st.session_state.pop("live_user_name", None)
                st.session_state.pop("live_user_key", None)
                st.session_state.pop("public_sim_name", None)
                st.session_state.pop("live_confirmation_code", None)
                if "user" in st.query_params:
                    st.query_params.pop("user")
                st.rerun()
            st.markdown("---")

        if st.session_state.get("admin_authenticated", False) and st.session_state.get("admin_mode", False):
            # Admin Menu
            admin_options = ["Dashboard", "Participantes", "Palpites Jogo a Jogo", "Jogos e Agenda", "Resultados Oficiais", "Ranking", "Exportações", "Configurações", "Auditoria", "Ajuda"]
            current_page = st.session_state["nav_page"]
            if current_page not in admin_options:
                current_page = "Dashboard"
            st.session_state["admin_nav_radio_key"] = current_page
            st.radio("Admin Menu", admin_options, key="admin_nav_radio_key", on_change=on_admin_nav_change, label_visibility="collapsed")
            show_admin = True
        else:
            # Acesso Rápido
            st.markdown("### ⚡ Acesso Rápido")
            col_q1, col_q2 = st.columns(2)
            with col_q1:
                if st.button("⚽ Palpitar", key="quick_palpites_btn", width="stretch"):
                    navigate_to("Jogos de Hoje")
                if st.button("📋 Minha Cartela", key="quick_cartela_btn", width="stretch"):
                    navigate_to("Minha Cartela")
            with col_q2:
                if st.button("🏆 Ranking", key="quick_ranking_btn", width="stretch"):
                    navigate_to("Ranking")
                if st.button("🏟️ Match Center", key="quick_match_center_btn", width="stretch"):
                    navigate_to("Match Center")
            st.markdown("---")

            # Grouped Public Menu
            st.markdown("### 📂 Seções do Bolão")
            
            GROUPS = {
                "🏠 Início & Regras": ["Início", "Regras"],
                "⚽ Enviar Palpites": ["Jogos de Hoje", "🇧🇷 Jogos do Brasil", "Palpite Clássico", "⚽ Artilheiro", "Match Center"],
                "🏆 Rankings & Estatísticas": ["Ranking", "Minha Cartela"],
                "💬 Social & Comunidade": ["Central do Bolão", "Palpites do Grupo", "Análise dos Palpites", "Duelo de Palpites"]
            }
            
            def get_page_group(page: str) -> str:
                for grp, pgs in GROUPS.items():
                    if page in pgs:
                        return grp
                return "🏠 Início & Regras"
            
            current_page = st.session_state.get("nav_page", "Início")
            active_group = get_page_group(current_page)
            
            # Initialize selectbox key to prevent default value warnings
            if "active_navigation_group_selectbox" not in st.session_state:
                st.session_state["active_navigation_group_selectbox"] = active_group
            
            # Programmatic navigation synchronization:
            if "last_nav_page" not in st.session_state:
                st.session_state["last_nav_page"] = current_page
                
            if current_page != st.session_state["last_nav_page"]:
                current_selected_group = st.session_state.get("active_navigation_group_selectbox")
                pages_in_sel_group = GROUPS.get(current_selected_group, [])
                if current_page not in pages_in_sel_group:
                    st.session_state["active_navigation_group_selectbox"] = active_group
                    current_selected_group = active_group
                
                # Safeguard public_nav_radio_key
                pages_in_active_grp = GROUPS.get(current_selected_group, [])
                if current_page in pages_in_active_grp:
                    st.session_state["public_nav_radio_key"] = current_page
                else:
                    st.session_state["public_nav_radio_key"] = pages_in_active_grp[0]
                    
                st.session_state["last_nav_page"] = current_page
            
            # Omit index parameter to avoid Streamlit policy warnings
            group_selected = st.selectbox(
                "Escolha a Seção", 
                list(GROUPS.keys()), 
                key="active_navigation_group_selectbox"
            )
            
            pages_in_group = GROUPS[group_selected]
            pages_for_radio = pages_in_group
            
            if current_page != "Admin Login" and current_page not in pages_in_group:
                st.session_state["nav_page"] = pages_in_group[0]
                st.rerun()
                
            if st.session_state.get("public_nav_radio_key") not in pages_for_radio:
                st.session_state["public_nav_radio_key"] = pages_for_radio[0]
                
            st.radio(
                "Páginas",
                pages_for_radio,
                key="public_nav_radio_key",
                on_change=on_public_nav_change,
                label_visibility="collapsed",
                format_func=lambda x: "🏟️ Match Center" if x == "Match Center" else x
            )
            show_admin = False

        st.markdown("---")
        render_theme_selector()
        st.markdown("---")

        if st.session_state.get("admin_authenticated", False):
            if st.session_state.get("admin_mode", False):
                if st.button("🌐 Ver Modo Público", width="stretch"):
                    navigate_to("Início", admin_mode=False)
            else:
                if st.button("🛠️ Painel Admin", width="stretch"):
                    navigate_to("Dashboard", admin_mode=True)
            
            if st.button("🚪 Sair do Admin", width="stretch"):
                st.session_state["admin_authenticated"] = False
                navigate_to("Início", admin_mode=False)
        else:
            if st.button("🔒 Área Admin", width="stretch", key="sidebar_admin_login_btn"):
                navigate_to("Admin Login")

    # Route display
    if st.session_state["nav_page"] == "Admin Login":
        st.markdown("### 🔒 Área Administrativa")
        st.caption("Esta área é protegida. Informe a senha de acesso.")
        
        if "admin_login_attempts" not in st.session_state:
            st.session_state["admin_login_attempts"] = 0
        
        max_attempts = 5
        if st.session_state["admin_login_attempts"] >= max_attempts:
            st.error(f"🔒 Número máximo de tentativas ({max_attempts}) excedido. Aguarde e tente novamente mais tarde.")
        else:
            password = st.text_input("Senha do admin", type="password", key="admin_password_input_page")
            if password:
                try:
                    admin_pwd = st.secrets.get("ADMIN_PASSWORD")
                except Exception:
                    admin_pwd = None
                
                from src.bolao.utils import is_debug_mode
                import os
                is_dev = is_debug_mode() or os.getenv("APP_ENV") == "development"
                
                allowed = False
                if is_dev and password == "brasilhexa":
                    allowed = True
                elif admin_pwd and password == admin_pwd:
                    allowed = True
                
                if allowed:
                    st.session_state["admin_login_attempts"] = 0
                    st.session_state["admin_authenticated"] = True
                    st.success("Login efetuado com sucesso!")
                    navigate_to("Dashboard", admin_mode=True)
                else:
                    st.session_state["admin_login_attempts"] += 1
                    remaining = max_attempts - st.session_state["admin_login_attempts"]
                    st.error(f"Senha incorreta. {remaining} tentativa(s) restante(s).")
                    
        st.markdown("---")
        if st.button("Voltar ao Início", width="stretch"):
            navigate_to("Início")
        return

    # Renderizar menu de navegação móvel rápida (apenas para celular)
    if st.session_state["nav_page"] != "Admin Login":
        m_opts = [
            "Dashboard", "Participantes", "Palpites Jogo a Jogo", "Jogos e Agenda", "Resultados Oficiais", 
            "Ranking", "Exportações", "Configurações", "Auditoria", "Ajuda"
        ] if show_admin else [
            "Início", "Jogos de Hoje", "🇧🇷 Jogos do Brasil", "Palpite Clássico", "⚽ Artilheiro", "Minha Cartela", 
            "Ranking", "Central do Bolão", "Palpites do Grupo", 
            "Análise dos Palpites", "Duelo de Palpites", "Match Center", "Regras"
        ]
        current_p = st.session_state["nav_page"]
        if current_p in m_opts:
            st.session_state["mobile_nav_selectbox_key"] = current_p
        else:
            st.session_state["mobile_nav_selectbox_key"] = m_opts[0]
            
        st.markdown('<div class="mobile-only-nav-trigger"></div>', unsafe_allow_html=True)
        st.selectbox("🧭 Navegação Rápida", m_opts, key="mobile_nav_selectbox_key", on_change=on_mobile_nav_change)

    if show_admin:
        if not st.session_state.get("admin_authenticated", False):
            st.error("🔒 Acesso não autorizado. Faça login como administrador.")
            navigate_to("Admin Login")
        else:
            page = st.session_state["nav_page"]
            if page == "Dashboard":
                admin_dashboard()
            elif page == "Participantes":
                admin_participants()
            elif page == "Palpites Jogo a Jogo":
                admin_palpites_jogo_a_jogo()
            elif page == "Editar Palpite Clássico":
                admin_edit_classic_page()
            elif page == "Jogos e Agenda":
                admin_matches_agenda()
            elif page == "Resultados Oficiais":
                admin_official_results()
            elif page == "Ranking":
                admin_ranking()
            elif page == "Exportações":
                admin_exports()
            elif page == "Configurações":
                admin_settings()
            elif page == "Auditoria":
                admin_auditoria()
            elif page == "🇧🇷 Seleção Brasileira":
                admin_selecao_brasileira()
            else:
                admin_help()
    else:
        user_name = st.session_state.get("live_user_name")
        if user_name:
            try:
                from src.bolao.ui_ranking import verificar_mudanca_posicao
                mudanca = verificar_mudanca_posicao(user_name)
                if mudanca:
                    if mudanca["delta"] > 0:
                        st.success(f"📈 Você subiu {mudanca['delta']} posição(ões)! Agora é {mudanca['posicao_atual']}º.")
                    else:
                        st.warning(f"📉 Você caiu {abs(mudanca['delta'])} posição(ões). Agora é {mudanca['posicao_atual']}º.")
            except Exception:
                pass
        page = st.session_state["nav_page"]
        if page == "Início":
            public_home()
        elif page == "Palpite Clássico":
            public_submission()
        elif page == "Jogos de Hoje":
            render_jogos_de_hoje()
        elif page == "🇧🇷 Jogos do Brasil":
            render_jogos_do_brasil()
        elif page == "Minha Cartela":
            render_minha_cartela()
        elif page == "Ranking":
            public_ranking()
        elif page == "Central do Bolão":
            render_central_do_bolao()
        elif page == "Palpites do Grupo":
            render_palpites_do_grupo()
        elif page == "Análise dos Palpites":
            render_analise_dos_palpites()
        elif page == "Duelo de Palpites":
            render_duelo_de_palpites()
        elif page == "Regras":
            render_regras_do_bolao()
        elif page == "Match Center":
            render_match_center()
        elif page == "⚽ Artilheiro":
            render_page_artilheiro()


if __name__ == "__main__":
    main()
