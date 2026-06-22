"""Health check for Bolão Copa Sanca — validates project structure and data integrity."""
import json
import sys
import importlib.util
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
STATE_DIR = BASE / "data" / "state"
sys.path.insert(0, str(BASE))

REQUIRED_FILES = [
    "app.py",
    "src/bolao/__init__.py",
    "src/bolao/models.py",
    "src/bolao/storage.py",
    "src/bolao/ui_ranking.py",
    "src/bolao/live_scoring.py",
    "src/bolao/scoring.py",
    "src/bolao/utils.py",
    "requirements.txt",
]

REQUIRED_JSONS = [
    "config.json",
    "matches_2026.json",
    "live_predictions.json",
    "registered_participants.json",
    "official_result.json",
    "archived_participants.json",
    "events.json",
    "artilheiro_palpites_dia.json",
    "artilheiro_palpites_rodada.json",
]

CRITICAL_IMPORTS = [
    "src.bolao.models",
    "src.bolao.storage",
    "src.bolao.ui_ranking",
    "src.bolao.live_scoring",
    "src.bolao.scoring",
    "src.bolao.utils",
]


def check(condition: bool, label: str) -> str:
    symbol = "PASS" if condition else "FAIL"
    print(f"  [{symbol}] {label}")
    return symbol


def main() -> int:
    print("--- Bolao Copa Sanca - Health Check ---\n")
    errors = 0

    print("[1] Arquivos obrigatorios")
    for f in REQUIRED_FILES:
        ok = (BASE / f).exists()
        if not ok:
            errors += 1
        check(ok, f"{f}")

    print("\n[2] JSONs de estado")
    for f in REQUIRED_JSONS:
        path = STATE_DIR / f
        ok = path.exists()
        if not ok:
            errors += 1
            check(ok, f"{f}")
            continue
        try:
            json.loads(path.read_text(encoding="utf-8"))
            check(True, f"{f} (válido)")
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            errors += 1
            check(False, f"{f} (inválido: {e})")

    print("\n[3] Imports criticos")
    for mod_name in CRITICAL_IMPORTS:
        try:
            importlib.import_module(mod_name)
            check(True, f"{mod_name}")
        except Exception as e:
            errors += 1
            check(False, f"{mod_name} — {e}")

    print("\n[4] Requirements")
    req_path = BASE / "requirements.txt"
    if req_path.exists():
        lines = [l.strip() for l in req_path.read_text().splitlines() if l.strip() and not l.startswith("#")]
        check(len(lines) > 0, f"{len(lines)} dependências listadas")
    else:
        errors += 1
        check(False, "requirements.txt ausente")

    summary = "\n--- Health check concluido (OK)" if errors == 0 else f"\n--- {errors} falha(s) encontrada(s)"
    print(summary)
    return 1 if errors > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
