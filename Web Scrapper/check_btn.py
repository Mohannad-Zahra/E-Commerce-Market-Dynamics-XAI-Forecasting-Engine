import asyncio
from playwright.async_api import async_playwright

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.goto('https://2b.com.eg/en/computers/laptops.html', wait_until='domcontentloaded')
        
        for _ in range(30):
            await page.evaluate('window.scrollBy(0, 800)')
            await asyncio.sleep(0.3)
            
        locators = await page.locator('a.action.next').all()
        for i, loc in enumerate(locators):
            print(f'Button {i}: visible={await loc.is_visible()}, href={await loc.get_attribute("href")}')
        
        await browser.close()

asyncio.run(run())
