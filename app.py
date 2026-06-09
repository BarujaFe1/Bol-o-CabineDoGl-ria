
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
    render_page_header,
    render_empty_state,
    render_badge,
)
from src.bolao.utils import decode_uploaded_file, norm_team, now_iso, stable_id
from src.bolao.validation import validate_prediction, has_blocking_errors
from src.bolao.simulator_engine import validate_prediction_complete
from src.bolao.ui_simulator import render_simulator, init_simulator_state, get_guess_completion_state


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
    from src.bolao.ocr_groups import merge_ocr_results, run_group_ocr
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
    
    config = load_app_data_cached().config
    status = config.get("status_label", "Recebendo palpites")
    is_locked = config.get("is_bolao_locked", False)
    deadline = config.get("submission_deadline", "")
    badge_kind = "error" if is_locked else "success"
    status_badge = render_badge(status, badge_kind)

    st.markdown(
        f"""
        <div style="margin: 15px 0 25px 0; padding: 12px 18px; border-radius: 12px; background-color: #FFFDF8; border: 1px solid rgba(11, 51, 40, 0.15); display: inline-flex; align-items: center; gap: 10px; flex-wrap: wrap;">
            <span style="font-weight: bold; color: #0B3328;">Status do Bolão:</span> {status_badge}
            {f'<span style="margin-left: 20px; font-weight: bold; color: #0B3328;">Prazo Limite:</span> <span class="badge info">{html.escape(deadline)}</span>' if deadline else ''}
        </div>
        """,
        unsafe_allow_html=True
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
        if st.button("🚀 Fazer meu palpite", type="primary", width="stretch"):
            st.session_state["nav_page"] = "Fazer palpite"
            st.rerun()
    with col2:
        if st.button("📊 Ver ranking", width="stretch"):
            st.session_state["nav_page"] = "Ranking"
            st.rerun()


def public_submission() -> None:
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
            <div class="success-card" style="margin-bottom: 25px; padding: 25px; border-radius: 12px; background-color: #FFFDF8; border: 2px solid #D8A94A;">
                <div style="font-size: 48px; text-align: center;">🏆</div>
                <h3 style="text-align: center; color: #0B3328; margin-top: 10px;">Palpite Enviado com Sucesso!</h3>
                <p style="text-align: center; color: #66736D;">Seu palpite foi registrado no sistema. O ranking será atualizado quando a organização aprovar os resultados oficiais.</p>
                <hr style="border: 0; border-top: 1px solid #E6E6E6; margin: 20px 0;">
                <div style="text-align: center; margin-bottom: 15px;">
                    <span style="font-size: 14px; color: #66736D; text-transform: uppercase; letter-spacing: 1px;">Código de Confirmação</span>
                    <h2 style="color: #D8A94A; margin: 5px 0; font-family: monospace; letter-spacing: 2px; font-size: 28px;">{pred.submission_id}</h2>
                </div>
                <div style="display: flex; justify-content: space-around; background: #F5EBDD; padding: 15px; border-radius: 8px; border: 1px dashed #D8A94A; margin-bottom: 20px;">
                    <div style="text-align: center; flex: 1;">
                        <span style="font-size: 12px; color: #66736D;">Campeão</span>
                        <div style="font-weight: bold; color: #0B3328;">{champion}</div>
                    </div>
                    <div style="text-align: center; border-left: 1px solid #D8A94A; padding-left: 20px; flex: 1;">
                        <span style="font-size: 12px; color: #66736D;">Grande Final</span>
                        <div style="font-weight: bold; color: #0B3328;">{finalist_1} x {finalist_2}</div>
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
                st.session_state["nav_page"] = "Ranking"
                st.session_state.pop("last_submitted_prediction", None)
                st.rerun()
                
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🆕 Fazer outro palpite", width="stretch"):
            st.session_state.pop("last_submitted_prediction", None)
            st.rerun()
        return

    hero("Fazer palpite", "Fluxo do participante", "Monte seu palpite completo da Copa do Mundo 2026 pelo simulador interativo.")

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
    
    # Load submissions to find match
    submissions = ctx.submissions
    existing = [p for p in submissions if p.participant.strip().lower() == name_clean.lower()]
    
    # If the user hasn't selected an action yet, show the options screen
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
        if st.button("Voltar", width="stretch"):
            st.session_state.pop("sim_prediction", None)
            st.session_state.pop("sim_public", None)
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
                if st.button(save_btn_text, type="primary", key="btn_save_sim_prediction", width="stretch"):
                    # Final check for locking status
                    config = load_config()
                    if config.get("is_bolao_locked", False):
                        st.error("🔒 O bolão foi bloqueado recentemente. Não é mais possível salvar ou editar palpites.")
                        return
                    
                    # Validate completeness
                    missing = validate_prediction_complete(updated_pred)
                    if missing:
                        st.error("⚠️ Palpite incompleto. Verifique os itens abaixo:")
                        for item in missing:
                            st.markdown(f"- {item}")
                        return
                        
                    updated_pred.status = "confirmado"
                    updated_pred.submitted_at = now_iso()
                    save_submission(updated_pred)
                    
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
    hero("Ranking público", "Consulta dos participantes", "Acompanhe os participantes, a classificação geral e o detalhamento da pontuação após a aprovação dos resultados oficiais.")
    ctx = load_app_data_cached()
    submissions = ctx.submissions
    official = ctx.official
    config = ctx.config

    status = config.get("status_label", "Recebendo palpites")
    is_locked = config.get("is_bolao_locked", False)
    deadline = config.get("submission_deadline", "")
    badge_kind = "error" if is_locked else "success"
    status_badge = render_badge(status, badge_kind)

    st.markdown(
        f"""
        <div style="margin-bottom: 20px; padding: 12px 18px; border-radius: 12px; background-color: #FFFDF8; border: 1px solid rgba(11, 51, 40, 0.15); display: inline-flex; align-items: center; gap: 10px; flex-wrap: wrap;">
            <span style="font-weight: bold; color: #0B3328;">Status do Bolão:</span> {status_badge}
            {f'<span style="margin-left: 20px; font-weight: bold; color: #0B3328;">Prazo Limite:</span> <span class="badge info">{html.escape(deadline)}</span>' if deadline else ''}
        </div>
        """,
        unsafe_allow_html=True
    )

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
            if render_empty_state("Nenhum palpite enviado ainda", "Seja o primeiro a participar do bolão e provocar os amigos! Faça seu palpite e veja sua pontuação assim que o resultado oficial for aprovado.", "Fazer Palpite", "cta_empty_ranking_pub"):
                st.session_state["nav_page"] = "Fazer palpite"
                st.rerun()
        return

    scores = rank_predictions(submissions, official, get_score_config())
    podium(scores)

    if scores:
        search_rank_pub = st.text_input("🔍 Filtrar por nome", placeholder="Digite o nome...", key="rank_pub_search")
        filtered_scores_pub = [s for s in scores if search_rank_pub.lower() in s.participant.lower()] if search_rank_pub else scores
        st.dataframe(ranking_to_dataframe(filtered_scores_pub), width="stretch", hide_index=True)
        if filtered_scores_pub:
            selected = st.selectbox("Ver detalhamento de participante", options=[s.participant for s in filtered_scores_pub])
        score = next((s for s in scores if s.participant == selected), None)
        if score:
            st.dataframe(details_dataframe(score), width="stretch", hide_index=True)
            
        # Comparison Section
        st.markdown("<br>", unsafe_allow_html=True)
        with st.expander("⚖️ Comparar Palpites dos Amigos", expanded=False):
            col_comp1, col_comp2 = st.columns(2)
            with col_comp1:
                part_a = st.selectbox("Escolha o Participante A", options=[s.participant for s in scores], key="compare_a")
            with col_comp2:
                part_b = st.selectbox("Escolha o Participante B", options=[s.participant for s in scores], key="compare_b", index=min(1, len(scores)-1))
                
            if part_a and part_b:
                score_a = next(s for s in scores if s.participant == part_a)
                score_b = next(s for s in scores if s.participant == part_b)
                
                # Find the corresponding predictions from submissions
                pred_a = next(p for p in submissions if p.participant == part_a)
                pred_b = next(p for p in submissions if p.participant == part_b)
                
                # Compare Champion
                champ_a = pred_a.champion or "Indefinido"
                champ_b = pred_b.champion or "Indefinido"
                
                # Compare Finalists
                finalists_a = []
                ko_final_a = pred_a.knockout.get("final", [])
                if ko_final_a and len(ko_final_a) > 0:
                    if ko_final_a[0].a: finalists_a.append(ko_final_a[0].a)
                    if ko_final_a[0].b: finalists_a.append(ko_final_a[0].b)
                fin_a = " x ".join(finalists_a) if finalists_a else "Indefinido"
                
                finalists_b = []
                ko_final_b = pred_b.knockout.get("final", [])
                if ko_final_b and len(ko_final_b) > 0:
                    if ko_final_b[0].a: finalists_b.append(ko_final_b[0].a)
                    if ko_final_b[0].b: finalists_b.append(ko_final_b[0].b)
                fin_b = " x ".join(finalists_b) if finalists_b else "Indefinido"
                
                comp_data = [
                    {"Critério": "Pontuação Total", part_a: f"{score_a.total} pts", part_b: f"{score_b.total} pts"},
                    {"Critério": "Campeão Escolhido", part_a: champ_a, part_b: champ_b},
                    {"Critério": "Finalistas", part_a: fin_a, part_b: fin_b},
                    {"Critério": "Pontos em Grupos", part_a: f"{score_a.group_points} pts", part_b: f"{score_b.group_points} pts"},
                    {"Critério": "Pontos em Mata-mata", part_a: f"{score_a.knockout_points} pts", part_b: f"{score_b.knockout_points} pts"},
                    {"Critério": "Placares Exatos", part_a: f"{score_a.exact_scores} acertos", part_b: f"{score_b.exact_scores} acertos"},
                ]
                st.dataframe(pd.DataFrame(comp_data), width="stretch", hide_index=True)
                
                if champ_a != champ_b:
                    st.markdown(f"💡 **Divergência de Campeão:** {part_a} aposta em **{champ_a}**, enquanto {part_b} aposta em **{champ_b}**.")
                else:
                    st.markdown(f"🤝 Ambos apostam em **{champ_a}** como campeão!")
    else:
        if render_empty_state("Nenhum palpite enviado ainda", "Seja o primeiro a participar do bolão e dar seu palpite!", "Fazer Palpite", "cta_empty_ranking_pub_2"):
            st.session_state["nav_page"] = "Fazer palpite"
            st.rerun()

    st.markdown("---")
    st.markdown("### 📣 Últimas Atividades do Bolão")
    events = load_events(10)
    pub_events = [ev for ev in events if ev["kind"] in ("submission_saved", "official_saved")]
    if pub_events:
        for ev in pub_events:
            ts = ev["timestamp"].split("T")[0]
            st.markdown(f"⚽ `{ts}` — {ev['message']}")
    else:
        st.caption("Nenhuma atividade recente registrada.")


def admin_dashboard() -> None:
    hero("Painel do admin", "Controle do bolão", "Gerencie participantes, resultado oficial, pontuação e exportações.")
    ctx = load_app_data_cached()
    submissions = ctx.submissions
    official = ctx.official
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
        if render_empty_state("Sem ranking calculado", "O resultado oficial ainda não foi aprovado, por isso as pontuações do ranking não puderam ser calculadas.", "Aprovar Resultado", "cta_dashboard_results"):
            st.session_state["nav_page"] = "Resultados oficiais"
            st.rerun()

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Carregar dados de demonstração", width="stretch"):
            load_demo_state()
            st.success("Demonstração carregada.")
            st.rerun()
    with col2:
        if st.checkbox("⚠️ Desbloquear limpeza de estado", key="confirm_reset_state_chk"):
            st.markdown('<div class="warn-box" style="background-color:#FDE7E3; color:#B42318; padding:10px; border-radius:4px; margin-bottom:10px;"><strong>Atenção:</strong> Isso apagará permanentemente todos os palpites, resultado oficial e configurações. Esta ação é irreversível!</div>', unsafe_allow_html=True)
            confirm_word = st.text_input("Digite LIMPAR para confirmar:", key="confirm_reset_state_word")
            if st.button("🚨 Apagar todos os dados", type="primary", disabled=confirm_word != "LIMPAR", width="stretch"):
                reset_state()
                st.toast("Todo o estado foi reiniciado com sucesso.")
                st.rerun()

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
    render_page_header("Admin", "Participantes", "Gerencie os palpites enviados pelos participantes.", "👥")
    submissions = load_app_data_cached().submissions
    if not submissions:
        render_empty_state("Nenhum participante", "Não há palpites cadastrados no sistema no momento. Quando alguém enviar um palpite, ele aparecerá aqui.", "Ir para Resultados", "cta_participants_empty")
        return

    search_term = st.text_input("🔍 Buscar por nome", placeholder="Digite parte do nome...", key="part_search")
    filtered = [p for p in submissions if search_term.lower() in p.participant.lower()] if search_term else submissions

    if not filtered:
        st.info(f"Nenhum participante encontrado para \"{search_term}\".")
        return

    df = pd.DataFrame([
        {"Nome": p.participant, "Código": p.submission_id[:8] + "...", "Enviado em": p.submitted_at, "Campeã": p.champion or "—"}
        for p in filtered
    ])
    st.dataframe(df, width="stretch", hide_index=True)

    with st.expander("Ver/editar um participante"):
        selected = st.selectbox("Participante", options=[f"{p.participant} · {p.submission_id[:8]}..." for p in filtered], key="part_select")
        idx = [f"{p.participant} · {p.submission_id[:8]}..." for p in filtered].index(selected)
        pred = filtered[idx]
        st.json(pred.to_dict(), expanded=False)

        st.markdown(f'<div class="error-box" style="margin-top: 15px;"><strong>🚨 Zona de Perigo:</strong> Excluir o palpite de <strong>{pred.participant}</strong> é irreversível. Não há como recuperar os dados depois.</div>', unsafe_allow_html=True)
        confirm_word = st.text_input(f"Digite EXCLUIR para confirmar a exclusão de {pred.participant}:", key=f"confirm_word_{pred.submission_id}")
        if st.button("🚨 Excluir permanentemente", type="primary", disabled=confirm_word != "EXCLUIR", width="stretch"):
            delete_submission(pred.submission_id)
            st.success(f"Palpite de {pred.participant} excluído permanentemente.")
            st.rerun()


def make_prediction_from_text(name: str, text: str) -> Prediction:
    knockout, champion, issues, meta = parse_ge_knockout_text(text)
    pred = Prediction(participant=name, knockout=knockout, champion=champion, submission_id=stable_id(name, now_iso()), submitted_at=now_iso())
    pred.meta = {"knockout_parser": meta, "issues": [i.__dict__ for i in issues]}
    return pred


def admin_official_results() -> None:
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

            missing = validate_prediction_complete(updated_official)
            if missing:
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
    render_page_header("Admin", "Ranking", "Classificação completa com pontuações e detalhamento individual.", "📊")
    ctx = load_app_data_cached()
    submissions = ctx.submissions
    official = ctx.official
    if not official:
        st.info("Aprove o resultado oficial para calcular o ranking.")
        return
    scores = rank_predictions(submissions, official, get_score_config())
    podium(scores)
    if scores:
        search_rank = st.text_input("🔍 Filtrar por nome", placeholder="Digite o nome...", key="rank_admin_search")
        filtered_scores = [s for s in scores if search_rank.lower() in s.participant.lower()] if search_rank else scores
        st.dataframe(ranking_to_dataframe(filtered_scores), width="stretch", hide_index=True)
        if filtered_scores:
            selected = st.selectbox("Detalhamento", options=[s.participant for s in filtered_scores], key="admin_detail")
            score = next(s for s in filtered_scores if s.participant == selected)
            st.dataframe(details_dataframe(score), width="stretch", hide_index=True)
    else:
        st.info("Nenhum participante confirmado.")


def admin_exports() -> None:
    render_page_header("Admin", "Exportações", "Baixe dados do bolão em vários formatos.", "📦")
    ctx = load_app_data_cached()
    submissions = ctx.submissions
    official = ctx.official
    scores = rank_predictions(submissions, official, get_score_config()) if official else []

    st.markdown("### 📥 Arquivos para Download")
    st.caption("Escolha o formato mais adequado para sua necessidade.")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("**📄 CSV** — Planilha")
        st.caption("Tabela de classificação compatível com Excel, Google Sheets e afins.")
        st.download_button("Baixar ranking CSV", data=ranking_csv(scores), file_name="ranking_bolao_cabine.csv", mime="text/csv", disabled=not bool(scores), width="stretch")
    with col2:
        st.markdown("**📋 JSON** — Dados estruturados")
        st.caption("Formato estruturado para integração com APIs ou sistemas externos.")
        st.download_button("Baixar ranking JSON", data=ranking_json(scores), file_name="ranking_bolao_cabine.json", mime="application/json", disabled=not bool(scores), width="stretch")
    with col3:
        st.markdown("**💾 Backup** — Pacote completo")
        st.caption("Todos os dados (palpites, resultado oficial, configurações) em um arquivo.")
        st.download_button("Baixar backup completo", data=json.dumps(export_all_state(), ensure_ascii=False, indent=2), file_name="backup_bolao_cabine.json", mime="application/json", width="stretch")

    st.markdown("---")
    st.markdown("### 💬 Texto pronto para Discord")
    st.caption("Formatação automática para compartilhar o ranking no Discord do grupo.")
    if scores:
        discord_text = discord_ranking(scores)
        st.text_area("Conteúdo para copiar", value=discord_text, height=200, key="discord_text_area")

        st.caption("💡 Selecione o texto acima manualmente (Ctrl+C / ⌘+C) para compartilhar.")
    else:
        st.info("🔄 O ranking estará disponível para exportação após a aprovação do resultado oficial.")

    st.markdown("---")
    st.markdown("### 🏆 Share card do pódio")
    st.caption("HTML com visual premium para compartilhar em redes sociais, print ou story.")
    if scores:
        status_lbl = ctx.config.get("status_label", "Aprovado")
        html_card = podium_html(scores, status_label=status_lbl)
        st.download_button("Baixar HTML do pódio", data=html_card, file_name="podio_bolao_cabine.html", mime="text/html", width="stretch")
    else:
        st.info("🔄 O pódio será gerado após a aprovação do resultado oficial.")


def admin_settings() -> None:
    render_page_header("Admin", "Configurações", "Controle geral do bolão: status, pontuação e prazos.", "⚙️")
    config = load_app_data_cached().config
    
    st.markdown("### Status & Acesso")
    config["is_bolao_locked"] = st.checkbox(
        "🔒 Bloquear envios e alterações de palpites",
        value=config.get("is_bolao_locked", False),
        help="Se marcado, novos palpites não poderão ser enviados, e palpites existentes não poderão ser editados ou excluídos."
    )
    config["status_label"] = st.text_input("Status público do bolão", value=config.get("status_label", "Recebendo palpites"))
    config["submission_deadline"] = st.text_input(
        "Prazo Limite para Envios (Opcional)",
        value=config.get("submission_deadline", ""),
        help="Exemplo: 11/06/2026 15:00 ou deixe em branco se não houver prazo rígido."
    )
    
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


def main() -> None:
    if "nav_page" not in st.session_state:
        st.session_state["nav_page"] = "Início"
    if "admin_mode" not in st.session_state:
        st.session_state["admin_mode"] = False

    with st.sidebar:
        st.markdown(f"## 🏆 {APP_NAME}")
        st.caption(APP_SUBTITLE)
        st.markdown("---")

        if st.session_state.get("admin_authenticated", False) and st.session_state.get("admin_mode", False):
            # Admin Menu
            admin_options = ["Dashboard", "Participantes", "Resultados oficiais", "Ranking Admin", "Exportações", "Configurações", "Ajuda Admin"]
            current_page = st.session_state["nav_page"]
            if current_page not in admin_options:
                current_page = "Dashboard"
            idx = admin_options.index(current_page)
            page = st.radio("Admin Menu", admin_options, index=idx, label_visibility="collapsed")
            st.session_state["nav_page"] = page
            show_admin = True
        else:
            # Public Menu
            public_options = ["Início", "Fazer palpite", "Ranking"]
            current_page = st.session_state["nav_page"]
            if current_page not in public_options:
                idx = 0
            else:
                idx = public_options.index(current_page)
            page = st.radio("Navegação", public_options, index=idx, label_visibility="collapsed")
            if st.session_state["nav_page"] != "Admin Login":
                st.session_state["nav_page"] = page
            show_admin = False

        st.markdown("---")
        if st.session_state.get("admin_authenticated", False):
            if st.session_state.get("admin_mode", False):
                if st.button("🌐 Ver Modo Público", width="stretch"):
                    st.session_state["admin_mode"] = False
                    st.session_state["nav_page"] = "Início"
                    st.rerun()
            else:
                if st.button("🛠️ Painel Admin", width="stretch"):
                    st.session_state["admin_mode"] = True
                    st.session_state["nav_page"] = "Dashboard"
                    st.rerun()
            
            if st.button("🚪 Sair do Admin", width="stretch"):
                st.session_state["admin_authenticated"] = False
                st.session_state["admin_mode"] = False
                st.session_state["nav_page"] = "Início"
                st.rerun()
        else:
            if st.button("🔒 Área Admin", width="stretch", key="sidebar_admin_login_btn"):
                st.session_state["nav_page"] = "Admin Login"
                st.rerun()

    # Route display
    if st.session_state["nav_page"] == "Admin Login":
        st.markdown("### 🔒 Área Administrativa")
        st.caption("Esta área é protegida. Informe a senha configurada nos secrets.")
        
        # We inline the login check to keep a back button
        try:
            has_secret = "ADMIN_PASSWORD" in st.secrets
        except Exception:
            has_secret = False

        if not has_secret:
            st.session_state["admin_authenticated"] = True
            st.session_state["admin_mode"] = True
            st.session_state["nav_page"] = "Dashboard"
            st.success("Desenvolvimento local: Senha não configurada. Acesso liberado.")
            st.rerun()
        else:
            password = st.text_input("Senha do admin", type="password", key="admin_password_input_page")
            if password:
                admin_pwd = st.secrets.get("ADMIN_PASSWORD")
                if password == admin_pwd:
                    st.session_state["admin_authenticated"] = True
                    st.session_state["admin_mode"] = True
                    st.session_state["nav_page"] = "Dashboard"
                    st.success("Login efetuado com sucesso!")
                    st.rerun()
                else:
                    st.error("Senha incorreta.")
                    
        st.markdown("---")
        if st.button("Voltar ao Início", width="stretch"):
            st.session_state["nav_page"] = "Início"
            st.rerun()
        return

    if show_admin:
        page = st.session_state["nav_page"]
        if page == "Dashboard":
            admin_dashboard()
        elif page == "Participantes":
            admin_participants()
        elif page == "Resultados oficiais":
            admin_official_results()
        elif page == "Ranking Admin":
            admin_ranking()
        elif page == "Exportações":
            admin_exports()
        elif page == "Configurações":
            admin_settings()
        else:
            admin_help()
    else:
        page = st.session_state["nav_page"]
        if page == "Início":
            public_home()
        elif page == "Fazer palpite":
            public_submission()
        elif page == "Ranking":
            public_ranking()


if __name__ == "__main__":
    main()
