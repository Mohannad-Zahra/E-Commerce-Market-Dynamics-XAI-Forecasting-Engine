"""
payload/btech.py — VERSION 4 (TreeWalker + empty-join fix)
─────────────────────────────────────────────────────────────────────
Playwright-based scraper payload for B.TECH Egypt.
 
ROOT CAUSE OF PREVIOUS FAILURES:
  BTech renders the price as TWO separate DOM text nodes:
    node 1: "EGP"
    node 2: "61,970"
  Joining with " " (space) gives "EGP 61,970" — regex fails.
  Joining with "" (empty) gives "EGP61,970"  — regex matches. ✓
 
This version uses document.createTreeWalker to collect all text nodes
and joins them with "" before running the EGP regex.
─────────────────────────────────────────────────────────────────────
"""
 
import asyncio
import logging
import random
from datetime import datetime, timezone
 
from playwright.async_api import async_playwright
from payload.base import ScraperPayload
 
logger = logging.getLogger("payload.btech")
 
CAT_MAP: dict[str, tuple[str, str | None]] = {
    "/en/c/laptop-pc/laptops/b/dell": ("laptops", "dell"),
    "/en/c/laptop-pc/laptops":        ("laptops", None),
    "/en/c/laptop-pc":                ("laptop-pc", None),
}
 
BASE_URL = "https://btech.com"
RETAILER_ID = "btech"
 
# ── KEY FIX: join text nodes with "" so "EGP" + "61,970" → "EGP61,970" ──
_EXTRACT_JS = """
() => {
    const results = [];
 
    function getJoinedText(el) {
        const texts = [];
        const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
        let node;
        while ((node = walker.nextNode())) {
            texts.push(node.textContent.trim());
        }
        return texts.join('');
    }
 
    function findPrices(el) {
        const joined = getJoinedText(el);
        const matches = joined.match(/EGP[\\d,]+/g) || [];
        return { matches, joined };
    }
 
    const anchors = document.querySelectorAll('a[href*="/en/p/"]');
 
    anchors.forEach(anchor => {
        try {
            const h2 = anchor.querySelector('h2');
            if (!h2) return;
 
            const titleText = h2.innerText.trim();
            if (!titleText) return;
 
            const href = anchor.getAttribute('href') || '';
 
            // Climb DOM to find card container that contains EGP
            let container = anchor.parentElement;
            let foundEGP = false;
 
            for (let i = 0; i < 10; i++) {
                if (!container || container === document.body) break;
                const { matches } = findPrices(container);
                if (matches.length > 0) {
                    foundEGP = true;
                    break;
                }
                container = container.parentElement;
            }
 
            if (!foundEGP || !container) {
                results.push({
                    title: titleText,
                    href: href,
                    currentPrice: '',
                    originalPrice: null,
                    hasPriceDrop: false,
                    debug: 'NO_EGP_FOUND',
                });
                return;
            }
 
            const { matches, joined } = findPrices(container);
            const hasPriceDrop = joined.includes('Pricedrop') ||
                                 (container.innerText || '').includes('Price drop');
 
            results.push({
                title:         titleText,
                href:          href,
                currentPrice:  matches[0] || '',
                originalPrice: (hasPriceDrop && matches.length >= 2) ? matches[1] : null,
                hasPriceDrop:  hasPriceDrop,
                debug:         matches.join('|'),
            });
 
        } catch (e) {
            results.push({ title: '??', href: '', currentPrice: '', debug: 'JS_ERR:' + e });
        }
    });
 
    return results;
}
"""
 
 
class Scraper(ScraperPayload):
    """Scraper for btech.com — async Playwright, JS-side extraction."""
 
    def run(self) -> list[dict]:
        logger.info("Starting B.TECH Egypt payload execution.")
        return asyncio.run(self._async_run(
            ["https://btech.com/en/c/laptop-pc/laptops/b/dell"]
        ))
 
    async def _polite_delay_async(self):
        delay = random.uniform(5.0, 7.0)
        logger.debug("Polite delay: %.2fs", delay)
        await asyncio.sleep(delay)
 
    async def _async_run(self, target_urls: list[str]) -> list[dict]:
        records = []
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/114.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1920, "height": 1080},
            )
            for url in target_urls:
                try:
                    url_records = await self._scrape_listing(context, url)
                    records.extend(url_records)
                    logger.info("Finished %s — %d records so far.", url, len(records))
                except Exception as exc:
                    logger.error("Error scraping %s: %s", url, exc, exc_info=True)
            await browser.close()
 
        logger.info("B.TECH Egypt payload complete — %d total records.", len(records))
        return records
 
    async def _scrape_listing(self, context, url: str) -> list[dict]:
        from urllib.parse import urlparse
        path = urlparse(url).path.rstrip("/")
        category, sub_category = CAT_MAP.get(path, ("laptops", "dell"))
 
        page = await context.new_page()
        records = []
 
        try:
            logger.info("Navigating to: %s", url)
            await self._polite_delay_async()
 
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=60_000)
            except Exception as exc:
                logger.warning("Navigation error: %s", exc)
                return records
 
            try:
                await page.wait_for_selector("a[href*='/en/p/'] h2", timeout=20_000)
            except Exception:
                logger.warning("No product titles found on %s", url)
                return records
 
            await self._scroll_to_bottom(page)
 
            raw_cards: list[dict] = await page.evaluate(_EXTRACT_JS)
            logger.info("JS extracted %d raw cards.", len(raw_cards))
 
            if raw_cards:
                s = raw_cards[0]
                logger.debug(
                    "Sample — title: %s | price: %s | debug: %s",
                    s.get("title", "")[:60],
                    s.get("currentPrice", ""),
                    s.get("debug", ""),
                )
 
            scrape_ts = datetime.now(timezone.utc).isoformat()
 
            for card in raw_cards:
                href = card.get("href", "")
                product_url = href if href.startswith("http") else f"{BASE_URL}{href}"
                raw_current_price = card.get("currentPrice", "")
 
                record = {
                    "scrape_timestamp":   scrape_ts,
                    "retailer_id":        RETAILER_ID,
                    "raw_title":          card.get("title", ""),
                    "raw_current_price":  raw_current_price,
                    "raw_original_price": card.get("originalPrice"),
                    "availability_text":  None,
                    "product_url":        product_url,
                    "category":           category,
                    "sub_category":       sub_category,
                }
 
                if self.validate_record(record):
                    records.append(record)
                else:
                    logger.debug(
                        "Validation failed — title: %s | price: %s | debug: %s",
                        card.get("title", "")[:60],
                        raw_current_price,
                        card.get("debug", ""),
                    )
 
            logger.info("Validated %d / %d records.", len(records), len(raw_cards))
 
        finally:
            await page.close()
 
        return records
 
    async def _scroll_to_bottom(self, page) -> None:
        prev_height = 0
        stall_count = 0
        for _ in range(40):
            await page.evaluate("window.scrollBy(0, 600)")
            await page.wait_for_timeout(400)
            curr_height = await page.evaluate("document.body.scrollHeight")
            if curr_height == prev_height:
                stall_count += 1
                if stall_count >= 3:
                    break
            else:
                stall_count = 0
            prev_height = curr_height
        await page.evaluate("window.scrollTo(0, 0)")
        await page.wait_for_timeout(300)
 
 
if __name__ == "__main__":
    import json as _json
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s | %(name)-20s | %(levelname)-8s | %(message)s",
    )
    scraper = Scraper()
    output = scraper.run()
    print(f"\nTotal records: {len(output)}")
    if output:
        print(_json.dumps(output[:3], indent=2))
    else:
        print("Still 0 — check DEBUG lines above for 'debug' field")
 