from __future__ import annotations

import streamlit as st
import pandas as pd
import urllib.parse
from datetime import datetime
from .storage import load_submissions, load_matches, load_live_predictions, load_official, load_config, load_app_data_cached
from .utils import normalize_participant_key, now_iso
from .live_scoring import calculate_live_prediction_points, calculate_live_ranking
from .scoring import rank_predictions
from .ui_simulator import get_team_badge_path
from .ui_live_matches import is_match_open_for_prediction
from .constants import GROUPS, PHASE_LABELS
from .achievements import calculate_achievements
from .social import build_my_card_share_text

def render_minha_cartela() -> None:
    st.markdown("### 📋 Minha Cartela — Visão Geral do Participante")
    st.caption("Acompanhe o status detalhado das suas apostas, pontuação, conquistas e compare seus palpites com os amigos.")

    config = load_config()
    ctx = load_app_data_cached()
    submissions = ctx.submissions
    official = ctx.official
    matches = ctx.matches
    live_preds = ctx.live_predictions

    # Obter conquistas calculadas
    ach_dict = calculate_achievements(ctx)

    if not submissions and not live_preds:
        st.info("Nenhum palpite enviado ainda no sistema.")
        return

    # Select Participant
    names = sorted(list(set([p.participant for p in submissions] + [p.participant_name for p in live_preds])), key=lambda x: x.lower())
    selected_name = st.selectbox("Escolha seu Nome para Visualizar a Cartela", options=names, key="cartela_name_select")
    
    pkey = normalize_participant_key(selected_name)

    # Find predictions for selected participant
    classic_pred = next((p for p in submissions if normalize_participant_key(p.participant) == pkey), None)
    user_live_preds = [p for p in live_preds if (p.participant_key or normalize_participant_key(p.participant_name)) == pkey]

    # Calculate classic points and position
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
            classic_rank = f"{user_classic_score.position}" if hasattr(user_classic_score, 'position') else f"{classic_scores.index(user_classic_score)+1}"
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
        live_rank = f"{user_live_score['position']}"
        live_exact = user_live_score["exact_scores"]
        live_rate = f"{int(user_live_score['hit_rate'] * 100)}%"

    # Calculate combined position if enabled
    pos_geral = "—"
    combined_enabled = config.get("combined_ranking_enabled", False)
    if combined_enabled and official:
        # Calcular ranking combinado
        combined_rules = config.get("combined_ranking", {})
        classic_weight = combined_rules.get("classic_weight", 1.0)
        live_weight = combined_rules.get("live_weight", 1.0)
        include_classic_only = combined_rules.get("include_classic_only_players", True)
        include_live_only = combined_rules.get("include_live_only_players", True)
        
        classic_dict = {normalize_participant_key(s.participant): s for s in rank_predictions(submissions, official, score_config)}
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
            c_pts = c_score.total if c_score else 0
            l_pts = l_score["total"] if l_score else 0
            combined_pts = c_pts * classic_weight + l_pts * live_weight
            combined_list.append({"key": pk, "total": combined_pts, "classic": c_pts, "live": l_pts})
            
        combined_list.sort(key=lambda x: (-x["total"], -x["classic"], -x["live"]))
        for idx, item in enumerate(combined_list, start=1):
            if item["key"] == pkey:
                pos_geral = str(idx)
                break

    # Find next pending game
    now = datetime.now().isoformat()
    open_matches = [m for m in matches if m.status != "result_approved" and m.starts_at and m.starts_at > now]
    open_matches.sort(key=lambda m: m.starts_at)
    
    guessed_match_ids = set(p.match_id for p in user_live_preds)
    pending_matches = [m for m in open_matches if m.match_id not in guessed_match_ids]
    if pending_matches:
        next_m = pending_matches[0]
        live_next_match = f"{next_m.home_team} x {next_m.away_team} (em {next_m.starts_at.replace('T', ' ')})"

    # Render Main Card
    st.markdown(
        f"""
        <div style="border: 2px solid var(--gold); border-radius: 24px; padding: 25px; background: var(--panel); box-shadow: var(--shadow); margin-bottom: 25px; color: var(--ink);">
            <div style="font-size: 40px; text-align: center; margin-bottom: 5px;">⚽</div>
            <h3 style="text-align: center; color: var(--ink); margin: 5px 0;">{selected_name}</h3>
            <p style="text-align: center; color: var(--muted); font-size: 14px; margin-top:0;">Chave estável: {pkey}</p>
            <div style="display: flex; gap: 20px; justify-content: space-around; margin-top: 20px; flex-wrap: wrap;">
                <div style="flex: 1; min-width: 200px; padding: 15px; border-radius: 12px; background-color: var(--bg-soft); border: 1px solid var(--line); text-align: center;">
                    <span style="font-size: 12px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.5px;">Modo Clássico</span>
                    <h2 style="margin: 8px 0; color: var(--green);">{classic_points} <span style="font-size: 14px; color: var(--muted);">pts</span></h2>
                    <div style="font-size: 13px; color: var(--muted);">Posição: <b>{classic_rank}º</b> · Campeão: <b>{classic_champ}</b></div>
                </div>
                <div style="flex: 1; min-width: 200px; padding: 15px; border-radius: 12px; background-color: var(--bg-soft); border: 1px solid var(--line); text-align: center;">
                    <span style="font-size: 12px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.5px;">Modo Jogo a Jogo</span>
                    <h2 style="margin: 8px 0; color: var(--green);">{live_points} <span style="font-size: 14px; color: var(--muted);">pts</span></h2>
                    <div style="font-size: 13px; color: var(--muted);">Posição: <b>{live_rank}º</b> · Aprov.: <b>{live_rate}</b></div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    c_tabs = st.tabs([
        "📊 Resumo Geral", 
        "🏆 Palpite Clássico", 
        "🎯 Palpites Jogo a Jogo", 
        "💡 Pontuação", 
        "🎖️ Conquistas",
        "⚖️ Comparar com Amigo"
    ])

    # Tab 1: Resumo Geral
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
        
        # Build share text via social.py helper
        share_text = build_my_card_share_text(selected_name, classic_rank, live_rank, pos_geral, classic_points, live_points)
        st.code(share_text, language="text")
        
        encoded_text = urllib.parse.quote(share_text)
        st.link_button("💬 Enviar no WhatsApp", f"https://api.whatsapp.com/send?text={encoded_text}", type="primary", width="stretch")

    # Tab 2: Palpite Clássico
    with c_tabs[1]:
        st.markdown("#### Detalhamento do Palpite Clássico")
        if not classic_pred:
            st.warning("Você não possui palpite clássico registrado.")
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

            # Show group matches predictions
            st.markdown("##### ⚽ Palpites de Placares nos Grupos")
            group_matches = classic_pred.meta.get("group_matches", {})
            if group_matches:
                from .worldcup_2026_data import GROUP_MATCHES, TEAMS
                gm_rows = []
                for gm in GROUP_MATCHES:
                    m_id = str(gm["id"])
                    score = group_matches.get(m_id)
                    if score and len(score) == 2:
                        home_name = TEAMS.get(gm["home_id"], {}).get("name", "Mandante")
                        away_name = TEAMS.get(gm["away_id"], {}).get("name", "Visitante")
                        gm_rows.append({
                            "Grupo": f"Grupo {gm['group']}",
                            "Rodada": f"Rodada {gm['round']}",
                            "Jogo": f"{home_name} x {away_name}",
                            "Palpite": f"{score[0]} x {score[1]}"
                        })
                if gm_rows:
                    with st.expander("Ver Todos os Palpites de Placares da Fase de Grupos", expanded=False):
                        st.dataframe(pd.DataFrame(gm_rows), width="stretch", hide_index=True)

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

    # Tab 5: Conquistas
    with c_tabs[4]:
        st.markdown("#### 🎖️ Suas Conquistas Sociais")
        st.caption("Conquistas e insígnias especiais baseadas no desempenho das suas previsões.")
        
        user_badges = ach_dict.get(pkey, [])
        if not user_badges:
            st.info("Você ainda não desbloqueou nenhuma conquista. Continue palpitando e acertando para ganhar insígnias!")
        else:
            cols = st.columns(min(len(user_badges), 3))
            for idx, badge in enumerate(user_badges):
                col = cols[idx % len(cols)]
                with col:
                    st.markdown(
                        f"""
                        <div class="card" style="text-align: center; padding: 20px; border-top: 4px solid var(--gold);">
                            <div style="font-size: 40px; margin-bottom: 8px;">{badge['icon']}</div>
                            <h4 style="margin: 0 0 6px; color: var(--ink);">{badge['name']}</h4>
                            <p style="font-size: 13px; color: var(--muted); margin: 0; line-height:1.3;">{badge['description']}</p>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )

    # Tab 6: Comparar com amigo
    with c_tabs[5]:
        st.markdown("#### Comparar Palpites")
        st.caption("Selecione um amigo e compare os palpites do modo clássico e do jogo a jogo.")
        
        friend_names = [n for n in names if n != selected_name]
        if not friend_names:
            st.warning("Não há outros participantes para comparar.")
        else:
            friend_name = st.selectbox("Escolha o amigo para comparar", options=friend_names, key="compare_friend_select")
            friend_key = normalize_participant_key(friend_name)
            
            friend_classic = next((p for p in submissions if normalize_participant_key(p.participant) == friend_key), None)
            friend_live_preds = [p for p in live_preds if (p.participant_key or normalize_participant_key(p.participant_name)) == friend_key]
            
            st.markdown(f"##### 📊 Comparativo Geral: {selected_name} vs {friend_name}")
            
            comp_general = [
                {"Modo / Critério": "Campeão Escolhido (Clássico)", selected_name: classic_champ, friend_name: friend_classic.champion if friend_classic else "—"},
                {"Modo / Critério": "Finalistas Previstos (Clássico)", selected_name: classic_final, friend_name: " x ".join([m.a or '—' for m in friend_classic.knockout.get("final", [])] + [m.b or '—' for m in friend_classic.knockout.get("final", [])]) if friend_classic and friend_classic.knockout.get("final") else "—"},
                {"Modo / Critério": "Pontuação Clássico", selected_name: f"{classic_points} pts", friend_name: f"{next((s.total for s in classic_scores if normalize_participant_key(s.participant) == friend_key), 0)} pts" if official else "—"},
                {"Modo / Critério": "Pontuação Jogo a Jogo", selected_name: f"{live_points} pts", friend_name: f"{next((s['total'] for s in live_scores if s['participant_key'] == friend_key), 0)} pts"}
            ]
            st.dataframe(pd.DataFrame(comp_general), width="stretch", hide_index=True)

            # Compare Jogo a Jogo
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
