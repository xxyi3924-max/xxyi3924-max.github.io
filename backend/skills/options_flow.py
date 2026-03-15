import json
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import logger

import yfinance as yf


def options_flow(ticker: str) -> dict:
    if os.getenv("MOCK_MODE", "false").lower() == "true":
        logger.fetch("fixture file", f"fixtures/{ticker.lower()}.json")
        return _load_fixture(ticker)

    return _fetch_yfinance(ticker)


def _fetch_yfinance(ticker: str) -> dict:
    logger.fetch("Yahoo Finance options chain", f"yfinance — {ticker}")
    stock = yf.Ticker(ticker)

    expirations = stock.options
    if not expirations:
        logger.warn("No options expirations found")
        return _empty()

    logger.found("Expirations available", len(expirations))
    logger.found("Scanning nearest", f"{min(3, len(expirations))} expiry dates: {', '.join(expirations[:3])}")

    top_contracts = []
    total_unusual_premium = 0.0
    unusual_count = 0
    call_unusual = 0
    put_unusual = 0

    # Scan the nearest 3 expiration dates
    for expiry in expirations[:3]:
        try:
            chain = stock.option_chain(expiry)
            logger.found(f"  {expiry}", f"{len(chain.calls)} calls, {len(chain.puts)} puts")
        except Exception:
            logger.warn(f"Failed to fetch chain for {expiry}")
            continue

        for opt_type, df in [("call", chain.calls), ("put", chain.puts)]:
            for _, row in df.iterrows():
                volume = row.get("volume", 0) or 0
                oi = row.get("openInterest", 1) or 1
                last_price = row.get("lastPrice", 0) or 0

                vol_oi = round(volume / oi, 2)
                premium = last_price * volume * 100

                if vol_oi > 1.5 and volume > 100:
                    unusual_count += 1
                    total_unusual_premium += premium
                    if opt_type == "call":
                        call_unusual += 1
                    else:
                        put_unusual += 1

                    top_contracts.append({
                        "strike": float(row.get("strike", 0)),
                        "expiry": expiry,
                        "vol_oi_ratio": vol_oi,
                        "type": opt_type,
                    })

    top_contracts = sorted(top_contracts, key=lambda x: x["vol_oi_ratio"], reverse=True)[:5]

    if call_unusual > put_unusual:
        lean = "bullish"
    elif put_unusual > call_unusual:
        lean = "bearish"
    else:
        lean = "neutral"

    unusual = unusual_count >= 3
    logger.found("Unusual contracts found", unusual_count)
    logger.found("Calls unusual / Puts unusual", f"{call_unusual} / {put_unusual}")

    return {
        "unusual": unusual,
        "sentiment_lean": lean,
        "sweep_detected": unusual and total_unusual_premium > 500_000,
        "total_unusual_premium": round(total_unusual_premium, 2),
        "top_contracts": top_contracts,
    }


def _empty() -> dict:
    return {
        "unusual": False,
        "sentiment_lean": "neutral",
        "sweep_detected": False,
        "total_unusual_premium": 0.0,
        "top_contracts": [],
    }


def _load_fixture(ticker: str) -> dict:
    path = os.path.join(os.path.dirname(__file__), "..", "fixtures", f"{ticker.lower()}.json")
    with open(path) as f:
        data = json.load(f)
    return data["options_flow"]
