import os
import requests
import time
import logging
from datetime import datetime, timezone

from src.bolao.storage import load_matches, save_matches, load_live_predictions, save_live_predictions, load_config, append_event
from src.bolao.utils import canonical_team
from src.bolao.live_scoring import calculate_live_prediction_points

API_KEY = os.environ.get("FOOTBALL_DATA_API_KEY", "")
BASE_URL = "https://api.football-data.org/v4"
HEADERS = {"X-Auth-Token": API_KEY} if API_KEY else {}

def fetch_matches(status_filter: str = "IN_PLAY,FINISHED,PAUSED") -> list[dict]:
    """Busca jogos da Copa 2026 por status."""
    if not API_KEY:
        logging.warning("[score_updater] Chave FOOTBALL_DATA_API_KEY não configurada.")
        return []
    url = f"{BASE_URL}/competitions/WC/matches"
    params = {"season": 2026, "status": status_filter}
    try:
        resp = requests.get(url, headers=HEADERS, params=params, timeout=15)
        resp.raise_for_status()
        return resp.json().get("matches", [])
    except requests.exceptions.RequestException as e:
        logging.error(f"[score_updater] Erro na API football-data.org: {e}")
        return []

def run_score_sync(supabase_client=None) -> dict:
    """
    Função principal de sincronização de placares e recálculo de pontuações.
    Lê a agenda do football-data.org e atualiza o estado local e/ou Supabase.
    """
    if not API_KEY:
        return {"erro": "Chave FOOTBALL_DATA_API_KEY não configurada nas variáveis de ambiente ou nos secrets.", "atualizados": 0, "ao_vivo": 0}

    matches_api = fetch_matches()
    if not matches_api:
        return {
            "atualizados": 0, 
            "ao_vivo": 0, 
            "erros": [], 
            "mensagem": "Nenhum jogo retornado da API ou ocorreu um erro na busca."
        }

    # Carregar dados locais/Supabase de forma agnóstica
    db_matches = load_matches()
    all_preds = load_live_predictions()
    config = load_config()

    updated_count = 0
    live_count = 0
    erros = []

    for match in matches_api:
        api_id = match.get("id")
        status = match.get("status")
        score = match.get("score", {}).get("fullTime", {})
        home_goals = score.get("home")
        away_goals = score.get("away")

        # Mapeamento do status para o nosso DB
        if status in ("IN_PLAY", "PAUSED"):
            live_count += 1
            db_status = "live"
        elif status == "FINISHED":
            db_status = "result_approved"
        else:
            db_status = "scheduled"

        # Tentar parear com algum jogo da nossa agenda
        # 1. Por api_match_id se já estiver gravado
        db_m = None
        for candidate in db_matches:
            if getattr(candidate, "api_match_id", None) == api_id:
                db_m = candidate
                break

        # 2. Fallback: tentar parear por time mandante, visitante e canonical_team
        if not db_m:
            api_home = canonical_team(match.get("homeTeam", {}).get("name"))
            api_away = canonical_team(match.get("awayTeam", {}).get("name"))
            
            for candidate in db_matches:
                cand_home = canonical_team(candidate.home_team)
                cand_away = canonical_team(candidate.away_team)
                if cand_home == api_home and cand_away == api_away:
                    db_m = candidate
                    db_m.api_match_id = api_id
                    break

        if db_m:
            # Proteção: não sobrescrever resultados já aprovados/concluídos
            if db_m.status == "result_approved":
                continue

            # Atualizar se houver alteração de placar ou status
            goals_changed = (db_m.official_home_goals != home_goals or db_m.official_away_goals != away_goals)
            status_changed = (db_m.status != db_status)

            if goals_changed or status_changed:
                if home_goals is not None and away_goals is not None:
                    db_m.official_home_goals = int(home_goals)
                    db_m.official_away_goals = int(away_goals)
                    if home_goals > away_goals:
                        db_m.winner = db_m.home_team
                    elif home_goals < away_goals:
                        db_m.winner = db_m.away_team
                    else:
                        db_m.winner = "draw"
                
                db_m.status = db_status
                db_m.source = "football-data.org"

                # Se o jogo finalizou, recalcular palpites dos participantes
                if db_status == "result_approved" and home_goals is not None and away_goals is not None:
                    match_preds = [p for p in all_preds if p.match_id == db_m.match_id]
                    for p in match_preds:
                        res = calculate_live_prediction_points(p, db_m, config)
                        p.points = res["points"]
                        p.scoring_breakdown = res["breakdown"]
                        p.is_locked = True
                
                updated_count += 1
                time.sleep(0.1)  # Respeitar rate limit

    if updated_count > 0:
        save_matches(db_matches)
        save_live_predictions(all_preds)
        append_event(
            kind="api_results_synced",
            message=f"Sincronização via API football-data.org: {updated_count} jogos finalizados/atualizados e palpites recalculados.",
            visibility="admin"
        )

    logging.info(f"[score_updater] Sincronização concluída: {updated_count} jogos atualizados, {live_count} ao vivo.")
    return {
        "atualizados": updated_count,
        "ao_vivo": live_count,
        "erros": erros,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

def has_live_matches_today(supabase_client=None) -> bool:
    """Verifica rapidamente se há jogos ao vivo no momento."""
    if not API_KEY:
        return False
    matches = fetch_matches(status_filter="IN_PLAY,PAUSED")
    return len(matches) > 0
