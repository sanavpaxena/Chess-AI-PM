"""
Pydantic models for the Grandmaster.AI API.

Defines request/response schemas for the blunder analysis pipeline.
"""

from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum


class GameResult(str, Enum):
    """Possible game outcomes."""
    WIN = "win"
    LOSS = "loss"
    DRAW = "draw"


class AnalysisRequest(BaseModel):
    """Request to analyze a Chess.com user's game."""
    username: str = Field(..., description="Chess.com username", min_length=1, max_length=50)
    game_index: int = Field(0, description="Index of game to analyze (0 = most recent)", ge=0)


class PGNAnalysisRequest(BaseModel):
    """Request to analyze a raw PGN string."""
    pgn: str = Field(..., description="PGN string of the game to analyze", min_length=10)
    player_color: Optional[str] = Field(None, description="'white' or 'black' — whose perspective to analyze")


class GameInfo(BaseModel):
    """Metadata about a chess game."""
    white: str = Field(..., description="White player's username")
    black: str = Field(..., description="Black player's username")
    white_elo: Optional[int] = Field(None, description="White player's Elo rating")
    black_elo: Optional[int] = Field(None, description="Black player's Elo rating")
    result: str = Field(..., description="Game result (e.g., '1-0', '0-1', '1/2-1/2')")
    date: Optional[str] = Field(None, description="Date the game was played")
    time_control: Optional[str] = Field(None, description="Time control (e.g., '600' for 10min)")
    opening: Optional[str] = Field(None, description="Opening name if available")
    url: Optional[str] = Field(None, description="Link to the game on Chess.com")
    total_moves: int = Field(0, description="Total number of moves in the game")


class BlunderInfo(BaseModel):
    """Details about the biggest blunder in a game."""
    move_number: int = Field(..., description="Move number where the blunder occurred")
    move_played: str = Field(..., description="The move that was played (SAN notation)")
    move_played_uci: str = Field(..., description="The move that was played (UCI notation)")
    best_move: str = Field(..., description="The engine's best move (SAN notation)")
    best_move_uci: str = Field(..., description="The engine's best move (UCI notation)")
    eval_before: float = Field(..., description="Engine evaluation before the blunder (centipawns)")
    eval_after: float = Field(..., description="Engine evaluation after the blunder (centipawns)")
    centipawn_loss: float = Field(..., description="Centipawn loss from the blunder")
    fen_before: str = Field(..., description="FEN position before the blunder move")
    fen_after: str = Field(..., description="FEN position after the blunder move")
    player_color: str = Field(..., description="Color of the player who blundered ('white' or 'black')")
    move_category: str = Field("blunder", description="Classification: blunder, mistake, inaccuracy")


class RetrievedContext(BaseModel):
    """A piece of retrieved historical commentary from the vector DB."""
    source: str = Field(..., description="Source of the commentary (e.g., game reference)")
    theme: str = Field(..., description="Chess theme (e.g., 'tactics', 'king_safety')")
    commentary: str = Field(..., description="The historical commentary text")
    similarity_score: float = Field(..., description="Cosine similarity score (0-1)")


class AnalysisResponse(BaseModel):
    """Complete response from the blunder analysis pipeline."""
    game_info: GameInfo
    blunder: BlunderInfo
    explanation: str = Field(..., description="AI-generated human-readable explanation of the blunder")
    similar_contexts: list[RetrievedContext] = Field(
        default_factory=list,
        description="Retrieved historical contexts used for RAG"
    )
    latency_ms: float = Field(..., description="Total response time in milliseconds")
    latency_budget_ms: float = Field(2500, description="Target latency budget")
    within_budget: bool = Field(True, description="Whether response was within latency budget")
    guardrail_flags: list[str] = Field(
        default_factory=list,
        description="Any guardrail warnings triggered during generation"
    )


class HealthResponse(BaseModel):
    """Health check response."""
    status: str = "healthy"
    stockfish_available: bool = False
    vector_db_ready: bool = False
    llm_available: bool = False
    version: str = "0.1.0"


class ErrorResponse(BaseModel):
    """Error response schema."""
    error: str
    detail: Optional[str] = None
    suggestion: Optional[str] = None
