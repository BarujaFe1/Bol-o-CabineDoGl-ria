
from __future__ import annotations

import json
import os
from copy import deepcopy
from pathlib import Path

import pandas as pd
import streamlit as st

from src.bolao.api_service import APIFootballService
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
from src.bolao.ocr_groups import merge_ocr_results, run_group_ocr
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
)
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
)
from src.bolao.utils import decode_uploaded_file, norm_team, now_iso, stable_id
from src.bolao.validation import validate_prediction
from src.bolao.ui_simulator import render_simulator, init_simulator_state


st.set_page_config(
    page_title=f"{APP_NAME} · {APP_SUBTITLE}",
    page_icon="🏆",
    layout="wide",
    initial_sidebar_state="expanded",
)
inject_css()


def get_score_config() -> ScoreConfig:
    config = load_config()
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



def infer_best_thirds_from_knockout(pred: Prediction) -> list[str]:
    """Infere os melhores terceiros a partir dos times que aparecem na fase de 32.

    Como o print dos grupos do ge não mostra a lista dos 8 terceiros classificados,
    a forma mais segura é cruzar o 3º colocado de cada grupo com os times que
    aparecem em Décima-sextas no texto exportado pelo ge.
    """
    fase_32_teams = set()
    for match in pred.knockout.get("fase_32", []):
        if match.a:
            fase_32_teams.add(norm_team(match.a))
        if match.b:
            fase_32_teams.add(norm_team(match.b))
    thirds = []
    for group in GROUPS:
        values = pred.groups.get(group, [])
        third = values[2] if len(values) >= 3 else None
        if third and norm_team(third) in fase_32_teams:
            thirds.append(third)
    return thirds

def build_prediction_from_public_inputs(name: str, af_file, gl_file, knockout_text: str) -> Prediction:
    expected_1 = list("ABCDEF")
    expected_2 = list("GHIJKL")
    ocr_results = []
    meta = {"ocr": {}, "warnings": []}

    if af_file is not None:
        ocr_results.append(run_group_ocr(af_file.getvalue(), expected_1))
    if gl_file is not None:
        ocr_results.append(run_group_ocr(gl_file.getvalue(), expected_2))
    groups, ocr_meta = merge_ocr_results(ocr_results)
    meta["ocr"] = ocr_meta
    meta["warnings"].extend(ocr_meta.get("warnings", []))

    knockout, champion, issues, ko_meta = parse_ge_knockout_text(knockout_text)
    meta["knockout_parser"] = ko_meta
    meta["knockout_issues"] = [issue.__dict__ for issue in issues]
    pred = Prediction(
        participant=name.strip(),
        groups=groups,
        knockout=knockout,
        champion=champion,
        submission_id=stable_id(name, now_iso()),
        submitted_at=now_iso(),
        status="rascunho",
        meta=meta,
    )
    pred.best_thirds = infer_best_thirds_from_knockout(pred)
    if pred.best_thirds:
        pred.meta.setdefault("info", []).append(
            "Melhores terceiros inferidos automaticamente a partir da fase Décima-sextas."
        )
    return pred


def public_home() -> None:
    hero(
        title="Bolão da Cabine do Glória",
        subtitle="Copa do Mundo 2026",
        description="Faça seu palpite completo da Copa do Mundo 2026 diretamente pelo nosso simulador interativo.\n\nPreencha os placares da fase de grupos, acompanhe a classificação em tempo real, escolha os vencedores do mata-mata e envie seu palpite completo em poucos passos. Tudo acontece dentro do próprio sistema, sem prints, sem arquivos e sem complicação."
    )
    
    st.markdown("### Como funciona")
    step_cards()
    
    st.markdown("---")
    st.markdown("### Como a pontuação funciona")
    st.markdown(
        """
        Na fase de grupos, a pontuação considera os placares dos jogos. No mata-mata, a pontuação considera os classificados escolhidos em cada fase e o campeão. O ranking é atualizado conforme os resultados oficiais forem cadastrados e aprovados pela organização.
        """
    )
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🚀 Fazer meu palpite", type="primary", use_container_width=True):
            st.session_state["nav_page"] = "Fazer palpite"
            st.rerun()
    with col2:
        if st.button("📊 Ver ranking", use_container_width=True):
            st.session_state["nav_page"] = "Ranking"
            st.rerun()


def public_submission() -> None:
    hero("Fazer palpite", "Fluxo do participante", "Monte seu palpite completo da Copa do Mundo 2026 pelo simulador interativo.")

    st.markdown("### 1. Identificação")
    name = st.text_input("Seu nome no bolão", placeholder="Ex.: César", key="public_sim_name")
    
    if not name.strip():
        st.info("Informe seu nome para começar a simulação.")
        st.session_state.pop("sim_prediction", None)
        st.session_state.pop("simulator", None)
        st.session_state.pop("edit_mode", None)
        st.session_state.pop("show_delete_confirm", None)
        return

    name_clean = name.strip()
    config = load_config()
    is_locked = config.get("is_bolao_locked", False)
    
    # Load submissions to find match
    submissions = load_submissions()
    existing = [p for p in submissions if p.participant.strip().lower() == name_clean.lower()]
    
    # If the user hasn't selected an action yet, show the options screen
    if existing and "edit_mode" not in st.session_state:
        existing_pred = existing[0]
        
        if is_locked:
            st.warning(f"🔒 Os palpites estão bloqueados. Existe um palpite cadastrado para **{existing_pred.participant}**, mas novas submissões ou edições estão desabilitadas.")
            if st.button(f"🔍 Visualizar o palpite de {existing_pred.participant}", use_container_width=True):
                st.session_state["sim_prediction"] = existing_pred
                init_simulator_state(existing_pred, force_reset=True)
                st.session_state["edit_mode"] = "view"
                st.rerun()
        else:
            st.info(f"💡 Encontramos um palpite já enviado para **{existing_pred.participant}**.")
            col_btn1, col_btn2, col_btn3 = st.columns(3)
            with col_btn1:
                if st.button("✏️ Editar palpite existente", type="primary", use_container_width=True):
                    st.session_state["sim_prediction"] = existing_pred
                    init_simulator_state(existing_pred, force_reset=True)
                    st.session_state["edit_mode"] = "edit"
                    st.rerun()
            with col_btn2:
                if st.button("❌ Excluir meu palpite", use_container_width=True):
                    st.session_state["show_delete_confirm"] = True
                    st.rerun()
            with col_btn3:
                if st.button("🆕 Iniciar novo do zero", use_container_width=True):
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
                if st.button("Sim, excluir permanentemente", type="primary", use_container_width=True):
                    delete_submission(existing_pred.submission_id)
                    st.success("Seu palpite foi excluído do sistema.")
                    st.session_state.pop("sim_prediction", None)
                    st.session_state.pop("simulator", None)
                    st.session_state.pop("edit_mode", None)
                    st.session_state.pop("show_delete_confirm", None)
                    st.balloons()
                    st.rerun()
            with c_del2:
                if st.button("Cancelar", use_container_width=True):
                    st.session_state.pop("show_delete_confirm", None)
                    st.rerun()
        return

    if not existing and is_locked:
        st.error("🔒 Os palpites estão encerrados pelo administrador. Não é possível enviar novos palpites.")
        return

    # If new user and not initialized yet
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
        if st.button("Voltar", use_container_width=True):
            st.session_state.pop("sim_prediction", None)
            st.session_state.pop("simulator", None)
            st.session_state.pop("edit_mode", None)
            st.rerun()
    else:
        if edit_mode == "edit":
            st.info(f"✏️ Você está editando o palpite de **{pred.participant}**.")
            
        updated_pred = render_simulator(pred)
        
        if updated_pred:
            st.markdown("### 5. Enviar palpite")
            if edit_mode == "edit":
                st.caption("Ao confirmar, o palpite existente será atualizado com os novos resultados.")
                save_btn_text = "Salvar alterações no meu palpite"
            else:
                st.caption("Ao confirmar, o palpite será salvo no sistema.")
                save_btn_text = "Confirmar e salvar meu palpite"
                
            col_save1, col_save2 = st.columns(2)
            with col_save1:
                if st.button(save_btn_text, type="primary", key="btn_save_sim_prediction", use_container_width=True):
                    # Final check for locking status
                    config = load_config()
                    if config.get("is_bolao_locked", False):
                        st.error("🔒 O bolão foi bloqueado recentemente. Não é mais possível salvar ou editar palpites.")
                        return
                        
                    updated_pred.status = "confirmado"
                    updated_pred.submitted_at = now_iso()
                    save_submission(updated_pred)
                    
                    st.session_state.pop("sim_prediction", None)
                    st.session_state.pop("simulator", None)
                    st.session_state.pop("edit_mode", None)
                    
                    st.markdown(
                        f"""
<div class="success-card">
  <h3>Palpite enviado com sucesso</h3>
  <p>Guarde este código de envio:</p>
  <h2>{updated_pred.submission_id}</h2>
  <p class="small-muted">Seu palpite já está registrado. O ranking será atualizado quando o resultado oficial estiver aprovado pelo admin.</p>
</div>
                        """,
                        unsafe_allow_html=True,
                    )
                    st.balloons()
            with col_save2:
                if st.button("Descartar e voltar", use_container_width=True):
                    st.session_state.pop("sim_prediction", None)
                    st.session_state.pop("simulator", None)
                    st.session_state.pop("edit_mode", None)
                    st.rerun()


def public_ranking() -> None:
    hero("Ranking público", "Consulta dos participantes", "Acompanhe os participantes, a classificação geral e o detalhamento da pontuação após a aprovação dos resultados oficiais.")
    submissions = load_submissions()
    official = load_official()
    config = load_config()

    scoring_mode_label = config.get("scoring_mode", "v2")
    if scoring_mode_label == "v2":
        scoring_mode_text = "V2 (Placares + Classificados)"
    else:
        scoring_mode_text = scoring_mode_label.capitalize()

    kpi_grid([
        ("Status", config.get("status_label", "Recebendo palpites")),
        ("Participantes", str(len(submissions))),
        ("Resultado oficial", "Aprovado" if official else "Pendente"),
        ("Modo de pontuação", scoring_mode_text),
    ])

    if scoring_mode_label == "v2":
        st.caption("ℹ️ **Modo V2**: A fase de grupos pontua por placar exato, resultado ou gols; o mata-mata pontua pelos times classificados em cada fase e pelo campeão.")

    if not official:
        st.info("O resultado oficial ainda não foi aprovado pela organização. O ranking será consolidado após a aprovação. Por enquanto, os palpites enviados aparecem abaixo.")
        if submissions:
            st.dataframe(pd.DataFrame([{"Participante": p.participant, "Enviado em": p.submitted_at, "Código": p.submission_id} for p in submissions]), width="stretch", hide_index=True)
        else:
            st.info("Nenhum palpite enviado ainda. Seja o primeiro a participar.")
        return

    scores = rank_predictions(submissions, official, get_score_config())
    podium(scores)

    if scores:
        st.dataframe(ranking_to_dataframe(scores), width="stretch", hide_index=True)
        selected = st.selectbox("Ver detalhamento de participante", options=[s.participant for s in scores])
        score = next((s for s in scores if s.participant == selected), None)
        if score:
            st.dataframe(details_dataframe(score), width="stretch", hide_index=True)
    else:
        st.info("Nenhum palpite enviado ainda. Seja o primeiro a participar.")


def admin_dashboard() -> None:
    hero("Painel do admin", "Controle do bolão", "Gerencie participantes, resultado oficial, pontuação e exportações.")
    submissions = load_submissions()
    official = load_official()
    scores = rank_predictions(submissions, official, get_score_config()) if official else []
    kpi_grid([
        ("Participantes", str(len(submissions))),
        ("Resultado oficial", "Aprovado" if official else "Pendente"),
        ("Líder", scores[0].participant if scores else "—"),
        ("Pontuação do líder", str(scores[0].total) if scores else "—"),
    ])
    if scores:
        podium(scores)
    else:
        st.info("Carregue um resultado oficial para calcular o ranking.")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Carregar dados de demonstração", width="stretch"):
            load_demo_state()
            st.success("Demonstração carregada.")
            st.rerun()
    with col2:
        if st.button("Limpar estado atual", width="stretch"):
            reset_state()
            st.warning("Estado limpo.")
            st.rerun()


def admin_participants() -> None:
    st.markdown("## Participantes")
    submissions = load_submissions()
    if not submissions:
        st.info("Nenhum palpite confirmado ainda.")
        return
    df = pd.DataFrame([
        {"Nome": p.participant, "Código": p.submission_id, "Enviado em": p.submitted_at, "Campeã": p.champion}
        for p in submissions
    ])
    st.dataframe(df, width="stretch", hide_index=True)

    with st.expander("Ver/editar um participante"):
        selected = st.selectbox("Participante", options=[f"{p.participant} · {p.submission_id}" for p in submissions])
        pred = submissions[[f"{p.participant} · {p.submission_id}" for p in submissions].index(selected)]
        st.json(pred.to_dict(), expanded=False)
        if st.button("Excluir este palpite"):
            delete_submission(pred.submission_id)
            st.success("Palpite excluído.")
            st.rerun()


def make_prediction_from_text(name: str, text: str) -> Prediction:
    knockout, champion, issues, meta = parse_ge_knockout_text(text)
    pred = Prediction(participant=name, knockout=knockout, champion=champion, submission_id=stable_id(name, now_iso()), submitted_at=now_iso())
    pred.meta = {"knockout_parser": meta, "issues": [i.__dict__ for i in issues]}
    return pred


def admin_official_results() -> None:
    st.markdown("## Central de Resultados Oficiais")
    st.caption("Fluxo recomendado: preencher pelo simulador oficial ou sincronizar API → aprovar resultado oficial → recalcular ranking.")

    tabs = st.tabs(["Simulador Oficial (Recomendado)", "Texto/manual", "API", "Resultado aprovado"])

    with tabs[0]:
        st.markdown("### Preencher via Simulador Nativo")
        st.caption("Preencha os placares da fase de grupos e selecione os vencedores do mata-mata para o resultado oficial.")
        
        official_draft = load_official() or Prediction(participant="Resultado oficial")
        updated_official = render_simulator(official_draft, is_admin=True)
        
        if updated_official:
            st.markdown("### Aprovar Resultado")
            if st.button("Aprovar e salvar resultado oficial (Simulador)", type="primary", key="btn_save_official_sim", width="stretch"):
                updated_official.status = "aprovado"
                updated_official.submitted_at = now_iso()
                save_official(updated_official)
                
                st.session_state.pop("simulator", None)
                st.success("Resultado oficial aprovado e salvo a partir do simulador!")
                st.rerun()

    with tabs[1]:
        name = "Resultado oficial"
        official_text = st.text_area("Cole o texto oficial do mata-mata ou do simulador final", height=220, key="official_text")
        if st.button("Interpretar texto oficial", width="stretch", disabled=not official_text.strip()):
            st.session_state["official_draft"] = make_prediction_from_text(name, official_text)
            st.rerun()

        draft = st.session_state.get("official_draft") or load_official() or Prediction(participant="Resultado oficial")
        st.markdown("### Revisar resultado oficial")
        draft = apply_review_form("official_review", deepcopy(draft))
        if st.button("Aprovar e salvar resultado oficial", type="primary", width="stretch"):
            save_official(draft)
            st.success("Resultado oficial aprovado e salvo.")
            st.rerun()

    with tabs[2]:
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
        official = load_official()
        if not official:
            st.info("Nenhum resultado oficial aprovado.")
        else:
            st.success(f"Resultado aprovado em {official.submitted_at or 'data não registrada'}.")
            st.json(official.to_dict(), expanded=False)


def admin_ranking() -> None:
    st.markdown("## Ranking")
    submissions = load_submissions()
    official = load_official()
    if not official:
        st.info("Aprove o resultado oficial para calcular o ranking.")
        return
    scores = rank_predictions(submissions, official, get_score_config())
    podium(scores)
    if scores:
        st.dataframe(ranking_to_dataframe(scores), width="stretch", hide_index=True)
        selected = st.selectbox("Detalhamento", options=[s.participant for s in scores], key="admin_detail")
        score = next(s for s in scores if s.participant == selected)
        st.dataframe(details_dataframe(score), width="stretch", hide_index=True)
    else:
        st.info("Nenhum participante confirmado.")


def admin_exports() -> None:
    st.markdown("## Exportações")
    submissions = load_submissions()
    official = load_official()
    scores = rank_predictions(submissions, official, get_score_config()) if official else []

    col1, col2, col3 = st.columns(3)
    with col1:
        st.download_button("Baixar ranking CSV", data=ranking_csv(scores), file_name="ranking_bolao_cabine.csv", mime="text/csv", disabled=not bool(scores))
    with col2:
        st.download_button("Baixar ranking JSON", data=ranking_json(scores), file_name="ranking_bolao_cabine.json", mime="application/json", disabled=not bool(scores))
    with col3:
        st.download_button("Baixar backup completo", data=json.dumps(export_all_state(), ensure_ascii=False, indent=2), file_name="backup_bolao_cabine.json", mime="application/json")

    st.markdown("### Texto pronto para Discord")
    discord_text = discord_ranking(scores)
    st.text_area("Copiar texto", value=discord_text, height=260)

    st.markdown("### Share card do pódio")
    html_card = podium_html(scores) if scores else "<p>Sem ranking.</p>"
    st.download_button("Baixar HTML do pódio", data=html_card, file_name="podio_bolao_cabine.html", mime="text/html", disabled=not bool(scores))


def admin_settings() -> None:
    st.markdown("## Configurações")
    config = load_config()
    
    st.markdown("### Status & Acesso")
    config["is_bolao_locked"] = st.checkbox(
        "🔒 Bloquear envios e alterações de palpites",
        value=config.get("is_bolao_locked", False),
        help="Se marcado, novos palpites não poderão ser enviados, e palpites existentes não poderão ser editados ou excluídos."
    )
    config["status_label"] = st.text_input("Status público do bolão", value=config.get("status_label", "Recebendo palpites"))
    
    mode_options = ["v2", "ponderado", "uniforme"]
    current_mode = config.get("scoring_mode", "v2")
    if current_mode not in mode_options:
        current_mode = "v2"
    mode_idx = mode_options.index(current_mode)
    config["scoring_mode"] = st.radio("Modo de pontuação", mode_options, index=mode_idx, horizontal=True)

    st.markdown("### Pontuação V2 (Fase de Grupos & Mata-mata)")
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

    st.markdown("#### Regras Criativas (Bônus Cumulativos)")
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

    st.markdown("### Pontuação ponderada (Legado)")
    weighted = config.get("weighted_rules", dict(DEFAULT_WEIGHTED_RULES))
    cols = st.columns(3)
    for idx, key in enumerate(DEFAULT_WEIGHTED_RULES.keys()):
        with cols[idx % 3]:
            weighted[key] = st.number_input(key, min_value=0, max_value=50, value=int(weighted.get(key, DEFAULT_WEIGHTED_RULES[key])), step=1)
    config["weighted_rules"] = weighted

    st.markdown("### Pontuação uniforme (Legado)")
    uniform = config.get("uniform_rules", dict(DEFAULT_UNIFORM_RULES))
    uniform["decision_points"] = st.number_input("Pontos por decisão", min_value=1, max_value=50, value=int(uniform.get("decision_points", 1)), step=1)
    uniform["champion_bonus"] = st.number_input("Bônus da campeã", min_value=0, max_value=100, value=int(uniform.get("champion_bonus", 0)), step=1)
    config["uniform_rules"] = uniform

    if st.button("Salvar configurações", type="primary", width="stretch"):
        save_config(config)
        st.success("Configurações salvas.")


def admin_help() -> None:
    st.markdown("## Ajuda rápida")
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


def check_admin_auth() -> bool:
    try:
        has_secret = "ADMIN_PASSWORD" in st.secrets
    except Exception:
        has_secret = False

    if not has_secret:
        return True
    if st.session_state.get("admin_authenticated", False):
        return True

    st.markdown("### 🔒 Área Administrativa")
    st.caption("Esta área é protegida. Informe a senha configurada nos secrets.")
    password = st.text_input("Senha do admin", type="password", key="admin_password_input")
    if password:
        try:
            admin_pwd = st.secrets.get("ADMIN_PASSWORD")
        except Exception:
            admin_pwd = None
        if password == admin_pwd:
            st.session_state["admin_authenticated"] = True
            st.rerun()
        else:
            st.error("Senha incorreta.")
    return False


def main() -> None:
    with st.sidebar:
        st.markdown(f"## 🏆 {APP_NAME}")
        st.caption(APP_SUBTITLE)

        try:
            has_admin_password = "ADMIN_PASSWORD" in st.secrets
        except Exception:
            has_admin_password = False
        mode = st.radio("Área", ["Público", "Admin"], horizontal=True, disabled=has_admin_password and not st.session_state.get("admin_authenticated"))

        if "nav_page" not in st.session_state:
            st.session_state["nav_page"] = "Início"

        if mode == "Público":
            options = ["Início", "Fazer palpite", "Ranking"]
            try:
                idx = options.index(st.session_state["nav_page"])
            except ValueError:
                idx = 0
            page = st.radio("Navegação", options, index=idx, label_visibility="collapsed")
            st.session_state["nav_page"] = page
            show_admin = False
        else:
            if not check_admin_auth():
                st.warning("Faça login para acessar a área de admin.")
                return
            page = st.radio("Admin", ["Dashboard", "Participantes", "Resultados oficiais", "Ranking", "Exportações", "Configurações", "Ajuda"], label_visibility="collapsed")
            show_admin = True

    if show_admin:
        if page == "Dashboard":
            admin_dashboard()
        elif page == "Participantes":
            admin_participants()
        elif page == "Resultados oficiais":
            admin_official_results()
        elif page == "Ranking":
            admin_ranking()
        elif page == "Exportações":
            admin_exports()
        elif page == "Configurações":
            admin_settings()
        else:
            admin_help()
    else:
        if page == "Início":
            public_home()
        elif page == "Fazer palpite":
            public_submission()
        elif page == "Ranking":
            public_ranking()


if __name__ == "__main__":
    main()
