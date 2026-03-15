"""
X (Twitter) Post Scraper — Playwright + Cookie Injection
---------------------------------------------------------
Usage:
    python x_scraper.py --query "your search term" --limit 20

Setup:
    pip install playwright
    playwright install chromium

Cookie setup:
    Edit COOKIES list below with your X session cookies.
    Grab them from browser DevTools → Application → Cookies → https://x.com
    Required keys: auth_token, ct0  (bare minimum)
"""

import asyncio
import argparse
import json
import re
from playwright.async_api import async_playwright

# ─────────────────────────────────────────────
# PASTE YOUR X COOKIES HERE
# Get from: DevTools → Application → Cookies → https://x.com
# ─────────────────────────────────────────────
COOKIES = [
    {
        "name": "auth_token",
        "value": "YOUR_AUTH_TOKEN_HERE",
        "domain": ".x.com",
        "path": "/",
        "httpOnly": True,
        "secure": True,
        "sameSite": "None",
    },
    {
        "name": "ct0",
        "value": "YOUR_CT0_VALUE_HERE",
        "domain": ".x.com",
        "path": "/",
        "httpOnly": False,
        "secure": True,
        "sameSite": "Lax",
    },
    # Add more cookies here if needed (e.g. guest_id, twid, etc.)
]


async def scrape_x_posts(query: str, limit: int = 20, headless: bool = True):
    """
    Scrape X posts for a given search query.

    Args:
        query:    Search term to look up
        limit:    Max number of posts to collect
        headless: Run browser in background (True) or visible (False)
    """

    search_url = f"https://x.com/search?q={query.replace(' ', '%20')}&src=typed_query&f=live"
    collected = []
    seen_texts = set()

    print(f"\n🔍 Searching X for: '{query}'")
    print(f"🎯 Target: {limit} posts\n")
    print("─" * 60)

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=headless,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",  # hide automation flag
                "--disable-infobars",
            ],
        )

        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/123.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 900},
            locale="en-US",
        )

        # ── Inject cookies ──────────────────────────────────────
        await context.add_cookies(COOKIES)

        page = await context.new_page()

        # Remove navigator.webdriver fingerprint
        await page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        """)

        print("🌐 Navigating to X search...")
        await page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(3000)

        # Check if we're logged in
        if "login" in page.url.lower():
            print("❌ Not logged in — check your cookies and try again.")
            await browser.close()
            return

        print("✅ Logged in. Scraping posts...\n")

        stall_count = 0
        last_count = 0

        while len(collected) < limit:
            # ── Extract tweet text from all visible tweet articles ──
            tweets = await page.query_selector_all('article[data-testid="tweet"]')

            for tweet in tweets:
                if len(collected) >= limit:
                    break

                try:
                    # Grab the tweet text block
                    text_el = await tweet.query_selector('[data-testid="tweetText"]')
                    if not text_el:
                        continue

                    text = await text_el.inner_text()
                    text = text.strip()

                    if not text or text in seen_texts:
                        continue

                    seen_texts.add(text)
                    collected.append(text)

                    idx = len(collected)
                    print(f"[{idx:>3}] {text[:120]}{'...' if len(text) > 120 else ''}\n")

                except Exception:
                    continue

            # ── Stall detection ─────────────────────────────────
            if len(collected) == last_count:
                stall_count += 1
                if stall_count >= 5:
                    print("⚠️  No new posts found after multiple scrolls. Stopping.")
                    break
            else:
                stall_count = 0

            last_count = len(collected)

            # ── Scroll down to load more ─────────────────────────
            await page.evaluate("window.scrollBy(0, window.innerHeight * 2)")
            await page.wait_for_timeout(2000)  # wait for lazy load

        await browser.close()

    print("─" * 60)
    print(f"\n✅ Done. Collected {len(collected)} posts for '{query}'.\n")
    return collected


def main():
    parser = argparse.ArgumentParser(description="Scrape X posts by search query")
    parser.add_argument("--query", "-q", required=True, help="Search query string")
    parser.add_argument("--limit", "-l", type=int, default=20, help="Max posts to collect (default: 20)")
    parser.add_argument("--show-browser", action="store_true", help="Show browser window (non-headless)")
    args = parser.parse_args()

    asyncio.run(
        scrape_x_posts(
            query=args.query,
            limit=args.limit,
            headless=not args.show_browser,
        )
    )


if __name__ == "__main__":
    main()
