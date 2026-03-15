# Smart Money Agent — Claude Code Context

> This file is automatically loaded by Claude Code as project context.
> Keep it up to date when architecture, skills, or data sources change.

---

## Project Thesis

Institutional investors move in a predictable sequence:
1. **Dark pool accumulation** — quiet block trades, no price impact
2. **Options positioning** — unusual sweeps at key strikes
3. **13F / Form 4 filings** — public 45 days after quarter-end
4. **Retail crowd awareness** — Reddit, CNBC, StockTwits traffic spikes

The **window between step 1 and step 3** is where alpha lives. This system
detects that window algorithmically by correlating six independent signal
layers. Any one layer is noisy. All six in agreement is a high-conviction event.

**One-line pitch:** An AI agent that correlates dark pool prints, options flow,
SEC filings, price structure, institutional crowding, and social sentiment to
surface smart money signals before the crowd notices.

---

## Architecture

```
User (ticker input)
    │
    ▼
React Frontend  ──SSE stream──▶  FastAPI /analyze
(Tab: Analysis)                  (CORS, API key auth,
(Tab: Terminal ◀── /logs SSE)     MOCK_MODE flag)
                                      │
                                      ▼
                          Multi-provider LLM Orchestrator
                          (Claude Sonnet / GPT-4o / Gemini Flash)
                          Tool-use agentic loop — calls ALL 6 skills
                                      │
          ┌───────────┬───────────┬───┴───────┬───────────┬───────────┐
          │           │           │           │           │           │
    Skill 1       Skill 2     Skill 3     Skill 4     Skill 5     Skill 6
  options_flow  social_buzz  insider_    price_      instit.     dark_pool
  (yfinance)    (Reddit/ST/  tracker     action      position.   (yfinance
                YF/Finviz)   (EDGAR)     (Twelve     (yfinance   OHLCV +
                             13F+Form4   Data+SMC)   SI+PC+      absorption
                                                     holders)    patterns)
                                      │
                                      ▼
                             Verdict  (JSON SSE event)
                     signal_type · conviction · explanation
                     bullish_divergence · cot_crowded
```

### Two-tier LLM design

| Role | Provider | Model | Purpose |
|------|----------|-------|---------|
| Orchestrator | Claude | `claude-sonnet-4-20250514` | Full 6-skill agentic loop, cross-signal reasoning, verdict |
| Orchestrator | OpenAI | `gpt-4o` | Same role when `LLM_PROVIDER=openai` (default) |
| Orchestrator | Gemini | `gemini-2.0-flash` | Same role when `LLM_PROVIDER=gemini` |
| Sub-agent | Claude | `claude-haiku-4-5-20251001` | Social buzz raw-data interpretation only |
| Sub-agent | OpenAI | `gpt-4o-mini` | Same role for OpenAI provider |

---

## 6-Skill Pipeline

### Why 6 skills and why this order

The orchestrator calls **all six skills unconditionally**. Options flow no
longer vetoes the pipeline — institutions frequently build positions via dark
pools and gradual 13F accumulation without triggering unusual options flags.
Each skill fills a specific temporal gap and blind spot:

```
Signal              Temporal layer   Blind spot filled
──────────────────  ───────────────  ────────────────────────────────────────────
options_flow        Real-time        Directional intent — but noisy, can be hedges
social_buzz         Real-time        Crowd awareness — is alpha window still open?
insider_tracker     Quarterly lag    Confirmed long equity positioning (13F)
price_action        Real-time        Where institutions entered (SMC primitives)
instit_positioning  Bi-monthly       Are we early or late? (COT Index equivalent)
dark_pool           Real-time        Silent block accumulation off-exchange
```

The **highest-conviction signal** fires when:
- `options_flow.unusual=true` (directional options bet placed)
- `insider_tracker.direction=accumulating` (confirmed in filings)
- `dark_pool.vol_price_divergence=true` (price down, volume up = silent buy)
- `institutional_positioning.crowded=false` (not overcrowded yet)
- `social_buzz.crowd_aware=false` (retail hasn't noticed)

---

## Skill Contracts

### Skill 1 — options_flow_scanner (`skills/options_flow.py`)
```python
{
    "unusual": bool,
    "sentiment_lean": "bullish" | "bearish" | "neutral",
    "sweep_detected": bool,
    "total_unusual_premium": float,
    "top_contracts": [{"strike", "expiry", "vol_oi_ratio", "type"}]
}
```
**Source:** yfinance. Scans nearest 3 expiries. vol/OI > 1.5 AND volume > 100 = unusual.
`unusual=True` requires ≥ 3 unusual contracts.
**Key change:** `unusual=False` no longer stops the pipeline.

---

### Skill 2 — social_buzz_scanner (`skills/social_buzz.py`)
```python
{
    "raw_metrics": {
        "reddit_post_count_48h": int,
        "reddit_top_post_score": int,
        "stocktwits_bull_ratio": float,
        "stocktwits_message_count": int,
        "headlines": [str],
        "yf_article_count": int,
        "yf_bull_ratio": float,
        "yf_sample_headlines": [str]
    },
    "interpretation": str,
    "crowd_aware": bool,
    "informed_vs_hype": "informed" | "hype" | "mixed" | "none"
}
```
**Sources:** Reddit (public JSON), StockTwits (curl_cffi Chrome impersonation for Cloudflare),
Finviz, yfinance news.
**X/Twitter retired:** x-client-transaction-id HMAC anti-scraping (deployed 2024) blocks all
cookie-based approaches — Playwright, curl_cffi, and twikit all fail.

---

### Skill 3 — insider_tracker (`skills/insider_tracker.py`)
```python
{
    "net_institutional_direction": "accumulating" | "distributing" | "neutral",
    "recent_13f_changes": [{"fund", "action", "shares_delta", "filed_date"}],
    "insider_buys": [{"name", "role", "shares", "value_usd", "date"}],
    "notable_funds": [str]
}
```
**Source:** SEC EDGAR (company_tickers.json CIK lookup, Form 4 XML, EFTS 13F search).
**13F blind spot:** Long-only. Shorts and derivatives are invisible. Skill 5 provides
short-side context via FINRA short interest as cross-reference.

---

### Skill 4 — price_action_context (`skills/price_action.py`)
```python
{
    "trend": "uptrend" | "downtrend" | "ranging",
    "volume_ratio": float,
    "pct_from_52w_high": float,
    "recent_catalyst": bool,
    # SMC primitives
    "order_block": {"type": "bullish"|"bearish"|"none", "price_level": float, "candles_ago": int},
    "fvg": {"type": "bullish"|"bearish"|"none", "upper": float, "lower": float, "candles_ago": int},
    "amd_phase": "accumulation" | "manipulation" | "distribution" | "trending",
    "flow_price_divergence": bool
}
```
**Source:** Twelve Data (60-day OHLCV).
**Order Block:** Last opposite-color candle before a Break of Structure.
**Fair Value Gap:** 3-candle imbalance (candle[i+2].low > candle[i].high for bullish).
**AMD Model:** ATR-based range analysis detecting accumulation → manipulation fakeout → distribution.
**Flow divergence:** numpy polyfit slopes — volume up + price down = silent accumulation.

---

### Skill 5 — institutional_positioning (`skills/institutional_positioning.py`)
```python
{
    "short_pct_float": float,
    "short_ratio": float,
    "short_covering": bool,
    "short_increasing": bool,
    "short_crowded": bool,
    "institutional_bias": "accumulating" | "distributing" | "neutral",
    "top_holders": [{"name", "pct_held", "pct_change"}],
    "pc_ratio": float,
    "pc_signal": "bullish" | "bearish" | "neutral",
    "crowding_score": float,   # 0–100
    "crowded": bool,           # score > 70 → cap conviction at medium
    "conviction_modifier": "upgrade" | "downgrade" | "neutral"
}
```
**Source:** yfinance (`stock.info`, `institutional_holders`, `option_chain` × 5 expirations).
**COT Index equivalent:** CFTC COT URLs all return 404 (site restructured). yfinance short
interest + P/C ratio + holder changes provide equivalent crowding detection at ticker level.
**Crowding rule:** `crowded=True` → cap final conviction at "medium" regardless of signal agreement.

---

### Skill 6 — dark_pool_activity (`skills/dark_pool.py`)
```python
{
    "absorption_detected": bool,
    "absorption_events": [{"date", "vol_ratio", "range_pct", "direction"}],
    "estimated_direction": "bullish" | "bearish" | "neutral" | "unknown",
    "block_trade_score": int,   # 0–10
    "vol_price_divergence": bool,
    "options_spread_signal": "tight" | "normal" | "wide" | "unavailable",
    "high_dark_pool_activity": bool
}
```
**Source:** yfinance OHLCV (30-day). FINRA TRF raw files are behind Cloudflare.
**Absorption:** vol > 1.5x avg AND daily range < ATR×0.6 = institution absorbing supply.
**Block score:** 10-day rolling — vol > 2x avg AND price move < ATR×0.4 = +3 pts per event.
**Vol/Price divergence:** volume slope positive + price slope negative = silent accumulation.
**ATM spread:** tight near-ATM options spread = institutional liquidity present.
**ATR-relative thresholds:** hardcoded 1% replaced with stock's own avg daily range ×0.6/0.4
to handle volatile large-caps (NVDA avg range 2–4%).

---

## Orchestrator Scoring

```
Signal                  Bullish pts  Notes
──────────────────────  ───────────  ──────────────────────────────────────
options_flow            0, +1, +2    unusual + lean
insider_tracker         0, +1, +2    accumulating + insider_buys
price_action            0, +1, +2    trend + OB/FVG near price
social_buzz             -1, +1, +2   crowd_aware=true subtracts 1
institutional_posit.    -2, 0, +1, +2  crowded=true → -2 override
dark_pool               0, +1, +2    absorption + divergence
──────────────────────
≥ 7 pts + not crowded  →  high conviction
4–6 pts OR crowded     →  medium conviction
< 4 pts                →  low conviction
```

**Bullish divergence** (highest-value signal): downtrend + bullish options +
accumulating 13F, OR `vol_price_divergence=true` → `bullish_divergence: true` in verdict.

---

## Verdict Output

```python
{
    "signal_type": "accumulation" | "distribution" | "hedge" | "noise",
    "conviction": "low" | "medium" | "high",
    "explanation": str,
    "watch_for": str,
    "skills_used": [str],
    "bullish_divergence": bool,
    "cot_crowded": bool
}
```

---

## File Structure

```
smart-money-agent/
├── CLAUDE.md
├── backend/
│   ├── main.py                            ← FastAPI: /health, /analyze, /logs (SSE)
│   ├── agent.py                           ← LLM loop, thread-safe queue bridge
│   ├── tools.py                           ← 6 tool schemas (Anthropic format)
│   ├── prompts.py                         ← SYSTEM_PROMPT + SOCIAL_BUZZ_SUBAGENT_PROMPT
│   ├── logger.py                          ← Thread-safe queue → /logs SSE
│   ├── llm/
│   │   ├── __init__.py  base.py
│   │   ├── claude.py  openai.py  gemini.py
│   ├── skills/
│   │   ├── __init__.py                    ← execute_skill() dispatcher
│   │   ├── options_flow.py                ← Skill 1
│   │   ├── social_buzz.py                 ← Skill 2
│   │   ├── insider_tracker.py             ← Skill 3
│   │   ├── price_action.py                ← Skill 4 (+ SMC)
│   │   ├── institutional_positioning.py   ← Skill 5 (NEW)
│   │   └── dark_pool.py                   ← Skill 6 (NEW)
│   └── fixtures/  nvda.json  tsla.json  aapl.json
└── frontend/
    └── src/
        ├── App.tsx                        ← Analysis + Terminal tabs
        ├── hooks/  useAgentStream.ts  useLogsStream.ts
        └── components/  SkillStep.tsx  Terminal.tsx  VerdictCard.tsx  ReasoningStream.tsx
```

---

## Environment Variables

```bash
LLM_PROVIDER=openai            # claude | openai | gemini
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-proj-...
GEMINI_API_KEY=...
TWELVE_DATA_API_KEY=...        # twelvedata.com — free 800 calls/day
API_KEY=...                    # shared secret, passed as ?api_key= query param
MOCK_MODE=false                # true = use fixtures, skip external APIs
```

No key needed: SEC EDGAR, StockTwits (curl_cffi), Reddit, yfinance, Finviz.

---

## Known Limitations & Retired Sources

| Source | Status | Reason |
|--------|--------|--------|
| Polygon.io | Retired | Options snapshot blocked on free tier |
| X / Twitter | Retired | x-client-transaction-id HMAC (2024) blocks all cookie scrapers |
| CFTC COT | Retired | All known URLs return 404 (site restructured) |
| FINRA RegSHO | Retired | Behind Cloudflare, raw files inaccessible |
| 13F long-only | Known gap | Shorts/derivatives invisible; Skill 5 partially compensates |
| Dark pool proxy | Known gap | FINRA TRF inaccessible; volume absorption is behavioral proxy |

---

## Backtest System (Planned)

The goal is to validate signal quality historically — did high-conviction signals
actually precede price moves? This requires point-in-time historical data to avoid
lookahead bias.

### Data sources under consideration

| Source | Data available | Access |
|--------|----------------|--------|
| Bloomberg Terminal | Full OHLCV, options chain history, 13F point-in-time, dark pool TRF prints | Pending — institutional access being arranged |
| yfinance | OHLCV only (no historical options, no point-in-time fundamentals) | Free, already integrated |
| EDGAR archives | Historical 13F XML filings (point-in-time) | Free, public |

### Architecture sketch

```
Bloomberg BDH / BDS  ──▶  historical_data_loader.py
    (OHLCV + options + TRF)         │
                                    ▼
                         backtest_runner.py
                         for each date in range:
                           - run all 6 skills on historical snapshot
                           - record verdict + conviction
                           - compare to forward return (1d, 5d, 20d)
                                    │
                                    ▼
                         results/   ← CSV + JSON
                         backtest_report.py  ← precision/recall per signal
```

### Key design constraints
- **Point-in-time discipline:** 13F data must use the filing date, not the period end date
  (45-day lag). Options data must use the exact expiry chain available on that date.
- **Forward return windows:** 1-day (momentum), 5-day (swing), 20-day (position).
- **Signal isolation:** test each skill independently before combining, to measure
  incremental value of each layer.
- **Bloomberg access:** if Terminal access is confirmed, use `blpapi` Python SDK.
  Historical options chain via `BDH("NVDA US Equity", "OPT_CHAIN", start, end)`.

---

## Running

```bash
# Backend
cd backend && ../.venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000

# Frontend
cd frontend && npm run dev
```
