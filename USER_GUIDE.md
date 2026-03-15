# Smart Money Agent — User Guide

> Personal reference guide covering setup, operation, signal interpretation, API, and architecture.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Prerequisites](#2-prerequisites)
3. [Installation & Setup](#3-installation--setup)
4. [Environment Configuration](#4-environment-configuration)
5. [Running the App](#5-running-the-app)
6. [Mock Mode vs Live Mode](#6-mock-mode-vs-live-mode)
7. [Switching LLM Providers](#7-switching-llm-providers)
8. [How to Interpret Signals](#8-how-to-interpret-signals)
9. [The 4 Skills Explained](#9-the-4-skills-explained)
10. [Console Log Reference](#10-console-log-reference)
11. [API Reference](#11-api-reference)
12. [Network Sharing](#12-network-sharing)
13. [File Structure Reference](#13-file-structure-reference)
14. [Troubleshooting](#14-troubleshooting)

---

## 1. Project Overview

Smart Money Agent detects institutional investor activity for a given stock ticker by correlating four data sources:

- **Options flow** — unusual options sweeps (via Yahoo Finance)
- **Social buzz** — Reddit, StockTwits, Finviz headlines, X/Twitter (via twscrape)
- **Insider tracker** — SEC EDGAR 13F institutional filings + Form 4 insider transactions
- **Price action** — trend, volume ratio, 52-week high proximity (via Twelve Data)

An LLM orchestrator (Claude / OpenAI / Gemini — your choice) calls these tools in sequence, reasons about the combined signal, and outputs a plain-English verdict.

**Core thesis:** Institutions move first — options sweeps appear before SEC filings, and SEC filings appear before retail attention. The system finds the gap between step 1 and step 2.

---

## 2. Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Python | 3.13 | 3.14 not supported (PyO3/pydantic-core issue) |
| Node.js | 18+ | For the React frontend |
| npm | 9+ | Comes with Node |

---

## 3. Installation & Setup

### Backend

```bash
cd "/Users/xiao/Documents/Projects/Smart Money/Dev"

# Create virtual environment (Python 3.13)
python3.13 -m venv .venv

# Activate
source .venv/bin/activate

# Install dependencies
pip install -r backend/requirements.txt

# Copy and fill in environment variables
cp backend/.env.example backend/.env
```

### Frontend

```bash
cd "/Users/xiao/Documents/Projects/Smart Money/Dev/frontend"
npm install
```

---

## 4. Environment Configuration

File: `backend/.env`

```env
# ── LLM Provider ──────────────────────────────────────────
LLM_PROVIDER=openai              # claude | openai | gemini

# ── LLM API Keys (only the chosen provider needs a real key) ──
ANTHROPIC_API_KEY=sk-ant-...     # console.anthropic.com
OPENAI_API_KEY=sk-...            # platform.openai.com
GEMINI_API_KEY=...               # aistudio.google.com

# ── Data APIs ─────────────────────────────────────────────
POLYGON_API_KEY=...              # NOT USED — replaced by yfinance
TWELVE_DATA_API_KEY=...          # twelvedata.com — free, 800 calls/day

# ── Social ────────────────────────────────────────────────
REDDIT_USER_AGENT=smartmoney-agent/1.0   # no key needed, public API

# X (Twitter) — free account credentials for twscrape
X_USERNAME=your_x_username
X_PASSWORD=your_x_password
X_EMAIL=                         # optional, only if X sends verification
X_EMAIL_PASSWORD=                # optional

# ── Dev ───────────────────────────────────────────────────
MOCK_MODE=false                  # true = use fixture files, no real API calls
API_KEY=your_secret_key          # protects /analyze endpoint on local network
```

File: `frontend/.env`

```env
VITE_BACKEND_URL=http://100.66.197.82:8000   # your local IP
VITE_API_KEY=your_secret_key                  # must match backend API_KEY
```

---

## 5. Running the App

### Start the backend

```bash
cd "/Users/xiao/Documents/Projects/Smart Money/Dev/backend"

# Local only (default)
../.venv/bin/uvicorn main:app --port 8000 --reload

# Exposed to local network
../.venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### Start the frontend

```bash
cd "/Users/xiao/Documents/Projects/Smart Money/Dev/frontend"

# Local only
npm run dev

# Exposed to local network
npm run dev -- --host
```

### Access

| Interface | URL |
|---|---|
| Frontend UI | `http://localhost:5173` |
| Backend API | `http://localhost:8000` |
| Health check | `http://localhost:8000/health` |
| Network (others) | `http://100.66.197.82:5173` |

> Find your local IP: `ipconfig getifaddr en0`

---

## 6. Mock Mode vs Live Mode

| | Mock Mode (`MOCK_MODE=true`) | Live Mode (`MOCK_MODE=false`) |
|---|---|---|
| Data source | `backend/fixtures/{ticker}.json` | Real APIs |
| LLM | Still runs live | Runs live |
| API keys needed | Only LLM key | All data API keys |
| Supported tickers | NVDA, TSLA, AAPL only | Any ticker |
| Speed | Fast | 15–30 seconds |

### Mock fixtures

Pre-built scenarios:

| Ticker | Signal | What it tests |
|---|---|---|
| `NVDA` | Accumulation (high conviction) | All 4 skills fire, crowd unaware |
| `TSLA` | Distribution (medium conviction) | Bearish options + institutional selling |
| `AAPL` | Noise | Options unusual=false → agent stops early |

To add a new fixture, create `backend/fixtures/{ticker}.json` following the structure of an existing one.

---

## 7. Switching LLM Providers

Change one line in `backend/.env`:

```env
LLM_PROVIDER=claude    # Sonnet 4 orchestrator + Haiku sub-agent
LLM_PROVIDER=openai    # gpt-4o orchestrator + gpt-4o-mini sub-agent
LLM_PROVIDER=gemini    # gemini-2.0-flash for both
```

Then restart the backend. No other code changes needed.

### Model mapping

| Role | Claude | OpenAI | Gemini |
|---|---|---|---|
| Orchestrator | claude-sonnet-4-20250514 | gpt-4o | gemini-2.0-flash |
| Social sub-agent | claude-haiku-4-5-20251001 | gpt-4o-mini | gemini-2.0-flash |

The sub-agent is only used inside `social_buzz` to interpret raw Reddit/StockTwits/X data into a structured signal before the orchestrator sees it.

---

## 8. How to Interpret Signals

### Signal types

| Signal | Meaning | What to look for |
|---|---|---|
| `accumulation` | Institutions quietly buying | Options bullish + 13F shows buying + crowd unaware |
| `distribution` | Institutions selling | Options bearish + 13F shows selling |
| `hedge` | Bearish options but funds still holding | Protective puts on existing long position |
| `noise` | No clear signal | Signals contradict, or no unusual options activity |

### Conviction levels

| Conviction | Condition |
|---|---|
| `high` | 3+ signals agree **AND** `crowd_aware=false` |
| `medium` | 2 signals agree |
| `low` | Mixed signals or only 1 signal |

### The key insight

The highest-value signal is:
```
options_flow.unusual = true
+ insider_tracker.direction = "accumulating"
+ social_buzz.crowd_aware = false
```
This means: institutions are quietly positioning, the crowd hasn't noticed yet. That's the window.

### What `crowd_aware=false` means

Reddit posts < 20 in 48h AND StockTwits messages < 100. The stock is not being discussed heavily on retail platforms — which is the signal that smart money is moving before retail awareness.

---

## 9. The 4 Skills Explained

### Skill 1 — Options Flow (`options_flow_scanner`)

**Source:** Yahoo Finance (`yfinance`)
**What it does:** Fetches option chains for the nearest 3 expiry dates, computes vol/OI ratio for each contract. Flags contracts with vol/OI > 1.5 and volume > 100 as unusual.

**Key outputs:**
- `unusual` — true if 3+ unusual contracts found
- `sentiment_lean` — bullish/bearish/neutral based on calls vs puts count
- `sweep_detected` — true if unusual=true AND total premium > $500k
- `total_unusual_premium` — dollar value of unusual activity

**Orchestrator rule:** If `unusual=false`, stop immediately and return `signal_type=noise`.

---

### Skill 2 — Social Buzz (`social_buzz_scanner`)

**Sources:** Reddit (public JSON API), StockTwits (public API), Finviz (scrape), X/Twitter (twscrape)
**What it does:** Collects raw social metrics, then passes them to a cheap LLM sub-agent that interprets them into a structured signal.

**Key outputs:**
- `crowd_aware` — true if retail is actively discussing this stock
- `informed_vs_hype` — informed / hype / mixed / none
- `interpretation` — 2-3 sentence plain English summary from sub-agent

**Note:** X requires a real account in `X_USERNAME` / `X_PASSWORD`. If not configured, X data returns empty and the other 3 sources still work.

---

### Skill 3 — Insider Tracker (`insider_tracker`)

**Source:** SEC EDGAR (no API key needed)
**What it does:**
1. Looks up company CIK via `sec.gov/files/company_tickers.json`
2. Fetches Form 4 filings (insider transactions) from `data.sec.gov/submissions/CIK{cik}.json`, parses XML for acquisitions only (code "A")
3. Searches EDGAR EFTS for recent 13F-HR institutional filings mentioning the ticker

**Key outputs:**
- `net_institutional_direction` — accumulating / distributing / neutral
- `recent_13f_changes` — list of funds with filing dates
- `insider_buys` — list of insiders who bought shares in last 90 days
- `notable_funds` — fund names from 13F filings

**Known limitation:** `shares_delta` is always 0. EDGAR's archive endpoints rate-limit aggressively when fetching the actual XML infotable files. Fund names and filing recency are the real signal here.

---

### Skill 4 — Price Action (`price_action_context`)

**Source:** Twelve Data (`twelvedata.com`)
**What it does:** Fetches 60 days of daily OHLCV, computes trend, volume ratio, distance from 60-day high (proxy for 52-week high), and detects recent volume spikes.

**Key outputs:**
- `trend` — uptrend / downtrend / ranging (based on 20-day price change)
- `volume_ratio` — today's volume vs 20-day average
- `pct_from_52w_high` — how far below the 60d high (negative = below)
- `near_resistance` — true if within 2% of 60d high
- `recent_catalyst` — true if any of the last 3 days had volume 1.5x above average

---

## 10. Console Log Reference

When the backend is running, the server terminal outputs structured logs for every analysis.

```
════════════════════════════════════════════════════════════
  Smart Money Agent  |  ticker=NVDA  |  llm=openai
════════════════════════════════════════════════════════════
[HH:MM:SS]  ▶  Calling skill: {name}        ← LLM requested this tool
[HH:MM:SS]     🌐 Fetching from {source}    ← where data is being pulled
[HH:MM:SS]     ✔  {label}: {value}          ← key data point found
[HH:MM:SS]     ⚠  {message}                 ← warning (non-fatal issue)
[HH:MM:SS]  ◀  [{tool}] {summary}           ← skill finished, decision made
[HH:MM:SS]  🧠 {text}                       ← LLM reasoning text
────────────────────────────────────────────────────────────
════════════════════════════════════════════════════════════
  VERDICT
  Signal type : HEDGE
  Conviction  : MEDIUM
  Explanation : ...
════════════════════════════════════════════════════════════
```

---

## 11. API Reference

### `GET /health`

Returns server status. No auth required.

```json
{
  "status": "ok",
  "llm_provider": "openai",
  "mock_mode": "false"
}
```

---

### `GET /analyze?ticker={TICKER}&api_key={KEY}`

Streams a Server-Sent Events (SSE) response. Requires `api_key` if `API_KEY` is set in `.env`.

**Parameters:**

| Param | Required | Description |
|---|---|---|
| `ticker` | Yes | Stock symbol, e.g. `NVDA` |
| `api_key` | If `API_KEY` set | Must match `API_KEY` in `.env` |

**SSE event types:**

```
event: tool_call
data: {"tool": "options_flow_scanner", "ticker": "NVDA", "status": "calling"}

event: tool_result
data: {"tool": "options_flow_scanner", "result": {...}, "status": "complete"}

event: reasoning
data: {"text": "Unusual put sweep detected at $250 strike..."}

event: verdict
data: {
  "signal_type": "hedge",
  "conviction": "medium",
  "explanation": "...",
  "watch_for": "...",
  "skills_used": ["options_flow_scanner", "social_buzz_scanner", ...]
}

event: error
data: {"message": "..."}

event: done
data: {}
```

**Example curl:**

```bash
curl "http://localhost:8000/analyze?ticker=NVDA&api_key=YOUR_KEY"
```

---

## 12. Network Sharing

To share the app with other computers on the same WiFi:

```bash
# Find your local IP
ipconfig getifaddr en0

# Start backend on all interfaces
../.venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000

# Start frontend on all interfaces
npm run dev -- --host
```

**Others connect to:**
- Frontend: `http://{YOUR_IP}:5173`
- Backend: `http://{YOUR_IP}:8000`

**Security:** The `API_KEY` in `.env` gates the `/analyze` endpoint. `/health` is always public. The key is passed as `?api_key=` in the URL (required for SSE since `EventSource` doesn't support custom headers).

---

## 13. File Structure Reference

```
Dev/
├── USER_GUIDE.md                  ← you are here
├── CLAUDE.md                      ← project context for Claude Code
├── backend/
│   ├── main.py                    ← FastAPI app, /health + /analyze SSE
│   ├── agent.py                   ← async agent loop, streams events
│   ├── prompts.py                 ← orchestrator + sub-agent prompts
│   ├── tools.py                   ← 4 Claude-format tool schemas
│   ├── logger.py                  ← human-readable terminal logger
│   ├── requirements.txt
│   ├── .env                       ← your secrets (not committed)
│   ├── .env.example               ← template
│   ├── llm/
│   │   ├── __init__.py            ← get_llm() factory
│   │   ├── base.py                ← abstract interface
│   │   ├── claude.py              ← Anthropic adapter
│   │   ├── openai.py              ← OpenAI adapter
│   │   └── gemini.py              ← Gemini adapter
│   ├── skills/
│   │   ├── __init__.py            ← execute_skill() dispatcher
│   │   ├── options_flow.py        ← yfinance options chain
│   │   ├── insider_tracker.py     ← SEC EDGAR Form 4 + 13F
│   │   ├── price_action.py        ← Twelve Data OHLCV
│   │   ├── social_buzz.py         ← Reddit + StockTwits + Finviz + X
│   │   └── x_scraper.py           ← twscrape X/Twitter wrapper
│   └── fixtures/
│       ├── nvda.json              ← mock: bullish accumulation
│       ├── tsla.json              ← mock: bearish distribution
│       └── aapl.json              ← mock: no signal / noise
└── frontend/
    ├── src/
    │   ├── App.tsx                ← main layout, search, quick tickers
    │   ├── types.ts               ← TypeScript interfaces
    │   ├── hooks/
    │   │   └── useAgentStream.ts  ← SSE consumer, state management
    │   └── components/
    │       ├── SkillStep.tsx      ← step-by-step skill progress + summary
    │       ├── ReasoningStream.tsx← live LLM reasoning text
    │       └── VerdictCard.tsx    ← final verdict display
    ├── .env                       ← VITE_BACKEND_URL + VITE_API_KEY
    └── vite.config.ts
```

---

## 14. Troubleshooting

### `pydantic-core` build fails on install
Python 3.14 is not supported. Use Python 3.13.
```bash
python3.13 -m venv .venv
```

### `Address already in use` on port 8000
Kill the existing process:
```bash
pkill -f "uvicorn main:app"
```

### Only options flow runs, others don't appear
Options flow returned `unusual=false` — this is correct behaviour. The agent stops early and returns `signal_type=noise`. Try `NVDA` or `TSLA` which have active options flow.

### `401 Unauthorized` on `/analyze`
Pass the API key: `?api_key=YOUR_KEY`. The key is in `backend/.env` under `API_KEY`.

### X scraper returns 0 posts
- Check `X_USERNAME` and `X_PASSWORD` are set in `.env`
- Delete `.twscrape_accounts.db` in `backend/` and let it re-login
- X may have flagged the session — try a different account

### EDGAR `insider_buys` always empty
NVDA insiders haven't made open-market purchases recently (last 90 days). Insider grants and option exercises are filtered out — only outright acquisitions (Form 4 transaction code "A") are shown.

### `503` errors on EDGAR archive requests
EDGAR rate-limits archive XML requests. `shares_delta` will remain 0. Fund names and filing dates are still returned correctly via EFTS search.

### Twelve Data returns no values
Free tier has 800 calls/day. Check usage at `twelvedata.com`. The skill falls back to a neutral empty result and the agent continues.

### Frontend shows "Connection lost"
Backend is not running. Start it with:
```bash
cd backend && ../.venv/bin/uvicorn main:app --port 8000
```

---

*Last updated: 2026-03-14*
