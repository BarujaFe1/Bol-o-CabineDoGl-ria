from __future__ import annotations

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from typing import Any
from .models import LivePrediction, Prediction
from .storage import load_matches, load_live_predictions, save_live_predictions, load_config, append_event, load_submissions, load_official
from .utils import normalize_participant_key, now_iso
from .live_scoring import calculate_live_prediction_points, calculate_live_ranking
from .ui_simulator import get_team_badge_path
from .social import build_live_match_share_text
from .ui_components import render_badge

def is_match_open_for_prediction(match: Any, now: str | None = None) -> bool:
    """
    Retorna True se agora < lock_at.
    """
    if not match.starts_at:
        return False
    
    if match.match_id == "13379":
        lock_at_str = "2026-06-11T23:59:00"
    elif not match.lock_at:
        try:
            dt = datetime.fromisoformat(match.starts_at)
            lock_dt = dt - timedelta(minutes=10)
            lock_at_str = lock_dt.isoformat()
        except Exception:
            return False
    else:
        lock_at_str = match.lock_at
        
    if now is None:
        now = datetime.now().isoformat()
    return now < lock_at_str

def render_jogos_de_hoje() -> None:
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

    matches.sort(key=lambda m: (m.starts_at or "", m.sort_order))

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
            for m in open_matches:
                pred_id = f"{user_key}_{m.match_id}"
                pred = next((p for p in live_preds if p.id == pred_id), None)
                
                # Calcular tempo restante
                try:
                    dt = datetime.fromisoformat(m.starts_at)
                    diff = dt - datetime.now()
                    if diff.total_seconds() > 0:
                        hours = int(diff.total_seconds() // 3600)
                        minutes = int((diff.total_seconds() % 3600) // 60)
                        countdown_str = f"Faltam {hours}h {minutes}min"
                    else:
                        countdown_str = "Fechando..."
                except Exception:
                    countdown_str = "Em breve"

                st.markdown(
                    f"""
                    <div style="border: 1px solid var(--line); padding: 15px; border-radius: 16px; background-color: var(--panel); margin-bottom: 15px;">
                        <div style="display: flex; justify-content: space-between; font-size: 12px; color: var(--muted); font-weight: bold; margin-bottom: 10px;">
                            <span>{m.round_label} {f'· Grupo {m.group}' if m.group else ''}</span>
                            <span style="color: var(--green);">🟢 Aberto ({countdown_str})</span>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
                
                col_teams1, col_inputs, col_btn = st.columns([5, 4, 3])
                
                with col_teams1:
                    from .simulator_engine import name_to_id
                    h_id = name_to_id(m.home_team)
                    a_id = name_to_id(m.away_team)
                    h_badge = get_team_badge_path(h_id) if h_id else None
                    a_badge = get_team_badge_path(a_id) if a_id else None
                    
                    sub1, sub2 = st.columns(2)
                    with sub1:
                        if h_badge: st.image(h_badge, width=28)
                        st.markdown(f"**{m.home_team}**")
                    with sub2:
                        if a_badge: st.image(a_badge, width=28)
                        st.markdown(f"**{m.away_team}**")

                with col_inputs:
                    default_h = pred.predicted_home_goals if pred else 0
                    default_a = pred.predicted_away_goals if pred else 0
                    
                    sub_i1, sub_vs, sub_i2 = st.columns([2, 1, 2])
                    with sub_i1:
                        val_h = st.number_input(f"{m.home_team} gols", min_value=0, max_value=20, value=default_h, step=1, key=f"live_h_{m.match_id}", label_visibility="collapsed")
                    with sub_vs:
                        st.markdown("<div style='text-align: center; line-height: 40px; color: var(--ink);'>x</div>", unsafe_allow_html=True)
                    with sub_i2:
                        val_a = st.number_input(f"{m.away_team} gols", min_value=0, max_value=20, value=default_a, step=1, key=f"live_a_{m.match_id}", label_visibility="collapsed")

                with col_btn:
                    if st.button("Salvar Palpite", key=f"save_btn_{m.match_id}", type="primary", width="stretch"):
                        if pred:
                            pred.predicted_home_goals = int(val_h)
                            pred.predicted_away_goals = int(val_a)
                            pred.updated_at = now_iso()
                        else:
                            pred = LivePrediction(
                                id=pred_id,
                                participant_name=user_name,
                                participant_key=user_key,
                                match_id=m.match_id,
                                predicted_home_goals=int(val_h),
                                predicted_away_goals=int(val_a),
                                submitted_at=now_iso(),
                                updated_at=now_iso(),
                                confirmation_code=conf_code,
                                locked_at=m.lock_at
                            )
                            live_preds.append(pred)
                            
                        save_live_predictions(live_preds)
                        append_event("live_guess_saved", f"Palpite de {user_name} para {m.home_team} x {m.away_team} salvo.")
                        st.toast("Palpite salvo com sucesso!")
                        st.rerun()

    # 2. Jogos Fechados / Live
    with m_tabs[1]:
        st.markdown("#### Palpites Fechados (Revelados)")
        if not locked_matches:
            st.info("Nenhum jogo bloqueado ou em andamento no momento.")
        else:
            for m in locked_matches:
                pred_id = f"{user_key}_{m.match_id}"
                pred = next((p for p in live_preds if p.id == pred_id), None)
                
                st.markdown(
                    f"""
                    <div style="border: 1px solid var(--line); padding: 15px; border-radius: 16px; background-color: var(--panel); margin-bottom: 15px;">
                        <div style="display: flex; justify-content: space-between; font-size: 12px; color: var(--muted); font-weight: bold; margin-bottom: 10px;">
                            <span>{m.round_label} {f'· Grupo {m.group}' if m.group else ''}</span>
                            <span style="color: var(--red);">🔒 Fechado</span>
                        </div>
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <span style="font-size: 16px; font-weight: bold; color: var(--ink);">{m.home_team} x {m.away_team}</span>
                            <span style="background-color: var(--gold-bg); padding: 4px 8px; border-radius: 8px; font-size: 12px; font-weight: bold; color: var(--gold);">
                                {f'Seu palpite: {pred.predicted_home_goals} x {pred.predicted_away_goals}' if pred else 'Você não palpitou'}
                            </span>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
                
                reveal_enabled = config.get("reveal_live_predictions_after_lock", True)
                if reveal_enabled:
                    with st.expander(f"👁️ Ver palpites e estatísticas de {m.home_team} x {m.away_team}"):
                        if st.button("Abrir Match Center do Jogo", key=f"btn_mc_link_{m.match_id}", width="stretch"):
                            st.session_state["nav_page"] = "Match Center"
                            st.session_state["match_center_selected_match_id"] = m.match_id
                            st.rerun()
                else:
                    st.caption("🔒 Revelação de palpites desativada pela organização.")

    # 3. Resultados Aprovados
    with m_tabs[2]:
        st.markdown("#### Jogos Concluídos")
        if not finished_matches:
            st.info("Nenhum jogo concluído e aprovado na agenda ainda.")
        else:
            for m in finished_matches:
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
                
                st.markdown(
                    f"""
                    <div style="border: 1px solid var(--line); padding: 15px; border-radius: 16px; background-color: var(--panel); margin-bottom: 15px; border-left: 5px solid var(--gold);">
                        <div style="display: flex; justify-content: space-between; font-size: 12px; color: var(--muted); font-weight: bold; margin-bottom: 8px;">
                            <span>{m.round_label} {f'· Grupo {m.group}' if m.group else ''}</span>
                            <span>🏁 Concluído</span>
                        </div>
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                            <span style="font-size: 16px; font-weight: bold; color: var(--ink);">{m.home_team} {m.official_home_goals} x {m.official_away_goals} {m.away_team}</span>
                            {points_badge}
                        </div>
                        <div style="font-size: 13px; color: var(--muted);">
                            ⚽ <b>Seu palpite:</b> {f'{pred.predicted_home_goals} x {pred.predicted_away_goals}' if pred else 'Não palpitou'} 
                            <br>💡 <b>Acertos:</b> {breakdown_text}
                        </div>
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
    matches.sort(key=lambda m: (m.starts_at or "", m.sort_order))
    
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
    if is_open:
        st.info("🔒 Estatísticas do grupo e palpites dos amigos serão revelados assim que o prazo de palpite expirar.")
        if user_pred:
            st.success(f"Seu palpite atual: **{user_pred.predicted_home_goals} x {user_pred.predicted_away_goals}**")
        else:
            st.warning("Você ainda não salvou palpite para esta partida. Vá em Jogos de Hoje para palpitar!")
        return

    # Se o jogo está bloqueado (estatísticas e palpites revelados)
    st.markdown("---")
    st.markdown("### 📊 Termômetro do Grupo")
    
    match_preds = [p for p in live_preds if p.match_id == m.match_id]
    total_preds = len(match_preds)
    
    if total_preds == 0:
        st.info("Ninguém no grupo enviou palpites para esta partida.")
    else:
        # Calcular estatísticas de votos
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
        
        # Placar mais apostado
        sorted_scores = sorted(score_counts.items(), key=lambda x: x[1], reverse=True)
        top_score, top_score_votes = sorted_scores[0]
        pct_top_score = (top_score_votes / total_preds) * 100

        # Render termômetro
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

        # Impacto no Ranking (Simulação rápida)
        st.markdown("---")
        st.markdown("### ⚡ Impacto no Ranking")
        st.caption("Como ficará a liderança do ranking Jogo a Jogo com base no resultado da partida?")

        # Função auxiliar para simular ranking com resultado fictício
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

        res_home_win = simulate_outcome(2, 1) # Simula vitória do mandante
        res_draw = simulate_outcome(1, 1) # Simula empate
        res_away_win = simulate_outcome(1, 2) # Simula vitória do visitante

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
        
        st.dataframe(pd.DataFrame(preds_list), width="stretch", hide_index=True)

        # WhatsApp text
        st.markdown("#### 📱 Compartilhar no WhatsApp")
        if user_pred:
            share_txt = build_live_match_share_text(user_name, m, user_pred.predicted_home_goals, user_pred.predicted_away_goals, user_pred.id[:8])
            st.code(share_txt, language="text")
        else:
            st.caption("Você não palpitou neste jogo para gerar mensagem de compartilhamento.")
