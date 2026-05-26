"""
Grandmaster.AI — FastAPI Backend

Main application with endpoints for chess game analysis,
blunder detection, and AI-powered explanation generation.
"""

import os
import time
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from app.models import (
    AnalysisRequest,
    PGNAnalysisRequest,
    AnalysisResponse,
    HealthResponse,
    ErrorResponse,
    GameInfo,
)
from app.chess_service import (
    fetch_user_games,
    parse_pgn,
    extract_game_info,
    find_biggest_blunder,
    get_board_svg,
    get_board_features,
)
from app.rag_engine import (
    init_vector_db,
    retrieve_similar_positions,
    build_prompt,
    generate_explanation,
    is_vector_db_ready,
    is_llm_available,
)
from app.guardrails import sanitize_explanation, enforce_latency_budget
from app.learning_loop import init_db, store_blunder_pattern

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

MAX_LATENCY_MS = float(os.getenv("MAX_LATENCY_MS", "2500"))


# ── Lifespan ────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize resources on startup."""
    logger.info("🚀 Starting Grandmaster.AI Backend")
    try:
        init_vector_db()
        logger.info("✅ Vector database initialized")
        init_db()
        logger.info("✅ Learning Loop database initialized")
    except Exception as e:
        logger.warning(f"⚠️ Vector DB initialization issue: {e}")
    yield
    logger.info("🛑 Shutting down Grandmaster.AI Backend")


# ── App ─────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Grandmaster.AI",
    description="Context-Aware Blunder Recovery — AI-powered chess analysis with RAG",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Health Check ────────────────────────────────────────────────────────
@app.get("/health", response_model=HealthResponse, tags=["System"])
async def health_check():
    """Check system health and component availability."""
    stockfish_available = os.path.exists(os.getenv("STOCKFISH_PATH", "/opt/homebrew/bin/stockfish"))
    return HealthResponse(
        status="healthy",
        stockfish_available=stockfish_available,
        vector_db_ready=is_vector_db_ready(),
        llm_available=is_llm_available(),
        version="0.1.0",
    )


# ── Analyze by Username ────────────────────────────────────────────────
@app.post(
    "/analyze",
    response_model=AnalysisResponse,
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    tags=["Analysis"],
)
async def analyze_game(request: AnalysisRequest):
    """
    Analyze a Chess.com user's recent game.

    1. Fetches the user's latest game from Chess.com API
    2. Identifies the biggest blunder using Stockfish
    3. Retrieves similar historical positions from the vector DB
    4. Generates a human-readable explanation via LLM
    5. Applies AI guardrails for quality & safety

    Latency budget: {MAX_LATENCY_MS}ms
    """
    start_time = time.time()

    try:
        # Step 1: Fetch game from Chess.com
        logger.info(f"Fetching games for user: {request.username}")
        games = await fetch_user_games(request.username)

        if not games:
            raise HTTPException(status_code=404, detail=f"No games found for user '{request.username}'")

        if request.game_index >= len(games):
            raise HTTPException(
                status_code=400,
                detail=f"Game index {request.game_index} out of range. Found {len(games)} games.",
            )

        game_data = games[request.game_index]
        pgn_str = game_data.get("pgn", "")
        game_url = game_data.get("url", "")

        if not pgn_str:
            raise HTTPException(status_code=400, detail="Game has no PGN data")

        # Step 2: Parse PGN
        game = parse_pgn(pgn_str)
        if not game:
            raise HTTPException(status_code=400, detail="Failed to parse game PGN")

        game_info = extract_game_info(game, url=game_url)

        # Determine which color the user played
        player_color = None
        if request.username.lower() == game_info.white.lower():
            player_color = "white"
        elif request.username.lower() == game_info.black.lower():
            player_color = "black"

        # Step 3: Find biggest blunder with Stockfish
        logger.info(f"Analyzing game ({game_info.total_moves} moves) with Stockfish...")
        blunder = find_biggest_blunder(game, player_color=player_color)

        if blunder is None:
            # If no blunder found for the specific color, try both colors
            blunder = find_biggest_blunder(game)

        if blunder is None:
            raise HTTPException(
                status_code=200,
                detail="No significant blunders found in this game. Well played!",
            )

        # Step 4: Retrieve similar positions from vector DB
        board_features = get_board_features(blunder.fen_before)
        similar_contexts = retrieve_similar_positions(blunder, board_features, k=3)

        # Step 5: Generate explanation via RAG
        prompt = build_prompt(blunder, similar_contexts)
        raw_explanation = await generate_explanation(prompt)

        # Step 6: Apply guardrails
        cleaned_explanation, guardrail_flags = sanitize_explanation(
            raw_explanation, blunder.fen_before
        )

        # Step 7: The Learning Loop (Product Feature)
        blunder_theme = similar_contexts[0].theme if similar_contexts else "general"
        store_blunder_pattern(request.username, blunder_theme)
        
        learning_loop_msg = "This is your most recent game. We'll track this pattern and check your next games tomorrow!"
        if request.game_index > 0:
            next_games = games[max(0, request.game_index - 3) : request.game_index]
            repeated = False
            for next_g in next_games:
                try:
                    next_game_obj = parse_pgn(next_g.get("pgn", ""))
                    next_blunder = find_biggest_blunder(next_game_obj, depth=8, player_color=player_color)
                    if next_blunder:
                        next_features = get_board_features(next_blunder.fen_before)
                        next_contexts = retrieve_similar_positions(next_blunder, next_features, k=1)
                        if next_contexts and next_contexts[0].theme == blunder_theme and blunder_theme != "general":
                            repeated = True
                            break
                except Exception as e:
                    logger.error(f"Learning loop check failed for next game: {e}")
                    pass
            
            if repeated:
                learning_loop_msg = "You made this mistake again in your next game — want to retry?"
            else:
                learning_loop_msg = f"You avoided this pattern in your next {len(next_games)} games ✓"

        # Step 8: Check latency
        elapsed_ms, within_budget = enforce_latency_budget(start_time, MAX_LATENCY_MS)

        return AnalysisResponse(
            game_info=game_info,
            blunder=blunder,
            explanation=cleaned_explanation,
            similar_contexts=similar_contexts,
            latency_ms=round(elapsed_ms, 1),
            latency_budget_ms=MAX_LATENCY_MS,
            within_budget=within_budget,
            guardrail_flags=guardrail_flags,
            learning_loop_feedback=learning_loop_msg,
        )

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.exception(f"Analysis failed: {e}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


# ── Analyze by PGN ─────────────────────────────────────────────────────
@app.post(
    "/analyze-pgn",
    response_model=AnalysisResponse,
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    tags=["Analysis"],
)
async def analyze_pgn(request: PGNAnalysisRequest):
    """
    Analyze a raw PGN string directly.

    Same pipeline as /analyze but accepts PGN input instead of
    fetching from Chess.com.
    """
    start_time = time.time()

    try:
        # Parse PGN
        game = parse_pgn(request.pgn)
        if not game:
            raise HTTPException(status_code=400, detail="Failed to parse PGN")

        game_info = extract_game_info(game)

        # Find blunder
        blunder = find_biggest_blunder(game, player_color=request.player_color)
        if blunder is None:
            blunder = find_biggest_blunder(game)

        if blunder is None:
            raise HTTPException(status_code=200, detail="No significant blunders found.")

        # RAG pipeline
        board_features = get_board_features(blunder.fen_before)
        similar_contexts = retrieve_similar_positions(blunder, board_features, k=3)
        prompt = build_prompt(blunder, similar_contexts)
        raw_explanation = await generate_explanation(prompt)
        cleaned_explanation, guardrail_flags = sanitize_explanation(
            raw_explanation, blunder.fen_before
        )

        elapsed_ms, within_budget = enforce_latency_budget(start_time, MAX_LATENCY_MS)

        return AnalysisResponse(
            game_info=game_info,
            blunder=blunder,
            explanation=cleaned_explanation,
            similar_contexts=similar_contexts,
            latency_ms=round(elapsed_ms, 1),
            latency_budget_ms=MAX_LATENCY_MS,
            within_budget=within_budget,
            guardrail_flags=guardrail_flags,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"PGN analysis failed: {e}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


# ── Board SVG ──────────────────────────────────────────────────────────
@app.get("/board", tags=["Utilities"])
async def get_board(fen: str, last_move: str = None, size: int = 400):
    """Get an SVG rendering of a chess board position."""
    from fastapi.responses import Response

    try:
        svg = get_board_svg(fen, last_move_uci=last_move, size=size)
        return Response(content=svg, media_type="image/svg+xml")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid FEN or move: {str(e)}")


# ── User Games List ───────────────────────────────────────────────────
@app.get("/games/{username}", response_model=list[GameInfo], tags=["Chess.com"])
async def list_user_games(username: str, limit: int = 10):
    """List recent games for a Chess.com user."""
    try:
        games = await fetch_user_games(username, max_games=limit)
        result = []
        for g in games:
            pgn_str = g.get("pgn", "")
            if pgn_str:
                game = parse_pgn(pgn_str)
                if game:
                    info = extract_game_info(game, url=g.get("url", ""))
                    result.append(info)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
