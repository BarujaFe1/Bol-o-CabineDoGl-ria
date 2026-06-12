from __future__ import annotations

import html
from typing import Any

import pandas as pd
import streamlit as st

from .constants import APP_NAME, APP_SUBTITLE, GE_SIMULATOR_URL, GROUPS, PHASE_LABELS, PHASES

def inject_css() -> None:
    from .styles import inject_css as styles_inject
    styles_inject()

def render_theme_selector() -> None:
    """
    Renderiza o seletor de tema na barra lateral.
    """
    if "theme_mode" not in st.session_state:
        st.session_state["theme_mode"] = "system"
        
    theme_options = {
        "light": "☀️ Claro",
        "dark": "🌙 Escuro",
        "system": "💻 Sistema"
    }
    
    current_theme = st.session_state["theme_mode"]
    keys = list(theme_options.keys())
    idx = keys.index(current_theme) if current_theme in keys else 2
    
    # Render theme selectbox
    selected_theme = st.selectbox(
        "Aparência do App",
        options=keys,
        format_func=lambda x: theme_options[x],
        index=idx,
        key="theme_selector_selectbox"
    )
    
    if selected_theme != st.session_state["theme_mode"]:
        st.session_state["theme_mode"] = selected_theme
        st.rerun()

def hero(title: str = APP_NAME, subtitle: str = APP_SUBTITLE, description: str | None = None) -> None:
    desc = description or "Faça seu palpite completo da Copa do Mundo 2026 diretamente pelo nosso simulador interativo. Preencha os placares dos grupos, acompanhe a classificação em tempo real e decida o mata-mata."
    st.markdown(
        f"""
<div class="copa-hero">
  <div class="eyebrow">🏟️ {html.escape(subtitle)}</div>
  <div class="copa-title">{html.escape(title)}</div>
  <p class="copa-subtitle">{html.escape(desc)}</p>
</div>
        """,
        unsafe_allow_html=True,
    )

def kpi_grid(items: list[tuple[str, str]]) -> None:
    html_items = "".join([f'<div class="kpi"><div class="label">{html.escape(label)}</div><div class="value">{html.escape(str(value))}</div></div>' for label, value in items])
    st.markdown(f'<div class="kpi-grid">{html_items}</div>', unsafe_allow_html=True)

def step_cards() -> None:
    steps = [
        ("Informe seu nome", "Comece identificando seu palpite para participar do ranking."),
        ("Simule a fase de grupos", "Preencha os placares de todos os jogos. A classificação é calculada automaticamente."),
        ("Escolha o mata-mata", "Selecione os vencedores de cada confronto até definir o campeão."),
        ("Revise e envie", "Confira seu palpite completo antes de confirmar. Depois de enviado, ele entra no ranking."),
    ]
    inner = ""
    for idx, (title, text) in enumerate(steps, start=1):
        inner += f'<div class="step"><div class="num">{idx}</div><h4>{html.escape(title)}</h4><p>{html.escape(text)}</p></div>'
    st.markdown(f'<div class="step-grid">{inner}</div>', unsafe_allow_html=True)

def card_start(title: str | None = None) -> None:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    if title:
        st.markdown(f"### {title}")

def card_end() -> None:
    st.markdown("</div>", unsafe_allow_html=True)

def issues_box(issues: list[Any]) -> None:
    for issue in issues:
        level = getattr(issue, "level", "warning")
        msg = getattr(issue, "message", str(issue))
        ctx = getattr(issue, "context", "")
        klass = "error-box" if level == "error" else "warn-box"
        st.markdown(f'<div class="{klass}"><strong>{html.escape(level.upper())}:</strong> {html.escape(msg)} {html.escape(ctx or "")}</div>', unsafe_allow_html=True)

def podium(scores: list[Any]) -> None:
    top = scores[:3]
    if not top:
        st.info("O pódio aparecerá quando houver ranking calculado.")
        return
    order = [(2, "🥈", "second"), (1, "🥇", "first"), (3, "🥉", "third")]
    cards = []
    for pos, medal, css in order:
        if len(top) >= pos:
            score = top[pos - 1]
            participant_name = score.get("participant") if isinstance(score, dict) else (score.participant if hasattr(score, 'participant') else "Participante")
            total_points = score.get("total") if isinstance(score, dict) else (score.total if hasattr(score, 'total') else 0)
            
            # Classic mode properties
            group_points = score.get("groups", 0) if isinstance(score, dict) else (getattr(score, 'group_points', 0))
            knockout_points = score.get("knockout", 0) if isinstance(score, dict) else (getattr(score, 'knockout_points', 0))
            champion_hit = score.get("champion_hit", False) if isinstance(score, dict) else (getattr(score, 'champion_hit', 0))
            
            detail_str = f"Mata-mata {knockout_points} · Campeã {'sim' if champion_hit else 'não'}"
            if "exact_scores" in score if isinstance(score, dict) else hasattr(score, 'exact_scores'):
                # Live mode properties
                exacts = score.get("exact_scores") if isinstance(score, dict) else getattr(score, 'exact_scores')
                detail_str = f"{exacts} exatos · {score.get('predictions_count', 0) if isinstance(score, dict) else 0} jogos"
                
            cards.append(
                f"""
<div class="podium-card {css}">
  <div class="medal">{medal}</div>
  <div class="podium-rank">{pos}º lugar</div>
  <div class="podium-name">{html.escape(participant_name)}</div>
  <div class="podium-points">{total_points} pts</div>
  <div class="podium-note">{html.escape(detail_str)}</div>
</div>
                """
            )
        else:
            cards.append('<div></div>')
    st.markdown(f'<div class="podium">{"".join(cards)}</div>', unsafe_allow_html=True)

def badges(labels: list[str]) -> None:
    st.markdown("".join(f'<span class="badge">{html.escape(x)}</span>' for x in labels), unsafe_allow_html=True)

def groups_dataframe(groups: dict[str, list[str | None]]) -> pd.DataFrame:
    return pd.DataFrame([
        {"Grupo": g, "1º": values[0], "2º": values[1], "3º": values[2], "4º": values[3]}
        for g, values in groups.items()
    ])

def dataframe_to_groups(df: pd.DataFrame) -> dict[str, list[str | None]]:
    groups: dict[str, list[str | None]] = {}
    for _, row in df.iterrows():
        g = str(row.get("Grupo", "")).strip().upper()
        if g:
            groups[g] = [row.get("1º") or None, row.get("2º") or None, row.get("3º") or None, row.get("4º") or None]
    return groups

def render_page_header(kicker: str, title: str, subtitle: str = "", icon: str = "🏆") -> None:
    st.markdown(
        f"""
        <div class="page-header">
            <div class="eyebrow">{icon} {html.escape(kicker)}</div>
            <h2 class="page-title" style="margin: 8px 0 4px 0;">{html.escape(title)}</h2>
            {f'<div class="page-subtitle">{html.escape(subtitle)}</div>' if subtitle else ''}
        </div>
        """,
        unsafe_allow_html=True
    )

def render_kpi_grid(items: list[dict[str, Any]]) -> None:
    html_items = "".join([f'<div class="kpi"><div class="label">{html.escape(item["label"])}</div><div class="value">{html.escape(str(item["value"]))}</div></div>' for item in items])
    st.markdown(f'<div class="kpi-grid">{html_items}</div>', unsafe_allow_html=True)

def render_step_cards(steps: list[dict[str, Any]]) -> None:
    inner = ""
    for idx, step in enumerate(steps, start=1):
        inner += f'<div class="step"><div class="num">{idx}</div><h4>{html.escape(step["title"])}</h4><p>{html.escape(step["description"])}</p></div>'
    st.markdown(f'<div class="step-grid">{inner}</div>', unsafe_allow_html=True)

def render_callout(message: str, kind: str = "info", title: str | None = None) -> None:
    title_html = f"<strong>{html.escape(title)}</strong><br>" if title else ""
    st.markdown(f'<div class="callout {kind}">{title_html}{html.escape(message)}</div>', unsafe_allow_html=True)

def render_empty_state(title: str, body: str, cta_label: str | None = None, cta_key: str | None = None) -> bool:
    st.markdown(
        f"""
        <div class="empty-state">
            <div class="icon">🔍</div>
            <h3>{html.escape(title)}</h3>
            <p>{html.escape(body)}</p>
        </div>
        """,
        unsafe_allow_html=True
    )
    if cta_label and cta_key:
        if st.button(cta_label, key=cta_key, width="stretch", type="primary"):
            return True
    return False

def render_progress_status(label: str, current: int, total: int) -> None:
    pct = (current / total) * 100 if total > 0 else 0
    st.markdown(
        f"""
        <div style="margin: 10px 0;">
            <div style="display: flex; justify-content: space-between; font-size: 14px; font-weight: bold; color: var(--ink); margin-bottom: 4px;">
                <span>{html.escape(label)}</span>
                <span>{current} / {total} ({pct:.0f}%)</span>
            </div>
            <div style="width: 100%; background-color: rgba(11, 51, 40, 0.1); height: 10px; border-radius: 99px; overflow: hidden;">
                <div style="width: {pct}%; background-color: var(--green); height: 100%; border-radius: 99px;"></div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

def render_badge(text: str, kind: str = "neutral") -> str:
    return f'<span class="badge {kind}">{html.escape(text)}</span>'

def render_step_indicator(steps: list[str], current_index: int) -> None:
    inner = ""
    for idx, step_name in enumerate(steps):
        is_active = idx == current_index
        is_done = idx < current_index
        circle = "✓" if is_done else str(idx + 1)
        cls = "step-dot active" if is_active else ("step-dot done" if is_done else "step-dot")
        line_cls = "step-line" if idx < len(steps) - 1 else ""
        line_state = " done" if idx < current_index else ""
        inner += f"""
            <div class="step-item">
                <div class="{cls}">{circle}</div>
                <div class="step-label">{html.escape(step_name)}</div>
            </div>
        """
        if idx < len(steps) - 1:
            inner += f'<div class="{line_cls}{line_state}"></div>'
    st.markdown(
        f'<div class="step-indicator">{inner}</div>',
        unsafe_allow_html=True
    )


def render_responsive_table(
    df: pd.DataFrame,
    card_renderer_callback: Any,
    key: str,
    desktop_columns: list[str] | None = None
) -> None:
    """
    Renderiza um dataframe no desktop e cards específicos no mobile.
    """
    # Desktop view wrapper
    st.markdown('<div class="desktop-only-table">', unsafe_allow_html=True)
    df_display = df[desktop_columns] if desktop_columns else df
    st.dataframe(df_display, width="stretch", hide_index=True)
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Mobile view wrapper
    st.markdown('<div class="mobile-only-cards">', unsafe_allow_html=True)
    if df.empty:
        st.caption("Nenhum registro para exibir.")
    else:
        for idx, row in df.iterrows():
            # Use unique key prefix inside callback if needed
            card_renderer_callback(row)
    st.markdown('</div>', unsafe_allow_html=True)
