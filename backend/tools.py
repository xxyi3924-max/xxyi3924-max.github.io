# Claude tool schemas (Anthropic format).
# The LLM adapters in backend/llm/ translate these to provider-specific formats.

_TICKER_PROP = {
    "ticker": {
        "type": "string",
        "description": "Stock ticker symbol, e.g. NVDA",
    }
}
_REQUIRED = {"type": "object", "properties": _TICKER_PROP, "required": ["ticker"]}

TOOLS = [
    {
        "name": "options_flow_scanner",
        "description": (
            "Scans unusual options activity for a ticker via yfinance. "
            "Returns unusual flag, sentiment_lean, sweep_detected, and top contracts. "
            "IMPORTANT: unusual=false does NOT stop the pipeline — call all remaining tools."
        ),
        "input_schema": _REQUIRED,
    },
    {
        "name": "social_buzz_scanner",
        "description": (
            "Checks Reddit, StockTwits, Yahoo Finance news, and Finviz for retail crowd awareness. "
            "crowd_aware=false means the crowd hasn't noticed yet — the early window. "
            "Always call this second."
        ),
        "input_schema": _REQUIRED,
    },
    {
        "name": "insider_tracker",
        "description": (
            "Fetches SEC 13F institutional filings and Form 4 insider transactions via EDGAR. "
            "Note: 13F only covers long equity positions — shorts and derivatives are invisible. "
            "Always call this third."
        ),
        "input_schema": _REQUIRED,
    },
    {
        "name": "price_action_context",
        "description": (
            "Returns Smart Money Concepts primitives: Order Block level, Fair Value Gap, AMD phase, "
            "plus classic trend/volume context. "
            "Also returns flow_price_divergence flag. Always call this fourth."
        ),
        "input_schema": _REQUIRED,
    },
    {
        "name": "institutional_positioning",
        "description": (
            "COT-equivalent crowding analysis: short interest % of float and trend, "
            "institutional holder accumulation/distribution, full-chain put/call ratio, "
            "and a crowding_score 0–100. "
            "crowded=true means the trade may already be overcrowded — cap conviction at medium. "
            "Always call this fifth."
        ),
        "input_schema": _REQUIRED,
    },
    {
        "name": "dark_pool_activity",
        "description": (
            "Detects off-exchange institutional block accumulation via volume absorption patterns, "
            "block trade scoring, flow/price divergence, and ATM options spread. "
            "vol_price_divergence=true is the clearest silent accumulation signal. "
            "Always call this sixth."
        ),
        "input_schema": _REQUIRED,
    },
]
