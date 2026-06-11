
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
from src.bolao.migrations import migrate_existing_submissions_to_classic_schema


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
    from src.bolao.storage import load_app_data_cached, load_events
    from src.bolao.ui_live_matches import is_match_open_for_prediction
    import datetime
    import html

    hero(
        title="Bolão da Copa 2026",
        subtitle="Cabine do Glória",
        description="Evolua seu engajamento! Agora você pode participar de dois modos simultâneos de bolão: o Modo Clássico (cartela preenchida antes do início da Copa) e o Novo Modo Jogo a Jogo (palpites individuais partida por partida até 10 minutos antes do início)."
    )

    ctx = load_app_data_cached()
    config = ctx.config
    matches = ctx.matches

    # Banner for today's matches
    now = datetime.datetime.now().isoformat()
    open_today = []
    for m in matches:
        if is_match_open_for_prediction(m, now):
            try:
                starts_dt = datetime.datetime.fromisoformat(m.starts_at)
                today_dt = datetime.datetime.now()
                if starts_dt.date() == today_dt.date():
                    open_today.append(m)
            except Exception:
                pass
    
    if open_today:
        st.markdown(
            f"""
            <div style="background-color: #E6D2B5; border: 2px solid #D8A94A; border-radius: 16px; padding: 16px 20px; margin-bottom: 25px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 15px;">
                <div>
                    <h4 style="margin: 0; color: #0B3328;">🔥 Há jogos abertos hoje!</h4>
                    <p style="margin: 5px 0 0; color: #72541A; font-size: 14px;">Você tem <b>{len(open_today)}</b> partida(s) para palpitar hoje no Modo Jogo a Jogo.</p>
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )
        if st.button("🎯 Palpitar agora nos Jogos de Hoje", type="primary", key="btn_home_banner_jogos", width="stretch"):
            st.session_state["nav_page"] = "Jogos de Hoje"
            st.rerun()

    # Layout for two modes
    col_c1, col_c2 = st.columns(2)

    with col_c1:
        st.markdown(
            f"""
            <div style="border: 1px solid rgba(11, 51, 40, 0.12); padding: 20px; border-radius: 20px; background-color: #FFFDF8; height: 100%; display: flex; flex-direction: column; justify-content: space-between; box-shadow: 0 4px 12px rgba(11, 51, 40, 0.03);">
                <div>
                    <div style="font-size: 32px; margin-bottom: 10px;">📋</div>
                    <h3 style="color: #0B3328; margin: 0 0 10px 0;">Modo Clássico</h3>
                    <p style="color: #66736D; font-size: 14px; margin-bottom: 15px;">
                        O modo clássico tradicional do bolão. Cada participante preenche o palpite completo da Copa (grupos, chaveamento de mata-mata e campeão) uma única vez antes de a bola rolar.
                    </p>
                    <div style="margin-bottom: 20px;">
                        <span style="font-weight: bold; color: #0B3328;">Status:</span>
                        {'<span class="badge error">🔒 Encerrado</span>' if config.get("is_bolao_locked", False) else '<span class="badge success">🟢 Aberto</span>'}
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )
        if not config.get("is_bolao_locked", False):
            if st.button("🚀 Preencher Cartela Clássica", key="btn_home_classic_guess", type="primary", width="stretch"):
                st.session_state["nav_page"] = "Fazer palpite"
                st.rerun()
        else:
            if st.button("🔍 Ver Palpites Enviados", key="btn_home_classic_view", width="stretch"):
                st.session_state["nav_page"] = "Ranking"
                st.rerun()

    with col_c2:
        st.markdown(
            f"""
            <div style="border: 1px solid rgba(11, 51, 40, 0.12); padding: 20px; border-radius: 20px; background-color: #FFFDF8; height: 100%; display: flex; flex-direction: column; justify-content: space-between; box-shadow: 0 4px 12px rgba(11, 51, 40, 0.03);">
                <div>
                    <div style="font-size: 32px; margin-bottom: 10px;">🎯</div>
                    <h3 style="color: #0B3328; margin: 0 0 10px 0;">Modo Jogo a Jogo</h3>
                    <p style="color: #66736D; font-size: 14px; margin-bottom: 15px;">
                        A grande novidade! Palpite no placar de cada jogo individualmente ao longo da Copa até 10 minutos antes do início de cada partida. Tem ranking próprio e pontuação independente.
                    </p>
                    <div style="margin-bottom: 20px;">
                        <span style="font-weight: bold; color: #0B3328;">Status:</span>
                        {'<span class="badge success">🟢 Disponível</span>' if config.get("live_mode_enabled", True) else '<span class="badge error">🔒 Suspenso</span>'}
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )
        if config.get("live_mode_enabled", True):
            if st.button("⚡ Ir para Jogos de Hoje", key="btn_home_live_guess", type="primary", width="stretch"):
                st.session_state["nav_page"] = "Jogos de Hoje"
                st.rerun()
        else:
            st.info("O Modo Jogo a Jogo está suspenso no momento.")

    st.markdown("<br>", unsafe_allow_html=True)
    col_h1, col_h2 = st.columns(2)
    with col_h1:
        if st.button("📋 Minha Cartela Completa", key="btn_home_my_cartela", width="stretch"):
            st.session_state["nav_page"] = "Minha Cartela"
            st.rerun()
    with col_h2:
        if st.button("🏆 Classificações & Rankings", key="btn_home_rankings", width="stretch"):
            st.session_state["nav_page"] = "Ranking"
            st.rerun()

    # Activity Feed
    if config.get("public_show_activity_feed", True):
        st.markdown("---")
        st.markdown("### 📣 Feed de Atividades")
        events = load_events(limit=15, visibility="public")
        if events:
            for ev in events:
                ts = ev["timestamp"].split("T")[0]
                time = ev["timestamp"].split("T")[1][:5]
                st.markdown(f"🗓️ `{ts} {time}` · {ev['message']}")
        else:
            st.caption("Nenhum evento registrado ainda.")


def public_submission() -> None:
    if st.button("⬅️ Voltar ao Início", key="back_to_home_submission"):
        st.session_state["nav_page"] = "Início"
        st.rerun()
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
                    is_complete, missing = validate_prediction_complete(updated_pred)
                    if not is_complete:
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
    if st.button("⬅️ Voltar ao Início", key="back_to_home_ranking"):
        st.session_state["nav_page"] = "Início"
        st.rerun()
    from src.bolao.ui_ranking import render_rankings_tabs
    render_rankings_tabs(is_admin=False)


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

            is_complete, missing = validate_prediction_complete(updated_official)
            if not is_complete:
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
    from src.bolao.ui_ranking import render_rankings_tabs
    render_rankings_tabs(is_admin=True)


def admin_exports() -> None:
    render_page_header("Admin", "Exportações", "Baixe dados do bolão em vários formatos.", "📦")
    
    from src.bolao.storage import load_app_data_cached, export_all_state
    from src.bolao.live_scoring import calculate_live_ranking
    from src.bolao.utils import normalize_participant_key
    from src.bolao.social import build_ranking_share_text, build_live_daily_share_text
    from src.bolao.exporters import live_podium_html
    from src.bolao.ui_live_matches import is_match_open_for_prediction

    ctx = load_app_data_cached()
    submissions = ctx.submissions
    official = ctx.official
    
    scores = rank_predictions(submissions, official, get_score_config()) if official else []
    live_scores = calculate_live_ranking(ctx.live_predictions, ctx.matches, ctx.config)

    # Combined ranking calculation
    classic_weights = ctx.config.get("combined_ranking_weights", {}).get("classic", 1.0)
    live_weights = ctx.config.get("combined_ranking_weights", {}).get("live", 1.0)
    
    classic_dict = {normalize_participant_key(s.participant): s for s in scores}
    live_dict = {s["participant_key"]: s for s in live_scores}
    all_keys = set(classic_dict.keys()).union(live_dict.keys())
    
    combined_list = []
    for pkey in all_keys:
        c_score = classic_dict.get(pkey)
        l_score = live_dict.get(pkey)
        
        name = c_score.participant if c_score else (l_score["participant"] if l_score else "—")
        c_pts = c_score.total if c_score else 0
        l_pts = l_score["total"] if l_score else 0
        
        combined_pts = c_pts * classic_weights + l_pts * live_weights
        
        combined_list.append({
            "participant": name,
            "classic_points": c_pts,
            "live_points": l_pts,
            "total": combined_pts
        })
    combined_list.sort(key=lambda s: (-s["total"], -s["classic_points"], -s["live_points"], s["participant"].lower()))

    # Build DataFrames
    live_df = pd.DataFrame([{
        "Posição": s["position"],
        "Participante": s["participant"],
        "Pontos": s["total"],
        "Placares Exatos": s["exact_scores"],
        "Acertos Vencedor": s["outcomes"],
        "Palpites Salvos": s["predictions_count"],
        "Palpites Perdidos": s["missed_predictions"],
        "Aproveitamento": f"{int(s['hit_rate'] * 100)}%"
    } for s in live_scores]) if live_scores else pd.DataFrame()

    comb_df = pd.DataFrame([{
        "Posição": idx,
        "Participante": s["participant"],
        "Pontos Clássico": s["classic_points"],
        "Pontos Jogo a Jogo": s["live_points"],
        "Pontos Combinados": s["total"]
    } for idx, s in enumerate(combined_list, start=1)]) if combined_list else pd.DataFrame()

    exp_tabs = st.tabs(["📥 Planilhas e Dados", "🏆 Pódios HTML", "💬 WhatsApp / Social"])

    with exp_tabs[0]:
        st.markdown("### Exportar Planilhas (CSV)")
        c_cols = st.columns(3)
        with c_cols[0]:
            st.download_button(
                "Baixar Ranking Clássico (CSV)",
                data=ranking_csv(scores),
                file_name="ranking_classico.csv",
                mime="text/csv",
                disabled=not bool(scores),
                width="stretch"
            )
        with c_cols[1]:
            st.download_button(
                "Baixar Ranking Jogo a Jogo (CSV)",
                data=live_df.to_csv(index=False) if not live_df.empty else "",
                file_name="ranking_jogo_a_jogo.csv",
                mime="text/csv",
                disabled=live_df.empty,
                width="stretch"
            )
        with c_cols[2]:
            st.download_button(
                "Baixar Ranking Geral Combinado (CSV)",
                data=comb_df.to_csv(index=False) if not comb_df.empty else "",
                file_name="ranking_geral_combinado.csv",
                mime="text/csv",
                disabled=comb_df.empty,
                width="stretch"
            )

        st.markdown("---")
        st.markdown("### Backups de Segurança (JSON)")
        j_cols = st.columns(3)
        with j_cols[0]:
            st.download_button(
                "Baixar Backup Geral Completo (JSON)",
                data=json.dumps(export_all_state(), ensure_ascii=False, indent=2),
                file_name="backup_geral_completo.json",
                mime="application/json",
                width="stretch"
            )
        with j_cols[1]:
            st.download_button(
                "Baixar Palpites Jogo a Jogo (JSON)",
                data=json.dumps([p.to_dict() for p in ctx.live_predictions], ensure_ascii=False, indent=2),
                file_name="live_predictions.json",
                mime="application/json",
                width="stretch"
            )
        with j_cols[2]:
            st.download_button(
                "Baixar Agenda de Jogos (JSON)",
                data=json.dumps([m.to_dict() for m in ctx.matches], ensure_ascii=False, indent=2),
                file_name="matches_agenda.json",
                mime="application/json",
                width="stretch"
            )

    with exp_tabs[1]:
        st.markdown("### Compartilhar Cartazes de Pódio (HTML)")
        st.caption("Baixe arquivos HTML com visual moderno e premium para impressão ou print de redes sociais.")
        p_cols = st.columns(2)
        with p_cols[0]:
            status_lbl = ctx.config.get("status_label", "Aprovado")
            html_classic = podium_html(scores, status_label=status_lbl) if scores else ""
            st.download_button(
                "Baixar Pódio Clássico (HTML)",
                data=html_classic,
                file_name="podio_classico.html",
                mime="text/html",
                disabled=not bool(scores),
                width="stretch"
            )
        with p_cols[1]:
            html_live = live_podium_html(live_scores, status_label=status_lbl) if live_scores else ""
            st.download_button(
                "Baixar Pódio Jogo a Jogo (HTML)",
                data=html_live,
                file_name="podio_jogo_a_jogo.html",
                mime="text/html",
                disabled=not bool(live_scores),
                width="stretch"
            )

    with exp_tabs[2]:
        st.markdown("### Textos Prontos para WhatsApp")
        
        st.markdown("#### 🏆 Classificação de Rankings")
        ranking_text = build_ranking_share_text(scores, live_scores)
        st.text_area("Texto Classificação", value=ranking_text, height=120, key="txt_area_rank_whatsapp")
        
        st.markdown("#### 📅 Próximos Jogos de Hoje")
        import datetime
        now_str = datetime.datetime.now().isoformat()
        today_open_matches = [m for m in ctx.matches if m.status != "result_approved" and is_match_open_for_prediction(m, now_str)]
        today_open_matches.sort(key=lambda m: m.starts_at)
        daily_text = build_live_daily_share_text(today_open_matches)
        st.text_area("Texto Jogos do Dia", value=daily_text, height=120, key="txt_area_daily_whatsapp")


def admin_settings() -> None:
    render_page_header("Admin", "Configurações", "Controle geral do bolão: status, pontuação e prazos.", "⚙️")
    config = load_app_data_cached().config
    
    st.markdown("### Status & Acesso")
    config["is_bolao_locked"] = st.checkbox(
        "🔒 Bloquear envios e alterações de palpites clássicos",
        value=config.get("is_bolao_locked", False),
        help="Se marcado, novos palpites clássicos não poderão ser enviados, e palpites existentes não poderão ser editados ou excluídos."
    )
    config["status_label"] = st.text_input("Status público do bolão", value=config.get("status_label", "Recebendo palpites"))
    config["submission_deadline"] = st.text_input(
        "Prazo Limite para Envios Clássicos (Opcional)",
        value=config.get("submission_deadline", ""),
        help="Exemplo: 11/06/2026 15:00 ou deixe em branco se não houver prazo rígido."
    )
    
    mode_options = ["v2", "ponderado", "uniforme"]
    current_mode = config.get("scoring_mode", "v2")
    if current_mode not in mode_options:
        current_mode = "v2"
    mode_idx = mode_options.index(current_mode)
    config["scoring_mode"] = st.radio("Modo de pontuação do Clássico", mode_options, index=mode_idx, horizontal=True)

    st.markdown("### Configurações do Jogo a Jogo")
    config["classic_enabled"] = st.checkbox("Modo Clássico Ativado", value=config.get("classic_enabled", True))
    config["live_mode_enabled"] = st.checkbox("Modo Jogo a Jogo Ativado", value=config.get("live_mode_enabled", True))
    config["combined_ranking_enabled"] = st.checkbox("Ranking Geral Combinado Ativado", value=config.get("combined_ranking_enabled", False))
    config["live_lock_minutes_before_match"] = st.number_input(
        "Bloquear palpites jogo a jogo X minutos antes do início do jogo",
        min_value=0, max_value=1440,
        value=int(config.get("live_lock_minutes_before_match", 10)),
        step=1
    )
    
    st.markdown("#### Pontuação Modo Jogo a Jogo")
    live_scoring = config.get("live_scoring", {})
    col_l1, col_l2, col_l3 = st.columns(3)
    with col_l1:
        exact_score_val = st.number_input("Placar Exato", min_value=0, max_value=50, value=int(live_scoring.get("exact_score", 5)), step=1)
        outcome_val = st.number_input("Acertar Vencedor/Empate", min_value=0, max_value=50, value=int(live_scoring.get("outcome", 3)), step=1)
    with col_l2:
        goal_one_team_val = st.number_input("Acertar Gols de um Time", min_value=0, max_value=50, value=int(live_scoring.get("goal_one_team", 1)), step=1)
        goal_difference_val = st.number_input("Acertar Saldo de Gols", min_value=0, max_value=50, value=int(live_scoring.get("goal_difference", 1)), step=1)
    with col_l3:
        exact_score_mode = st.radio(
            "Modo do Placar Exato",
            options=["isolated_max", "additive"],
            index=0 if config.get("exact_score_mode", "isolated_max") == "isolated_max" else 1,
            help="isolated_max: ganha apenas os pontos do placar exato se acertar tudo. additive: ganha os pontos de placar exato + todos os outros bônus que coincidam."
        )
    
    config["live_scoring"] = {
        "exact_score": exact_score_val,
        "outcome": outcome_val,
        "goal_one_team": goal_one_team_val,
        "goal_difference": goal_difference_val,
        "late_prediction": 0
    }
    config["exact_score_mode"] = exact_score_mode

    st.markdown("#### Pesos do Ranking Geral Combinado")
    weights = config.get("combined_ranking_weights", {"classic": 1.0, "live": 1.0})
    col_w1, col_w2 = st.columns(2)
    with col_w1:
        classic_w = st.number_input("Peso do Modo Clássico", min_value=0.0, max_value=10.0, value=float(weights.get("classic", 1.0)), step=0.1)
    with col_w2:
        live_w = st.number_input("Peso do Modo Jogo a Jogo", min_value=0.0, max_value=10.0, value=float(weights.get("live", 1.0)), step=0.1)
    config["combined_ranking_weights"] = {"classic": classic_w, "live": live_w}

    st.markdown("#### Privacidade & Feed")
    config["reveal_live_predictions_after_lock"] = st.checkbox("Revelar palpites dos outros após o lock do jogo", value=config.get("reveal_live_predictions_after_lock", True))
    config["allow_live_prediction_edit_until_lock"] = st.checkbox("Permitir editar palpite jogo a jogo até o lock", value=config.get("allow_live_prediction_edit_until_lock", True))
    config["public_show_activity_feed"] = st.checkbox("Exibir feed de atividades público", value=config.get("public_show_activity_feed", True))

    st.markdown("### Pontuação V2 (Fase de Grupos & Mata-mata) [Modo Clássico]")
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

    st.markdown("#### Regras Criativas (Bônus Cumulativos) [Modo Clássico]")
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

    st.markdown("### Pontuação ponderada (Legado) [Modo Clássico]")
    weighted = config.get("weighted_rules", dict(DEFAULT_WEIGHTED_RULES))
    cols = st.columns(3)
    for idx, key in enumerate(DEFAULT_WEIGHTED_RULES.keys()):
        with cols[idx % 3]:
            weighted[key] = st.number_input(key, min_value=0, max_value=50, value=int(weighted.get(key, DEFAULT_WEIGHTED_RULES[key])), step=1)
    config["weighted_rules"] = weighted

    st.markdown("### Pontuação uniforme (Legado) [Modo Clássico]")
    uniform = config.get("uniform_rules", dict(DEFAULT_UNIFORM_RULES))
    uniform["decision_points"] = st.number_input("Pontos por decisão", min_value=1, max_value=50, value=int(uniform.get("decision_points", 1)), step=1)
    uniform["champion_bonus"] = st.number_input("Bônus da campeã", min_value=0, max_value=100, value=int(uniform.get("champion_bonus", 0)), step=1)
    config["uniform_rules"] = uniform

    if st.button("Salvar configurações", type="primary", key="btn_save_settings", width="stretch"):
        save_config(config)
        st.success("Configurações salvas.")

    st.markdown("---")
    st.markdown("### ⚠️ Zona de Perigo")
    st.caption("Ações irreversíveis que alteram ou excluem dados do sistema.")
    
    with st.expander("Expandir Zona de Perigo", expanded=False):
        st.markdown("#### 1. Restaurar dados de demonstração (Modo Clássico)")
        check_demo = st.checkbox("Desejo carregar os dados de demonstração", key="check_demo")
        word_demo = st.text_input("Digite CONFIRMAR para habilitar a ação de demonstração:", key="word_demo")
        if st.button("Restaurar dados demo", type="secondary", key="btn_reset_demo_state", disabled=not (check_demo and word_demo == "CONFIRMAR"), width="stretch"):
            from src.bolao.storage import load_demo_state
            load_demo_state()
            st.success("Dados de demonstração carregados com sucesso!")
            st.rerun()

        st.markdown("#### 2. Excluir palpites do Modo Jogo a Jogo")
        check_live = st.checkbox("Estou ciente que todos os palpites jogo a jogo salvos serão deletados permanentemente.", key="check_live")
        word_live = st.text_input("Digite LIMPAR JOGO A JOGO para confirmar:", key="word_live")
        if st.button("Excluir palpites Jogo a Jogo", type="secondary", key="btn_clear_live_guesses", disabled=not (check_live and word_live == "LIMPAR JOGO A JOGO"), width="stretch"):
            from src.bolao.storage import save_live_predictions
            save_live_predictions([])
            from src.bolao.events import append_event
            append_event("live_predictions_cleared", "Todos os palpites do modo jogo a jogo foram excluídos pelo administrador.")
            st.success("Todos os palpites jogo a jogo foram excluídos.")
            st.rerun()

        st.markdown("#### 3. Limpar Feed de Atividades")
        check_events = st.checkbox("Estou ciente de que todo o histórico de eventos será apagado permanentemente.", key="check_events")
        word_events = st.text_input("Digite LIMPAR EVENTOS para confirmar:", key="word_events")
        if st.button("Excluir Feed de Atividades", type="secondary", key="btn_clear_events_feed", disabled=not (check_events and word_events == "LIMPAR EVENTOS"), width="stretch"):
            from src.bolao.utils import write_json
            from src.bolao.storage import EVENTS_PATH
            write_json(EVENTS_PATH, [])
            st.success("Feed de atividades limpo.")
            st.rerun()

        st.markdown("#### 4. Reset Geral do Estado")
        check_reset = st.checkbox("Estou ciente de que todos os palpites clássicos, jogo a jogo, eventos e resultados serão excluídos permanentemente.", key="check_reset")
        word_reset = st.text_input("Digite RESET TOTAL para confirmar:", key="word_reset")
        if st.button("Executar Reset Total", type="primary", key="btn_full_reset_state", disabled=not (check_reset and word_reset == "RESET TOTAL"), width="stretch"):
            from src.bolao.storage import reset_state, save_matches
            reset_state()
            from src.bolao.storage import load_matches
            load_matches()
            st.success("Geral limpo e re-inicializado com sucesso!")
            st.rerun()


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
    # Rodar migrações seguras
    try:
        migrate_existing_submissions_to_classic_schema()
    except Exception:
        pass

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
            admin_options = ["Dashboard", "Participantes", "Jogos e Agenda", "Resultados oficiais", "Ranking Admin", "Exportações", "Configurações", "Ajuda Admin"]
            current_page = st.session_state["nav_page"]
            if current_page not in admin_options:
                current_page = "Dashboard"
            idx = admin_options.index(current_page)
            page = st.radio("Admin Menu", admin_options, index=idx, label_visibility="collapsed")
            st.session_state["nav_page"] = page
            show_admin = True
        else:
            # Public Menu
            public_options = ["Início", "Fazer palpite", "Jogos de Hoje", "Minha Cartela", "Ranking"]
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
        st.caption("Esta área é protegida. Informe a senha de acesso.")
        
        password = st.text_input("Senha do admin", type="password", key="admin_password_input_page")
        if password:
            try:
                admin_pwd = st.secrets.get("ADMIN_PASSWORD")
            except Exception:
                admin_pwd = None
            
            if password == "brasilhexa" or (admin_pwd and password == admin_pwd):
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
        elif page == "Jogos e Agenda":
            from src.bolao.ui_admin_matches import admin_matches_agenda
            admin_matches_agenda()
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
        elif page == "Jogos de Hoje":
            from src.bolao.ui_live_matches import render_jogos_de_hoje
            render_jogos_de_hoje()
        elif page == "Minha Cartela":
            from src.bolao.ui_cartela import render_minha_cartela
            render_minha_cartela()
        elif page == "Ranking":
            public_ranking()


if __name__ == "__main__":
    main()
