import os
import sys
from sqlalchemy import text

# Add paths
sys.path.append(os.getcwd())
sys.path.append(os.path.join(os.getcwd(), 'backend'))
sys.path.append(os.path.join(os.getcwd(), 'src_integrated'))

from backend.main import get_cached_data
from src_integrated.database.db import SessionLocal

def test_prices():
    session = SessionLocal()
    try:
        print("Fetching cached products...")
        products, categories, stats = get_cached_data(session)
        
        print(f"\nStats: {stats}")
        print("\nSample Products:")
        for p in products[:10]:
            print(f" - {p['title'][:60]}: {p['price']} EGP (Base: {p.get('originalPrice')})")
            
    finally:
        session.close()

if __name__ == "__main__":
    test_prices()
