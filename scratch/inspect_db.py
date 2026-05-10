import sqlite3
import pandas as pd

db_path = r"e:\MY PROJECT\Machine Learning\E-Commerce-Market-Dynamics-XAI-Forecasting-Engine\data\electronics_history.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = cursor.fetchall()
print("Tables:", tables)

for table_name in [t[0] for t in tables]:
    print(f"\nSchema for {table_name}:")
    cursor.execute(f"PRAGMA table_info({table_name});")
    print(cursor.fetchall())

conn.close()
