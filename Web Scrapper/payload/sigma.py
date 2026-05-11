"""
payload/sigma.py
─────────────────────────────────────────────────────────────────────
Playwright-based scraper payload for Sigma Computer.
─────────────────────────────────────────────────────────────────────
"""
import asyncio
import json
import logging
import random
import os
from datetime import datetime, timezone
from urllib.parse import urlparse

from playwright.async_api import async_playwright
from payload.base import ScraperPayload

logger = logging.getLogger("payload.sigma")

CAT_MAP = {
    "9f5039de-5c80-46f3-9fe4-6e8f94189b8c": ("Laptops", "Laptops"),
    "9f5039af-f5d2-4396-9ba2-8ac40277c373": ("Hardware", "Hardware Components"),
    "9f5039ed-8dd4-4a9b-a8ce-caf20ed29436": ("Storage", "Storage"),
    "9f503a01-79d7-4a25-b3f3-63b0fd5b3094": ("Monitors", "Monitors"),
}

class Scraper(ScraperPayload):
    """
    Scraper implementation for sigma-computer.com using async_playwright.
    """

    def _parse_category(self, url: str) -> tuple[str, str | None]:
        """
        Extract category and sub_category from a Sigma target URL.
        """
        # URL format: .../category/UUID
        path = urlparse(url).path
        segments = [s for s in path.strip("/").split("/") if s]
        
        uuid = segments[-1] if segments else "unknown"
        return CAT_MAP.get(uuid, ("unknown", None))

    def run(self) -> list[dict]:
        logger.info("Starting Sigma Computer payload execution.")
        
        # Load config to get target URLs
        config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'config.json')
        target_urls = []
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                for retailer in config.get("retailers", []):
                    if retailer.get("retailer_id") == "sigma-computer":
                        target_urls = retailer.get("target_urls", [])
                        break
        except Exception as e:
            logger.error("Failed to load target_urls from config.json: %s", e)
            
        if not target_urls:
            logger.warning("No target URLs found for sigma-computer.")
            return []
            
        return asyncio.run(self.async_run(target_urls))

    async def polite_delay_async(self):
        """
        Async equivalent of the hardware 5.0-7.0s compliance delay.
        """
        delay = random.uniform(5.0, 7.0)
        logger.debug("Applying polite delay of %.2f seconds.", delay)
        await asyncio.sleep(delay)

    async def async_run(self, target_urls: list[str]) -> list[dict]:
        records = []
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
                viewport={'width': 1920, 'height': 1080}
            )
            
            for url in target_urls:
                try:
                    category_records = await self.scrape_category(context, url)
                    records.extend(category_records)
                except Exception as e:
                    logger.error("Error scraping category %s: %s", url, e)
                    
            await browser.close()
            
        logger.info("Successfully fetched %d records for Sigma Computer.", len(records))
        return records

    async def scrape_category(self, context, start_url: str) -> list[dict]:
        page = await context.new_page()
        records = []
        category, sub_category = self._parse_category(start_url)
        page_num = 1

        try:
            logger.info("Scraping Sigma category %s, page %d: %s", category, page_num, start_url)
            await self.polite_delay_async()
            await page.goto(start_url, wait_until="domcontentloaded", timeout=60000)

            while True:
                # ── Scroll to handle lazy loading ──
                # Sigma uses Chakra UI and products often load as you scroll
                prev_height = 0
                for _ in range(10):
                    await page.evaluate("window.scrollBy(0, 800)")
                    await page.wait_for_timeout(500)
                    curr_height = await page.evaluate("document.body.scrollHeight")
                    if curr_height == prev_height:
                        break
                    prev_height = curr_height

                # ── Extract product cards ──
                # Based on research, products are in a grid. 
                # Let's find elements that look like product cards.
                # Common pattern in their markup: grids containing links with tooltips
                product_cards = await page.locator("div.css-1f9f2sk, div.css-0").all() # Refined based on visual research
                # Fallback: if those specific classes fail, look for the title link's parent
                if not product_cards:
                     product_cards = await page.locator("a.chakra-tooltip__trigger.line-clamp-2").all()
                     # If we find links, we take their parents/ancestors as cards
                     # But for now, let's target the links directly if card selector is tricky.

                logger.info("Page %d: detected %d potential product elements.", page_num, len(product_cards))

                # Since card selector is dynamic (Chakra UI), we'll find the title links and traverse upwards if needed, 
                # or just use the title links to find other info.
                title_links = await page.locator("a.chakra-tooltip__trigger.line-clamp-2").all()
                
                for link in title_links:
                    try:
                        raw_title = (await link.inner_text()).strip()
                        product_url = await link.get_attribute("href")
                        if product_url and not product_url.startswith("http"):
                            product_url = f"https://www.sigma-computer.com{product_url}"

                        # Traverse to find price and availability relative to the link
                        # The price is usually in the same container.
                        # We'll use a locator relative to the card/link.
                        card = link.locator("xpath=ancestor::div[contains(@class, 'css-')]").first
                        
                        # Price extraction: looks for "EGP"
                        price_elements = await card.locator("text=/.*EGP.*/").all()
                        raw_current_price = ""
                        raw_original_price = None
                        
                        if len(price_elements) >= 1:
                            raw_current_price = (await price_elements[0].inner_text()).strip()
                        if len(price_elements) >= 2:
                            raw_original_price = (await price_elements[1].inner_text()).strip()

                        # Availability
                        cart_btn = card.locator("button:has-text('Add to cart')")
                        if await cart_btn.count() > 0:
                            availability_text = "In Stock"
                        else:
                            availability_text = "Out of Stock"

                        record = {
                            "scrape_timestamp": datetime.now(timezone.utc).isoformat(),
                            "retailer_id": "sigma-computer",
                            "raw_title": raw_title,
                            "raw_current_price": raw_current_price,
                            "raw_original_price": raw_original_price,
                            "availability_text": availability_text,
                            "product_url": product_url,
                            "category": category,
                            "sub_category": sub_category,
                        }

                        if self.validate_record(record):
                            records.append(record)
                    except Exception as e:
                        logger.warning("Extraction error for product link: %s", e)

                # ── Pagination ──
                next_btn = page.locator("button[aria-label='next page'], button:has(svg[data-testid='ArrowRightIcon'])").first
                if await next_btn.count() == 0 or not await next_btn.is_enabled():
                    logger.info("No 'Next' button or disabled. Category '%s' finished.", category)
                    break
                
                await next_btn.scroll_into_view_if_needed()
                await self.polite_delay_async()
                await next_btn.click()
                page_num += 1
                
                # Wait for content update (the product list should change)
                await page.wait_for_timeout(3000) 
                logger.info("Moved to page %d", page_num)

        finally:
            await page.close()

        return records

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    # Mocking config mapping for standalone test
    scraper = Scraper()
    # Test with one URL
    urls = ["https://www.sigma-computer.com/en/category/9f5039de-5c80-46f3-9fe4-6e8f94189b8c"]
    print("Scraping started (standalone test)...")
    import asyncio
    output = asyncio.run(scraper.async_run(urls))
    print(json.dumps(output[:2], indent=2))
