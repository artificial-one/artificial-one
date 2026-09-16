#!/usr/bin/env python3
"""Monitor mapped vendor sources and publish only repeated, sanitized changes."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from hashlib import sha256
from html import unescape
import json
from pathlib import Path
import re
import sys
from typing import Any
from urllib.request import Request, urlopen

try:
    from scripts import build_tool_intelligence as intelligence
except ImportError:
    import build_tool_intelligence as intelligence  # type: ignore


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STATE = ROOT / ".tool-intelligence" / "private-state.json"
SIGNAL_RE = re.compile(
    r"\b(price|pricing|plan|free|trial|month|annual|year|credit|limit|feature|integration|api|available|availability|discontinued|deprecated)\b",
    re.I,
)


def load(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return dict(default)
    return value if isinstance(value, dict) else dict(default)


def write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def extract_signal(raw: str) -> str:
    raw = re.sub(r"<(script|style|svg|noscript)\b.*?</\1>", " ", raw, flags=re.I | re.S)
    prominent = re.findall(r"<(?:title|h1|h2|h3)[^>]*>(.*?)</(?:title|h1|h2|h3)>", raw, re.I | re.S)
    meta = re.findall(r'<meta[^>]+(?:name|property)=["\'](?:description|og:description)["\'][^>]+content=["\']([^"\']+)', raw, re.I)
    visible = re.sub(r"<[^>]+>", "\n", raw)
    candidates = [*prominent, *meta, *visible.splitlines()]
    selected: list[str] = []
    for index, value in enumerate(candidates):
        line = re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", value))).strip()
        if not 8 <= len(line) <= 360:
            continue
        if index < len(prominent) + len(meta) or SIGNAL_RE.search(line):
            if line not in selected:
                selected.append(line)
        if len(selected) >= 60:
            break
    return "\n".join(selected)


def fetch_source(tool: dict[str, Any]) -> tuple[str, str, str, str] | None:
    url = str(tool.get("links", {}).get("source") or "")
    if not url.startswith("https://"):
        return None
    request = Request(
        url,
        headers={
            "User-Agent": "artificial.one intelligence monitor/1.0 (+https://artificial.one/about.html)",
            "Accept": "text/html,application/xhtml+xml",
        },
    )
    try:
        with urlopen(request, timeout=22) as response:
            content_type = str(response.headers.get("content-type") or "")
            if response.status >= 400 or "html" not in content_type:
                return None
            raw = response.read(1_800_000).decode("utf-8", errors="ignore")
    except Exception:
        return None
    signal = extract_signal(raw)
    if len(signal) < 30:
        return None
    return str(tool["id"]), url, sha256(signal.encode()).hexdigest(), signal


def change_kind(previous: str, current: str) -> str:
    changed = (previous + "\n" + current).casefold()
    if any(word in changed for word in ("discontinued", "deprecated", "no longer available", "availability")):
        return "availability"
    if any(word in changed for word in ("price", "pricing", "month", "annual", "year", "credit", "free plan", "trial")):
        return "pricing or plan"
    return "feature or product"


def batch_for(tools: list[dict[str, Any]], today: date, size: int) -> list[dict[str, Any]]:
    sources = [tool for tool in tools if str(tool.get("links", {}).get("source") or "").startswith("https://")]
    if len(sources) <= size:
        return sources
    start = ((today.toordinal() - 1) * size) % len(sources)
    rotated = sources[start:] + sources[:start]
    return rotated[:size]


def observe(
    tools: list[dict[str, Any]], state: dict[str, Any], history: dict[str, Any],
    today: date, batch_size: int = 75, workers: int = 8,
) -> tuple[list[dict[str, Any]], int]:
    selected = batch_for(tools, today, batch_size)
    records = state.setdefault("tools", {})
    by_id = {str(tool["id"]): tool for tool in tools}
    confirmed: list[dict[str, Any]] = []
    successful = 0
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        futures = [pool.submit(fetch_source, tool) for tool in selected]
        for future in as_completed(futures):
            result = future.result()
            if not result:
                continue
            successful += 1
            tool_id, source_url, fingerprint, signal = result
            record = records.setdefault(tool_id, {})
            if not record.get("stable_hash"):
                record.update({
                    "stable_hash": fingerprint, "stable_signal": signal,
                    "source_url": source_url, "checked_on": today.isoformat(),
                })
                continue
            if fingerprint == record.get("stable_hash"):
                record.pop("pending_hash", None)
                record.pop("pending_signal", None)
                record.pop("pending_seen", None)
            elif fingerprint == record.get("pending_hash"):
                record["pending_seen"] = int(record.get("pending_seen") or 1) + 1
                if record["pending_seen"] >= 2:
                    tool = by_id.get(tool_id, {})
                    kind = change_kind(str(record.get("stable_signal") or ""), signal)
                    event = {
                        "id": sha256(f"{tool_id}|{today.isoformat()}|{fingerprint}".encode()).hexdigest()[:16],
                        "tool_id": tool_id,
                        "tool_name": str(tool.get("name") or tool_id),
                        "detected_on": today.isoformat(),
                        "kind": kind,
                        "message": f"A repeated vendor-source observation indicates a {kind} change. Recheck the current details before deciding or purchasing.",
                        "source_url": source_url,
                    }
                    confirmed.append(event)
                    record.update({
                        "stable_hash": fingerprint, "stable_signal": signal,
                        "changed_on": today.isoformat(),
                    })
                    record.pop("pending_hash", None)
                    record.pop("pending_signal", None)
                    record.pop("pending_seen", None)
            else:
                record.update({"pending_hash": fingerprint, "pending_signal": signal, "pending_seen": 1})
            record.update({"source_url": source_url, "checked_on": today.isoformat()})
    state["updated_at"] = today.isoformat()
    existing = [item for item in history.get("events", []) if isinstance(item, dict)]
    seen = {str(item.get("id") or "") for item in confirmed}
    history["events"] = (confirmed + [item for item in existing if str(item.get("id") or "") not in seen])[:200]
    history["coverage"] = {
        "tracked_sources": sum(bool(tool.get("links", {}).get("source")) for tool in tools),
        "scheduled_checks": len(selected),
        "successful_checks": successful,
    }
    history["updated_at"] = today.isoformat()
    history["version"] = 1
    history["method"] = "two-consecutive-observation vendor-source monitor"
    return confirmed, successful


def run(state_path: Path, cached: bool = False, check: bool = False, batch_size: int = 75) -> int:
    catalog = intelligence.build_catalog()
    history = load(intelligence.HISTORY_PATH, intelligence.default_history())
    if check:
        if not isinstance(history.get("events"), list) or not isinstance(history.get("coverage"), dict):
            print("Tool change history has an invalid schema.", file=sys.stderr)
            return 1
        return intelligence.build(check=True)
    if cached:
        intelligence.build(check=False)
        print("Tool intelligence change page refreshed from cached public history.")
        return 0
    state = load(state_path, {"version": 1, "tools": {}})
    confirmed, successful = observe(list(catalog["tools"]), state, history, date.today(), batch_size=batch_size)
    write(state_path, state)
    write(intelligence.HISTORY_PATH, history)
    intelligence.build(check=False)
    print(f"Tool intelligence monitor checked {successful} source(s); {len(confirmed)} confirmed change(s) published.")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE)
    parser.add_argument("--cached", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--batch-size", type=int, default=75)
    args = parser.parse_args()
    raise SystemExit(run(args.state, args.cached, args.check, max(1, args.batch_size)))
