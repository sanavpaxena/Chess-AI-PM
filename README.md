
# ♟ Grandmaster.AI — Context-Aware Blunder Recovery

> Transforming cryptic engine evaluations into human-readable, actionable chess insights powered by Retrieval-Augmented Generation (RAG).

![Python](https://img.shields.io/badge/Python-3.11+-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green)
![Streamlit](https://img.shields.io/badge/Streamlit-1.39-red)
![ChromaDB](https://img.shields.io/badge/ChromaDB-0.5-orange)
![Gemini](https://img.shields.io/badge/Gemini_API-Free-blue)

## 🎯 What Is This?

**Grandmaster.AI** is an AI Product Management portfolio project that demonstrates:

1. **Product Strategy** — User persona, journey mapping, problem statement
2. **Technical Execution** — Working prototype with RAG pipeline  
3. **AI Evaluation & Guardrails** — Hallucination detection, latency budgets
4. **Analytics & GTM** — Simulated A/B test results, metrics dashboards

## 📁 Project Structure

```
ChessProj/
├── prd/                          # Product Requirements Document
│   ├── index.html                # Interactive PRD page
│   └── styles.css                # Premium dark-mode styling
│
├── app/                          # Python Backend (FastAPI)
│   ├── main.py                   # FastAPI application & endpoints
│   ├── models.py                 # Pydantic request/response schemas
│   ├── chess_service.py          # Chess.com API + Stockfish analysis
│   ├── rag_engine.py             # ChromaDB + HuggingFace RAG pipeline
│   └── guardrails.py             # AI safety & validation checks
│
├── data/
│   ├── annotations/
│   │   └── positions.json        # 50 curated annotated positions
│   └── seed_data.py              # Ingestion script for vector DB
│
├── streamlit_app/                # Frontend UI
│   ├── app.py                    # Interactive chess analysis app
│   └── .streamlit/config.toml    # Dark theme configuration
│
├── dashboard/                    # Analytics Dashboard
│   ├── index.html                # Power BI-style dashboard
│   ├── styles.css                # Dashboard styling
│   └── dashboard.js              # Chart.js visualizations
│
├── requirements.txt              # Python dependencies
├── .env.example                  # Environment variable template
└── README.md                     # This file
```

## 🚀 Quick Start

### Prerequisites

- **Python 3.11+**
- **Stockfish** chess engine: `brew install stockfish` (macOS)
- **Hugging Face account** is NOT required — we use Google Gemini API (free tier)
- **Google Gemini API key** (free — get from https://ai.google.dev/)

### Installation

```bash
# Clone and navigate
cd ChessProj

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your Gemini API key (free from https://ai.google.dev/)
```

### Seed the Vector Database

```bash
python -m data.seed_data
```

### Run the API Server

```bash
uvicorn app.main:app --reload --port 8000
```

API docs available at: http://localhost:8000/docs

### Run the Streamlit Frontend

```bash
cd streamlit_app
streamlit run app.py
```

Opens at: http://localhost:8501

### View Static Pages

- **PRD**: Open `prd/index.html` in your browser
- **Dashboard**: Open `dashboard/index.html` in your browser

## 🔌 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | System health check |
| `POST` | `/analyze` | Analyze a Chess.com user's game |
| `POST` | `/analyze-pgn` | Analyze a raw PGN string |
| `GET` | `/games/{username}` | List user's recent games |
| `GET` | `/board?fen=...` | Render board position as SVG |

### Example Request

```bash
curl -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -d '{"username": "hikaru", "game_index": 0}'
```

## ⚙️ Architecture

```
User → Streamlit → FastAPI → Chess.com API (fetch PGN)
                           → Stockfish (find blunder)
                           → ChromaDB (retrieve similar positions)
                           → Google Gemini (generate explanation)
                           → Guardrails (validate & sanitize)
                           → Response
```

### Why RAG over Fine-Tuning?

| Aspect | RAG ✅ | Fine-Tuning |
|--------|--------|------------|
| Time to Market | Days | Weeks–Months |
| Compute Cost | $0 (free tier) | $100s–$1000s |
| Knowledge Updates | Instant | Requires retraining |
| Hallucination Control | Grounded in context | Black-box |

## 🛡 AI Guardrails

- **Move Legality Validation** — Every move in the AI's response is verified against the actual position
- **Piece Existence Check** — References to pieces are cross-validated with the board state
- **Latency Budget** — 2.5s target enforced per request
- **Response Sanitization** — System prompt leakage detection, length capping, and fallback generation

## 📊 Metrics & Evaluation

- **North Star**: +15% average session length
- **Blunder Detection Accuracy**: 95%+ (vs Stockfish depth 20)
- **Explanation Helpfulness**: 4.2/5.0 target
- **Hallucination Rate**: < 5%
- **Latency Budget**: ≤ 2.5 seconds

## 📝 License

This is a portfolio project. Use freely for learning and reference.
=======
# Chess-AI-PM

