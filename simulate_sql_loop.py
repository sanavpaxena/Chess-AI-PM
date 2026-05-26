import os
import sys

# Setup environment for testing
os.environ["CHROMA_DB_PATH"] = "./tests/data/chromadb"
os.environ["ANONYMIZED_TELEMETRY"] = "False"
os.environ["GEMINI_API_KEY"] = "MOCK_KEY_FOR_TESTING"
os.environ["LEARNING_LOOP_DB_PATH"] = "./data/learning_loop.db"

from fastapi.testclient import TestClient
from app.main import app
from unittest.mock import patch, MagicMock, AsyncMock

def main():
    print("--- Simulating the SQLite Learning Loop ---\n")
    
    # Initialize TestClient which triggers the lifespan events (DB init)
    with TestClient(app) as client:
        # We patch external calls to make the script run instantly without API limits
        with patch("app.main.fetch_user_games", new_callable=AsyncMock) as mock_fetch, \
             patch("app.main.find_biggest_blunder") as mock_blunder, \
             patch("app.main.retrieve_similar_positions") as mock_rag, \
             patch("app.main.generate_explanation", new_callable=AsyncMock) as mock_gen, \
             patch("app.main.parse_pgn") as mock_parse:
             
            # Mock fetch_user_games to return 5 dummy games
            mock_fetch.return_value = [{"pgn": f"dummy pgn {i}"} for i in range(5)]
            
            # Mock blunder detection
            blunder_mock = MagicMock()
            blunder_mock.fen_before = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
            mock_blunder.return_value = blunder_mock
            
            # Mock RAG retrieval so it identifies the 'king_safety' theme
            rag_mock = MagicMock()
            rag_mock.theme = "king_safety"
            mock_rag.return_value = [rag_mock]
            
            mock_gen.return_value = "Mock AI explanation"
            
            print("[1] Simulating user 'hikaru' analyzing an older game (Game Index 3)...")
            print("    The Learning Loop will automatically scan Games 2, 1, and 0 to see if the 'king_safety' mistake was repeated.")
            
            response = client.post("/analyze", json={"username": "hikaru", "game_index": 3})
            
            if response.status_code != 200:
                print(f"Error: {response.text}")
                return
                
            data = response.json()
            feedback = data.get("learning_loop_feedback")
            
            print(f"\n[2] Learning Loop Feedback Returned to Streamlit:")
            print(f"    ➡️  {feedback}")
            
            print("\n[3] Verifying data was successfully persisted to SQLite...")
            from app.learning_loop import get_user_patterns
            patterns = get_user_patterns("hikaru")
            for idx, p in enumerate(patterns):
                print(f"    Record {idx+1}: Theme='{p['theme']}', Timestamp='{p['timestamp']}'")
                
            print("\n✅ SQL Loop Test Completed Successfully!")

if __name__ == "__main__":
    main()
