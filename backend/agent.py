import asyncio
from collections.abc import AsyncGenerator
from typing import Any

import logger
from llm import get_llm
from prompts import SYSTEM_PROMPT
from skills import execute_skill
from tools import TOOLS


async def run_agent(ticker: str) -> AsyncGenerator[dict, None]:
    queue: asyncio.Queue[dict | None] = asyncio.Queue()

    def _put(item: dict | None):
        # asyncio.Queue is NOT thread-safe; use call_soon_threadsafe from the worker thread
        loop.call_soon_threadsafe(queue.put_nowait, item)

    def on_tool_call(tool_name: str, tool_args: dict):
        logger.step(f"Calling skill: {tool_name}", f"ticker={tool_args.get('ticker', ticker)}")
        _put({
            "event": "tool_call",
            "data": {"tool": tool_name, "ticker": tool_args.get("ticker", ticker), "status": "calling"},
        })

    def on_tool_result(tool_name: str, result: Any):
        _log_tool_result(tool_name, result)
        _put({
            "event": "tool_result",
            "data": {"tool": tool_name, "result": result, "status": "complete"},
        })

    def on_reasoning(text: str):
        logger.reasoning(text)
        _put({
            "event": "reasoning",
            "data": {"text": text},
        })

    def run_in_thread():
        try:
            import os
            provider = os.getenv("LLM_PROVIDER", "claude")
            logger.section(f"Smart Money Agent  |  ticker={ticker.upper()}  |  llm={provider}")
            llm = get_llm()
            verdict = llm.run_agent_loop(
                system_prompt=SYSTEM_PROMPT,
                user_message=f"Analyze ticker: {ticker.upper()}",
                tools=TOOLS,
                tool_executor=execute_skill,
                on_reasoning=on_reasoning,
                on_tool_call=on_tool_call,
                on_tool_result=on_tool_result,
            )
            logger.verdict(verdict)
            _put({"event": "verdict", "data": verdict})
        except Exception as e:
            logger.error(str(e))
            _put({"event": "error", "data": {"message": str(e)}})
        finally:
            _put(None)

    loop = asyncio.get_running_loop()
    future = loop.run_in_executor(None, run_in_thread)

    while True:
        item = await queue.get()
        if item is None:
            yield {"event": "done", "data": {}}
            break
        yield item

    await future


def _log_tool_result(tool_name: str, result: Any):
    if tool_name == "options_flow_scanner":
        unusual = result.get("unusual")
        lean = result.get("sentiment_lean")
        premium = result.get("total_unusual_premium", 0)
        sweep = result.get("sweep_detected")
        contracts = result.get("top_contracts", [])
        logger.found("Unusual activity", unusual)
        logger.found("Sentiment lean", lean)
        logger.found("Total unusual premium", f"${premium:,.0f}")
        logger.found("Sweep detected", sweep)
        if contracts:
            top = contracts[0]
            logger.found("Top contract", f"{top['type'].upper()} ${top['strike']} exp {top['expiry']} (vol/OI={top['vol_oi_ratio']})")
        decision = "→ Options unusual: proceeding with strong signal" if unusual else "→ No unusual options. Continuing pipeline — dark pool / COT may still show accumulation."
        logger.result("options_flow_scanner", decision)

    elif tool_name == "social_buzz_scanner":
        raw = result.get("raw_metrics", {})
        logger.found("Reddit posts (48h)", raw.get("reddit_post_count_48h", 0))
        logger.found("StockTwits bull ratio", raw.get("stocktwits_bull_ratio", 0))
        logger.found("Yahoo Finance articles", raw.get("yf_article_count", 0))
        logger.found("Yahoo Finance sentiment", raw.get("yf_bull_ratio", 0.5))
        logger.found("Crowd aware", result.get("crowd_aware"))
        logger.found("Informed vs hype", result.get("informed_vs_hype"))
        logger.found("Interpretation", result.get("interpretation", "")[:120])
        logger.result("social_buzz_scanner", f"crowd_aware={result.get('crowd_aware')}  type={result.get('informed_vs_hype')}")

    elif tool_name == "insider_tracker":
        direction = result.get("net_institutional_direction")
        funds = result.get("notable_funds", [])
        changes = result.get("recent_13f_changes", [])
        buys = result.get("insider_buys", [])
        logger.found("Institutional direction", direction)
        logger.found("Notable funds", ", ".join(funds) if funds else "none found")
        logger.found("Recent 13F changes", len(changes))
        logger.found("Insider buys (90d)", len(buys))
        if buys:
            b = buys[0]
            logger.found("Top insider buy", f"{b['name']} ({b['role']}) — {b['shares']:,} shares @ ${b['value_usd']:,.0f}")
        logger.result("insider_tracker", f"direction={direction}  funds={len(funds)}")

    elif tool_name == "price_action_context":
        trend = result.get("trend")
        vol = result.get("volume_ratio")
        pct = result.get("pct_from_52w_high")
        catalyst = result.get("recent_catalyst")
        ob = result.get("order_block", {})
        fvg = result.get("fvg", {})
        amd = result.get("amd_phase", "unknown")
        divergence = result.get("flow_price_divergence", False)
        logger.found("Trend", trend)
        logger.found("Volume ratio (vs 20d avg)", f"{vol}x")
        logger.found("% from 52w high", f"{pct}%")
        logger.found("Recent catalyst", catalyst)
        logger.found("Order Block", f"{ob.get('type','none')} @ ${ob.get('price_level',0):.2f}" if ob.get("type") != "none" else "none")
        logger.found("Fair Value Gap", f"{fvg.get('type','none')} [{fvg.get('lower',0):.2f}–{fvg.get('upper',0):.2f}]" if fvg.get("type") != "none" else "none")
        logger.found("AMD phase", amd)
        logger.found("Flow/Price divergence", divergence)
        logger.result("price_action_context", f"trend={trend}  amd={amd}  OB={ob.get('type','none')}  FVG={fvg.get('type','none')}  divergence={divergence}")

    elif tool_name == "institutional_positioning":
        bias = result.get("institutional_bias")
        crowding = result.get("crowding_score", 0)
        crowded = result.get("crowded")
        pc = result.get("pc_ratio")
        pc_sig = result.get("pc_signal")
        modifier = result.get("conviction_modifier")
        short_pct = result.get("short_pct_float", 0)
        covering = result.get("short_covering")
        holders = result.get("top_holders", [])
        logger.found("Institutional bias", bias)
        logger.found("Crowding score", f"{crowding}/100")
        logger.found("Crowded (>70)", crowded)
        logger.found("Short % of float", f"{short_pct:.2f}%")
        logger.found("Shorts covering", covering)
        logger.found("P/C ratio", f"{pc}  ({pc_sig})")
        if holders:
            top = holders[0]
            logger.found("Top holder", f"{top['name']} — {top['pct_held']:.2f}% ({top['pct_change']:+.1f}%)")
        logger.result("institutional_positioning", f"bias={bias}  crowding={crowding:.0f}/100  PC={pc}  modifier={modifier}")

    elif tool_name == "dark_pool_activity":
        absorbed = result.get("absorption_detected")
        direction = result.get("estimated_direction")
        score = result.get("block_trade_score", 0)
        divergence = result.get("vol_price_divergence")
        spread = result.get("options_spread_signal")
        high = result.get("high_dark_pool_activity")
        events = result.get("absorption_events", [])
        logger.found("Absorption detected", absorbed)
        logger.found("Absorption events", len(events))
        logger.found("Estimated direction", direction)
        logger.found("Block trade score", f"{score}/10")
        logger.found("Vol↑/Price↓ divergence", divergence)
        logger.found("ATM options spread", spread)
        logger.result("dark_pool_activity", f"direction={direction}  score={score}/10  divergence={divergence}  high={high}")
