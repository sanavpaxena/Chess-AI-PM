import pytest
from fastapi.testclient import TestClient
import os

# Set testing environment variables before importing the app
os.environ["CHROMA_DB_PATH"] = "./tests/data/chromadb"
os.environ["ANONYMIZED_TELEMETRY"] = "False"
os.environ["GEMINI_API_KEY"] = "AIzaSy_MOCK_TEST_KEY_THAT_IS_39_CHARS_LONG"

from app.main import app
from app.rag_engine import get_chroma_client

@pytest.fixture(scope="session", autouse=True)
def setup_test_env():
    """Setup testing environment, like mock DBs."""
    os.makedirs("./tests/data", exist_ok=True)
    yield
    # Cleanup could happen here

@pytest.fixture
def client():
    """Returns a FastAPI test client."""
    with TestClient(app) as test_client:
        yield test_client

@pytest.fixture
def mock_stockfish(mocker):
    """Mocks the Stockfish engine so tests don't require the binary."""
    mock_engine = mocker.MagicMock()
    mock_popen = mocker.patch("chess.engine.SimpleEngine.popen_uci")
    mock_popen.return_value = mock_engine
    
    # Setup mock analysis results
    mock_info = {
        "score": mocker.MagicMock(),
        "pv": [mocker.MagicMock()]
    }
    # Return 0 eval by default
    mock_info["score"].white.return_value.score.return_value = 0
    mock_info["score"].white.return_value.is_mate.return_value = False
    
    mock_engine.analyse.return_value = mock_info
    
    yield mock_engine, mock_info

@pytest.fixture
def mock_gemini(mocker):
    """Mocks the Gemini API client."""
    mock_client = mocker.MagicMock()
    mocker.patch("app.rag_engine.get_gemini_client", return_value=mock_client)
    
    # Setup a fake response
    mock_response = mocker.MagicMock()
    mock_response.text = "This is a mock AI explanation."
    mock_client.models.generate_content.return_value = mock_response
    
    yield mock_client
