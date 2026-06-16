import sys
import os
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta

# Mock streamlit.set_page_config before importing app to prevent crashes
with patch('streamlit.set_page_config'):
    import app

from src.bolao.models import LiveMatch, LivePrediction, Prediction
from src.bolao.ui_live_matches import is_match_open_for_prediction
from src.bolao.storage import (
    load_registered_participants,
    register_participant,
    delete_registered_participant,
    save_registered_participants,
)


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
        self.set_page_config = MagicMock()
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
        self.checkbox = MagicMock(return_value=False)
        self.text_area = MagicMock(return_value="")
        self.link_button = MagicMock()
        self.write = MagicMock()
        self.rerun = MagicMock()
        self.code = MagicMock()
        self.html = MagicMock()
        self.json = MagicMock()
        
        # Context managers / layout
        self.form = MagicMock(return_value=MockStreamlitContext())
        self.form_submit_button = MagicMock(return_value=False)
        self.button = MagicMock(return_value=False)
        self.expander = MagicMock(return_value=MockStreamlitContext())
        self.container = MagicMock(return_value=MockStreamlitContext())
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

mock_st = MockStreamlit()


@pytest.fixture(autouse=True)
def run_before_and_after_tests():
    mock_st.session_state.clear()
    mock_st.markdown.reset_mock()
    mock_st.caption.reset_mock()
    mock_st.warning.reset_mock()
    mock_st.error.reset_mock()
    mock_st.success.reset_mock()
    mock_st.info.reset_mock()
    mock_st.toast.reset_mock()
    mock_st.text_input.reset_mock()
    mock_st.text_input.return_value = "Test Name"
    mock_st.number_input.reset_mock()
    mock_st.selectbox.reset_mock()
    mock_st.selectbox.side_effect = lambda label, options, **kwargs: options[0] if options else None
    mock_st.checkbox.reset_mock()
    mock_st.checkbox.return_value = False
    mock_st.text_area.reset_mock()
    mock_st.link_button.reset_mock()
    mock_st.write.reset_mock()
    mock_st.rerun.reset_mock()
    mock_st.form.reset_mock()
    mock_st.form_submit_button.reset_mock()
    mock_st.button.reset_mock()
    mock_st.expander.reset_mock()
    mock_st.container.reset_mock()
    mock_st.dataframe.reset_mock()
    mock_st.image.reset_mock()
    mock_st.columns.reset_mock()
    mock_st.tabs.reset_mock()
    mock_st.json.reset_mock()
    
    # Patch st dynamically at runtime in all modules
    with patch('src.bolao.ui_live_matches.st', mock_st), \
         patch('src.bolao.ui_components.st', mock_st), \
         patch('src.bolao.storage.st', mock_st), \
         patch('app.st', mock_st):
        yield


def test_is_match_open_for_prediction_overrides():
    # Base match (normally open)
    starts_at = (datetime.now() + timedelta(minutes=15)).isoformat()
    match = LiveMatch(
        match_id="99", phase="grupos", group="A", round_label="R1",
        home_team="Team A", away_team="Team B", starts_at=starts_at, lock_at=None,
        bets_manual_closed=None
    )
    
    # 1. Default (None) is open
    assert is_match_open_for_prediction(match) is True

    # 2. Override: Closed
    match.bets_manual_closed = True
    assert is_match_open_for_prediction(match) is False

    # 3. Override: Open
    match.bets_manual_closed = False
    assert is_match_open_for_prediction(match) is True

    # 4. Lock time passed but force open
    match.bets_manual_closed = False
    match.starts_at = (datetime.now() - timedelta(minutes=15)).isoformat()
    assert is_match_open_for_prediction(match) is True


def test_registered_participants_lifecycle(tmp_path):
    # Setup temporary file path for registered_participants
    temp_json_path = tmp_path / "registered_participants.json"
    
    with patch('src.bolao.storage.REGISTERED_PARTICIPANTS_PATH', temp_json_path), \
         patch('src.bolao.storage.load_live_predictions', return_value=[]), \
         patch('src.bolao.storage.load_submissions', return_value=[]), \
         patch('src.bolao.storage._seed_initial_state', return_value=None):
        # Starts empty
        assert load_registered_participants() == []
        
        # Register new participant
        register_participant("Lucas")
        assert load_registered_participants() == ["Lucas"]
        
        # Duplicate registration ignored (case-insensitive)
        register_participant("lucas ")
        assert load_registered_participants() == ["Lucas"]
        
        # Delete participant
        delete_registered_participant("LUCAS")
        assert load_registered_participants() == []


def test_admin_participants_loads_registered_participants():
    # Mock return values for load_submissions, load_live_predictions, load_registered_participants
    submissions = [
        Prediction(participant="Alice", submission_id="sub1", submitted_at="", status="confirmado")
    ]
    live_preds = [
        LivePrediction(
            id="lp1", participant_name="Bob", participant_key="bob",
            match_id="1", predicted_home_goals=1, predicted_away_goals=0,
            submitted_at="", updated_at="", points=0, scoring_breakdown=[]
        )
    ]
    registered = ["Charlie"]
    
    # Configure text_input mock to return empty string for search query
    mock_st.text_input.return_value = ""

    with patch('app.load_app_data_cached') as mock_cache, \
         patch('src.bolao.storage.load_submissions', return_value=submissions), \
         patch('src.bolao.storage.load_live_predictions', return_value=live_preds), \
         patch('src.bolao.storage.load_registered_participants', return_value=registered), \
         patch('src.bolao.storage.load_matches', return_value=[]):
        
        mock_ctx = MagicMock()
        mock_ctx.submissions = submissions
        mock_cache.return_value = mock_ctx
        
        from app import admin_participants
        
        admin_participants()
        
        # Verify Charlie appears in the data frame of participants
        import pandas as pd
        df_call = None
        for call in mock_st.dataframe.call_args_list:
            args, kwargs = call
            if len(args) > 0 and isinstance(args[0], pd.DataFrame):
                df_call = args[0]
                break
        
        assert df_call is not None
        names_list = df_call["Nome"].tolist()
        assert "Alice" in names_list
        assert "Bob" in names_list
        assert "Charlie" in names_list
