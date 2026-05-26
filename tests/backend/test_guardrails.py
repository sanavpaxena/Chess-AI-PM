import pytest
import chess
from app.guardrails import sanitize_explanation, enforce_latency_budget
import time

def test_move_legality_check():
    """Test that illegal moves are flagged and removed."""
    # Start position FEN
    fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
    
    # Valid explanation with legal move (e4)
    valid_expl = "You should have played e4 to control the center."
    cleaned, flags = sanitize_explanation(valid_expl, fen)
    assert len(flags) == 0
    
    # Invalid explanation with illegal move (Ke5 from start pos)
    invalid_expl = "You should have played Ke5 to attack."
    cleaned, flags = sanitize_explanation(invalid_expl, fen)
    assert len(flags) > 0
    assert any("may not be legal" in flag for flag in flags)

def test_piece_existence_check():
    """Test that referencing non-existent pieces triggers a flag."""
    # Position with NO queens
    fen = "rnb1kbnr/pppppppp/8/8/8/8/PPPPPPPP/RNB1KBNR w KQkq - 0 1"
    
    expl = "Your queen was hanging."
    cleaned, flags = sanitize_explanation(expl, fen)
    assert len(flags) > 0
    assert any("References a" in flag for flag in flags)

def test_enforce_latency_budget():
    """Test the latency timer."""
    start = time.time() - 3.0  # Pretend it took 3 seconds
    elapsed, within_budget = enforce_latency_budget(start, budget_ms=2500)
    assert not within_budget
    assert elapsed >= 3000

    start_fast = time.time() - 1.0
    elapsed_fast, within_budget_fast = enforce_latency_budget(start_fast, budget_ms=2500)
    assert within_budget_fast
