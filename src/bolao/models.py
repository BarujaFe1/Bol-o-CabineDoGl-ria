
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .constants import GROUPS, PHASES


@dataclass
class ParseIssue:
    level: str
    message: str
    context: str = ""


@dataclass
class Match:
    a: str | None = None
    b: str | None = None
    winner: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"a": self.a, "b": self.b, "winner": self.winner}


@dataclass
class Prediction:
    participant: str
    groups: dict[str, list[str | None]] = field(default_factory=lambda: {g: [None, None, None, None] for g in GROUPS})
    best_thirds: list[str] = field(default_factory=list)
    knockout: dict[str, list[Match]] = field(default_factory=lambda: {p: [] for p in PHASES})
    champion: str | None = None
    submission_id: str | None = None
    submitted_at: str | None = None
    status: str = "rascunho"
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "participant": self.participant,
            "groups": self.groups,
            "best_thirds": self.best_thirds,
            "knockout": {phase: [m.to_dict() if isinstance(m, Match) else m for m in matches] for phase, matches in self.knockout.items()},
            "champion": self.champion,
            "submission_id": self.submission_id,
            "submitted_at": self.submitted_at,
            "status": self.status,
            "meta": self.meta,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Prediction":
        groups = {g: list(data.get("groups", {}).get(g, [None, None, None, None]))[:4] for g in GROUPS}
        for g in GROUPS:
            while len(groups[g]) < 4:
                groups[g].append(None)
        knockout: dict[str, list[Match]] = {}
        for phase in PHASES:
            raw_matches = data.get("knockout", {}).get(phase, [])
            knockout[phase] = [Match(m.get("a"), m.get("b"), m.get("winner")) for m in raw_matches if isinstance(m, dict)]
        return cls(
            participant=data.get("participant") or data.get("participante") or "Participante",
            groups=groups,
            best_thirds=list(data.get("best_thirds") or data.get("melhores_terceiros") or []),
            knockout=knockout,
            champion=data.get("champion") or data.get("campeao"),
            submission_id=data.get("submission_id"),
            submitted_at=data.get("submitted_at"),
            status=data.get("status", "confirmado"),
            meta=dict(data.get("meta", {})),
        )


@dataclass
class ScoreBreakdown:
    participant: str
    total: int = 0
    group_points: int = 0
    best_third_points: int = 0
    knockout_points: int = 0
    champion_points: int = 0
    champion_hit: int = 0
    group_hits: int = 0
    best_third_hits: int = 0
    knockout_hits: int = 0
    details: list[dict[str, Any]] = field(default_factory=list)
    tie_breaker: str = ""

    def to_row(self, position: int | None = None) -> dict[str, Any]:
        row = {
            "Posição": position,
            "Participante": self.participant,
            "Pontos": self.total,
            "Grupos": self.group_points,
            "Terceiros": self.best_third_points,
            "Mata-mata": self.knockout_points,
            "Campeã": "Sim" if self.champion_hit else "Não",
            "Desempate": self.tie_breaker,
        }
        return row
