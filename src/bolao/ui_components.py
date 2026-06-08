
from __future__ import annotations

import html
from typing import Any

import pandas as pd
import streamlit as st

from .constants import APP_NAME, APP_SUBTITLE, GE_SIMULATOR_URL, GROUPS, PHASE_LABELS, PHASES


def inject_css() -> None:
    st.markdown(
        """
<style>
:root {
  --bg: #f7f2e9;
  --panel: rgba(255,255,255,.82);
  --panel-strong: #ffffff;
  --ink: #10231d;
  --muted: #6f766f;
  --green: #1f5b42;
  --green-2: #173b2d;
  --gold: #c49a3c;
  --line: rgba(25, 55, 44, .13);
  --shadow: 0 22px 70px rgba(17, 42, 31, .12);
}

[data-testid="stAppViewContainer"] {
  background:
    radial-gradient(circle at 8% 5%, rgba(199, 158, 75, .22), transparent 28%),
    radial-gradient(circle at 95% 20%, rgba(31, 91, 66, .18), transparent 30%),
    linear-gradient(180deg, #fbf7ef 0%, #f3eadb 100%);
}

[data-testid="stHeader"] { background: transparent; }
[data-testid="stSidebar"] {
  background: linear-gradient(180deg, #10231d, #173b2d 70%, #0f211b);
}
[data-testid="stSidebar"] * { color: #fffaf1 !important; }
.block-container { padding-top: 2rem; max-width: 1240px; }

.copa-hero {
  border: 1px solid var(--line);
  background:
    linear-gradient(135deg, rgba(255,255,255,.9), rgba(255,252,246,.74)),
    radial-gradient(circle at 92% 18%, rgba(196,154,60,.22), transparent 30%);
  border-radius: 34px;
  padding: 34px 34px;
  box-shadow: var(--shadow);
  margin-bottom: 22px;
  position: relative;
  overflow: hidden;
}

.copa-hero:after {
  content: "";
  position: absolute;
  right: -80px;
  bottom: -90px;
  width: 260px;
  height: 260px;
  border-radius: 999px;
  border: 32px solid rgba(31, 91, 66, .08);
}

.eyebrow {
  display:inline-flex;
  align-items:center;
  gap:8px;
  padding: 7px 11px;
  border-radius: 999px;
  background: rgba(31,91,66,.08);
  color: var(--green);
  font-size: 12px;
  font-weight: 800;
  letter-spacing: .08em;
  text-transform: uppercase;
}

.copa-title {
  color: var(--ink);
  font-size: clamp(36px, 5vw, 64px);
  line-height: .98;
  font-weight: 900;
  letter-spacing: -2px;
  margin: 18px 0 8px;
}

.copa-subtitle {
  color: #59645d;
  font-size: 18px;
  max-width: 790px;
  line-height: 1.55;
  margin-bottom: 0;
}

.card {
  border: 1px solid var(--line);
  background: var(--panel);
  border-radius: 26px;
  padding: 22px;
  box-shadow: 0 14px 42px rgba(15, 35, 28, .08);
  margin-bottom: 16px;
}

.kpi-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
  margin: 18px 0;
}

.kpi {
  border: 1px solid var(--line);
  background: rgba(255,255,255,.85);
  border-radius: 24px;
  padding: 18px 18px;
  box-shadow: 0 10px 30px rgba(17, 42, 31, .07);
}

.kpi .label {
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing:.08em;
  font-weight: 800;
  color: #748077;
}

.kpi .value {
  font-size: 30px;
  font-weight: 900;
  color: var(--ink);
  margin-top: 6px;
}

.step-grid {
  display:grid;
  grid-template-columns: repeat(4, minmax(0,1fr));
  gap: 14px;
}

.step {
  background: rgba(255,255,255,.78);
  border:1px solid var(--line);
  border-radius: 24px;
  padding: 18px;
  min-height: 155px;
}

.step .num {
  width: 34px;
  height: 34px;
  display:flex;
  align-items:center;
  justify-content:center;
  border-radius: 50%;
  background: var(--green);
  color: #fff;
  font-weight: 900;
  margin-bottom: 12px;
}

.step h4 { margin: 0 0 8px; color: var(--ink); }
.step p { color: var(--muted); font-size: 14px; margin: 0; line-height: 1.45; }

.podium {
  display:grid;
  grid-template-columns: 1fr 1.18fr 1fr;
  gap: 16px;
  align-items:end;
  margin: 18px 0 22px;
}

.podium-card {
  border: 1px solid rgba(196,154,60,.28);
  background: linear-gradient(180deg, rgba(255,255,255,.95), rgba(255,249,236,.82));
  border-radius: 30px;
  padding: 22px;
  text-align:center;
  box-shadow: 0 18px 46px rgba(70, 50, 16, .10);
}

.podium-card.first {
  padding: 30px 22px;
  transform: translateY(-16px);
  box-shadow: 0 28px 74px rgba(196,154,60,.2);
}

.medal { font-size: 42px; margin-bottom: 6px; }
.podium-rank { font-size:12px; font-weight:900; letter-spacing:.08em; text-transform:uppercase; color:#9a742a; }
.podium-name { color: var(--ink); font-size: 25px; font-weight: 900; margin-top: 7px; }
.podium-points { color: var(--green); font-size: 34px; font-weight: 950; margin-top: 8px; }
.podium-note { color:#768076; font-size: 13px; margin-top: 7px; }

.badge {
  display:inline-flex;
  border-radius:999px;
  border:1px solid var(--line);
  background:rgba(255,255,255,.78);
  padding:6px 10px;
  color: var(--green-2);
  font-size: 12px;
  font-weight: 800;
  margin-right: 6px;
  margin-bottom: 6px;
}

.success-card {
  border-radius: 28px;
  padding: 26px;
  background: linear-gradient(135deg, rgba(31,91,66,.12), rgba(196,154,60,.16));
  border:1px solid rgba(31,91,66,.22);
}

.warn-box {
  border: 1px solid rgba(196,154,60,.38);
  background: rgba(255,249,236,.82);
  border-radius: 20px;
  padding: 14px 16px;
  color: #75591d;
  margin: 8px 0;
}

.error-box {
  border: 1px solid rgba(190,55,55,.26);
  background: rgba(255,242,242,.86);
  border-radius: 20px;
  padding: 14px 16px;
  color: #842525;
  margin: 8px 0;
}

.small-muted { color: var(--muted); font-size: 14px; line-height:1.48; }
a.button-link {
  display:inline-flex;
  padding: 12px 16px;
  border-radius: 16px;
  background: var(--green);
  color:white !important;
  text-decoration:none;
  font-weight: 800;
  margin-top: 14px;
}

@media (max-width: 900px) {
  .kpi-grid, .step-grid, .podium { grid-template-columns: 1fr; }
  .podium-card.first { transform: none; }
  .copa-hero { padding: 24px; border-radius: 26px; }
}
</style>
        """,
        unsafe_allow_html=True,
    )


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
            cards.append(
                f"""
<div class="podium-card {css}">
  <div class="medal">{medal}</div>
  <div class="podium-rank">{pos}º lugar</div>
  <div class="podium-name">{html.escape(score.participant)}</div>
  <div class="podium-points">{score.total} pts</div>
  <div class="podium-note">Mata-mata {score.knockout_points} · Campeã {'sim' if score.champion_hit else 'não'}</div>
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
