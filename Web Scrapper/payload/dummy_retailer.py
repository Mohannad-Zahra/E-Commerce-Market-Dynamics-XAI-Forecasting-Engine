"""
payload/dummy_retailer.py
─────────────────────────────────────────────────────────────────────
Boilerplate implementations for team members to use when adding
new retailer scrapers. Includes examples for required methods.

HOW TO USE THIS TEMPLATE:
1. Copy this file and rename it for your retailer (e.g. 'twob.py')
2. Add your new file to `config/config.json` inside the "retailers" list.
   Ensure "payload_module" matches your filename (e.g. "payload.twob").
3. DO NOT write your own `time.sleep()`! The framework enforces legal
   rate limiting. Call `self.polite_delay()` in your loops, or use 
   `self.fetch_page("URL")` which handles delays and User-Agent rotation.
4. Your `.run()` method MUST return a list of dictionaries.
5. Every dictionary must contain precisely these 5 mandatory keys:
   - "scrape_timestamp": The exact UTC time the item was scraped.
   - "retailer_id": The unique ID for your retailer (e.g. "2b_egypt").
   - "raw_title": The product title as seen on the site.
   - "raw_current_price": The extracted price string.
   - "product_url": The direct link to the item.
   (Optional: "raw_original_price", "availability_text", "extra_data")
─────────────────────────────────────────────────────────────────────
"""

import logging
from datetime import datetime, timezone
from payload.base import ScraperPayload

logger = logging.getLogger("payload.dummy")

class Scraper(ScraperPayload):
    """
    Template class handling the dummy retailer operations.
    Copy this block for your specific retailer and implement Logic below!
    """

    def run(self) -> list[dict]:
        logger.info("Starting dummy retailer payload execution.")
        records = []
        
        try:
            # TODO: Add your scraping logic (e.g. pagination traversal)
            # Example using the base class helper to make a polite request:
            # response = self.fetch_page("https://dummy.com/products")
            
            # TODO: Extract data using BeautifulSoup, Regex, Playwright, etc...
            self.polite_delay() # Mandatory hardcoded 5-7s delay simulation
            
            # TODO: Add logic to populate the Bronze layer schema properties:
            fake_record = {
                "scrape_timestamp": datetime.now(timezone.utc).isoformat(),
                "retailer_id": "dummy_retailer",
                "raw_title": "Example Boilerplate Laptop 15-inch",
                "raw_current_price": "25000.00 EGP",
                "raw_original_price": "30000.00 EGP",
                "availability_text": "In Stock",
                "product_url": "https://dummy.com/product/1",
                "category": "test",
                "sub_category": "boilerplate",
                "extra_data": {"processor": "Intel i7", "ram": "16GB"}
            }
            
            # Validate output matches required schema layout before adding:
            if self.validate_record(fake_record):
                records.append(fake_record)
                
        except Exception as exc:
            # Let exceptions escalate up to scraper.py to log properly.
            logger.error("Dummy retailer encountered an error: %s", exc)
            raise 

        logger.info("Successfully fetched %d records for dummy.", len(records))
        return records

if __name__ == "__main__":
    # Provides simple standalone testing utility independent of scheduler layer.
    logging.basicConfig(level=logging.INFO)
    scraper = Scraper()
    print("Scraping started.")
    output = scraper.run()
    import json
    print(json.dumps(output, indent=2))
