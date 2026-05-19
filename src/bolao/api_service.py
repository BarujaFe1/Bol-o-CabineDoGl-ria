
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
        self.api_key = api_key or os.getenv("APIFOOTBALL_KEY") or os.getenv("API_FOOTBALL_KEY")

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
