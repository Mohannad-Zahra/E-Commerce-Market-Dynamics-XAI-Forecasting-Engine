from database import SessionLocal, engine, Base
import models
from datetime import datetime

# Initialize the database schema
Base.metadata.create_all(bind=engine)

def seed_db():
    db = SessionLocal()
    
    if db.query(models.Product).first():
        print("Database already seeded.")
        return

    products = [
        {
            "scrape_timestamp": datetime.utcnow().isoformat() + "Z",
            "retailer_id": "2b_egypt",
            "raw_title": "Lenovo Legion 5 - Ryzen 7 5800H - 16GB RAM - 512GB SSD - RTX 3050Ti",
            "raw_current_price": 38500.0,
            "raw_original_price": 42000.0,
            "availability_text": "In Stock",
            "product_url": "https://2b.com.eg/en/lenovo-legion",
            "category": "laptops",
            "sub_category": "gaming",
            "brand": "lenovo",
            "thumbnail": "https://p3-ofp.static.pub/ShareResource/na/products/legion/400x400/lenovo-legion-5-gen-6-15-amd-04.png",
        },
        {
            "scrape_timestamp": datetime.utcnow().isoformat() + "Z",
            "retailer_id": "sigma-computer",
            "raw_title": "Asus TUF Gaming F15 - Core i5 11400H - 8GB RAM - 512GB SSD - GTX 1650",
            "raw_current_price": 27500.0,
            "raw_original_price": 29000.0,
            "availability_text": "In Stock",
            "product_url": "https://www.sigma-computer.com/asus-tuf",
            "category": "laptops",
            "sub_category": "gaming",
            "brand": "asus",
            "thumbnail": "https://dlcdnwebimgs.asus.com/gain/9B9F6BC6-63FB-41B0-A2BC-437E5528811A/w250",
        },
        {
            "scrape_timestamp": datetime.utcnow().isoformat() + "Z",
            "retailer_id": "dream2000",
            "raw_title": "Apple iPhone 14 Pro Max - 256GB - Deep Purple",
            "raw_current_price": 62000.0,
            "raw_original_price": 65000.0,
            "availability_text": "In Stock",
            "product_url": "https://dream2000.com.eg/iphone-14-pro-max",
            "category": "mobiles",
            "sub_category": "smartphones",
            "brand": "apple",
            "thumbnail": "https://www.apple.com/v/iphone-14-pro/a/images/overview/hero/hero_deep_purple__bsu1e9u1ujs2_large.jpg",
        },
        {
            "scrape_timestamp": datetime.utcnow().isoformat() + "Z",
            "retailer_id": "btech",
            "raw_title": "Samsung Galaxy S23 Ultra - 256GB - Phantom Black",
            "raw_current_price": 49000.0,
            "raw_original_price": 52000.0,
            "availability_text": "In Stock",
            "product_url": "https://btech.com/samsung-s23-ultra",
            "category": "mobiles",
            "sub_category": "smartphones",
            "brand": "samsung",
            "thumbnail": "https://images.samsung.com/is/image/samsung/p6pim/eg/sm-s918bzkgmea/gallery/eg-galaxy-s23-s918-sm-s918bzkgmea-534886905?$650_519_PNG$",
        },
        {
            "scrape_timestamp": datetime.utcnow().isoformat() + "Z",
            "retailer_id": "2b_egypt",
            "raw_title": "Sony PlayStation 5 Console",
            "raw_current_price": 28500.0,
            "raw_original_price": 31000.0,
            "availability_text": "Out of Stock",
            "product_url": "https://2b.com.eg/en/ps5",
            "category": "playstation",
            "sub_category": "consoles",
            "brand": "sony",
            "thumbnail": "https://gmedia.playstation.com/is/image/SIEPDC/ps5-product-thumbnail-01-en-14sep21?$facebook$",
        }
    ]

    for p_data in products:
        db_product = models.Product(**p_data)
        db.add(db_product)
    
    db.commit()
    print(f"Seeded {len(products)} products into the database.")
    db.close()

if __name__ == "__main__":
    seed_db()
