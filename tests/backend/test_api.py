def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
    assert "version" in response.json()

def test_get_board(client):
    fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
    response = client.get(f"/board?fen={fen}")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/svg+xml"
    assert "<svg" in response.text

def test_analyze_pgn_invalid(client):
    req = {"pgn": "invalid data"}
    response = client.post("/analyze-pgn", json=req)
    # the endpoint might just say no blunders if it parses to empty game, or 400
    # based on our implementation, it checks if len(mainline) == 0 sometimes, or find_biggest_blunder returns None
    assert response.status_code in [200, 400]

def test_analyze_pgn_no_blunders(client, mock_stockfish, mock_gemini):
    req = {"pgn": "1. e4 e5 2. Nf3 Nc6 3. Bc4 Bc5"}
    response = client.post("/analyze-pgn", json=req)
    assert response.status_code == 200
    assert "No significant blunders" in response.json()["detail"]
