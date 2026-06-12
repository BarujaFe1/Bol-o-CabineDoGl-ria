
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
    mode: str = "classic"
    schema_version: str = "classic-v1"

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
            "mode": self.mode,
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Prediction":
        from .utils import format_display_name
        raw_name = data.get("participant") or data.get("participante") or "Participante"
        participant = format_display_name(raw_name)
        groups = {g: list(data.get("groups", {}).get(g, [None, None, None, None]))[:4] for g in GROUPS}
        for g in GROUPS:
            while len(groups[g]) < 4:
                groups[g].append(None)
        knockout: dict[str, list[Match]] = {}
        for phase in PHASES:
            raw_matches = data.get("knockout", {}).get(phase, [])
            knockout[phase] = [Match(m.get("a"), m.get("b"), m.get("winner")) for m in raw_matches if isinstance(m, dict)]
        return cls(
            participant=participant,
            groups=groups,
            best_thirds=list(data.get("best_thirds") or data.get("melhores_terceiros") or []),
            knockout=knockout,
            champion=data.get("champion") or data.get("campeao"),
            submission_id=data.get("submission_id"),
            submitted_at=data.get("submitted_at"),
            status=data.get("status", "confirmado"),
            meta=dict(data.get("meta", {})),
            mode=data.get("mode", "classic"),
            schema_version=data.get("schema_version", "classic-v1"),
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
    exact_scores: int = 0
    submitted_at: str = ""
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


@dataclass
class LiveMatch:
    match_id: str
    phase: str
    group: str
    round_label: str
    home_team: str
    away_team: str
    starts_at: str  # ISO timestamp
    starts_at_timezone: str = "America/Sao_Paulo"
    lock_at: str | None = None
    status: str = "scheduled"  # scheduled, locked, live, finished, result_approved
    official_home_goals: int | None = None
    official_away_goals: int | None = None
    winner: str | None = None  # time vencedor ou 'draw'
    source: str = "manual"  # manual, official_result, imported
    sort_order: int = 0
    bets_manual_closed: bool | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "match_id": self.match_id,
            "phase": self.phase,
            "group": self.group,
            "round_label": self.round_label,
            "home_team": self.home_team,
            "away_team": self.away_team,
            "starts_at": self.starts_at,
            "starts_at_timezone": self.starts_at_timezone,
            "lock_at": self.lock_at,
            "status": self.status,
            "official_home_goals": self.official_home_goals,
            "official_away_goals": self.official_away_goals,
            "winner": self.winner,
            "source": self.source,
            "sort_order": self.sort_order,
            "bets_manual_closed": self.bets_manual_closed,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "LiveMatch":
        return cls(
            match_id=str(d.get("match_id", "")),
            phase=d.get("phase", ""),
            group=d.get("group", ""),
            round_label=d.get("round_label", d.get("round", "")),
            home_team=d.get("home_team", ""),
            away_team=d.get("away_team", ""),
            starts_at=d.get("starts_at", ""),
            starts_at_timezone=d.get("starts_at_timezone", "America/Sao_Paulo"),
            lock_at=d.get("lock_at"),
            status=d.get("status", "scheduled"),
            official_home_goals=d.get("official_home_goals") if d.get("official_home_goals") is None else int(d.get("official_home_goals")),
            official_away_goals=d.get("official_away_goals") if d.get("official_away_goals") is None else int(d.get("official_away_goals")),
            winner=d.get("winner"),
            source=d.get("source", "manual"),
            sort_order=int(d.get("sort_order", 0)),
            bets_manual_closed=d.get("bets_manual_closed") if d.get("bets_manual_closed") is None else bool(d.get("bets_manual_closed")),
        )


@dataclass
class LivePrediction:
    id: str  # unique id (key + "_" + match_id)
    participant_name: str
    participant_key: str
    match_id: str
    predicted_home_goals: int
    predicted_away_goals: int
    submitted_at: str
    updated_at: str
    confirmation_code: str | None = None
    locked_at: str | None = None
    is_locked: bool = False
    is_late: bool = False
    points: int | None = None
    scoring_breakdown: list[str] = field(default_factory=list)
    schema_version: str = "live-v1"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "participant_name": self.participant_name,
            "participant_key": self.participant_key,
            "match_id": self.match_id,
            "predicted_home_goals": self.predicted_home_goals,
            "predicted_away_goals": self.predicted_away_goals,
            "submitted_at": self.submitted_at,
            "updated_at": self.updated_at,
            "confirmation_code": self.confirmation_code,
            "locked_at": self.locked_at,
            "is_locked": self.is_locked,
            "is_late": self.is_late,
            "points": self.points,
            "scoring_breakdown": self.scoring_breakdown,
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "LivePrediction":
        from .utils import format_display_name, normalize_participant_key
        
        # 1. Format name and guarantee key
        raw_name = d.get("participant_name", "")
        participant_name = format_display_name(raw_name)
        participant_key = d.get("participant_key")
        if not participant_key:
            participant_key = normalize_participant_key(participant_name)
        else:
            participant_key = normalize_participant_key(participant_key)
            
        # 2. Match ID coercion
        match_id = str(d.get("match_id", ""))
        
        # 3. ID conversion & fallback
        pred_id = d.get("id") or d.get("prediction_id")
        if not pred_id:
            pred_id = f"{participant_key}_{match_id}"
            
        # 4. Coerce goals
        try:
            predicted_home_goals = int(d.get("predicted_home_goals", 0))
        except (ValueError, TypeError):
            predicted_home_goals = 0
            
        try:
            predicted_away_goals = int(d.get("predicted_away_goals", 0))
        except (ValueError, TypeError):
            predicted_away_goals = 0
            
        # 5. Points conversion
        points = d.get("points")
        if points is not None:
            try:
                points = int(points)
            except (ValueError, TypeError):
                points = None
                
        # 6. Normalize scoring breakdown
        raw_breakdown = d.get("scoring_breakdown")
        if raw_breakdown is None:
            scoring_breakdown = []
        elif isinstance(raw_breakdown, dict):
            scoring_breakdown = [f"{k}: {v}" for k, v in raw_breakdown.items()]
        elif isinstance(raw_breakdown, str):
            scoring_breakdown = [raw_breakdown]
        elif isinstance(raw_breakdown, list):
            scoring_breakdown = [str(x) for x in raw_breakdown]
        else:
            scoring_breakdown = [str(raw_breakdown)]

        return cls(
            id=pred_id,
            participant_name=participant_name,
            participant_key=participant_key,
            match_id=match_id,
            predicted_home_goals=predicted_home_goals,
            predicted_away_goals=predicted_away_goals,
            submitted_at=d.get("submitted_at", ""),
            updated_at=d.get("updated_at", ""),
            confirmation_code=d.get("confirmation_code"),
            locked_at=d.get("locked_at"),
            is_locked=bool(d.get("is_locked", False)),
            is_late=bool(d.get("is_late", False)),
            points=points,
            scoring_breakdown=scoring_breakdown,
            schema_version=d.get("schema_version", "live-v1"),
        )


@dataclass
class ActivityEvent:
    id: str
    timestamp: str
    kind: str
    message: str
    visibility: str = "public"  # public, admin
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "kind": self.kind,
            "message": self.message,
            "visibility": self.visibility,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ActivityEvent":
        return cls(
            id=d.get("id", ""),
            timestamp=d.get("timestamp", ""),
            kind=d.get("kind", ""),
            message=d.get("message", ""),
            visibility=d.get("visibility", "public"),
            metadata=dict(d.get("metadata") or {}),
        )
