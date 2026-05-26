"""
RAG Engine for Grandmaster.AI

Handles:
- ChromaDB vector database initialization and management
- Ingestion of annotated chess positions
- Semantic retrieval of similar positions/commentary
- LLM prompt construction and inference via Google Gemini API (free tier)
"""

import os
import json
import logging
from typing import Optional
from pathlib import Path

# Disable ChromaDB telemetry (avoids posthog version mismatch errors)
os.environ["ANONYMIZED_TELEMETRY"] = "False"

import chromadb
from google import genai
from dotenv import load_dotenv

from app.models import BlunderInfo, RetrievedContext

load_dotenv()
logger = logging.getLogger(__name__)

# ── Configuration ──────────────────────────────────────────────────────────
CHROMA_DB_PATH = os.getenv("CHROMA_DB_PATH", "./data/chromadb")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
COLLECTION_NAME = "chess_annotations"

# ── Clients (Singleton) ─────────────────────────────────────────────────
_chroma_client: Optional[chromadb.PersistentClient] = None
_gemini_client: Optional[genai.Client] = None


def get_chroma_client() -> chromadb.PersistentClient:
    """Get or create the ChromaDB persistent client."""
    global _chroma_client
    if _chroma_client is None:
        os.makedirs(CHROMA_DB_PATH, exist_ok=True)
        _chroma_client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
        logger.info(f"ChromaDB initialized at {CHROMA_DB_PATH}")
    return _chroma_client


def get_gemini_client() -> Optional[genai.Client]:
    """Get or create the Google Gemini client."""
    global _gemini_client
    if _gemini_client is None:
        if not GEMINI_API_KEY or GEMINI_API_KEY.startswith("AIza_xxx"):
            logger.warning(
                "No valid Gemini API key found. "
                "Set GEMINI_API_KEY in your .env file. "
                "Get a free key at https://aistudio.google.com/apikey — "
                "Using fallback explanation generation."
            )
            return None
        if not GEMINI_API_KEY.startswith("AIzaSy") or len(GEMINI_API_KEY) < 39:
            logger.warning(
                f"Gemini API key looks malformed (length={len(GEMINI_API_KEY)}). "
                "Valid keys are 39 characters starting with 'AIzaSy'. "
                "Get a new key at https://aistudio.google.com/apikey"
            )
        _gemini_client = genai.Client(api_key=GEMINI_API_KEY)
        logger.info(f"Gemini client initialized with model: {GEMINI_MODEL}")
    return _gemini_client


def init_vector_db() -> chromadb.Collection:
    """
    Initialize the ChromaDB collection for chess annotations.

    Uses the default embedding function (all-MiniLM-L6-v2) which is
    automatically handled by ChromaDB.
    """
    client = get_chroma_client()
    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"description": "Annotated chess positions with grandmaster commentary"},
    )
    logger.info(f"Collection '{COLLECTION_NAME}' ready with {collection.count()} documents")
    return collection


def ingest_annotations(data_dir: str = "./data/annotations") -> int:
    """
    Load annotated chess positions from JSON files and ingest into ChromaDB.

    Each position document contains:
    - FEN string
    - Theme tags (tactics, positional, endgame, etc.)
    - Human commentary explaining the position
    - Source attribution

    Returns:
        Number of documents ingested
    """
    collection = init_vector_db()
    data_path = Path(data_dir)

    if not data_path.exists():
        logger.error(f"Data directory not found: {data_dir}")
        return 0

    total_ingested = 0

    for json_file in data_path.glob("*.json"):
        try:
            with open(json_file, "r") as f:
                data = json.load(f)

            positions = data.get("positions", [])
            if not positions:
                continue

            # Prepare batch data
            ids = []
            documents = []
            metadatas = []

            for idx, pos in enumerate(positions):
                doc_id = f"{json_file.stem}_{idx}"

                # Check if already ingested
                existing = collection.get(ids=[doc_id])
                if existing and existing["ids"]:
                    continue

                # Create a rich text document for embedding
                # Combine FEN description, theme, and commentary for semantic search
                doc_text = _build_document_text(pos)
                meta = {
                    "fen": pos.get("fen", ""),
                    "theme": pos.get("theme", "general"),
                    "source": pos.get("source", "Unknown"),
                    "tags": ",".join(pos.get("tags", [])),
                }

                ids.append(doc_id)
                documents.append(doc_text)
                metadatas.append(meta)

            if ids:
                collection.add(ids=ids, documents=documents, metadatas=metadatas)
                total_ingested += len(ids)
                logger.info(f"Ingested {len(ids)} positions from {json_file.name}")

        except Exception as e:
            logger.error(f"Error ingesting {json_file}: {e}")

    logger.info(f"Total documents ingested: {total_ingested}. Collection size: {collection.count()}")
    return total_ingested


def _build_document_text(position: dict) -> str:
    """
    Build a rich text document from a position entry for embedding.

    Combines the chess theme, commentary, and contextual tags into a
    single document that captures the semantic meaning of the position.
    """
    parts = []

    theme = position.get("theme", "general")
    parts.append(f"Chess position theme: {theme}.")

    commentary = position.get("commentary", "")
    if commentary:
        parts.append(commentary)

    tags = position.get("tags", [])
    if tags:
        parts.append(f"Related concepts: {', '.join(tags)}.")

    source = position.get("source", "")
    if source:
        parts.append(f"From: {source}.")

    fen = position.get("fen", "")
    if fen:
        parts.append(f"Position (FEN): {fen}")

    return " ".join(parts)


def retrieve_similar_positions(
    blunder_info: BlunderInfo,
    board_features: dict,
    k: int = 3,
) -> list[RetrievedContext]:
    """
    Query the vector database for positions similar to the blunder.

    Uses a combination of the board state description and the blunder
    characteristics to find relevant historical commentary.
    """
    collection = init_vector_db()

    if collection.count() == 0:
        logger.warning("Vector DB is empty. Run seed_data.py first.")
        return []

    # Build a query that captures the essence of the blunder
    query = _build_query_from_blunder(blunder_info, board_features)

    try:
        results = collection.query(
            query_texts=[query],
            n_results=min(k, collection.count()),
        )

        contexts = []
        if results and results["documents"]:
            for i, (doc, meta, distance) in enumerate(zip(
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0],
            )):
                # Convert distance to similarity score (ChromaDB uses cosine distance)
                similarity = max(0, 1 - (distance / 2))  # Normalize

                contexts.append(RetrievedContext(
                    source=meta.get("source", "Unknown"),
                    theme=meta.get("theme", "general"),
                    commentary=doc,
                    similarity_score=round(similarity, 3),
                ))

        return contexts

    except Exception as e:
        logger.error(f"Vector search failed: {e}")
        return []


def _build_query_from_blunder(blunder_info: BlunderInfo, features: dict) -> str:
    """Build a semantic search query from blunder information."""
    parts = []

    # Describe the blunder type
    parts.append(f"A {blunder_info.move_category} in a chess game.")

    # Phase of the game
    themes = features.get("themes", [])
    if "endgame" in themes:
        parts.append("This occurred in the endgame phase.")
    elif "opening" in themes:
        parts.append("This occurred in the opening phase.")
    else:
        parts.append("This occurred in the middlegame.")

    # Material context
    if "material_imbalance" in themes:
        parts.append("There is a significant material imbalance.")

    # Evaluation swing
    loss = blunder_info.centipawn_loss
    if loss > 500:
        parts.append("This was a catastrophic blunder losing significant material or allowing checkmate.")
    elif loss > 200:
        parts.append("This was a major blunder losing material worth roughly a piece.")
    else:
        parts.append("This was a positional mistake weakening the position.")

    # King safety
    if features.get("is_check"):
        parts.append("The position involves a check.")

    return " ".join(parts)


def build_prompt(blunder_info: BlunderInfo, contexts: list[RetrievedContext]) -> str:
    """
    Construct the RAG prompt for LLM explanation generation.

    The prompt includes:
    1. System instruction for chess coach persona
    2. The blunder details
    3. Retrieved historical context
    4. Output format guidelines
    """
    # Build context section from retrieved documents
    context_text = ""
    if contexts:
        context_parts = []
        for i, ctx in enumerate(contexts, 1):
            context_parts.append(
                f"Reference {i} ({ctx.source}):\n{ctx.commentary}"
            )
        context_text = "\n\n".join(context_parts)

    prompt = f"""You are a friendly, expert chess coach explaining a blunder to an intermediate player (1000-1500 Elo). Your goal is to help them understand WHY the move was bad and HOW to improve, using simple, human-readable language. Avoid raw engine numbers — instead, explain concepts.

## The Blunder
- **Move {blunder_info.move_number}**: {blunder_info.player_color.capitalize()} played **{blunder_info.move_played}** (a {blunder_info.move_category})
- **Better move**: **{blunder_info.best_move}**
- **Evaluation shift**: From {blunder_info.eval_before:+.1f} to {blunder_info.eval_after:+.1f} (lost {blunder_info.centipawn_loss:.0f} centipawns)
- **Position (FEN)**: {blunder_info.fen_before}

## Historical Context from Similar Positions
{context_text if context_text else "No similar positions found in the database."}

## Instructions
1. Explain in 2-3 paragraphs why the move played was a {blunder_info.move_category}.
2. Describe what the better move ({blunder_info.best_move}) achieves — what tactical or positional advantage it provides.
3. Give one practical takeaway the player can use in future games.
4. Keep the tone encouraging — chess is hard! Reference the historical context if relevant.
5. Do NOT suggest any specific moves beyond what is provided. Do NOT invent piece placements.
6. Keep the total response under 200 words.

## Your Explanation:"""

    return prompt


async def generate_explanation(prompt: str) -> str:
    """
    Generate a human-readable explanation using the Google Gemini API (free tier).

    Falls back to a template-based explanation if the API is unavailable.
    """
    client = get_gemini_client()

    if client is None:
        logger.info("Using fallback explanation (no Gemini API key)")
        return _fallback_explanation(prompt)

    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=genai.types.GenerateContentConfig(
                temperature=0.7,
                top_p=0.9,
                max_output_tokens=300,
            ),
        )

        # Extract the text from the response
        explanation = response.text.strip()

        # Remove any system prompt leakage
        if "## Your Explanation:" in explanation:
            explanation = explanation.split("## Your Explanation:")[-1].strip()

        return explanation

    except Exception as e:
        logger.error(f"Gemini generation failed: {e}")
        return _fallback_explanation(prompt)


def _fallback_explanation(prompt: str) -> str:
    """
    Generate a template-based explanation when the LLM API is unavailable.

    This ensures the prototype always returns a useful response, even
    without an API key — important for demos and testing.
    """
    # Extract blunder details from the prompt using simple parsing
    import re

    move_match = re.search(r"played \*\*(.+?)\*\*", prompt)
    best_match = re.search(r"Better move\*\*: \*\*(.+?)\*\*", prompt)
    category_match = re.search(r"a (\w+)\)", prompt)
    loss_match = re.search(r"lost ([\d.]+) centipawns", prompt)

    move_played = move_match.group(1) if move_match else "the move"
    best_move = best_match.group(1) if best_match else "the engine's suggestion"
    category = category_match.group(1) if category_match else "blunder"
    cp_loss = loss_match.group(1) if loss_match else "significant"

    return (
        f"The move **{move_played}** was a {category} because it significantly weakened your position, "
        f"resulting in approximately {cp_loss} centipawns of evaluation loss. This is roughly equivalent to "
        f"giving your opponent the advantage of an extra piece.\n\n"
        f"The better move, **{best_move}**, would have maintained your position's integrity. "
        f"It likely addresses a tactical threat or improves piece coordination that {move_played} ignored. "
        f"When evaluating moves, always ask yourself: 'Does this move leave any of my pieces undefended? "
        f"Does it create weaknesses my opponent can exploit?'\n\n"
        f"💡 **Takeaway**: Before making a move, use the \"Blunder Check\" mental habit — "
        f"scan for your opponent's checks, captures, and threats. This simple 5-second habit "
        f"can prevent the majority of tactical blunders at the intermediate level."
    )


def is_vector_db_ready() -> bool:
    """Check if the vector database has been populated."""
    try:
        collection = init_vector_db()
        return collection.count() > 0
    except Exception:
        return False


def is_llm_available() -> bool:
    """Check if the Google Gemini API is accessible."""
    client = get_gemini_client()
    return client is not None
