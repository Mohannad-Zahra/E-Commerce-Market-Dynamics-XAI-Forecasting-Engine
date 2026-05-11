"""
payload/twob.py
─────────────────────────────────────────────────────────────────────
Playwright-based scraper payload for 2B Egypt.
─────────────────────────────────────────────────────────────────────
"""
import asyncio
import json
import logging
import random
from datetime import datetime, timezone
from urllib.parse import urlparse
import os

from playwright.async_api import async_playwright
from payload.base import ScraperPayload

logger = logging.getLogger("payload.twob")

class Scraper(ScraperPayload):
    """
    Scraper implementation for 2b.com.eg using async_playwright.
    """

    @staticmethod
    def _parse_category(url: str) -> tuple[str, str | None]:
        """
        Extract category and sub_category from a 2B target URL.

        Examples:
            .../en/computers/laptops.html          → ("computers", "laptops")
            .../en/mobile-and-tablet/mobiles.html   → ("mobile-and-tablet", "mobiles")
            .../en/audio/headphones/true-wireless-headphones.html
                                                   → ("audio", "headphones/true-wireless-headphones")
        """
        path = urlparse(url).path  # e.g. /en/computers/laptops.html
        # Strip leading/trailing slashes and remove .html suffix
        segments = [s.replace(".html", "") for s in path.strip("/").split("/") if s]
        # Remove the locale segment (e.g. 'en')
        if segments and len(segments[0]) <= 3:
            segments = segments[1:]

        category = segments[0] if len(segments) >= 1 else "unknown"
        sub_category = "/".join(segments[1:]) if len(segments) >= 2 else None
        return category, sub_category

    def run(self) -> list[dict]:
        logger.info("Starting 2B Egypt payload execution.")
        
        # Load config to get target URLs
        config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'config.json')
        target_urls = []
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                for retailer in config.get("retailers", []):
                    if retailer.get("retailer_id") == "2b_egypt":
                        target_urls = retailer.get("target_urls", [])
                        break
        except Exception as e:
            logger.error("Failed to load target_urls from config.json: %s", e)
            
        if not target_urls:
            logger.warning("No target URLs found for 2b_egypt.")
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
            
        logger.info("Successfully fetched %d records for 2B Egypt.", len(records))
        return records
        
    async def scrape_category(self, context, start_url: str) -> list[dict]:
        page = await context.new_page()
        records = []
        category, sub_category = self._parse_category(start_url)
        page_num = 1

        try:
            # ── Load the first page via normal navigation ──────────
            logger.info("Scraping 2B category page 1: %s", start_url)
            await self.polite_delay_async()
            try:
                await page.goto(start_url, wait_until="domcontentloaded", timeout=60000)
            except Exception as e:
                logger.warning("Timeout or err navigating to %s: %s", start_url, e)
                return records

            while True:
                # ── Scroll to bottom to trigger lazy-loaded products ──
                prev_height = 0
                for _ in range(30):
                    await page.evaluate("window.scrollBy(0, 800)")
                    await page.wait_for_timeout(350)
                    curr_height = await page.evaluate("document.body.scrollHeight")
                    if curr_height == prev_height:
                        break
                    prev_height = curr_height

                # ── Extract product cards from the current page ───────
                product_cards = await page.locator(".product-item").all()
                if not product_cards:
                    await asyncio.sleep(2)
                    product_cards = await page.locator(".product-item").all()

                logger.info(
                    "Page %d: found %d products (category=%s)",
                    page_num, len(product_cards), category,
                )

                for card in product_cards:
                    try:
                        title_loc = card.locator(".product-item-link")
                        raw_title = await title_loc.inner_text() if await title_loc.count() > 0 else ""
                        raw_title = raw_title.strip()

                        price_loc = card.locator("[data-price-type=\"finalPrice\"] .price").first
                        raw_current_price = await price_loc.inner_text() if await price_loc.count() > 0 else ""
                        raw_current_price = raw_current_price.strip()

                        old_price_loc = card.locator("[data-price-type=\"oldPrice\"] .price").first
                        raw_original_price = await old_price_loc.inner_text() if await old_price_loc.count() > 0 else None
                        if raw_original_price:
                            raw_original_price = raw_original_price.strip()

                        stock_loc = card.locator(".stock.available span, .stock.unavailable span").first
                        availability_text = await stock_loc.inner_text() if await stock_loc.count() > 0 else None
                        if availability_text:
                            availability_text = availability_text.strip()

                        product_url = await title_loc.get_attribute("href") if await title_loc.count() > 0 else ""

                        if not raw_title or not product_url:
                            continue

                        record = {
                            "scrape_timestamp": datetime.now(timezone.utc).isoformat(),
                            "retailer_id": "2b_egypt",
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
                        logger.warning("Failed to extract data from a product card: %s", e)

                # ── AJAX pagination: click "Next" if it exists ────────
                next_btn = page.locator("a.action.next:visible")
                if await next_btn.count() == 0:
                    logger.info("No more pages for category '%s'. Done.", category)
                    break

                # Scroll the next button into view and click it
                await next_btn.first.scroll_into_view_if_needed()
                await page.wait_for_timeout(300)

                # Capture a reference product title to detect when new content loads
                first_product = page.locator(".product-item-link").first
                old_title = ""
                if await first_product.count() > 0:
                    old_title = (await first_product.inner_text()).strip()

                await self.polite_delay_async()
                await next_btn.first.click()
                page_num += 1

                # Wait for AJAX: the loading overlay (Magento 2 spinner)
                # appears as .loading-mask or similar; wait for it to vanish.
                try:
                    loader = page.locator(".loading-mask, .loader, #loader")
                    await loader.first.wait_for(state="visible", timeout=3000)
                    await loader.first.wait_for(state="hidden", timeout=30000)
                except Exception:
                    # Spinner may not always appear; fall back to product change detection
                    pass

                # Also wait until the first product title changes (new page loaded)
                if old_title:
                    for _ in range(30):  # up to 15 seconds
                        await page.wait_for_timeout(500)
                        try:
                            new_first = page.locator(".product-item-link").first
                            new_title = (await new_first.inner_text()).strip() if await new_first.count() > 0 else ""
                            if new_title and new_title != old_title:
                                break
                        except Exception:
                            pass
                else:
                    await page.wait_for_timeout(3000)

                # Scroll back to top for the next extraction pass
                await page.evaluate("window.scrollTo(0, 0)")
                await page.wait_for_timeout(500)

                logger.info("Navigated to page %d via AJAX click.", page_num)

        finally:
            await page.close()

        return records

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    scraper = Scraper()
    print("Scraping started.")
    output = scraper.run()
    print(json.dumps(output[:2], indent=2))
