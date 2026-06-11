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
    st.markdown("### 📅 Jogos e Agenda — Modo Jogo a Jogo")
    st.caption("Cadastre jogos, gerencie a agenda da Copa, defina os horários oficiais e aprove os placares para pontuar os participantes.")

    tabs = st.tabs(["📋 Lista de Jogos", "➕ Cadastrar / Editar", "📤 Importar / Exportar", "🎯 Aprovar Resultados"])

    matches = load_matches()
    # Sort matches by starts_at and sort_order
    matches.sort(key=lambda m: (m.starts_at or "", m.sort_order))

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
                        sort_order=int(sort_order)
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
                    append_event("matches_imported", f"Importado {len(imported_matches)} jogos via arquivo CSV.")
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

        pending_matches = [m for m in matches if m.status != "result_approved"]
        if not pending_matches:
            st.success("🎉 Todos os jogos cadastrados possuem resultados oficiais aprovados!")
        else:
            match_options = [f"{m.match_id} : {m.home_team} x {m.away_team} ({m.round_label})" for m in pending_matches]
            selected_opt = st.selectbox("Selecione o Jogo para Aprovar Resultado", options=match_options, key="approve_match_select")
            selected_id = selected_opt.split(" : ")[0]
            m = next(m for m in matches if m.match_id == selected_id)

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
                        message=f"Resultado oficial aprovado: {m.home_team} {goals_h} x {goals_a} {m.away_team}. Pontos recalculados para {len(match_preds)} participantes."
                    )
                    
                    st.success(f"Resultado de {m.home_team} {goals_h} x {goals_a} {m.away_team} aprovado! Pontos recalculados.")
                    st.cache_data.clear()
                    st.rerun()
