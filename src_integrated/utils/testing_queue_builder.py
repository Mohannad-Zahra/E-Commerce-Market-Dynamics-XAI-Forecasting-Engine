import os
import json
import sqlite3
import pandas as pd
from pathlib import Path

DB_PATH = 'src_integrated/database/testing_queue.db'
DATA_DIR = 'oldData_need the scrape_time to update for it to work'

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS raw_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            payload TEXT NOT NULL
        )
    ''')
    # Clear existing data for fresh build
    cursor.execute('DELETE FROM raw_queue')
    conn.commit()
    return conn

def load_data(conn):
    cursor = conn.cursor()
    count = 0
    
    for filename in os.listdir(DATA_DIR):
        filepath = os.path.join(DATA_DIR, filename)
        if filename.endswith('.json'):
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    if not content:
                        continue
                    
                    # Try to parse as a single JSON array or object
                    try:
                        data = json.loads(content)
                        if isinstance(data, list):
                            for item in data:
                                cursor.execute('INSERT INTO raw_queue (payload) VALUES (?)', (json.dumps(item),))
                                count += 1
                        else:
                            cursor.execute('INSERT INTO raw_queue (payload) VALUES (?)', (json.dumps(data),))
                            count += 1
                    except json.JSONDecodeError:
                        # Fallback to JSON lines if it fails
                        f.seek(0)
                        for line in f:
                            line = line.strip()
                            if not line:
                                continue
                            try:
                                item = json.loads(line)
                                cursor.execute('INSERT INTO raw_queue (payload) VALUES (?)', (json.dumps(item),))
                                count += 1
                            except json.JSONDecodeError:
                                pass
            except Exception as e:
                print(f"Error processing JSON {filename}: {e}")
        elif filename.endswith('.csv'):
            try:
                df = pd.read_csv(filepath)
                # Convert each row to JSON
                for _, row in df.iterrows():
                    data = row.dropna().to_dict()
                    cursor.execute('INSERT INTO raw_queue (payload) VALUES (?)', (json.dumps(data),))
                    count += 1
            except Exception as e:
                print(f"Error reading CSV {filename}: {e}")
                
    conn.commit()
    print(f"Loaded {count} rows into {DB_PATH}")

if __name__ == '__main__':
    print("Building testing queue...")
    conn = init_db()
    load_data(conn)
    conn.close()
    print("Done.")
