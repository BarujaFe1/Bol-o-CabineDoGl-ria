from __future__ import annotations

import functools
import re
from typing import Any

from .worldcup_2026_data import TEAMS, GROUPS_TEAMS, GROUP_MATCHES, BRACKET_SLOTS
from .simulator_models import GroupStanding, GroupMatch

# TERCEIRO_SLOTS config for the greedy third-place allocation
TERCEIRO_SLOTS = [
    {"matchId": 90002, "vs1st": "E", "eligible": ["A", "B", "C", "D", "F"]},
    {"matchId": 90005, "vs1st": "I", "eligible": ["C", "D", "F", "G", "H"]},
    {"matchId": 90007, "vs1st": "A", "eligible": ["C", "E", "F", "H", "I"]},
    {"matchId": 90008, "vs1st": "D", "eligible": ["B", "E", "F", "I", "J"]},
    {"matchId": 90009, "vs1st": "G", "eligible": ["A", "E", "H", "I", "J"]},
    {"matchId": 90010, "vs1st": "L", "eligible": ["E", "H", "I", "J", "K"]},
    {"matchId": 90013, "vs1st": "B", "eligible": ["E", "F", "G", "I", "J"]},
    {"matchId": 90016, "vs1st": "K", "eligible": ["D", "E", "J", "I", "L"]}
]

# Map slot index to the match ID that contains it for 3rd place lookup
SLOT_TO_MATCH_ID = {
    32: 90002,
    34: 90005,
    44: 90008,
    46: 90009,
    52: 90007,
    54: 90010,
    60: 90013,
    62: 90016
}

def calculate_group_standings(group_letter: str, matches: list[GroupMatch]) -> list[GroupStanding]:
    """
    Calculates standings for a group and resolves ties using FIFA WC 2026 rules:
    1. Points
    2. Head-to-head (mini-table if 3+ tied, match result if 2 tied)
    3. Goal difference
    4. Goals scored
    5. Fallback deterministic: visual/original order in group
    """
    team_ids = GROUPS_TEAMS[group_letter]
    stats = {
        tid: GroupStanding(
            team_id=tid,
            name=TEAMS[tid]["name"],
            abbr=TEAMS[tid]["abbr"]
        ) for tid in team_ids
    }

    # Filter matches belonging to this group
    group_matches = [m for m in matches if m.group == group_letter]

    # Calculate overall stats
    for m in group_matches:
        if m.home_score is None or m.away_score is None:
            continue
        h_id, a_id = m.home_id, m.away_id
        h_g, a_g = m.home_score, m.away_score

        stats[h_id].played += 1
        stats[a_id].played += 1
        stats[h_id].gf += h_g
        stats[h_id].ga += a_g
        stats[a_id].gf += a_g
        stats[a_id].ga += h_g

        if h_g > a_g:
            stats[h_id].points += 3
            stats[h_id].wins += 1
            stats[a_id].losses += 1
        elif h_g < a_g:
            stats[a_id].points += 3
            stats[a_id].wins += 1
            stats[h_id].losses += 1
        else:
            stats[h_id].points += 1
            stats[a_id].points += 1
            stats[h_id].draws += 1
            stats[a_id].draws += 1

    for tid in team_ids:
        st = stats[tid]
        st.gd = st.gf - st.ga
        if st.played > 0:
            st.percent = (st.points / (st.played * 3)) * 100
        else:
            st.percent = 0.0

    # Helper function to resolve subgroup of tied teams
    def resolve_subgroup(sub_teams: list[str]) -> list[str]:
        if len(sub_teams) <= 1:
            return sub_teams

        # 2-way tie: head-to-head match
        if len(sub_teams) == 2:
            t1, t2 = sub_teams[0], sub_teams[1]
            h2h_match = None
            for m in group_matches:
                if (m.home_id == t1 and m.away_id == t2) or (m.home_id == t2 and m.away_id == t1):
                    h2h_match = m
                    break
            if h2h_match and h2h_match.home_score is not None and h2h_match.away_score is not None:
                h_id, a_id = h2h_match.home_id, h2h_match.away_id
                h_g, a_g = h2h_match.home_score, h2h_match.away_score
                if h_g > a_g:
                    winner, loser = h_id, a_id
                elif h_g < a_g:
                    winner, loser = a_id, h_id
                else:
                    winner, loser = None, None
                
                if winner:
                    return [winner, loser]

            # If draw or match not simulated, resolve by overall GD, GF, visual order
            return resolve_by_overall(sub_teams)

        # 3-way tie: mini-table points/GD/GF
        if len(sub_teams) == 3:
            sub_set = set(sub_teams)
            mini = {tid: {"pts": 0, "gd": 0, "gf": 0, "ga": 0} for tid in sub_teams}
            for m in group_matches:
                if m.home_id in sub_set and m.away_id in sub_set:
                    h_id, a_id = m.home_id, m.away_id
                    h_g, a_g = m.home_score, m.away_score
                    if h_g is not None and a_g is not None:
                        mini[h_id]["gf"] += h_g
                        mini[h_id]["ga"] += a_g
                        mini[a_id]["gf"] += a_g
                        mini[a_id]["ga"] += h_g
                        if h_g > a_g:
                            mini[h_id]["pts"] += 3
                        elif h_g < a_g:
                            mini[a_id]["pts"] += 3
                        else:
                            mini[h_id]["pts"] += 1
                            mini[a_id]["pts"] += 1
            for tid in sub_teams:
                mini[tid]["gd"] = mini[tid]["gf"] - mini[tid]["ga"]

            def compare_3way(t_a, t_b):
                # Points in head-to-head
                if mini[t_a]["pts"] != mini[t_b]["pts"]:
                    return mini[t_a]["pts"] - mini[t_b]["pts"]
                # Goal Difference in head-to-head
                if mini[t_a]["gd"] != mini[t_b]["gd"]:
                    return mini[t_a]["gd"] - mini[t_b]["gd"]
                # Goals Scored in head-to-head
                if mini[t_a]["gf"] != mini[t_b]["gf"]:
                    return mini[t_a]["gf"] - mini[t_b]["gf"]
                # Overall Goal Difference
                if stats[t_a].gd != stats[t_b].gd:
                    return stats[t_a].gd - stats[t_b].gd
                # Overall Goals Scored
                if stats[t_a].gf != stats[t_b].gf:
                    return stats[t_a].gf - stats[t_b].gf
                # Fallback: Visual order (original index in group list, lower index is better, so t_b index - t_a index)
                return team_ids.index(t_b) - team_ids.index(t_a)

            return sorted(sub_teams, key=functools.cmp_to_key(compare_3way), reverse=True)

        # 4-way tie: mini-table is overall table, so directly resolve by overall
        return resolve_by_overall(sub_teams)

    def resolve_by_overall(sub_teams: list[str]) -> list[str]:
        def compare_overall(t_a, t_b):
            if stats[t_a].gd != stats[t_b].gd:
                return stats[t_a].gd - stats[t_b].gd
            if stats[t_a].gf != stats[t_b].gf:
                return stats[t_a].gf - stats[t_b].gf
            return team_ids.index(t_b) - team_ids.index(t_a)

        return sorted(sub_teams, key=functools.cmp_to_key(compare_overall), reverse=True)

    # Main sorting flow
    by_points = {}
    for tid in team_ids:
        pts = stats[tid].points
        by_points.setdefault(pts, []).append(tid)

    sorted_teams = []
    for pts in sorted(by_points.keys(), reverse=True):
        tied = by_points[pts]
        resolved = resolve_subgroup(tied)
        sorted_teams.extend(resolved)

    # Set positions (1-indexed)
    resolved_standings = []
    for idx, tid in enumerate(sorted_teams, start=1):
        st = stats[tid]
        st.position = idx
        resolved_standings.append(st)

    return resolved_standings


def get_best_third_placed_teams(all_standings: dict[str, list[GroupStanding]]) -> list[GroupStanding]:
    """
    Identifies and ranks the 3rd-placed teams from all 12 groups.
    Returns them sorted (best to worst) based on Points, GD, Goals Scored, and Group Letter (A-L).
    """
    thirds = []
    for group_letter, standings in all_standings.items():
        if len(standings) >= 3:
            thirds.append(standings[2])  # 3rd place (index 2)
        
    def compare_thirds(t_a: GroupStanding, t_b: GroupStanding):
        if t_a.points != t_b.points:
            return t_a.points - t_b.points
        if t_a.gd != t_b.gd:
            return t_a.gd - t_b.gd
        if t_a.gf != t_b.gf:
            return t_a.gf - t_b.gf
        
        # Fallback: group letter (lower letter is better, so 'B' index > 'A' index, return reverse)
        group_a = next(g for g, t_ids in GROUPS_TEAMS.items() if t_a.team_id in t_ids)
        group_b = next(g for g, t_ids in GROUPS_TEAMS.items() if t_b.team_id in t_ids)
        return ord(group_b) - ord(group_a)

    return sorted(thirds, key=functools.cmp_to_key(compare_thirds), reverse=True)


def assign_3rd_place_slots(best_thirds_groups: list[str]) -> dict[int, str]:
    """
    Implements the greedy matching algorithm for third-place team allocation.
    Returns a mapping of matchId (int) -> group letter (str) for the 8 slots.
    """
    e = set(best_thirds_groups)
    
    # Calculate candidates lists for each slot
    slots_with_candidates = []
    for slot in TERCEIRO_SLOTS:
        candidates = [g for g in slot["eligible"] if g in e]
        slots_with_candidates.append({
            "matchId": slot["matchId"],
            "candidates": candidates
        })
        
    # Sort slots by number of eligible candidates ascending
    slots_with_candidates.sort(key=lambda x: len(x["candidates"]))
    
    assignment = {}
    assigned_groups = set()
    
    # First pass: assign greedy
    for slot in slots_with_candidates:
        available = [g for g in slot["candidates"] if g not in assigned_groups]
        if available:
            chosen = available[0]
            assignment[slot["matchId"]] = chosen
            assigned_groups.add(chosen)
            
    # Second pass: assign remaining unassigned groups to empty slots in order
    unassigned_groups = [g for g in best_thirds_groups if g not in assigned_groups]
    for slot in TERCEIRO_SLOTS:
        m_id = slot["matchId"]
        if m_id not in assignment and unassigned_groups:
            chosen = unassigned_groups.pop(0)
            assignment[m_id] = chosen
            assigned_groups.add(chosen)
            
    return assignment


def build_initial_bracket_slots(
    groups_standings: dict[str, list[GroupStanding]],
    best_thirds_groups: list[str]
) -> dict[int, str]:
    """
    Populates the 32 slots of the Round of 32 (indices 31 to 62).
    Returns a dict mapping slot_id (int) -> team_id (str) or None.
    """
    # 1. Map third place groups
    third_place_assignment = assign_3rd_place_slots(best_thirds_groups)
    
    slots = {}
    for slot_id in range(63):
        slots[slot_id] = None

    # Populate slots 31 to 62 from the static config
    for slot_id in range(31, 63):
        config = BRACKET_SLOTS[slot_id]
        placeholder = config["label"]
        
        # Check if placeholder is a group rank like "1ºE" or "2ºA"
        match_group_rank = re.match(r'([12]º)([A-L])', placeholder)
        if match_group_rank:
            rank = 1 if match_group_rank.group(1) == "1º" else 2
            g_letter = match_group_rank.group(2)
            
            # Get the team at that position in the group standings
            standings = groups_standings.get(g_letter, [])
            if len(standings) >= rank:
                slots[slot_id] = standings[rank-1].team_id
        
        # Check if placeholder is "3ºs"
        elif placeholder == "3ºs":
            match_id = SLOT_TO_MATCH_ID.get(slot_id)
            if match_id:
                assigned_group = third_place_assignment.get(match_id)
                if assigned_group:
                    standings = groups_standings.get(assigned_group, [])
                    if len(standings) >= 3:
                        slots[slot_id] = standings[2].team_id
                        
    return slots


def propagate_winner(slots: dict[int, str | None], slot_id: int, winner_team_id: str | None) -> None:
    """
    Propagates the winner of slot_id to its parent slot.
    Clears parents if the winner is None or changes.
    """
    if slot_id <= 0:
        return
        
    parent_id = (slot_id - 1) >> 1
    old_parent_winner = slots[parent_id]
    
    # If the winner didn't change, no propagation needed
    if old_parent_winner == winner_team_id:
        return
        
    slots[parent_id] = winner_team_id
    
    # If there was an old winner, recursively clear that team from all grandparent nodes
    if old_parent_winner is not None:
        clear_ancestor_team(slots, parent_id, old_parent_winner)

def clear_ancestor_team(slots: dict[int, str | None], slot_id: int, team_id: str) -> None:
    if slot_id <= 0:
        return
    parent_id = (slot_id - 1) >> 1
    if slots[parent_id] == team_id:
        slots[parent_id] = None
        clear_ancestor_team(slots, parent_id, team_id)


# Knockout bracket slot mappings (home_slot, visitor_slot, winner_slot)
MAP_FASE_32 = [
    (31, 32, 15), (33, 34, 16), (35, 36, 17), (37, 38, 18),
    (39, 40, 19), (41, 42, 20), (43, 44, 21), (45, 46, 22),
    (47, 48, 23), (49, 50, 24), (51, 52, 25), (53, 54, 26),
    (55, 56, 27), (57, 58, 28), (59, 60, 29), (61, 62, 30)
]

MAP_OITAVAS = [
    (15, 16, 7), (17, 18, 8), (19, 20, 9), (21, 22, 10),
    (23, 24, 11), (25, 26, 12), (27, 28, 13), (29, 30, 14)
]

MAP_QUARTAS = [
    (7, 8, 3), (9, 10, 4), (11, 12, 5), (14, 13, 6)
]

MAP_SEMIFINAIS = [
    (3, 4, 1), (5, 6, 2)
]

MAP_FINAL = [
    (1, 2, 0)
]


def name_to_id(name: str | None) -> str | None:
    """Finds the team ID associated with a team name (or abbreviation) under norm_team."""
    if not name:
        return None
    from .utils import norm_team
    norm = norm_team(name)
    for tid, info in TEAMS.items():
        if norm_team(info["name"]) == norm or norm_team(info["abbr"]) == norm:
            return tid
    return None


def serialize_slots_to_prediction(slots: dict[int, str | None], prediction: Prediction) -> None:
    """Serializes the bracket slots dict into the prediction's champion and knockout match fields."""
    from .models import Match

    def tname(tid: str | None) -> str | None:
        if not tid:
            return None
        return TEAMS.get(tid, {}).get("name", tid)

    prediction.champion = tname(slots[0])
    
    prediction.knockout["fase_32"] = [
        Match(a=tname(slots[h]), b=tname(slots[v]), winner=tname(slots[w]))
        for h, v, w in MAP_FASE_32
    ]
    prediction.knockout["oitavas"] = [
        Match(a=tname(slots[h]), b=tname(slots[v]), winner=tname(slots[w]))
        for h, v, w in MAP_OITAVAS
    ]
    prediction.knockout["quartas"] = [
        Match(a=tname(slots[h]), b=tname(slots[v]), winner=tname(slots[w]))
        for h, v, w in MAP_QUARTAS
    ]
    prediction.knockout["semifinais"] = [
        Match(a=tname(slots[h]), b=tname(slots[v]), winner=tname(slots[w]))
        for h, v, w in MAP_SEMIFINAIS
    ]
    prediction.knockout["final"] = [
        Match(a=tname(slots[h]), b=tname(slots[v]), winner=tname(slots[w]))
        for h, v, w in MAP_FINAL
    ]


def deserialize_prediction_to_slots(
    prediction: Prediction,
    groups_standings: dict[str, list[GroupStanding]],
    best_thirds_groups: list[str]
) -> dict[int, str | None]:
    """Deserializes a prediction's champion and knockout match fields back into a bracket slots dict."""
    # 1. Initialize slot positions from groups
    slots = build_initial_bracket_slots(groups_standings, best_thirds_groups)
    
    # 2. Fill winners for each round based on the match winner names
    # Fase de 32
    ko_fase_32 = prediction.knockout.get("fase_32", [])
    for idx, (h, v, w) in enumerate(MAP_FASE_32):
        if idx < len(ko_fase_32):
            slots[w] = name_to_id(ko_fase_32[idx].winner)

    # Oitavas
    ko_oitavas = prediction.knockout.get("oitavas", [])
    for idx, (h, v, w) in enumerate(MAP_OITAVAS):
        if idx < len(ko_oitavas):
            slots[w] = name_to_id(ko_oitavas[idx].winner)

    # Quartas
    ko_quartas = prediction.knockout.get("quartas", [])
    for idx, (h, v, w) in enumerate(MAP_QUARTAS):
        if idx < len(ko_quartas):
            slots[w] = name_to_id(ko_quartas[idx].winner)

    # Semifinais
    ko_semis = prediction.knockout.get("semifinais", [])
    for idx, (h, v, w) in enumerate(MAP_SEMIFINAIS):
        if idx < len(ko_semis):
            slots[w] = name_to_id(ko_semis[idx].winner)

    # Final & Champion
    ko_final = prediction.knockout.get("final", [])
    if ko_final:
        slots[0] = name_to_id(ko_final[0].winner)
    elif prediction.champion:
        slots[0] = name_to_id(prediction.champion)

    return slots

