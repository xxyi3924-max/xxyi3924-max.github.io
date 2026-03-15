import asyncio
import json
import os
import queue
import secrets

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from agent import run_agent

app = FastAPI(title="Smart Money Agent")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

API_KEY = os.getenv("API_KEY", "")

UNPROTECTED = {"/health"}


@app.middleware("http")
async def require_api_key(request: Request, call_next):
    if not API_KEY or request.url.path in UNPROTECTED:
        return await call_next(request)

    # Accept key via header OR query param (query param needed for SSE/EventSource)
    key = (
        request.headers.get("X-API-Key")
        or request.query_params.get("api_key")
    )
    if not key or not secrets.compare_digest(key, API_KEY):
        return JSONResponse(status_code=401, content={"error": "Invalid or missing API key"})

    return await call_next(request)


@app.get("/health")
def health():
    provider = os.getenv("LLM_PROVIDER", "claude")
    mock = os.getenv("MOCK_MODE", "false")
    return {"status": "ok", "llm_provider": provider, "mock_mode": mock}


@app.get("/logs")
async def logs_stream(api_key: str = Query(default="")):
    import logger as log_module

    async def event_stream():
        while True:
            try:
                line = log_module._log_queue.get_nowait()
                yield f"event: log\ndata: {json.dumps({'text': line})}\n\n"
            except queue.Empty:
                await asyncio.sleep(0.1)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/analyze")
async def analyze(
    ticker: str = Query(..., description="Stock ticker, e.g. NVDA"),
    api_key: str = Query(default="", include_in_schema=False),  # consumed by middleware
):
    ticker = ticker.upper().strip()

    async def event_stream():
        async for event in run_agent(ticker):
            yield f"event: {event['event']}\ndata: {json.dumps(event['data'])}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
