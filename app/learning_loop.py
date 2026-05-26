import sqlite3
import os
import logging
from typing import Optional, List
from datetime import datetime

logger = logging.getLogger(__name__)

DB_PATH = os.getenv("LEARNING_LOOP_DB_PATH", "./data/learning_loop.db")

def init_db():
    """Initialize the SQLite database for the learning loop."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_patterns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            theme TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()
    logger.info("Learning loop database initialized.")

def store_blunder_pattern(username: str, theme: str):
    """Store a blunder pattern for a user."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO user_patterns (username, theme) VALUES (?, ?)',
            (username.lower(), theme)
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Failed to store learning loop pattern: {e}")

def get_user_patterns(username: str) -> List[dict]:
    """Retrieve historical blunder patterns for a user."""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            'SELECT theme, timestamp FROM user_patterns WHERE username = ? ORDER BY timestamp DESC',
            (username.lower(),)
        )
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"Failed to fetch learning loop patterns: {e}")
        return []
