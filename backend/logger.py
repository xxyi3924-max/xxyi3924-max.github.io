"""
Human-readable terminal logger for Smart Money Agent.
Outputs to stdout AND a thread-safe queue streamed to the frontend /logs endpoint.
"""

import queue
from datetime import datetime

# Thread-safe queue — frontend /logs SSE endpoint drains this
_log_queue: queue.Queue = queue.Queue(maxsize=1000)


def _ts() -> str:
    return datetime.now().strftime("%H:%M:%S")


def _line(char: str = "─", width: int = 60) -> str:
    return char * width


def _emit(text: str):
    print(text)
    try:
        _log_queue.put_nowait(text)
    except queue.Full:
        pass


def section(title: str):
    _emit(f"")
    _emit(f"{_line('═')}")
    _emit(f"  {title}")
    _emit(_line('═'))


def step(label: str, detail: str = ""):
    suffix = f"  →  {detail}" if detail else ""
    _emit(f"[{_ts()}]  ▶  {label}{suffix}")


def fetch(source: str, url: str = ""):
    suffix = f"  ({url})" if url else ""
    _emit(f"[{_ts()}]     🌐 Fetching from {source}{suffix}")


def found(label: str, value):
    _emit(f"[{_ts()}]     ✔  {label}: {value}")


def warn(msg: str):
    _emit(f"[{_ts()}]     ⚠  {msg}")


def result(tool: str, summary: str):
    _emit(f"[{_ts()}]  ◀  [{tool}] {summary}")
    _emit(_line("─"))


def reasoning(text: str):
    for line in text.strip().splitlines():
        line = line.strip()
        if line:
            _emit(f"[{_ts()}]  🧠 {line}")


def verdict(data: dict):
    _emit(f"")
    _emit(_line('═'))
    _emit(f"  VERDICT")
    _emit(_line('═'))
    _emit(f"  Signal type : {data.get('signal_type', '?').upper()}")
    _emit(f"  Conviction  : {data.get('conviction', '?').upper()}")
    _emit(f"  Explanation : {data.get('explanation', '')}")
    if data.get("watch_for"):
        _emit(f"  Watch for   : {data.get('watch_for')}")
    _emit(f"  Skills used : {', '.join(data.get('skills_used', []))}")
    _emit(_line('═'))


def error(msg: str):
    _emit(f"[{_ts()}]  ✖  ERROR: {msg}")
