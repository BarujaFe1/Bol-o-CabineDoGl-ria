from __future__ import annotations

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from .models import LivePrediction
from .storage import load_matches, load_live_predictions, save_live_predictions, load_config, append_event, load_submissions
from .utils import normalize_participant_key, now_iso
from .live_scoring import calculate_live_prediction_points
from .ui_simulator import get_team_badge_path

def is_match_open_for_prediction(match, now=None) -> bool:
    """
    Retorna True se agora < lock_at.
    """
    if not match.starts_at:
        return False
    if not match.lock_at:
        # Padrão: 10 minutos antes
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
                    
                    # Verificar se existe submissão clássica com esse nome
                    classic_subs = load_submissions()
                    existing_classic = [s for s in classic_subs if s.participant.strip().lower() == name_clean.lower()]
                    
                    if existing_classic:
                        # Se existe clássico, valida com código de confirmação
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
        <div style="padding: 12px 16px; border-radius: 12px; background-color: #FFFDF8; border: 1px solid rgba(11, 51, 40, 0.12); margin-bottom: 20px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px;">
            <div>
                👤 Participante: <b>{user_name}</b> {f'<span class="badge info">Clássico Vinculado</span>' if conf_code else ''}
            </div>
            <button style="border: none; background: none; color: #B42318; font-weight: bold; cursor: pointer;" onclick="window.location.reload();" 
            id="change_user_btn">Alterar Usuário</button>
        </div>
        """,
        unsafe_allow_html=True
    )
    
    # Simple trick to handle click of Alterar Usuário
    if st.button("🚪 Alterar Usuário/Sair"):
        st.session_state.pop("live_user_name", None)
        st.session_state.pop("live_user_key", None)
        st.session_state.pop("live_confirmation_code", None)
        st.rerun()

    matches = load_matches()
    live_preds = load_live_predictions()

    if not matches:
        st.info("Nenhum jogo cadastrado na agenda do bolão.")
        return

    # Filter games (by status / date)
    # Sort matches by starts_at
    matches.sort(key=lambda m: (m.starts_at or "", m.sort_order))

    # Tabs to separate categories
    m_tabs = st.tabs(["🚀 Jogos Abertos", "🔒 Jogos Fechados & Live", "🏆 Resultados Aprovados"])
    
    now = datetime.now().isoformat()

    # Match groupings
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
                # Find current prediction if any
                pred_id = f"{user_key}_{m.match_id}"
                pred = next((p for p in live_preds if p.id == pred_id), None)
                
                # Render Match Card
                st.markdown(
                    f"""
                    <div style="border: 1px solid rgba(11, 51, 40, 0.12); padding: 15px; border-radius: 16px; background-color: #FFFDF8; margin-bottom: 15px;">
                        <div style="display: flex; justify-content: space-between; font-size: 12px; color: #66736D; font-weight: bold;">
                            <span>{m.round_label} {f'· Grupo {m.group}' if m.group else ''}</span>
                            <span style="color: #176B4D;">🟢 Aberto até {m.lock_at.replace("T", " ") if m.lock_at else "—"}</span>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
                
                col_teams1, col_inputs, col_btn = st.columns([5, 4, 3])
                
                with col_teams1:
                    # Wait, get_team_badge_path expects team ID. Let's find team ID by name:
                    from .simulator_engine import name_to_id
                    h_id = name_to_id(m.home_team)
                    a_id = name_to_id(m.away_team)
                    h_badge = get_team_badge_path(h_id) if h_id else None
                    a_badge = get_team_badge_path(a_id) if a_id else None
                    
                    sub1, sub2 = st.columns(2)
                    with sub1:
                        if h_badge: st.image(h_badge, width=32)
                        st.markdown(f"**{m.home_team}**")
                    with sub2:
                        if a_badge: st.image(a_badge, width=32)
                        st.markdown(f"**{m.away_team}**")

                with col_inputs:
                    default_h = pred.predicted_home_goals if pred else 0
                    default_a = pred.predicted_away_goals if pred else 0
                    
                    sub_i1, sub_vs, sub_i2 = st.columns([2, 1, 2])
                    with sub_i1:
                        val_h = st.number_input(f"{m.home_team} gols", min_value=0, max_value=20, value=default_h, step=1, key=f"live_h_{m.match_id}", label_visibility="collapsed")
                    with sub_vs:
                        st.markdown("<div style='text-align: center; line-height: 40px;'>x</div>", unsafe_allow_html=True)
                    with sub_i2:
                        val_a = st.number_input(f"{m.away_team} gols", min_value=0, max_value=20, value=default_a, step=1, key=f"live_a_{m.match_id}", label_visibility="collapsed")

                with col_btn:
                    if st.button("Salvar Palpite", key=f"save_btn_{m.match_id}", type="primary", width="stretch"):
                        # Save prediction
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
                    <div style="border: 1px solid rgba(11, 51, 40, 0.12); padding: 15px; border-radius: 16px; background-color: #F8F9FA; margin-bottom: 15px;">
                        <div style="display: flex; justify-content: space-between; font-size: 12px; color: #66736D; font-weight: bold; margin-bottom: 10px;">
                            <span>{m.round_label} {f'· Grupo {m.group}' if m.group else ''}</span>
                            <span style="color: #B42318;">🔒 Fechado em {m.lock_at.replace("T", " ") if m.lock_at else "—"}</span>
                        </div>
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <span style="font-size: 16px; font-weight: bold; color: #0B3328;">{m.home_team} x {m.away_team}</span>
                            <span style="background-color: #E6D2B5; padding: 4px 8px; border-radius: 8px; font-size: 12px; font-weight: bold; color: #72541A;">
                                {f'Seu palpite: {pred.predicted_home_goals} x {pred.predicted_away_goals}' if pred else 'Você não palpitou'}
                            </span>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
                
                # Reveal predictions from others
                reveal_enabled = config.get("reveal_live_predictions_after_lock", True)
                if reveal_enabled:
                    with st.expander(f"👁️ Ver palpites do grupo para {m.home_team} x {m.away_team}"):
                        other_preds = [p for p in live_preds if p.match_id == m.match_id and p.participant_key != user_key]
                        if not other_preds:
                            st.caption("Nenhum outro participante palpitou para este jogo.")
                        else:
                            other_data = []
                            for op in other_preds:
                                other_data.append({
                                    "Participante": op.participant_name,
                                    "Palpite": f"{op.predicted_home_goals} x {op.predicted_away_goals}",
                                    "Envio": op.submitted_at.replace("T", " ") if op.submitted_at else "—"
                                })
                            st.dataframe(pd.DataFrame(other_data), width="stretch", hide_index=True)
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
                
                badge_color = "#DFF5E8" if points_gained > 0 else "#FDE7E3"
                text_color = "#0B3328" if points_gained > 0 else "#B42318"
                points_badge = f'<span style="background-color: {badge_color}; color: {text_color}; padding: 4px 10px; border-radius: 99px; font-weight: bold;">+{points_gained} pts</span>'
                
                st.markdown(
                    f"""
                    <div style="border: 1px solid rgba(11, 51, 40, 0.12); padding: 15px; border-radius: 16px; background-color: #FFFDF8; margin-bottom: 15px; border-left: 5px solid #D8A94A;">
                        <div style="display: flex; justify-content: space-between; font-size: 12px; color: #66736D; font-weight: bold; margin-bottom: 8px;">
                            <span>{m.round_label} {f'· Grupo {m.group}' if m.group else ''}</span>
                            <span>🏁 Concluído</span>
                        </div>
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                            <span style="font-size: 16px; font-weight: bold; color: #0B3328;">{m.home_team} {m.official_home_goals} x {m.official_away_goals} {m.away_team}</span>
                            {points_badge}
                        </div>
                        <div style="font-size: 13px; color: #66736D;">
                            ⚽ <b>Seu palpite:</b> {f'{pred.predicted_home_goals} x {pred.predicted_away_goals}' if pred else 'Não palpitou'} 
                            <br>💡 <b>Breakdown:</b> {breakdown_text}
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
