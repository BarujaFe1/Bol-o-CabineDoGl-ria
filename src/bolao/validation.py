
from __future__ import annotations

from .constants import GROUPS, PHASES
from .models import Prediction, ParseIssue


def validate_prediction(pred: Prediction, strict: bool = False) -> list[ParseIssue]:
    issues: list[ParseIssue] = []
    if not pred.participant or len(pred.participant.strip()) < 2:
        issues.append(ParseIssue("error", "Informe o nome do participante."))

    for g in GROUPS:
        values = pred.groups.get(g, [])
        if len(values) != 4:
            issues.append(ParseIssue("error", f"Grupo {g} precisa ter 4 posições."))
            continue
        clean = [v for v in values if v]
        if len(clean) < 4:
            issues.append(ParseIssue("warning" if not strict else "error", f"Grupo {g} está incompleto."))
        if len(clean) != len(set(clean)):
            issues.append(ParseIssue("warning", f"Grupo {g} tem seleção repetida."))

    for phase in PHASES:
        matches = pred.knockout.get(phase, [])
        if not matches:
            issues.append(ParseIssue("warning" if not strict else "error", f"Mata-mata sem jogos em {phase}."))
        for idx, m in enumerate(matches, start=1):
            if not m.a or not m.b:
                issues.append(ParseIssue("warning", f"Jogo {idx} em {phase} está sem os dois times."))
            if not m.winner:
                issues.append(ParseIssue("warning", f"Jogo {idx} em {phase} está sem vencedor."))
            elif m.a and m.b and m.winner not in {m.a, m.b}:
                issues.append(ParseIssue("warning", f"Vencedor do jogo {idx} em {phase} não está no confronto.", f"{m.a} x {m.b} → {m.winner}"))

    if not pred.champion:
        issues.append(ParseIssue("warning" if not strict else "error", "Campeã não informada."))
    return issues


def has_blocking_errors(issues: list[ParseIssue]) -> bool:
    return any(i.level == "error" for i in issues)
