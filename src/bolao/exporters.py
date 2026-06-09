
from __future__ import annotations

import csv
import io
import json
from typing import Any

import pandas as pd

from .models import ScoreBreakdown


def ranking_to_dataframe(scores: list[ScoreBreakdown]) -> pd.DataFrame:
    rows = []
    max_exact = max([s.exact_scores for s in scores]) if scores else 0
    total_scores = len(scores)
    for i, score in enumerate(scores, start=1):
        row = score.to_row(i)
        badges_list = []
        if i == 1:
            badges_list.append("👑 Líder")
        elif i in (2, 3):
            badges_list.append("🏅 Top 3")
        if score.champion_hit:
            badges_list.append("🔮 Cravou Campeão")
        if max_exact > 0 and score.exact_scores == max_exact:
            badges_list.append("🎯 Mestre dos Placares")
        if i == total_scores and total_scores > 3:
            badges_list.append("🐢 Lanterna")
            
        row["Conquistas"] = ", ".join(badges_list) if badges_list else "—"
        rows.append(row)
    return pd.DataFrame(rows)


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


def podium_html(scores: list[ScoreBreakdown], status_label: str = "Aprovado", date_label: str | None = None) -> str:
    if not date_label:
        from .utils import now_iso
        date_label = now_iso()

    top = scores[:3]
    cards = []
    medals = ["🥇", "🥈", "🥉"]
    rank_labels = ["1º Lugar", "2º Lugar", "3º Lugar"]
    for idx, score in enumerate(top, start=1):
        medal = medals[idx - 1]
        place_class = f"place-{idx}"
        champ_text = "✅ Campeão" if score.champion_hit else "❌ Campeão"
        cards.append(
            f"""
            <div class="podium-place {place_class}">
              <div class="medal">{medal}</div>
              <div class="rank-label">{rank_labels[idx - 1]}</div>
              <div class="name">{score.participant}</div>
              <div class="points">{score.total} <span class="pts-label">pts</span></div>
              <div class="details">
                <span class="detail-item">Mata-mata: {score.knockout_points}</span>
                <span class="detail-divider">·</span>
                <span class="detail-item">{champ_text}</span>
              </div>
            </div>
            """
        )

    if not cards:
        cards.append('<div style="text-align: center; width: 100%; color: #66736D; padding: 40px 0;">Sem participantes no pódio ainda.</div>')

    return f"""<!doctype html>
<html lang="pt-br">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Pódio — Bolão da Cabine do Glória</title>
<style>
* {{
  box-sizing: border-box;
}}
body {{
  margin: 0;
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  background:
    radial-gradient(ellipse at 50% 80%, rgba(216, 169, 74, 0.12) 0%, transparent 60%),
    radial-gradient(ellipse at 50% 0%, rgba(23, 107, 77, 0.08) 0%, transparent 50%),
    linear-gradient(160deg, #0B3328 0%, #061914 100%);
  padding: 20px;
}}
.wrap {{
  width: 640px;
  max-width: 100%;
  padding: 48px 36px 36px;
  border-radius: 32px;
  background: linear-gradient(180deg, #FFFDF8 0%, #F5EBDD 100%);
  color: #0A211B;
  box-shadow: 0 24px 80px rgba(0, 0, 0, 0.5), 0 0 0 1px rgba(216, 169, 74, 0.15);
  text-align: center;
  position: relative;
  overflow: hidden;
}}
.wrap::before {{
  content: '';
  position: absolute;
  top: 0; left: 0; right: 0;
  height: 6px;
  background: linear-gradient(90deg, #D8A94A 0%, #FFF3CC 40%, #D8A94A 100%);
}}
.trophy-icon {{
  font-size: 64px;
  margin-bottom: 8px;
  line-height: 1;
}}
h1 {{
  margin: 0;
  font-size: 30px;
  color: #0B3328;
  font-weight: 900;
  letter-spacing: -0.5px;
}}
.subtitle {{
  margin: 6px 0 32px;
  color: #66736D;
  font-size: 13px;
  text-transform: uppercase;
  letter-spacing: 2px;
  font-weight: 600;
}}
.podium-container {{
  display: flex;
  justify-content: center;
  align-items: flex-end;
  gap: 12px;
  margin: 24px 0 32px;
  min-height: 310px;
}}
.podium-place {{
  flex: 1;
  max-width: 180px;
  border-radius: 20px;
  background: linear-gradient(180deg, #FFFDF8 0%, #F5EBDD 100%);
  border: 1.5px solid #E6D2B5;
  padding: 24px 12px 20px;
  display: flex;
  flex-direction: column;
  align-items: center;
  transition: transform 0.2s ease;
}}
.podium-place:hover {{
  transform: translateY(-4px);
}}
.place-1 {{
  order: 2;
  background: linear-gradient(180deg, #FFFDF8 0%, #FFF8E7 100%);
  border: 2px solid #D8A94A;
  box-shadow: 0 12px 32px rgba(216, 169, 74, 0.2);
  padding: 36px 16px 28px;
  margin-bottom: -8px;
}}
.place-2 {{
  order: 1;
  padding: 20px 12px 16px;
}}
.place-3 {{
  order: 3;
  padding: 16px 12px 14px;
}}
.medal {{
  font-size: 44px;
  margin-bottom: 4px;
  line-height: 1;
}}
.place-1 .medal {{
  font-size: 56px;
}}
.rank-label {{
  font-size: 11px;
  font-weight: 800;
  color: #D8A94A;
  text-transform: uppercase;
  letter-spacing: 1px;
  margin-bottom: 6px;
}}
.name {{
  font-size: 16px;
  font-weight: 800;
  color: #0B3328;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  width: 100%;
  margin: 4px 0;
}}
.place-1 .name {{
  font-size: 20px;
  font-weight: 900;
}}
.points {{
  font-size: 24px;
  font-weight: 900;
  color: #176B4D;
  margin: 6px 0;
  line-height: 1;
}}
.pts-label {{
  font-size: 14px;
  font-weight: 600;
  color: #66736D;
}}
.place-1 .points {{
  font-size: 32px;
  color: #D8A94A;
}}
.details {{
  font-size: 11px;
  color: #66736D;
  margin-top: 8px;
  line-height: 1.5;
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 4px;
}}
.detail-item {{
  white-space: nowrap;
}}
.detail-divider {{
  color: #D8A94A;
}}
.footer {{
  margin-top: 4px;
  padding-top: 20px;
  border-top: 1px solid rgba(11, 51, 40, 0.1);
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 11px;
  color: #66736D;
}}
.badge {{
  display: inline-block;
  background-color: #0B3328;
  color: #FFFDF8;
  padding: 3px 10px;
  border-radius: 99px;
  font-weight: 700;
  text-transform: uppercase;
  font-size: 10px;
  letter-spacing: 0.5px;
}}
@media (max-width: 500px) {{
  .wrap {{
    padding: 32px 16px 24px;
  }}
  .podium-container {{
    gap: 8px;
    min-height: 260px;
  }}
  .place-1 {{
    padding: 28px 10px 20px;
  }}
  .points {{
    font-size: 20px;
  }}
  .place-1 .points {{
    font-size: 26px;
  }}
}}
</style>
</head>
<body>
<div class="wrap">
  <div class="trophy-icon">🏆</div>
  <h1>Bolão Cabine do Glória</h1>
  <div class="subtitle">Copa do Mundo 2026 · Pódio Atualizado</div>
  <div class="podium-container">
    {''.join(cards)}
  </div>
  <div class="footer">
    <span>Status: <span class="badge">{status_label}</span></span>
    <span>Gerado: <b>{date_label[:10]}</b></span>
  </div>
</div>
</body>
</html>
"""


def details_dataframe(score: ScoreBreakdown) -> pd.DataFrame:
    return pd.DataFrame(score.details)
