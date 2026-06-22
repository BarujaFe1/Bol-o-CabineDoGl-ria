"""Remove Testador Sanca and TestUser from the system."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.bolao.storage import (
    load_registered_participants, save_registered_participants,
    load_archived_participants, save_archived_participants,
    load_submissions, load_live_predictions, save_live_predictions,
    normalize_participant_key, now_iso, append_event, SUBMISSIONS_DIR
)

TEST_USERS = ["Testador Sanca", "TestUser"]

def main():
    # 1. Remove from registered participants
    registered = load_registered_participants(include_archived=True)
    kept = [p for p in registered if p not in TEST_USERS]
    save_registered_participants(kept)
    removed = [p for p in registered if p in TEST_USERS]
    print("Register: {} removidos, {} mantidos".format(len(removed), len(kept)))

    # 2. Add to archived
    archived = load_archived_participants()
    for name in removed:
        key = normalize_participant_key(name)
        if not any(a.get("participant_key") == key for a in archived):
            archived.append({
                "name": name, "participant_key": key,
                "archived_at": now_iso(), "reason": "excluido_pelo_admin",
                "had_classic_prediction": False, "live_predictions_count": 0,
                "backup_reference": "limpeza_test_users"
            })
    save_archived_participants(archived)

    # 3. Delete classic submissions
    for p in TEST_USERS:
        key = normalize_participant_key(p)
        for f in SUBMISSIONS_DIR.glob("{}*.json".format(key)):
            f.unlink()
            print("  Submission removido: {}".format(f.name))

    # 4. Delete live predictions
    lp_list = load_live_predictions(include_archived=True)
    kept_lp = [lp for lp in lp_list if lp.participant_name not in TEST_USERS]
    removed_lp = len(lp_list) - len(kept_lp)
    if removed_lp > 0:
        save_live_predictions(kept_lp)
        print("Live predictions removidas: {}".format(removed_lp))

    append_event("test_users_cleaned",
                 "Usuarios de teste removidos: {}".format(", ".join(removed)),
                 visibility="admin")
    print("\nLimpeza concluida!")

if __name__ == "__main__":
    main()
