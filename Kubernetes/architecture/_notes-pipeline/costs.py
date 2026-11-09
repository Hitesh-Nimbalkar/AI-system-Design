"""Token pricing, cost estimation and live spend tracking.

Prices live in ``pricing.json`` next to this file. The defaults below are
DeepSeek's published rates for the V4 generation (off-peak), with peak hours
costing 2x. Edit ``pricing.json`` - no code change needed - when prices move.

Everything here is an estimate except the token counts that the API itself
reports back; the UI labels live numbers as estimated until the run finishes.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path

import pipeline

HERE = Path(__file__).resolve().parent
PRICING_FILE = HERE / "pricing.json"

# USD per 1M tokens, off-peak (peak = x2, see peak_hours_utc below).
DEFAULT_PRICING = {
    "usd_inr": 88.0,
    "peak_multiplier": 2.0,
    "thinking_output_multiplier": 1.9,
    "peak_hours_utc": [[1, 4], [6, 10]],
    "models": {
        "deepseek-flash": {"input": 0.15, "cache_hit": 0.003, "output": 0.60},
        "deepseek-v4-pro": {"input": 0.66, "cache_hit": 0.022, "output": 1.98},
    },
    "aliases": {
        "deepseek-chat": "deepseek-flash",
        "deepseek-reasoner": "deepseek-flash",
    },
    "default_model": "deepseek-flash",
}

CHARS_PER_TOKEN = 3.6


def _as_float(v, fallback=0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return fallback


def _merge(data: dict, extra: dict) -> dict:
    if not isinstance(extra, dict):
        return data
    for key in ("usd_inr", "peak_multiplier", "thinking_output_multiplier"):
        if isinstance(extra.get(key), (int, float)):
            data[key] = float(extra[key])
    models = extra.get("models")
    if isinstance(models, dict):
        for name, cfg in models.items():
            if not isinstance(cfg, dict):
                continue
            dst = data["models"].setdefault(str(name), {})
            for field in ("input", "cache_hit", "output"):
                if isinstance(cfg.get(field), (int, float)):
                    dst[field] = float(cfg[field])
    aliases = extra.get("aliases")
    if isinstance(aliases, dict):
        data["aliases"].update({str(k): str(v) for k, v in aliases.items()})
    if isinstance(extra.get("default_model"), str):
        data["default_model"] = extra["default_model"]
    return data


def load_pricing(path: Path | None = None, override: dict | None = None) -> dict:
    data = json.loads(json.dumps(DEFAULT_PRICING))
    p = Path(path) if path else PRICING_FILE
    try:
        if p.exists():
            _merge(data, json.loads(p.read_text(encoding="utf-8")))
    except Exception:
        pass
    if override:
        _merge(data, override)
    return data


def resolve_model(model: str, pricing: dict) -> str:
    name = (model or "").strip()
    models = pricing["models"]
    if name in models:
        return name
    alias = pricing["aliases"].get(name)
    if alias in models:
        return alias
    low = name.lower()
    if "v4-pro" in low or ("pro" in low and "deepseek" in low):
        return "deepseek-v4-pro"
    for key in models:
        if key in low:
            return key
    if "reasoner" in low or "chat" in low or "flash" in low:
        return "deepseek-flash"
    return pricing["default_model"]


def is_peak(now: datetime | None = None, pricing: dict | None = None) -> bool:
    """True during DeepSeek's peak windows (UTC, weekdays)."""
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    now = now.astimezone(timezone.utc)
    if now.weekday() >= 5:
        return False
    hour = now.hour + now.minute / 60.0
    hours = (pricing or DEFAULT_PRICING).get("peak_hours_utc") or []
    return any(start <= hour < end for start, end in hours)


def rates_for(model: str, pricing: dict, peak: bool) -> dict:
    key = resolve_model(model, pricing)
    base = pricing["models"].get(pricing["default_model"]) or {
        "input": 0.15, "cache_hit": 0.003, "output": 0.60,
    }
    cfg = dict(base)
    cfg.update(pricing["models"].get(key) or {})
    mult = pricing.get("peak_multiplier", 2.0) if peak else 1.0
    return {
        "model": key,
        "input": cfg["input"] * mult,
        "cache_hit": cfg.get("cache_hit", cfg["input"]) * mult,
        "output": cfg["output"] * mult,
        "peak": peak,
    }


def _tokens(chars: int) -> int:
    return max(1, round(chars / CHARS_PER_TOKEN))


def _leg(role: str, model: str, calls: int, in_tokens: int, out_tokens: int,
         pricing: dict, peak: bool) -> dict:
    r = rates_for(model, pricing, peak)
    usd = (in_tokens * r["input"] + out_tokens * r["output"]) / 1_000_000
    return {
        "role": role,
        "model": model,
        "billed_as": r["model"],
        "calls": calls,
        "in_tokens": int(in_tokens),
        "out_tokens": int(out_tokens),
        "usd": round(usd, 8),
    }


def estimate(text: str, mode: str, map_model: str, write_model: str,
             pricing: dict | None = None, now: datetime | None = None) -> dict:
    """Cheap pre-flight estimate from the source text. No API calls."""
    pricing = pricing or load_pricing()
    peak = is_peak(now, pricing)
    chunks = pipeline.chunk_text(text or "")
    src_tokens = _tokens(len(text or ""))

    map_in = 0
    map_out = 0
    for chunk in chunks:
        chunk_tokens = _tokens(len(chunk))
        map_in += chunk_tokens + 700          # extract system + user template
        map_out += min(5000, 180 + int(chunk_tokens * 0.42))

    facts_tokens = map_out
    facts_chars = facts_tokens * 3.2
    reduce_calls = 0
    reduce_in = reduce_out = 0
    if facts_chars > pipeline.MAX_FACT_CHARS:
        reduce_calls = math.ceil(facts_chars / pipeline.MAX_FACT_CHARS)
        part_tokens = _tokens(pipeline.MAX_FACT_CHARS)
        reduce_in = reduce_calls * (part_tokens + 500)
        reduce_out = int(reduce_in * 0.6)
        facts_tokens = reduce_out

    write_in = facts_tokens + 1800            # style spec + rules + header
    answer = min(getattr(pipeline, "WRITE_MAX_TOKENS", 32768),
                 1400 + int(src_tokens * 0.72))
    writing_is_thinking = "reasoner" in write_model.lower() or "thinking" in write_model.lower()
    write_out = int(answer * (pricing.get("thinking_output_multiplier", 1.9)
                              if writing_is_thinking else 1.0))

    legs = []
    if map_model == write_model:
        legs.append(_leg("Extraction + writing", map_model,
                         len(chunks) + reduce_calls,
                         map_in + reduce_in + write_in,
                         map_out + reduce_out + write_out, pricing, peak))
    else:
        legs.append(_leg("Extraction", map_model, len(chunks) + reduce_calls,
                         map_in + reduce_in, map_out + reduce_out, pricing, peak))
        legs.append(_leg("Writing", write_model, 1, write_in, write_out, pricing, peak))

    usd = sum(leg["usd"] for leg in legs)
    spread = 2.2 if writing_is_thinking else 1.5
    return {
        "chunks": len(chunks),
        "source_chars": len(text or ""),
        "source_tokens": src_tokens,
        "peak": peak,
        "rates": {
            "map": rates_for(map_model, pricing, peak),
            "write": rates_for(write_model, pricing, peak),
        },
        "legs": legs,
        "usd": round(usd, 6),
        "inr": round(usd * pricing.get("usd_inr", 88.0), 4),
        "low_usd": round(usd * 0.72, 6),
        "high_usd": round(usd * spread, 6),
        "tokens": {
            "in": sum(leg["in_tokens"] for leg in legs),
            "out": sum(leg["out_tokens"] for leg in legs),
        },
        "note": "estimate only - actual usage is shown after the run",
    }


def breakdown(usage: dict, pricing: dict | None = None,
              now: datetime | None = None, map_model: str = "",
              write_model: str = "") -> dict:
    """Turn API-reported usage into money, per model."""
    pricing = pricing or load_pricing()
    peak = is_peak(now, pricing)
    models = {}
    total = 0.0
    total_in = total_out = 0
    for name, u in (usage or {}).items():
        prompt = int(u.get("prompt_tokens") or 0)
        completion = int(u.get("completion_tokens") or 0)
        if not prompt and not completion:
            continue
        hit = min(int(u.get("cache_hit_tokens") or 0), prompt)
        miss = max(0, prompt - hit)
        r = rates_for(name, pricing, peak)
        usd = (miss * r["input"] + hit * r["cache_hit"] + completion * r["output"]) / 1_000_000
        role = ""
        if name == map_model and name == write_model:
            role = "Extraction + writing"
        elif name == map_model:
            role = "Extraction"
        elif name == write_model:
            role = "Writing"
        models[name] = {
            "role": role,
            "billed_as": r["model"],
            "in_tokens": prompt,
            "out_tokens": completion,
            "cache_hit_tokens": hit,
            "usd": round(usd, 8),
        }
        total += usd
        total_in += prompt
        total_out += completion
    return {
        "models": models,
        "usd": round(total, 8),
        "inr": round(total * pricing.get("usd_inr", 88.0), 4),
        "peak": peak,
        "tokens": {"in": total_in, "out": total_out},
        "estimated": False,
    }


def live(usage: dict, pricing: dict | None = None, now: datetime | None = None,
         map_model: str = "", write_model: str = "", streaming_model: str = "",
         written_chars: int = 0, prompt_chars: int = 0,
         thinking_chars: int = 0) -> dict:
    """Actual spend so far, plus an estimate for the still-streaming write."""
    pricing = pricing or load_pricing()
    base = breakdown(usage, pricing, now, map_model, write_model)
    if streaming_model and (written_chars or prompt_chars or thinking_chars):
        u = (usage or {}).get(streaming_model) or {}
        have_out = int(u.get("completion_tokens") or 0)
        have_in = int(u.get("prompt_tokens") or 0)
        out_chars = written_chars + thinking_chars
        est_out = max(0, _tokens(out_chars) - have_out) if out_chars else 0
        est_in = max(0, _tokens(prompt_chars) - have_in) if prompt_chars else 0
        r = rates_for(streaming_model, pricing, base["peak"])
        extra = (est_in * r["input"] + est_out * r["output"]) / 1_000_000
        if extra:
            base["usd"] = round(base["usd"] + extra, 8)
            base["inr"] = round(base["usd"] * pricing.get("usd_inr", 88.0), 4)
            base["estimated"] = True
            entry = base["models"].get(streaming_model)
            if entry is None:
                entry = {
                    "role": "Writing" if streaming_model == write_model else "",
                    "billed_as": r["model"], "in_tokens": 0, "out_tokens": 0,
                    "cache_hit_tokens": 0, "usd": 0.0,
                }
                base["models"][streaming_model] = entry
            entry["in_tokens"] += est_in
            entry["out_tokens"] += est_out
            entry["usd"] = round(entry["usd"] + extra, 8)
            base["tokens"]["in"] += est_in
            base["tokens"]["out"] += est_out
    return base
