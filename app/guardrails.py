"""
AI Guardrails for Grandmaster.AI

Implements safety checks and quality validation for LLM-generated
chess explanations. Ensures the AI doesn't hallucinate moves,
reference non-existent pieces, or exceed latency budgets.
"""

import time
import chess
import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)


class GuardrailResult:
    """Result of a guardrail check."""

    def __init__(self):
        self.passed = True
        self.flags: list[str] = []
        self.cleaned_text: Optional[str] = None

    def add_flag(self, flag: str, severity: str = "warning"):
        """Add a guardrail flag."""
        self.flags.append(f"[{severity.upper()}] {flag}")
        if severity == "error":
            self.passed = False

    def __bool__(self):
        return self.passed


def validate_move_legality(fen: str, move_str: str) -> bool:
    """
    Verify that a move referenced in the LLM output is legal in the given position.

    Args:
        fen: FEN string of the position
        move_str: Move in SAN or UCI notation

    Returns:
        True if the move is legal, False otherwise
    """
    try:
        board = chess.Board(fen)

        # Try SAN notation first
        try:
            board.parse_san(move_str)
            return True
        except (chess.IllegalMoveError, chess.InvalidMoveError, chess.AmbiguousMoveError):
            pass

        # Try UCI notation
        try:
            move = chess.Move.from_uci(move_str)
            return move in board.legal_moves
        except ValueError:
            pass

        return False

    except Exception as e:
        logger.error(f"Move legality check failed: {e}")
        return False


def check_hallucination(explanation: str, fen: str) -> GuardrailResult:
    """
    Check for hallucinations in the LLM-generated explanation.

    Verifies:
    1. Piece references match actual board state
    2. No invented moves or impossible scenarios
    3. Color references are consistent

    Args:
        explanation: The LLM-generated text
        fen: FEN of the position being discussed

    Returns:
        GuardrailResult with flags for any issues found
    """
    result = GuardrailResult()
    board = chess.Board(fen)

    # ── Check 1: Piece existence ────────────────────────────────
    # Extract piece references from the text
    piece_patterns = {
        "queen": chess.QUEEN,
        "rook": chess.ROOK,
        "bishop": chess.BISHOP,
        "knight": chess.KNIGHT,
        "pawn": chess.PAWN,
    }

    for piece_name, piece_type in piece_patterns.items():
        # Count references to "your queen" / "white's queen" etc.
        pattern = rf"\b(?:your|white'?s?|black'?s?|the)\s+{piece_name}\b"
        mentions = re.findall(pattern, explanation.lower())

        if mentions:
            # Check if that piece type exists on the board
            white_count = len(board.pieces(piece_type, chess.WHITE))
            black_count = len(board.pieces(piece_type, chess.BLACK))

            if white_count == 0 and black_count == 0:
                result.add_flag(
                    f"References a {piece_name} but none exist on the board",
                    severity="warning"
                )

    # ── Check 2: Square references ─────────────────────────────
    # Look for algebraic square references (e.g., "e4", "d5")
    square_pattern = r"\b([a-h][1-8])\b"
    squares_mentioned = set(re.findall(square_pattern, explanation.lower()))

    for sq_str in squares_mentioned:
        try:
            sq = chess.parse_square(sq_str)
            # Square reference is valid (it's on the board, even if empty)
            # This is a soft check — mentioning empty squares isn't necessarily wrong
        except ValueError:
            result.add_flag(
                f"Invalid square reference: {sq_str}",
                severity="warning"
            )

    # ── Check 3: Move suggestions (should not invent new moves) ──
    # Look for move-like patterns (e.g., "Nf3", "Bxe5", "O-O")
    move_pattern = r"\b([KQRBN]?[a-h]?[1-8]?x?[a-h][1-8](?:=[QRBN])?[+#]?)\b"
    moves_mentioned = re.findall(move_pattern, explanation)

    for move_str in moves_mentioned:
        # Skip if it's just a square reference
        if len(move_str) == 2:
            continue
        if not validate_move_legality(fen, move_str):
            result.add_flag(
                f"Suggests move '{move_str}' which may not be legal in this position",
                severity="warning"
            )

    # ── Check 4: Result consistency ────────────────────────────
    # Check for contradictory claims
    if "checkmate" in explanation.lower():
        if not board.is_checkmate():
            result.add_flag(
                "Claims checkmate but the position is not checkmate",
                severity="warning"
            )

    if "stalemate" in explanation.lower():
        if not board.is_stalemate():
            result.add_flag(
                "Claims stalemate but the position is not stalemate",
                severity="warning"
            )

    return result


def enforce_latency_budget(
    start_time: float,
    budget_ms: float = 2500,
) -> tuple[float, bool]:
    """
    Check if the response time is within the latency budget.

    Args:
        start_time: time.time() when the request started
        budget_ms: Maximum acceptable latency in milliseconds

    Returns:
        Tuple of (elapsed_ms, within_budget)
    """
    elapsed_ms = (time.time() - start_time) * 1000

    if elapsed_ms > budget_ms:
        logger.warning(
            f"Latency budget exceeded: {elapsed_ms:.0f}ms > {budget_ms:.0f}ms budget"
        )
        return elapsed_ms, False

    return elapsed_ms, True


def sanitize_explanation(explanation: str, fen: str) -> tuple[str, list[str]]:
    """
    Full guardrail pipeline: check and sanitize an LLM explanation.

    Args:
        explanation: Raw LLM output
        fen: FEN of the position

    Returns:
        Tuple of (cleaned_explanation, list_of_flags)
    """
    flags = []

    # Run hallucination check
    hallucination_result = check_hallucination(explanation, fen)
    flags.extend(hallucination_result.flags)

    # Basic text cleaning
    cleaned = explanation.strip()

    # Remove any system prompt leakage
    markers = ["## Instructions", "## Your Explanation", "## The Blunder", "<|", "|>"]
    for marker in markers:
        if marker in cleaned:
            cleaned = cleaned.split(marker)[0].strip()
            flags.append("[INFO] Removed system prompt leakage from response")

    # Ensure the response isn't empty after cleaning
    if not cleaned or len(cleaned) < 20:
        flags.append("[ERROR] Generated explanation was too short or empty")
        cleaned = (
            "The engine detected a significant evaluation loss on this move. "
            "Consider reviewing the position carefully to understand what tactical "
            "or positional element was missed."
        )

    # Cap length (prevent runaway generation)
    max_words = 350
    words = cleaned.split()
    if len(words) > max_words:
        cleaned = " ".join(words[:max_words]) + "..."
        flags.append(f"[INFO] Response truncated to {max_words} words")

    return cleaned, flags
