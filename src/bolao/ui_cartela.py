from __future__ import annotations

import streamlit as st
import pandas as pd
from datetime import datetime
from .storage import load_submissions, load_matches, load_live_predictions, load_official, load_config
from .utils import normalize_participant_key, now_iso
from .live_scoring import calculate_live_ranking, calculate_live_prediction_points
from .scoring import rank_predictions
from .ui_simulator import get_team_badge_path
from .ui_live_matches import is_match_open_for_prediction
from .constants import GROUPS, PHASE_LABELS

def render_minha_cartela() -> None:
    if st.button("⬅️ Voltar ao Início", key="back_to_home_cartela"):
        st.session_state["nav_page"] = "Início"
        st.rerun()

    st.markdown("### 📋 Minha Cartela — Visão Geral do Participante")
    st.caption("Acompanhe o status detalhado das suas apostas, pontuação, próximos confrontos e compare seus palpites com os amigos.")

    config = load_config()
    submissions = load_submissions()
    official = load_official()
    matches = load_matches()
    live_preds = load_live_predictions()

    if not submissions and not live_preds:
        st.info("Nenhum palpite enviado ainda no sistema.")
        return

    # Select Participant
    # Build unique list of participant names
    names = sorted(list(set([p.participant for p in submissions] + [p.participant_name for p in live_preds])), key=lambda x: x.lower())
    selected_name = st.selectbox("Escolha seu Nome para Visualizar a Cartela", options=names, key="cartela_name_select")
    
    pkey = normalize_participant_key(selected_name)

    # Find predictions for selected participant
    classic_pred = next((p for p in submissions if normalize_participant_key(p.participant) == pkey), None)
    user_live_preds = [p for p in live_preds if p.participant_key == pkey]

    # Calculate classic points and position if official result is approved
    classic_points = 0
    classic_rank = "—"
    classic_exact = 0
    classic_champ = "—"
    classic_final = "—"
    
    if official and submissions:
        from .scoring import ScoreConfig
        from .constants import DEFAULT_WEIGHTED_RULES, DEFAULT_UNIFORM_RULES, DEFAULT_V2_RULES
        score_config = ScoreConfig(
            mode=config.get("scoring_mode", "v2"),
            weighted_rules=config.get("weighted_rules", dict(DEFAULT_WEIGHTED_RULES)),
            uniform_rules=config.get("uniform_rules", dict(DEFAULT_UNIFORM_RULES)),
            v2_rules=config.get("v2_rules", dict(DEFAULT_V2_RULES)),
        )
        classic_scores = rank_predictions(submissions, official, score_config)
        user_classic_score = next((s for s in classic_scores if normalize_participant_key(s.participant) == pkey), None)
        if user_classic_score:
            classic_points = user_classic_score.total
            classic_rank = f"{user_classic_score.position}º" if hasattr(user_classic_score, 'position') else f"{classic_scores.index(user_classic_score)+1}º"
            classic_exact = user_classic_score.exact_scores

    if classic_pred:
        classic_champ = classic_pred.champion or "Não escolhido"
        finalists = []
        ko_final = classic_pred.knockout.get("final", [])
        if ko_final and len(ko_final) > 0:
            if ko_final[0].a: finalists.append(ko_final[0].a)
            if ko_final[0].b: finalists.append(ko_final[0].b)
        classic_final = " x ".join(finalists) if finalists else "Não definido"

    # Calculate live points and position
    live_points = 0
    live_rank = "—"
    live_exact = 0
    live_rate = "—"
    live_next_match = "Nenhum"
    
    live_scores = calculate_live_ranking(live_preds, matches, config)
    user_live_score = next((s for s in live_scores if s["participant_key"] == pkey), None)
    if user_live_score:
        live_points = user_live_score["total"]
        live_rank = f"{user_live_score['position']}º"
        live_exact = user_live_score["exact_scores"]
        live_rate = f"{int(user_live_score['hit_rate'] * 100)}%"

    # Find next pending game for the user
    now = datetime.now().isoformat()
    open_matches = [m for m in matches if m.status != "result_approved" and m.starts_at and m.starts_at > now]
    open_matches.sort(key=lambda m: m.starts_at)
    
    guessed_match_ids = set(p.match_id for p in user_live_preds)
    pending_matches = [m for m in open_matches if m.match_id not in guessed_match_ids]
    if pending_matches:
        next_m = pending_matches[0]
        live_next_match = f"{next_m.home_team} x {next_m.away_team} (em {next_m.starts_at.replace('T', ' ')})"

    # Render Main Card
    card_html = f"""
<div style="border: 2px solid #D8A94A; border-radius: 24px; padding: 25px; background: linear-gradient(180deg, #ffffff, #FFFDF8); box-shadow: 0 16px 48px rgba(11, 51, 40, 0.08); margin-bottom: 25px;">
<div style="font-size: 40px; text-align: center; margin-bottom: 5px;">⚽</div>
<h3 style="text-align: center; color: #0B3328; margin: 5px 0;">{selected_name}</h3>
<p style="text-align: center; color: #66736D; font-size: 14px;">Chave estável: {pkey}</p>
<div style="display: flex; gap: 20px; justify-content: space-around; margin-top: 20px; flex-wrap: wrap;">
<div style="flex: 1; min-width: 200px; padding: 15px; border-radius: 12px; background-color: #F8F9FA; border: 1px solid rgba(11, 51, 40, 0.08); text-align: center;">
<span style="font-size: 12px; color: #66736D; text-transform: uppercase; letter-spacing: 0.5px;">Modo Clássico</span>
<h2 style="margin: 8px 0; color: #176B4D;">{classic_points} <span style="font-size: 14px; color: #66736D;">pts</span></h2>
<div style="font-size: 13px; color: #66736D;">Rank: <b>{classic_rank}</b> · Campeão: <b>{classic_champ}</b></div>
</div>
<div style="flex: 1; min-width: 200px; padding: 15px; border-radius: 12px; background-color: #F8F9FA; border: 1px solid rgba(11, 51, 40, 0.08); text-align: center;">
<span style="font-size: 12px; color: #66736D; text-transform: uppercase; letter-spacing: 0.5px;">Modo Jogo a Jogo</span>
<h2 style="margin: 8px 0; color: #176B4D;">{live_points} <span style="font-size: 14px; color: #66736D;">pts</span></h2>
<div style="font-size: 13px; color: #66736D;">Rank: <b>{live_rank}</b> · Aprov.: <b>{live_rate}</b></div>
</div>
</div>
</div>
"""
    st.markdown(card_html, unsafe_allow_html=True)

    c_tabs = st.tabs(["📊 Resumo Geral", "🏆 Palpite Clássico", "🎯 Palpites Jogo a Jogo", "💡 Pontuação", "⚖️ Comparar com Amigo"])

    # Tab 1: Resumo
    with c_tabs[0]:
        st.markdown("#### Resumo da sua Participação")
        
        col_res1, col_res2 = st.columns(2)
        with col_res1:
            st.markdown("**Informações do Modo Clássico:**")
            st.write(f"- 🏆 **Campeão Escolhido:** {classic_champ}")
            st.write(f"- ⚔️ **Final Prevista:** {classic_final}")
            st.write(f"- 📊 **Placares Exatos em Grupos:** {classic_exact}")
        
        with col_res2:
            st.markdown("**Informações do Jogo a Jogo:**")
            st.write(f"- 🧩 **Palpites Realizados:** {len(user_live_preds)}")
            st.write(f"- 🎯 **Placares Exatos Jogo a Jogo:** {live_exact}")
            st.write(f"- ⏳ **Próximo Jogo Pendente:** {live_next_match}")

        # WhatsApp share code
        st.markdown("---")
        st.markdown("#### 📱 Compartilhar status no WhatsApp")
        
        share_text = f"🏆 Meu status no Bolão da Copa!\n\n⚽ Clássico: {classic_points} pts ({classic_rank})\n🎯 Jogo a Jogo: {live_points} pts ({live_rank})\n🏆 Meu Campeão: {classic_champ}\n\nEntra e palpita também!"
        st.text_area("Texto copiável para compartilhar", value=share_text, height=120, key="share_txt_cartela", disabled=True)
        
        import urllib.parse
        encoded_text = urllib.parse.quote(share_text)
        st.link_button("💬 Enviar no WhatsApp", f"https://api.whatsapp.com/send?text={encoded_text}", type="primary", width="stretch")

    # Tab 2: Palpite Clássico
    with c_tabs[1]:
        st.markdown("#### Detalhamento do Palpite Clássico")
        if not classic_pred:
            st.warning("Você não possui palpite clássico registrado.")
            if st.button("Criar palpite clássico", width="stretch"):
                st.session_state["nav_page"] = "Fazer palpite"
                st.rerun()
        else:
            st.markdown(f"**Código de confirmação:** `{classic_pred.submission_id}`")
            st.markdown(f"**Enviado em:** `{classic_pred.submitted_at.replace('T', ' ') if classic_pred.submitted_at else '—'}`")
            
            # Show group classification
            st.markdown("##### 👥 Classificados nos Grupos")
            grp_data = []
            for g in GROUPS:
                teams = classic_pred.groups.get(g, [None, None, None, None])
                grp_data.append({
                    "Grupo": f"Grupo {g}",
                    "1º Lugar": teams[0] or "—",
                    "2º Lugar": teams[1] or "—",
                    "3º Lugar": teams[2] or "—",
                    "4º Lugar": teams[3] or "—"
                })
            st.dataframe(pd.DataFrame(grp_data), width="stretch", hide_index=True)

            # Show best thirds
            st.markdown(f"##### 🥉 Melhores terceiros classificados: `{', '.join(classic_pred.best_thirds) if classic_pred.best_thirds else '—'}`")

            # Show knockout path
            st.markdown("##### ⚔️ Chave de Mata-Mata")
            for phase, matches_list in classic_pred.knockout.items():
                with st.expander(PHASE_LABELS.get(phase, phase).capitalize(), expanded=(phase == "final")):
                    phase_rows = []
                    for idx, m in enumerate(matches_list, start=1):
                        phase_rows.append({
                            "Jogo": idx,
                            "Confronto": f"{m.a or '—'} x {m.b or '—'}",
                            "Vencedor Escolhido": m.winner or "—"
                        })
                    st.dataframe(pd.DataFrame(phase_rows), width="stretch", hide_index=True)

            # Button to edit classic prediction
            is_locked = config.get("is_bolao_locked", False)
            if not is_locked:
                st.markdown("---")
                if st.button("✏️ Editar palpite clássico", width="stretch", type="primary"):
                    st.session_state["nav_page"] = "Fazer palpite"
                    st.session_state["public_sim_name"] = selected_name
                    st.session_state["edit_mode"] = "edit"
                    st.rerun()

    # Tab 3: Jogo a Jogo
    with c_tabs[2]:
        st.markdown("#### Detalhamento do Palpite Jogo a Jogo")
        if not user_live_preds:
            st.warning("Você não realizou nenhum palpite no Modo Jogo a Jogo ainda.")
        else:
            live_rows = []
            for p in user_live_preds:
                m = next((m for m in matches if m.match_id == p.match_id), None)
                if m:
                    res = calculate_live_prediction_points(p, m, config)
                    live_rows.append({
                        "Jogo": f"{m.home_team} x {m.away_team}",
                        "Fase": m.round_label,
                        "Seu Palpite": f"{p.predicted_home_goals} x {p.predicted_away_goals}",
                        "Placar Oficial": f"{m.official_home_goals} x {m.official_away_goals}" if m.status == "result_approved" else "Aguardando",
                        "Status": "Aprovado" if m.status == "result_approved" else "Aberto/Bloqueado",
                        "Pontos": res["points"] if m.status == "result_approved" else "Pendente",
                        "Critério": " · ".join(res["breakdown"]) if m.status == "result_approved" else "—"
                    })
            st.dataframe(pd.DataFrame(live_rows), width="stretch", hide_index=True)

    # Tab 4: Pontos
    with c_tabs[3]:
        st.markdown("#### Decomposição da Pontuação")
        if classic_pred and official:
            st.markdown("##### 📊 Pontos no Modo Clássico")
            user_classic_score = next((s for s in classic_scores if normalize_participant_key(s.participant) == pkey), None)
            if user_classic_score:
                st.write(f"- Pontos em Fase de Grupos: **{user_classic_score.group_points}**")
                st.write(f"- Pontos em Melhores Terceiros: **{user_classic_score.best_third_points}**")
                st.write(f"- Pontos em Mata-Mata: **{user_classic_score.knockout_points}**")
                st.write(f"- Pontos em Campeão: **{user_classic_score.champion_points}**")
                st.write(f"- **Pontuação Total Clássico:** **{user_classic_score.total} pts**")

        st.markdown("##### 📊 Pontos no Modo Jogo a Jogo")
        if user_live_preds:
            st.write(f"- **Pontuação Total Jogo a Jogo:** **{live_points} pts**")
        else:
            st.write("Nenhum palpite computado no jogo a jogo.")

    # Tab 5: Comparar com amigo
    with c_tabs[4]:
        st.markdown("#### Comparar Palpites")
        st.caption("Selecione um amigo e compare os palpites do modo clássico e do jogo a jogo (apenas jogos bloqueados).")
        
        friend_names = [n for n in names if n != selected_name]
        if not friend_names:
            st.warning("Não há outros participantes para comparar.")
        else:
            friend_name = st.selectbox("Escolha o amigo para comparar", options=friend_names, key="compare_friend_select")
            friend_key = normalize_participant_key(friend_name)
            
            friend_classic = next((p for p in submissions if normalize_participant_key(p.participant) == friend_key), None)
            friend_live_preds = [p for p in live_preds if p.participant_key == friend_key]
            
            st.markdown(f"##### 📊 Comparativo Geral: {selected_name} vs {friend_name}")
            
            comp_general = [
                {"Modo / Critério": "Campeão Escolhido (Clássico)", selected_name: classic_champ, friend_name: friend_classic.champion if friend_classic else "—"},
                {"Modo / Critério": "Finalistas Previstos (Clássico)", selected_name: classic_final, friend_name: " x ".join([m.a or '—' for m in friend_classic.knockout.get("final", [])] + [m.b or '—' for m in friend_classic.knockout.get("final", [])]) if friend_classic and friend_classic.knockout.get("final") else "—"},
                {"Modo / Critério": "Pontuação Clássico", selected_name: f"{classic_points} pts", friend_name: f"{next((s.total for s in classic_scores if normalize_participant_key(s.participant) == friend_key), 0)} pts" if official else "—"},
                {"Modo / Critério": "Pontuação Jogo a Jogo", selected_name: f"{live_points} pts", friend_name: f"{next((s['total'] for s in live_scores if s['participant_key'] == friend_key), 0)} pts"}
            ]
            st.dataframe(pd.DataFrame(comp_general), width="stretch", hide_index=True)

            # Compare Jogo a Jogo (only locked/closed matches)
            st.markdown("##### 🔒 Comparativo Jogo a Jogo (Apenas Jogos Bloqueados)")
            locked_match_ids = set(m.match_id for m in matches if m.status == "result_approved" or not is_match_open_for_prediction(m, now))
            
            compare_rows = []
            for m in matches:
                if m.match_id in locked_match_ids:
                    p_user = next((p for p in user_live_preds if p.match_id == m.match_id), None)
                    p_friend = next((p for p in friend_live_preds if p.match_id == m.match_id), None)
                    
                    if p_user or p_friend:
                        user_guess = f"{p_user.predicted_home_goals} x {p_user.predicted_away_goals}" if p_user else "Não palpitou"
                        friend_guess = f"{p_friend.predicted_home_goals} x {p_friend.predicted_away_goals}" if p_friend else "Não palpitou"
                        
                        compare_rows.append({
                            "Jogo": f"{m.home_team} x {m.away_team}",
                            selected_name: user_guess,
                            friend_name: friend_guess,
                            "Resultado Oficial": f"{m.official_home_goals} x {m.official_away_goals}" if m.status == "result_approved" else "Pendente"
                        })
            if compare_rows:
                st.dataframe(pd.DataFrame(compare_rows), width="stretch", hide_index=True)
            else:
                st.caption("Nenhum palpite jogo a jogo em jogos já encerrados ou bloqueados.")
