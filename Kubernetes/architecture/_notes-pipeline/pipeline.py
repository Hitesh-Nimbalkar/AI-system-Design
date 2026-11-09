"""Notes pipeline: transcript in, incremental study notes out.

Design goals (in order):
  1. NEVER fail because the input is long or the model returns bad JSON.
  2. Break the transcript into chunks small enough that one extraction call
     cannot blow its output budget.
  3. Report progress and metrics while it runs.

Flow:
    chunk -> extract facts (cheap model) -> [reduce if needed] -> write notes (pro model)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

import prompts

DEFAULT_BASE_URL = os.environ.get("NOTES_BASE_URL", "https://api.deepseek.com")
DEFAULT_MAP_MODEL = os.environ.get("NOTES_MAP_MODEL", "deepseek-chat")
DEFAULT_WRITE_MODEL = os.environ.get("NOTES_WRITE_MODEL", "deepseek-reasoner")

HERE = Path(__file__).resolve().parent
CACHE_DIR = HERE / ".cache"
OUTPUT_DIR = HERE / "output"

# One chunk must fit comfortably in the extraction model's OUTPUT budget:
# ~9k chars of transcript -> a few thousand facts tokens, not 8k.
MAX_CHUNK_CHARS = 9000
CHUNK_OVERLAP = 700
MAX_FACT_CHARS = 90000
MIN_SPLIT_CHARS = 2500          # do not recurse below this
MAX_SPLIT_DEPTH = 4
# Cap for the final notes. 8192 was too small: a thinking model spends most of
# that on reasoning and can return empty content. DeepSeek V4 allows far more.
WRITE_MAX_TOKENS = int(os.environ.get("NOTES_WRITE_MAX_TOKENS", "32768"))
# If a write comes back empty or truncated, retry once/twice with a bigger cap
# instead of writing a blank file. Bounded by this ceiling.
WRITE_MAX_RETRY_CAP = int(os.environ.get("NOTES_WRITE_MAX_RETRY_CAP", "131072"))
# Facts longer than this get a cheap "compress + analyse" pass (flash) before
# the reasoning model writes, so the writer is never handed a 30k-char dump.
COMPRESS_THRESHOLD_CHARS = int(os.environ.get("NOTES_COMPRESS_CHARS", "16000"))


# ---------------------------------------------------------------------------
# logging / progress
# ---------------------------------------------------------------------------

def _nop(_msg: str) -> None:
    pass


def _nop_progress(_info: dict) -> None:
    pass


# ---------------------------------------------------------------------------
# LLM client
# ---------------------------------------------------------------------------

class LLMError(RuntimeError):
    pass


class Cancelled(RuntimeError):
    """Raised when the user cancels a running job."""


class LLM:
    def __init__(self, base_url: str, api_key: str, map_model: str, write_model: str,
                 timeout: int = 900):
        if not api_key:
            raise LLMError("No API key. Set DEEPSEEK_API_KEY (or run with --mock).")
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.map_model = map_model
        self.write_model = write_model
        self.timeout = timeout
        self.last_finish = ""
        # Per-model token accounting, e.g. {"deepseek-chat": {...}, ...}.
        # The server turns this into money; the pipeline only counts tokens.
        self.usage_by_model: dict[str, dict] = {}

    def _add_usage(self, model: str, usage) -> None:
        if not isinstance(usage, dict):
            return
        u = self.usage_by_model.setdefault(model, {
            "prompt_tokens": 0, "completion_tokens": 0, "cache_hit_tokens": 0,
        })
        try:
            prompt = int(usage.get("prompt_tokens") or 0)
            u["prompt_tokens"] += prompt
            u["completion_tokens"] += int(usage.get("completion_tokens") or 0)
            u["cache_hit_tokens"] += int(usage.get("prompt_cache_hit_tokens") or 0)
        except (TypeError, ValueError):
            pass

    def chat(self, system: str, user: str, *, model: str, max_tokens: int = 8192,
             temperature: float = 0.2) -> str:
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "max_tokens": max_tokens,
            "stream": False,
        }
        if "reasoner" not in model:
            payload["temperature"] = temperature

        body = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        last_err = ""
        for attempt in range(4):
            req = urllib.request.Request(self.base_url + "/chat/completions",
                                         data=body, headers=headers, method="POST")
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                self._add_usage(model, data.get("usage"))
                choice = data["choices"][0]
                self.last_finish = choice.get("finish_reason") or ""
                return choice["message"]["content"] or ""
            except urllib.error.HTTPError as e:
                detail = ""
                try:
                    detail = e.read().decode("utf-8", "replace")[:400]
                except Exception:
                    pass
                last_err = f"HTTP {e.code}: {detail}"
                if e.code in (408, 409, 429, 500, 502, 503, 504) and attempt < 3:
                    time.sleep(2 ** attempt)
                    continue
                raise LLMError(last_err) from e
            except (urllib.error.URLError, TimeoutError, KeyError, json.JSONDecodeError) as e:
                last_err = f"{type(e).__name__}: {e}"
                if attempt < 3:
                    time.sleep(2 ** attempt)
                    continue
                raise LLMError(last_err) from e
        raise LLMError(last_err or "unknown error")

    def chat_stream(self, system: str, user: str, *, model: str, max_tokens: int = 8192,
                    temperature: float = 0.25, on_delta=None, on_thinking=None,
                    should_cancel=None) -> str:
        """Same API as chat(), but streams deltas to on_delta as they arrive.

        stream_options is tried once and dropped if the endpoint rejects it, so
        this works with OpenAI-compatible servers that do not support it.
        """
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "max_tokens": max_tokens,
            "stream": True,
        }
        if "reasoner" not in model:
            payload["temperature"] = temperature
        payload["stream_options"] = {"include_usage": True}

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        last_err = ""
        include_usage = True
        for attempt in range(4):
            body = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(self.base_url + "/chat/completions",
                                         data=body, headers=headers, method="POST")
            pieces: list[str] = []
            started = False
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    for raw in resp:
                        if should_cancel and should_cancel():
                            raise Cancelled("cancelled")
                        line = raw.decode("utf-8", "replace").strip()
                        if not line.startswith("data:"):
                            continue
                        data = line[5:].strip()
                        if data == "[DONE]":
                            break
                        try:
                            obj = json.loads(data)
                        except json.JSONDecodeError:
                            continue
                        self._add_usage(model, obj.get("usage"))
                        choices = obj.get("choices") or []
                        if not choices:
                            continue
                        choice = choices[0]
                        if choice.get("finish_reason"):
                            self.last_finish = choice["finish_reason"]
                        delta = choice.get("delta") or {}
                        thinking = delta.get("reasoning_content") or ""
                        if thinking and on_thinking:
                            on_thinking(thinking)
                        piece = delta.get("content") or ""
                        if piece:
                            started = True
                            pieces.append(piece)
                            if on_delta:
                                on_delta(piece)
                return "".join(pieces)
            except Cancelled:
                raise
            except urllib.error.HTTPError as e:
                detail = ""
                try:
                    detail = e.read().decode("utf-8", "replace")[:400]
                except Exception:
                    pass
                last_err = f"HTTP {e.code}: {detail}"
                if e.code == 400 and include_usage:
                    include_usage = False
                    payload.pop("stream_options", None)
                    continue
                if started:
                    raise LLMError(last_err) from e
                if e.code in (408, 409, 429, 500, 502, 503, 504) and attempt < 3:
                    time.sleep(2 ** attempt)
                    continue
                raise LLMError(last_err) from e
            except (urllib.error.URLError, TimeoutError, OSError, KeyError,
                    json.JSONDecodeError) as e:
                last_err = f"{type(e).__name__}: {e}"
                if started:
                    raise LLMError(last_err) from e
                if attempt < 3:
                    time.sleep(2 ** attempt)
                    continue
                raise LLMError(last_err) from e
        raise LLMError(last_err or "unknown error")


class MockLLM:
    """Deterministic stand-in so the whole flow can be tested without a key."""

    map_model = "mock"
    write_model = "mock"

    def __init__(self):
        self.last_finish = "stop"
        self.usage_by_model: dict[str, dict] = {}

    def _count(self, model: str, prompt: str, completion: str) -> None:
        u = self.usage_by_model.setdefault(model, {
            "prompt_tokens": 0, "completion_tokens": 0, "cache_hit_tokens": 0,
        })
        u["prompt_tokens"] += max(1, len(prompt) // 4)
        u["completion_tokens"] += max(1, len(completion) // 4)

    def chat(self, system: str, user: str, *, model: str, max_tokens: int = 8192,
             temperature: float = 0.2) -> str:
        if "note-taking engine" in system:
            chunk = user.split("--- BEGIN CHUNK ---", 1)[-1].split("--- END CHUNK ---", 1)[0]
            text = json.dumps(_mock_facts(chunk))
        elif "bullet-point extractor" in system:
            text = "- mock bullet\n- mock bullet"
        else:
            text = _mock_notes(user)
        self._count(model, system + user, text)
        return text

    def chat_stream(self, system: str, user: str, *, model: str, max_tokens: int = 8192,
                    temperature: float = 0.25, on_delta=None, on_thinking=None,
                    should_cancel=None) -> str:
        if on_thinking:
            on_thinking("Mock reasoning: picking the section order before writing. " * 4)
        text = self.chat(system, user, model=model, max_tokens=max_tokens,
                         temperature=temperature)
        step = max(160, len(text) // 10)
        for i in range(0, len(text), step):
            if should_cancel and should_cancel():
                raise Cancelled("cancelled")
            if on_delta:
                on_delta(text[i:i + step])
        return text


def _mock_facts(chunk: str) -> dict:
    lines = [ln.strip() for ln in chunk.splitlines() if ln.strip()]
    cmds = [ln for ln in lines if re.match(r"^\s*(kubectl|helm|openssl|ssh|docker|kind)\b", ln)]
    return {
        "concepts": [{"name": "MOCK concept",
                      "explanation": (lines[0][:180] if lines else ""),
                      "why_it_matters": "mock"}],
        "definitions": [],
        "commands": [{"command": c[:180], "purpose": "mock", "notes": ""} for c in cmds[:5]],
        "yaml": [], "demos": [], "numbers": [], "comparisons": [],
        "gotchas": [], "analogies": [], "quotes": [], "processes": [],
        "assumed_knowledge": [],
        "open_questions": ["MOCK MODE - no model was called"],
    }


def _mock_notes(user: str) -> str:
    return (
        "# MOCK OUTPUT - pipeline smoke test\n\n"
        "> Produced with `--mock` / mock mode: no model was called.\n\n"
        "## 1) What the pipeline did\n\n"
        "- Chunked the source.\n- Extracted facts per chunk (mocked).\n"
        "- Rendered facts and wrote notes (mocked).\n\n"
        "## 2) Writer prompt size\n\n"
        f"- {len(user)} characters reached the writing model.\n\n"
        "## 3) Key Takeaways\n\n1. Mock mode works.\n\n"
        "*End of mock notes.*\n"
    )


# ---------------------------------------------------------------------------
# chunking - must always produce chunks <= max_chars
# ---------------------------------------------------------------------------

def _normalise(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n").strip()


def _fixed_slices(text: str, max_chars: int, overlap: int) -> list[str]:
    """Last-resort splitter: cut on a newline/space near the limit, else raw."""
    slices, start, n = [], 0, len(text)
    while start < n:
        end = min(start + max_chars, n)
        if end < n:
            window = text[start:end]
            cut = max(window.rfind("\n\n"), window.rfind("\n"), window.rfind(". "))
            if cut > int(max_chars * 0.5):
                end = start + cut + 1
        slices.append(text[start:end].strip())
        if end >= n:
            break
        start = max(end - overlap, start + 1)
    return [s for s in slices if s]


def _split_oversized(unit: str, max_chars: int, overlap: int) -> list[str]:
    if len(unit) <= max_chars:
        return [unit]
    paras = re.split(r"\n\s*\n", unit)
    if len(paras) == 1:                      # a wall of text, no blank lines
        return _fixed_slices(unit, max_chars, overlap)
    out: list[str] = []
    buf = ""
    for p in paras:
        for piece in (_fixed_slices(p, max_chars, overlap) if len(p) > max_chars else [p]):
            if len(buf) + len(piece) + 2 > max_chars and buf:
                out.append(buf.strip())
                buf = piece
            else:
                buf = (buf + "\n\n" + piece) if buf else piece
    if buf.strip():
        out.append(buf.strip())
    return out


def _units(text: str) -> list[str]:
    if re.search(r"^##\s+", text, flags=re.M):
        return [u for u in re.split(r"(?m)^(?=##\s+)", text) if u.strip()]
    return [u for u in re.split(r"\n\s*\n", text) if u.strip()]


def chunk_text(text: str, max_chars: int = MAX_CHUNK_CHARS,
               overlap: int = CHUNK_OVERLAP) -> list[str]:
    text = _normalise(text)
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]

    chunks: list[str] = []
    buf = ""
    for unit in _units(text):
        for piece in _split_oversized(unit, max_chars, overlap):
            if len(buf) + len(piece) + 2 > max_chars and buf:
                chunks.append(buf.strip())
                buf = piece
            else:
                buf = (buf + "\n\n" + piece) if buf else piece
    if buf.strip():
        chunks.append(buf.strip())

    # Final guarantee: nothing oversized may reach the extraction model.
    safe: list[str] = []
    for c in chunks:
        safe.extend(_fixed_slices(c, max_chars, overlap) if len(c) > max_chars else [c])
    return safe


# ---------------------------------------------------------------------------
# cache
# ---------------------------------------------------------------------------

def _cache_key(*parts: str) -> str:
    h = hashlib.sha256()
    for p in parts:
        h.update(p.encode("utf-8", "replace"))
        h.update(b"\x00")
    return h.hexdigest()[:32]


def _cache_get(key: str):
    f = CACHE_DIR / f"{key}.json"
    if f.exists():
        try:
            return json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            return None
    return None


def _cache_put(key: str, value) -> None:
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        (CACHE_DIR / f"{key}.json").write_text(json.dumps(value, ensure_ascii=False),
                                               encoding="utf-8")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# tolerant JSON parsing
# ---------------------------------------------------------------------------

def _repair_json(s: str) -> str:
    s = re.sub(r",\s*([}\]])", r"\1", s)          # trailing commas
    s = s.replace("\u201c", '"').replace("\u201d", '"')
    s = re.sub(r"(?<=[}\]\"0-9a-z])\s+(?=[}\]])", "", s, flags=re.I)
    opens = s.count("{") - s.count("}")
    if opens > 0:
        s += "}" * opens
    opens = s.count("[") - s.count("]")
    if opens > 0:
        s += "]" * opens
    return s


def parse_json_loose(raw: str) -> dict:
    s = (raw or "").strip()
    s = re.sub(r"^```(?:json)?\s*", "", s)
    s = re.sub(r"\s*```$", "", s)
    start = s.find("{")
    if start == -1:
        raise ValueError("no JSON object in response")
    body = s[start:]
    # try progressively shorter prefixes, from the last '}' backwards
    ends = [m.start() for m in re.finditer(r"\}", body)]
    for end in reversed(ends[-4:] if len(ends) > 4 else ends):
        cand = body[:end + 1]
        for attempt in (cand, _repair_json(cand)):
            try:
                return json.loads(attempt)
            except Exception:
                continue
    raise ValueError("could not parse JSON even after repair")


def _coerce_facts(parsed) -> dict:
    keys = ["concepts", "definitions", "commands", "yaml", "demos", "numbers",
            "comparisons", "gotchas", "analogies", "quotes", "processes",
            "assumed_knowledge", "open_questions"]
    out = {}
    if not isinstance(parsed, dict):
        return {"bullet_fallback": str(parsed)}
    for k in keys:
        v = parsed.get(k)
        out[k] = v if isinstance(v, list) else ([] if v is None else [v])
    if parsed.get("bullet_fallback"):
        out["bullet_fallback"] = str(parsed["bullet_fallback"])
    return out


# ---------------------------------------------------------------------------
# facts rendering
# ---------------------------------------------------------------------------

def render_facts(facts_list: list[dict]) -> str:
    out: list[str] = []

    def head(title):
        out.append("\n## " + title)

    for f in facts_list:
        if f.get("bullet_fallback"):
            head("Raw notes (fallback extraction)")
            out.append(f["bullet_fallback"])
        if f.get("concepts"):
            head("Concepts")
            for c in f["concepts"]:
                if isinstance(c, str):
                    out.append("- " + c); continue
                out.append(f"- **{c.get('name','')}** - {c.get('explanation','')}"
                           f" Why: {c.get('why_it_matters','')}".rstrip(". ") + ".")
        if f.get("definitions"):
            head("Definitions")
            for d in f["definitions"]:
                if isinstance(d, str):
                    out.append("- " + d); continue
                out.append(f"- **{d.get('term','')}** - {d.get('meaning','')}")
        if f.get("commands"):
            head("Commands")
            for c in f["commands"]:
                if isinstance(c, str):
                    out.append(f"- `{c}`"); continue
                note = f" ({c['notes']})" if c.get("notes") else ""
                out.append(f"- `{c.get('command','')}` - {c.get('purpose','')}{note}")
        if f.get("yaml"):
            head("YAML")
            for y in f["yaml"]:
                if isinstance(y, str):
                    out.append(f"- ```yaml\n{y}\n```"); continue
                out.append(f"- {y.get('caption','')}:\n\n```yaml\n{y.get('body','')}\n```")
        if f.get("demos"):
            head("Demos")
            for d in f["demos"]:
                if isinstance(d, str):
                    out.append("- " + d); continue
                steps = "; ".join(str(s) for s in d.get("steps", []) if s)
                out.append(f"- **{d.get('title','')}** - {steps} "
                           f"Observed: {d.get('observed_output','')}")
        if f.get("numbers"):
            head("Numbers and versions")
            for n in f["numbers"]:
                if isinstance(n, str):
                    out.append("- " + n); continue
                out.append(f"- {n.get('fact','')}: {n.get('value','')}")
        if f.get("comparisons"):
            head("Comparisons")
            for c in f["comparisons"]:
                if isinstance(c, str):
                    out.append("- " + c); continue
                out.append(f"- {c.get('subject','')}: {c.get('left','')} vs "
                           f"{c.get('right','')} - {c.get('detail','')}")
        if f.get("gotchas"):
            head("Gotchas")
            for g in f["gotchas"]:
                if isinstance(g, str):
                    out.append("- " + g); continue
                out.append(f"- {g.get('problem','')} -> {g.get('cause','')} -> "
                           f"{g.get('fix','')}")
        if f.get("analogies"):
            head("Analogies")
            for a in f["analogies"]:
                if isinstance(a, str):
                    out.append("- " + a); continue
                out.append(f"- {a.get('analogy','')} -> maps to {a.get('maps_to','')}")
        if f.get("quotes"):
            head("Instructor quotes")
            for q in f["quotes"]:
                if isinstance(q, str):
                    out.append(f"- \"{q}\""); continue
                out.append(f"- \"{q.get('quote','')}\" ({q.get('context','')})")
        if f.get("processes"):
            head("Processes")
            for p in f["processes"]:
                if isinstance(p, str):
                    out.append("- " + p); continue
                out.append(f"- {p.get('name','')}: " + ", ".join(p.get("steps", [])))
        if f.get("assumed_knowledge"):
            head("Assumed knowledge")
            for k in f["assumed_knowledge"]:
                out.append(f"- {k if isinstance(k, str) else k}")
        if f.get("open_questions"):
            head("Open questions / uncertain")
            for q in f["open_questions"]:
                out.append(f"- {q}")
    return "\n".join(out).strip()


# ---------------------------------------------------------------------------
# output naming
# ---------------------------------------------------------------------------

def slugify(text: str, fallback: str = "notes") -> str:
    s = re.sub(r"\.(md|txt|markdown)$", "", text or "", flags=re.I)
    s = re.sub(r"[^\w\s-]", "", s).strip().lower()
    s = re.sub(r"[\s_]+", "-", s)
    s = re.sub(r"-{2,}", "-", s).strip("-")
    return s[:80] or fallback


def unique_output(slug: str, style: str) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    base = f"{slug}.{style}"
    dest = OUTPUT_DIR / f"{base}.md"
    n = 2
    while dest.exists():
        dest = OUTPUT_DIR / f"{base}-{n}.md"
        n += 1
    return dest


# ---------------------------------------------------------------------------
# pipeline stages
# ---------------------------------------------------------------------------

def _extract_chunk(llm, chunk: str, source: str, label: str, log, progress,
                   depth: int = 0, index: int = 1, total: int = 1,
                   should_cancel=None) -> tuple[list[dict], dict]:
    """Extract one chunk. Returns (facts, meta) and never dies on bad JSON."""
    meta = {"cached": False, "splits": 0, "fallback": False}
    if should_cancel and should_cancel():
        raise Cancelled("cancelled")

    key = _cache_key(prompts.EXTRACT_VERSION, "extract", llm.map_model, chunk)
    cached = _cache_get(key)
    if cached is not None:
        log(f"{label} cached ({len(chunk)} chars)")
        meta["cached"] = True
        return [cached], meta

    log(f"{label} extracting {len(chunk)} chars (depth {depth})")
    user = prompts.EXTRACT_USER.format(source=source, index=index, total=total, chunk=chunk)
    raw = llm.chat(prompts.EXTRACT_SYSTEM, user, model=llm.map_model,
                   max_tokens=8000, temperature=0.0)
    truncated = getattr(llm, "last_finish", "") == "length"

    parsed = None
    if not truncated:
        try:
            parsed = _coerce_facts(parse_json_loose(raw))
        except Exception as e:
            log(f"{label} JSON unusable ({e}); will split/fallback")
    else:
        log(f"{label} hit the output limit; will split")

    if parsed is not None:
        _cache_put(key, parsed)
        return [parsed], meta

    # Adaptive recovery: halve the chunk and extract each half.
    if depth < MAX_SPLIT_DEPTH and len(chunk) >= MIN_SPLIT_CHARS:
        mid = len(chunk) // 2
        cut = chunk.rfind("\n", 0, mid)
        if cut < len(chunk) * 0.3:
            cut = chunk.find("\n", mid)
            if cut < 0:
                cut = mid
        left, right = chunk[:cut].strip(), chunk[cut:].strip()
        if left and right:
            log(f"{label} split into {len(left)} + {len(right)} chars")
            lf, lm = _extract_chunk(llm, left, source, label + ".a", log, progress,
                                    depth + 1, index, total, should_cancel)
            rf, rm = _extract_chunk(llm, right, source, label + ".b", log, progress,
                                    depth + 1, index, total, should_cancel)
            meta["splits"] = 1 + lm["splits"] + rm["splits"]
            meta["fallback"] = lm["fallback"] or rm["fallback"]
            meta["cached"] = lm["cached"] and rm["cached"]
            return lf + rf, meta

    # Last resort: plain bullets, so the run never dies on a parse error.
    # Deliberately not cached: a transient bad response should not poison the
    # cache forever, so the next run gets another shot at structured JSON.
    log(f"{label} falling back to bullet extraction")
    text = llm.chat(prompts.BULLET_SYSTEM, prompts.BULLET_USER.format(
        source=source, chunk=chunk), model=llm.map_model, max_tokens=4000, temperature=0.0)
    meta["fallback"] = True
    return [{"bullet_fallback": text.strip()}], meta


def extract_facts(llm, chunks: list[str], source: str, log, progress,
                  should_cancel=None) -> list[dict]:
    facts: list[dict] = []
    total_chars = sum(len(c) for c in chunks) or 1
    done_chars = 0
    for i, chunk in enumerate(chunks, 1):
        if should_cancel and should_cancel():
            raise Cancelled("cancelled")
        base = {"stage": "map", "index": i, "total": len(chunks),
                "chars": done_chars, "total_chars": total_chars,
                "chunk_chars": len(chunk)}
        progress({**base, "done": i - 1, "working": True, "secs": 0,
                  "cached": False, "splits": 0, "fallback": False})
        t0 = time.time()
        got, meta = _extract_chunk(llm, chunk, source, f"[map {i}/{len(chunks)}]",
                                   log, progress, index=i, total=len(chunks),
                                   should_cancel=should_cancel)
        facts.extend(got)
        done_chars += len(chunk)
        progress({**base, "done": i, "chars": done_chars, "working": False,
                  "secs": round(time.time() - t0, 1), **meta})
    return facts


def reduce_facts(llm, facts_text: str, source: str, log, progress,
                 should_cancel=None, threshold: int | None = None) -> str:
    threshold = threshold if threshold is not None else MAX_FACT_CHARS
    if len(facts_text) <= threshold:
        return facts_text
    log(f"[compress] facts are {len(facts_text)} chars - flash compresses before the write")
    parts = [facts_text[i:i + MAX_FACT_CHARS] for i in range(0, len(facts_text), MAX_FACT_CHARS)]
    reduced = []
    for i, part in enumerate(parts, 1):
        if should_cancel and should_cancel():
            raise Cancelled("cancelled")
        progress({"stage": "reduce", "done": i - 1, "total": len(parts)})
        reduced.append(llm.chat(prompts.REDUCE_SYSTEM, prompts.REDUCE_USER.format(
            source=source, index=i, total=len(parts), facts=part),
            model=llm.map_model, max_tokens=8000, temperature=0.0))
        progress({"stage": "reduce", "done": i, "total": len(parts)})
    return "\n\n".join(reduced)


def write_notes(llm, facts_text: str, mode: str, source: str, title: str,
                date: str, log, progress, on_delta=None, on_thinking=None,
                should_cancel=None) -> str:
    system, user = prompts.build_write_messages(mode, facts_text, source, date, title)
    progress({"stage": "write", "written": 0, "prompt_chars": len(user)})
    log(f"[write] {llm.write_model} is writing {len(facts_text)} chars of facts")

    key = _cache_key(prompts.WRITE_VERSION, "write", llm.write_model, mode,
                     str(WRITE_MAX_TOKENS), user)
    cached = _cache_get(key)
    if isinstance(cached, dict) and cached.get("md"):
        log("[write] served from cache")
        md = cached["md"]
        progress({"stage": "write", "written": 0, "prompt_chars": len(user),
                  "cached": True})
        if on_delta:
            on_delta(md)
        return md

    # Adaptive cap: if the model comes back empty or truncated, retry with a
    # larger budget instead of saving a blank file. Only the first attempt
    # streams, so a retry never duplicates text in the live preview.
    caps = [WRITE_MAX_TOKENS]
    cap = WRITE_MAX_TOKENS
    while cap < WRITE_MAX_RETRY_CAP:
        cap = min(cap * 2, WRITE_MAX_RETRY_CAP)
        caps.append(cap)

    md = ""
    for i, cap in enumerate(caps):
        if i > 0:
            progress({"stage": "write", "written": 0, "attempt": i, "retry_cap": cap})
        md = llm.chat_stream(
            system, user, model=llm.write_model, max_tokens=cap,
            temperature=0.25,
            on_delta=(on_delta if i == 0 else None),
            on_thinking=(on_thinking if i == 0 else None),
            should_cancel=should_cancel)
        truncated = getattr(llm, "last_finish", "") == "length"
        empty = not (md or "").strip()
        if (empty or truncated) and i < len(caps) - 1:
            log(f"[write] {'no content' if empty else 'truncated'} at {cap} tokens; "
                f"retrying with {caps[i + 1]}")
            continue
        break

    if not (md or "").strip():
        raise LLMError(
            f"the writing model returned no notes even at {cap} tokens. "
            "Use deepseek-flash for the write, or split the lecture.")
    if getattr(llm, "last_finish", "") == "length":
        log(f"[write] WARNING: output hit the token cap at {cap} tokens - notes may "
            "be truncated. Raise NOTES_WRITE_MAX_TOKENS, use deepseek-flash, or "
            "split the lecture.")
    md = _strip_fences(md)
    _cache_put(key, {"md": md})
    return md


def _strip_fences(md: str) -> str:
    s = (md or "").strip()
    if s.startswith("```"):
        s = re.sub(r"^```[a-zA-Z]*\s*\n", "", s)
        s = re.sub(r"\n```\s*$", "", s)
    return s.strip() + "\n"


# ---------------------------------------------------------------------------
# entry point
# ---------------------------------------------------------------------------

def run_job(*, mode: str = "complete-fresh", input_path: str | None = None,
            content: str | None = None, name: str | None = None,
            title: str | None = None, out_path: str | None = None,
            mock: bool = False, api_key: str | None = None,
            base_url: str | None = None, map_model: str | None = None,
            write_model: str | None = None, log=_nop, progress=_nop_progress,
            should_cancel=None, on_delta=None, on_thinking=None) -> dict:
    if mode not in prompts.MODE_SPECS:
        raise ValueError(f"unknown mode {mode!r}")

    started = time.time()
    if input_path:
        src_path = Path(input_path).resolve()
        if not src_path.exists():
            raise FileNotFoundError(src_path)
        text = src_path.read_text(encoding="utf-8", errors="replace")
        source_name = src_path.name
    else:
        text = content or ""
        source_name = name or "pasted.md"
        src_path = None
    if not text.strip():
        raise ValueError("source is empty")

    display_title = (title or "").strip() or Path(source_name).stem.replace("_", " ").replace("-", " ")
    date_str = datetime.now().strftime("%Y-%m-%d")
    log(f"[load] {source_name}: {len(text)} chars, title={display_title!r}, mode={mode}")

    progress({"stage": "chunk", "total_chars": len(text), "chunks": 0})
    chunks = chunk_text(text)
    progress({"stage": "chunk", "total_chars": len(text), "chunks": len(chunks)})
    log(f"[chunk] {len(chunks)} chunk(s), max {max((len(c) for c in chunks), default=0)} chars")

    if mock:
        llm = MockLLM()
    else:
        llm = LLM(base_url or DEFAULT_BASE_URL,
                  api_key if api_key is not None else os.environ.get("DEEPSEEK_API_KEY", ""),
                  map_model or DEFAULT_MAP_MODEL,
                  write_model or DEFAULT_WRITE_MODEL)

    def report(info: dict):
        """progress() plus a token snapshot, so the server can price live."""
        info = dict(info)
        info["usage"] = {k: dict(v) for k, v in getattr(llm, "usage_by_model", {}).items()}
        progress(info)

    facts = extract_facts(llm, chunks, source_name, log, report,
                          should_cancel=should_cancel)
    facts_text = render_facts(facts)
    log(f"[facts] {len(facts_text)} chars extracted")
    facts_text = reduce_facts(llm, facts_text, source_name, log, report,
                              should_cancel=should_cancel,
                              threshold=COMPRESS_THRESHOLD_CHARS)
    md = write_notes(llm, facts_text, mode, source_name, display_title, date_str,
                     log, report, on_delta=on_delta, on_thinking=on_thinking,
                     should_cancel=should_cancel)

    if should_cancel and should_cancel():
        raise Cancelled("cancelled")

    style = prompts.MODE_SPECS[mode]["style"]
    if out_path:
        dest = Path(out_path).resolve()
        dest.parent.mkdir(parents=True, exist_ok=True)
    else:
        dest = unique_output(slugify(display_title), style)
    dest.write_text(md, encoding="utf-8")

    elapsed = round(time.time() - started, 1)
    log(f"[done] {dest.name} ({len(md)} chars) in {elapsed}s")
    progress({"stage": "done", "elapsed": elapsed})
    return {"md": md, "out": str(dest), "backup": None,
            "title": display_title, "style": style,
            "chunks": len(chunks), "facts_chars": len(facts_text),
            "source_chars": len(text),
            "elapsed": elapsed,
            "map_model": llm.map_model, "write_model": llm.write_model,
            "usage": {k: dict(v) for k, v in getattr(llm, "usage_by_model", {}).items()}}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def selftest() -> int:
    """Prove the chunker can never hand an oversized chunk to the extractor."""
    cases = {
        "blank lines": ("para one.\n\n" * 3000),
        "single newlines": ("line of transcript text\n" * 5000),
        "one giant word": ("x" * 60000),
        "headings": ("".join(f"## Section {i}\n" + ("filler text. " * 200) + "\n\n"
                             for i in range(40))),
        "mixed": ("intro\n\n## A\n" + ("a " * 9000) + "\n\n## B\n" + ("b\n" * 4000)),
    }
    ok = True
    for name, text in cases.items():
        chunks = chunk_text(text)
        biggest = max((len(c) for c in chunks), default=0)
        status = "OK" if biggest <= MAX_CHUNK_CHARS else "FAIL"
        if status == "FAIL":
            ok = False
        print(f"{status:4} {name:16} chars={len(text):7} chunks={len(chunks):3} "
              f"largest={biggest:6} limit={MAX_CHUNK_CHARS}")
    return 0 if ok else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Turn transcripts into study notes.")
    ap.add_argument("--input", "-i")
    ap.add_argument("--mode", "-m", default="complete-fresh", choices=sorted(prompts.MODE_SPECS))
    ap.add_argument("--out", "-o", help="explicit output path (default: output/ folder)")
    ap.add_argument("--title", "-t", help="source title used in the notes header")
    ap.add_argument("--mock", action="store_true")
    ap.add_argument("--map-model")
    ap.add_argument("--write-model")
    ap.add_argument("--base-url")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)

    if args.selftest:
        return selftest()

    try:
        result = run_job(mode=args.mode, input_path=args.input, out_path=args.out,
                         title=args.title, mock=args.mock,
                         base_url=args.base_url, map_model=args.map_model,
                         write_model=args.write_model,
                         log=lambda m: print(m, flush=True))
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    print(f"\nDone: {result['out']}  ({result['elapsed']}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
