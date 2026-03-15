import json
import math
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import logger

import requests


def price_action(ticker: str) -> dict:
    if os.getenv("MOCK_MODE", "false").lower() == "true":
        logger.fetch("fixture file", f"fixtures/{ticker.lower()}.json")
        return _load_fixture(ticker)

    return _fetch_twelve_data(ticker)


def _fetch_twelve_data(ticker: str) -> dict:
    api_key = os.environ["TWELVE_DATA_API_KEY"]
    url = (
        f"https://api.twelvedata.com/time_series"
        f"?symbol={ticker}&interval=1day&outputsize=60&apikey={api_key}"
    )
    logger.fetch("Twelve Data", f"api.twelvedata.com — {ticker} daily OHLCV, 60 bars")
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    data = resp.json()

    if "values" not in data:
        logger.warn("Twelve Data returned no values")
        return _empty()

    values = data["values"]
    if len(values) < 21:
        logger.warn(f"Not enough data points ({len(values)} returned, need 21)")
        return _empty()

    logger.found("Data points received", len(values))

    closes = [float(v["close"]) for v in values]
    volumes = [float(v["volume"]) for v in values]

    latest_close = closes[0]
    latest_volume = volumes[0]
    avg_volume_20d = sum(volumes[1:21]) / 20
    volume_ratio = round(latest_volume / avg_volume_20d, 2) if avg_volume_20d > 0 else 1.0

    high_52w = max(float(v["high"]) for v in values)
    pct_from_52w_high = round((latest_close - high_52w) / high_52w * 100, 2)

    close_20d_ago = closes[20]
    if latest_close > close_20d_ago * 1.03:
        trend = "uptrend"
    elif latest_close < close_20d_ago * 0.97:
        trend = "downtrend"
    else:
        trend = "ranging"

    recent_catalyst = any(v > avg_volume_20d * 1.5 for v in volumes[:3])

    logger.found("Latest close", f"${latest_close:.2f}")
    logger.found("20d avg volume", f"{avg_volume_20d:,.0f}")
    logger.found("Today's volume", f"{latest_volume:,.0f}  ({volume_ratio}x avg)")
    logger.found("60d high (proxy 52w)", f"${high_52w:.2f}  ({pct_from_52w_high}% away)")
    logger.found("Close 20d ago", f"${close_20d_ago:.2f}  → trend={trend}")
    # ── SMC primitives ──────────────────────────────────────────────────────────
    # values[0] is the most recent candle; reverse for chronological order.
    chron = list(reversed(values))

    order_block = _calc_order_block(chron)
    fvg = _calc_fvg(chron, latest_close)
    amd_phase = _calc_amd_phase(chron)
    flow_price_divergence = _calc_flow_price_divergence(closes, volumes)

    return {
        "trend": trend,
        "volume_ratio": volume_ratio,
        "pct_from_52w_high": pct_from_52w_high,
        "recent_catalyst": recent_catalyst,
        # SMC fields
        "order_block": order_block,
        "fvg": fvg,
        "amd_phase": amd_phase,
        "flow_price_divergence": flow_price_divergence,
    }


# ── SMC helper: Order Block ──────────────────────────────────────────────────

def _calc_order_block(chron: list) -> dict:
    """
    Scan the last 20 candles (chronological order, chron[-1] = most recent) for
    a Break of Structure (BOS) and return the Order Block candle that preceded it.

    Bullish BOS  = close breaks above the prior swing high  →  OB is the last
                   bearish candle before the breakout candle.
    Bearish BOS  = close breaks below the prior swing low   →  OB is the last
                   bullish candle before the breakdown candle.

    A swing high/low is the highest high / lowest low of the 3 candles that
    precede the potential breakout candle (simple 3-bar pivot).
    """
    no_ob = {"type": "none", "price_level": 0.0, "candles_ago": 0}
    window = chron[-20:] if len(chron) >= 20 else chron
    n = len(window)
    if n < 5:
        return no_ob

    # We need at least a pivot lookback (3 bars) + breakout candle.
    # Iterate from index 3 onward (so indexes 0-2 form the pivot reference).
    best = None  # (candles_ago_from_end, ob_dict)

    for i in range(3, n):
        pivot_highs = [float(window[j]["high"]) for j in range(i - 3, i)]
        pivot_lows  = [float(window[j]["low"])  for j in range(i - 3, i)]
        swing_high = max(pivot_highs)
        swing_low  = min(pivot_lows)

        c_close = float(window[i]["close"])
        c_open  = float(window[i]["open"])

        # Bullish BOS: close breaks above swing high
        if c_close > swing_high:
            # Find the last bearish candle before index i
            ob_idx = None
            for k in range(i - 1, -1, -1):
                if float(window[k]["close"]) < float(window[k]["open"]):
                    ob_idx = k
                    break
            if ob_idx is not None:
                candles_ago = (n - 1) - ob_idx
                price_level = round(float(window[ob_idx]["low"]), 2)
                best = {"type": "bullish", "price_level": price_level, "candles_ago": candles_ago}
            # Keep scanning; later BOS will overwrite (we want the most recent)

        # Bearish BOS: close breaks below swing low
        elif c_close < swing_low:
            ob_idx = None
            for k in range(i - 1, -1, -1):
                if float(window[k]["close"]) > float(window[k]["open"]):
                    ob_idx = k
                    break
            if ob_idx is not None:
                candles_ago = (n - 1) - ob_idx
                price_level = round(float(window[ob_idx]["high"]), 2)
                best = {"type": "bearish", "price_level": price_level, "candles_ago": candles_ago}

    return best if best is not None else no_ob


# ── SMC helper: Fair Value Gap ───────────────────────────────────────────────

def _calc_fvg(chron: list, latest_close: float) -> dict:
    """
    Scan last 20 candles for 3-candle FVG patterns and return the most recent
    *unfilled* one.

    Bullish FVG : candle[i+2].low  > candle[i].high  (gap above candle i)
    Bearish FVG : candle[i+2].high < candle[i].low   (gap below candle i)

    A gap is considered filled if latest_close has traded inside it.
    We iterate from the newest eligible triplet backward so the first unfilled
    one we find is the most recent.
    """
    no_fvg = {"type": "none", "upper": 0.0, "lower": 0.0, "candles_ago": 0}
    window = chron[-20:] if len(chron) >= 20 else chron
    n = len(window)
    if n < 3:
        return no_fvg

    # Iterate newest-first: triplet is (i, i+1, i+2); latest valid start = n-3
    for i in range(n - 3, -1, -1):
        low_i   = float(window[i]["low"])
        high_i  = float(window[i]["high"])
        low_i2  = float(window[i + 2]["low"])
        high_i2 = float(window[i + 2]["high"])

        # Candles ago counts from the last candle in the window
        candles_ago = (n - 1) - i  # how many candles ago was candle[i]

        # Bullish FVG
        if low_i2 > high_i:
            upper = round(low_i2, 2)
            lower = round(high_i, 2)
            # Filled if latest_close has dipped into or below the gap
            if latest_close >= lower:  # gap not yet filled from below
                return {"type": "bullish", "upper": upper, "lower": lower, "candles_ago": candles_ago}

        # Bearish FVG
        elif high_i2 < low_i:
            upper = round(low_i, 2)
            lower = round(high_i2, 2)
            # Filled if latest_close has risen into or above the gap
            if latest_close <= upper:  # gap not yet filled from above
                return {"type": "bearish", "upper": upper, "lower": lower, "candles_ago": candles_ago}

    return no_fvg


# ── SMC helper: AMD Phase ────────────────────────────────────────────────────

def _calc_amd_phase(chron: list) -> str:
    """
    Rolling 20-candle AMD phase detection.

    ATR (simple True Range average over the window):
        TR = max(high-low, |high-prev_close|, |low-prev_close|)

    Accumulation   : ATR% < 1.5% for 5+ consecutive candles in the window
    Manipulation   : a single candle's range > 2× ATR
    Distribution   : a directional candle (|close-open| > 0.5× ATR) following
                     the manipulation candle
    Trending       : none of the above patterns detected
    """
    window = chron[-21:] if len(chron) >= 21 else chron  # extra bar for prev_close
    n = len(window)
    if n < 3:
        return "trending"

    # Compute True Ranges
    trs = []
    for i in range(1, n):
        high  = float(window[i]["high"])
        low   = float(window[i]["low"])
        prev_c = float(window[i - 1]["close"])
        tr = max(high - low, abs(high - prev_c), abs(low - prev_c))
        trs.append(tr)

    if not trs:
        return "trending"

    atr = sum(trs) / len(trs)
    candles = window[1:]  # align with trs (skip the first bar used as prev)
    m = len(candles)

    # Check Accumulation: ATR% < 1.5% for 5+ consecutive candles
    consec_low_atr = 0
    max_consec = 0
    for i, tr in enumerate(trs):
        mid = (float(candles[i]["high"]) + float(candles[i]["low"])) / 2
        atr_pct = (tr / mid * 100) if mid > 0 else 999
        if atr_pct < 1.5:
            consec_low_atr += 1
            max_consec = max(max_consec, consec_low_atr)
        else:
            consec_low_atr = 0

    if max_consec >= 5:
        # Check if Manipulation candle follows the accumulation zone
        # A manipulation candle has range > 2× ATR
        for i in range(m):
            c_range = float(candles[i]["high"]) - float(candles[i]["low"])
            if c_range > 2 * atr:
                # Check if a Distribution candle follows
                if i + 1 < m:
                    next_c = candles[i + 1]
                    body = abs(float(next_c["close"]) - float(next_c["open"]))
                    if body > 0.5 * atr:
                        return "distribution"
                return "manipulation"
        return "accumulation"

    # Check Manipulation without prior accumulation signal
    for i in range(m):
        c_range = float(candles[i]["high"]) - float(candles[i]["low"])
        if c_range > 2 * atr:
            if i + 1 < m:
                next_c = candles[i + 1]
                body = abs(float(next_c["close"]) - float(next_c["open"]))
                if body > 0.5 * atr:
                    return "distribution"
            return "manipulation"

    return "trending"


# ── SMC helper: Flow vs Price Divergence ─────────────────────────────────────

def _calc_flow_price_divergence(closes: list, volumes: list) -> bool:
    """
    Flow/Price Divergence (silent accumulation signal):
      - 10-period close slope is negative (price falling)
      - 10-period volume slope is positive (volume rising)

    Uses simple linear regression slope via least-squares on a 10-point window.
    closes[0] and volumes[0] are the most recent values.
    """
    n = 10
    if len(closes) < n or len(volumes) < n:
        return False

    # Take the 10 most recent; reverse so index 0 = oldest, 9 = newest
    c_window = list(reversed(closes[:n]))
    v_window = list(reversed(volumes[:n]))

    def _slope(series: list) -> float:
        xs = list(range(len(series)))
        x_mean = sum(xs) / len(xs)
        y_mean = sum(series) / len(series)
        num = sum((xs[i] - x_mean) * (series[i] - y_mean) for i in range(len(series)))
        den = sum((xs[i] - x_mean) ** 2 for i in range(len(xs)))
        return num / den if den != 0 else 0.0

    close_slope  = _slope(c_window)
    volume_slope = _slope(v_window)

    return close_slope < 0 and volume_slope > 0


# ── Fallback helpers ─────────────────────────────────────────────────────────

def _empty() -> dict:
    return {
        "trend": "ranging",
        "volume_ratio": 1.0,
        "pct_from_52w_high": -10.0,
        "recent_catalyst": False,
        # SMC defaults
        "order_block": {"type": "none", "price_level": 0.0, "candles_ago": 0},
        "fvg": {"type": "none", "upper": 0.0, "lower": 0.0, "candles_ago": 0},
        "amd_phase": "trending",
        "flow_price_divergence": False,
    }


def _load_fixture(ticker: str) -> dict:
    path = os.path.join(os.path.dirname(__file__), "..", "fixtures", f"{ticker.lower()}.json")
    with open(path) as f:
        data = json.load(f)
    return data["price_action"]
