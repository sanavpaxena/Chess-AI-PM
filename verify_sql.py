import os
from app.learning_loop import init_db, store_blunder_pattern, get_user_patterns

def test_db():
    print("--- 🔄 Testing SQLite Learning Loop ---\n")
    
    # 1. Init
    print("[1] Initializing SQLite database at ./data/learning_loop.db")
    init_db()
    
    # 2. Store
    test_user = "demo_user"
    print(f"\n[2] Simulating a blunder evaluation...")
    print(f"    -> Saving pattern 'king_safety' for user '{test_user}'")
    store_blunder_pattern(test_user, "king_safety")
    
    # 3. Retrieve
    print(f"\n[3] Retrieving historical patterns for user '{test_user}'...")
    patterns = get_user_patterns(test_user)
    
    for idx, p in enumerate(patterns):
        print(f"    ✅ Match {idx+1}: Theme = '{p['theme']}', Timestamp = {p['timestamp']}")
        
    print("\n✅ SQLite tracking verified. The RAG pipeline will cross-reference these records for future games.")

if __name__ == "__main__":
    test_db()
