import json, os, shutil
from datetime import datetime

STATE_DIR = "data/state"
ROOT_LP_FILE = "live_predictions.json"
BACKUP_FILE = "backup_geral_completo.json"

def read_json_safe(path, default=None):
    if not os.path.exists(path):
        return default
    for encoding in ["utf-8", "latin-1", "cp1252"]:
        try:
            with open(path, "r", encoding=encoding) as f:
                return json.load(f)
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
    return default

def main():
    print("=== LEVANTAMENTO DOS DADOS ATUAIS ===")
    
    # 1. Live predictions - usar state (358) como mestre
    state_lp = read_json_safe(os.path.join(STATE_DIR, "live_predictions.json"), [])
    print(f"State live_predictions.json: {len(state_lp)} previsões")
    
    # 2. Root live_predictions (286) - será substituído
    root_lp = read_json_safe(ROOT_LP_FILE, [])
    print(f"Root live_predictions.json: {len(root_lp)} previsões")
    
    # Comparar e mostrar diferenças
    state_ids = set(p.get("id") for p in state_lp)
    root_ids = set(p.get("id") for p in root_lp)
    
    only_in_state = state_ids - root_ids
    only_in_root = root_ids - state_ids
    
    if only_in_state:
        print(f"\nPrevisões APENAS no state (SALVAS): {len(only_in_state)}")
        # Mostrar detalhes
        by_name = {}
        for pid in only_in_state:
            for p in state_lp:
                if p.get("id") == pid:
                    n = p.get("participant_name", "?")
                    by_name[n] = by_name.get(n, 0) + 1
                    break
        for n, c in sorted(by_name.items()):
            print(f"  + {n}: {c}")
    
    if only_in_root:
        print(f"\nPrevisões APENAS no root (SERÃO PERDIDAS): {len(only_in_root)}")
    
    # 3. Submissions clássicas
    sub_dir = os.path.join(STATE_DIR, "submissions")
    if os.path.isdir(sub_dir):
        subs = [f for f in os.listdir(sub_dir) if f.endswith(".json") and f != ".gitkeep"]
        print(f"\nSubmissões clássicas: {len(subs)}")
        for fn in subs:
            fp = os.path.join(sub_dir, fn)
            s = read_json_safe(fp, {})
            pname = s.get("participant", fn)
            champion = s.get("champion", "?")
            print(f"  - {pname} (campeão: {champion})")
    
    # 4. Registered participants
    rp = read_json_safe(os.path.join(STATE_DIR, "registered_participants.json"), [])
    print(f"\nParticipantes registrados: {len(rp)}")
    for p in rp:
        print(f"  - {p}")
    
    # 5. Other state files
    for fname in ["config.json", "official_result.json", "events.json",
                  "brasil_palpites_goleadores.json", "brasil_resultados_goleadores.json",
                  "brasil_palpites_classicos.json", "ranking_snapshots.json", "comentarios_jogo.json",
                  "archived_participants.json", "migrations.json",
                  "artilheiro_palpites_dia.json", "artilheiro_palpites_rodada.json",
                  "artilheiro_resultado_dia.json", "artilheiro_resultado_rodada.json"]:
        fpath = os.path.join(STATE_DIR, fname)
        data = read_json_safe(fpath, None)
        if data is not None:
            if isinstance(data, list):
                print(f"  {fname}: {len(data)} itens")
            elif isinstance(data, dict):
                print(f"  {fname}: dict com {len(data)} chaves")
            else:
                print(f"  {fname}: {type(data).__name__}")
    
    # === AÇÕES DE RECUPERAÇÃO ===
    print("\n\n=== EXECUTANDO RECUPERAÇÃO ===")
    
    # Ação 1: Copiar state_lp para root live_predictions.json
    if len(state_lp) >= len(root_lp):
        print(f"Copiando state live_predictions.json ({len(state_lp)}) -> root live_predictions.json")
        with open(ROOT_LP_FILE, "w", encoding="utf-8") as f:
            json.dump(state_lp, f, ensure_ascii=False, indent=2)
        print("  OK - Root live_predictions.json atualizado!")
    else:
        print(f"AVISO: state ({len(state_lp)}) < root ({len(root_lp)}), não substituindo")
    
    # Ação 2: Criar backup completo com timestamp
    import copy
    full_backup = {
        "config": read_json_safe(os.path.join(STATE_DIR, "config.json"), {}),
        "official": read_json_safe(os.path.join(STATE_DIR, "official_result.json"), {}),
        "submissions": [],
        "live_predictions": copy.deepcopy(state_lp),
        "matches": read_json_safe(os.path.join(STATE_DIR, "matches_2026.json"), []),
        "events": read_json_safe(os.path.join(STATE_DIR, "events.json"), []),
        "migrations": read_json_safe(os.path.join(STATE_DIR, "migrations.json"), {}),
        "registered_participants": read_json_safe(os.path.join(STATE_DIR, "registered_participants.json"), []),
        "archived_participants": read_json_safe(os.path.join(STATE_DIR, "archived_participants.json"), []),
        "brasil_palpites_goleadores": read_json_safe(os.path.join(STATE_DIR, "brasil_palpites_goleadores.json"), []),
        "brasil_resultados_goleadores": read_json_safe(os.path.join(STATE_DIR, "brasil_resultados_goleadores.json"), []),
        "brasil_palpites_classicos": read_json_safe(os.path.join(STATE_DIR, "brasil_palpites_classicos.json"), []),
        "ranking_snapshots": read_json_safe(os.path.join(STATE_DIR, "ranking_snapshots.json"), []),
        "comentarios_jogo": read_json_safe(os.path.join(STATE_DIR, "comentarios_jogo.json"), []),
        "artilheiro_palpites_dia": read_json_safe(os.path.join(STATE_DIR, "artilheiro_palpites_dia.json"), []),
        "artilheiro_palpites_rodada": read_json_safe(os.path.join(STATE_DIR, "artilheiro_palpites_rodada.json"), []),
        "artilheiro_resultado_dia": read_json_safe(os.path.join(STATE_DIR, "artilheiro_resultado_dia.json"), []),
        "artilheiro_resultado_rodada": read_json_safe(os.path.join(STATE_DIR, "artilheiro_resultado_rodada.json"), []),
        "timestamp": datetime.now().isoformat(),
        "app_version": "2026-live-mode-v2",
    }
    
    # Add classic submissions
    for fn in subs:
        fp = os.path.join(sub_dir, fn)
        s = read_json_safe(fp, {})
        if s:
            full_backup["submissions"].append(s)
    print(f"Adicionadas {len(full_backup['submissions'])} submissões clássicas ao backup")
    
    # Salvar backup  
    with open(BACKUP_FILE, "w", encoding="utf-8") as f:
        json.dump(full_backup, f, ensure_ascii=False, indent=2)
    size_mb = os.path.getsize(BACKUP_FILE) / (1024*1024)
    print(f"✓ Backup salvo em {BACKUP_FILE} ({size_mb:.2f} MB)")
    
    # Ação 3: Verificar se há previsões dos "sem palpite clássico"
    classic_participants = set()
    for fn in subs:
        fp = os.path.join(sub_dir, fn)
        s = read_json_safe(fp, {})
        classic_participants.add(s.get("participant"))
    
    live_participants = set(p.get("participant_name") for p in state_lp)
    live_only = live_participants - classic_participants
    print(f"\n=== PARTICIPANTES SEM PALPITE CLÁSSICO (APENAS LIVE) ===")
    for p in sorted(live_only):
        count = sum(1 for lp in state_lp if lp.get("participant_name") == p)
        print(f"  ✓ {p}: {count} previsões live preservadas")
    
    print("\n✅ RECUPERAÇÃO CONCLUÍDA!")
    print(f"   {len(state_lp)} previsões live no root live_predictions.json")
    print(f"   {len(full_backup['submissions'])} submissões clássicas no backup")
    print(f"   {len(full_backup['live_predictions'])} previsões live no backup")

if __name__ == "__main__":
    main()
