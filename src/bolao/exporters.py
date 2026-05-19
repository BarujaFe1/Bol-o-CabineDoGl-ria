
from __future__ import annotations

import csv
import io
import json
from typing import Any

import pandas as pd

from .models import ScoreBreakdown


def ranking_to_dataframe(scores: list[ScoreBreakdown]) -> pd.DataFrame:
    return pd.DataFrame([score.to_row(i) for i, score in enumerate(scores, start=1)])


def ranking_csv(scores: list[ScoreBreakdown]) -> str:
    df = ranking_to_dataframe(scores)
    return df.to_csv(index=False)


def ranking_json(scores: list[ScoreBreakdown]) -> str:
    return json.dumps([score.to_row(i) for i, score in enumerate(scores, start=1)], ensure_ascii=False, indent=2)


def discord_ranking(scores: list[ScoreBreakdown], title: str = "BOLÃO DA CABINE DO GLÓRIA") -> str:
    lines = [f"🏆 {title}", "", "Ranking atualizado:"]
    medals = ["🥇", "🥈", "🥉"]
    for idx, score in enumerate(scores, start=1):
        prefix = medals[idx - 1] if idx <= 3 else f"{idx}."
        lines.append(f"{prefix} {score.participant} — {score.total} pts | Mata-mata: {score.knockout_points} | Campeã: {'✅' if score.champion_hit else '❌'}")
    if not scores:
        lines.append("Ainda não há ranking calculado.")
    return "\n".join(lines)


def podium_html(scores: list[ScoreBreakdown]) -> str:
    top = scores[:3]
    cards = []
    for idx, score in enumerate(top, start=1):
        medal = ["🥇", "🥈", "🥉"][idx - 1]
        cards.append(
            f"""
            <div class="podium-card podium-{idx}">
              <div class="medal">{medal}</div>
              <div class="rank">{idx}º lugar</div>
              <div class="name">{score.participant}</div>
              <div class="points">{score.total} pts</div>
              <div class="sub">Mata-mata {score.knockout_points} · Campeã {'sim' if score.champion_hit else 'não'}</div>
            </div>
            """
        )
    return f"""
<!doctype html>
<html lang="pt-br">
<head>
<meta charset="utf-8">
<title>Pódio — Bolão da Cabine do Glória</title>
<style>
body {{
  margin:0; min-height:100vh; display:flex; align-items:center; justify-content:center;
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
  background: radial-gradient(circle at top left,#f7e5bb,#fffaf1 36%,#10251d 120%);
}}
.wrap {{ width: 1100px; max-width: 94vw; padding: 42px; border-radius: 36px; background: rgba(255,255,255,.75); box-shadow: 0 30px 90px rgba(20,41,33,.18); }}
h1 {{ margin:0; font-size:42px; color:#12261f; letter-spacing:-1px; }}
p {{ margin:8px 0 30px; color:#6b5d45; }}
.grid {{ display:grid; grid-template-columns: repeat(3,1fr); gap:18px; align-items:end; }}
.podium-card {{ border:1px solid rgba(42,77,61,.16); border-radius:28px; padding:26px; background:linear-gradient(180deg,#ffffff,#faf6ec); text-align:center; }}
.podium-1 {{ transform: translateY(-18px); box-shadow:0 28px 50px rgba(183,135,39,.2); }}
.medal {{ font-size:44px; }}
.rank {{ color:#8b6b22; text-transform:uppercase; letter-spacing:.08em; font-size:12px; font-weight:800; }}
.name {{ font-size:28px; color:#12261f; font-weight:850; margin-top:8px; }}
.points {{ font-size:36px; font-weight:900; color:#163d2e; margin-top:8px; }}
.sub {{ color:#6c756f; margin-top:8px; }}
</style>
</head>
<body>
<div class="wrap">
<h1>Bolão da Cabine do Glória</h1>
<p>Copa do Mundo 2026 · Pódio atualizado</p>
<div class="grid">{''.join(cards)}</div>
</div>
</body>
</html>
"""


def details_dataframe(score: ScoreBreakdown) -> pd.DataFrame:
    return pd.DataFrame(score.details)
