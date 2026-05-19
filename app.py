
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
        mode=config.get("scoring_mode", "ponderado"),
        weighted_rules=config.get("weighted_rules", dict(DEFAULT_WEIGHTED_RULES)),
        uniform_rules=config.get("uniform_rules", dict(DEFAULT_UNIFORM_RULES)),
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
    hero(description="Um bolão simples para quem participa e completo para quem organiza. Você envia dois prints dos grupos e cola o texto do mata-mata; o site detecta tudo e mostra uma conferência antes de salvar.")
    step_cards()
    st.markdown("### O que você precisa enviar")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown('<div class="card"><h4>Imagem 1</h4><p class="small-muted">Print dos grupos A até F. Deixe o zoom confortável e todos os nomes visíveis.</p></div>', unsafe_allow_html=True)
    with col2:
        st.markdown('<div class="card"><h4>Imagem 2</h4><p class="small-muted">Print dos grupos G até L. Evite cortes, modo escuro excessivo ou imagem borrada.</p></div>', unsafe_allow_html=True)
    with col3:
        st.markdown('<div class="card"><h4>Texto do mata-mata</h4><p class="small-muted">Cole o texto exportado pelo ge com Décima-sextas, Oitavas, Quartas, Semi, Final e Campeã.</p></div>', unsafe_allow_html=True)

    st.markdown("### Dicas para o OCR acertar mais")
    badges([
        "Use print sem corte",
        "Aumente o zoom antes de tirar o print",
        "Evite imagem tremida",
        "Confira antes de salvar",
        "Não precisa mexer com JSON",
    ])


def public_submission() -> None:
    hero("Enviar palpite", "Fluxo do participante", "Preencha os campos, envie as duas imagens dos grupos e cole o texto do mata-mata. Depois revise tudo antes de confirmar.")

    with st.expander("Ver instruções rápidas", expanded=True):
        step_cards()

    st.markdown("### 1. Identificação")
    name = st.text_input("Seu nome no bolão", placeholder="Ex.: Cesar", key="public_name")

    st.markdown("### 2. Upload dos grupos")
    col_a, col_b = st.columns(2)
    with col_a:
        af_file = st.file_uploader("Imagem dos grupos A-F", type=["png", "jpg", "jpeg", "webp"], key="af_file")
        if af_file:
            st.image(af_file, caption="Prévia A-F", width=320)
    with col_b:
        gl_file = st.file_uploader("Imagem dos grupos G-L", type=["png", "jpg", "jpeg", "webp"], key="gl_file")
        if gl_file:
            st.image(gl_file, caption="Prévia G-L", width=320)

    st.markdown("### 3. Texto do mata-mata exportado pelo ge")
    knockout_text = st.text_area(
        "Cole aqui o texto do ge",
        height=260,
        placeholder="Simulador Copa do Mundo 2026\n\nDécima-sextas\nAlemanha x Paraguai\nFrança x Suécia\n...\n\nCampeã\nBrasil",
        key="knockout_text",
    )

    missing = []
    if not name.strip():
        missing.append("nome")
    if not af_file:
        missing.append("imagem A-F")
    if not gl_file:
        missing.append("imagem G-L")
    if not knockout_text.strip():
        missing.append("texto do mata-mata")

    if missing:
        st.info("Preencha para continuar: " + ", ".join(missing))

    if st.button("Ler imagens e preparar conferência", type="primary", disabled=bool(missing), width="stretch"):
        with st.spinner("Fazendo OCR das imagens e interpretando o texto do mata-mata..."):
            st.session_state["draft_prediction"] = build_prediction_from_public_inputs(name, af_file, gl_file, knockout_text)
            st.session_state["show_review"] = True
        st.rerun()

    if st.session_state.get("show_review") and st.session_state.get("draft_prediction"):
        st.markdown("---")
        st.markdown("## 4. Conferência obrigatória")
        pred: Prediction = deepcopy(st.session_state["draft_prediction"])

        ocr_warnings = pred.meta.get("warnings", [])
        ko_issues = pred.meta.get("knockout_issues", [])
        if ocr_warnings:
            st.warning("OCR com avisos: revise os grupos antes de salvar.")
            for w in ocr_warnings[:8]:
                st.caption(f"• {w}")
        if ko_issues:
            issues_box([type("Issue", (), i) for i in ko_issues[:12]])

        with st.expander("Ver texto bruto detectado pelo OCR", expanded=False):
            st.text(pred.meta.get("ocr", {}).get("raw_ocr_text", "") or "Sem texto bruto de OCR.")

        pred = apply_review_form("public_review", pred)
        issues = validate_prediction(pred, strict=False)
        if issues:
            st.markdown("#### Avisos da conferência")
            issues_box(issues)

        st.markdown("### 5. Confirmação final")
        st.caption("Ao confirmar, o palpite será salvo no sistema. Se você fizer novo envio com o mesmo nome, o admin verá os dois registros.")
        if st.button("Confirmar e salvar meu palpite", type="primary", width="stretch"):
            pred.status = "confirmado"
            pred.submitted_at = now_iso()
            save_submission(pred)
            st.session_state.pop("draft_prediction", None)
            st.session_state.pop("show_review", None)
            st.markdown(
                f"""
<div class="success-card">
  <h3>Palpite enviado com sucesso</h3>
  <p>Guarde este código de envio:</p>
  <h2>{pred.submission_id}</h2>
  <p class="small-muted">Seu palpite já está registrado. O ranking será atualizado quando o resultado oficial estiver aprovado pelo admin.</p>
</div>
                """,
                unsafe_allow_html=True,
            )


def public_ranking() -> None:
    hero("Ranking público", "Consulta dos participantes", "Veja o pódio, a classificação geral e o detalhamento quando o resultado oficial estiver aprovado.")
    submissions = load_submissions()
    official = load_official()
    config = load_config()

    kpi_grid([
        ("Status", config.get("status_label", "Recebendo palpites")),
        ("Participantes", str(len(submissions))),
        ("Resultado oficial", "Aprovado" if official else "Pendente"),
        ("Modo", config.get("scoring_mode", "ponderado").capitalize()),
    ])

    if not official:
        st.info("O resultado oficial ainda não foi aprovado. Por enquanto, os palpites enviados aparecem abaixo.")
        if submissions:
            st.dataframe(pd.DataFrame([{"Participante": p.participant, "Enviado em": p.submitted_at, "Código": p.submission_id} for p in submissions]), width="stretch", hide_index=True)
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
        st.info("Ainda não há participantes para ranquear.")


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
    st.caption("Fluxo recomendado: sincronizar API ou colar texto → revisar manualmente → aprovar resultado oficial → recalcular ranking.")

    tabs = st.tabs(["Texto/manual", "API", "Resultado aprovado"])

    with tabs[0]:
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

    with tabs[1]:
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

    with tabs[2]:
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
    config["status_label"] = st.text_input("Status público do bolão", value=config.get("status_label", "Recebendo palpites"))
    config["scoring_mode"] = st.radio("Modo de pontuação", ["ponderado", "uniforme"], index=0 if config.get("scoring_mode") == "ponderado" else 1, horizontal=True)

    st.markdown("### Pontuação ponderada")
    weighted = config.get("weighted_rules", dict(DEFAULT_WEIGHTED_RULES))
    cols = st.columns(3)
    for idx, key in enumerate(DEFAULT_WEIGHTED_RULES.keys()):
        with cols[idx % 3]:
            weighted[key] = st.number_input(key, min_value=0, max_value=50, value=int(weighted.get(key, DEFAULT_WEIGHTED_RULES[key])), step=1)
    config["weighted_rules"] = weighted

    st.markdown("### Pontuação uniforme")
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
        f"""
**Fluxo do participante**

1. Acessa o simulador do ge: {GE_SIMULATOR_URL}
2. Preenche a simulação.
3. Envia dois prints dos grupos.
4. Cola o texto exportado do mata-mata.
5. Confere o que o OCR e o parser detectaram.
6. Confirma o palpite.

**Fluxo do admin**

1. Recebe os palpites.
2. Aprova o resultado oficial na Central de Resultados.
3. Confere ranking.
4. Exporta texto para Discord ou CSV/JSON.

**OCR**

A leitura dos grupos usa primeiro o layout/cor dos cards do ge. O Tesseract fica como fallback auxiliar. Se algo falhar, a revisão manual continua disponível.
        """
    )


def check_admin_auth() -> bool:
    if "ADMIN_PASSWORD" not in st.secrets:
        return True
    if st.session_state.get("admin_authenticated", False):
        return True

    st.markdown("### 🔒 Área Administrativa")
    st.caption("Esta área é protegida. Informe a senha configurada nos secrets.")
    password = st.text_input("Senha do admin", type="password", key="admin_password_input")
    if password:
        if password == st.secrets.get("ADMIN_PASSWORD"):
            st.session_state["admin_authenticated"] = True
            st.rerun()
        else:
            st.error("Senha incorreta.")
    return False


def main() -> None:
    with st.sidebar:
        st.markdown(f"## 🏆 {APP_NAME}")
        st.caption(APP_SUBTITLE)

        has_admin_password = "ADMIN_PASSWORD" in st.secrets
        mode = st.radio("Área", ["Público", "Admin"], horizontal=True, disabled=has_admin_password and not st.session_state.get("admin_authenticated"))

        if mode == "Público":
            page = st.radio("Navegação", ["Início", "Enviar palpite", "Ranking"], label_visibility="collapsed")
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
        elif page == "Enviar palpite":
            public_submission()
        elif page == "Ranking":
            public_ranking()


if __name__ == "__main__":
    main()
