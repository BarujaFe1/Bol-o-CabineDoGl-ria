from __future__ import annotations

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from typing import Any
from .models import LivePrediction, Prediction, LiveMatch
from .storage import (
    load_matches,
    load_live_predictions,
    save_live_predictions,
    load_config,
    append_event,
    load_submissions,
    load_official,
    load_brasil_palpites_goleadores,
    save_brasil_palpite_goleadores
)
from .utils import normalize_participant_key, now_iso, render_countdown, avatar_url
from .live_scoring import calculate_live_prediction_points, calculate_live_ranking
from .ui_simulator import get_team_badge_path
from .social import build_live_match_share_text
from .ui_components import render_badge
from streamlit_autorefresh import st_autorefresh

def is_match_open_for_prediction(match: Any, now: str | None = None) -> bool:
    """
    Retorna True se o palpite está aberto.
    """
    from datetime import timezone, timedelta

    # Check match status first
    if getattr(match, "status", None) in ("finished", "result_approved"):
        return False

    # Check manual override
    if hasattr(match, "bets_manual_closed") and match.bets_manual_closed is not None:
        return not match.bets_manual_closed

    if not match.starts_at:
        return False
    
    # 1. Get lock minutes from config
    try:
        from .storage import load_config
        config = load_config()
    except Exception:
        config = {}
    
    lock_minutes = int(config.get("live_lock_minutes_before_match", 10))
    
    # 2. Compute lock_at if not explicitly set
    if not getattr(match, "lock_at", None):
        try:
            dt = datetime.fromisoformat(match.starts_at)
            lock_dt = dt - timedelta(minutes=lock_minutes)
        except Exception:
            return False
    else:
        try:
            lock_dt = datetime.fromisoformat(match.lock_at)
        except Exception:
            return False
            
    # Normalize lock_dt: if naive, assume America/Sao_Paulo (UTC-3)
    tz_sp = timezone(timedelta(hours=-3))
    if lock_dt.tzinfo is None:
        lock_dt = lock_dt.replace(tzinfo=tz_sp)
        
    # Get now_dt as aware in UTC
    if now is None:
        now_dt = datetime.now(timezone.utc)
    else:
        try:
            now_dt = datetime.fromisoformat(now)
            if now_dt.tzinfo is None:
                now_dt = now_dt.replace(tzinfo=tz_sp)
        except Exception:
            now_dt = datetime.now(timezone.utc)
            
    # Convert both to UTC for absolute comparison
    now_utc = now_dt.astimezone(timezone.utc)
    lock_utc = lock_dt.astimezone(timezone.utc)
        
    return now_utc < lock_utc


def jogo_esta_ao_vivo(m: Any) -> bool:
    from datetime import datetime, timezone, timedelta
    if not getattr(m, "starts_at", None):
        return False
    if getattr(m, "status", None) == "result_approved":
        return False
    try:
        agora = datetime.now(timezone.utc)
        inicio = datetime.fromisoformat(m.starts_at)
        tz_sp = timezone(timedelta(hours=-3))
        if inicio.tzinfo is None:
            inicio = inicio.replace(tzinfo=tz_sp)
        inicio_utc = inicio.astimezone(timezone.utc)
        fim_estimado = inicio_utc + timedelta(hours=2, minutes=15)
        return inicio_utc <= agora <= fim_estimado
    except Exception:
        return False

def render_jogos_de_hoje() -> None:
    st_autorefresh(interval=30_000, key="timer_refresh")
    st.markdown("### ⚽ Jogos de Hoje — Jogo a Jogo")
    st.caption("Palpite em cada partida individualmente até 10 minutos antes do início do jogo e acompanhe os palpites dos seus amigos após o bloqueio.")

    config = load_config()
    if not config.get("live_mode_enabled", True):
        st.warning("O Modo Jogo a Jogo está desativado no momento. Entre em contato com a organização.")
        return

    # 1. Identificação do participante
    if "live_user_name" not in st.session_state:
        st.session_state["live_user_name"] = ""
        st.session_state["live_user_key"] = ""

    user_name = st.session_state.get("live_user_name", "")
    
    if not user_name:
        st.markdown("#### 👤 Identifique-se para palpitar")
        with st.form("live_user_identification"):
            input_name = st.text_input("Seu Nome no Bolão", placeholder="Ex: César")
            input_code = st.text_input("Código de Confirmação Clássico (Opcional)", placeholder="Ex: a10ce10e6a14", help="Se você já enviou um palpite clássico, informe o código para sincronizar seus dados.")
            
            submitted = st.form_submit_button("Entrar", width="stretch")
            if submitted:
                if not input_name.strip():
                    st.error("Por favor, digite seu nome.")
                else:
                    name_clean = input_name.strip()
                    pkey = normalize_participant_key(name_clean)
                    
                    classic_subs = load_submissions()
                    existing_classic = [s for s in classic_subs if s.participant.strip().lower() == name_clean.lower()]
                    
                    if existing_classic:
                        classic_pred = existing_classic[0]
                        if input_code.strip() and input_code.strip() != classic_pred.submission_id:
                            st.error("Código de confirmação clássico inválido para este participante.")
                            return
                        elif not input_code.strip():
                            st.warning(f"Vinculando ao participante clássico '{classic_pred.participant}'. Se este não for você, por favor informe o código de confirmação.")
                            
                    st.session_state["live_user_name"] = name_clean
                    st.session_state["live_user_key"] = pkey
                    st.session_state["live_confirmation_code"] = existing_classic[0].submission_id if existing_classic else None
                    st.success(f"Bem-vindo(a), {name_clean}! Identificação salva.")
                    st.rerun()
        return

    # User identified
    user_key = st.session_state["live_user_key"]
    user_name = st.session_state["live_user_name"]
    conf_code = st.session_state.get("live_confirmation_code")

    st.markdown(
        f"""
        <div style="padding: 12px 16px; border-radius: 12px; background-color: var(--panel); border: 1px solid var(--line); margin-bottom: 20px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px; color: var(--ink);">
            <div>
                👤 Participante: <b>{user_name}</b> {f'<span class="badge info">Clássico Vinculado</span>' if conf_code else ''}
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )
    
    if st.button("🚪 Alterar Usuário/Sair", key="live_btn_change_user", width="stretch"):
        st.session_state.pop("live_user_name", None)
        st.session_state.pop("live_user_key", None)
        st.session_state.pop("live_confirmation_code", None)
        st.rerun()

    matches = load_matches()
    live_preds = load_live_predictions()

    if not matches:
        st.info("Nenhum jogo cadastrado na agenda do bolão.")
        return

    from datetime import datetime, timezone, timedelta
    tz_sp = timezone(timedelta(hours=-3))
    today_str = datetime.now(tz_sp).strftime("%Y-%m-%d")

    if "jogos_hoje_selected_date" not in st.session_state:
        st.session_state["jogos_hoje_selected_date"] = today_str

    current_selected_date = st.session_state["jogos_hoje_selected_date"]

    st.markdown("#### 📅 Calendário de Jogos")
    col_nav1, col_nav2, col_nav3, col_nav4 = st.columns([1, 2, 1, 1])

    with col_nav1:
        if st.button("⬅️ Anterior", key="btn_prev_date", width="stretch"):
            dt = datetime.strptime(current_selected_date, "%Y-%m-%d")
            st.session_state["jogos_hoje_selected_date"] = (dt - timedelta(days=1)).strftime("%Y-%m-%d")
            st.rerun()

    with col_nav2:
        try:
            dt_display = datetime.strptime(current_selected_date, "%Y-%m-%d")
            weekdays = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]
            months = ["", "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
            display_str = f"{weekdays[dt_display.weekday()]}, {dt_display.day} de {months[dt_display.month]}"
        except Exception:
            display_str = current_selected_date
        st.markdown(f"<div style='text-align: center; font-weight: bold; line-height: 38px; font-size: 15px; color: var(--ink);'>{display_str}</div>", unsafe_allow_html=True)

    with col_nav3:
        if st.button("➡️ Próximo", key="btn_next_date", width="stretch"):
            dt = datetime.strptime(current_selected_date, "%Y-%m-%d")
            st.session_state["jogos_hoje_selected_date"] = (dt + timedelta(days=1)).strftime("%Y-%m-%d")
            st.rerun()

    with col_nav4:
        if st.button("📅 Hoje", key="btn_today_date", width="stretch"):
            st.session_state["jogos_hoje_selected_date"] = today_str
            st.rerun()

    # Filter to only show games on the selected date
    matches = [m for m in matches if m.starts_at and m.starts_at.split("T")[0] == current_selected_date]

    if not matches:
        st.info("⚽ Não há jogos agendados para esta data.")
        return

    def get_sort_key(m):
        g = m.group or ""
        g_clean = g.strip().upper()
        if not g_clean or len(g_clean) > 1 or g_clean < 'A' or g_clean > 'L':
            group_key = "Z_Mata-Mata"
        else:
            group_key = f"Grupo {g_clean}"
        return (group_key, m.starts_at or "", m.sort_order)
    matches.sort(key=get_sort_key)

    # F19 — Modo Relâmpago Card
    lightning_matches = [m for m in matches if getattr(m, "modo_relampago_ativo", False)]
    for lm in lightning_matches:
        lm_pred = next((p for p in live_preds if p.match_id == lm.match_id and (p.participant_key or normalize_participant_key(p.participant_name)) == user_key), None)
        
        st.markdown(
            f"""
            <div style="background-color: #ffd700; color: #1a472a; padding: 15px; border-radius: 12px; border: 2px solid #1a472a; margin-bottom: 15px; font-weight: bold; text-align: center; box-shadow: 0 4px 10px rgba(0,0,0,0.15);">
                ⚡ MODO RELÂMPAGO ATIVO ⚡
                <div style="font-size: 14px; margin-top: 4px; color: #1a472a;">Como vai terminar o 2º tempo de {lm.home_team} {lm.placar_intervalo_mandante or 0} × {lm.placar_intervalo_visitante or 0} {lm.away_team}?</div>
            </div>
            """,
            unsafe_allow_html=True
        )
        
        with st.container():
            col_l1, col_l2 = st.columns(2)
            with col_l1:
                cur_h = lm_pred.predicted_second_half_home_goals if (lm_pred and lm_pred.predicted_second_half_home_goals is not None) else 0
                pred_h = st.number_input(f"Gols {lm.home_team} no 2º tempo", min_value=0, max_value=10, value=cur_h, key=f"lightning_h_{lm.match_id}")
            with col_l2:
                cur_a = lm_pred.predicted_second_half_away_goals if (lm_pred and lm_pred.predicted_second_half_away_goals is not None) else 0
                pred_a = st.number_input(f"Gols {lm.away_team} no 2º tempo", min_value=0, max_value=10, value=cur_a, key=f"lightning_a_{lm.match_id}")
                
            st.markdown(
                f"""
                <div style="font-size:12px; color:var(--muted); text-align:center; margin-bottom:8px;">
                    ℹ️ Placar final estimado: <b>{lm.home_team} {(lm.placar_intervalo_mandante or 0) + pred_h} × {(lm.placar_intervalo_visitante or 0) + pred_a} {lm.away_team}</b><br>
                    🎯 Exato: <b>+4pts</b> · Resultado: <b>+2pts</b> (pontos do 2º tempo apenas)
                </div>
                """,
                unsafe_allow_html=True
            )
            
            if st.button("⚡ Salvar Relâmpago", key=f"btn_save_lightning_{lm.match_id}", width="stretch"):
                if lm_pred:
                    lm_pred.predicted_second_half_home_goals = int(pred_h)
                    lm_pred.predicted_second_half_away_goals = int(pred_a)
                    lm_pred.updated_at = datetime.now().isoformat()
                else:
                    pred_id = f"{user_key}_{lm.match_id}"
                    lm_pred = LivePrediction(
                        id=pred_id,
                        participant_name=user_name,
                        participant_key=user_key,
                        match_id=lm.match_id,
                        predicted_home_goals=0,
                        predicted_away_goals=0,
                        predicted_second_half_home_goals=int(pred_h),
                        predicted_second_half_away_goals=int(pred_a),
                        submitted_at=datetime.now().isoformat(),
                        updated_at=datetime.now().isoformat(),
                    )
                    live_preds.append(lm_pred)
                save_live_predictions(live_preds)
                st.success("⚡ Palpite relâmpago salvo com sucesso!")
                st.rerun()
        st.markdown("---")

    # Tabs
    m_tabs = st.tabs(["🚀 Jogos Abertos", "🔒 Jogos Fechados & Live", "🏆 Resultados Aprovados"])
    
    now = datetime.now().isoformat()

    open_matches = []
    locked_matches = []
    finished_matches = []

    for m in matches:
        if m.status == "result_approved":
            finished_matches.append(m)
        elif is_match_open_for_prediction(m, now):
            open_matches.append(m)
        else:
            locked_matches.append(m)

    # 1. Jogos Abertos
    with m_tabs[0]:
        st.markdown("#### Dê seus Palpites")
        if not open_matches:
            st.info("Nenhum jogo aberto para palpitar no momento.")
        else:
            filtro_pendente = st.radio("Mostrar:", ["Todos os jogos", "Apenas pendentes (sem palpite ainda)"], horizontal=True, key="filtro_jogos_abertos")
            
            if filtro_pendente == "Apenas pendentes (sem palpite ainda)":
                def tem_palpite(m_id):
                    p_id = f"{user_key}_{m_id}"
                    return any(p.id == p_id for p in live_preds)
                open_matches = [m for m in open_matches if not tem_palpite(m.match_id)]
                
            if not open_matches:
                st.info("🎉 Você já palpitou em todos os jogos abertos!")
                
            _last_group = None
            for m in open_matches:
                _cur_group = f"Grupo {m.group}" if (m.group and m.group.strip()) else "Mata-Mata"
                if _cur_group != _last_group:
                    st.markdown(f"##### 🏆 {_cur_group}")
                    _last_group = _cur_group
                pred_id = f"{user_key}_{m.match_id}"
                pred = next((p for p in live_preds if p.id == pred_id), None)
                
                # F01 - Live Countdown
                lock_mins = int(config.get("live_lock_minutes_before_match", 10))
                try:
                    dt = datetime.fromisoformat(m.starts_at)
                    countdown_str = render_countdown(dt, lock_mins)
                except Exception:
                    countdown_str = "🔒 FECHADO"
                
                is_closed = not is_match_open_for_prediction(m)
                
                default_h = pred.predicted_home_goals if pred else 0
                default_a = pred.predicted_away_goals if pred else 0

                from .simulator_engine import name_to_id
                h_id = name_to_id(m.home_team)
                a_id = name_to_id(m.away_team)
                h_badge = get_team_badge_path(h_id) if h_id else None
                a_badge = get_team_badge_path(a_id) if a_id else None

                is_live = jogo_esta_ao_vivo(m)
                live_badge_html = '<span style="background:#dc2626;color:white;padding:2px 8px;border-radius:4px;font-size:12px;font-weight:bold;margin-left:8px;">🔴 AO VIVO</span>' if is_live else ''

                with st.container(border=True):
                    # Unified Card Header
                    st.markdown(
                        f"""
                        <div style="display: flex; justify-content: space-between; font-size: 13px; color: var(--muted); font-weight: bold; margin-bottom: 15px; border-bottom: 1px solid var(--line); padding-bottom: 8px; align-items: center;">
                            <span>🏆 {m.round_label} {f'· Grupo {m.group}' if m.group else ''}{live_badge_html}</span>
                            <span style="color: {'var(--red)' if is_closed else 'var(--green)'}; font-weight: bold;">{'🔒 FECHADO' if is_closed else countdown_str}</span>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
                    
                    # F03 - Stadium and fuso info
                    if getattr(m, "stadium", None):
                        from .constants import VENUES_COPA_2026
                        venue = VENUES_COPA_2026.get(m.stadium)
                        if venue:
                            st.markdown(
                                f"""
                                <div style="font-size: 12px; color: var(--muted); margin-bottom: 12px; margin-top: -8px;">
                                    🏟️ {venue['pais']} {m.stadium} · {venue['cidade']} · {datetime.fromisoformat(m.starts_at).strftime('%H:%M')} local ({venue['fuso']})
                                </div>
                                """,
                                unsafe_allow_html=True
                            )
                        else:
                            st.markdown(
                                f"""
                                <div style="font-size: 12px; color: var(--muted); margin-bottom: 12px; margin-top: -8px;">
                                    🏟️ {m.stadium}
                                </div>
                                """,
                                unsafe_allow_html=True
                            )
                    
                    # Columns for team flags, inputs, and save button
                    c_team1, c_vs_inputs, c_team2, c_btn = st.columns([3, 4, 3, 2])
                    
                    with c_team1:
                        st.markdown("<div style='text-align: center;'>", unsafe_allow_html=True)
                        if h_badge: st.image(h_badge, width=32)
                        st.markdown(f"<div style='font-weight: 700; margin-top: 4px; color: var(--ink);'>{m.home_team}</div>", unsafe_allow_html=True)
                        st.markdown("</div>", unsafe_allow_html=True)
                        
                    with c_vs_inputs:
                        sub_i1, sub_vs, sub_i2 = st.columns([2, 1, 2])
                        with sub_i1:
                            val_h = st.number_input(f"{m.home_team} gols", min_value=0, max_value=20, value=default_h, step=1, key=f"live_h_{m.match_id}", label_visibility="collapsed", disabled=is_closed)
                        with sub_vs:
                            st.markdown("<div style='text-align: center; font-size: 18px; font-weight: bold; line-height: 44px; color: var(--muted);'>x</div>", unsafe_allow_html=True)
                        with sub_i2:
                            val_a = st.number_input(f"{m.away_team} gols", min_value=0, max_value=20, value=default_a, step=1, key=f"live_a_{m.match_id}", label_visibility="collapsed", disabled=is_closed)
                            
                    with c_team2:
                        st.markdown("<div style='text-align: center;'>", unsafe_allow_html=True)
                        if a_badge: st.image(a_badge, width=32)
                        st.markdown(f"<div style='font-weight: 700; margin-top: 4px; color: var(--ink);'>{m.away_team}</div>", unsafe_allow_html=True)
                        st.markdown("</div>", unsafe_allow_html=True)

                    # F02 - reminders buttons
                    if not is_closed:
                        st.markdown("<div style='margin-top: 10px;'></div>", unsafe_allow_html=True)
                        col_rem1, col_rem2 = st.columns(2)
                        with col_rem1:
                            import urllib.parse
                            dt_starts = datetime.fromisoformat(m.starts_at)
                            starts_str = dt_starts.strftime("%H:%M")
                            texto_wa = (f"⏰ *Bolão da Cabine do Glória*\n"
                                        f"Não esquece de palpitar em *{m.home_team} x {m.away_team}*!\n"
                                        f"Fecha às {starts_str} (10min antes do apito)\n"
                                        f"👉 https://bolaodogloria.streamlit.app/")
                            wa_link = f"https://wa.me/?text={urllib.parse.quote(texto_wa)}"
                            st.link_button("📲 Lembrar no WhatsApp", wa_link, width="stretch")
                        with col_rem2:
                            dt_lembrete = dt_starts - timedelta(minutes=30)
                            dt_fim = dt_lembrete + timedelta(hours=1)
                            fmt = "%Y%m%dT%H%M%SZ"
                            params = urllib.parse.urlencode({
                                "action": "TEMPLATE",
                                "text": f"⚽ Palpitar: {m.home_team} x {m.away_team} — Bolão do Glória",
                                "dates": f"{dt_lembrete.strftime(fmt)}/{dt_fim.strftime(fmt)}",
                                "details": "Lembrete automático do Bolão da Cabine do Glória.",
                            })
                            gcal_link = f"https://calendar.google.com/calendar/render?{params}"
                            st.link_button("📅 Adicionar ao Google Agenda", gcal_link, width="stretch")

                    # F05 - Módulo Brasil Card Redirect
                    is_brasil_game = ("Brasil" in m.home_team or "Brasil" in m.away_team)
                    gols_bra = 0
                    if is_brasil_game:
                        gols_bra = val_h if m.home_team == "Brasil" else val_a
                        st.markdown("""
                        <div style="background: linear-gradient(135deg, #1a472a, #0d2818);
                                     border: 2px solid #ffd700; border-radius: 12px;
                                     padding: 16px; margin: 12px 0; color: white; box-shadow: 0 4px 10px rgba(0,0,0,0.15);">
                            <strong>🇧🇷 Este é um jogo do Brasil!</strong><br>
                            Escale seus goleadores, assistentes e reservas no Módulo Brasil.
                        </div>
                        """, unsafe_allow_html=True)
                        if st.button("⚽ Ir para o Módulo Brasil", key=f"goto_brasil_{m.match_id}", width="stretch"):
                            st.session_state["jogo_brasil_selecionado"] = m.match_id
                            from .navigation import navigate_to
                            navigate_to("🇧🇷 Jogos do Brasil")
                        
                        # Show warning if goals count doesn't match saved scorers count
                        if gols_bra > 0:
                            palpites_g = load_brasil_palpites_goleadores()
                            user_palpite = next((p for p in palpites_g if p["participante_nome"] == user_name and p["jogo_id"] == m.match_id), None)
                            saved_goleadores = user_palpite.get("goleadores", []) if user_palpite else []
                            if len(saved_goleadores) != gols_bra:
                                st.warning(f"⚠️ Você apostou {gols_bra} gol(s) do Brasil, mas escalou {len(saved_goleadores)} goleador(es). Por favor, clique no botão acima para ajustar!")

                    with c_btn:
                        st.markdown("<div style='height: 4px;'></div>", unsafe_allow_html=True)
                        can_save = (not is_closed)
                            
                        if st.button("💾 Salvar", key=f"save_btn_{m.match_id}", type="primary", width="stretch", disabled=not can_save):
                            from .storage import upsert_live_prediction
                            upsert_live_prediction(
                                participant_name=user_name,
                                match_id=m.match_id,
                                home_goals=int(val_h),
                                away_goals=int(val_a),
                                confirmation_code=conf_code
                            )
                            if is_brasil_game:
                                palpites_g = load_brasil_palpites_goleadores()
                                user_palpite = next((p for p in palpites_g if p["participante_nome"] == user_name and p["jogo_id"] == m.match_id), None)
                                saved_goleadores = user_palpite.get("goleadores", []) if user_palpite else []
                                saved_assistentes = user_palpite.get("assistentes", []) if user_palpite else []
                                saved_reservas = user_palpite.get("reservas", []) if user_palpite else []
                                
                                # Crop to match new gols_bra count
                                if len(saved_goleadores) > gols_bra:
                                    saved_goleadores = saved_goleadores[:gols_bra]
                                if len(saved_assistentes) > gols_bra:
                                    saved_assistentes = saved_assistentes[:gols_bra]
                                if len(saved_reservas) > gols_bra:
                                    saved_reservas = saved_reservas[:gols_bra]
                                    
                                save_brasil_palpite_goleadores({
                                    "participante_nome": user_name,
                                    "jogo_id": m.match_id,
                                    "gols_brasil_apostados": gols_bra,
                                    "goleadores": saved_goleadores,
                                    "assistentes": saved_assistentes,
                                    "reservas": saved_reservas,
                                    "pontos_ganhos": None
                                })
                            append_event("live_guess_saved", f"Palpite de {user_name} para {m.home_team} x {m.away_team} salvo.")
                            st.toast("Palpite salvo com sucesso!")
                            st.rerun()
                            
                    if pred and getattr(pred, "contador_edicoes", 0) > 0 and not is_closed:
                        ts = pred.updated_at
                        time_str = ts.replace("T", " ")[:16] if ts else "—"
                        st.markdown(f"<div style='font-size: 11px; color: var(--muted); margin-top: 8px;'>✏️ Editado <b>{pred.contador_edicoes}x</b> · última vez: {time_str}</div>", unsafe_allow_html=True)

    # 2. Jogos Fechados / Live
    with m_tabs[1]:
        st.markdown("#### Palpites Fechados (Revelados)")
        if not locked_matches:
            st.info("Nenhum jogo bloqueado ou em andamento no momento.")
        else:
            _last_group = None
            for m in locked_matches:
                _cur_group = f"Grupo {m.group}" if (m.group and m.group.strip()) else "Mata-Mata"
                if _cur_group != _last_group:
                    st.markdown(f"##### 🏆 {_cur_group}")
                    _last_group = _cur_group
                pred_id = f"{user_key}_{m.match_id}"
                pred = next((p for p in live_preds if p.id == pred_id), None)
                
                from .simulator_engine import name_to_id
                h_id = name_to_id(m.home_team)
                a_id = name_to_id(m.away_team)
                h_badge = get_team_badge_path(h_id) if h_id else None
                a_badge = get_team_badge_path(a_id) if a_id else None

                with st.container(border=True):
                    # Header
                    col_info, col_status = st.columns([2, 1])
                    with col_info:
                        st.markdown(f"🏆 **{m.round_label}** {f'· Grupo {m.group}' if m.group else ''}")
                    with col_status:
                        if jogo_esta_ao_vivo(m):
                            st.markdown(f"<div style='text-align: right; color: white; background: #dc2626; padding: 2px 8px; border-radius: 4px; font-size:12px; font-weight: bold; display: inline-block; float: right;'>🔴 AO VIVO</div>", unsafe_allow_html=True)
                        else:
                            st.markdown(f"<div style='text-align: right; color: var(--red); font-weight: bold;'>🔒 Fechado</div>", unsafe_allow_html=True)
                    
                    # Columns for team flags/names and prediction badge
                    col_match, col_user_pred = st.columns([3, 1])
                    
                    with col_match:
                        c_flag1, c_vs_name, c_flag2 = st.columns([1, 4, 1])
                        with c_flag1:
                            if h_badge: st.image(h_badge, width=28)
                        with c_vs_name:
                            st.markdown(f"**{m.home_team}** vs **{m.away_team}**")
                        with c_flag2:
                            if a_badge: st.image(a_badge, width=28)
                        
                    with col_user_pred:
                        if pred:
                            st.markdown(
                                f"""
                                <div style="background-color: var(--gold-bg); padding: 6px 10px; border-radius: 8px; text-align: center; font-size: 13px; font-weight: bold; color: var(--gold);">
                                    Seu palpite: {pred.predicted_home_goals} x {pred.predicted_away_goals}
                                </div>
                                """,
                                unsafe_allow_html=True
                            )
                        else:
                            st.markdown(
                                """
                                <div style="background-color: var(--red-bg); padding: 6px 10px; border-radius: 8px; text-align: center; font-size: 13px; font-weight: bold; color: var(--red);">
                                    Sem palpite
                                </div>
                                """,
                                unsafe_allow_html=True
                            )
                    
                    # Match Center expansion
                    reveal_enabled = config.get("reveal_live_predictions_after_lock", True)
                    if reveal_enabled:
                        with st.expander(f"👁️ Ver palpites de outros e estatísticas para {m.home_team} x {m.away_team}"):
                            if st.button("Abrir Match Center", key=f"btn_mc_link_{m.match_id}", width="stretch"):
                                from .navigation import navigate_to
                                st.session_state["match_center_selected_match_id"] = m.match_id
                                navigate_to("Match Center")
                    else:
                        st.caption("🔒 Revelação de palpites desativada pela organização.")

    # 3. Resultados Aprovados
    with m_tabs[2]:
        st.markdown("#### Jogos Concluídos")
        if not finished_matches:
            st.info("Nenhum jogo concluído e aprovado na agenda ainda.")
        else:
            _last_group = None
            for m in finished_matches:
                _cur_group = f"Grupo {m.group}" if (m.group and m.group.strip()) else "Mata-Mata"
                if _cur_group != _last_group:
                    st.markdown(f"##### 🏆 {_cur_group}")
                    _last_group = _cur_group
                pred_id = f"{user_key}_{m.match_id}"
                pred = next((p for p in live_preds if p.id == pred_id), None)
                
                points_gained = 0
                breakdown_text = "Nenhum acerto"
                
                if pred:
                    res = calculate_live_prediction_points(pred, m, config)
                    points_gained = res["points"]
                    breakdown_text = " · ".join(res["breakdown"])
                
                badge_color = "success" if points_gained > 0 else "error"
                points_badge = render_badge(f"+{points_gained} pts", badge_color)
                
                from .simulator_engine import name_to_id
                h_id = name_to_id(m.home_team)
                a_id = name_to_id(m.away_team)
                h_badge = get_team_badge_path(h_id) if h_id else None
                a_badge = get_team_badge_path(a_id) if a_id else None

                with st.container(border=True):
                    # Header
                    col_info, col_status = st.columns([2, 1])
                    with col_info:
                        st.markdown(f"🏆 **{m.round_label}** {f'· Grupo {m.group}' if m.group else ''}")
                    with col_status:
                        st.markdown(f"<div style='text-align: right; color: var(--muted); font-weight: bold;'>🏁 Concluído</div>", unsafe_allow_html=True)
                    
                    # Columns
                    col_match, col_badge = st.columns([3, 1])
                    with col_match:
                        # Match scores with flags
                        c_f1, c_text, c_f2 = st.columns([1, 4, 1])
                        with c_f1:
                            if h_badge: st.image(h_badge, width=28)
                        with c_text:
                            st.markdown(f"**{m.home_team} {m.official_home_goals} x {m.official_away_goals} {m.away_team}**")
                        with c_f2:
                            if a_badge: st.image(a_badge, width=28)
                    with col_badge:
                        st.markdown(f"<div style='text-align: right;'>{points_badge}</div>", unsafe_allow_html=True)
                        
                    st.markdown(
                        f"""
                        <div style="font-size: 13px; color: var(--muted); margin-top: 8px; padding-top: 8px; border-top: 1px dashed var(--line);">
                            ⚽ <b>Seu palpite:</b> {f'{pred.predicted_home_goals} x {pred.predicted_away_goals}' if pred else 'Não palpitou'} 
                            <br>💡 <b>Pontuação detalhada:</b> {breakdown_text}
                        </div>
                        """,
                        unsafe_allow_html=True
                    )


def render_match_center() -> None:
    st.markdown("### 🏟️ Match Center")
    st.caption("Acompanhe o termômetro das apostas do grupo e simule o impacto no ranking em tempo real.")
    
    matches = load_matches()
    live_preds = load_live_predictions()
    config = load_config()

    if not matches:
        st.info("Nenhum jogo disponível na agenda.")
        return

    # Obter jogo pré-selecionado do estado ou permitir selecionar
    preselected_id = st.session_state.get("match_center_selected_match_id")
    def get_sort_key(m):
        g = m.group or ""
        g_clean = g.strip().upper()
        if not g_clean or len(g_clean) > 1 or g_clean < 'A' or g_clean > 'L':
            group_key = "Z_Mata-Mata"
        else:
            group_key = f"Grupo {g_clean}"
        return (group_key, m.starts_at or "", m.sort_order)
    matches.sort(key=get_sort_key)
    
    idx_sel = 0
    if preselected_id:
        ids = [m.match_id for m in matches]
        if preselected_id in ids:
            idx_sel = ids.index(preselected_id)

    selected_match = st.selectbox(
        "Selecione a partida para analisar", 
        matches, 
        index=idx_sel,
        format_func=lambda m: f"{m.home_team} x {m.away_team} ({m.round_label})"
    )

    if not selected_match:
        return

    m = selected_match
    now = datetime.now().isoformat()
    is_open = is_match_open_for_prediction(m, now)

    # Detalhes principais da partida
    from .simulator_engine import name_to_id
    h_id = name_to_id(m.home_team)
    a_id = name_to_id(m.away_team)
    h_badge = get_team_badge_path(h_id) if h_id else None
    a_badge = get_team_badge_path(a_id) if a_id else None

    col_h1, col_vs, col_h2 = st.columns([4, 1, 4])
    with col_h1:
        st.markdown(f"<div style='text-align:center;'>", unsafe_allow_html=True)
        if h_badge:
            st.image(h_badge, width=64)
        st.markdown(f"<h4>{m.home_team}</h4></div>", unsafe_allow_html=True)
    with col_vs:
        st.markdown("<br><br><div style='text-align:center; font-size:24px; font-weight:bold; color:var(--muted);'>VS</div>", unsafe_allow_html=True)
    with col_h2:
        st.markdown(f"<div style='text-align:center;'>", unsafe_allow_html=True)
        if a_badge:
            st.image(a_badge, width=64)
        st.markdown(f"<h4>{m.away_team}</h4></div>", unsafe_allow_html=True)

    # Status e prazos
    status_label = "Aberto para Palpites" if is_open else "Bloqueado para Palpites"
    status_color = "success" if is_open else "error"
    
    st.markdown(
        f"""
        <div style="text-align: center; margin: 15px 0;">
            {render_badge(status_label, status_color)}
            <div style="font-size:14px; color: var(--muted); margin-top: 6px;">
                📅 Início: {m.starts_at.replace("T", " ")} | 🔒 Fechamento: {m.lock_at.replace("T", " ") if m.lock_at else "—"}
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    user_name = st.session_state.get("live_user_name", "")
    user_key = st.session_state.get("live_user_key", "")
    
    pred_id = f"{user_key}_{m.match_id}"
    user_pred = next((p for p in live_preds if p.id == pred_id), None) if user_key else None

    # Se o jogo ainda está aberto e o usuário está identificado
    tab_palpites, tab_mural = st.tabs(["📊 Palpites", "💬 Mural"])
    
    with tab_palpites:
        # Se o jogo ainda está aberto e o usuário está identificado
        if is_open:
            st.info("🟢 O jogo está aberto para palpites! Faça o seu palpite em Jogos de Hoje.")
            if user_pred:
                st.success(f"Seu palpite atual: **{user_pred.predicted_home_goals} x {user_pred.predicted_away_goals}**")
            else:
                st.warning("Você ainda não salvou palpite para esta partida. Vá em Jogos de Hoje para palpitar!")

        # Controle de privacidade e exibição de dados
        st.markdown("---")
        
        match_preds = [p for p in live_preds if p.match_id == m.match_id]
        total_preds = len(match_preds)
        
        if is_open:
            st.info("🔒 Os palpites individuais e a simulação do impacto no ranking dos outros participantes estão ocultos até o fechamento do jogo.")
            if total_preds > 0:
                st.metric("Total de palpites enviados no grupo", total_preds)
                
            show_termometro_before_lock = config.get("show_termometro_before_lock", False)
            if show_termometro_before_lock and total_preds > 0:
                st.markdown("### 📊 Termômetro do Grupo (Parcial)")
                home_wins = 0
                away_wins = 0
                draws = 0
                score_counts = {}
                for lp in match_preds:
                    h = lp.predicted_home_goals
                    a = lp.predicted_away_goals
                    if h > a:
                        home_wins += 1
                    elif h < a:
                        away_wins += 1
                    else:
                        draws += 1
                    score_str = f"{h} x {a}"
                    score_counts[score_str] = score_counts.get(score_str, 0) + 1
                    
                pct_home = (home_wins / total_preds) * 100
                pct_draw = (draws / total_preds) * 100
                pct_away = (away_wins / total_preds) * 100
                
                st.markdown(
                    f"""
                    <div style="margin: 15px 0;">
                        <div style="display:flex; justify-content:space-between; font-weight:bold; color:var(--ink); font-size:14px; margin-bottom:5px;">
                            <span>Vitória {m.home_team}: {pct_home:.0f}%</span>
                            <span>Empate: {pct_draw:.0f}%</span>
                            <span>Vitória {m.away_team}: {pct_away:.0f}%</span>
                        </div>
                        <div style="display:flex; width: 100%; height: 16px; border-radius: 99px; overflow:hidden;">
                            <div style="width: {pct_home}%; background-color: #176B4D; height: 100%;"></div>
                            <div style="width: {pct_draw}%; background-color: #66736D; height: 100%;"></div>
                            <div style="width: {pct_away}%; background-color: #D8A94A; height: 100%;"></div>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
                
            if user_pred:
                st.markdown("---")
                st.markdown("#### 📱 Compartilhar seu Palpite no WhatsApp")
                share_txt = build_live_match_share_text(user_name, m, user_pred.predicted_home_goals, user_pred.predicted_away_goals, user_pred.id[:8])
                st.code(share_txt, language="text")
        else:
            reveal_allowed = config.get("reveal_live_predictions_after_lock", True) or m.status == "result_approved"
            if not reveal_allowed:
                st.info("🔒 A visualização dos palpites dos outros participantes está desativada conforme as regras de privacidade do bolão.")
            else:
                st.markdown("### 📊 Termômetro do Grupo")
                if total_preds == 0:
                    st.info("Ninguém no grupo enviou palpites para esta partida.")
                else:
                    home_wins = 0
                    away_wins = 0
                    draws = 0
                    score_counts = {}
                    for lp in match_preds:
                        h = lp.predicted_home_goals
                        a = lp.predicted_away_goals
                        if h > a:
                            home_wins += 1
                        elif h < a:
                            away_wins += 1
                        else:
                            draws += 1
                        score_str = f"{h} x {a}"
                        score_counts[score_str] = score_counts.get(score_str, 0) + 1
                    
                    pct_home = (home_wins / total_preds) * 100
                    pct_draw = (draws / total_preds) * 100
                    pct_away = (away_wins / total_preds) * 100
                    sorted_scores = sorted(score_counts.items(), key=lambda x: x[1], reverse=True)
                    top_score, top_score_votes = sorted_scores[0]
                    pct_top_score = (top_score_votes / total_preds) * 100
                    
                    st.markdown(
                        f"""
                        <div style="margin: 15px 0;">
                            <div style="display:flex; justify-content:space-between; font-weight:bold; color:var(--ink); font-size:14px; margin-bottom:5px;">
                                <span>Vitória {m.home_team}: {pct_home:.0f}%</span>
                                <span>Empate: {pct_draw:.0f}%</span>
                                <span>Vitória {m.away_team}: {pct_away:.0f}%</span>
                            </div>
                            <div style="display:flex; width: 100%; height: 16px; border-radius: 99px; overflow:hidden;">
                                <div style="width: {pct_home}%; background-color: #176B4D; height: 100%;"></div>
                                <div style="width: {pct_draw}%; background-color: #66736D; height: 100%;"></div>
                                <div style="width: {pct_away}%; background-color: #D8A94A; height: 100%;"></div>
                            </div>
                            <div style="margin-top: 12px; font-size: 15px; font-weight: bold; color: var(--ink);">
                                🎯 Placar mais apostado pelo grupo: <span style="color: var(--green);">{top_score}</span> (apostado por {pct_top_score:.0f}% do grupo)
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
                    
                    # F09 — Termômetro de Artilheiros no Match Center dos Jogos do Brasil
                    is_brasil_game = "Brasil" in m.home_team or "Brasil" in m.away_team
                    if is_brasil_game:
                        st.markdown("---")
                        st.markdown("#### ⚽ Quem o grupo acha que vai marcar?")
                        from src.bolao.storage import load_brasil_palpites_goleadores, load_brasil_resultados_goleadores
                        g_palpites = load_brasil_palpites_goleadores()
                        g_match = [p for p in g_palpites if p["jogo_id"] == m.match_id]
                        
                        all_voted_scorers = []
                        for gp in g_match:
                            all_voted_scorers.extend(gp.get("goleadores", []))
                            
                        nobody_count = sum(1 for gp in g_match if gp.get("gols_brasil_apostados", 0) == 0)
                        total_voted = len(all_voted_scorers) + nobody_count
                        
                        if total_voted == 0:
                            st.caption("Nenhum goleador apostado pelo grupo ainda.")
                        else:
                            from collections import Counter
                            scorer_counts = Counter(all_voted_scorers)
                            total = sum(scorer_counts.values()) or 1
                            top_scorers = scorer_counts.most_common(6)
                            
                            for name, cnt in top_scorers:
                                pct = cnt / total
                                st.markdown(f"**{name}**")
                                st.progress(pct, text=f"{cnt} votos ({pct*100:.0f}%)")
                            
                            # Acertos reais se encerrado
                            resultados_g = load_brasil_resultados_goleadores()
                            real_res = resultados_g.get(m.match_id)
                            if real_res and real_res.get("goleadores_reais"):
                                real_scorers = real_res.get("goleadores_reais", [])
                                hit_strs = []
                                for player in set(real_scorers):
                                    hits = [gp["participante_nome"] for gp in g_match if player in gp.get("goleadores", [])]
                                    if hits:
                                        hit_strs.append(f"🟢 **Acertaram {player}:** {', '.join(hits)}")
                                if hit_strs:
                                    st.markdown("<br>".join(hit_strs), unsafe_allow_html=True)
                    
                    # Impacto no Ranking (Simulação rápida)
                    st.markdown("---")
                    st.markdown("### ⚡ Impacto no Ranking")
                    st.caption("Como ficará a liderança do ranking Jogo a Jogo com base no resultado da partida?")
                    
                    def simulate_outcome(sim_home: int, sim_away: int) -> dict:
                        sim_match = LiveMatch.from_dict(m.to_dict())
                        sim_match.status = "result_approved"
                        sim_match.official_home_goals = sim_home
                        sim_match.official_away_goals = sim_away
                        sim_match.winner = "draw" if sim_home == sim_away else (m.home_team if sim_home > sim_away else m.away_team)
                        
                        sim_matches = [sim_match if x.match_id == m.match_id else x for x in matches]
                        sim_ranking = calculate_live_ranking(live_preds, sim_matches, config)
                        if sim_ranking:
                            leader = sim_ranking[0]["participant"]
                            leader_pts = sim_ranking[0]["total"]
                            return {"leader": leader, "pts": leader_pts}
                        return {"leader": "—", "pts": 0}
                        
                    res_home_win = simulate_outcome(2, 1)
                    res_draw = simulate_outcome(1, 1)
                    res_away_win = simulate_outcome(1, 2)
                    
                    col_sc1, col_sc2, col_sc3 = st.columns(3)
                    with col_sc1:
                        st.markdown(
                            f"""
                            <div class="card" style="text-align: center; border-bottom: 4px solid #176B4D; padding: 15px;">
                                <small style="color: var(--muted); text-transform: uppercase;">Se {m.home_team} vencer</small>
                                <h5 style="margin: 8px 0; color: var(--ink);">{res_home_win['leader']}</h5>
                                <div style="font-weight: bold; color: var(--green); font-size:16px;">Líder com {res_home_win['pts']} pts</div>
                            </div>
                            """,
                            unsafe_allow_html=True
                        )
                    with col_sc2:
                        st.markdown(
                            f"""
                            <div class="card" style="text-align: center; border-bottom: 4px solid #66736D; padding: 15px;">
                                <small style="color: var(--muted); text-transform: uppercase;">Se empatar</small>
                                <h5 style="margin: 8px 0; color: var(--ink);">{res_draw['leader']}</h5>
                                <div style="font-weight: bold; color: var(--green); font-size:16px;">Líder com {res_draw['pts']} pts</div>
                            </div>
                            """,
                            unsafe_allow_html=True
                        )
                    with col_sc3:
                        st.markdown(
                            f"""
                            <div class="card" style="text-align: center; border-bottom: 4px solid #D8A94A; padding: 15px;">
                                <small style="color: var(--muted); text-transform: uppercase;">Se {m.away_team} vencer</small>
                                <h5 style="margin: 8px 0; color: var(--ink);">{res_away_win['leader']}</h5>
                                <div style="font-weight: bold; color: var(--green); font-size:16px;">Líder com {res_away_win['pts']} pts</div>
                            </div>
                            """,
                            unsafe_allow_html=True
                        )
                    
                    # Lista completa de palpites revelados
                    st.markdown("---")
                    st.markdown("#### 👥 Todos os Palpites do Grupo")
                    
                    preds_list = []
                    for lp in match_preds:
                        preds_list.append({
                            "Participante": lp.participant_name,
                            "Palpite": f"{lp.predicted_home_goals} x {lp.predicted_away_goals}",
                            "Envio": lp.submitted_at.replace("T", " ") if lp.submitted_at else "—"
                        })
                    
                    df_preds = pd.DataFrame(preds_list)
                    
                    def render_pred_card(row):
                        st.markdown(
                            f"""
                            <div class="card" style="margin-bottom: 10px; padding: 12px; border-left: 4px solid var(--green);">
                                <div style="display:flex; justify-content:space-between; font-weight:bold;">
                                    <span>{row['Participante']}</span>
                                    <span style="color:var(--green); font-size:16px;">{row['Palpite']}</span>
                                </div>
                                <div style="font-size:12px; color:var(--muted); margin-top:4px;">
                                    Envio: {row['Envio']}
                                </div>
                            </div>
                            """,
                            unsafe_allow_html=True
                        )
                        
                    from .ui_components import render_responsive_table
                    render_responsive_table(df_preds, render_pred_card, key=f"preds_match_{m.match_id}")
                
                # WhatsApp text
                st.markdown("#### 📱 Compartilhar seu Palpite no WhatsApp")
                if user_pred:
                    share_txt = build_live_match_share_text(user_name, m, user_pred.predicted_home_goals, user_pred.predicted_away_goals, user_pred.id[:8])
                    st.code(share_txt, language="text")
                else:
                    st.caption("Você não palpitou neste jogo para gerar mensagem de compartilhamento.")

    with tab_mural:
        st.markdown(f"#### 💬 Mural de Comentários — {m.home_team} x {m.away_team}")
        st.caption("Escreva sua provocação ou opinião sobre o jogo (limite de 140 caracteres).")
        
        from src.bolao.storage import load_comentarios_jogo, save_comentario_jogo, delete_comentario_jogo
        from src.bolao.utils import now_iso, stable_id
        
        comments = load_comentarios_jogo(m.match_id)
        
        for c in comments:
            if c.get("deletado", False):
                continue
            with st.chat_message("user"):
                col_c_text, col_c_del = st.columns([8, 1])
                with col_c_text:
                    ts = c.get("created_at", "")
                    time_str = ts.split("T")[1][:5] if "T" in ts else ts[:5]
                    st.write(f"**{c['participante_nome']}** · <small style='color:var(--muted);'>{time_str}</small>", unsafe_allow_html=True)
                    st.write(c["texto"])
                with col_c_del:
                    is_admin = st.session_state.get("is_admin", False)
                    is_owner = c["participante_nome"] == user_name
                    if is_admin or is_owner:
                        if st.button("🗑️", key=f"del_comm_{c['id']}", help="Excluir comentário"):
                            delete_comentario_jogo(c["id"])
                            st.rerun()
                            
        if not user_name:
            st.caption("Identifique-se na aba de palpites para poder comentar.")
        else:
            novo_comentario = st.chat_input("Escreva um comentário (máx 140 caracteres)...", key=f"new_comment_{m.match_id}")
            if novo_comentario:
                if len(novo_comentario) > 140:
                    st.error("Comentário muito longo (máx 140 caracteres)")
                else:
                    save_comentario_jogo({
                        "id": stable_id(),
                        "jogo_id": m.match_id,
                        "participante_nome": user_name,
                        "texto": novo_comentario,
                        "deletado": False,
                        "created_at": now_iso()
                    })
                    st.rerun()

def render_jogos_do_brasil() -> None:
    st.markdown("### 🇧🇷 Jogos do Brasil — Módulo Brasil")
    st.caption("Palpites, estatísticas e acompanhamento exclusivo dos jogos da Seleção Brasileira.")

    config = load_config()
    
    if "live_user_name" not in st.session_state:
        st.session_state["live_user_name"] = ""
        st.session_state["live_user_key"] = ""

    user_name = st.session_state.get("live_user_name", "")
    
    if not user_name:
        st.markdown("#### 👤 Identifique-se para palpitar nos jogos do Brasil")
        with st.form("live_user_identification_brasil"):
            input_name = st.text_input("Seu Nome no Bolão", placeholder="Ex: César")
            input_code = st.text_input("Código de Confirmação Clássico (Opcional)", placeholder="Ex: a10ce10e6a14")
            
            submitted = st.form_submit_button("Entrar", width="stretch")
            if submitted:
                if not input_name.strip():
                    st.error("Por favor, digite seu nome.")
                else:
                    name_clean = input_name.strip()
                    pkey = normalize_participant_key(name_clean)
                    
                    classic_subs = load_submissions()
                    existing_classic = [s for s in classic_subs if s.participant.strip().lower() == name_clean.lower()]
                    
                    if existing_classic:
                        classic_pred = existing_classic[0]
                        if input_code.strip() and input_code.strip() != classic_pred.submission_id:
                            st.error("Código de confirmação clássico inválido.")
                            return
                            
                    st.session_state["live_user_name"] = name_clean
                    st.session_state["live_user_key"] = pkey
                    st.session_state["live_confirmation_code"] = existing_classic[0].submission_id if existing_classic else None
                    st.success(f"Bem-vindo(a), {name_clean}!")
                    st.rerun()
        return

    user_key = st.session_state["live_user_key"]
    user_name = st.session_state["live_user_name"]
    conf_code = st.session_state.get("live_confirmation_code")

    st.markdown(
        f"""
        <div style="padding: 12px 16px; border-radius: 12px; background-color: var(--panel); border: 1px solid var(--line); margin-bottom: 20px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px; color: var(--ink);">
            <div>
                👤 Participante: <b>{user_name}</b> {f'<span class="badge info">Clássico Vinculado</span>' if conf_code else ''}
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    matches = load_matches()
    live_preds = load_live_predictions()
    br_matches = [m for m in matches if "Brasil" in m.home_team or "Brasil" in m.away_team]

    if not br_matches:
        st.info("Nenhum jogo do Brasil cadastrado na agenda do bolão.")
        return

    br_matches.sort(key=lambda m: (m.starts_at or "", m.sort_order))

    selected_idx = 0
    if "jogo_brasil_selecionado" in st.session_state:
        selected_match_id = st.session_state["jogo_brasil_selecionado"]
        for idx, m in enumerate(br_matches):
            if m.match_id == selected_match_id:
                selected_idx = idx
                break
                
    selected_match = st.selectbox(
        "Selecione a partida do Brasil:",
        options=br_matches,
        index=selected_idx,
        format_func=lambda m: f"{m.home_team} {f'{m.official_home_goals}' if m.official_home_goals is not None else ''} x {f'{m.official_away_goals}' if m.official_away_goals is not None else ''} {m.away_team} — {m.round_label}",
        key="brasil_match_selectbox"
    )
    
    if selected_match:
        st.session_state["jogo_brasil_selecionado"] = selected_match.match_id

    tab_escalar, tab_termometro, tab_nosso_craque, tab_elenco, tab_ranking_canarinho = st.tabs([
        "⚽ Escalar Goleadores",
        "🔥 Termômetro & Secador",
        "⭐ Nosso Craque & Artilheiros",
        "🇧🇷 Jogadores Convocados",
        "🏆 Ranking Canarinho"
    ])

    from .utils import foto_jogador
    from .storage import load_brasil_resultados_goleadores, load_brasil_palpites_classicos, save_brasil_palpite_goleadores, load_brasil_palpites_goleadores
    from .live_scoring import calcular_pontos_goleadores, calculate_live_prediction_points
    from .events import append_event
    from .navigation import navigate_to
    from datetime import datetime, timedelta
    from collections import Counter
    import pandas as pd

    with tab_escalar:
        if selected_match:
            m = selected_match
            now = datetime.now().isoformat()
            is_closed = not is_match_open_for_prediction(m, now)
            
            # Compute countdown
            if is_closed:
                countdown_str = "🔒 FECHADO"
            else:
                starts_dt = datetime.fromisoformat(m.starts_at)
                lock_mins = int(config.get("live_lock_minutes_before_match", 10))
                countdown_str = render_countdown(starts_dt, lock_mins)
                if countdown_str == "🔒 FECHADO":
                    is_closed = True

            pred_id = f"{user_key}_{m.match_id}"
            pred = next((p for p in live_preds if p.id == pred_id), None)
            
            default_h = pred.predicted_home_goals if pred else 0
            default_a = pred.predicted_away_goals if pred else 0

            from .simulator_engine import name_to_id
            h_id = name_to_id(m.home_team)
            a_id = name_to_id(m.away_team)
            h_badge = get_team_badge_path(h_id) if h_id else None
            a_badge = get_team_badge_path(a_id) if a_id else None

            # Render Match Card
            with st.container(border=True):
                st.markdown(
                    f"""
                    <div style="display: flex; justify-content: space-between; font-size: 13px; color: var(--muted); font-weight: bold; margin-bottom: 15px; border-bottom: 1px solid var(--line); padding-bottom: 8px;">
                        <span>🏆 {m.round_label} {f'· Grupo {m.group}' if m.group else ''}</span>
                        <span style="color: {'var(--red)' if is_closed else 'var(--green)'}; font-weight: bold;">{'🔒 FECHADO' if is_closed else countdown_str}</span>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
                
                # Venue/Stadium and local time
                if getattr(m, "stadium", None):
                    from .constants import VENUES_COPA_2026
                    venue = VENUES_COPA_2026.get(m.stadium)
                    if venue:
                        st.markdown(
                            f"""
                            <div style="font-size: 12px; color: var(--muted); margin-bottom: 12px; margin-top: -8px;">
                                🏟️ {venue['pais']} {m.stadium} · {venue['cidade']} · {datetime.fromisoformat(m.starts_at).strftime('%H:%M')} local ({venue['fuso']})
                            </div>
                            """,
                            unsafe_allow_html=True
                        )
                    else:
                        st.markdown(
                            f"""
                            <div style="font-size: 12px; color: var(--muted); margin-bottom: 12px; margin-top: -8px;">
                                🏟️ {m.stadium}
                            </div>
                            """,
                            unsafe_allow_html=True
                        )

                # Team Flags and Input goals
                c_team1, c_vs_inputs, c_team2, c_btn = st.columns([3, 4, 3, 2])
                with c_team1:
                    st.markdown("<div style='text-align: center;'>", unsafe_allow_html=True)
                    if h_badge: st.image(h_badge, width=32)
                    st.markdown(f"<div style='font-weight: 700; margin-top: 4px; color: var(--ink);'>{m.home_team}</div>", unsafe_allow_html=True)
                    st.markdown("</div>", unsafe_allow_html=True)
                    
                with c_vs_inputs:
                    sub_i1, sub_vs, sub_i2 = st.columns([2, 1, 2])
                    with sub_i1:
                        val_h = st.number_input(f"{m.home_team} gols", min_value=0, max_value=20, value=default_h, step=1, key=f"live_br_h_{m.match_id}", label_visibility="collapsed", disabled=is_closed)
                    with sub_vs:
                        st.markdown("<div style='text-align: center; font-size: 18px; font-weight: bold; line-height: 44px; color: var(--muted);'>x</div>", unsafe_allow_html=True)
                    with sub_i2:
                        val_a = st.number_input(f"{m.away_team} gols", min_value=0, max_value=20, value=default_a, step=1, key=f"live_br_a_{m.match_id}", label_visibility="collapsed", disabled=is_closed)
                        
                with c_team2:
                    st.markdown("<div style='text-align: center;'>", unsafe_allow_html=True)
                    if a_badge: st.image(a_badge, width=32)
                    st.markdown(f"<div style='font-weight: 700; margin-top: 4px; color: var(--ink);'>{m.away_team}</div>", unsafe_allow_html=True)
                    st.markdown("</div>", unsafe_allow_html=True)

                # Reminders
                if not is_closed:
                    st.markdown("<div style='margin-top: 10px;'></div>", unsafe_allow_html=True)
                    col_rem1, col_rem2 = st.columns(2)
                    with col_rem1:
                        import urllib.parse
                        dt_starts = datetime.fromisoformat(m.starts_at)
                        starts_str = dt_starts.strftime("%H:%M")
                        texto_wa = (f"⏰ *Bolão da Cabine do Glória*\n"
                                    f"Não esquece de palpitar em *{m.home_team} x {m.away_team}*!\n"
                                    f"Fecha às {starts_str} (10min antes do apito)\n"
                                    f"👉 https://bolaodogloria.streamlit.app/")
                        wa_link = f"https://wa.me/?text={urllib.parse.quote(texto_wa)}"
                        st.link_button("📲 Lembrar no WhatsApp", wa_link, key=f"btn_wa_br_{m.match_id}", width="stretch")
                    with col_rem2:
                        dt_lembrete = dt_starts - timedelta(minutes=30)
                        dt_fim = dt_lembrete + timedelta(hours=1)
                        fmt = "%Y%m%dT%H%M%SZ"
                        params = urllib.parse.urlencode({
                            "action": "TEMPLATE",
                            "text": f"⚽ Palpitar: {m.home_team} x {m.away_team} — Bolão do Glória",
                            "dates": f"{dt_lembrete.strftime(fmt)}/{dt_fim.strftime(fmt)}",
                            "details": "Lembrete automático do Bolão da Cabine do Glória.",
                        })
                        gcal_link = f"https://calendar.google.com/calendar/render?{params}"
                        st.link_button("📅 Adicionar ao Google Agenda", gcal_link, key=f"btn_gcal_br_{m.match_id}", width="stretch")

                # Interactive Grid to Select Scorers
                gols_bra = val_h if m.home_team == "Brasil" else val_a
                has_assistant_no_scorer = False
                
                if gols_bra > 0:
                    st.markdown("---")
                    st.markdown("##### 🇧🇷 Escalar Goleadores e Assistentes do Brasil")
                    
                    if f"goleadores_br_{m.match_id}" not in st.session_state:
                        palpites_g = load_brasil_palpites_goleadores()
                        user_palpite = next((p for p in palpites_g if p["participante_nome"] == user_name and p["jogo_id"] == m.match_id), None)
                        if user_palpite:
                            st.session_state[f"goleadores_br_{m.match_id}"] = user_palpite.get("goleadores", [])
                            st.session_state[f"assistentes_br_{m.match_id}"] = user_palpite.get("assistentes", [])
                        else:
                            st.session_state[f"goleadores_br_{m.match_id}"] = []
                            st.session_state[f"assistentes_br_{m.match_id}"] = []
                    
                    # Force adjustment of grid lists
                    if len(st.session_state[f"goleadores_br_{m.match_id}"]) > gols_bra:
                        st.session_state[f"goleadores_br_{m.match_id}"] = st.session_state[f"goleadores_br_{m.match_id}"][:gols_bra]
                        st.warning("⚠️ O número de goleadores foi ajustado para corresponder ao placar de gols do Brasil.")
                    if len(st.session_state[f"assistentes_br_{m.match_id}"]) > gols_bra:
                        st.session_state[f"assistentes_br_{m.match_id}"] = st.session_state[f"assistentes_br_{m.match_id}"][:gols_bra]
                        
                    if f"active_filter_br_{m.match_id}" not in st.session_state:
                        st.session_state[f"active_filter_br_{m.match_id}"] = "Todos"
                        
                    cols_filt = st.columns(5)
                    positions_list = ["Todos", "GOL", "DEF", "MEI", "ATA"]
                    emojis_pos = {"Todos": "🌍", "GOL": "🧤", "DEF": "🛡️", "MEI": "⚙️", "ATA": "⚡"}
                    
                    for c_idx, pos in enumerate(positions_list):
                        with cols_filt[c_idx]:
                            if st.button(f"{emojis_pos[pos]} {pos}", key=f"btn_filt_br_{pos}_{m.match_id}", type="primary" if st.session_state[f"active_filter_br_{m.match_id}"] == pos else "secondary", width="stretch"):
                                st.session_state[f"active_filter_br_{m.match_id}"] = pos
                                st.rerun()
                                
                    from .constants import ELENCO_BRASIL_2026
                    suspended_players = config.get("suspended_players", [])
                    p_filtered = [p for p in ELENCO_BRASIL_2026 if st.session_state[f"active_filter_br_{m.match_id}"] == "Todos" or p["posicao"] == st.session_state[f"active_filter_br_{m.match_id}"]]
                    
                    st.write(f"Escalados: **{len(st.session_state[f'goleadores_br_{m.match_id}'])} / {gols_bra}** Goleadores · **{len(st.session_state[f'assistentes_br_{m.match_id}'])} / {gols_bra}** Assistentes")
                    
                    p_cols = st.columns(4)
                    for p_idx, p in enumerate(p_filtered):
                        p_col = p_cols[p_idx % 4]
                        with p_col:
                            is_suspended = p["nome"] in suspended_players
                            g_count = st.session_state[f"goleadores_br_{m.match_id}"].count(p["nome"])
                            a_count = st.session_state[f"assistentes_br_{m.match_id}"].count(p["nome"])
                            
                            p_avatar = foto_jogador(p["camisa"], p["nome"])
                            
                            border_color = "var(--green)" if (g_count > 0 or a_count > 0) else "var(--line)"
                            bg_color = "var(--panel)" if not is_suspended else "var(--bg-soft)"
                            opacity = "1.0" if not is_suspended else "0.5"
                            
                            badge_g = f"<span class='badge success'>⚽ ×{g_count}</span>" if g_count > 0 else ""
                            badge_a = f"<span class='badge info'>🅰️ ×{a_count}</span>" if a_count > 0 else ""
                            
                            st.markdown(
                                f"""
                                <div style="border: 2px solid {border_color}; border-radius: 12px; padding: 8px; text-align: center; background-color: {bg_color}; opacity: {opacity}; position: relative; margin-bottom: 10px;">
                                    <span style="position: absolute; top: 4px; right: 4px; background-color: var(--gold); color: black; font-weight: bold; font-size: 10px; padding: 2px 5px; border-radius: 4px;">#{p['camisa']}</span>
                                    <img src="{p_avatar}" style="width: 44px; height: 44px; border-radius: 50%; margin-bottom: 4px;" />
                                    <div style="font-weight: bold; font-size: 11px; color: var(--ink); white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">{p['nome']}</div>
                                    <div style="font-size: 9px; color: var(--muted);">{p['posicao']}</div>
                                    <div style="margin-top: 4px; font-size:10px;">{badge_g} {badge_a}</div>
                                </div>
                                """,
                                unsafe_allow_html=True
                            )
                            
                            if not is_suspended and not is_closed:
                                c_actions = st.columns(2)
                                with c_actions[0]:
                                    dis_g = len(st.session_state[f"goleadores_br_{m.match_id}"]) >= gols_bra
                                    if st.button("⚽ +", key=f"btn_g_add_br_{p['nome']}_{m.match_id}", disabled=dis_g, width="stretch"):
                                        st.session_state[f"goleadores_br_{m.match_id}"].append(p["nome"])
                                        st.rerun()
                                with c_actions[1]:
                                    dis_a = len(st.session_state[f"assistentes_br_{m.match_id}"]) >= gols_bra
                                    if st.button("🅰️ +", key=f"btn_a_add_br_{p['nome']}_{m.match_id}", disabled=dis_a, width="stretch"):
                                        st.session_state[f"assistentes_br_{m.match_id}"].append(p["nome"])
                                        st.rerun()
                                        
                                if g_count > 0 or a_count > 0:
                                    if st.button("Limpar", key=f"btn_clear_br_{p['nome']}_{m.match_id}", width="stretch"):
                                        st.session_state[f"goleadores_br_{m.match_id}"] = [x for x in st.session_state[f"goleadores_br_{m.match_id}"] if x != p["nome"]]
                                        st.session_state[f"assistentes_br_{m.match_id}"] = [x for x in st.session_state[f"assistentes_br_{m.match_id}"] if x != p["nome"]]
                                        st.rerun()
                    
                    has_assistant_no_scorer = len(st.session_state[f"goleadores_br_{m.match_id}"]) == 0 and len(st.session_state[f"assistentes_br_{m.match_id}"]) > 0

                    # Reserves slots selector (N3)
                    st.markdown("---")
                    st.markdown("##### 🔄 Escalar Reservas para cada Goleador (Opcional)")
                    if f"reservas_br_{m.match_id}" not in st.session_state:
                        palpites_g = load_brasil_palpites_goleadores()
                        user_palpite = next((p for p in palpites_g if p["participante_nome"] == user_name and p["jogo_id"] == m.match_id), None)
                        st.session_state[f"reservas_br_{m.match_id}"] = user_palpite.get("reservas", []) if user_palpite else []
                    
                    reserves_list = st.session_state[f"reservas_br_{m.match_id}"]
                    while len(reserves_list) < gols_bra:
                        reserves_list.append("Nenhum")
                    st.session_state[f"reservas_br_{m.match_id}"] = reserves_list[:gols_bra]
                    
                    for idx_res in range(gols_bra):
                        if idx_res < len(st.session_state[f"goleadores_br_{m.match_id}"]):
                            titular = st.session_state[f"goleadores_br_{m.match_id}"][idx_res]
                            options_res = ["Nenhum"] + [p["nome"] for p in ELENCO_BRASIL_2026 if p["nome"] != titular and p["nome"] not in config.get("suspended_players", [])]
                            default_res = st.session_state[f"reservas_br_{m.match_id}"][idx_res]
                            if default_res not in options_res:
                                default_res = "Nenhum"
                            res_idx = options_res.index(default_res)
                            val_res = st.selectbox(
                                f"Reserva para #{idx_res+1} ({titular}):",
                                options=options_res,
                                index=res_idx,
                                key=f"res_sel_br_{m.match_id}_{idx_res}",
                                disabled=is_closed
                            )
                            st.session_state[f"reservas_br_{m.match_id}"][idx_res] = val_res

                    st.markdown("---")
                    st.markdown(
                        f"""
                        <div style="background-color: var(--panel-strong); padding: 12px; border-radius: 8px; border: 1px solid var(--line);">
                            ⚡ <b>RESUMO DO SEU PALPITE BRASIL</b>
                            <br>Gols apostados: {gols_bra}
                            <br>Goleadores: {", ".join(st.session_state[f"goleadores_br_{m.match_id}"]) if st.session_state[f"goleadores_br_{m.match_id}"] else "Nenhum selecionado"}
                            <br>Reservas: {", ".join(st.session_state[f"reservas_br_{m.match_id}"]) if st.session_state[f"reservas_br_{m.match_id}"] else "Nenhum selecionado"}
                            <br>Assistentes: {", ".join(st.session_state[f"assistentes_br_{m.match_id}"]) if st.session_state[f"assistentes_br_{m.match_id}"] else "Nenhum selecionado"}
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
                    
                    if has_assistant_no_scorer:
                        st.warning("⚠️ Você selecionou assistentes, mas nenhum goleador do Brasil. Adicione pelo menos um goleador.")

                with c_btn:
                    st.markdown("<div style='height: 4px;'></div>", unsafe_allow_html=True)
                    can_save = (not is_closed)
                    if gols_bra > 0:
                        can_save = can_save and (len(st.session_state[f"goleadores_br_{m.match_id}"]) == gols_bra) and (not has_assistant_no_scorer)
                        
                    if st.button("💾 Salvar", key=f"save_btn_br_{m.match_id}", type="primary", width="stretch", disabled=not can_save):
                        from .storage import upsert_live_prediction
                        upsert_live_prediction(
                            participant_name=user_name,
                            match_id=m.match_id,
                            home_goals=int(val_h),
                            away_goals=int(val_a),
                            confirmation_code=conf_code
                        )
                        if gols_bra > 0:
                            save_brasil_palpite_goleadores({
                                "participante_nome": user_name,
                                "jogo_id": m.match_id,
                                "gols_brasil_apostados": gols_bra,
                                "goleadores": st.session_state[f"goleadores_br_{m.match_id}"],
                                "assistentes": st.session_state[f"assistentes_br_{m.match_id}"],
                                "reservas": st.session_state.get(f"reservas_br_{m.match_id}", []),
                                "pontos_ganhos": None
                            })
                        from .events import append_event
                        append_event("live_guess_saved", f"Palpite de {user_name} para {m.home_team} x {m.away_team} salvo.")
                        st.toast("Palpite salvo com sucesso!")
                        st.rerun()
                        
                    if pred and getattr(pred, "contador_edicoes", 0) > 0 and not is_closed:
                        ts = pred.updated_at
                        time_str = ts.replace("T", " ")[:16] if ts else "—"
                        st.markdown(f"<div style='font-size: 11px; color: var(--muted); margin-top: 8px;'>✏️ Editado <b>{pred.contador_edicoes}x</b> · última vez: {time_str}</div>", unsafe_allow_html=True)

                if is_closed:
                    st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)
                    c_link1, c_link2 = st.columns(2)
                    with c_link1:
                        if st.button(f"📊 Ver Termômetro/Palpites: {m.home_team} x {m.away_team}", key=f"btn_lnk_br_mc_{m.match_id}", width="stretch"):
                            st.session_state["match_center_selected_match_id"] = m.match_id
                            from .navigation import navigate_to
                            navigate_to("Match Center")
                    with c_link2:
                        if st.button(f"💬 Mural de Comentários: {m.home_team} x {m.away_team}", key=f"btn_lnk_br_mural_{m.match_id}", width="stretch"):
                            st.session_state["match_center_selected_match_id"] = m.match_id
                            from .navigation import navigate_to
                            navigate_to("Match Center")

    with tab_termometro:
        if selected_match:
            m = selected_match
            st.markdown(f"#### ⚽ Quem o grupo acha que vai marcar em {m.home_team} x {m.away_team}?")
            palpites_g = load_brasil_palpites_goleadores()
            g_match = [p for p in palpites_g if p["jogo_id"] == m.match_id]
            
            all_voted_scorers = []
            for gp in g_match:
                all_voted_scorers.extend(gp.get("goleadores", []))
                
            nobody_count = sum(1 for gp in g_match if gp.get("gols_brasil_apostados", 0) == 0)
            total_voted = len(all_voted_scorers) + nobody_count
            
            if total_voted == 0:
                st.info("Nenhum goleador apostado pelo grupo para esta partida ainda.")
            else:
                from collections import Counter
                scorer_counts = Counter(all_voted_scorers)
                total = sum(scorer_counts.values()) or 1
                top_scorers = scorer_counts.most_common(6)
                
                for name, cnt in top_scorers:
                    pct = cnt / total
                    st.markdown(f"**{name}**")
                    st.progress(pct, text=f"{cnt} votos ({pct*100:.0f}%)")
                    
                # Who got it right:
                resultados_g = load_brasil_resultados_goleadores()
                real_res = resultados_g.get(m.match_id)
                if real_res and real_res.get("goleadores_reais"):
                    real_scorers = real_res.get("goleadores_reais", [])
                    hit_strs = []
                    for player in set(real_scorers):
                        hits = [gp["participante_nome"] for gp in g_match if player in gp.get("goleadores", [])]
                        if hits:
                            hit_strs.append(f"🟢 **Acertaram {player}:** {', '.join(hits)}")
                    if hit_strs:
                        st.markdown("<br>".join(hit_strs), unsafe_allow_html=True)

    with tab_nosso_craque:
        st.markdown("### ⭐ Nosso Craque — a aposta do bolão")
        classic_br = load_brasil_palpites_classicos()
        
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Artilheiro do Brasil mais apostado:**")
            votos_brasil = Counter(p.get("artilheiro_brasil_copa") for p in classic_br if p.get("artilheiro_brasil_copa"))
            total = sum(votos_brasil.values()) or 1
            if votos_brasil:
                for jogador, qtd in votos_brasil.most_common(5):
                    st.progress(qtd / total, text=f"{jogador} — {qtd} votos ({qtd/total*100:.0f}%)")
            else:
                st.caption("Nenhum palpite para artilheiro do Brasil ainda.")

        with col2:
            st.markdown("**Artilheiro Geral mais apostado:**")
            votos_geral = Counter(p.get("artilheiro_geral_copa") for p in classic_br if p.get("artilheiro_geral_copa"))
            total = sum(votos_geral.values()) or 1
            if votos_geral:
                for jogador, qtd in votos_geral.most_common(5):
                    st.progress(qtd / total, text=f"{jogador} — {qtd} votos ({qtd/total*100:.0f}%)")
            else:
                st.caption("Nenhum palpite para artilheiro geral ainda.")

    with tab_elenco:
        st.markdown("#### 🇧🇷 Elenco Oficial da Seleção Brasileira — Copa 2026")
        st.caption("Selecione o jogador para ver fotos, clube e estatísticas em tempo real.")
        
        from .constants import ELENCO_BRASIL_2026
        
        classic_br = load_brasil_palpites_classicos()
        resultados_g = load_brasil_resultados_goleadores()
        suspended_players = config.get("suspended_players", [])
        
        if "elenco_filter" not in st.session_state:
            st.session_state["elenco_filter"] = "Todos"
            
        cols_e_filt = st.columns(5)
        positions_list = ["Todos", "GOL", "DEF", "MEI", "ATA"]
        for c_idx, pos in enumerate(positions_list):
            with cols_e_filt[c_idx]:
                if st.button(f"{pos}", key=f"btn_e_filt_{pos}", type="primary" if st.session_state["elenco_filter"] == pos else "secondary", width="stretch"):
                    st.session_state["elenco_filter"] = pos
                    st.rerun()
                    
        elenco_filtrado = [p for p in ELENCO_BRASIL_2026 if st.session_state["elenco_filter"] == "Todos" or p["posicao"] == st.session_state["elenco_filter"]]
        
        e_cols = st.columns(2)
        for idx, p in enumerate(elenco_filtrado):
            col = e_cols[idx % 2]
            with col:
                is_susp = p["nome"] in suspended_players
                status_suffix = " ❌ Suspenso" if is_susp else ""
                with st.expander(f"#{p['camisa']} {p['nome']} — {p['posicao']}{status_suffix}"):
                    c1, c2 = st.columns([1, 2])
                    with c1:
                        st.image(foto_jogador(p["camisa"], p["nome"]), width=80)
                    with c2:
                        st.markdown(f"**Clube:** {p.get('clube', '—')}")
                        gols_copa = sum(res.get("goleadores_reais", []).count(p["nome"]) for res in resultados_g.values())
                        st.markdown(f"**Gols na Copa:** {gols_copa}")
                        
                        votos_art = sum(1 for pc in classic_br if pc.get("artilheiro_brasil_copa") == p["nome"])
                        total_pc = len(classic_br) or 1
                        pct_art = (votos_art / total_pc) * 100
                        st.markdown(f"**% Aposta Artilheiro:** {pct_art:.0f}%")

    with tab_ranking_canarinho:
        st.markdown("#### 🏆 Ranking Canarinho")
        st.caption("Classificação baseada apenas nas partidas da Seleção Brasileira (Placar + Goleadores + Assistências).")
        
        def calculate_ranking_canarinho_local(live_predictions: list, matches: list, config: dict) -> list[dict]:
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
                            config,
                            reservas_palpitadas=gp.get("reservas", [])
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
            
        canarinho_ranking = calculate_ranking_canarinho_local(live_preds, matches, config)
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
            
            from .ui_components import render_responsive_table
            render_responsive_table(pd.DataFrame(can_rows), render_canarinho_card, "canarinho_ranking_table_local")
