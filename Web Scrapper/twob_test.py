import asyncio
import logging
from payload.twob import Scraper

async def run():
    logging.basicConfig(level=logging.INFO)
    s = Scraper()
    # test on mobiles to verify 7 pages (or fewer if we stop early)
    urls = ['https://2b.com.eg/en/mobile-and-tablet/mobiles.html']
    records = await s.async_run(urls)
    print(f"Total records fetched: {len(records)}")

if __name__ == "__main__":
    asyncio.run(run())
