
from __future__ import annotations

import re
from typing import Any

from .constants import CHAMPION_ALIASES, PHASE_ALIASES, PHASE_LABELS, PHASES
from .models import Match, ParseIssue
from .utils import canonical_team, norm_text


def detect_section(line: str) -> str | None:
    clean = norm_text(line)
    clean = clean.replace("de final", "").strip()
    if clean in PHASE_ALIASES:
        return PHASE_ALIASES[clean]
    for alias, phase in PHASE_ALIASES.items():
        if clean == alias or clean.startswith(alias + " "):
            return phase
    return None


def is_champion_heading(line: str) -> bool:
    clean = norm_text(line)
    return clean in {norm_text(x) for x in CHAMPION_ALIASES}


def is_noise(line: str) -> bool:
    clean = norm_text(line)
    if not clean:
        return True
    if clean.startswith("simulador copa"):
        return True
    if "ge globo" in clean or "geglobonacopa" in clean or "ge globo simulador" in clean:
        return True
    if clean.startswith("http") or "ge globo simulador" in clean:
        return True
    if line.strip().startswith("#"):
        return True
    return False


def split_match(line: str) -> tuple[str, str] | None:
    value = re.sub(r"\s+", " ", line.strip())
    value = value.replace("–", "-").replace("—", "-")
    # Keep the common "x" separator used by ge.
    match = re.match(r"^(.+?)\s+(?:x|X|vs\.?|VS)\s+(.+?)$", value)
    if not match:
        return None
    left = match.group(1).strip(" -\t")
    right = match.group(2).strip(" -\t")
    if not left or not right:
        return None
    return left, right


def _teams_in_phase(matches: list[Match]) -> set[str]:
    teams: set[str] = set()
    for m in matches:
        if m.a:
            teams.add(norm_text(m.a))
        if m.b:
            teams.add(norm_text(m.b))
    return teams


def derive_winners(knockout: dict[str, list[Match]], champion: str | None) -> list[ParseIssue]:
    issues: list[ParseIssue] = []
    for idx, phase in enumerate(PHASES):
        next_teams: set[str] = set()
        if phase == "final":
            if champion:
                next_teams = {norm_text(champion)}
        else:
            next_phase = PHASES[idx + 1]
            next_teams = _teams_in_phase(knockout.get(next_phase, []))

        for i, m in enumerate(knockout.get(phase, []), start=1):
            candidates = []
            if m.a and norm_text(m.a) in next_teams:
                candidates.append(m.a)
            if m.b and norm_text(m.b) in next_teams:
                candidates.append(m.b)

            if len(candidates) == 1:
                m.winner = candidates[0]
            elif len(candidates) == 0:
                m.winner = None
                issues.append(ParseIssue("warning", f"Não consegui inferir o vencedor do jogo {i} em {PHASE_LABELS[phase]}.", f"{m.a} x {m.b}"))
            else:
                m.winner = None
                issues.append(ParseIssue("warning", f"Vencedor ambíguo no jogo {i} em {PHASE_LABELS[phase]}.", f"{m.a} x {m.b}"))
    return issues


def parse_ge_knockout_text(text: str) -> tuple[dict[str, list[Match]], str | None, list[ParseIssue], dict[str, Any]]:
    knockout = {phase: [] for phase in PHASES}
    issues: list[ParseIssue] = []
    current_phase: str | None = None
    champion: str | None = None
    expect_champion_next = False
    invalid_lines: list[str] = []

    lines = [line.strip() for line in (text or "").replace("\r", "\n").split("\n")]
    for raw in lines:
        line = raw.strip()
        if is_noise(line):
            continue

        if expect_champion_next:
            if line:
                champion = canonical_team(line.strip())
                expect_champion_next = False
                current_phase = None
                continue

        section = detect_section(line)
        if section:
            current_phase = section
            continue

        if is_champion_heading(line):
            expect_champion_next = True
            current_phase = None
            continue

        clean = norm_text(line)
        for heading in CHAMPION_ALIASES:
            h = norm_text(heading)
            if clean.startswith(h + " "):
                champion = canonical_team(line.split(None, 1)[1].strip())
                current_phase = None
                break
        if champion and current_phase is None:
            continue

        if current_phase:
            parsed = split_match(line)
            if parsed:
                a, b = parsed
                knockout[current_phase].append(Match(a=canonical_team(a), b=canonical_team(b), winner=None))
            else:
                invalid_lines.append(line)

    for phase in PHASES:
        if not knockout[phase]:
            issues.append(ParseIssue("error", f"Fase ausente ou sem confrontos: {PHASE_LABELS[phase]}."))
    if not champion:
        issues.append(ParseIssue("error", "Campeã ausente. O texto precisa ter a seção Campeã ou Campeão."))

    seen: set[str] = set()
    for phase, matches in knockout.items():
        for m in matches:
            key = f"{phase}:{norm_text(m.a)}:{norm_text(m.b)}"
            reverse = f"{phase}:{norm_text(m.b)}:{norm_text(m.a)}"
            if key in seen or reverse in seen:
                issues.append(ParseIssue("warning", f"Confronto duplicado em {PHASE_LABELS[phase]}.", f"{m.a} x {m.b}"))
            seen.add(key)

    if invalid_lines:
        for line in invalid_lines[:8]:
            issues.append(ParseIssue("warning", "Linha ignorada no texto do mata-mata.", line))
        if len(invalid_lines) > 8:
            issues.append(ParseIssue("warning", f"{len(invalid_lines) - 8} outras linhas foram ignoradas."))

    issues.extend(derive_winners(knockout, champion))

    meta = {
        "match_counts": {phase: len(knockout[phase]) for phase in PHASES},
        "complete": not any(issue.level == "error" for issue in issues),
    }
    return knockout, champion, issues, meta


def knockout_to_rows(knockout: dict[str, list[Match]]) -> list[dict[str, Any]]:
    rows = []
    for phase in PHASES:
        for i, match in enumerate(knockout.get(phase, []), start=1):
            rows.append({
                "fase": phase,
                "fase_nome": PHASE_LABELS[phase],
                "jogo": i,
                "time_a": match.a,
                "time_b": match.b,
                "vencedor": match.winner,
            })
    return rows


def rows_to_knockout(rows: list[dict[str, Any]]) -> dict[str, list[Match]]:
    knockout = {phase: [] for phase in PHASES}
    for row in rows:
        phase = row.get("fase")
        if phase in knockout:
            knockout[phase].append(Match(
                a=row.get("time_a") or row.get("a"),
                b=row.get("time_b") or row.get("b"),
                winner=row.get("vencedor") or row.get("winner"),
            ))
    return knockout
