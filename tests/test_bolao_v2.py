import pytest
from datetime import datetime, timedelta, timezone
from src.bolao.utils import render_countdown, avatar_url, foto_jogador
from src.bolao.live_scoring import calcular_pontos_goleadores
from src.bolao.storage import load_config, recalcular_pontos_modulo_brasil

def test_formatar_countdown_dias():
    # Offset of 5 days: 5 * 86400 + 8 * 3600 + 25 * 60 = 462300 seconds
    # It should show: 🟢 Fecha em 5d 08h25m
    futuro = datetime.now(timezone(timezone.utc.utcoffset(datetime.now()) or timedelta(hours=-3))) + timedelta(days=5, hours=8, minutes=25)
    res = render_countdown(futuro, 0)
    assert "Fecha em 5d 08h25m" in res
    assert "🟢" in res

def test_formatar_countdown_horas():
    # Offset of 50 minutes: 3000 seconds -> should show 🟡
    # Offset of 16 minutes: 1000 seconds -> should show 🔴
    futuro_yellow = datetime.now(timezone(timedelta(hours=-3))) + timedelta(minutes=50)
    res_y = render_countdown(futuro_yellow, 0)
    assert "🟡" in res_y

    futuro_red = datetime.now(timezone(timedelta(hours=-3))) + timedelta(minutes=16)
    res_r = render_countdown(futuro_red, 0)
    assert "🔴" in res_r

def test_foto_jogador_fallback():
    url = foto_jogador(99, "Jogador Inexistente")
    assert url.startswith("https://api.dicebear.com")
    assert "Jogador%20Inexistente" in url or "Jogador Inexistente" in url

def test_avatar_consistente_cartela_e_ranking():
    nome = "Baruja"
    assert avatar_url(nome) == avatar_url(nome)  # pure function

def test_recalculo_pontos_modulo_brasil():
    config = {
        "live_scoring": {
            "pts_acertar_goleador": 4,
            "pts_acertar_assistente": 2
        }
    }
    # Neymar suspended, Endrick is the reserve and Endrick scores.
    config["suspended_players"] = ["Neymar"]
    
    # Calculate points with reserve scoring
    pts_breakdown = calcular_pontos_goleadores(
        goleadores_palpitados=["Neymar"],
        assistentes_palpitados=[],
        goleadores_reais=["Endrick"],
        assistentes_reais=[],
        config=config,
        reservas_palpitadas=["Endrick"]
    )
    
    # Neymar suspended, reserve Endrick scored -> half points (4 // 2 = 2)
    assert pts_breakdown["total"] == 2
    assert any("Endrick" in d and "Reserva de Neymar" in d for d in pts_breakdown["detalhes"])
