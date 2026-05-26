"""
Chess Service for Grandmaster.AI

Handles:
- Fetching games from Chess.com public API
- PGN parsing with python-chess
- Stockfish-based blunder detection
"""

import chess
import chess.pgn
import chess.engine
import httpx
import io
import os
import logging
from typing import Optional
from datetime import datetime
from dotenv import load_dotenv

from app.models import GameInfo, BlunderInfo

load_dotenv()
logger = logging.getLogger(__name__)

# ── Configuration ──────────────────────────────────────────────────────────
STOCKFISH_PATH = os.getenv("STOCKFISH_PATH", "/opt/homebrew/bin/stockfish")
ANALYSIS_DEPTH = int(os.getenv("ANALYSIS_DEPTH", "16"))
CHESS_COM_API_BASE = "https://api.chess.com/pub"

# Centipawn thresholds for move classification
BLUNDER_THRESHOLD = 200  # centipawns
MISTAKE_THRESHOLD = 100
INACCURACY_THRESHOLD = 50


def _get_headers() -> dict:
    """Chess.com API requires a User-Agent header."""
    return {
        "User-Agent": "GrandmasterAI/1.0 (Chess Analysis Tool; contact: grandmaster-ai@example.com)",
        "Accept": "application/json",
    }


async def fetch_user_games(username: str, max_games: int = 10) -> list[dict]:
    """
    Fetch recent games for a Chess.com user.

    Uses the archives endpoint to find the most recent month,
    then fetches games from that archive.
    """
    async with httpx.AsyncClient(timeout=15.0) as client:
        # Get list of monthly archives
        archives_url = f"{CHESS_COM_API_BASE}/player/{username}/games/archives"
        resp = await client.get(archives_url, headers=_get_headers())

        if resp.status_code == 404:
            raise ValueError(f"Chess.com user '{username}' not found.")
        resp.raise_for_status()

        archives = resp.json().get("archives", [])
        if not archives:
            raise ValueError(f"No game archives found for '{username}'.")

        # Fetch games from the most recent archive(s)
        all_games = []
        for archive_url in reversed(archives[-2:]):  # Last 2 months
            resp = await client.get(archive_url, headers=_get_headers())
            resp.raise_for_status()
            games = resp.json().get("games", [])
            all_games.extend(games)
            if len(all_games) >= max_games:
                break

        # Sort by end_time descending, return most recent
        all_games.sort(key=lambda g: g.get("end_time", 0), reverse=True)
        return all_games[:max_games]


def parse_pgn(pgn_string: str) -> Optional[chess.pgn.Game]:
    """Parse a PGN string into a python-chess Game object."""
    try:
        pgn_io = io.StringIO(pgn_string)
        errors = []
        
        class ErrorCatchingBuilder(chess.pgn.GameBuilder):
            def handle_error(self, error):
                errors.append(str(error))
                super().handle_error(error)
                
        game = chess.pgn.read_game(pgn_io, Visitor=ErrorCatchingBuilder)
        if errors:
            logger.warning(f"PGN parse warnings: {errors}")
        return game
    except Exception as e:
        logger.error(f"Failed to parse PGN: {e}")
        return None


def extract_game_info(game: chess.pgn.Game, url: Optional[str] = None) -> GameInfo:
    """Extract metadata from a parsed PGN game."""
    headers = game.headers

    # Count total moves
    total_moves = 0
    node = game
    while node.variations:
        node = node.variations[0]
        total_moves += 1

    return GameInfo(
        white=headers.get("White", "Unknown"),
        black=headers.get("Black", "Unknown"),
        white_elo=int(headers["WhiteElo"]) if "WhiteElo" in headers and headers["WhiteElo"] != "?" else None,
        black_elo=int(headers["BlackElo"]) if "BlackElo" in headers and headers["BlackElo"] != "?" else None,
        result=headers.get("Result", "*"),
        date=headers.get("Date", None),
        time_control=headers.get("TimeControl", None),
        opening=headers.get("ECOUrl", headers.get("Opening", None)),
        url=url,
        total_moves=total_moves,
    )


def find_biggest_blunder(
    game: chess.pgn.Game,
    stockfish_path: str = STOCKFISH_PATH,
    depth: int = ANALYSIS_DEPTH,
    player_color: Optional[str] = None,
) -> Optional[BlunderInfo]:
    """
    Iterate through all moves in a game, evaluate each position with Stockfish,
    and identify the biggest blunder (largest centipawn loss).

    Args:
        game: Parsed PGN game
        stockfish_path: Path to Stockfish binary
        depth: Analysis depth (higher = more accurate, slower)
        player_color: If set, only analyze this color's moves ('white' or 'black')

    Returns:
        BlunderInfo for the biggest blunder, or None if no significant blunder found
    """
    try:
        engine = chess.engine.SimpleEngine.popen_uci(stockfish_path)
    except FileNotFoundError:
        logger.error(f"Stockfish not found at: {stockfish_path}")
        raise RuntimeError(
            f"Stockfish engine not found at '{stockfish_path}'. "
            "Install it via 'brew install stockfish' (macOS) or download from stockfishchess.org"
        )

    try:
        board = game.board()
        moves = list(game.mainline_moves())

        if len(moves) < 4:
            logger.warning("Game has fewer than 4 moves, skipping analysis.")
            return None

        biggest_blunder = None
        biggest_loss = 0
        prev_eval = 0  # Start from equal position

        for i, move in enumerate(moves):
            move_number = (i // 2) + 1
            is_white = (i % 2 == 0)
            color_str = "white" if is_white else "black"

            # Skip if we're only analyzing one color
            if player_color and color_str != player_color:
                board.push(move)
                # Still evaluate to track position
                info = engine.analyse(board, chess.engine.Limit(depth=max(depth - 4, 8)))
                score = info["score"].white()
                prev_eval = _score_to_centipawns(score)
                continue

            # Get evaluation BEFORE this move (engine's best)
            fen_before = board.fen()
            info_before = engine.analyse(board, chess.engine.Limit(depth=depth))
            eval_before = _score_to_centipawns(info_before["score"].white())
            best_move_engine = info_before.get("pv", [None])[0]

            # Play the move
            san_played = board.san(move)
            board.push(move)
            fen_after = board.fen()

            # Get evaluation AFTER the move
            info_after = engine.analyse(board, chess.engine.Limit(depth=depth))
            eval_after = _score_to_centipawns(info_after["score"].white())

            # Calculate centipawn loss from the player's perspective
            if is_white:
                cp_loss = eval_before - eval_after
            else:
                cp_loss = eval_after - eval_before  # For black, higher is worse

            # Track the biggest blunder
            if cp_loss > biggest_loss and cp_loss >= INACCURACY_THRESHOLD:
                # Classify the move
                if cp_loss >= BLUNDER_THRESHOLD:
                    category = "blunder"
                elif cp_loss >= MISTAKE_THRESHOLD:
                    category = "mistake"
                else:
                    category = "inaccuracy"

                # Get best move in SAN notation
                best_san = "N/A"
                best_uci = "N/A"
                if best_move_engine:
                    # We need a fresh board at the position before the move
                    temp_board = chess.Board(fen_before)
                    best_san = temp_board.san(best_move_engine)
                    best_uci = best_move_engine.uci()

                biggest_loss = cp_loss
                biggest_blunder = BlunderInfo(
                    move_number=move_number,
                    move_played=san_played,
                    move_played_uci=move.uci(),
                    best_move=best_san,
                    best_move_uci=best_uci,
                    eval_before=round(eval_before / 100, 2),  # Convert to pawns
                    eval_after=round(eval_after / 100, 2),
                    centipawn_loss=round(cp_loss, 0),
                    fen_before=fen_before,
                    fen_after=fen_after,
                    player_color=color_str,
                    move_category=category,
                )

            prev_eval = eval_after

        return biggest_blunder

    finally:
        engine.quit()


def _score_to_centipawns(score: chess.engine.PovScore) -> float:
    """Convert a Stockfish score to centipawns (from White's perspective)."""
    if score.is_mate():
        mate_in = score.mate()
        if mate_in is not None:
            # Large positive/negative value for mate
            return 10000 if mate_in > 0 else -10000
    cp = score.score()
    return float(cp) if cp is not None else 0.0


def get_board_svg(fen: str, last_move_uci: Optional[str] = None, size: int = 400) -> str:
    """
    Generate an SVG representation of a chess board position.

    Args:
        fen: FEN string of the position
        last_move_uci: UCI notation of the last move (for highlighting)
        size: Board size in pixels

    Returns:
        SVG string of the board
    """
    board = chess.Board(fen)

    # Parse last move for highlighting
    last_move = None
    if last_move_uci:
        try:
            last_move = chess.Move.from_uci(last_move_uci)
        except ValueError:
            pass

    svg = chess.svg.board(
        board,
        lastmove=last_move,
        size=size,
        colors={
            "square light": "#e8e0d0",
            "square dark": "#7c6f64",
            "margin": "#1a1a2e",
            "coord": "#a0a0b8",
        },
    )
    return svg


def get_board_features(fen: str) -> dict:
    """
    Extract chess features from a FEN position for similarity matching.

    This creates a feature vector that captures the essence of a position
    for vector similarity search in the RAG pipeline.
    """
    board = chess.Board(fen)

    features = {
        # Material balance
        "material_white": sum(
            len(board.pieces(pt, chess.WHITE)) * val
            for pt, val in [
                (chess.PAWN, 1), (chess.KNIGHT, 3), (chess.BISHOP, 3),
                (chess.ROOK, 5), (chess.QUEEN, 9)
            ]
        ),
        "material_black": sum(
            len(board.pieces(pt, chess.BLACK)) * val
            for pt, val in [
                (chess.PAWN, 1), (chess.KNIGHT, 3), (chess.BISHOP, 3),
                (chess.ROOK, 5), (chess.QUEEN, 9)
            ]
        ),
        # King safety indicators
        "white_king_file": chess.square_file(board.king(chess.WHITE)),
        "black_king_file": chess.square_file(board.king(chess.BLACK)),
        "white_castling": board.has_castling_rights(chess.WHITE),
        "black_castling": board.has_castling_rights(chess.BLACK),
        # Pawn structure
        "white_pawns": len(board.pieces(chess.PAWN, chess.WHITE)),
        "black_pawns": len(board.pieces(chess.PAWN, chess.BLACK)),
        # Piece activity
        "white_pieces_total": sum(len(board.pieces(pt, chess.WHITE)) for pt in chess.PIECE_TYPES[1:]),
        "black_pieces_total": sum(len(board.pieces(pt, chess.BLACK)) for pt in chess.PIECE_TYPES[1:]),
        # Phase (opening/middlegame/endgame)
        "total_pieces": len(board.piece_map()),
        "is_endgame": len(board.piece_map()) <= 12,
        # Tactical indicators
        "is_check": board.is_check(),
        "legal_moves_count": len(list(board.legal_moves)),
        # Turn
        "turn": "white" if board.turn else "black",
    }

    # Detect common themes
    themes = []
    if features["is_check"]:
        themes.append("check")
    if features["is_endgame"]:
        themes.append("endgame")
    if features["total_pieces"] > 28:
        themes.append("opening")
    elif not features["is_endgame"]:
        themes.append("middlegame")
    if abs(features["material_white"] - features["material_black"]) > 3:
        themes.append("material_imbalance")
    if not features["white_castling"] and not features["black_castling"]:
        themes.append("open_position")

    features["themes"] = themes
    return features
