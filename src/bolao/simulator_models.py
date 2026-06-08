from __future__ import annotations

from dataclasses import dataclass
from typing import Any

@dataclass
class Team:
    id: str
    name: str
    abbr: str
    badge: str

@dataclass
class GroupMatch:
    id: str
    group: str
    round: str
    home_id: str
    away_id: str
    home_score: int | None = None
    away_score: int | None = None
    stadium: str = ""
    date: str = ""
    hour: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "group": self.group,
            "round": self.round,
            "home_id": self.home_id,
            "away_id": self.away_id,
            "home_score": self.home_score,
            "away_score": self.away_score,
            "stadium": self.stadium,
            "date": self.date,
            "hour": self.hour,
        }

@dataclass
class GroupStanding:
    team_id: str
    name: str
    abbr: str
    points: int = 0
    played: int = 0
    wins: int = 0
    draws: int = 0
    losses: int = 0
    gf: int = 0  # Gols Pró
    ga: int = 0  # Gols Contra
    gd: int = 0  # Saldo de Gols
    percent: float = 0.0  # Aproveitamento (0 to 100)
    position: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "team_id": self.team_id,
            "name": self.name,
            "abbr": self.abbr,
            "points": self.points,
            "played": self.played,
            "wins": self.wins,
            "draws": self.draws,
            "losses": self.losses,
            "gf": self.gf,
            "ga": self.ga,
            "gd": self.gd,
            "percent": self.percent,
            "position": self.position,
        }
