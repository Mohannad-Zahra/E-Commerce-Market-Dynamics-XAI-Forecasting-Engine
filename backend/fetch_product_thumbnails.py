"""
Fetch product page hero images from product_url values and store in products.thumbnail.

Uses common meta tags (og:image, twitter:image) so it works across 2B, Sigma, Dream2000, etc.

Usage (from repo root or backend/):
  python backend/fetch_product_thumbnails.py
  python backend/fetch_product_thumbnails.py --limit 20
  python backend/fetch_product_thumbnails.py --delay 1.5

Restart the FastAPI server after updating thumbnails so the in-memory cache reloads.
"""
from __future__ import annotations

import argparse
import logging
import sqlite3
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("fetch_thumbnails")

DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "electronics_history.db"


def _abs_url(base: str, href: str | None) -> str | None:
    if not href or not str(href).strip():
        return None
    u = urljoin(base, str(href).strip())
    p = urlparse(u)
    if p.scheme not in ("http", "https"):
        return None
    return u


def extract_image_url(html: str, page_url: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")

    for prop in ("og:image", "og:image:url", "og:image:secure_url"):
        tag = soup.find("meta", property=prop)
        if tag and tag.get("content"):
            u = _abs_url(page_url, tag["content"])
            if u:
                return u

    for name in ("twitter:image", "twitter:image:src"):
        tag = soup.find("meta", attrs={"name": name})
        if tag and tag.get("content"):
            u = _abs_url(page_url, tag["content"])
            if u:
                return u

    link = soup.find("link", rel=lambda x: x and "image_src" in x.lower().split())
    if link and link.get("href"):
        u = _abs_url(page_url, link["href"])
        if u:
            return u

    for img in soup.find_all(attrs={"itemprop": "image"}):
        src = img.get("src") or img.get("content")
        u = _abs_url(page_url, src)
        if u:
            return u

    return None


def fetch_page(
    session: requests.Session,
    url: str,
    timeout: float,
    retries: int = 2,
) -> str | None:
    last_err: Exception | None = None
    for attempt in range(retries + 1):
        try:
            r = session.get(url, timeout=timeout, allow_redirects=True)
            r.raise_for_status()
            ctype = (r.headers.get("content-type") or "").lower()
            if "html" not in ctype and "text" not in ctype:
                log.warning("Unexpected content-type for %s: %s", url[:60], ctype)
            return r.text
        except requests.RequestException as e:
            last_err = e
            if attempt < retries:
                time.sleep(1.5 * (attempt + 1))
    log.warning("Request failed %s: %s", url[:70], last_err)
    return None


def main() -> None:
    ap = argparse.ArgumentParser(description="Populate products.thumbnail from live pages")
    ap.add_argument("--delay", type=float, default=1.0, help="Seconds between requests")
    ap.add_argument("--timeout", type=float, default=45.0)
    ap.add_argument("--limit", type=int, default=0, help="Max URLs (0 = all pending)")
    ap.add_argument("--force", action="store_true", help="Re-fetch even if thumbnail set")
    args = ap.parse_args()

    if not DB_PATH.is_file():
        raise SystemExit(f"Database not found: {DB_PATH}")

    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()

    if args.force:
        cur.execute("SELECT DISTINCT product_url FROM products")
    else:
        cur.execute(
            """
            SELECT DISTINCT product_url FROM products
            WHERE thumbnail IS NULL OR TRIM(thumbnail) = ''
            """
        )
    urls = [r[0] for r in cur.fetchall() if r[0]]
    if args.limit > 0:
        urls = urls[: args.limit]

    log.info("URLs to process: %d (db=%s)", len(urls), DB_PATH)

    session = requests.Session()
    session.headers.update({"User-Agent": DEFAULT_UA, "Accept-Language": "en-US,en;q=0.9"})

    ok = fail = 0
    for i, url in enumerate(urls):
        html = fetch_page(session, url, args.timeout)
        if not html:
            fail += 1
        else:
            img = extract_image_url(html, url)
            if img:
                cur.execute(
                    "UPDATE products SET thumbnail = ? WHERE product_url = ?",
                    (img, url),
                )
                conn.commit()
                ok += 1
                log.info("[%d/%d] OK %s", i + 1, len(urls), img[:80])
            else:
                log.warning("[%d/%d] No image meta in %s", i + 1, len(urls), url[:70])
                fail += 1

        if i + 1 < len(urls):
            time.sleep(args.delay)

    conn.close()
    log.info("Done. updated=%d failed_or_empty=%d", ok, fail)


if __name__ == "__main__":
    main()
