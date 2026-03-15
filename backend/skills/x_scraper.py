"""
X (Twitter) Post Scraper — twikit
----------------------------------
twikit handles the x-client-transaction-id anti-scraping header automatically.
Uses cookie-based auth (no API key needed).

Env vars (set in .env):
    X_AUTH_TOKEN   — auth_token cookie from DevTools → Application → Cookies
    X_CT0          — ct0 cookie (CSRF token)
    X_TWID         — twid cookie (u%3D<user_id>)
"""

import asyncio
import os

_MAX_POSTS = 30

BULLISH_TERMS = {
    "bullish", "calls", "moon", "buy", "long", "breakout",
    "squeeze", "upside", "🚀", "📈", "beat", "surge", "rally", "upgrade",
}
BEARISH_TERMS = {
    "bearish", "puts", "short", "sell", "crash", "dump",
    "downside", "🐻", "📉", "miss", "cut", "warning", "downgrade",
}


def fetch_x_posts(ticker: str) -> dict:
    auth_token = os.getenv("X_AUTH_TOKEN", "").strip()
    ct0 = os.getenv("X_CT0", "").strip()
    twid = os.getenv("X_TWID", "").strip()

    if not auth_token or not ct0:
        return _empty()

    try:
        import twikit  # noqa
    except ImportError:
        print("[x_scraper] twikit not installed — skipping X data")
        return _empty()

    try:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(
                asyncio.wait_for(_scrape(ticker, auth_token, ct0, twid), timeout=30)
            )
        finally:
            loop.close()
    except asyncio.TimeoutError:
        print("[x_scraper] timed out after 30s")
        return _empty()
    except Exception as e:
        print(f"[x_scraper] error: {e}")
        return _empty()


async def _scrape(ticker: str, auth_token: str, ct0: str, twid: str) -> dict:
    from twikit import Client

    client = Client(language="en-US")
    client.set_cookies({
        "auth_token": auth_token,
        "ct0": ct0,
        "twid": twid,
    })

    query = f"${ticker} OR #{ticker}stock lang:en -is:retweet"
    tweets = await client.search_tweet(query, product="Latest", count=_MAX_POSTS)

    collected = []
    for tweet in tweets:
        text = tweet.text or ""
        if not text:
            continue
        likes = tweet.favorite_count or 0
        collected.append({"text": text, "likes": likes})

    if not collected:
        print("[x_scraper] no tweets returned")
        return _empty()

    bull_count = sum(1 for p in collected if _is_bullish(p["text"]))
    bear_count = sum(1 for p in collected if _is_bearish(p["text"]))
    bull_ratio = round(bull_count / len(collected), 2)

    top = sorted(collected, key=lambda p: p["likes"], reverse=True)[:3]
    sample_texts = [p["text"][:200] for p in top]

    print(f"[x_scraper] got {len(collected)} posts, bull_ratio={bull_ratio}")
    return {
        "post_count": len(collected),
        "bull_ratio": bull_ratio,
        "bear_count": bear_count,
        "top_posts": top,
        "sample_texts": sample_texts,
    }


def _is_bullish(text: str) -> bool:
    lower = text.lower()
    return any(term in lower for term in BULLISH_TERMS)


def _is_bearish(text: str) -> bool:
    lower = text.lower()
    return any(term in lower for term in BEARISH_TERMS)


def _empty() -> dict:
    return {
        "post_count": 0,
        "bull_ratio": 0.5,
        "bear_count": 0,
        "top_posts": [],
        "sample_texts": [],
    }
