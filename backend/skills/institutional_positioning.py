"""
Institutional Positioning Intelligence — Skill 5.

Aggregates short interest trends, full-chain put/call ratio, and institutional
holder changes to compute a crowding score and positioning direction.

This replaces direct CFTC COT access with equivalent market-derived signals
that are more precise at the individual-stock level:

  - Short interest % of float  →  how crowded the bearish trade already is
  - Short interest month-over-month change  →  covering or building?
  - Institutional holder pctChange (top 10)  →  smart money accumulation/distribution
  - Put/Call ratio across all expirations  →  options positioning bias

COT Index equivalent:
  crowding_score 0–100 = (short_float * 4) + (holder_concentration * 0.5) + (PC_extreme * 30)
  crowded = score > 70  →  conviction_modifier = "downgrade"
"""

import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import logger

import yfinance as yf


def institutional_positioning(ticker: str) -> dict:
    if os.getenv("MOCK_MODE", "false").lower() == "true":
        return _load_fixture(ticker)
    return _fetch(ticker)


def _fetch(ticker: str) -> dict:
    stock = yf.Ticker(ticker)
    info = stock.info

    # ── Short Interest ────────────────────────────────────────────────────────
    logger.fetch("yfinance short interest", f"{ticker} float, ratio, month-over-month trend")

    shares_short = info.get("sharesShort", 0) or 0
    shares_short_prior = info.get("sharesShortPriorMonth", 0) or 0
    short_pct_float = round((info.get("shortPercentOfFloat", 0) or 0) * 100, 2)
    short_ratio = round(info.get("shortRatio", 0) or 0, 1)  # days-to-cover

    if shares_short_prior > 0:
        short_change_pct = (shares_short - shares_short_prior) / shares_short_prior * 100
    else:
        short_change_pct = 0.0

    short_covering = short_change_pct < -5.0   # >5% fewer shorts = potential squeeze
    short_increasing = short_change_pct > 5.0  # >5% more shorts = growing bear bet
    short_crowded = short_pct_float > 8.0      # >8% float shorted = significant crowding


    # ── Institutional Holder Changes ──────────────────────────────────────────
    logger.fetch("yfinance institutional holders", f"{ticker} 13F holder accumulation/distribution")

    accumulating_count = 0
    distributing_count = 0
    top_holders = []

    try:
        holders = stock.institutional_holders
        if holders is not None and not holders.empty:
            for _, row in holders.head(10).iterrows():
                pct_change = float(row.get("pctChange", 0) or 0)
                holder_name = str(row.get("Holder", ""))
                pct_held = float(row.get("pctHeld", 0) or 0) * 100

                if pct_change > 0.01:
                    accumulating_count += 1
                elif pct_change < -0.01:
                    distributing_count += 1

                top_holders.append({
                    "name": holder_name,
                    "pct_held": round(pct_held, 2),
                    "pct_change": round(pct_change * 100, 2),
                })
    except Exception as e:
        logger.warn(f"Institutional holders fetch failed: {e}")

    if accumulating_count > distributing_count:
        institutional_bias = "accumulating"
    elif distributing_count > accumulating_count:
        institutional_bias = "distributing"
    else:
        institutional_bias = "neutral"


    # ── Put/Call Ratio (all expirations) ──────────────────────────────────────
    logger.fetch("yfinance options chain", f"{ticker} full P/C ratio across 5 expirations")

    total_call_oi = 0
    total_put_oi = 0

    try:
        expirations = stock.options[:5]
        for exp in expirations:
            chain = stock.option_chain(exp)
            total_call_oi += int(chain.calls["openInterest"].fillna(0).sum())
            total_put_oi += int(chain.puts["openInterest"].fillna(0).sum())
    except Exception as e:
        logger.warn(f"Options P/C ratio failed: {e}")

    pc_ratio = round(total_put_oi / total_call_oi, 2) if total_call_oi > 0 else 1.0

    if pc_ratio < 0.7:
        pc_signal = "bullish"   # more calls = market expects up
    elif pc_ratio > 1.2:
        pc_signal = "bearish"   # more puts = hedging or directional down
    else:
        pc_signal = "neutral"


    # ── Crowding Score (0–100) ────────────────────────────────────────────────
    # High crowding = late to the trade, downgrade conviction
    crowding_score = 0.0
    crowding_score += min(short_pct_float * 4, 40)                    # short float → up to 40pts
    top_pct_held = sum(h["pct_held"] for h in top_holders[:5])
    crowding_score += min(top_pct_held * 0.5, 30)                     # concentration → up to 30pts
    crowding_score += min(abs(pc_ratio - 1.0) * 30, 30)               # PC extreme → up to 30pts
    crowding_score = round(min(crowding_score, 100), 1)
    crowded = crowding_score > 70

    if crowded and institutional_bias == "distributing":
        conviction_modifier = "downgrade"
    elif not crowded and short_covering and institutional_bias == "accumulating":
        conviction_modifier = "upgrade"
    else:
        conviction_modifier = "neutral"

    return {
        "short_pct_float": short_pct_float,
        "short_ratio": short_ratio,
        "short_covering": short_covering,
        "short_increasing": short_increasing,
        "short_crowded": short_crowded,
        "institutional_bias": institutional_bias,
        "top_holders": top_holders[:5],
        "pc_ratio": pc_ratio,
        "pc_signal": pc_signal,
        "crowding_score": crowding_score,
        "crowded": crowded,
        "conviction_modifier": conviction_modifier,
    }


def _empty(ticker: str) -> dict:
    return {
        "short_pct_float": 0.0,
        "short_ratio": 0.0,
        "short_covering": False,
        "short_increasing": False,
        "short_crowded": False,
        "institutional_bias": "neutral",
        "top_holders": [],
        "pc_ratio": 1.0,
        "pc_signal": "neutral",
        "crowding_score": 50.0,
        "crowded": False,
        "conviction_modifier": "neutral",
    }


def _load_fixture(ticker: str) -> dict:
    import json
    path = os.path.join(os.path.dirname(__file__), "..", "fixtures", f"{ticker.lower()}.json")
    with open(path) as f:
        data = json.load(f)
    return data.get("institutional_positioning", _empty(ticker))
