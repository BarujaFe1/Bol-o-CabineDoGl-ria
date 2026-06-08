import pytest
from src.bolao.models import Prediction, Match
from src.bolao.simulator_models import GroupMatch, GroupStanding
from src.bolao.worldcup_2026_data import TEAMS, GROUPS_TEAMS, GROUP_MATCHES
from src.bolao.simulator_engine import (
    calculate_group_standings,
    get_best_third_placed_teams,
    assign_3rd_place_slots,
    build_initial_bracket_slots,
    propagate_winner,
    serialize_slots_to_prediction,
    deserialize_prediction_to_slots,
)
from src.bolao.scoring import ScoreConfig, score_prediction, rank_predictions
from src.bolao.constants import DEFAULT_V2_RULES


def test_worldcup_data_integrity():
    """Verify that static World Cup data contains the correct number of entities."""
    assert len(TEAMS) == 48
    assert len(GROUPS_TEAMS) == 12
    assert len(GROUP_MATCHES) == 72
    for g, teams in GROUPS_TEAMS.items():
        assert len(teams) == 4
        for tid in teams:
            assert tid in TEAMS


def test_calculate_group_standings_simple():
    """Verify standard standings calculation without complex ties."""
    # Group A: Mexico (228), South Africa (232), South Korea (546), Czech Rep (832)
    # Let's create matches for Group A
    matches = [
        GroupMatch(id="1", group="A", round="1", home_id="228", away_id="232", home_score=2, away_score=1),
        GroupMatch(id="2", group="A", round="1", home_id="546", away_id="832", home_score=1, away_score=1),
        GroupMatch(id="3", group="A", round="1", home_id="228", away_id="546", home_score=3, away_score=0),
        GroupMatch(id="4", group="A", round="1", home_id="232", away_id="832", home_score=2, away_score=2),
        GroupMatch(id="5", group="A", round="1", home_id="832", away_id="228", home_score=0, away_score=1),
        GroupMatch(id="6", group="A", round="1", home_id="232", away_id="546", home_score=0, away_score=2),
    ]

    standings = calculate_group_standings("A", matches)
    assert len(standings) == 4

    # Mexico (228) won 3 games -> 9 pts, 6 GF, 1 GA, +5 GD
    mex = next(s for s in standings if s.team_id == "228")
    assert mex.points == 9
    assert mex.played == 3
    assert mex.wins == 3
    assert mex.gf == 6
    assert mex.ga == 1
    assert mex.gd == 5
    assert mex.position == 1

    # South Korea (546): draw (1), loss (0), win (2) -> 4 pts, 3 GF, 4 GA, -1 GD
    kor = next(s for s in standings if s.team_id == "546")
    assert kor.points == 4
    assert kor.wins == 1
    assert kor.draws == 1
    assert kor.losses == 1
    assert kor.gd == -1
    assert kor.position == 2


def test_calculate_group_standings_2way_tie_h2h():
    """Verify 2-way tie resolved by Head-to-Head."""
    # Group A teams: 228 and 232 are tied on points. 228 won the H2H match.
    matches = [
        GroupMatch(id="1", group="A", round="1", home_id="228", away_id="232", home_score=1, away_score=0), # H2H
        GroupMatch(id="2", group="A", round="1", home_id="546", away_id="832", home_score=0, away_score=0),
        
        GroupMatch(id="3", group="A", round="1", home_id="228", away_id="546", home_score=1, away_score=2),
        GroupMatch(id="4", group="A", round="1", home_id="232", away_id="832", home_score=2, away_score=1),
        
        GroupMatch(id="5", group="A", round="1", home_id="832", away_id="228", home_score=0, away_score=1),
        GroupMatch(id="6", group="A", round="1", home_id="232", away_id="546", home_score=2, away_score=1),
    ]
    # Points:
    # 228: 3 + 0 + 3 = 6 pts, GD: +1 (3-2)
    # 232: 0 + 3 + 3 = 6 pts, GD: +1 (4-3)
    # Note overall GD is equal (+1). South Africa (232) scored more goals (4 vs 3),
    # but Mexico (228) won Head-to-Head, so Mexico must rank higher.

    standings = calculate_group_standings("A", matches)
    assert standings[0].team_id == "228"
    assert standings[1].team_id == "232"


def test_calculate_group_standings_2way_tie_gd():
    """Verify 2-way tie resolved by overall GD when H2H is a draw."""
    matches = [
        GroupMatch(id="1", group="A", round="1", home_id="228", away_id="232", home_score=1, away_score=1), # H2H Draw
        GroupMatch(id="2", group="A", round="1", home_id="546", away_id="832", home_score=0, away_score=0),
        
        GroupMatch(id="3", group="A", round="1", home_id="228", away_id="546", home_score=3, away_score=0),
        GroupMatch(id="4", group="A", round="1", home_id="232", away_id="832", home_score=1, away_score=0),
        
        GroupMatch(id="5", group="A", round="1", home_id="832", away_id="228", home_score=0, away_score=0),
        GroupMatch(id="6", group="A", round="1", home_id="232", away_id="546", home_score=0, away_score=0),
    ]
    # Points:
    # 228: 1 (draw) + 3 (win) + 1 (draw) = 5 pts, GD: +3 (4-1)
    # 232: 1 (draw) + 3 (win) + 1 (draw) = 5 pts, GD: +1 (2-1)
    # Head-to-Head is a draw. Overall GD resolves it: Mexico (228) has +3, South Africa (232) has +1.

    standings = calculate_group_standings("A", matches)
    assert standings[0].team_id == "228"
    assert standings[1].team_id == "232"


def test_calculate_group_standings_3way_tie():
    """Verify 3-way tie resolved by mini-table points."""
    # Let's create a scenario where teams T1, T2, T3 are tied on 6 points overall.
    # T1 beats T2, T2 beats T3, T3 beats T1.
    # We will use A, B, C from Group A: 228 (Mexico), 232 (South Africa), 546 (South Korea).
    # Czech Rep (832) loses all games (0 pts).
    matches = [
        # H2H between the three
        GroupMatch(id="1", group="A", round="1", home_id="228", away_id="232", home_score=2, away_score=0), # Mexico beat SA
        GroupMatch(id="2", group="A", round="1", home_id="232", away_id="546", home_score=3, away_score=0), # SA beat SK
        GroupMatch(id="3", group="A", round="1", home_id="546", away_id="228", home_score=1, away_score=0), # SK beat Mexico
        
        # Matches against Czech Rep (832)
        GroupMatch(id="4", group="A", round="1", home_id="228", away_id="832", home_score=1, away_score=0), # Mexico beat Czech
        GroupMatch(id="5", group="A", round="1", home_id="232", away_id="832", home_score=1, away_score=0), # SA beat Czech
        GroupMatch(id="6", group="A", round="1", home_id="546", away_id="832", home_score=1, away_score=0), # SK beat Czech
    ]
    # Points overall:
    # 228: 3 (SA) + 0 (SK) + 3 (Czech) = 6 pts. Overall GD: +2 (3-1), GF: 3
    # 232: 0 (Mex) + 3 (SK) + 3 (Czech) = 6 pts. Overall GD: +2 (4-2), GF: 4
    # 546: 3 (Mex) + 0 (SA) + 3 (Czech) = 6 pts. Overall GD: -1 (2-3), GF: 2
    # In the mini-table between 228, 232, 546:
    # 228: 3 pts, GD: +1 (2-1), GF: 2
    # 232: 3 pts, GD: +1 (3-2), GF: 3
    # 546: 3 pts, GD: -2 (1-3), GF: 1
    # Note mini-table points are all 3.
    # Mini-table GD: 228 has +1, 232 has +1, 546 has -2 (so 546 is 3rd of the tie, i.e., 3rd overall).
    # To resolve between 228 and 232:
    # Mini-table GF: 232 has 3 goals, 228 has 2 goals. So South Africa (232) is 1st, Mexico (228) is 2nd.

    standings = calculate_group_standings("A", matches)
    assert standings[0].team_id == "232" # South Africa
    assert standings[1].team_id == "228" # Mexico
    assert standings[2].team_id == "546" # South Korea
    assert standings[3].team_id == "832" # Czech Rep


def test_get_best_third_placed_teams():
    """Verify sorting and ranking of third-placed teams across 12 groups."""
    # Let's create dummy standings for groups A-L
    # Standing position 3 (index 2) will have different stats
    all_standings = {}
    
    # We will populate index 2 of each group with a team of different points/GD
    # Best thirds must be: Group B (9 pts), Group C (7 pts), Group D (6 pts), Group E (5 pts, +2 GD), Group F (5 pts, +1 GD), Group G (5 pts, +0 GD), Group H (4 pts), Group I (3 pts)
    # The others (J, K, L) will have lower points or ord fallback
    group_letters = list("ABCDEFGHIJKL")
    
    # Setup some dummy team IDs
    for idx, g in enumerate(group_letters):
        t1 = GroupStanding(team_id=f"t_{g}_1", name="Team 1", abbr="T1", position=1, points=9)
        t2 = GroupStanding(team_id=f"t_{g}_2", name="Team 2", abbr="T2", position=2, points=6)
        
        # 3rd placed teams have varying stats
        pts = 0
        gd = 0
        gf = 0
        if g == "B":
            pts, gd, gf = 9, 3, 5
        elif g == "C":
            pts, gd, gf = 7, 2, 4
        elif g == "D":
            pts, gd, gf = 6, 1, 3
        elif g == "E":
            pts, gd, gf = 5, 2, 4
        elif g == "F":
            pts, gd, gf = 5, 1, 3
        elif g == "G":
            pts, gd, gf = 5, 1, 2  # Worse gf than F
        elif g == "H":
            pts, gd, gf = 4, 0, 2
        elif g == "I":
            pts, gd, gf = 3, -1, 1
        elif g == "J":
            pts, gd, gf = 2, -2, 0
        elif g == "K":
            pts, gd, gf = 1, -3, 0
        elif g == "L":
            pts, gd, gf = 0, -4, 0
        else: # Group A
            pts, gd, gf = 4, 0, 1 # Worse gf than H
            
        t3 = GroupStanding(team_id=f"t_{g}_3", name=f"Team {g} 3", abbr=f"T{g}3", position=3, points=pts)
        t3.gd = gd
        t3.gf = gf
        t4 = GroupStanding(team_id=f"t_{g}_4", name="Team 4", abbr="T4", position=4, points=0)
        
        all_standings[g] = [t1, t2, t3, t4]

    best_thirds = get_best_third_placed_teams(all_standings)
    assert len(best_thirds) == 12
    
    # Check top 3 order: B (9), C (7), D (6)
    assert best_thirds[0].team_id == "t_B_3"
    assert best_thirds[1].team_id == "t_C_3"
    assert best_thirds[2].team_id == "t_D_3"
    
    # Check E (5, +2), F (5, +1, GF 3), G (5, +1, GF 2)
    assert best_thirds[3].team_id == "t_E_3"
    assert best_thirds[4].team_id == "t_F_3"
    assert best_thirds[5].team_id == "t_G_3"
    
    # Check H (4, GF 2), A (4, GF 1)
    assert best_thirds[6].team_id == "t_H_3"
    assert best_thirds[7].team_id == "t_A_3"


def test_assign_3rd_place_slots():
    """Verify greedy 3rd place slot assignment from GloboEsporte minified code."""
    # Let's say the 8 qualified 3rd place groups are A, B, C, D, E, F, G, H
    best_thirds_groups = ["A", "B", "C", "D", "E", "F", "G", "H"]
    mapping = assign_3rd_place_slots(best_thirds_groups)
    
    # The output must contain mapping for all 8 matches
    assert len(mapping) == 8
    
    # Match IDs: 90002, 90005, 90007, 90008, 90009, 90010, 90013, 90016
    expected_matches = {90002, 90005, 90007, 90008, 90009, 90010, 90013, 90016}
    assert set(mapping.keys()) == expected_matches
    
    # Check that all mapped groups are unique and in the best_thirds_groups
    mapped_groups = set(mapping.values())
    assert mapped_groups == set(best_thirds_groups)


def test_propagate_winner_and_bracket():
    """Verify interactive bracket propagation and clearing of previous path."""
    # Initialize blank slots dict (0 to 62)
    slots = {i: None for i in range(63)}
    
    # Set Round of 32 teams for game index 31 and 32
    slots[31] = "228" # Mexico
    slots[32] = "232" # South Africa
    
    # Propagate Mexico (228) from slot 31 as winner
    propagate_winner(slots, 31, "228")
    
    # Parent of 31 and 32 is (31-1)>>1 = 15. So slot 15 should contain Mexico (228)
    assert slots[15] == "228"
    
    # Propagate Mexico (228) further to parent of 15 (which is 7)
    propagate_winner(slots, 15, "228")
    assert slots[7] == "228"
    
    # Propagate Mexico (228) to parent of 7 (which is 3)
    propagate_winner(slots, 7, "228")
    assert slots[3] == "228"
    
    # Now, let's change winner of Round of 32 from Mexico (228) to South Africa (232)
    propagate_winner(slots, 31, "232")
    
    # Verify that parent (15) was updated to South Africa (232)
    assert slots[15] == "232"
    # Verify that higher nodes (7, 3) were cleared because their old winner (228) was broken
    assert slots[7] is None
    assert slots[3] is None


def test_serialize_deserialize():
    """Verify serialization/deserialization compatibility between flat slots and Prediction object."""
    # Set up dummy groups standings and best thirds
    dummy_standings = {g: [GroupStanding(team_id=GROUPS_TEAMS[g][i], name=TEAMS[GROUPS_TEAMS[g][i]]["name"], abbr=TEAMS[GROUPS_TEAMS[g][i]]["abbr"], position=i+1) for i in range(4)] for g in GROUPS_TEAMS}
    best_thirds_groups = ["A", "B", "C", "D", "E", "F", "G", "H"]
    
    # Build initial slots
    slots = build_initial_bracket_slots(dummy_standings, best_thirds_groups)
    
    # Set some winners
    # Parent of 31/32 is 15. Assign winner of slot 31/32 to slot 15.
    t_31 = slots[31]
    slots[15] = t_31
    slots[0] = t_31  # Champion
    
    # Serialize to Prediction
    pred = Prediction(participant="Cesar")
    serialize_slots_to_prediction(slots, pred)
    
    assert pred.champion == TEAMS[t_31]["name"]
    assert pred.knockout["fase_32"][0].winner == TEAMS[t_31]["name"]
    
    # Deserialize back
    restored_slots = deserialize_prediction_to_slots(pred, dummy_standings, best_thirds_groups)
    assert restored_slots[15] == t_31
    assert restored_slots[0] == t_31


def test_scoring_v2_exact_and_others():
    """Verify that scoring V2 handles exact scores, result+GD, result, team goals, and KO advancement."""
    # Create official and prediction objects
    official = Prediction(participant="Official")
    pred = Prediction(participant="Predictor")
    
    # Group match scoring verification
    # Setup official scores in meta
    official.meta["group_matches"] = {
        "m1": [2, 1], # exact 2x1
        "m2": [3, 1], # GD result 3x1 (pred 2x0)
        "m3": [1, 0], # result only 1x0 (pred 3x1)
        "m4": [2, 2], # team goals 2x2 (pred 2x0)
        "m5": [0, 1], # complete miss 0x1 (pred 2x0)
    }
    
    # Setup predicted scores in meta
    pred.meta["group_matches"] = {
        "m1": [2, 1], # Exact hit (5pts)
        "m2": [2, 0], # Same result (Win) and GD (+2) -> (3pts)
        "m3": [3, 1], # Same result (Win), GD is +2 instead of +1 -> (2pts)
        "m4": [2, 0], # Missed result, but hit home goals (2) -> (1pt)
        "m5": [2, 0], # Missed completely -> (0pts)
    }
    
    # Let's override GROUP_MATCHES in a test-safe way, or just write mock data.
    # Note: scoring.py:score_prediction reads GROUP_MATCHES from worldcup_2026_data.
    # Let's patch GROUP_MATCHES inside the test or use the actual matches by mapping their IDs.
    import src.bolao.scoring as scoring_mod
    original_group_matches = scoring_mod.GROUP_MATCHES
    
    # Temporary mock matches
    scoring_mod.GROUP_MATCHES = [
        {"id": "m1", "group": "A", "home_id": "228", "away_id": "232"},
        {"id": "m2", "group": "A", "home_id": "228", "away_id": "232"},
        {"id": "m3", "group": "A", "home_id": "228", "away_id": "232"},
        {"id": "m4", "group": "A", "home_id": "228", "away_id": "232"},
        {"id": "m5", "group": "A", "home_id": "228", "away_id": "232"},
    ]
    
    try:
        config = ScoreConfig(mode="v2", v2_rules=DEFAULT_V2_RULES)
        sb = score_prediction(pred, official, config)
        
        # Verify group points: 5 + 3 + 2 + 1 + 0 = 11 pts
        assert sb.group_points == 11
        assert sb.exact_scores == 1
        assert sb.group_hits == 3 # m1, m2, m3 are counted as hits in ScoreBreakdown
    finally:
        # Restore
        scoring_mod.GROUP_MATCHES = original_group_matches


def test_ranking_v2_tiebreakers():
    """Verify that ranking V2 sorts predictions strictly according to the 7 tiebreaking criteria."""
    # Let's build a set of predictions and official result
    official = Prediction(participant="Official", champion="Brasil")
    official.meta["group_matches"] = {
        "m1": [1, 0]
    }
    
    # Mock GROUP_MATCHES
    import src.bolao.scoring as scoring_mod
    original_group_matches = scoring_mod.GROUP_MATCHES
    scoring_mod.GROUP_MATCHES = [
        {"id": "m1", "group": "A", "home_id": "228", "away_id": "232"},
    ]
    
    # We will build predictions that check each tier of tiebreakers.
    # We want:
    # pred1: 5 points (exact hit m1: 1x0), champion hit (Brasil), KO points 10, submitted 2026-06-01, name "A"
    # pred2: 5 points (exact hit m1: 1x0), champion hit (Brasil), KO points 10, submitted 2026-06-02, name "A" (worse timestamp than pred1)
    # pred3: 5 points (exact hit m1: 1x0), champion hit (Brasil), KO points 10, submitted 2026-06-02, name "B" (worse name than pred2)
    # pred4: 5 points (exact hit m1: 1x0), champion hit (Brasil), KO points 5 (worse KO than pred3)
    # pred5: 5 points (exact hit m1: 1x0), champion miss (Argentina), KO points 20 (worse champion than pred4)
    # pred6: 3 points (result+GD hit m1: 2x1), champion hit (Brasil), KO points 20 (worse total points than pred5)
    
    # Wait, let's verify if total points for pred6: 3 + 20 = 23, which is more than pred5: 5 + 0 + 20 = 25?
    # Ah, let's calculate carefully:
    # pred1: exact (5) + champ (20) + KO (10) = 35 total pts. Champ Hit: 1, KO: 10, Exact: 1, Group Pts: 5, time: 2026-06-01, name: "A"
    # pred2: exact (5) + champ (20) + KO (10) = 35 total pts. Champ Hit: 1, KO: 10, Exact: 1, Group Pts: 5, time: 2026-06-02, name: "A"
    # pred3: exact (5) + champ (20) + KO (10) = 35 total pts. Champ Hit: 1, KO: 10, Exact: 1, Group Pts: 5, time: 2026-06-02, name: "B"
    # pred4: exact (5) + champ (20) + KO (5)  = 30 total pts. Champ Hit: 1, KO: 5, Exact: 1, Group Pts: 5, time: 2026-06-01, name: "A"
    # pred5: exact (5) + champ (0)  + KO (25) = 30 total pts. Champ Hit: 0, KO: 25, Exact: 1, Group Pts: 5, time: 2026-06-01, name: "A"
    # (pred5 has 30 pts, champ hit 0, KO pts 25. pred4 has 30 pts, champ hit 1, KO pts 5. So pred4 > pred5 on Champion Hit)
    
    # pred6: resultGD (3) + champ (20) + KO (5) = 28 total pts. Champ Hit: 1, KO: 5, Exact: 0, Group Pts: 3, time: 2026-06-01, name: "A"
    # pred7: exact (5) + champ (0) + KO (23) = 28 total pts. Champ Hit: 0, KO: 23, Exact: 1, Group Pts: 5. (pred6 > pred7 on Total Points 28=28, Champ Hit 1 > 0)
    
    p1 = Prediction(participant="A", champion="Brasil", submitted_at="2026-06-01T12:00:00Z")
    p1.meta["group_matches"] = {"m1": [1, 0]} # 5 pts
    p1.knockout = {"oitavas": [Match(a="Mexico", b="SA", winner="Mexico")]} # 1 hit -> 3 pts, let's manually mock KO points or let score_prediction handle it.
    
    # Instead of simulating full knockout match lists, we can just populate knockout maps with matching teams.
    # For Oitavas (3pts each), let's make official have:
    official.knockout = {
        "oitavas": [
            Match(a="México", b="África do Sul", winner="México"),
            Match(a="Canadá", b="Bósnia", winner="Canadá"),
            Match(a="Brasil", b="Marrocos", winner="Brasil"),
        ],
        "quartas": [], "semifinais": [], "final": []
    }
    
    # p1: 1 group hit (5pts) + 3 oitavas hits (México, Canadá, Brasil -> 9pts) + champion (Brasil -> 20pts) = 34pts
    # Let's check:
    # Oitavas teams in official: México (228), Canadá (224), Brasil (226) (names normalized).
    # If p1 has those teams in oitavas, it gets 9pts.
    p1.knockout = {
        "oitavas": [
            Match(a="México", b="Canadá", winner="México"),
            Match(a="Brasil", b="Marrocos", winner="Brasil")
        ], # has México, Canadá, Brasil -> 3 hits -> 9pts
        "quartas": [], "semifinais": [], "final": []
    }
    
    # p2: Same as p1 but submitted later
    p2 = Prediction(participant="A", champion="Brasil", submitted_at="2026-06-02T12:00:00Z")
    p2.meta["group_matches"] = {"m1": [1, 0]}
    p2.knockout = {
        "oitavas": [
            Match(a="México", b="Canadá", winner="México"),
            Match(a="Brasil", b="Marrocos", winner="Brasil")
        ],
        "quartas": [], "semifinais": [], "final": []
    }
    
    # p3: Same as p2 but alphabetical name is "B"
    p3 = Prediction(participant="B", champion="Brasil", submitted_at="2026-06-02T12:00:00Z")
    p3.meta["group_matches"] = {"m1": [1, 0]}
    p3.knockout = {
        "oitavas": [
            Match(a="México", b="Canadá", winner="México"),
            Match(a="Brasil", b="Marrocos", winner="Brasil")
        ],
        "quartas": [], "semifinais": [], "final": []
    }
    
    # p4: Same as p1 but 1 less oitavas hit (lacks Brasil) -> KO points: 6pts. Total: 5 + 6 + 20 = 31pts
    p4 = Prediction(participant="A", champion="Brasil", submitted_at="2026-06-01T12:00:00Z")
    p4.meta["group_matches"] = {"m1": [1, 0]}
    p4.knockout = {
        "oitavas": [
            Match(a="México", b="Canadá", winner="México"),
        ], # México, Canadá -> 2 hits -> 6pts
        "quartas": [], "semifinais": [], "final": []
    }
    
    # p5: Misses champion (Argentina), but has more KO hits (9pts). Total: 5 (exact) + 0 (champ) + 9 (KO) = 14pts.
    # Note: p4 has 31pts, p5 has 14pts, so p4 is ahead on total points.
    # Let's adjust points to compare tiebreakers at same total points:
    # Say we want to compare:
    # p_champ_hit: 5 (exact) + 20 (champ) + 0 (KO) = 25 pts. Champ Hit: 1, KO: 0.
    # p_champ_miss: 5 (exact) + 0 (champ) + 20 (KO) = 25 pts. Champ Hit: 0, KO: 20 (has more KO points, but missed champion).
    # Since they both have 25 points, p_champ_hit must be ranked higher because of Champion Hit!
    p_champ_hit = Prediction(participant="ChampHit", champion="Brasil", submitted_at="2026-06-01T12:00:00Z")
    p_champ_hit.meta["group_matches"] = {"m1": [1, 0]} # 5 pts
    p_champ_hit.knockout = {"oitavas": [], "quartas": [], "semifinais": [], "final": []} # 0 pts. Total = 25
    
    p_champ_miss = Prediction(participant="ChampMiss", champion="Argentina", submitted_at="2026-06-01T12:00:00Z")
    p_champ_miss.meta["group_matches"] = {"m1": [1, 0]} # 5 pts
    p_champ_miss.knockout = {
        "oitavas": [
            Match(a="México", b="Canadá", winner="México"),
            Match(a="Brasil", b="Marrocos", winner="Brasil"),
            # Let's add extra matches in official/pred to get to 20 pts.
            # 20 pts in Oitavas = 20 / 3 = 6.66 hits. Not integer.
            # But we can define custom config rules or just use another phase!
            # Let's say we have 4 Oitavas hits (12pts) and 1 Quartas hit (5pts) and 1 Group Team Goals (1pt) + 1 Group Result (2pt) -> 20pts
        ],
        "quartas": [], "semifinais": [], "final": []
    }
    # Wait, a simpler way is to mock/set v2_rules to have simple numbers (e.g. ko_oitavas=20, ko_champion=20).
    # Let's do that!
    
    config = ScoreConfig(
        mode="v2",
        v2_rules={
            "group_exact": 5,
            "group_result_gd": 3,
            "group_result": 2,
            "group_team_goals": 1,
            "ko_oitavas": 10,
            "ko_quartas": 10,
            "ko_semifinais": 10,
            "ko_final": 10,
            "ko_champion": 20,
        }
    )
    
    # Now:
    # p_champ_hit: 5 (exact) + 20 (champ) + 0 (KO) = 25 pts
    # p_champ_miss: 5 (exact) + 0 (champ) + 20 (2 oitavas hits: 20 pts) = 25 pts
    p_champ_hit.knockout = {"oitavas": [], "quartas": [], "semifinais": [], "final": []}
    p_champ_miss.knockout = {
        "oitavas": [
            Match(a="México", b="Canadá", winner="México"), # 2 hits (México, Canadá are in official)
            Match(a="Inglaterra", b="França", winner="Inglaterra"), # 0 hits (Inglaterra, França are NOT in official)
        ],
        "quartas": [], "semifinais": [], "final": []
    }
    
    try:
        scores = rank_predictions([p_champ_miss, p_champ_hit], official, config)
        # ChampHit must be 1st because of champion_hit tiebreaker
        assert scores[0].participant == "ChampHit"
        assert scores[1].participant == "ChampMiss"
        
        # Test order of all: p1, p2, p3
        # p1: 5 (exact) + 20 (champ) + 20 (KO) = 45 pts. time: 2026-06-01
        # p2: 5 (exact) + 20 (champ) + 20 (KO) = 45 pts. time: 2026-06-02
        # p3: 5 (exact) + 20 (champ) + 20 (KO) = 45 pts. time: 2026-06-02, name "B"
        all_preds = [p3, p1, p2]
        scores = rank_predictions(all_preds, official, config)
        assert scores[0].participant == "A" and scores[0].submitted_at == "2026-06-01T12:00:00Z"
        assert scores[1].participant == "A" and scores[1].submitted_at == "2026-06-02T12:00:00Z"
        assert scores[2].participant == "B"
        
    finally:
        scoring_mod.GROUP_MATCHES = original_group_matches


def test_scoring_v2_creative_rules():
    """Verify that cumulative creative scoring rules are correctly applied."""
    official = Prediction(participant="Official")
    pred = Prediction(participant="Predictor")
    
    official.meta["group_matches"] = {
        "m1": [2, 1], # sum = 3, both = True, over_2_5 = True
        "m2": [1, 2], # sum = 3, both = True, over_2_5 = True
        "m3": [0, 0], # sum = 0, both = False, over_2_5 = False
    }
    
    pred.meta["group_matches"] = {
        "m1": [2, 1], # Exact hit (5pts) + sum (2pts) + both (1pt) + over (1pt) = 9pts
        "m2": [2, 1], # Missed result (Win instead of Loss), but sum=3 (2pts) + both=True (1pt) + over=True (1pt) = 4pts
        "m3": [1, 0], # Missed completely, sum=1 vs 0 (0pts), both=False (1pt), over=False (1pt) = 2pts
    }
    
    import src.bolao.scoring as scoring_mod
    original_group_matches = scoring_mod.GROUP_MATCHES
    scoring_mod.GROUP_MATCHES = [
        {"id": "m1", "group": "A", "home_id": "228", "away_id": "232"},
        {"id": "m2", "group": "A", "home_id": "228", "away_id": "232"},
        {"id": "m3", "group": "A", "home_id": "228", "away_id": "232"},
    ]
    
    try:
        config = ScoreConfig(
            mode="v2",
            v2_rules={
                "group_exact": 5,
                "group_result_gd": 3,
                "group_result": 2,
                "group_team_goals": 1,
                "group_sum_goals": 2,
                "group_both_scored": 1,
                "group_over_2_5": 1,
            }
        )
        sb = score_prediction(pred, official, config)
        # m1: 5 + 2 + 1 + 1 = 9
        # m2: 0 + 2 + 1 + 1 = 4
        # m3: 1 (team goals) + 0 + 1 + 1 = 3
        # Total group_points = 16
        assert sb.group_points == 16
    finally:
        scoring_mod.GROUP_MATCHES = original_group_matches


def test_default_config_includes_lock_flag():
    """Verify that default_config includes is_bolao_locked as False."""
    from src.bolao.storage import default_config
    config = default_config()
    assert "is_bolao_locked" in config
    assert config["is_bolao_locked"] is False


def test_init_simulator_state_restores_slots():
    """Verify that init_simulator_state restores slots and group matches from Prediction meta."""
    from src.bolao.ui_simulator import init_simulator_state
    from src.bolao.worldcup_2026_data import GROUP_MATCHES as ALL_GM
    import streamlit as st
    from unittest.mock import patch

    pred = Prediction(participant="TestParticipant")
    m_id = ALL_GM[0]["id"]
    pred.meta["group_matches"] = {m_id: [2, 1]}
    pred.meta["slots"] = {"0": "232", "1": "204"}

    session_state_mock = {}
    with patch.object(st, "session_state", session_state_mock):
        init_simulator_state(pred, force_reset=True)
        state = session_state_mock["simulator"]
        
        # Verify group matches restored
        assert state["group_matches"][m_id] == [2, 1]
        
        # Verify slots restored and keys converted to int
        assert state["slots"][0] == "232"
        assert state["slots"][1] == "204"


def test_init_simulator_state_deserializes_knockout():
    """Verify that init_simulator_state deserializes prediction knockout if no saved slots in meta."""
    from src.bolao.ui_simulator import init_simulator_state
    from src.bolao.worldcup_2026_data import GROUP_MATCHES as ALL_GM
    import streamlit as st
    from unittest.mock import patch

    pred = Prediction(participant="TestParticipant")
    # Mark group matches as simulated/complete
    group_matches = {}
    for gm in ALL_GM:
        group_matches[gm["id"]] = [1, 0] # Simple win for home
    pred.meta["group_matches"] = group_matches
    
    # We populate some knockout matches
    # e.g., fase_32 winner: Mexico (232) in the first match
    pred.knockout["fase_32"] = [Match(a="México", b="África do Sul", winner="México")]
    # champion: México
    pred.champion = "México"

    session_state_mock = {}
    with patch.object(st, "session_state", session_state_mock):
        init_simulator_state(pred, force_reset=True)
        state = session_state_mock["simulator"]
        
        # slots should be populated by deserialize_prediction_to_slots
        # México is team 232. Let's assert winner slot of first fase_32 match or champion slot is '232'
        # MAP_FASE_32 first match winner slot is slots[15] or slots[31]? Let's check:
        # It should deserialize winner of first fase_32 match to slots[w] where w is from MAP_FASE_32[0]
        from src.bolao.simulator_engine import MAP_FASE_32 as M_32
        first_w_slot = M_32[0][2]
        assert state["slots"][first_w_slot] == "232"
        assert state["slots"][0] == "232"

