import sys
import os
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta

# Create Mock Streamlit Context and SessionState
class MockStreamlitContext:
    def __enter__(self):
        return self
    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

class MockSessionState(dict):
    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError(f"MockSessionState object has no attribute '{key}'")
    def __setattr__(self, key, value):
        self[key] = value
    def __delattr__(self, key):
        try:
            del self[key]
        except KeyError:
            raise AttributeError(f"MockSessionState object has no attribute '{key}'")

def mock_decorator(*args, **kwargs):
    def decorator(func):
        return func
    return decorator

class MockStreamlit:
    def __init__(self):
        self.session_state = MockSessionState()
        self.secrets = {}
        
        # Cache decorators
        self.cache_resource = MagicMock(side_effect=mock_decorator)
        cache_data_mock = MagicMock(side_effect=mock_decorator)
        cache_data_mock.clear = MagicMock()
        self.cache_data = cache_data_mock

        self.markdown = MagicMock()
        self.caption = MagicMock()
        self.warning = MagicMock()
        self.error = MagicMock()
        self.success = MagicMock()
        self.info = MagicMock()
        self.toast = MagicMock()
        self.text_input = MagicMock(return_value="Test Name")
        self.number_input = MagicMock(return_value=0)
        self.selectbox = MagicMock(side_effect=lambda label, options, **kwargs: options[0] if options else None)
        self.text_area = MagicMock(return_value="")
        self.link_button = MagicMock()
        self.write = MagicMock()
        self.rerun = MagicMock()
        self.code = MagicMock()
        self.html = MagicMock()
        
        # Context managers / layout
        self.form = MagicMock(return_value=MockStreamlitContext())
        self.form_submit_button = MagicMock(return_value=False)
        self.button = MagicMock(return_value=False)
        self.expander = MagicMock(return_value=MockStreamlitContext())
        self.dataframe = MagicMock()
        self.image = MagicMock()
        
        # columns helper
        def cols_mock(spec):
            length = len(spec) if isinstance(spec, list) else spec
            return [MockStreamlitContext() for _ in range(length)]
        self.columns = MagicMock(side_effect=cols_mock)
        
        # tabs helper
        def tabs_mock(spec):
            return [MockStreamlitContext() for _ in range(len(spec))]
        self.tabs = MagicMock(side_effect=tabs_mock)

# Inject mock Streamlit into sys.modules temporarily during imports
mock_st = MockStreamlit()
real_st = sys.modules.get('streamlit')
sys.modules['streamlit'] = mock_st

# Now import the modules to test
from src.bolao.models import LiveMatch, LivePrediction, Prediction
from src.bolao.ui_live_matches import render_jogos_de_hoje, is_match_open_for_prediction
from src.bolao.ui_cartela import render_minha_cartela
from src.bolao.ui_simulator import render_simulator

# Restore real streamlit in sys.modules
if real_st is not None:
    sys.modules['streamlit'] = real_st
else:
    sys.modules.pop('streamlit', None)


@pytest.fixture(autouse=True)
def run_before_and_after_tests():
    # Reset streamlit mock call logs and session state before each test
    mock_st.session_state.clear()
    mock_st.markdown.reset_mock()
    mock_st.caption.reset_mock()
    mock_st.warning.reset_mock()
    mock_st.error.reset_mock()
    mock_st.success.reset_mock()
    mock_st.info.reset_mock()
    mock_st.toast.reset_mock()
    mock_st.text_input.reset_mock()
    mock_st.number_input.reset_mock()
    mock_st.selectbox.reset_mock()
    mock_st.selectbox.side_effect = lambda label, options, **kwargs: options[0] if options else None
    mock_st.text_area.reset_mock()
    mock_st.link_button.reset_mock()
    mock_st.write.reset_mock()
    mock_st.rerun.reset_mock()
    mock_st.form.reset_mock()
    mock_st.form_submit_button.reset_mock()
    mock_st.button.reset_mock()
    mock_st.expander.reset_mock()
    mock_st.dataframe.reset_mock()
    mock_st.image.reset_mock()
    mock_st.columns.reset_mock()
    mock_st.tabs.reset_mock()
    
    # Patch st dynamically at runtime in all modules
    with patch('src.bolao.ui_live_matches.st', mock_st), \
         patch('src.bolao.ui_cartela.st', mock_st), \
         patch('src.bolao.ui_simulator.st', mock_st), \
         patch('src.bolao.storage.st', mock_st), \
         patch('src.bolao.scoring.st', mock_st):
        yield

def test_is_match_open_for_prediction_edge_cases():
    # Test open match
    starts_at = (datetime.now() + timedelta(minutes=15)).isoformat()
    match = LiveMatch(
        match_id="1", phase="grupos", group="A", round_label="R1",
        home_team="Brasil", away_team="França", starts_at=starts_at, lock_at=None
    )
    assert is_match_open_for_prediction(match) is True

    # Test lock time reached
    match.lock_at = (datetime.now() - timedelta(minutes=1)).isoformat()
    assert is_match_open_for_prediction(match) is False

    # Test missing starts_at
    match.starts_at = ""
    assert is_match_open_for_prediction(match) is False

    # Test invalid starts_at format
    match.starts_at = "invalid-date"
    assert is_match_open_for_prediction(match) is False


@patch("src.bolao.ui_live_matches.load_config")
@patch("src.bolao.ui_live_matches.load_matches")
@patch("src.bolao.ui_live_matches.load_live_predictions")
@patch("src.bolao.ui_live_matches.load_submissions")
def test_render_jogos_de_hoje_anonymous(mock_submissions, mock_preds, mock_matches, mock_config):
    mock_config.return_value = {"live_mode_enabled": True}
    mock_matches.return_value = []
    mock_preds.return_value = []
    mock_submissions.return_value = []

    # Render - user not identified yet
    render_jogos_de_hoje()
    
    # Verification that the name form is shown
    mock_st.form.assert_called_once_with("live_user_identification")
    mock_st.text_input.assert_any_call("Seu Nome no Bolão", placeholder="Ex: César")


@patch("src.bolao.ui_live_matches.load_config")
@patch("src.bolao.ui_live_matches.load_matches")
@patch("src.bolao.ui_live_matches.load_live_predictions")
@patch("src.bolao.ui_live_matches.load_submissions")
def test_render_jogos_de_hoje_identified(mock_submissions, mock_preds, mock_matches, mock_config):
    mock_config.return_value = {
        "live_mode_enabled": True,
        "reveal_live_predictions_after_lock": True,
        "live_scoring": {
            "exact_score": 5,
            "outcome": 3,
            "goal_one_team": 1,
            "goal_difference": 1
        }
    }
    
    # 3 Matches: 1 open, 1 locked/live, 1 approved
    now_dt = datetime.now()
    m_open = LiveMatch(
        match_id="1", phase="grupos", group="A", round_label="Rodada 1",
        home_team="Brasil", away_team="França",
        starts_at=(now_dt + timedelta(hours=2)).isoformat(),
        lock_at=(now_dt + timedelta(hours=1, minutes=50)).isoformat(),
        status="scheduled"
    )
    m_locked = LiveMatch(
        match_id="2", phase="grupos", group="A", round_label="Rodada 1",
        home_team="Espanha", away_team="Alemanha",
        starts_at=(now_dt - timedelta(minutes=5)).isoformat(),
        lock_at=(now_dt - timedelta(minutes=15)).isoformat(),
        status="live"
    )
    m_approved = LiveMatch(
        match_id="3", phase="grupos", group="A", round_label="Rodada 1",
        home_team="Argentina", away_team="Uruguai",
        starts_at=(now_dt - timedelta(hours=4)).isoformat(),
        lock_at=(now_dt - timedelta(hours=4, minutes=10)).isoformat(),
        status="result_approved",
        official_home_goals=2, official_away_goals=1, winner="Argentina"
    )
    
    mock_matches.return_value = [m_open, m_locked, m_approved]
    
    # Predictions
    pred_approved = LivePrediction(
        id="cesar_3", participant_name="César", participant_key="cesar",
        match_id="3", predicted_home_goals=2, predicted_away_goals=1,
        submitted_at=now_dt.isoformat(), updated_at=now_dt.isoformat()
    )
    
    mock_preds.return_value = [pred_approved]
    mock_submissions.return_value = []
    
    # Set session state for identified user
    mock_st.session_state["live_user_name"] = "César"
    mock_st.session_state["live_user_key"] = "cesar"
    
    # Test rendering runs completely without crashes
    render_jogos_de_hoje()
    
    # Check that it drew the main UI elements
    mock_st.tabs.assert_called_once_with(["🚀 Jogos Abertos", "🔒 Jogos Fechados & Live", "🏆 Resultados Aprovados"])
    mock_st.markdown.assert_any_call("### ⚽ Jogos de Hoje — Jogo a Jogo")


@patch("src.bolao.ui_cartela.load_config")
@patch("src.bolao.ui_cartela.load_submissions")
@patch("src.bolao.ui_cartela.load_official")
@patch("src.bolao.ui_cartela.load_matches")
@patch("src.bolao.ui_cartela.load_live_predictions")
def test_render_minha_cartela(mock_preds, mock_matches, mock_official, mock_submissions, mock_config):
    mock_config.return_value = {"scoring_mode": "v2"}
    mock_official.return_value = {}
    
    # Set up some matches
    mock_matches.return_value = [
        LiveMatch(
            match_id="1", phase="grupos", group="A", round_label="Rodada 1",
            home_team="Brasil", away_team="França", starts_at="2026-06-11T16:00:00",
            lock_at="2026-06-11T15:50:00", status="scheduled"
        )
    ]
    
    # Set up classic submissions
    sub_1 = Prediction(participant="César")
    sub_1.submission_id = "testcode123"
    sub_1.champion = "Brasil"
    sub_1.groups = {"A": ["Brasil", "França", "Coreia do Sul", "México"]}
    sub_1.knockout = {"final": [MagicMock(a="Brasil", b="França", winner="Brasil")]}
    
    sub_2 = Prediction(participant="Pedro")
    sub_2.submission_id = "testcode456"
    sub_2.champion = "Argentina"
    sub_2.groups = {"A": ["Argentina", "França", "Coreia do Sul", "México"]}
    sub_2.knockout = {"final": [MagicMock(a="Argentina", b="França", winner="Argentina")]}
    
    mock_submissions.return_value = [sub_1, sub_2]
    
    # Set up live predictions
    pred_1 = LivePrediction(
        id="cesar_1", participant_name="César", participant_key="cesar",
        match_id="1", predicted_home_goals=3, predicted_away_goals=1,
        submitted_at="2026-06-11T16:00:00", updated_at="2026-06-11T16:00:00"
    )
    pred_2 = LivePrediction(
        id="pedro_1", participant_name="Pedro", participant_key="pedro",
        match_id="1", predicted_home_goals=2, predicted_away_goals=2,
        submitted_at="2026-06-11T16:00:00", updated_at="2026-06-11T16:00:00"
    )
    mock_preds.return_value = [pred_1, pred_2]
    
    # Mock selected name return: first call (César), second call (Pedro)
    mock_st.selectbox.side_effect = ["César", "Pedro"]
    
    # Run UI rendering
    render_minha_cartela()
    
    # Verify elements rendering
    mock_st.markdown.assert_any_call("### 📋 Minha Cartela — Visão Geral do Participante")
    mock_st.tabs.assert_called_once_with(["📊 Resumo Geral", "🏆 Palpite Clássico", "🎯 Palpites Jogo a Jogo", "💡 Pontuação", "🎖️ Conquistas", "⚖️ Comparar com Amigo"])


@patch("src.bolao.ui_simulator.init_simulator_state")
def test_render_simulator(mock_init_state):
    from src.bolao.worldcup_2026_data import GROUP_MATCHES
    pred = Prediction(participant="Teste")
    pred.groups = {}
    pred.knockout = {}
    pred.champion = None
    
    mock_st.session_state["public_classic_guess_Teste"] = {
        "group_matches": {gm["id"]: [None, None] for gm in GROUP_MATCHES},
        "slots": {i: None for i in range(63)},
        "_version": "2026-live-mode-v1"
    }
    
    # Call render simulator with mock
    with patch("src.bolao.ui_simulator._sim_state_key", return_value="public_classic_guess_Teste"):
        render_simulator(pred, is_admin=False)
        
    mock_st.markdown.assert_any_call("### 🎛️ Controles do Simulador")
