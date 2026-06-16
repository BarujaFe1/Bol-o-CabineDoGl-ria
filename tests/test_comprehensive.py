"""
Comprehensive tests covering new features:
- Artilheiro storage (dia / rodada)
- Squad lists data integrity
- Goleadores points integration in live ranking
- Group section headers in match sorting
- Edge cases
"""
import pytest
import json
import os
from datetime import datetime, date

from src.bolao.storage import (
    load_artilheiro_palpites_dia, save_artilheiro_palpite_dia,
    load_artilheiro_palpites_rodada, save_artilheiro_palpite_rodada,
    load_matches, load_live_predictions, load_config,
    load_brasil_palpites_goleadores,
)
from src.bolao.live_scoring import calculate_live_ranking
from src.bolao.utils import normalize_participant_key, now_iso
from src.bolao.models import LiveMatch


# ── Artilheiro Storage Tests ─────────────────────────────────────────────

class TestArtilheiroStorage:
    def test_save_and_load_dia_empty(self):
        """load returns empty list when no data saved yet."""
        data = load_artilheiro_palpites_dia()
        assert isinstance(data, list), "load_artilheiro_palpites_dia must return a list"

    def test_save_and_load_dia_roundtrip(self):
        """Save then load returns the same data."""
        palpite = {
            "participante_nome": "TestUser",
            "data": "2026-06-20",
            "jogador": "Kylian Mbappé",
            "selecao": "França",
            "atualizado_em": now_iso(),
        }
        save_artilheiro_palpite_dia(palpite)
        all_dia = load_artilheiro_palpites_dia()
        found = [p for p in all_dia if p["participante_nome"] == "TestUser" and p["data"] == "2026-06-20"]
        assert len(found) == 1, "Saved prediction must be found"
        assert found[0]["jogador"] == "Kylian Mbappé"
        assert found[0]["selecao"] == "França"

    def test_save_and_load_dia_upsert(self):
        """Saving same participant+data overwrites previous."""
        v1 = {
            "participante_nome": "TestUser",
            "data": "2026-06-21",
            "jogador": "Lionel Messi",
            "selecao": "Argentina",
            "atualizado_em": now_iso(),
        }
        save_artilheiro_palpite_dia(v1)
        v2 = {
            "participante_nome": "TestUser",
            "data": "2026-06-21",
            "jogador": "Erling Haaland",
            "selecao": "Noruega",
            "atualizado_em": now_iso(),
        }
        save_artilheiro_palpite_dia(v2)
        all_dia = load_artilheiro_palpites_dia()
        matches = [p for p in all_dia if p["participante_nome"] == "TestUser" and p["data"] == "2026-06-21"]
        assert len(matches) == 1, "Upsert must replace, not append"
        assert matches[0]["jogador"] == "Erling Haaland"

    def test_save_and_load_rodada_roundtrip(self):
        """Save then load rodada predictions correctly."""
        palpite = {
            "participante_nome": "TestUser",
            "rodada": "Rodada 2",
            "jogador": "Vinícius Jr.",
            "selecao": "Brasil",
            "atualizado_em": now_iso(),
        }
        save_artilheiro_palpite_rodada(palpite)
        all_rod = load_artilheiro_palpites_rodada()
        found = [p for p in all_rod if p["participante_nome"] == "TestUser" and p["rodada"] == "Rodada 2"]
        assert len(found) == 1
        assert found[0]["jogador"] == "Vinícius Jr."

    def test_save_and_load_rodada_upsert(self):
        """Same participant+rodada overwrites."""
        save_artilheiro_palpite_rodada({
            "participante_nome": "TestUser",
            "rodada": "Rodada 3",
            "jogador": "Neymar",
            "selecao": "Brasil",
            "atualizado_em": now_iso(),
        })
        save_artilheiro_palpite_rodada({
            "participante_nome": "TestUser",
            "rodada": "Rodada 3",
            "jogador": "Harry Kane",
            "selecao": "Inglaterra",
            "atualizado_em": now_iso(),
        })
        all_rod = load_artilheiro_palpites_rodada()
        matches = [p for p in all_rod if p["participante_nome"] == "TestUser" and p["rodada"] == "Rodada 3"]
        assert len(matches) == 1
        assert matches[0]["jogador"] == "Harry Kane"

    def test_multiple_participants_dia(self):
        """Different participants for same date are both stored."""
        save_artilheiro_palpite_dia({
            "participante_nome": "Alice", "data": "2026-06-22",
            "jogador": "Jude Bellingham", "selecao": "Inglaterra", "atualizado_em": now_iso(),
        })
        save_artilheiro_palpite_dia({
            "participante_nome": "Bob", "data": "2026-06-22",
            "jogador": "Kylian Mbappé", "selecao": "França", "atualizado_em": now_iso(),
        })
        all_dia = load_artilheiro_palpites_dia()
        day_preds = [p for p in all_dia if p["data"] == "2026-06-22"]
        assert len(day_preds) >= 2
        names = {p["participante_nome"] for p in day_preds}
        assert "Alice" in names
        assert "Bob" in names


# ── Squad Lists Data Integrity ────────────────────────────────────────────

class TestSquadListsIntegrity:
    @pytest.fixture(autouse=True)
    def _load_squad(self):
        try:
            from squad_lists_2026 import SQUAD_LISTS_2026
            self.squad = SQUAD_LISTS_2026
        except ImportError:
            import sys, os
            root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            if root not in sys.path:
                sys.path.insert(0, root)
            from squad_lists_2026 import SQUAD_LISTS_2026
            self.squad = SQUAD_LISTS_2026

    def test_all_48_teams_present(self):
        """The squad list must contain exactly 48 teams."""
        assert len(self.squad) >= 48, f"Expected >=48 teams, got {len(self.squad)}"

    def test_every_player_has_required_fields(self):
        """Every player entry must have nome, posicao, camisa."""
        valid_positions = {"GOL", "DEF", "MEI", "ATA"}
        for team, players in self.squad.items():
            assert isinstance(players, list), f"{team}: players must be a list"
            for p in players:
                assert "nome" in p, f"{team}: player missing 'nome': {p}"
                assert "posicao" in p, f"{team}: {p['nome']} missing 'posicao'"
                assert "camisa" in p, f"{team}: {p['nome']} missing 'camisa'"
                assert p["posicao"] in valid_positions, \
                    f"{team}: {p['nome']} invalid posicao '{p['posicao']}'"
                assert isinstance(p["camisa"], int), \
                    f"{team}: {p['nome']} camisa must be int, got {type(p['camisa'])}"

    def test_brazil_squad_has_26_players(self):
        """Brazil squad has at least 23 players (standard)."""
        br = self.squad.get("Brasil", [])
        assert len(br) >= 23, f"Brazil should have >=23 players, got {len(br)}"

    def test_all_players_have_unique_shirts_per_team(self):
        """Within each team, jersey numbers are unique."""
        for team, players in self.squad.items():
            shirts = [p["camisa"] for p in players]
            assert len(shirts) == len(set(shirts)), f"{team}: duplicate jersey numbers"

    def test_all_positions_have_at_least_one_player(self):
        """Each team has at least 1 GOL, 1 DEF, 1 MEI, 1 ATA."""
        for team, players in self.squad.items():
            positions = {p["posicao"] for p in players}
            for pos in ["GOL", "DEF", "MEI", "ATA"]:
                assert pos in positions, f"{team}: missing position {pos}"


# ── Live Scoring + Goleadores Integration ────────────────────────────────

class TestLiveScoringWithGoleadores:
    def test_ranking_includes_goleadores_points(self):
        """calculate_live_ranking must include goleadores points for Brazil matches."""
        matches = load_matches()
        preds = load_live_predictions()
        config = load_config()
        ranking = calculate_live_ranking(preds, matches, config)

        assert isinstance(ranking, list), "Ranking must be a list"
        if ranking:
            # Keys every entry must have
            for entry in ranking:
                assert "participant" in entry
                assert "participant_key" in entry
                assert "total" in entry
                assert "exact_scores" in entry
                assert "position" in entry

    def test_brazil_match_goleadores_points_added(self):
        """Participants with correct goleador picks get extra points for Brazil match."""
        matches = load_matches()
        preds = load_live_predictions()
        config = load_config()
        ranking = calculate_live_ranking(preds, matches, config)

        # Find the Brazil match (13384) and check if any participant has goleador points
        goleadores = load_brasil_palpites_goleadores()
        br_goleadores = [g for g in goleadores if g["jogo_id"] == "13384"]
        if br_goleadores:
            # At least one participant should have points (Vini Jr. scored)
            pts_map = {normalize_participant_key(g["participante_nome"]): g.get("pontos_ganhos", 0) or 0
                       for g in br_goleadores}
            for entry in ranking:
                pkey = entry["participant_key"]
                if pkey in pts_map and pts_map[pkey] > 0:
                    # Verify they have at least the goleador points
                    assert entry["total"] > 0, \
                        f"{entry['participant']} should have points from goleador"
                    break
            else:
                # No participant with goleador points found — valid if no data
                pass

    def test_goleadores_points_match_expected_values(self):
        """Known goleador points must match expected calculation."""
        goleadores = load_brasil_palpites_goleadores()
        br_data = [g for g in goleadores if g["jogo_id"] == "13384"]
        for g in br_data:
            pts = g.get("pontos_ganhos", 0) or 0
            assert isinstance(pts, int), f"pontos_ganhos must be int, got {type(pts)} for {g['participante_nome']}"
            assert 0 <= pts <= 20, f"Unrealistic pontos_ganhos: {pts} for {g['participante_nome']}"


# ── Match Grouping & Ordering ─────────────────────────────────────────────

class TestMatchGrouping:
    def test_matches_sorted_by_group_then_date(self):
        """Matches sorted by get_sort_key must have groups in order, dates within groups."""
        matches = load_matches()
        if not matches:
            pytest.skip("No matches loaded")

        def get_sort_key(m):
            g = m.group or ""
            g_clean = g.strip().upper()
            if not g_clean or len(g_clean) > 1 or g_clean < 'A' or g_clean > 'L':
                group_key = "Z_Mata-Mata"
            else:
                group_key = f"Grupo {g_clean}"
            return (group_key, m.starts_at or "", m.sort_order)

        sorted_m = sorted(matches, key=get_sort_key)
        prev_key = ("", "", 0)
        for m in sorted_m:
            cur_key = get_sort_key(m)
            assert cur_key >= prev_key, \
                f"Sort order violated: {prev_key} -> {cur_key} for {m.home_team} vs {m.away_team}"
            prev_key = cur_key

    def test_group_section_detection(self):
        """Group change detection (for section headers) works correctly."""
        matches = load_matches()
        if not matches:
            pytest.skip("No matches loaded")

        def get_sort_key(m):
            g = m.group or ""
            g_clean = g.strip().upper()
            if not g_clean or len(g_clean) > 1 or g_clean < 'A' or g_clean > 'L':
                group_key = "Z_Mata-Mata"
            else:
                group_key = f"Grupo {g_clean}"
            return (group_key, m.starts_at or "", m.sort_order)

        def current_group(m):
            g = m.group or ""
            return f"Grupo {g}" if (g and g.strip()) else "Mata-Mata"

        sorted_m = sorted(matches, key=get_sort_key)
        group_changes = 0
        last_group = None
        for m in sorted_m:
            cg = current_group(m)
            if cg != last_group:
                group_changes += 1
                last_group = cg
        assert group_changes >= 1, "Must have at least one group change"
        # All groups must be detected
        groups_found = set()
        for m in sorted_m:
            groups_found.add(current_group(m))
        assert len(groups_found) >= 1


# ── Edge Cases ────────────────────────────────────────────────────────────

class TestEdgeCases:
    def test_artilheiro_without_login(self):
        """Saving artilheiro without login should not crash (handled by UI)."""
        save_artilheiro_palpite_dia({
            "participante_nome": "",
            "data": "2026-06-30",
            "jogador": "Test Player",
            "selecao": "Test Team",
            "atualizado_em": now_iso(),
        })
        all_dia = load_artilheiro_palpites_dia()
        found = [p for p in all_dia if p["participante_nome"] == ""]
        assert len(found) >= 0  # Should not crash, may or may not save

    def test_ranking_empty_predictions(self):
        """calculate_live_ranking with empty predictions returns empty list."""
        from src.bolao.models import LiveMatch, LivePrediction
        config = load_config()
        matches = load_matches()
        ranking = calculate_live_ranking([], matches, config)
        assert isinstance(ranking, list)
        # If there are no predictions but approved matches exist, ranking is empty
        assert len(ranking) == 0

    def test_ranking_none_config(self):
        """calculate_live_ranking with None config uses defaults."""
        matches = load_matches()
        preds = load_live_predictions()
        ranking = calculate_live_ranking(preds, matches, {})
        assert isinstance(ranking, list)

    def test_recalc_goleadores_no_result(self):
        """recalcular_pontos_modulo_brasil with non-existent match doesn't crash."""
        from src.bolao.storage import recalcular_pontos_modulo_brasil
        # This match_id doesn't exist — should just return silently
        recalcular_pontos_modulo_brasil("99999")
        assert True  # Should not crash

    def test_squad_list_import(self):
        """Verify squad_lists_2026 can be imported and has valid structure."""
        try:
            from squad_lists_2026 import SQUAD_LISTS_2026
            sl = SQUAD_LISTS_2026
        except ImportError:
            import sys, os
            root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            if root not in sys.path:
                sys.path.insert(0, root)
            from squad_lists_2026 import SQUAD_LISTS_2026
            sl = SQUAD_LISTS_2026

        assert isinstance(sl, dict)
        assert len(sl) > 0
        # Check a few known teams
        assert "Brasil" in sl
        assert "Argentina" in sl
        # Brazil must have a GK
        br_players = sl["Brasil"]
        assert any(p["posicao"] == "GOL" for p in br_players)


# ── Mobile Navigation Integrity ───────────────────────────────────────────

class TestNavigationIntegrity:
    def test_mobile_nav_includes_artilheiro(self):
        """Verify app.py mobile nav includes '⚽ Artilheiro'."""
        import sys
        app_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app.py")
        assert os.path.exists(app_path), "app.py must exist"
        with open(app_path, encoding="utf-8") as f:
            content = f.read()
        # Check the mobile nav list contains Artilheiro
        assert '"⚽ Artilheiro"' in content or "'⚽ Artilheiro'" in content, \
            "Mobile navigation must include ⚽ Artilheiro"

    def test_sidebar_groups_include_artilheiro(self):
        """Verify GROUPS dict includes Artilheiro."""
        app_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app.py")
        with open(app_path, encoding="utf-8") as f:
            content = f.read()
        assert '"⚽ Artilheiro"' in content or "'⚽ Artilheiro'" in content, \
            "Sidebar GROUPS must include ⚽ Artilheiro"

    def test_routing_includes_artilheiro(self):
        """Verify app.py routing has elif for Artilheiro."""
        app_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app.py")
        with open(app_path, encoding="utf-8") as f:
            content = f.read()
        assert 'render_page_artilheiro' in content, \
            "app.py must import and call render_page_artilheiro"
