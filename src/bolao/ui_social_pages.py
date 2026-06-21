from __future__ import annotations

import streamlit as st
import pandas as pd
import urllib.parse
from datetime import datetime
from .storage import load_matches, load_live_predictions, load_submissions, load_official, load_config, load_app_data_cached, load_registered_participants, load_archived_participants
from .live_scoring import calculate_live_prediction_points, calculate_live_ranking
from .scoring import rank_predictions
from .utils import normalize_participant_key
from .ui_components import render_page_header, render_kpi_grid, render_empty_state, render_badge, render_responsive_table
from .achievements import calculate_achievements
from .social import build_duel_share_text, build_taunt_text
from .ui_live_matches import is_match_open_for_prediction
from .constants import SCORING_MODE_OPTIONS, SCORING_MODE_LABELS, DEFAULT_V2_RULES

def render_central_do_bolao() -> None:
    render_page_header("Central", "Central Social do Bolão", "Painel esportivo com os principais destaques, sequências e zoeiras do grupo.", "📣")
    
    ctx = load_app_data_cached()
    config = ctx.config
    submissions = ctx.submissions
    live_preds = ctx.live_predictions
    matches = ctx.matches
    official = ctx.official

    if not submissions and not live_preds:
        st.info("Nenhum palpite enviado ainda no sistema.")
        return

    # Líderes
    classic_leader = "—"
    live_leader = "—"
    combined_leader = "—"
    lanterna = "—"
    
    # Calcular rankings
    if submissions and official:
        from .scoring import ScoreConfig
        from .constants import DEFAULT_WEIGHTED_RULES, DEFAULT_UNIFORM_RULES, DEFAULT_V2_RULES
        score_config = ScoreConfig(
            mode=config.get("scoring_mode", "v2"),
            weighted_rules=config.get("weighted_rules", dict(DEFAULT_WEIGHTED_RULES)),
            uniform_rules=config.get("uniform_rules", dict(DEFAULT_UNIFORM_RULES)),
            v2_rules=config.get("v2_rules", dict(DEFAULT_V2_RULES)),
        )
        classic_ranks = rank_predictions(submissions, official, score_config)
        if classic_ranks:
            classic_leader = classic_ranks[0].participant
            
    live_ranks = calculate_live_ranking(live_preds, matches, config)
    if live_ranks:
        live_leader = live_ranks[0]["participant"]
        lanterna = live_ranks[-1]["participant"]

    combined_enabled = config.get("combined_ranking_enabled", False)
    if combined_enabled and official:
        combined_rules = config.get("combined_ranking", {})
        classic_weight = combined_rules.get("classic_weight", 1.0)
        live_weight = combined_rules.get("live_weight", 1.0)
        
        classic_dict = {normalize_participant_key(s.participant): s for s in classic_ranks}
        live_dict = {s["participant_key"]: s for s in live_ranks}
        all_keys = set(classic_dict.keys()).union(live_dict.keys())
        
        combined_list = []
        for pk in all_keys:
            c_s = classic_dict.get(pk)
            l_s = live_dict.get(pk)
            c_p = c_s.total if c_s else 0
            l_p = l_s["total"] if l_s else 0
            combined_list.append({"name": c_s.participant if c_s else l_s["participant"], "total": c_p * classic_weight + l_p * live_weight})
        combined_list.sort(key=lambda x: -x["total"])
        if combined_list:
            combined_leader = combined_list[0]["name"]

    # Render KPIs
    kpi_items = [
        {"label": "Líder Clássico", "value": classic_leader},
        {"label": "Líder Jogo a Jogo", "value": live_leader},
    ]
    if combined_enabled:
        kpi_items.append({"label": "Líder Geral", "value": combined_leader})
    render_kpi_grid(kpi_items)

    # CTA Button for Jogo a Jogo
    if st.button("⚽ Palpitar nos Jogos de Hoje", type="primary", key="central_cta_jogos_hoje", width="stretch"):
        from .navigation import navigate_to
        navigate_to("Jogos de Hoje")

    # Zoeira do dia (Taunt)
    st.markdown("#### 🗣️ Provocação da Rodada")
    taunt_ctx = {"nome": live_leader, "kind": "lider"}
    if live_leader != "—":
        st.markdown(f'<div class="callout warning">📢 {build_taunt_text(taunt_ctx)}</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="callout info">📢 A Copa está começando! Quem assumirá a liderança primeiro?</div>', unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("#### ⏰ Próximos Fechamentos")
        now = datetime.now().isoformat()
        upcoming = [m for m in matches if m.starts_at and m.starts_at > now and m.status != "result_approved"]
        upcoming.sort(key=lambda x: x.starts_at)
        
        if not upcoming:
            st.write("Nenhum jogo futuro agendado.")
        else:
            for m in upcoming[:3]:
                st.write(f"⚽ **{m.home_team} x {m.away_team}**")
                st.caption(f"Fecha em: {m.lock_at.replace('T', ' ')}")

    with col2:
        st.markdown("#### 📢 Últimos Acontecimentos")
        # Load only public events, excluding archived players
        from .storage import load_events, get_archived_keys
        archived_keys = get_archived_keys()
        events = load_events(limit=15, visibility="public")
        filtered_events = []
        for e in events:
            meta = e.get("metadata", {})
            pkey = meta.get("participant_key")
            if pkey and pkey in archived_keys:
                continue
            filtered_events.append(e)
            if len(filtered_events) >= 5:
                break
        if not filtered_events:
            st.write("Sem atividades recentes.")
        else:
            for e in filtered_events:
                ts = e.get("timestamp", "").split("T")[1][:5] if "T" in e.get("timestamp", "") else "—"
                st.write(f"⏱️ **{ts}** — {e.get('message')}")


def render_palpites_do_grupo() -> None:
    render_page_header("Palpites do Grupo", "Palpites Coletivos", "Veja o que cada participante palpitou para os jogos.", "👥")
    
    ctx = load_app_data_cached()
    matches = ctx.matches
    live_preds = ctx.live_predictions
    submissions = ctx.submissions
    config = ctx.config

    if not matches:
        st.info("Nenhum jogo agendado.")
        return

    matches.sort(key=lambda m: (m.starts_at or "", m.sort_order))

    tabs_public = st.tabs(["🔍 Por Jogo", "📋 Matriz Geral de Palpites", "🏳️ Todos os Palpites (Filtros & Bandeiras)"])
    
    with tabs_public[0]:
        # Filtro por rodada/fase
        rounds = sorted(list(set(m.round_label for m in matches)))
        selected_round = st.selectbox("Filtrar por Rodada/Fase", ["Todas"] + rounds, key="palpites_grupo_round_filter")
        
        if selected_round != "Todas":
            filtered_matches = [m for m in matches if m.round_label == selected_round]
        else:
            filtered_matches = matches
            
        if not filtered_matches:
            st.info("Nenhuma partida nesta rodada.")
        else:
            # Escolher o jogo
            selected_match = st.selectbox(
                "Selecione uma partida para ver os palpites", 
                filtered_matches, 
                format_func=lambda m: f"{m.home_team} x {m.away_team} ({m.round_label})"
            )

            if selected_match:
                m = selected_match
                now = datetime.now().isoformat()
                is_open = is_match_open_for_prediction(m, now)

                st.markdown(f"#### Palpites para: {m.home_team} x {m.away_team}")
                
                match_preds = [lp for lp in live_preds if lp.match_id == m.match_id]
                
                # Privado antes do lock
                if is_open:
                    st.info("🔒 Os palpites individuais estão ocultados até o fechamento das apostas (10 minutos antes do início do jogo).")
                    st.metric("Total de palpites enviados até agora", len(match_preds))
                else:
                    # Privacidade pós lock
                    reveal_allowed = config.get("public_features", {}).get("reveal_live_predictions_after_lock", True) or m.status == "result_approved"
                    if not reveal_allowed:
                        st.info("🔒 A visualização dos palpites dos outros participantes está desativada conforme as regras de privacidade do bolão.")
                    elif not match_preds:
                        st.info("Ninguém palpitou nesta partida.")
                    else:
                        data = []
                        for lp in match_preds:
                            points_gained = None
                            if m.status == "result_approved":
                                res = calculate_live_prediction_points(lp, m, config)
                                points_gained = res["points"]
                                
                            data.append({
                                "Participante": lp.participant_name,
                                "Palpite": f"{lp.predicted_home_goals} x {lp.predicted_away_goals}",
                                "Pontos Ganhos": points_gained,
                                "Envio": lp.submitted_at.replace("T", " ") if lp.submitted_at else "—"
                            })
                            
                        def render_palpite_grupo_card(r):
                            badge_pts = f"<span class='badge success'>{r['Pontos Ganhos']} pts</span>" if r['Pontos Ganhos'] is not None else ""
                            st.markdown(
                                f"""
                                <div class="card" style="margin-bottom: 12px; padding: 16px; border-left: 5px solid var(--green);">
                                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                                        <span style="font-weight: bold; font-size: 15px; color: var(--ink);">{r['Participante']}</span>
                                        {badge_pts}
                                    </div>
                                    <div style="font-size: 13px; color: var(--muted); line-height: 1.4;">
                                        🎯 Palpite: <strong style="color:var(--green); font-size:14px;">{r['Palpite']}</strong>
                                        <br>⏱️ Envio: {r['Envio']}
                                    </div>
                                </div>
                                """,
                                unsafe_allow_html=True
                            )

                        render_responsive_table(pd.DataFrame(data), render_palpite_grupo_card, f"palpites_grupo_{m.match_id}")

    with tabs_public[1]:
        st.markdown("#### 📋 Tabela Geral de Palpites")
        st.caption("Consulte os palpites de todos os participantes para todas as partidas. Os palpites de partidas ainda abertas são protegidos sob sigilo (🔒 Oculto) para manter a integridade da competição.")
        
        from .storage import load_registered_participants
        active_participants = load_registered_participants(include_archived=False)
        participant_names = sorted([p for p in active_participants], key=lambda x: x.lower())
        
        logged_user_name = st.session_state.get("live_user_name", "")
        logged_user_key = st.session_state.get("live_user_key", "")
        
        preds_map = {(lp.participant_key or normalize_participant_key(lp.participant_name), lp.match_id): lp for lp in live_preds}
        now = datetime.now().isoformat()
        
        # Sort matches by group and then chronologically
        def get_sort_key(m):
            g = m.group or ""
            g_clean = g.strip().upper()
            if not g_clean or len(g_clean) > 1 or g_clean < 'A' or g_clean > 'L':
                group_key = "Z_Mata-Mata"
            else:
                group_key = f"Grupo {g_clean}"
            return (group_key, m.starts_at or "", m.sort_order)
        sorted_matches_for_matrix = sorted(matches, key=get_sort_key)

        matrix_data = []
        for m in sorted_matches_for_matrix:
            is_open = is_match_open_for_prediction(m, now)
            
            row = {
                "Grupo": f"Grupo {m.group}" if (m.group and m.group.strip()) else "Mata-Mata",
                "Jogo": f"{m.home_team} x {m.away_team}",
                "Rodada": m.round_label,
                "Início": m.starts_at.replace("T", " ") if m.starts_at else "—",
                "Resultado Oficial": f"{m.official_home_goals} x {m.official_away_goals}" if m.official_home_goals is not None else "Aguardando"
            }
            
            for p_name in participant_names:
                pkey = normalize_participant_key(p_name)
                pred = preds_map.get((pkey, m.match_id))
                
                if is_open:
                    if pkey == logged_user_key:
                        row[p_name] = f"{pred.predicted_home_goals} x {pred.predicted_away_goals} (Você)" if pred else "Sem palpite"
                    else:
                        row[p_name] = "🔒 Oculto"
                else:
                    reveal_allowed = config.get("public_features", {}).get("reveal_live_predictions_after_lock", True) or m.status == "result_approved"
                    if reveal_allowed:
                        if pred:
                            pts_str = ""
                            if m.status == "result_approved":
                                res = calculate_live_prediction_points(pred, m, config)
                                pts_str = f" ({res['points']} pts)"
                            row[p_name] = f"{pred.predicted_home_goals} x {pred.predicted_away_goals}{pts_str}"
                        else:
                            row[p_name] = "—"
                    else:
                        if pkey == logged_user_key and pred:
                            row[p_name] = f"{pred.predicted_home_goals} x {pred.predicted_away_goals}"
                        else:
                            row[p_name] = "🔒 Oculto"
                            
            matrix_data.append(row)
            
        if not matrix_data:
            st.info("Nenhum palpite computado ou jogo agendado.")
        else:
            df_matrix = pd.DataFrame(matrix_data)
            
            tab_matriz, tab_lista = st.tabs(["📊 Matriz Completa", "📱 Visão por Participante"])
            
            with tab_matriz:
                st.markdown('<div style="overflow-x: auto; max-width: 100%;">', unsafe_allow_html=True)
                st.dataframe(df_matrix, width="content", hide_index=True)
                st.markdown('</div>', unsafe_allow_html=True)
                
            with tab_lista:
                if not participant_names:
                    st.caption("Nenhum participante cadastrado.")
                else:
                    participante_sel = st.selectbox("Ver palpites de:", options=participant_names, key="matriz_select_participante")
                    df_participante = df_matrix[["Grupo", "Jogo", "Rodada", "Resultado Oficial", participante_sel]]
                    st.dataframe(df_participante, width="stretch", hide_index=True)

    with tabs_public[2]:
        st.markdown("#### 🏳️ Todos os Palpites (Filtros & Bandeiras)")
        st.caption("Consulte todos os palpites jogo a jogo dos participantes. Filtre por rodada, por time ou por participante e veja as bandeiras das seleções.")

        # 1. Filtros
        col_f1, col_f2, col_f3 = st.columns(3)
        with col_f1:
            filtro_participante = st.selectbox(
                "Filtrar por Participante",
                ["Todos"] + participant_names,
                key="public_all_preds_participante"
            )
        with col_f2:
            filtro_rodada = st.selectbox(
                "Filtrar por Rodada/Fase",
                ["Todas"] + sorted(list(set(m.round_label for m in matches))),
                key="public_all_preds_rodada"
            )
        with col_f3:
            all_teams = sorted(list(set(m.home_team for m in matches).union(set(m.away_team for m in matches))))
            filtro_time = st.selectbox(
                "Filtrar por Seleção",
                ["Todas"] + all_teams,
                key="public_all_preds_time"
            )

        # 2. Get and filter predictions
        preds_to_show = []
        now = datetime.now().isoformat()
        
        from .ui_simulator import get_team_badge_path
        from .simulator_engine import name_to_id
        
        for lp in live_preds:
            m = next((m for m in matches if m.match_id == lp.match_id), None)
            if not m:
                continue
            
            # Apply Participant filter
            if filtro_participante != "Todos" and (lp.participant_key or normalize_participant_key(lp.participant_name)) != normalize_participant_key(filtro_participante):
                continue
                
            # Apply Round filter
            if filtro_rodada != "Todas" and m.round_label != filtro_rodada:
                continue
                
            # Apply Team filter
            if filtro_time != "Todas" and m.home_team != filtro_time and m.away_team != filtro_time:
                continue
                
            preds_to_show.append((lp, m))
            
        preds_to_show.sort(key=lambda item: (item[1].starts_at or "", item[1].sort_order, item[0].participant_name.lower()))
        
        if not preds_to_show:
            st.info("Nenhum palpite corresponde aos filtros selecionados.")
        else:
            logged_user_key = st.session_state.get("live_user_key", "")
            
            _last_group = None
            for lp, m in preds_to_show:
                _cur_group = f"Grupo {m.group}" if (m.group and m.group.strip()) else "Mata-Mata"
                if _cur_group != _last_group:
                    st.markdown(f"##### 🏆 {_cur_group}")
                    _last_group = _cur_group
            
            for lp, m in preds_to_show:
                is_open = is_match_open_for_prediction(m, now)
                
                h_id = name_to_id(m.home_team)
                a_id = name_to_id(m.away_team)
                h_badge = get_team_badge_path(h_id) if h_id else None
                a_badge = get_team_badge_path(a_id) if a_id else None
                
                # Privacy
                if is_open:
                    if (lp.participant_key or normalize_participant_key(lp.participant_name)) == logged_user_key:
                        guess_display = f"{lp.predicted_home_goals} x {lp.predicted_away_goals} (Você)"
                        status_str = "<span class='badge success'>🟢 ABERTO (Palpitado)</span>"
                    else:
                        guess_display = "🔒 Oculto"
                        status_str = "<span class='badge info'>🟢 ABERTO (Sigilo)</span>"
                else:
                    reveal_allowed = config.get("public_features", {}).get("reveal_live_predictions_after_lock", True) or m.status == "result_approved"
                    if reveal_allowed:
                        guess_display = f"{lp.predicted_home_goals} x {lp.predicted_away_goals}"
                    else:
                        if (lp.participant_key or normalize_participant_key(lp.participant_name)) == logged_user_key:
                            guess_display = f"{lp.predicted_home_goals} x {lp.predicted_away_goals}"
                        else:
                            guess_display = "🔒 Oculto"
                    
                    if m.status == "result_approved":
                        res = calculate_live_prediction_points(lp, m, config)
                        status_str = f"<span class='badge success'>🏆 CONCLUÍDO (+{res['points']} pts)</span>"
                    else:
                        status_str = "<span class='badge error'>🔒 BLOQUEADO</span>"
                        
                with st.container(border=True):
                    # Card Header
                    col_h1, col_h2 = st.columns([2, 1])
                    with col_h1:
                        st.markdown(f"**{m.round_label}** · Participante: **{lp.participant_name}**")
                    with col_h2:
                        st.markdown(f"<div style='text-align: right;'>{status_str}</div>", unsafe_allow_html=True)
                        
                    # Card body - teams, flags, and prediction
                    col_t1, col_vs, col_t2 = st.columns([4, 4, 4])
                    with col_t1:
                        st.markdown("<div style='text-align: center;'>", unsafe_allow_html=True)
                        if h_badge:
                            st.image(h_badge, width=32)
                        st.markdown(f"<div style='font-weight: 700; margin-top: 4px; color: var(--ink);'>{m.home_team}</div>", unsafe_allow_html=True)
                        st.markdown("</div>", unsafe_allow_html=True)
                        
                    with col_vs:
                        st.markdown(
                            f"""
                            <div style='text-align: center; margin-top: 10px;'>
                                <div style='font-size: 13px; color: var(--muted); text-transform: uppercase;'>Palpite</div>
                                <div style='font-size: 20px; font-weight: 900; color: var(--green);'>{guess_display}</div>
                            </div>
                            """, 
                            unsafe_allow_html=True
                        )
                        if m.status == "result_approved":
                            st.markdown(
                                f"""
                                <div style='text-align: center; font-size: 11px; color: var(--muted); margin-top: 4px;'>
                                    Placar Real: <b>{m.official_home_goals} x {m.official_away_goals}</b>
                                </div>
                                """,
                                unsafe_allow_html=True
                            )
                            
                    with col_t2:
                        st.markdown("<div style='text-align: center;'>", unsafe_allow_html=True)
                        if a_badge:
                            st.image(a_badge, width=32)
                        st.markdown(f"<div style='font-weight: 700; margin-top: 4px; color: var(--ink);'>{m.away_team}</div>", unsafe_allow_html=True)
                        st.markdown("</div>", unsafe_allow_html=True)


def render_analise_dos_palpites() -> None:
    render_page_header("Análise", "Análise dos Palpites vs Realidade", "Estatísticas retrospectivas de acertos, erros e zebras.", "📊")
    
    ctx = load_app_data_cached()
    matches = ctx.matches
    live_preds = ctx.live_predictions
    submissions = ctx.submissions
    config = ctx.config

    approved_matches = [m for m in matches if m.status == "result_approved" and m.official_home_goals is not None and m.official_away_goals is not None]
    if not approved_matches:
        st.info("Nenhuma partida concluída e aprovada ainda para realizar a análise retrospectiva.")
        return

    st.markdown("#### 🎯 Maiores Pontuadores da Rodada")
    # Agrupar por rodada
    rounds = sorted(list(set(m.round_label for m in approved_matches)))
    selected_round = st.selectbox("Escolha a rodada para analisar", rounds)
    
    round_matches = [m for m in approved_matches if m.round_label == selected_round]
    round_match_ids = {m.match_id for m in round_matches}
    
    round_preds = [lp for lp in live_preds if lp.match_id in round_match_ids]
    round_ranks = calculate_live_ranking(round_preds, round_matches, config)
    
    if round_ranks:
        sub_df = pd.DataFrame([{
            "Posição": r["position"],
            "Participante": r["participant"],
            "Pontos na Rodada": r["total"],
            "Placares Exatos": r["exact_scores"],
            "Aproveitamento": f"{int(r['hit_rate']*100)}%"
        } for r in round_ranks])
        
        def render_analise_ranking_card(r):
            st.markdown(
                f"""
                <div class="card" style="margin-bottom: 12px; padding: 16px; border-left: 5px solid var(--green);">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                        <span style="font-weight: bold; font-size: 15px; color: var(--ink);">{r['Posição']}º. {r['Participante']}</span>
                        <span class="badge success">{r['Pontos na Rodada']} pts</span>
                    </div>
                    <div style="font-size: 13px; color: var(--muted); line-height: 1.4;">
                        🎯 Placares Exatos: {r['Placares Exatos']}
                        <br>📈 Aproveitamento: {r['Aproveitamento']}
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )
        render_responsive_table(sub_df, render_analise_ranking_card, f"analise_ranking_{selected_round}")
    else:
        st.caption("Sem palpites computados para esta rodada.")

    # Estatísticas de Zebras
    st.markdown("#### 🦓 Acertos de Zebras (Divergência do Grupo)")
    zebra_hits_list = []
    
    for m in approved_matches:
        match_preds = [lp for lp in live_preds if lp.match_id == m.match_id]
        total_p = len(match_preds)
        if total_p == 0:
            continue
            
        home_votes = sum(1 for lp in match_preds if lp.predicted_home_goals > lp.predicted_away_goals)
        away_votes = sum(1 for lp in match_preds if lp.predicted_home_goals < lp.predicted_away_goals)
        draw_votes = sum(1 for lp in match_preds if lp.predicted_home_goals == lp.predicted_away_goals)
        
        real_outcome = "draw"
        if m.official_home_goals > m.official_away_goals:
            real_outcome = "home"
        elif m.official_home_goals < m.official_away_goals:
            real_outcome = "away"
            
        votes_for_real = home_votes if real_outcome == "home" else (away_votes if real_outcome == "away" else draw_votes)
        pct_votes_for_real = (votes_for_real / total_p)
        
        # Se menos de 30% apostaram no resultado real, é zebra!
        if pct_votes_for_real < 0.30:
            # Encontrar quem acertou
            winners = []
            for lp in match_preds:
                res = calculate_live_prediction_points(lp, m, config)
                if res["flags"].get("outcome"):
                    winners.append(lp.participant_name)
            
            zebra_hits_list.append({
                "Jogo": f"{m.home_team} x {m.away_team}",
                "Placar Oficial": f"{m.official_home_goals} x {m.official_away_goals}",
                "Apoio do Grupo": f"{int(pct_votes_for_real * 100)}%",
                "Quem Acertou": ", ".join(winners) if winners else "Ninguém"
            })
            
    if zebra_hits_list:
        def render_zebra_card(r):
            st.markdown(
                f"""
                <div class="card" style="margin-bottom: 12px; padding: 16px; border-left: 5px solid var(--gold);">
                    <div style="font-weight: bold; font-size: 15px; color: var(--ink); margin-bottom: 6px;">{r['Jogo']}</div>
                    <div style="font-size: 13px; color: var(--muted); line-height: 1.4;">
                        🏁 Placar Oficial: <b>{r['Placar Oficial']}</b>
                        <br>📊 Apoio do Grupo: {r['Apoio do Grupo']}
                        <br>🦓 Quem Acertou: <strong style="color:var(--green);">{r['Quem Acertou']}</strong>
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )
        render_responsive_table(pd.DataFrame(zebra_hits_list), render_zebra_card, "zebra_hits")
    else:
        st.write("Nenhum resultado classificado como zebra ocorreu na Copa ainda.")


def render_duelo_de_palpites() -> None:
    render_page_header("Duelo", "Duelo Direto de Palpites", "Compare o desempenho de dois participantes lado a lado.", "⚔️")
    
    ctx = load_app_data_cached()
    submissions = ctx.submissions
    live_preds = ctx.live_predictions
    matches = ctx.matches
    official = ctx.official
    config = ctx.config

    names = sorted(list(set([p.participant for p in submissions] + [p.participant_name for p in live_preds])), key=lambda x: x.lower())
    if len(names) < 2:
        st.info("São necessários pelo menos 2 participantes para iniciar um duelo.")
        return

    col1, col2 = st.columns(2)
    with col1:
        player_a = st.selectbox("Escolha o Participante A", names, index=0, key="duel_player_a")
    with col2:
        player_b = st.selectbox("Escolha o Participante B", names, index=min(1, len(names)-1), key="duel_player_b")

    if player_a == player_b:
        st.warning("Selecione participantes diferentes para duelar.")
        return

    pkey_a = normalize_participant_key(player_a)
    pkey_b = normalize_participant_key(player_b)

    # Rankings
    classic_points_a = classic_points_b = 0
    live_points_a = live_points_b = 0
    
    if submissions and official:
        from .scoring import ScoreConfig
        from .constants import DEFAULT_WEIGHTED_RULES, DEFAULT_UNIFORM_RULES, DEFAULT_V2_RULES
        score_config = ScoreConfig(
            mode=config.get("scoring_mode", "v2"),
            weighted_rules=config.get("weighted_rules", dict(DEFAULT_WEIGHTED_RULES)),
            uniform_rules=config.get("uniform_rules", dict(DEFAULT_UNIFORM_RULES)),
            v2_rules=config.get("v2_rules", dict(DEFAULT_V2_RULES)),
        )
        classic_scores = rank_predictions(submissions, official, score_config)
        sc_a = next((s for s in classic_scores if normalize_participant_key(s.participant) == pkey_a), None)
        sc_b = next((s for s in classic_scores if normalize_participant_key(s.participant) == pkey_b), None)
        classic_points_a = sc_a.total if sc_a else 0
        classic_points_b = sc_b.total if sc_b else 0

    live_scores = calculate_live_ranking(live_preds, matches, config)
    ls_a = next((s for s in live_scores if s["participant_key"] == pkey_a), None)
    ls_b = next((s for s in live_scores if s["participant_key"] == pkey_b), None)
    live_points_a = ls_a["total"] if ls_a else 0
    live_points_b = ls_b["total"] if ls_b else 0

    st.markdown(f"#### 📊 Confronto: {player_a} vs {player_b}")
    
    # KPI Grid
    kpis = [
        {"label": f"Pontos {player_a} (Jogo a Jogo)", "value": str(live_points_a)},
        {"label": f"Pontos {player_b} (Jogo a Jogo)", "value": str(live_points_b)},
    ]
    render_kpi_grid(kpis)

    # Discordâncias no Jogo a Jogo (apenas bloqueados)
    now = datetime.now().isoformat()
    locked_match_ids = set(m.match_id for m in matches if m.status == "result_approved" or not is_match_open_for_prediction(m, now))

    discord_list = []
    diff_count = 0
    
    for m in matches:
        if m.match_id in locked_match_ids:
            p_a = next((lp for lp in live_preds if lp.match_id == m.match_id and (lp.participant_key or normalize_participant_key(lp.participant_name)) == pkey_a), None)
            p_b = next((lp for lp in live_preds if lp.match_id == m.match_id and (lp.participant_key or normalize_participant_key(lp.participant_name)) == pkey_b), None)
            
            if p_a or p_b:
                guess_a = f"{p_a.predicted_home_goals} x {p_a.predicted_away_goals}" if p_a else "Não palpitou"
                guess_b = f"{p_b.predicted_home_goals} x {p_b.predicted_away_goals}" if p_b else "Não palpitou"
                
                if guess_a != guess_b:
                    diff_count += 1
                    discord_list.append({
                        "Jogo": f"{m.home_team} x {m.away_team}",
                        player_a: guess_a,
                        player_b: guess_b,
                        "Resultado Oficial": f"{m.official_home_goals} x {m.official_away_goals}" if m.status == "result_approved" else "Pendente"
                    })
                    
    # Determinar líder do duelo
    leader = "Empate"
    if live_points_a > live_points_b:
        leader = player_a
    elif live_points_b > live_points_a:
        leader = player_b

    st.markdown("#### 📱 Compartilhar Duelo no WhatsApp")
    share_duel_txt = build_duel_share_text(player_a, player_b, live_points_a, live_points_b, leader, diff_count)
    st.code(share_duel_txt, language="text")
    
    encoded = urllib.parse.quote(share_duel_txt)
    st.link_button("💬 Enviar Duelo no WhatsApp", f"https://api.whatsapp.com/send?text={encoded}", type="primary", width="stretch")

    st.markdown("#### ⚔️ Divergências de Placares em Jogos Bloqueados")
    if discord_list:
        def render_duel_discord_card(r):
            st.markdown(
                f"""
                <div class="card" style="margin-bottom: 12px; padding: 16px; border-left: 5px solid var(--red);">
                    <div style="font-weight: bold; font-size: 15px; color: var(--ink); margin-bottom: 6px;">{r['Jogo']}</div>
                    <div style="font-size: 13px; color: var(--muted); line-height: 1.4;">
                        👤 <b>{player_a}:</b> {r[player_a]}
                        <br>👥 <b>{player_b}:</b> {r[player_b]}
                        <br>🏁 Placar Oficial: <b>{r['Resultado Oficial']}</b>
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )
        render_responsive_table(pd.DataFrame(discord_list), render_duel_discord_card, f"duel_{pkey_a}_{pkey_b}")
    else:
        st.caption("Os dois participantes concordaram em todos os palpites dos jogos bloqueados até o momento.")


def render_transparencia() -> None:
    render_page_header("Transparência", "Auditoria e Transparência do Bolão", "Validação pública dos parâmetros, bloqueios e regras operacionais.", "🛡️")
    
    ctx = load_app_data_cached()
    config = ctx.config
    matches = ctx.matches
    submissions = ctx.submissions

    st.markdown("#### ⚙️ Parâmetros Ativos de Pontuação")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Modo Clássico:**")
        st.write(f"- Método de cálculo: `{config.get('scoring_mode', 'v2').upper()}`")
        st.write(f"- Submissões clássicas travadas: `{'Sim' if config.get('classic_submissions_locked', False) or config.get('is_bolao_locked', False) else 'Não'}`")
    with col2:
        st.markdown("**Modo Jogo a Jogo:**")
        st.write(f"- Prazo de bloqueio individual: `{config.get('live_lock_minutes_before_match', 10)} minutos antes do jogo`")
        st.write(f"- Regra de acerto exato: `{config.get('live_scoring', {}).get('exact_score_mode', 'isolated_max')}`")

    # KPIs de Integridade
    kpi_items = [
        {"label": "Cadastros Clássicos", "value": str(len(submissions))},
        {"label": "Palpites Jogo a Jogo", "value": str(len(ctx.live_predictions))},
        {"label": "Eventos de Auditoria", "value": str(len(ctx.events))},
    ]
    render_kpi_grid(kpi_items)

    st.markdown("#### 🏁 Regras de Desempate (Ranking Oficial)")
    st.markdown(
        """
        Em caso de igualdade de pontos nos rankings, os critérios aplicados serão:
        1. **Modo Clássico:**
           * Maior pontuação obtida na fase de mata-mata.
           * Maior quantidade de acertos de placares exatos na fase de grupos.
           * Ordem cronológica de envio (palpite enviado primeiro vence).
        2. **Modo Jogo a Jogo:**
           * Maior quantidade de acertos de placares exatos.
           * Maior percentual de aproveitamento de palpites (hit rate).
           * Menor quantidade de palpites perdidos (esqueceu de palpitar).
        """
    )


def render_regras_do_bolao() -> None:
    render_page_header("Regras", "Regras e Como Funciona o Bolão", "Instruções completas para participar e pontuar nos dois modos.", "📖")

    config = load_config()
    ctx = load_app_data_cached()

    active_parts = load_registered_participants(include_archived=False)
    matches = ctx.matches
    total_live_preds = len(ctx.live_predictions)
    now = datetime.now().isoformat()
    open_count = len([m for m in matches if is_match_open_for_prediction(m, now)])
    pending_count = len([m for m in matches if m.status != "result_approved"])
    approved_count = len([m for m in matches if m.status == "result_approved"])

    mode_key = config.get("scoring_mode", "v2")
    mode_label = SCORING_MODE_OPTIONS.get(mode_key, mode_key)
    exact_mode_key = config.get("exact_score_mode", "isolated_max")
    exact_mode_label = SCORING_MODE_LABELS.get(exact_mode_key, exact_mode_key)
    live_scoring = config.get("live_scoring", {})
    lock_mins = int(config.get("live_lock_minutes_before_match", 10))

    st.markdown("### 📡 Status do Bolão — Transparente e em Tempo Real")
    st.caption("Informações atualizadas automaticamente. Sem segredos.")

    cols = st.columns(4)
    with cols[0]:
        st.metric("Participantes Ativos", len(active_parts))
    with cols[1]:
        st.metric("Jogos Abertos", open_count)
    with cols[2]:
        st.metric("Jogos Finalizados", approved_count)
    with cols[3]:
        st.metric("Palpites Enviados", total_live_preds)

    status_lock = "🔒 Fechado" if config.get("is_bolao_locked", False) else "✅ Aberto"
    deadline = config.get("submission_deadline", "") or "Sem prazo definido"
    status_label = config.get("status_label", "Recebendo palpites")

    st.info(
        f"**Status:** {status_label} | **Submissões Clássicas:** {status_lock} | "
        f"**Prazo:** {deadline} | "
        f"**Modo de Pontuação:** {mode_label} | "
        f"**Bloqueio Jogo a Jogo:** {lock_mins} min antes"
    )

    st.markdown("---")

    st.markdown(
        f"""
        ### 🏆 Dois Modos de Disputa Independentes e Paralelos
        
        O **Bolão da Cabine do Glória** oferece dois modos de participação. Você pode competir em apenas um deles, ou em ambos simultaneamente!
        
        ---
        
        ### 1. 📋 MODO CLÁSSICO
        Neste modo, você preenche a simulação completa da Copa do Mundo 2026 de uma só vez (grupos, classificados, mata-mata e o campeão):
        * **Preenchimento:** Realizado na aba **Palpite Clássico** antes do prazo final do bolão.
        * **Edição:** Permitida a qualquer momento enquanto as submissões clássicas estiverem abertas.
        * **Visualização dos outros:** Os palpites de todos os participantes do clássico serão revelados publicamente após o encerramento do prazo.
        * **Ranking:** Gera o **Ranking Clássico** baseado nas regras de acertos de posições, classificados e campeão.
        
        ---
        
        ### 2. ⚽ MODO JOGO A JOGO
        Palpite individualmente em cada partida da Copa:
        * **Preenchimento:** Na aba **Jogos de Hoje**, informe seus placares jogo por jogo.
        * **Prazos:** Você pode enviar ou alterar seu palpite até **{lock_mins} minutos antes** do início de cada partida.
        * **Privacidade:** Os palpites de um jogo ficam ocultos e só são revelados ao grupo após o bloqueio das apostas daquele jogo ({lock_mins} minutos antes do jogo começar).
        * **Ranking:** Gera o **Ranking Jogo a Jogo** focado na precisão de placares individuais.
        
        ---
        
        ### 📊 Critérios de Pontuação do Modo Jogo a Jogo

        Os pontos por partida no Modo Jogo a Jogo são calculados da seguinte forma:
        * **Placar Exato:** **{live_scoring.get('exact_score', 5)} pontos** (se acertar em cheio o placar exato).
        * **Resultado Correto (Vitória/Empate):** **{live_scoring.get('outcome', 3)} pontos** (se acertar o vencedor ou empate, mas errar o placar).
        * **Gols de um Time:** **{live_scoring.get('goal_one_team', 1)} ponto{'s' if live_scoring.get('goal_one_team', 1) != 1 else ''}** por time (se acertar a quantidade de gols marcada por um dos times).
        * **Saldo de Gols:** **{live_scoring.get('goal_difference', 1)} ponto{'s' if live_scoring.get('goal_difference', 1) != 1 else ''}** (se acertar a diferença de gols entre os times).

        **Modo de pontuação:** _{exact_mode_label}_
        """
    )

    v2_rules = config.get("v2_rules", dict(DEFAULT_V2_RULES))
    st.markdown(
        f"""
        ---
        
        ### 🏆 Pontuação do Modo Clássico (Fase de Grupos)
        
        Os pontos na fase de grupos seguem o sistema **{mode_label}**:
        
        | Critério | Pontos |
        |---|---|
        | Placar Exato | **{v2_rules.get('group_exact', 5)}** |
        | Resultado + Saldo de Gols | **{v2_rules.get('group_result_gd', 3)}** |
        | Apenas Resultado (Vencedor/Empate) | **{v2_rules.get('group_result', 2)}** |
        | Gols de um Time | **{v2_rules.get('group_team_goals', 1)}** |
        
        **Bônus criativos (cumulativos):** Soma de Gols (+{v2_rules.get('group_sum_goals', 0)}), Ambas Marcam (+{v2_rules.get('group_both_scored', 0)}), Mais de 2.5 Gols (+{v2_rules.get('group_over_2_5', 0)})
        
        ### 🏆 Pontuação do Modo Clássico (Mata-mata)
        
        | Fase | Pontos por time classificado |
        |---|---|
        | Oitavas de Final | **{v2_rules.get('ko_oitavas', 2)}** |
        | Quartas de Final | **{v2_rules.get('ko_quartas', 2)}** |
        | Semifinais | **{v2_rules.get('ko_semifinais', 3)}** |
        | Final | **{v2_rules.get('ko_final', 4)}** |
        | Campeão | **{v2_rules.get('ko_champion', 6)}** |
        
        ---
        
        ### 🥈 RANKING GERAL (Combinado)
        """
    )

    combined_enabled = config.get("combined_ranking_enabled", False)
    if combined_enabled:
        weights = config.get("combined_ranking_weights", {"classic": 1.0, "live": 1.0})
        st.markdown(
            f"O **Ranking Geral** está ativado! Pontuação = `(Clássico × {weights.get('classic', 1.0)}) + (Jogo a Jogo × {weights.get('live', 1.0)})`."
        )
    else:
        st.markdown(
            "O **Ranking Geral** está desativado no momento. Apenas os rankings isolados (Clássico e Jogo a Jogo) estão disponíveis."
        )

    st.markdown(
        """
        * Participantes que jogam apenas um modo aparecem com 0 pontos no outro modo.
        """
    )
