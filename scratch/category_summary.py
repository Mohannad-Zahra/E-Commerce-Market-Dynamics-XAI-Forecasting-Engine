import os
import sys
from sqlalchemy import text

# Add paths
sys.path.append(os.getcwd())
sys.path.append(os.path.join(os.getcwd(), 'backend'))
sys.path.append(os.path.join(os.getcwd(), 'src_integrated'))

from backend.main import get_cached_data
from src_integrated.database.db import SessionLocal

def check_category_summary():
    session = SessionLocal()
    try:
        products, categories, _ = get_cached_data(session)
        print(f"TOTAL PRODUCTS: {len(products)}")
        
        for cat in sorted(categories):
            cat_products = [p for p in products if p['category'] == cat]
            print(f"CATEGORY: {cat:20} | COUNT: {len(cat_products)}")
            # Sample 3 titles to verify logic
            for p in cat_products[:3]:
                title = p['title'].encode('ascii', 'ignore').decode('ascii')
                print(f"  -> {title[:60]}")
                
    finally:
        session.close()

if __name__ == "__main__":
    check_category_summary()
