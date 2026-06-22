
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import requests

from .models import Prediction
from .utils import now_iso


@dataclass
class APIResponse:
    ok: bool
    message: str
    raw: dict[str, Any] | None = None
    prediction: Prediction | None = None


class APIFootballService:
    """
    Integração isolada com API-FOOTBALL/API-Sports.

    A API real pode expor fixtures, standings e resultados em estruturas próprias.
    Por isso este serviço mantém o dado bruto e deixa a aprovação final sempre
    passar pela Central de Resultados Oficiais.
    """

    base_url = "https://v3.football.api-sports.io"

    def __init__(self, api_key: str | None = None):
        st_key = None
        try:
            import streamlit as st
            st_key = st.secrets.get("APIFOOTBALL_KEY") or st.secrets.get("API_FOOTBALL_KEY")
        except Exception:
            pass
        self.api_key = api_key or st_key or os.getenv("APIFOOTBALL_KEY") or os.getenv("API_FOOTBALL_KEY")

    def _headers(self) -> dict[str, str]:
        return {"x-apisports-key": self.api_key or ""}

    def enabled(self) -> bool:
        return bool(self.api_key)

    def fetch_world_cup_2026(self) -> APIResponse:
        if not self.enabled():
            return APIResponse(False, "Chave APIFOOTBALL_KEY não configurada. Use texto manual enquanto isso.")

        raw: dict[str, Any] = {"synced_at": now_iso(), "fixtures": None, "standings": None}
        try:
            # League ID 1 is commonly used by API-FOOTBALL for World Cup.
            fixtures = requests.get(
                f"{self.base_url}/fixtures",
                headers=self._headers(),
                params={"league": 1, "season": 2026},
                timeout=20,
            )
            fixtures.raise_for_status()
            raw["fixtures"] = fixtures.json()

            standings = requests.get(
                f"{self.base_url}/standings",
                headers=self._headers(),
                params={"league": 1, "season": 2026},
                timeout=20,
            )
            # Standings may be absent before/while the tournament is not covered.
            raw["standings"] = standings.json() if standings.ok else {"status_code": standings.status_code, "text": standings.text[:500]}

            prediction = self._adapt_raw_to_prediction(raw)
            return APIResponse(True, "Sincronização concluída. Revise antes de aprovar.", raw=raw, prediction=prediction)
        except requests.HTTPError as exc:
            return APIResponse(False, f"API retornou erro HTTP: {exc}", raw=raw)
        except requests.RequestException as exc:
            return APIResponse(False, f"Falha de rede ao consultar API: {exc}", raw=raw)
        except Exception as exc:
            return APIResponse(False, f"Falha inesperada na integração: {exc}", raw=raw)

    def _adapt_raw_to_prediction(self, raw: dict[str, Any]) -> Prediction:
        # A adaptação completa depende da estrutura que a API disponibilizará durante a Copa.
        # O app preserva os dados brutos e deixa revisão manual, evitando consolidar algo errado.
        pred = Prediction(participant="Resultado oficial via API")
        pred.meta = {
            "source": "api-football",
            "synced_at": raw.get("synced_at"),
            "api_note": "Dados importados como rascunho. Revise manualmente antes de aprovar.",
            "raw_counts": {
                "fixtures": len((raw.get("fixtures") or {}).get("response") or []),
                "standings_blocks": len((raw.get("standings") or {}).get("response") or []),
            },
        }
        # Fixtures can still help admin see matches, even when final adapter is incomplete.
        fixtures = ((raw.get("fixtures") or {}).get("response") or [])
        pred.meta["fixtures_preview"] = [
            {
                "date": f.get("fixture", {}).get("date"),
                "round": f.get("league", {}).get("round"),
                "home": f.get("teams", {}).get("home", {}).get("name"),
                "away": f.get("teams", {}).get("away", {}).get("name"),
                "home_winner": f.get("teams", {}).get("home", {}).get("winner"),
                "away_winner": f.get("teams", {}).get("away", {}).get("winner"),
            }
            for f in fixtures[:80]
        ]
        return pred

    def sync_matches_scores_with_api(self) -> APIResponse:
        if not self.enabled():
            return APIResponse(False, "Chave APIFOOTBALL_KEY não configurada. Configure para sincronizar por API.")

        try:
            # 1. Fetch fixtures
            response = requests.get(
                f"{self.base_url}/fixtures",
                headers=self._headers(),
                params={"league": 1, "season": 2026},
                timeout=20,
            )
            response.raise_for_status()
            res_json = response.json()
            fixtures = res_json.get("response", [])
            if not fixtures:
                return APIResponse(False, "Nenhum jogo encontrado na API-Football para a Copa de 2026.")

            # 2. Load existing matches
            from .storage import load_matches, save_matches, load_live_predictions, save_live_predictions, load_config
            from .utils import canonical_team
            from .live_scoring import calculate_live_prediction_points
            
            matches = load_matches()
            all_preds = load_live_predictions()
            config = load_config()

            updated_count = 0
            live_count = 0
            
            # Match fixtures by canonical team names
            for f in fixtures:
                api_home = f.get("teams", {}).get("home", {}).get("name")
                api_away = f.get("teams", {}).get("away", {}).get("name")
                
                canon_home = canonical_team(api_home)
                canon_away = canonical_team(api_away)
                
                # Find matching match
                m = None
                for candidate in matches:
                    cand_home = canonical_team(candidate.home_team)
                    cand_away = canonical_team(candidate.away_team)
                    if cand_home == canon_home and cand_away == canon_away:
                        m = candidate
                        break
                
                if m:
                    status_short = f.get("fixture", {}).get("status", {}).get("short")
                    goals_home = f.get("goals", {}).get("home")
                    goals_away = f.get("goals", {}).get("away")
                    
                    if status_short in ("FT", "AET", "PEN"):
                        if goals_home is not None and goals_away is not None:
                            if m.status != "result_approved" or m.official_home_goals != goals_home or m.official_away_goals != goals_away:
                                m.official_home_goals = int(goals_home)
                                m.official_away_goals = int(goals_away)
                                m.status = "result_approved"
                                if goals_home > goals_away:
                                    m.winner = m.home_team
                                elif goals_home < goals_away:
                                    m.winner = m.away_team
                                else:
                                    m.winner = "draw"
                                
                                # Recalculate predictions score for this match
                                match_preds = [p for p in all_preds if p.match_id == m.match_id]
                                for p in match_preds:
                                    res = calculate_live_prediction_points(p, m, config)
                                    p.points = res["points"]
                                    p.scoring_breakdown = res["breakdown"]
                                    p.is_locked = True
                                
                                updated_count += 1
                    elif status_short in ("1H", "2H", "HT", "ET", "P", "LIVE"):
                        if goals_home is not None and goals_away is not None:
                            if m.status != "live" or m.official_home_goals != goals_home or m.official_away_goals != goals_away:
                                m.official_home_goals = int(goals_home)
                                m.official_away_goals = int(goals_away)
                                m.status = "live"
                                live_count += 1

            if updated_count > 0 or live_count > 0:
                save_matches(matches)
                save_live_predictions(all_preds)
                from .storage import append_event, sync_matches_to_official
                synced_off = sync_matches_to_official()
                append_event(
                    kind="api_results_synced",
                    message=f"Sincronização via API: {updated_count} jogos finalizados e {live_count} ao vivo atualizados. {synced_off} jogos copiados para o Simulador Oficial.",
                    visibility="admin"
                )
            
            msg = f"Sincronização concluída: {updated_count} jogos finalizados e {live_count} ao vivo foram atualizados e processados."
            return APIResponse(True, msg, raw={"updated_finished": updated_count, "updated_live": live_count})
        except Exception as exc:
            return APIResponse(False, f"Erro ao sincronizar resultados via API: {exc}")
