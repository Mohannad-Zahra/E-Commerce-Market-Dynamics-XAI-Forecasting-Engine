import os
import sys
from sqlalchemy import text

# Add paths
sys.path.append(os.getcwd())
sys.path.append(os.path.join(os.getcwd(), 'backend'))
sys.path.append(os.path.join(os.getcwd(), 'src_integrated'))

from backend.main import get_cached_data
from src_integrated.database.db import SessionLocal

def check_category_mapping():
    session = SessionLocal()
    try:
        products, categories, _ = get_cached_data(session)
        
        print(f"Total Products: {len(products)}")
        print(f"Categories found: {categories}")
        
        for cat in categories:
            cat_products = [p for p in products if p['category'] == cat]
            print(f"\n--- Category: {cat.upper()} ({len(cat_products)} products) ---")
            for p in cat_products[:15]:
                try:
                    title = p['title'].encode('ascii', 'ignore').decode('ascii')
                    print(f"  [{p['price']:,.0f} EGP] - {title[:80]}...")
                except Exception:
                    pass
                
    finally:
        session.close()

if __name__ == "__main__":
    check_category_mapping()
