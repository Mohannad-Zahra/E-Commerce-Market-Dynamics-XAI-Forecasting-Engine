import sqlite3
import os

new_db = 'src_integrated/database/wise_purchaser.sqlite'
old_db = 'data/electronics_history.db'

print(f"Connecting to {new_db}...")
conn = sqlite3.connect(new_db)
c = conn.cursor()

# 1. Add columns if they don't exist
print("Adding thumbnail and images columns...")
try:
    c.execute('ALTER TABLE products ADD COLUMN thumbnail TEXT')
except sqlite3.OperationalError:
    print("  thumbnail already exists or error")
try:
    c.execute('ALTER TABLE products ADD COLUMN images TEXT')
except sqlite3.OperationalError:
    print("  images already exists or error")

# 2. Attach legacy DB
print(f"Attaching {old_db}...")
c.execute(f"ATTACH DATABASE '{old_db}' AS legacy")

# 3. Update from legacy
print("Updating metadata from legacy products table...")
c.execute('''
    UPDATE products 
    SET thumbnail = (SELECT thumbnail FROM legacy.products l WHERE l.product_url = products.id),
        images = (SELECT images FROM legacy.products l WHERE l.product_url = products.id)
''')

print(f"Updated {c.rowcount} rows.")
conn.commit()
conn.close()
print("Done.")
