from __future__ import annotations

import streamlit as st
import pandas as pd
import csv
from io import StringIO
from datetime import datetime
from .models import LiveMatch
from .storage import load_matches, save_matches, load_live_predictions, save_live_predictions, append_event
from .utils import now_iso

def admin_matches_agenda() -> None:
    if st.button("⬅️ Voltar ao Painel Admin", key="back_to_dashboard_matches", width="stretch"):
        from .navigation import navigate_to
        navigate_to("Dashboard")
    st.markdown("### 📅 Jogos e Agenda — Modo Jogo a Jogo")
    st.caption("Cadastre jogos, gerencie a agenda da Copa, defina os horários oficiais e aprove os placares para pontuar os participantes.")

    tabs = st.tabs(["📋 Lista de Jogos", "➕ Cadastrar / Editar", "📤 Importar / Exportar", "🎯 Aprovar Resultados"])

    matches = load_matches()
    def get_sort_key(m):
        g = m.group or ""
        g_clean = g.strip().upper()
        if not g_clean or len(g_clean) > 1 or g_clean < 'A' or g_clean > 'L':
            group_key = "Z_Mata-Mata"
        else:
            group_key = f"Grupo {g_clean}"
        return (group_key, m.starts_at or "", m.sort_order)
    matches.sort(key=get_sort_key)

    # Tab 1: List
    with tabs[0]:
        st.markdown("#### Agenda Atual de Jogos")
        if not matches:
            st.info("Nenhum jogo cadastrado na agenda.")
        else:
            data = []
            for m in matches:
                data.append({
                    "ID": m.match_id,
                    "Fase": m.phase,
                    "Grupo": m.group or "—",
                    "Rodada": m.round_label,
                    "Jogo": f"{m.home_team} x {m.away_team}",
                    "Início": m.starts_at.replace("T", " ") if m.starts_at else "—",
                    "Bloqueio (Lock)": m.lock_at.replace("T", " ") if m.lock_at else "—",
                    "Status": m.status,
                    "Resultado": f"{m.official_home_goals} x {m.official_away_goals}" if m.official_home_goals is not None else "Aguardando"
                })
            df = pd.DataFrame(data)
            st.dataframe(df, width="stretch", hide_index=True)

    # Tab 2: Create / Edit
    with tabs[1]:
        st.markdown("#### Cadastrar ou Editar Jogo")
        
        # Select action
        action = st.radio("Ação", ["Novo Jogo", "Editar Existente"], horizontal=True, key="admin_match_action")
        
        match_to_edit = None
        if action == "Editar Existente":
            if not matches:
                st.warning("Não há jogos para editar.")
            else:
                match_options = [f"{m.match_id} : {m.home_team} x {m.away_team} ({m.round_label})" for m in matches]
                selected_opt = st.selectbox("Selecione o Jogo", options=match_options)
                selected_id = selected_opt.split(" : ")[0]
                match_to_edit = next(m for m in matches if m.match_id == selected_id)

        # Form fields
        with st.form("match_form", clear_on_submit=False):
            m_id = st.text_input("ID do Jogo (Único)", value=match_to_edit.match_id if match_to_edit else "", disabled=(action == "Editar Existente"))
            phase = st.selectbox("Fase", ["grupos", "fase_32", "oitavas", "quartas", "semifinais", "final"], index=["grupos", "fase_32", "oitavas", "quartas", "semifinais", "final"].index(match_to_edit.phase) if match_to_edit else 0)
            group = st.text_input("Grupo (se houver)", value=match_to_edit.group if match_to_edit else "")
            round_label = st.text_input("Rótulo da Rodada / Fase", value=match_to_edit.round_label if match_to_edit else "Rodada 1")
            
            col1, col2 = st.columns(2)
            with col1:
                home_team = st.text_input("Time Mandante", value=match_to_edit.home_team if match_to_edit else "")
            with col2:
                away_team = st.text_input("Time Visitante", value=match_to_edit.away_team if match_to_edit else "")
            
            starts_at_str = match_to_edit.starts_at if match_to_edit else "2026-06-11T16:00:00"
            starts_at = st.text_input("Início (Formato: YYYY-MM-DDTHH:MM:SS)", value=starts_at_str, help="Exemplo: 2026-06-11T16:00:00")
            timezone = st.text_input("Timezone do Jogo", value=match_to_edit.starts_at_timezone if match_to_edit else "America/Sao_Paulo")
            sort_order = st.number_input("Ordem de Exibição (Inteiro)", value=match_to_edit.sort_order if match_to_edit else 0, step=1)
            
            status = st.selectbox("Status do Jogo", ["scheduled", "locked", "live", "finished", "result_approved"], index=["scheduled", "locked", "live", "finished", "result_approved"].index(match_to_edit.status) if match_to_edit else 0)

            # Estádio & Custom Lock (F03 and custom match lock override)
            stadium = st.text_input("Estádio (🏟️ Venue)", value=match_to_edit.stadium if (match_to_edit and getattr(match_to_edit, "stadium", None)) else "")
            has_custom_lock = st.checkbox("Definir Horário de Fechamento Customizado?", value=match_to_edit.has_custom_lock if (match_to_edit and getattr(match_to_edit, "has_custom_lock", None) is not None) else False)
            lock_at_val = match_to_edit.lock_at if (match_to_edit and getattr(match_to_edit, "lock_at", None)) else "2026-06-11T15:50:00"
            lock_at_str = st.text_input("Fechamento Customizado (Formato: YYYY-MM-DDTHH:MM:SS)", value=lock_at_val, help="Exemplo: 2026-06-11T15:50:00")

            # Bets manual override selectbox
            bets_override_options = ["Padrão (Baseado no Horário)", "Forçar Aberto", "Forçar Fechado"]
            current_override = "Padrão (Baseado no Horário)"
            if match_to_edit and hasattr(match_to_edit, "bets_manual_closed") and match_to_edit.bets_manual_closed is not None:
                current_override = "Forçar Fechado" if match_to_edit.bets_manual_closed else "Forçar Aberto"
            bets_override = st.selectbox("Status das Apostas (Manual Override)", bets_override_options, index=bets_override_options.index(current_override))

            submitted = st.form_submit_button("Salvar Jogo", width="stretch")
            if submitted:
                if not m_id.strip() or not home_team.strip() or not away_team.strip():
                    st.error("Campos obrigatórios vazios (ID, Mandante, Visitante).")
                else:
                    try:
                        datetime.fromisoformat(starts_at)
                    except Exception:
                        st.error("Formato de data de início inválido. Use YYYY-MM-DDTHH:MM:SS.")
                        return

                    if has_custom_lock:
                        try:
                            datetime.fromisoformat(lock_at_str)
                        except Exception:
                            st.error("Formato de data de fechamento customizado inválido. Use YYYY-MM-DDTHH:MM:SS.")
                            return

                    bets_val = None
                    if bets_override == "Forçar Fechado":
                        bets_val = True
                    elif bets_override == "Forçar Aberto":
                        bets_val = False

                    # Create or update match object
                    new_match = LiveMatch(
                        match_id=m_id.strip(),
                        phase=phase,
                        group=group.strip(),
                        round_label=round_label.strip(),
                        home_team=home_team.strip(),
                        away_team=away_team.strip(),
                        starts_at=starts_at,
                        starts_at_timezone=timezone.strip(),
                        status=status,
                        sort_order=int(sort_order),
                        bets_manual_closed=bets_val,
                        has_custom_lock=has_custom_lock,
                        stadium=stadium.strip() if stadium.strip() else None,
                        lock_at=lock_at_str if has_custom_lock else None,
                        modo_relampago_ativo=match_to_edit.modo_relampago_ativo if match_to_edit else False,
                        placar_intervalo_mandante=match_to_edit.placar_intervalo_mandante if match_to_edit else None,
                        placar_intervalo_visitante=match_to_edit.placar_intervalo_visitante if match_to_edit else None,
                    )
                    
                    if match_to_edit:
                        # Copy results if editing and result was already filled
                        new_match.official_home_goals = match_to_edit.official_home_goals
                        new_match.official_away_goals = match_to_edit.official_away_goals
                        new_match.winner = match_to_edit.winner
                        new_match.source = match_to_edit.source
                        # Remove old version from matches list
                        matches = [m for m in matches if m.match_id != m_id]

                    matches.append(new_match)
                    save_matches(matches)
                    st.success(f"Jogo {new_match.home_team} x {new_match.away_team} salvo com sucesso!")
                    st.rerun()

    # Tab 3: Import / Export
    with tabs[2]:
        st.markdown("#### Importar Agenda via CSV")
        st.caption("O arquivo CSV deve conter o cabeçalho exato: `match_id,phase,group,round_label,home_team,away_team,starts_at,timezone,sort_order`")
        
        csv_file = st.file_uploader("Upload do CSV de Agenda", type=["csv"])
        if csv_file is not None:
            try:
                content = csv_file.getvalue().decode("utf-8")
                f = StringIO(content)
                reader = csv.DictReader(f)
                
                imported_matches = []
                for row in reader:
                    m = LiveMatch(
                        match_id=str(row["match_id"].strip()),
                        phase=row["phase"].strip(),
                        group=row["group"].strip(),
                        round_label=row["round_label"].strip(),
                        home_team=row["home_team"].strip(),
                        away_team=row["away_team"].strip(),
                        starts_at=row["starts_at"].strip(),
                        starts_at_timezone=row.get("timezone", "America/Sao_Paulo").strip(),
                        sort_order=int(row.get("sort_order", 0)),
                        status="scheduled"
                    )
                    imported_matches.append(m)

                if st.button("Confirmar Importação de Jogos", type="primary", width="stretch"):
                    # Merge imported matches (replace existing by ID)
                    existing_by_id = {m.match_id: m for m in matches}
                    for im in imported_matches:
                        existing_by_id[im.match_id] = im
                    
                    save_matches(list(existing_by_id.values()))
                    append_event("matches_imported", f"Importado {len(imported_matches)} jogos via arquivo CSV.", visibility="admin")
                    st.success(f"Agenda importada com sucesso! Total de {len(imported_matches)} jogos.")
                    st.rerun()
            except Exception as e:
                st.error(f"Erro ao analisar arquivo CSV: {str(e)}")

        st.markdown("---")
        st.markdown("#### Exportar Agenda")
        st.download_button(
            "Download da Agenda (JSON)",
            data=pd.Series([m.to_dict() for m in matches]).to_json(orient="records", indent=2),
            file_name="matches_copa_2026.json",
            mime="application/json",
            width="stretch"
        )

    # Tab 4: Results Approval
    with tabs[3]:
        st.markdown("#### Aprovação de Resultados e Recálculo de Pontos")
        st.caption("Insira o placar oficial de um jogo finalizado para calcular os pontos de todos os palpites recebidos.")

        # API-Football automated sync
        from .api_service import APIFootballService
        service = APIFootballService()
        if service.enabled():
            if st.button("🔄 Sincronizar Todos os Placares Automaticamente via API-Football", key="btn_sync_api_results_auto", type="primary", use_container_width=True):
                with st.spinner("Conectando ao API-Football e atualizando resultados..."):
                    res = service.sync_matches_scores_with_api()
                if res.ok:
                    st.success(res.message)
                    import time
                    time.sleep(1.0)
                    st.rerun()
                else:
                    st.error(res.message)
        else:
            st.info("💡 Para atualizar placares automaticamente via API, configure a chave APIFOOTBALL_KEY nas variáveis de ambiente ou nos Secrets.")
        
        st.markdown("---")

        pending_matches = [m for m in matches if m.status != "result_approved"]
        if not pending_matches:
            st.success("🎉 Todos os jogos cadastrados possuem resultados oficiais aprovados!")
        else:
            match_options = [f"{m.match_id} : {m.home_team} x {m.away_team} ({m.round_label})" for m in pending_matches]
            selected_opt = st.selectbox("Selecione o Jogo para Aprovar Resultado", options=match_options, key="approve_match_select")
            selected_id = selected_opt.split(" : ")[0]
            m = next(m for m in matches if m.match_id == selected_id)

            # F19 — Halftime / Lightning Mode Admin Controls
            st.markdown("##### ⚡ Modo Relâmpago (Intervalo)")
            is_active = getattr(m, "modo_relampago_ativo", False)
            if is_active:
                st.warning(f"O Modo Relâmpago está atualmente ATIVO para esta partida! (Intervalo em andamento)")
                col_c1, col_c2 = st.columns(2)
                with col_c1:
                    st.write(f"Placar do 1º tempo cadastrado: **{m.home_team} {m.placar_intervalo_mandante} × {m.placar_intervalo_visitante} {m.away_team}**")
                with col_c2:
                    if st.button("🔒 Fechar Intervalo", key=f"btn_close_interval_{m.match_id}", width="stretch"):
                        m.modo_relampago_ativo = False
                        save_matches(matches)
                        st.success("Intervalo fechado e Modo Relâmpago desativado!")
                        st.rerun()
            else:
                col_o1, col_o2 = st.columns(2)
                with col_o1:
                    pi_h = st.number_input(f"Gols {m.home_team} no 1º tempo", min_value=0, max_value=20, value=m.placar_intervalo_mandante if (getattr(m, "placar_intervalo_mandante", None) is not None) else 0, key=f"admin_pi_h_{m.match_id}")
                with col_o2:
                    pi_a = st.number_input(f"Gols {m.away_team} no 1º tempo", min_value=0, max_value=20, value=m.placar_intervalo_visitante if (getattr(m, "placar_intervalo_visitante", None) is not None) else 0, key=f"admin_pi_a_{m.match_id}")
                
                if st.button("⚡ Abrir Intervalo (Modo Relâmpago)", key=f"btn_open_interval_{m.match_id}", width="stretch"):
                    m.modo_relampago_ativo = True
                    m.placar_intervalo_mandante = int(pi_h)
                    m.placar_intervalo_visitante = int(pi_a)
                    save_matches(matches)
                    st.success("Modo Relâmpago ativado para esta partida!")
                    st.rerun()
            st.markdown("---")

            with st.form("approve_result_form"):
                st.markdown(f"##### {m.home_team} x {m.away_team}")
                st.caption(f"Início: {m.starts_at} · Status atual: {m.status}")
                
                col1, col2 = st.columns(2)
                with col1:
                    goals_h = st.number_input(f"Gols: {m.home_team}", min_value=0, max_value=20, value=0, step=1)
                with col2:
                    goals_a = st.number_input(f"Gols: {m.away_team}", min_value=0, max_value=20, value=0, step=1)
                
                submitted = st.form_submit_button("Aprovar Placar Oficial", width="stretch")
                if submitted:
                    if not m.home_team or not m.away_team or m.home_team.strip() == "" or m.away_team.strip() == "" or "definir" in m.home_team.lower() or "definir" in m.away_team.lower():
                        st.error("Erro: Não é possível aprovar placar oficial sem mandante e visitante preenchidos ou com times 'A definir'.")
                    else:
                        # Update match results
                        m.official_home_goals = int(goals_h)
                        m.official_away_goals = int(goals_a)
                        if goals_h > goals_a:
                            m.winner = m.home_team
                        elif goals_h < goals_a:
                            m.winner = m.away_team
                        else:
                            m.winner = "draw"
                        
                        m.status = "result_approved"
                        
                        # Update predictions score
                        all_preds = load_live_predictions()
                        config = st.session_state.get("bolao_config", None)
                        if config is None:
                            from .storage import load_config
                            config = load_config()

                        # Recalculate points for this match
                        from .live_scoring import calculate_live_prediction_points
                        match_preds = [p for p in all_preds if p.match_id == m.match_id]
                        
                        for p in match_preds:
                            res = calculate_live_prediction_points(p, m, config)
                            p.points = res["points"]
                            p.scoring_breakdown = res["breakdown"]
                            p.is_locked = True

                        # Save updated matches and predictions
                        save_matches(matches)
                        save_live_predictions(all_preds)
                        
                        # Log event
                        append_event(
                            kind="result_approved",
                            message=f"Resultado oficial aprovado: {m.home_team} {goals_h} x {goals_a} {m.away_team}. Pontos recalculados para {len(match_preds)} participantes.",
                            visibility="admin"
                        )
                        
                        st.success(f"Resultado de {m.home_team} {goals_h} x {goals_a} {m.away_team} aprovado! Pontos recalculados.")
                        st.cache_data.clear()
                        st.rerun()


def admin_palpites_jogo_a_jogo() -> None:
    if st.button("⬅️ Voltar ao Painel Admin", key="back_to_dashboard_palpites", width="stretch"):
        from .navigation import navigate_to
        navigate_to("Dashboard")
        
    st.markdown("### 🏟️ Palpites e Bloqueios Jogo a Jogo")
    st.caption("Gerencie e edite os palpites individuais dos participantes e controle o status dos bloqueios de cada partida.")

    # Load data
    matches = load_matches()
    live_preds = load_live_predictions()
    from .storage import load_registered_participants, upsert_live_prediction, save_live_predictions
    participants = load_registered_participants(include_archived=False)
    
    # Sort matches by group and chronological order
    def get_sort_key(m):
        g = m.group or ""
        g_clean = g.strip().upper()
        if not g_clean or len(g_clean) > 1 or g_clean < 'A' or g_clean > 'L':
            group_key = "Z_Mata-Mata"
        else:
            group_key = f"Grupo {g_clean}"
        return (group_key, m.starts_at or "", m.sort_order)
    matches.sort(key=get_sort_key)

    # Filters layout
    st.markdown("#### 🔍 Filtros Globais")
    col_f1, col_f2, col_f3, col_f4 = st.columns(4)
    
    # 1. Group Filter
    groups = sorted(list(set(m.group for m in matches if m.group)))
    with col_f1:
        group_filter = st.selectbox("Grupo", ["Todos"] + groups, key="admin_palpites_group_filter")
        
    # 2. Date Filter
    dates = sorted(list(set(m.starts_at.split("T")[0] for m in matches if m.starts_at)))
    with col_f2:
        date_filter = st.selectbox("Data", ["Todas"] + dates, key="admin_palpites_date_filter")
        
    # 3. Team Filter
    teams = sorted(list(set(m.home_team for m in matches).union(m.away_team for m in matches)))
    with col_f3:
        team_filter = st.selectbox("Seleção", ["Todas"] + teams, key="admin_palpites_team_filter")
        
    # 4. Person Filter
    participant_names = [p for p in participants]
    with col_f4:
        participant_filter = st.selectbox("Participante", ["Todos"] + participant_names, key="admin_palpites_person_filter")

    # Apply filters to matches
    filtered_matches = matches
    if group_filter != "Todos":
        filtered_matches = [m for m in filtered_matches if m.group == group_filter]
    if date_filter != "Todas":
        filtered_matches = [m for m in filtered_matches if m.starts_at and m.starts_at.startswith(date_filter)]
    if team_filter != "Todas":
        filtered_matches = [m for m in filtered_matches if m.home_team == team_filter or m.away_team == team_filter]

    # Map predictions by (participant_key, match_id)
    from .utils import normalize_participant_key
    preds_map = {(p.participant_key or normalize_participant_key(p.participant_name), p.match_id): p for p in live_preds}

    # Filtered participants
    selected_participants = participants
    if participant_filter != "Todos":
        selected_participants = [p for p in participants if p == participant_filter]

    st.markdown("---")
    
    # Admin Tabs
    tabs_admin = st.tabs(["📊 Tabela Geral", "⚙️ Controle por Jogo (Ligar/Desligar e Editar)"])
    
    with tabs_admin[0]:
        st.markdown("#### 📊 Tabela de Palpites Editável")
        st.caption("Dica: você pode filtrar os participantes ou os jogos usando os filtros globais acima antes de editar os palpites na tabela. Clique em 'Salvar Alterações na Tabela' após editar.")
        st.caption("Digite os palpites no formato **GolsMandante x GolsVisitante** (ex: `2x1` ou `0x0`). Deixe em branco para remover o palpite.")
        
        # Build pivot matrix dataframe
        # Rows: Matches
        # Columns: [match_id, Fase/Rodada, Jogo, Participant 1, Participant 2, ...]
        matrix_rows = []
        for m in filtered_matches:
            row_dict = {
                "match_id": m.match_id,
                "Grupo": f"Grupo {m.group}" if (m.group and m.group.strip()) else "Mata-Mata",
                "Fase/Rodada": m.round_label,
                "Jogo": f"{m.home_team} x {m.away_team}"
            }
            for p in selected_participants:
                pkey = normalize_participant_key(p)
                pred = preds_map.get((pkey, m.match_id))
                if pred and pred.predicted_home_goals is not None and pred.predicted_away_goals is not None:
                    row_dict[p] = f"{int(pred.predicted_home_goals)}x{int(pred.predicted_away_goals)}"
                else:
                    row_dict[p] = ""
            matrix_rows.append(row_dict)

        if not matrix_rows:
            st.info("Nenhum palpite ou jogo corresponde aos filtros selecionados.")
        else:
            df_matrix = pd.DataFrame(matrix_rows)
            
            # Configure streamlit data editor column configs
            col_configs = {
                "match_id": None,
                "Grupo": st.column_config.TextColumn("Grupo", disabled=True),
                "Fase/Rodada": st.column_config.TextColumn("Fase/Rodada", disabled=True),
                "Jogo": st.column_config.TextColumn("Jogo", disabled=True),
            }
            for p in selected_participants:
                col_configs[p] = st.column_config.TextColumn(p)
                
            edited_df = st.data_editor(
                df_matrix,
                column_config=col_configs,
                width="stretch",
                hide_index=True,
                key="admin_bulk_predictions_editor"
            )
            
            if st.button("💾 Salvar Alterações na Tabela", type="primary", key="btn_save_bulk_predictions", width="stretch"):
                import re
                
                def parse_placar(score_str: str) -> tuple[int, int] | None:
                    if not score_str:
                        return None
                    digits = re.findall(r'\d+', score_str)
                    if len(digits) == 2:
                        try:
                            return int(digits[0]), int(digits[1])
                        except ValueError:
                            return None
                    return None

                changes_count = 0
                
                # Check each cell for changes
                for idx, row in edited_df.iterrows():
                    orig_row = df_matrix.iloc[idx]
                    match_id = row["match_id"]
                    
                    for p in selected_participants:
                        new_val = str(row[p]).strip()
                        orig_val = str(orig_row[p]).strip()
                        
                        if new_val != orig_val:
                            if new_val == "":
                                # Delete prediction
                                all_preds = load_live_predictions(include_archived=True)
                                pkey = normalize_participant_key(p)
                                pred_id = f"{pkey}_{match_id}"
                                all_preds = [lp for lp in all_preds if lp.id != pred_id]
                                save_live_predictions(all_preds)
                                changes_count += 1
                            else:
                                parsed = parse_placar(new_val)
                                if parsed is not None:
                                    h_goals, a_goals = parsed
                                    upsert_live_prediction(
                                        participant_name=p,
                                        match_id=match_id,
                                        home_goals=h_goals,
                                        away_goals=a_goals
                                    )
                                    changes_count += 1
                                else:
                                    st.warning(f"Formato inválido para o palpite de {p} no jogo {row['Jogo']}: '{new_val}'. Use o formato 'Gols Mandante x Gols Visitante' (Ex: 2x1).")

                if changes_count > 0:
                    # Recalculate points for matches that are already approved
                    matches_by_id = {m.match_id: m for m in matches}
                    from .storage import load_config
                    from .live_scoring import calculate_live_prediction_points
                    
                    all_preds = load_live_predictions(include_archived=True)
                    cfg = load_config()
                    recalc_needed = False
                    
                    for idx, row in edited_df.iterrows():
                        orig_row = df_matrix.iloc[idx]
                        match_id = row["match_id"]
                        m = matches_by_id.get(match_id)
                        
                        if m and m.status == "result_approved":
                            # Check if any participant prediction for this match changed
                            match_changed = False
                            for p in selected_participants:
                                if str(row[p]).strip() != str(orig_row[p]).strip():
                                    match_changed = True
                                    break
                            
                            if match_changed:
                                for p in selected_participants:
                                    pkey = normalize_participant_key(p)
                                    updated_pred = next((lp for lp in all_preds if lp.id == f"{pkey}_{match_id}"), None)
                                    if updated_pred:
                                        res = calculate_live_prediction_points(updated_pred, m, cfg)
                                        updated_pred.points = res["points"]
                                        updated_pred.scoring_breakdown = res["breakdown"]
                                        updated_pred.is_locked = True
                                        recalc_needed = True
                    
                    if recalc_needed:
                        save_live_predictions(all_preds)
                    
                    st.success(f"Palpites atualizados com sucesso! Total de alterações salvas: {changes_count}")
                    st.cache_data.clear()
                    st.rerun()
                else:
                    st.info("Nenhuma alteração detectada na tabela.")

    with tabs_admin[1]:
        st.markdown("#### ⚙️ Controle Direto por Jogo")
        st.caption("Gerencie o fechamento de apostas (Ligar/Desligar) e edite os palpites de todos os participantes diretamente para cada partida.")
        
        if not filtered_matches:
            st.info("Nenhum jogo corresponde aos filtros selecionados.")
        else:
            for m in filtered_matches:
                # Estilo de cor baseado no status manual
                if m.bets_manual_closed is True:
                    status_text = "🔒 Fechado (Manual)"
                    border_color = "var(--red)"
                elif m.bets_manual_closed is False:
                    status_text = "🟢 Aberto (Manual)"
                    border_color = "var(--green)"
                else:
                    status_text = "⚙️ Automático"
                    border_color = "var(--line)"
                
                with st.container(border=True):
                    st.markdown(
                        f"""
                        <div style="border-left: 5px solid {border_color}; padding-left: 10px; margin-bottom: 8px;">
                            <h4 style="margin: 0; color: var(--ink);">⚽ {m.home_team} x {m.away_team} ({m.round_label})</h4>
                            <span style="font-size: 12px; color: var(--muted);">Início: {m.starts_at.replace('T', ' ')} | Bloqueio atual: <b>{status_text}</b></span>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
                    
                    # Lock Toggle buttons
                    col_b1, col_b2, col_b3 = st.columns(3)
                    with col_b1:
                        if st.button("🟢 Ligar (Forçar Aberto)", key=f"force_open_btn_{m.match_id}", width="stretch"):
                            m.bets_manual_closed = False
                            save_matches(matches)
                            append_event("match_lock_override", f"Partida {m.home_team} x {m.away_team} alterada para Forçar Aberto.", visibility="admin")
                            st.success("Apostas abertas!")
                            st.cache_data.clear()
                            st.rerun()
                    with col_b2:
                        if st.button("🔴 Desligar (Forçar Fechado)", key=f"force_close_btn_{m.match_id}", width="stretch"):
                            m.bets_manual_closed = True
                            save_matches(matches)
                            append_event("match_lock_override", f"Partida {m.home_team} x {m.away_team} alterada para Forçar Fechado.", visibility="admin")
                            st.success("Apostas fechadas!")
                            st.cache_data.clear()
                            st.rerun()
                    with col_b3:
                        if st.button("⚙️ Reset (Automático)", key=f"reset_lock_btn_{m.match_id}", width="stretch"):
                            m.bets_manual_closed = None
                            save_matches(matches)
                            append_event("match_lock_override", f"Partida {m.home_team} x {m.away_team} alterada para Automático.", visibility="admin")
                            st.success("Resetado para Automático!")
                            st.cache_data.clear()
                            st.rerun()
                            
                    # Table editor for this match's predictions
                    with st.expander("📝 Editar Palpites dos Participantes", expanded=False):
                        edit_data = []
                        for p in selected_participants:
                            pkey = normalize_participant_key(p)
                            pred = preds_map.get((pkey, m.match_id))
                            edit_data.append({
                                "Participante": p,
                                "Gols Mandante": int(pred.predicted_home_goals) if pred else 0,
                                "Gols Visitante": int(pred.predicted_away_goals) if pred else 0
                            })
                            
                        df_edit = pd.DataFrame(edit_data)
                        
                        edited_df = st.data_editor(
                            df_edit,
                            key=f"editor_preds_{m.match_id}",
                            num_rows="fixed",
                            width="stretch",
                            column_config={
                                "Participante": st.column_config.TextColumn("Participante", disabled=True),
                                "Gols Mandante": st.column_config.NumberColumn("Gols Mandante", min_value=0, max_value=20, step=1),
                                "Gols Visitante": st.column_config.NumberColumn("Gols Visitante", min_value=0, max_value=20, step=1)
                            }
                        )
                        
                        if st.button("💾 Salvar Palpites", key=f"btn_save_all_preds_{m.match_id}", width="stretch"):
                            for idx, row in edited_df.iterrows():
                                p_name = row["Participante"]
                                g_home = int(row["Gols Mandante"])
                                g_away = int(row["Gols Visitante"])
                                upsert_live_prediction(p_name, m.match_id, g_home, g_away)
                                
                            # Recalculate score if match is already approved
                            if m.status == "result_approved":
                                all_preds = load_live_predictions()
                                from .live_scoring import calculate_live_prediction_points
                                from .storage import load_config
                                cfg = load_config()
                                
                                for idx, row in edited_df.iterrows():
                                    p_name = row["Participante"]
                                    pkey = normalize_participant_key(p_name)
                                    updated_pred = next((lp for lp in all_preds if lp.id == f"{pkey}_{m.match_id}"), None)
                                    if updated_pred:
                                        res = calculate_live_prediction_points(updated_pred, m, cfg)
                                        updated_pred.points = res["points"]
                                        updated_pred.scoring_breakdown = res["breakdown"]
                                        updated_pred.is_locked = True
                                save_live_predictions(all_preds)
                                
                            append_event("prediction_edited_by_admin", f"Palpites da partida {m.home_team} x {m.away_team} editados em massa.", visibility="admin")
                            st.success("Todos os palpites salvos!")
                            st.cache_data.clear()
                            st.rerun()
