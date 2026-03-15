"""
Dark Pool / Off-Exchange Accumulation Proxy — Skill 6.

FINRA TRF (Trade Reporting Facility) raw files are behind a Cloudflare wall,
so this skill infers dark pool activity from behavioral signatures that
institutional block trades leave in OHLCV data:

1. Volume Absorption  — high volume + narrow daily range = institution absorbing
   retail supply without moving price. Classic dark pool accumulation footprint.

2. Block Trade Score  — 10-day rolling score based on vol/price impact ratio.
   vol > 2x avg AND price move < 1.5% = probable block print.

3. Flow/Price Divergence  — volume slope rising while price slope is flat/down
   = silent accumulation. This is the exact scenario the project thesis targets.

4. ATM Options Spread  — tight near-ATM spread = market makers providing
   liquidity = institutional participant present.

These four signals triangulate dark pool activity without direct TRF access.
When 2+ signals fire simultaneously the probability of real off-exchange
institutional activity is high.
"""

import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import logger

import numpy as np
import yfinance as yf


def dark_pool(ticker: str) -> dict:
    if os.getenv("MOCK_MODE", "false").lower() == "true":
        return _load_fixture(ticker)
    return _fetch(ticker)


def _fetch(ticker: str) -> dict:
    stock = yf.Ticker(ticker)

    logger.fetch("yfinance OHLCV", f"{ticker} 30-day daily bars for absorption analysis")
    hist = stock.history(period="30d")

    if len(hist) < 10:
        logger.warn("Insufficient price history for dark pool analysis")
        return _empty(ticker)

    closes = hist["Close"].values.astype(float)
    volumes = hist["Volume"].values.astype(float)
    highs = hist["High"].values.astype(float)
    lows = hist["Low"].values.astype(float)

    avg_vol = volumes[:-1].mean() if len(volumes) > 1 else volumes.mean()
    latest_close = closes[-1]

    # ATR-relative thresholds — hardcoded 1% fails for volatile large-caps (NVDA
    # has a typical daily range of 2–4%). Instead, measure "narrow" relative to
    # the stock's own average daily range over the lookback window.
    daily_ranges_pct = (highs - lows) / closes * 100
    avg_range_pct = float(daily_ranges_pct.mean()) if len(daily_ranges_pct) > 0 else 2.0
    # "narrow day" = range is in the bottom 60% of the stock's own typical range
    narrow_threshold = avg_range_pct * 0.6
    # "small move" for block score = close-to-close change < 60% of avg range
    small_move_threshold = avg_range_pct * 0.6
    tight_move_threshold = avg_range_pct * 0.4
    logger.found("Avg daily range (ATR proxy)", f"{avg_range_pct:.2f}%  →  narrow<{narrow_threshold:.2f}%")

    # ── 1. Volume Absorption Detection ───────────────────────────────────────
    # High volume + narrow intraday range (relative to this stock's ATR)
    absorption_events = []
    for i in range(max(0, len(hist) - 5), len(hist)):
        vol_ratio = volumes[i] / avg_vol if avg_vol > 0 else 1.0
        range_pct = (highs[i] - lows[i]) / closes[i] * 100
        close_pos = (closes[i] - lows[i]) / (highs[i] - lows[i]) if highs[i] > lows[i] else 0.5

        if vol_ratio > 1.5 and range_pct < narrow_threshold:
            direction = "bullish" if close_pos >= 0.5 else "bearish"
            absorption_events.append({
                "date": hist.index[i].date().isoformat(),
                "vol_ratio": round(vol_ratio, 2),
                "range_pct": round(range_pct, 2),
                "direction": direction,
            })

    absorption_detected = len(absorption_events) >= 1

    # ── 2. Block Trade Score (0–10) ───────────────────────────────────────────
    block_score = 0
    for i in range(max(1, len(hist) - 10), len(hist)):
        vol_ratio = volumes[i] / avg_vol if avg_vol > 0 else 1.0
        price_change_pct = abs(closes[i] - closes[i - 1]) / closes[i - 1] * 100

        if vol_ratio > 2.0 and price_change_pct < tight_move_threshold:
            block_score += 3
        elif vol_ratio > 1.5 and price_change_pct < small_move_threshold:
            block_score += 2
        elif vol_ratio > 1.5:
            block_score += 1

    block_score = min(block_score, 10)

    # ── 3. Flow / Price Divergence ────────────────────────────────────────────
    # Volume slope rising + price slope negative = institutions quietly accumulating
    window = min(10, len(hist))
    vol_slope = float(np.polyfit(range(window), volumes[-window:], 1)[0])
    price_slope = float(np.polyfit(range(window), closes[-window:], 1)[0])

    vol_price_divergence = vol_slope > 0 and price_slope < 0

    # ── 4. ATM Options Spread ─────────────────────────────────────────────────
    options_spread_signal = "unavailable"
    try:
        exp = stock.options[0]
        chain = stock.option_chain(exp)
        calls = chain.calls.copy()
        atm = calls[(calls["strike"] - latest_close).abs() < latest_close * 0.02]
        if not atm.empty:
            atm["spread_pct"] = (atm["ask"] - atm["bid"]) / atm["lastPrice"].replace(0, float("nan"))
            avg_spread = atm["spread_pct"].dropna().mean()
            if avg_spread < 0.05:
                options_spread_signal = "tight"    # institutional liquidity
            elif avg_spread < 0.15:
                options_spread_signal = "normal"
            else:
                options_spread_signal = "wide"     # retail-dominated
    except Exception:
        pass

    # ── Estimated Direction ───────────────────────────────────────────────────
    if absorption_events:
        bull_abs = sum(1 for e in absorption_events if e["direction"] == "bullish")
        bear_abs = len(absorption_events) - bull_abs
        if bull_abs > bear_abs:
            estimated_direction = "bullish"
        elif bear_abs > bull_abs:
            estimated_direction = "bearish"
        else:
            estimated_direction = "neutral"
    elif vol_price_divergence:
        estimated_direction = "bullish"  # vol up, price down = accumulation
    else:
        estimated_direction = "unknown"

    high_activity = block_score >= 5 or (absorption_detected and estimated_direction != "unknown")

    return {
        "absorption_detected": absorption_detected,
        "absorption_events": absorption_events,
        "estimated_direction": estimated_direction,
        "block_trade_score": block_score,
        "vol_price_divergence": vol_price_divergence,
        "options_spread_signal": options_spread_signal,
        "high_dark_pool_activity": high_activity,
    }


def _empty(ticker: str) -> dict:
    return {
        "absorption_detected": False,
        "absorption_events": [],
        "estimated_direction": "unknown",
        "block_trade_score": 0,
        "vol_price_divergence": False,
        "options_spread_signal": "unavailable",
        "high_dark_pool_activity": False,
    }


def _load_fixture(ticker: str) -> dict:
    import json
    path = os.path.join(os.path.dirname(__file__), "..", "fixtures", f"{ticker.lower()}.json")
    with open(path) as f:
        data = json.load(f)
    return data.get("dark_pool", _empty(ticker))
