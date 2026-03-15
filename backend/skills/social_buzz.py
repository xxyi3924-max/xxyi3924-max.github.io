import json
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import logger

import requests
import yfinance as yf
from curl_cffi import requests as cf_requests
from finvizfinance.quote import finvizfinance

from prompts import SOCIAL_BUZZ_SUBAGENT_PROMPT

REDDIT_HEADERS = {"User-Agent": "smartmoney-agent/1.0 (research tool)"}
REDDIT_SEARCH_URL = (
    "https://www.reddit.com/r/wallstreetbets+stocks+investing+options/"
    "search.json?q={ticker}&restrict_sr=1&sort=new&t=day&limit=25"
)

# Specific financial-event terms only — avoid generic movement words
# ("record", "strong", "rise", "gain" fire on almost every AI/tech headline)
BULLISH_TERMS = {"bullish", "upgrade", "outperform", "buy rating", "beat", "beats", "breakout", "surge", "rally", "soar", "guidance raise", "raised target", "blowout", "exceeds estimates"}
BEARISH_TERMS = {"bearish", "downgrade", "underperform", "sell rating", "miss", "misses", "crash", "plunge", "guidance cut", "lowered target", "disappoints", "layoffs", "investigation", "lawsuit"}


def social_buzz(ticker: str) -> dict:
    if os.getenv("MOCK_MODE", "false").lower() == "true":
        logger.fetch("fixture file", f"fixtures/{ticker.lower()}.json")
        raw = _load_fixture_raw(ticker)
    else:
        raw = _fetch_raw(ticker)

    logger.fetch("LLM sub-agent", "interpreting social data with cheap model")
    interpretation = _interpret_with_subagent(ticker, raw)

    return {
        "raw_metrics": raw,
        "interpretation": interpretation["interpretation"],
        "crowd_aware": interpretation["crowd_aware"],
        "informed_vs_hype": interpretation["informed_vs_hype"],
    }


def _fetch_raw(ticker: str) -> dict:
    logger.fetch("Reddit", REDDIT_SEARCH_URL.format(ticker=ticker))
    reddit_count, reddit_score, reddit_flair = _fetch_reddit(ticker)
    logger.found("Reddit top post score", reddit_score)

    logger.fetch("StockTwits", f"api.stocktwits.com/api/2/streams/symbol/{ticker}.json")
    bull_ratio, msg_count = _fetch_stocktwits(ticker)
    logger.found("StockTwits messages", msg_count)

    logger.fetch("Finviz", f"finviz.com/quote.ashx?t={ticker} (news headlines)")
    headlines = _fetch_finviz(ticker)
    logger.found("Finviz headlines found", len(headlines))
    for h in headlines[:3]:
        logger.found("  Headline", h)

    logger.fetch("Yahoo Finance news", f"yfinance — {ticker} recent news")
    yf_post_count, yf_bull_ratio, yf_samples = _fetch_yf_news(ticker)

    return {
        "reddit_post_count_48h": reddit_count,
        "reddit_top_post_score": reddit_score,
        "reddit_top_post_flair": reddit_flair,
        "stocktwits_bull_ratio": bull_ratio,
        "stocktwits_message_count": msg_count,
        "headlines": headlines,
        "yf_article_count": yf_post_count,
        "yf_bull_ratio": yf_bull_ratio,
        "yf_sample_headlines": yf_samples,
    }


def _fetch_reddit(ticker: str) -> tuple[int, int, str]:
    try:
        url = REDDIT_SEARCH_URL.format(ticker=ticker)
        resp = requests.get(url, headers=REDDIT_HEADERS, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        posts = data.get("data", {}).get("children", [])
        if not posts:
            return 0, 0, ""
        top = max(posts, key=lambda p: p["data"].get("score", 0))
        top_data = top["data"]
        return len(posts), top_data.get("score", 0), top_data.get("link_flair_text", "") or ""
    except Exception as e:
        logger.warn(f"Reddit fetch failed: {e}")
        return 0, 0, ""


def _fetch_stocktwits(ticker: str) -> tuple[float, int]:
    """Uses curl_cffi to impersonate Chrome and bypass Cloudflare on StockTwits."""
    try:
        url = f"https://api.stocktwits.com/api/2/streams/symbol/{ticker}.json"
        resp = cf_requests.get(url, impersonate="chrome110", timeout=10)
        if resp.status_code != 200:
            logger.warn(f"StockTwits returned {resp.status_code}")
            return 0.5, 0
        data = resp.json()
        messages = data.get("messages", [])
        if not messages:
            return 0.5, 0
        bulls = sum(
            1 for m in messages
            if (m.get("entities", {}).get("sentiment") or {}).get("basic") == "Bullish"
        )
        return round(bulls / len(messages), 2), len(messages)
    except Exception as e:
        logger.warn(f"StockTwits fetch failed: {e}")
        return 0.5, 0


def _fetch_finviz(ticker: str) -> list[str]:
    try:
        stock = finvizfinance(ticker)
        news_df = stock.ticker_news()
        headlines = news_df["Title"].tolist()[:8]
        return [str(h) for h in headlines]
    except Exception as e:
        logger.warn(f"Finviz fetch failed: {e}")
        return []


def _fetch_yf_news(ticker: str) -> tuple[int, float, list[str]]:
    """Fetch recent news from Yahoo Finance via yfinance and score sentiment."""
    try:
        stock = yf.Ticker(ticker)
        news = stock.news or []
        if not news:
            return 0, 0.5, []

        titles = []
        for item in news[:20]:
            content = item.get("content", {})
            title = content.get("title", "") if isinstance(content, dict) else ""
            if title:
                titles.append(title)

        if not titles:
            return 0, 0.5, []

        bull_count = sum(1 for t in titles if any(w in t.lower() for w in BULLISH_TERMS))
        bear_count = sum(1 for t in titles if any(w in t.lower() for w in BEARISH_TERMS))
        total = bull_count + bear_count
        bull_ratio = round(bull_count / total, 2) if total > 0 else 0.5

        return len(titles), bull_ratio, titles[:5]
    except Exception as e:
        logger.warn(f"Yahoo Finance news fetch failed: {e}")
        return 0, 0.5, []


def _interpret_with_subagent(ticker: str, raw: dict) -> dict:
    from llm import get_llm
    llm = get_llm()
    user_msg = f"Ticker: {ticker}\n\nRaw social data:\n{json.dumps(raw, indent=2)}"
    response_text = llm.run_simple(SOCIAL_BUZZ_SUBAGENT_PROMPT, user_msg)
    try:
        start = response_text.index("{")
        end = response_text.rindex("}") + 1
        return json.loads(response_text[start:end])
    except (ValueError, json.JSONDecodeError):
        return {"interpretation": response_text, "crowd_aware": False, "informed_vs_hype": "none"}


def _load_fixture_raw(ticker: str) -> dict:
    path = os.path.join(os.path.dirname(__file__), "..", "fixtures", f"{ticker.lower()}.json")
    with open(path) as f:
        data = json.load(f)
    return data["social_buzz_raw"]
