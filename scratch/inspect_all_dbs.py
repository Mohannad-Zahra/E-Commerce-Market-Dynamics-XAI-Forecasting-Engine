import sqlite3
import os

db_paths = [
    'data/electronics_history.db',
    'backend/electronics_history.db',
    'src_integrated/database/wise_purchaser.sqlite'
]

for path in db_paths:
    print(f"\nChecking: {path}")
    if not os.path.exists(path):
        print("  FILE NOT FOUND")
        continue
    
    size = os.path.getsize(path)
    print(f"  Size: {size:,} bytes")
    
    if size == 0:
        print("  EMPTY FILE")
        continue
        
    try:
        conn = sqlite3.connect(path)
        c = conn.cursor()
        c.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [t[0] for t in c.fetchall()]
        print(f"  Tables: {tables}")
        conn.close()
    except Exception as e:
        print(f"  ERROR: {e}")
