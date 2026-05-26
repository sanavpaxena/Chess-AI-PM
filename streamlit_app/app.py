"""
Grandmaster.AI — Streamlit Frontend

Interactive chess analysis UI with:
- Chess.com username input
- Game selection
- Interactive chessboard (SVG)
- AI-powered blunder explanation panel
- Latency & guardrail monitoring
"""

import sys
import os
import time

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import chess
import chess.svg
import asyncio

from app.chess_service import (
    fetch_user_games,
    parse_pgn,
    extract_game_info,
    find_biggest_blunder,
    get_board_features,
    get_board_svg,
    STOCKFISH_PATH,
)
from app.rag_engine import (
    retrieve_similar_positions,
    build_prompt,
    generate_explanation,
    init_vector_db,
    ingest_annotations,
)
from app.guardrails import sanitize_explanation, enforce_latency_budget

# ── Page Configuration ─────────────────────────────────────────────────
st.set_page_config(
    page_title="Grandmaster.AI — Blunder Recovery",
    page_icon="♟",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ─────────────────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

    .stApp {
        font-family: 'Inter', sans-serif;
    }

    /* Header styling */
    .main-header {
        text-align: center;
        padding: 20px 0 30px;
    }

    .main-header h1 {
        font-size: 2.5rem;
        font-weight: 800;
        background: linear-gradient(135deg, #a855f7, #c084fc, #e879f9);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        letter-spacing: -1.5px;
        margin-bottom: 8px;
    }

    .main-header p {
        color: #a0a0b8;
        font-size: 1.05rem;
    }

    /* Cards */
    .analysis-card {
        background: rgba(26, 26, 46, 0.6);
        border: 1px solid rgba(255, 255, 255, 0.06);
        border-radius: 16px;
        padding: 24px;
        margin: 12px 0;
        backdrop-filter: blur(10px);
    }

    .blunder-badge {
        display: inline-block;
        padding: 4px 14px;
        border-radius: 100px;
        font-size: 12px;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 1px;
    }

    .blunder-badge.blunder {
        background: rgba(239, 68, 68, 0.15);
        color: #ef4444;
        border: 1px solid rgba(239, 68, 68, 0.3);
    }

    .blunder-badge.mistake {
        background: rgba(245, 158, 11, 0.15);
        color: #f59e0b;
        border: 1px solid rgba(245, 158, 11, 0.3);
    }

    .blunder-badge.inaccuracy {
        background: rgba(59, 130, 246, 0.15);
        color: #3b82f6;
        border: 1px solid rgba(59, 130, 246, 0.3);
    }

    /* Eval bar */
    .eval-container {
        background: #1a1a2e;
        border-radius: 8px;
        padding: 16px;
        margin: 12px 0;
    }

    .eval-bar-outer {
        background: #2a2a3e;
        border-radius: 4px;
        height: 24px;
        position: relative;
        overflow: hidden;
    }

    .eval-bar-inner {
        height: 100%;
        border-radius: 4px;
        transition: width 0.5s ease;
    }

    /* Latency indicator */
    .latency-badge {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 6px 14px;
        border-radius: 100px;
        font-size: 13px;
        font-weight: 500;
    }

    .latency-badge.good {
        background: rgba(16, 185, 129, 0.1);
        color: #10b981;
        border: 1px solid rgba(16, 185, 129, 0.3);
    }

    .latency-badge.slow {
        background: rgba(239, 68, 68, 0.1);
        color: #ef4444;
        border: 1px solid rgba(239, 68, 68, 0.3);
    }

    /* Source citation */
    .source-cite {
        background: rgba(124, 58, 237, 0.08);
        border-left: 3px solid #7c3aed;
        padding: 12px 16px;
        border-radius: 0 8px 8px 0;
        margin: 8px 0;
        font-size: 13px;
    }

    /* Sidebar improvements */
    .sidebar-section {
        padding: 16px;
        background: rgba(26, 26, 46, 0.4);
        border-radius: 12px;
        margin-bottom: 16px;
    }

    /* Divider */
    .custom-divider {
        border: none;
        height: 1px;
        background: linear-gradient(90deg, transparent, rgba(255,255,255,0.06), transparent);
        margin: 24px 0;
    }
</style>
""", unsafe_allow_html=True)


# ── Helper Functions ───────────────────────────────────────────────────
def run_async(coro):
    """Run an async function in a synchronous context."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def eval_to_bar_width(eval_value: float) -> float:
    """Convert engine evaluation to a bar width percentage (50% = equal)."""
    # Clamp to -10 to +10 range, then map to 0-100%
    clamped = max(-10, min(10, eval_value))
    return 50 + (clamped * 5)  # Each pawn = 5% deviation from center


def render_board_svg(fen: str, last_move_uci: str = None, size: int = 380):
    """Render chess board as SVG."""
    board = chess.Board(fen)
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
            "margin": "#0a0a0f",
            "coord": "#a0a0b8",
        },
    )
    return svg


# ── Initialize Vector DB ──────────────────────────────────────────────
@st.cache_resource
def setup_vector_db():
    """Initialize and populate the vector database (cached)."""
    collection = init_vector_db()
    if collection.count() == 0:
        data_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "data", "annotations"
        )
        ingest_annotations(data_dir)
    return collection


# ── Main App ──────────────────────────────────────────────────────────
def main():
    # Initialize vector DB
    setup_vector_db()

    # ── Header ─────────────────────────────────────────────────────
    st.markdown("""
    <div class="main-header">
        <h1>♟ Grandmaster.AI</h1>
        <p>Context-Aware Blunder Recovery — Powered by RAG</p>
    </div>
    """, unsafe_allow_html=True)

    # ── Sidebar ────────────────────────────────────────────────────
    with st.sidebar:
        st.markdown("### ⚙️ Configuration")

        st.markdown('<div class="sidebar-section">', unsafe_allow_html=True)
        username = st.text_input(
            "Chess.com Username",
            value="hikaru",
            placeholder="Enter a Chess.com username",
            help="Enter any Chess.com username to analyze their recent games"
        )

        analyze_mode = st.radio(
            "Analysis Mode",
            options=["Chess.com User", "Paste PGN"],
            horizontal=True,
        )
        st.markdown('</div>', unsafe_allow_html=True)

        # Stockfish status
        st.markdown('<div class="sidebar-section">', unsafe_allow_html=True)
        st.markdown("### 🔧 System Status")
        stockfish_ok = os.path.exists(STOCKFISH_PATH)
        st.markdown(f"{'✅' if stockfish_ok else '❌'} Stockfish: `{STOCKFISH_PATH}`")

        collection = setup_vector_db()
        st.markdown(f"✅ Vector DB: {collection.count()} documents")

        gemini_key = os.getenv("GEMINI_API_KEY", "")
        has_key = gemini_key and not gemini_key.startswith("AIza_xxx")
        st.markdown(f"{'✅' if has_key else '⚠️'} Gemini API: {'Connected' if has_key else 'Using fallback'}")
        st.markdown('</div>', unsafe_allow_html=True)

        # Info
        st.markdown('<div class="sidebar-section">', unsafe_allow_html=True)
        st.markdown("### 📋 About")
        st.markdown(
            "Grandmaster.AI uses **Retrieval-Augmented Generation** "
            "to transform cryptic engine evaluations into human-readable "
            "chess insights."
        )
        st.markdown(
            "🔗 [View PRD](../prd/index.html) · "
            "[View Dashboard](../dashboard/index.html)"
        )
        st.markdown('</div>', unsafe_allow_html=True)

    # ── Main Content ───────────────────────────────────────────────
    if analyze_mode == "Chess.com User":
        render_chess_com_mode(username)
    else:
        render_pgn_mode()


def render_chess_com_mode(username: str):
    """Render the Chess.com analysis mode."""

    col_left, col_right = st.columns([1, 1], gap="large")

    with col_left:
        st.markdown("### 🎮 Game Selection")

        if st.button("🔍 Fetch Recent Games", use_container_width=True, type="primary"):
            with st.spinner(f"Fetching games for **{username}**..."):
                try:
                    games = run_async(fetch_user_games(username, max_games=10))
                    st.session_state["games"] = games
                    st.session_state["username"] = username
                    st.success(f"Found {len(games)} recent games!")
                except Exception as e:
                    st.error(f"Error: {str(e)}")
                    return

        # Game selector
        if "games" in st.session_state and st.session_state.get("username") == username:
            games = st.session_state["games"]

            game_options = []
            for i, g in enumerate(games):
                pgn = parse_pgn(g.get("pgn", ""))
                if pgn:
                    info = extract_game_info(pgn)
                    label = f"Game {i+1}: {info.white} vs {info.black} ({info.result})"
                    game_options.append(label)

            if game_options:
                selected_idx = st.selectbox(
                    "Select a game to analyze",
                    range(len(game_options)),
                    format_func=lambda i: game_options[i],
                )

                if st.button("⚡ Analyze for Blunders", use_container_width=True):
                    analyze_game_flow(games[selected_idx], username, col_right)

    # Show results if already analyzed
    if "analysis_result" in st.session_state:
        display_results(col_left, col_right)


def render_pgn_mode():
    """Render the PGN paste mode."""
    st.markdown("### 📝 Paste a PGN")

    pgn_input = st.text_area(
        "PGN String",
        height=200,
        placeholder='[Event "Casual Game"]\n[White "Player1"]\n[Black "Player2"]\n\n1. e4 e5 2. Nf3 Nc6 ...',
    )

    player_color = st.radio("Analyze for", ["Both", "White", "Black"], horizontal=True)
    color_filter = None if player_color == "Both" else player_color.lower()

    if st.button("⚡ Analyze PGN", use_container_width=True, type="primary") and pgn_input:
        game = parse_pgn(pgn_input)
        if not game:
            st.error("Failed to parse PGN. Please check the format.")
            return

        game_data = {"pgn": pgn_input}
        col_left, col_right = st.columns([1, 1], gap="large")
        analyze_game_flow(game_data, "PGN", col_right, player_color=color_filter)

        if "analysis_result" in st.session_state:
            display_results(col_left, col_right)


def analyze_game_flow(game_data: dict, username: str, col_right, player_color=None):
    """Run the full analysis pipeline."""
    start_time = time.time()

    with st.spinner("🔍 Analyzing game with Stockfish..."):
        try:
            pgn_str = game_data.get("pgn", "")
            game = parse_pgn(pgn_str)
            if not game:
                st.error("Failed to parse game.")
                return

            game_info = extract_game_info(game, url=game_data.get("url", ""))

            # Determine player color
            if player_color is None and username != "PGN":
                if username.lower() == game_info.white.lower():
                    player_color = "white"
                elif username.lower() == game_info.black.lower():
                    player_color = "black"

            # Find blunder
            blunder = find_biggest_blunder(game, player_color=player_color)
            if blunder is None:
                blunder = find_biggest_blunder(game)

            if blunder is None:
                st.success("🎉 No significant blunders found! Well played!")
                return

            # RAG pipeline
            board_features = get_board_features(blunder.fen_before)
            similar_contexts = retrieve_similar_positions(blunder, board_features, k=3)
            prompt = build_prompt(blunder, similar_contexts)
            raw_explanation = run_async(generate_explanation(prompt))
            cleaned_explanation, guardrail_flags = sanitize_explanation(
                raw_explanation, blunder.fen_before
            )

            elapsed_ms, within_budget = enforce_latency_budget(start_time, 2500)

            # Store results
            st.session_state["analysis_result"] = {
                "game_info": game_info,
                "blunder": blunder,
                "explanation": cleaned_explanation,
                "similar_contexts": similar_contexts,
                "latency_ms": round(elapsed_ms, 1),
                "within_budget": within_budget,
                "guardrail_flags": guardrail_flags,
            }

        except RuntimeError as e:
            st.error(f"⚠️ {str(e)}")
        except Exception as e:
            st.error(f"Analysis failed: {str(e)}")


def display_results(col_left, col_right):
    """Display analysis results."""
    result = st.session_state["analysis_result"]
    game_info = result["game_info"]
    blunder = result["blunder"]
    explanation = result["explanation"]
    contexts = result["similar_contexts"]
    latency_ms = result["latency_ms"]
    within_budget = result["within_budget"]
    flags = result["guardrail_flags"]

    with col_left:
        st.markdown("---")

        # Game info
        st.markdown(f"""
        <div class="analysis-card">
            <strong>{game_info.white}</strong> ({game_info.white_elo or '?'}) vs
            <strong>{game_info.black}</strong> ({game_info.black_elo or '?'})<br>
            <span style="color: #a0a0b8;">Result: {game_info.result} · {game_info.total_moves} moves</span>
        </div>
        """, unsafe_allow_html=True)

        # Chessboard
        st.markdown("#### 📍 Blunder Position")
        svg = render_board_svg(blunder.fen_before, blunder.move_played_uci)
        st.markdown(f'<div style="text-align: center;">{svg}</div>', unsafe_allow_html=True)

        st.markdown(f"""
        <div style="text-align: center; margin-top: 8px; color: #a0a0b8; font-size: 13px;">
            Move {blunder.move_number}: {blunder.player_color.capitalize()} played <strong style="color: #ef4444;">{blunder.move_played}</strong>
        </div>
        """, unsafe_allow_html=True)

    with col_right:
        st.markdown("---")

        # Blunder details
        badge_class = blunder.move_category
        st.markdown(f"""
        <div class="analysis-card">
            <span class="blunder-badge {badge_class}">{blunder.move_category}</span>
            <h3 style="margin: 16px 0 8px; font-size: 20px;">Move {blunder.move_number}: {blunder.move_played}</h3>
            <p style="color: #a0a0b8; margin-bottom: 16px;">
                {blunder.player_color.capitalize()} played <strong style="color: #ef4444;">{blunder.move_played}</strong>
                instead of <strong style="color: #10b981;">{blunder.best_move}</strong>
            </p>
        </div>
        """, unsafe_allow_html=True)

        # Eval bar
        before_width = eval_to_bar_width(blunder.eval_before)
        after_width = eval_to_bar_width(blunder.eval_after)
        bar_color = "#10b981" if blunder.eval_after > 0 else "#ef4444"

        st.markdown(f"""
        <div class="eval-container">
            <div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
                <span style="font-size: 13px; color: #a0a0b8;">Before: <strong style="color: #f0f0f5;">{blunder.eval_before:+.1f}</strong></span>
                <span style="font-size: 13px; color: #a0a0b8;">After: <strong style="color: {bar_color};">{blunder.eval_after:+.1f}</strong></span>
            </div>
            <div class="eval-bar-outer">
                <div class="eval-bar-inner" style="width: {after_width}%; background: linear-gradient(90deg, #ef4444, {bar_color});"></div>
            </div>
            <div style="text-align: center; margin-top: 8px;">
                <span style="font-size: 14px; color: #ef4444; font-weight: 600;">−{blunder.centipawn_loss:.0f} centipawns</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # AI Explanation
        st.markdown("#### 🤖 AI Explanation")
        st.markdown(f"""
        <div class="analysis-card" style="border-left: 3px solid #7c3aed;">
            {explanation}
        </div>
        """, unsafe_allow_html=True)

        # Learning Loop Tracker
        learning_loop_feedback = result.get("learning_loop_feedback")
        if learning_loop_feedback:
            st.markdown("#### 🔄 Learning Loop Tracker")
            is_success = "avoided" in learning_loop_feedback.lower() or "track this pattern" in learning_loop_feedback.lower()
            icon = "✅" if is_success else "⚠️"
            color = "#10b981" if is_success else "#f59e0b"
            st.markdown(f"""
            <div class="analysis-card" style="border-left: 3px solid {color};">
                <strong>{icon} {learning_loop_feedback}</strong>
            </div>
            """, unsafe_allow_html=True)

        # Retrieved contexts
        if contexts:
            st.markdown("#### 📚 Historical References")
            for ctx in contexts:
                st.markdown(f"""
                <div class="source-cite">
                    <strong>{ctx.source}</strong> — <em>{ctx.theme}</em>
                    <span style="float: right; opacity: 0.5;">Similarity: {ctx.similarity_score:.1%}</span>
                </div>
                """, unsafe_allow_html=True)

        # Latency & Guardrails
        st.markdown("---")
        latency_class = "good" if within_budget else "slow"
        latency_icon = "✅" if within_budget else "⚠️"

        st.markdown(f"""
        <div style="display: flex; gap: 12px; flex-wrap: wrap;">
            <span class="latency-badge {latency_class}">
                {latency_icon} {latency_ms:.0f}ms / 2500ms budget
            </span>
        </div>
        """, unsafe_allow_html=True)

        if flags:
            with st.expander("🛡 Guardrail Flags", expanded=False):
                for flag in flags:
                    st.markdown(f"- {flag}")


# ── Run ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    main()
