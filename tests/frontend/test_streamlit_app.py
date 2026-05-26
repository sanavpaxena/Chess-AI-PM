import pytest
from streamlit.testing.v1 import AppTest
import os

def test_app_loads():
    """Test that the Streamlit app loads without exceptions and displays the title."""
    os.environ["CHROMA_DB_PATH"] = "./tests/data/chromadb"
    
    # Run the streamlit app
    at = AppTest.from_file("streamlit_app/app.py").run(timeout=10)
    
    # Assert no exceptions during run
    assert not at.exception
    
    # Assert title or markdown header exists
    assert any("Grandmaster.AI" in m.value for m in at.markdown)
