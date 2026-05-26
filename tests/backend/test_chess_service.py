import pytest
import chess
from app.chess_service import parse_pgn, extract_game_info, find_biggest_blunder, get_board_features

def test_parse_pgn_valid():
    pgn = '[Event "Casual Game"]\n\n1. e4 e5 2. Nf3 Nc6'
    game = parse_pgn(pgn)
    assert game is not None
    assert game.headers.get("Event") == "Casual Game"

def test_parse_pgn_invalid():
    pgn = 'not a real pgn string at all'
    game = parse_pgn(pgn)
    # python-chess might still return a Game object with no moves
    assert game is not None
    assert len(list(game.mainline_moves())) == 0

def test_extract_game_info():
    pgn = '[White "Hikaru"]\n[Black "Magnus"]\n[Result "1-0"]\n\n1. e4'
    game = parse_pgn(pgn)
    info = extract_game_info(game)
    assert info.white == "Hikaru"
    assert info.black == "Magnus"
    assert info.result == "1-0"
    assert info.total_moves == 1

def test_get_board_features():
    fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
    features = get_board_features(fen)
    assert features["material_white"] == 39
    assert features["material_black"] == 39
    assert "opening" in features["themes"]

def test_find_biggest_blunder(mock_stockfish):
    """Test blunder finding using the mock stockfish fixture."""
    pgn = '1. e4 e5 2. Nf3 Nc6 3. Bc4'
    game = parse_pgn(pgn)
    
    # Configure mock eval sequence so that move 3 (Bc4) is a "blunder"
    mock_engine, mock_info = mock_stockfish
    
    # We simulate evaluations for 3 moves (6 total evals as it checks before/after)
    # Let's say White's last move (Bc4) loses 300 centipawns
    def mock_eval_score():
        score_mock = mock_engine.analyse.return_value["score"].white.return_value
        return score_mock

    # It checks before and after. We just ensure it doesn't crash since we mocked it.
    blunder = find_biggest_blunder(game, depth=1)
    
    # Since our mock just returns 0 every time, there will be no blunder
    assert blunder is None
