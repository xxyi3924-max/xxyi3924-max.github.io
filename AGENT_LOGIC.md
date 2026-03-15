# Smart Money Agent — Logic, Reasoning & Rationale

---

## Was the AI Actually Thinking?

**Short answer: No — not before the prompt rewrite.**

The original prompt said `ALWAYS call first`, `ALWAYS call second` six times in a numbered list. GPT-4o was executing a fixed sequence. It had no choice in tool selection or ordering. The only real reasoning happened at the very end, when it saw all 6 results and wrote the verdict.

The scoring table made it worse. By specifying exact point values (`+2 if unusual=true AND bullish...`), we replaced LLM judgment with arithmetic that a simple Python `if/else` could do. The model was a pipeline executor, not an analyst.

**What changed after the rewrite:**

The prompt now requires the LLM to write after every tool result:

> *"Hypothesis so far: [what I think is happening and why]"*

This forces genuine integration of each result before the next tool call. The hypothesis shapes which tool gets called next and what the LLM is looking to confirm or refute. The call order is now a recommendation the LLM can deviate from — not a rigid script.

---

## How the Full System Works

### End-to-End Flow

```
User types ticker → FastAPI /analyze → SSE stream opens
                                            │
                                            ▼
                              LLM Orchestrator (GPT-4o / Claude Sonnet)
                              reads system prompt, forms null hypothesis
                                            │
                        ┌───────────────────┴───────────────────┐
                        │  Agentic tool-use loop (multi-round)  │
                        │                                       │
                        │  Round 1  → call tool                 │
                        │           → get result                │
                        │           → write hypothesis          │
                        │           → decide next tool          │
                        │                                       │
                        │  Round 2–6  → same pattern            │
                        │                                       │
                        │  Final round  → no more tool calls    │
                        │              → write verdict JSON     │
                        └───────────────────────────────────────┘
                                            │
                          SSE events stream to frontend in real time:
                          tool_call → tool_result → reasoning → verdict
                                            │
                                            ▼
                              Frontend renders skill steps,
                              reasoning stream, verdict card
```

### The Agentic Loop in Code

```python
while True:
    response = llm.call(messages, tools)       # LLM decides: call a tool or stop
    if response.finish_reason == "stop":
        return parse_verdict(response.content) # done — emit verdict
    for tool_call in response.tool_calls:
        result = execute_skill(tool_call.name) # run the actual data skill
        messages.append(tool_result)           # feed result back to LLM
                                               # loop — LLM sees result and decides next
```

The LLM controls the loop. It can call tools in any order, call one per turn or several, and stops when it has enough to write the verdict. We do not force it through a fixed sequence.

---

## The 6-Skill Pipeline — What Each Detects and Why

Institutions move in a predictable sequence:

```
Dark pool prints → Options sweeps → 13F filings → Retail awareness
(immediate)        (immediate)      (45d lag)      (too late)
```

The system captures all four layers. Each skill fills a blind spot the others cannot:

### Skill 1 — Options Flow (`options_flow_scanner`)

**What it detects:** Unusual options activity — high vol/OI contracts at specific strikes, large premium sweeps.

**Why it matters:** When a fund buys 500 deep-ITM calls in a single sweep, they are making a large directional bet. This is the loudest, most visible institutional signal.

**Limitation:** Options can also be hedges. A fund holding 10M shares of NVDA buying puts is not bearish — it is protecting a long position. Options alone cannot tell you direction without corroboration.

**Scoring contribution:** +2 if unusual + bullish lean, +1 if unusual + neutral, 0 if no unusual activity. Does **not** veto the pipeline — institutions frequently accumulate via dark pools without touching the options market.

---

### Skill 2 — Social Buzz (`social_buzz_scanner`)

**What it detects:** Whether the retail crowd has already noticed the stock — Reddit activity, StockTwits sentiment, news headlines, Yahoo Finance article volume.

**Why it matters:** The entire thesis of this project is finding the gap between institutional positioning and retail awareness. `crowd_aware=false` means that gap is still open. `crowd_aware=true` means the edge is shrinking or gone.

**Sources:** Reddit (public JSON), StockTwits (curl_cffi Chrome impersonation to bypass Cloudflare), Finviz headlines, Yahoo Finance news via yfinance. A Haiku/gpt-4o-mini sub-agent interprets raw data into a structured signal.

**What "informed vs hype" means:**
- `informed` — posts discuss filings, earnings, institutional moves (sophisticated crowd)
- `hype` — price targets, moon emojis, meme language (retail FOMO)
- `none` — almost no activity (earliest possible window)

---

### Skill 3 — Insider Tracker (`insider_tracker`)

**What it detects:** SEC 13F institutional filings (quarterly long position disclosures) and Form 4 insider transactions (C-suite buying/selling their own stock).

**Why it matters:** 13F filings are ground truth — they are legally required disclosures of what funds actually own. When multiple funds increase their holdings in the same quarter, that is confirmed accumulation, not a guess.

**Form 4 (insider buys) are the strongest signal of all.** A CEO buying $5M of their own stock in the open market is putting their personal money where their mouth is.

**Known limitations:**
- 13F is long-only. Shorts, futures, and derivatives are invisible. A fund marked "accumulating" may simultaneously hold short positions via swaps — treat as one layer, not proof.
- 45-day reporting lag. Filings show where funds *were* positioned at quarter end, not where they are today.
- `shares_delta=0` is expected in the output — EDGAR rate-limits archive XML parsing.

---

### Skill 4 — Price Action / SMC (`price_action_context`)

**What it detects:** Where institutions actually entered the stock, using Smart Money Concepts (SMC) primitives on daily OHLCV data.

**Why SMC over standard resistance levels:**

Generic resistance (`near_resistance: bool`) only tells you price is near a past level — not *why* it matters or *who* is positioned there. SMC replaces this with:

| Concept | What it is | Why it matters |
|---|---|---|
| **Order Block (OB)** | Last red candle before a bullish Break of Structure | Institutions built their position here — they will defend it as support |
| **Fair Value Gap (FVG)** | 3-candle price gap where candle[i+2].low > candle[i].high | Price imbalances that statistically fill ~70% of the time — a magnet for price |
| **AMD Phase** | Accumulation → Manipulation fakeout → Distribution | Identifies which stage of the institutional cycle price is currently in |
| **Flow/Price Divergence** | Volume slope rising + price slope falling | The clearest behavioral signature of silent accumulation |

**Practical reading:**
- `amd_phase=accumulation` + `order_block=bullish` near current price = institutions defending their entry level
- `fvg=bullish` below current price = institutions will likely return to that level before moving higher
- `flow_price_divergence=true` = someone is absorbing selling pressure without moving price — classic dark pool behavior

---

### Skill 5 — Institutional Positioning (`institutional_positioning`)

**What it detects:** Whether the institutional trade is already crowded — using short interest trend, institutional holder changes, and full-chain put/call ratio as a COT Index equivalent.

**Why crowding matters:** Three signals agreeing can mean two completely different things:
1. We are **early** — institutions are quietly building, crowd hasn't noticed, trade isn't crowded
2. We are **late** — institutions are already heavily positioned, trade is overcrowded, the move is mostly done

Without a crowding check, the system cannot distinguish these. This is the "Critical Logic Flaw 3" from the research gap analysis.

**The three crowding inputs:**

| Input | What it measures | High reading means |
|---|---|---|
| `short_pct_float` | % of float currently sold short | >8% = significant short crowding |
| `short_covering` | Short interest fell >5% month-over-month | Shorts closing = potential squeeze setup |
| `institutional_bias` | Top 10 holder pctChange direction | Distributing = smart money exiting |
| `pc_ratio` | Full-chain put/call OI ratio | >1.2 = heavy hedging or directional puts |

**Crowding score (0–100):** Composite of above. Score > 70 = `crowded=true` → **conviction capped at "medium" regardless of how many other signals agree.** An overcrowded trade is a late trade.

**Why CFTC COT is not used:** All known CFTC download URLs return 404 — the site was restructured. The yfinance-based approach is actually more precise for individual stocks because CFTC COT covers index futures (market-wide), not individual tickers.

---

### Skill 6 — Dark Pool Activity (`dark_pool_activity`)

**What it detects:** Off-exchange block accumulation inferred from behavioral signatures in OHLCV data — without direct access to FINRA TRF files (which are behind Cloudflare).

**Why dark pool matters:** It answers the question the options flow skill cannot: *is this a sustained institutional positioning pattern or a one-time event?* A single options sweep could be a hedge. Three days of volume absorption at the same price level is a pattern.

**The four detection methods:**

| Method | Signal | Interpretation |
|---|---|---|
| **Volume Absorption** | vol > 1.5x avg AND daily range < 1% | Institution absorbing supply without moving price |
| **Block Trade Score** | vol > 2x avg AND price move < 1.5% = +3pts | Sustained block activity over 10 days |
| **Vol/Price Divergence** | Volume slope positive + price slope negative | The clearest "silent accumulation" signature |
| **ATM Options Spread** | Tight near-ATM spread | Market makers providing institutional liquidity |

**Why FINRA TRF is not used:** The raw Reg SHO files at `regsho.finra.org` are behind Cloudflare and return HTML regardless of impersonation method. Volume absorption patterns are a behavioral proxy — they capture the *effect* of dark pool activity without needing direct TRF access.

---

## The Core Signal — Silent Accumulation Window

This is the scenario the entire system is designed to surface:

```
price_action.trend          = "downtrend"    ← price is falling (retail selling)
dark_pool.vol_price_div     = true           ← volume rising while price falls
options_flow.unusual        = true           ← directional bet placed
options_flow.sentiment_lean = "bullish"      ← someone expects up
insider_tracker.direction   = "accumulating" ← confirmed in 13F filings
social_buzz.crowd_aware     = false          ← retail hasn't noticed yet
institutional.crowded       = false          ← we are early, not late
─────────────────────────────────────────────────────────────────────
VERDICT: signal_type=accumulation, conviction=HIGH
         bullish_divergence=true

Explanation: "While the price has been falling, smart money appears to be
quietly accumulating. [Fund names] have increased their positions while retail
attention remains low — the crowd hasn't noticed yet."
```

This fires rarely. When it does, every independent data layer is pointing the same direction, which is the actual definition of a high-conviction signal.

---

## Known Weaknesses

| Weakness | Impact | Mitigation |
|---|---|---|
| 13F is 45-day lagging | Direction confirmed but not current | Dark pool divergence provides real-time corroboration |
| 13F long-only | A "accumulating" fund may be net short via derivatives | Skill 5 short interest cross-reference partially compensates |
| Dark pool is a proxy | No direct TRF data | Volume absorption catches the behavioral effect of block trades |
| LLM confidence ≠ accuracy | Model states verdicts confidently regardless of data quality | `conviction="low"` for thin data; no backtesting yet |
| yfinance rate limits | Repeated rapid requests throttled | MOCK_MODE for demos; fixture data for testing |

---

## Summary Table

| Layer | Skill | Data Source | Temporal | Key Output |
|---|---|---|---|---|
| Options | options_flow | yfinance | Real-time | unusual, sentiment_lean |
| Crowd | social_buzz | Reddit/StockTwits/YF/Finviz | Real-time | crowd_aware, informed_vs_hype |
| Filings | insider_tracker | SEC EDGAR | 45-day lag | direction, notable_funds |
| Structure | price_action | Twelve Data | Real-time | OB, FVG, AMD, divergence |
| Crowding | institutional_positioning | yfinance | Bi-monthly | crowding_score, crowded |
| Dark pool | dark_pool | yfinance | Real-time | absorption, vol_price_divergence |
