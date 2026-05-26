import pytest
from app.rag_engine import _build_query_from_blunder
from app.models import BlunderInfo

def test_build_query_from_blunder():
    blunder = BlunderInfo(
        move_number=10,
        move_played="Nf6",
        move_played_uci="g8f6",
        best_move="Bd7",
        best_move_uci="c8d7",
        eval_before=1.5,
        eval_after=-2.0,
        centipawn_loss=350,
        fen_before="start_fen",
        fen_after="end_fen",
        player_color="white",
        move_category="blunder"
    )
    
    features = {
        "themes": ["middlegame", "material_imbalance"],
        "is_check": True
    }
    
    query = _build_query_from_blunder(blunder, features)
    
    assert "blunder" in query
    assert "middlegame" in query
    assert "material imbalance" in query
    assert "major blunder" in query
    assert "check" in query

@pytest.mark.asyncio
async def test_generate_explanation_mock(mock_gemini):
    from app.rag_engine import generate_explanation
    
    prompt = "Explain this blunder."
    result = await generate_explanation(prompt)
    
    assert result == "This is a mock AI explanation."
    mock_gemini.models.generate_content.assert_called_once()
