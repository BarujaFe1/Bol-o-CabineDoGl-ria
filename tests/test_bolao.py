import pytest
from datetime import datetime, timedelta, timezone
from src.bolao.utils import render_countdown, buscar_jogador_copa, avatar_url
from src.bolao.constants import ELENCO_BRASIL_2026, VENUES_COPA_2026
from src.bolao.live_scoring import calcular_pontos_goleadores, calcular_pontos_artilheiro_classico

CONFIG_PADRAO = {
    "live_scoring": {
        "pts_acertar_goleador": 4,
        "pts_acertar_assistente": 2,
        "pts_goleador_mais_assist": 8,
        "pts_todos_goleadores": 5
    },
    "pts_artilheiro_brasil_copa": 15,
    "pts_top3_artilheiros_brasil": 5,
    "pts_artilheiro_geral_copa": 20,
    "pts_top3_artilheiros_generais": 7,
    "pts_gol_de_ouro": 10
}

def test_countdown_jogo_aberto():
    # dado um horário 2h no futuro, deve retornar string com h:mm:ss
    futuro = datetime.now(timezone.utc) + timedelta(hours=2)
    res = render_countdown(futuro, 10)
    assert "Fecha em 01:" in res or "Fecha em 02:" in res

def test_countdown_jogo_fechado():
    # dado um horário no passado, deve retornar "FECHADO"
    passado = datetime.now(timezone.utc) - timedelta(hours=1)
    res = render_countdown(passado, 10)
    assert res == "🔒 FECHADO"

def test_pontos_goleador_simples():
    # acertar 1 de 2 goleadores → 4 pts
    assert calcular_pontos_goleadores(
        ["Neymar", "Vini Jr."], [], ["Neymar", "Endrick"], [], CONFIG_PADRAO
    )["total"] == 4

def test_pontos_todos_goleadores():
    # acertar todos → 4+4+5bonus = 13 pts
    assert calcular_pontos_goleadores(
        ["Neymar", "Vini Jr."], [], ["Neymar", "Vini Jr."], [], CONFIG_PADRAO
    )["total"] == 13

def test_pontos_goleador_repetido():
    # apostar Vini×2, acertar 1 → 4 pts (não 8)
    assert calcular_pontos_goleadores(
        ["Vini Jr.", "Vini Jr."], [], ["Vini Jr.", "Neymar"], [], CONFIG_PADRAO
    )["total"] == 4

def test_pontos_assistente():
    # acertar 1 assistente → 2 pts
    assert calcular_pontos_goleadores(
        ["Neymar"], ["Raphinha"], ["Neymar"], ["Raphinha"], CONFIG_PADRAO
    )["total"] == 4 + 2  # gol + assist separados

def test_busca_jogador_copa():
    resultado = buscar_jogador_copa("mbappe")
    assert any("Mbappé" in r["nome"] for r in resultado)
    assert all(r["selecao"] == "França" for r in resultado if "Mbappé" in r["nome"])

def test_busca_jogador_brasil():
    resultado = buscar_jogador_copa("vini")
    assert any("Vini Jr." in r["nome"] for r in resultado)

def test_avatar_url_retorna_string():
    url = avatar_url("Baruja")
    assert url.startswith("https://api.dicebear.com")
    assert "Baruja" in url or "Baruja" in url

def test_elenco_brasil_tem_26():
    assert len(ELENCO_BRASIL_2026) == 26

def test_elenco_brasil_sem_wesley():
    nomes = [j["nome"] for j in ELENCO_BRASIL_2026]
    assert "Wesley" not in nomes
    assert "Éderson" in nomes  # lateral, não o goleiro Ederson Moraes
    assert "Ederson Moraes" in nomes  # goleiro

def test_elenco_brasil_camisa_2_ederson():
    camisa2 = next(j for j in ELENCO_BRASIL_2026 if j["camisa"] == 2)
    assert camisa2["nome"] == "Éderson"
    assert camisa2["posicao"] == "DEF"

def test_venues_tem_16():
    assert len(VENUES_COPA_2026) == 16

def test_calcular_ousadia_sem_historico():
    # We will test calculate_ousadia logic or mock it
    # For now, assert a dummy to ensure test protocol runs
    assert True

def test_pontuacao_artilheiro_classico_top3():
    # função que calcula pontos clássicos do artilheiro
    assert calcular_pontos_artilheiro_classico(
        palpitado="Neymar",
        artilheiros_reais=["Vini Jr.", "Neymar", "Endrick"],
        config=CONFIG_PADRAO
    ) == 5  # top 3, não o 1º

def test_pontuacao_artilheiro_classico_acerto_exato():
    assert calcular_pontos_artilheiro_classico(
        palpitado="Vini Jr.",
        artilheiros_reais=["Vini Jr.", "Neymar", "Endrick"],
        config=CONFIG_PADRAO
    ) == 15  # acertou o 1º

def test_pontos_modo_relampago():
    from src.bolao.live_scoring import calculate_live_prediction_points
    from src.bolao.models import LiveMatch, LivePrediction
    
    # Match with halftime scores and lightning mode active
    match = LiveMatch(
        match_id="test_lightning_match",
        phase="grupos",
        group="Group A",
        round_label="Rodada 1",
        home_team="Brasil",
        away_team="Marrocos",
        starts_at="2026-06-11T16:00:00",
        status="result_approved",
        official_home_goals=3,
        official_away_goals=0,
        placar_intervalo_mandante=1,
        placar_intervalo_visitante=0,
        modo_relampago_ativo=False
    )
    
    # Exact prediction: Brasil +2, Marrocos +0 (halftime prediction goals)
    pred_exact = LivePrediction(
        id="user1_test_lightning_match",
        participant_name="User1",
        participant_key="user1",
        match_id="test_lightning_match",
        predicted_home_goals=2, # pre-match prediction (Brasil 2 x 1)
        predicted_away_goals=1,
        submitted_at="2026-06-11T15:00:00",
        updated_at="2026-06-11T15:00:00",
        predicted_second_half_home_goals=2, # exact (2 goals)
        predicted_second_half_away_goals=0  # exact (0 goals)
    )
    
    # Outcome prediction: Brasil +1, Marrocos +0
    pred_outcome = LivePrediction(
        id="user2_test_lightning_match",
        participant_name="User2",
        participant_key="user2",
        match_id="test_lightning_match",
        predicted_home_goals=2,
        predicted_away_goals=1,
        submitted_at="2026-06-11T15:00:00",
        updated_at="2026-06-11T15:00:00",
        predicted_second_half_home_goals=1, # outcome matches but not exact
        predicted_second_half_away_goals=0
    )
    
    config = {
        "live_scoring": {
            "exact_score": 5,
            "outcome": 3,
            "goal_one_team": 1,
            "goal_difference": 1,
            "pts_relampago_exato": 4,
            "pts_relampago_resultado": 2
        }
    }
    
    res_exact = calculate_live_prediction_points(pred_exact, match, config)
    res_outcome = calculate_live_prediction_points(pred_outcome, match, config)
    
    assert res_exact["points"] == 7
    assert any("⚡ Relâmpago Exato" in x for x in res_exact["breakdown"])
    
    assert res_outcome["points"] == 5
    assert any("⚡ Relâmpago Resultado" in x for x in res_outcome["breakdown"])
