"""Local web UI + job runner for the notes pipeline.

    python server.py --port 8765            # real runs (needs DEEPSEEK_API_KEY)
    python server.py --port 8765 --mock     # click through the flow with no key

Then open http://127.0.0.1:8765
Binds to loopback only; nothing is exposed to the network.
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import threading
import time
import traceback
import uuid
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import costs
import pipeline
import prompts

HERE = Path(__file__).resolve().parent
BASE_DIR = HERE.parent  # the notes folder this tool lives in
OUTPUT_DIR = HERE / "output"
ALLOWED_SUFFIXES = {".md", ".txt", ".markdown"}

JOBS: dict[str, dict] = {}
JOBS_LOCK = threading.Lock()
OPTIONS = {"mock": False}
APP_VERSION = "2026-11-09.8"

MODEL_CHOICES = [
    {"id": "deepseek-flash", "label": "deepseek-flash · fast + cheap"},
    {"id": "deepseek-v4-pro", "label": "deepseek-v4-pro · best writing, pricier"},
    {"id": "deepseek-chat", "label": "deepseek-chat · legacy alias of flash"},
    {"id": "deepseek-reasoner", "label": "deepseek-reasoner · legacy thinking mode"},
]


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def list_sources() -> list[dict]:
    out = []
    for p in BASE_DIR.rglob("*"):
        if not p.is_file() or p.suffix.lower() not in ALLOWED_SUFFIXES:
            continue
        if "_notes-pipeline" in p.parts:
            continue
        try:
            st = p.stat()
        except OSError:
            continue
        out.append({
            "name": p.name,
            "path": str(p),
            "rel": str(p.relative_to(BASE_DIR)),
            "kb": round(st.st_size / 1024, 1),
            "mtime": st.st_mtime,
        })
    out.sort(key=lambda x: x["mtime"], reverse=True)
    return out[:300]


def list_outputs() -> list[dict]:
    out = []
    if not OUTPUT_DIR.exists():
        return out
    for p in OUTPUT_DIR.glob("*.md"):
        try:
            st = p.stat()
            lines = sum(1 for _ in p.open(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        out.append({
            "name": p.name,
            "path": str(p),
            "kb": round(st.st_size / 1024, 1),
            "lines": lines,
            "mtime": st.st_mtime,
        })
    out.sort(key=lambda x: x["mtime"], reverse=True)
    return out


def inside_base(path: Path) -> bool:
    try:
        path.resolve().relative_to(BASE_DIR.resolve())
        return True
    except ValueError:
        return False


def new_job(pricing: dict | None = None) -> tuple[str, dict]:
    job_id = uuid.uuid4().hex[:12]
    job = {
        "id": job_id, "status": "running", "log": [], "result": None,
        "error": None, "started": time.time(), "progress": {},
        "cancel": False, "deltas": [], "usage_by_model": {},
        "pricing": pricing or costs.load_pricing(),
        "cost": None, "written": 0, "prompt_chars": 0, "thinking_chars": 0,
        "write_cached": False,
    }
    with JOBS_LOCK:
        JOBS[job_id] = job
        # keep memory bounded on a long-lived server
        if len(JOBS) > 40:
            finished = [k for k, v in JOBS.items() if v["status"] != "running"]
            for k in finished[:max(0, len(JOBS) - 40)]:
                JOBS.pop(k, None)
    return job_id, job


def log_into(job: dict):
    def _log(msg: str) -> None:
        stamp = time.strftime("%H:%M:%S")
        with JOBS_LOCK:
            job["log"].append(f"{stamp}  {msg}")
    return _log


# ---------------------------------------------------------------------------
# HTTP handler
# ---------------------------------------------------------------------------

class Handler(BaseHTTPRequestHandler):
    server_version = "NotesPipeline/1.0"

    # -- plumbing ----------------------------------------------------------
    def log_message(self, fmt, *args):  # quiet console
        pass

    def _send(self, code: int, body: bytes, ctype: str = "application/json"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _json(self, code: int, obj):
        self._send(code, json.dumps(obj).encode("utf-8"))

    def _body(self) -> dict:
        n = int(self.headers.get("Content-Length") or 0)
        if not n:
            return {}
        return json.loads(self.rfile.read(n).decode("utf-8"))

    # -- routes ------------------------------------------------------------
    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)

        if u.path in ("/", "/index.html"):
            html = (HERE / "index.html").read_bytes()
            return self._send(200, html, "text/html; charset=utf-8")

        if u.path == "/api/health":
            return self._json(200, {"ok": True, "mock": OPTIONS["mock"],
                                    "version": APP_VERSION,
                                    "base": str(BASE_DIR),
                                    "output": str(OUTPUT_DIR)})

        if u.path == "/api/files":
            return self._json(200, {"files": list_sources()})

        if u.path == "/api/outputs":
            return self._json(200, {"dir": str(OUTPUT_DIR), "files": list_outputs()})

        if u.path == "/api/output":
            name = q.get("name", [""])[0]
            target = (OUTPUT_DIR / name).resolve()
            try:
                target.relative_to(OUTPUT_DIR.resolve())
            except ValueError:
                return self._json(400, {"error": "bad path"})
            if not target.exists() or target.suffix.lower() != ".md":
                return self._json(404, {"error": "not found"})
            return self._json(200, {"name": target.name,
                                    "md": target.read_text(encoding="utf-8", errors="replace")})

        if u.path == "/api/modes":
            return self._json(200, {"modes": [
                {"id": k, "label": v["label"]} for k, v in prompts.MODE_SPECS.items()
            ]})

        if u.path == "/api/models":
            import os as _os
            return self._json(200, {
                "choices": MODEL_CHOICES,
                "default_map": _os.environ.get("NOTES_MAP_MODEL", pipeline.DEFAULT_MAP_MODEL),
                "default_write": _os.environ.get("NOTES_WRITE_MODEL", pipeline.DEFAULT_WRITE_MODEL),
                "mock": OPTIONS["mock"],
            })

        if u.path == "/api/stream":
            return self._stream(q.get("job", [""])[0])

        if u.path == "/api/result":
            job_id = q.get("job", [""])[0]
            job = JOBS.get(job_id)
            if not job:
                return self._json(404, {"error": "unknown job"})
            return self._json(200, {
                "status": job["status"],
                "log": job["log"],
                "error": job["error"],
                "progress": job.get("progress") or {},
                "md": (job["result"] or {}).get("md"),
                "out": (job["result"] or {}).get("out"),
                "title": (job["result"] or {}).get("title"),
                "style": (job["result"] or {}).get("style"),
                "source": job.get("source"),
                "source_path": job.get("source_path"),
                "chunks": (job["result"] or {}).get("chunks"),
                "source_chars": (job["result"] or {}).get("source_chars"),
                "elapsed": (job["result"] or {}).get("elapsed"),
                "map_model": job.get("map_model"),
                "write_model": job.get("write_model"),
                "usage": job.get("usage_by_model") or {},
                "cost": job.get("cost"),
            })

        self._json(404, {"error": "not found"})

    def do_POST(self):
        u = urlparse(self.path)
        try:
            if u.path == "/api/run":
                return self._run(self._body())
            if u.path == "/api/estimate":
                return self._estimate(self._body())
            if u.path == "/api/cancel":
                return self._cancel(self._body())
        except Exception as e:
            traceback.print_exc()
            return self._json(500, {"error": f"{type(e).__name__}: {e}"})
        self._json(404, {"error": "not found"})

    # -- endpoints ---------------------------------------------------------
    def _run(self, body: dict):
        mode = body.get("mode") or "complete-fresh"
        if mode not in prompts.MODE_SPECS:
            return self._json(400, {"error": f"bad mode {mode}"})

        path = (body.get("path") or "").strip()
        content = body.get("content")
        name = (body.get("name") or "").strip()
        title = (body.get("title") or "").strip()

        if not path and not content:
            return self._json(400, {"error": "provide a file path or file content"})
        if path:
            p = Path(path).resolve()
            if not inside_base(p):
                return self._json(400, {"error": "path outside the notes folder"})
            if not p.exists():
                return self._json(400, {"error": "file not found"})

        pricing = costs.load_pricing(override=body.get("pricing"))
        job_id, job = new_job(pricing)
        job["mode"] = mode
        job["source"] = name or (Path(path).name if path else "pasted file")
        job["source_path"] = str(Path(path).resolve()) if path else None
        job["map_model"] = (body.get("map_model") or "").strip() or pipeline.DEFAULT_MAP_MODEL
        job["write_model"] = (body.get("write_model") or "").strip() or pipeline.DEFAULT_WRITE_MODEL

        def worker():
            log = log_into(job)

            def progress(info: dict):
                with JOBS_LOCK:
                    merged = dict(job.get("progress") or {})
                    merged.update(info)
                    job["progress"] = merged
                    usage = info.get("usage")
                    if isinstance(usage, dict):
                        job["usage_by_model"] = usage
                    if info.get("stage") == "write":
                        if "written" in info:
                            job["written"] = int(info.get("written") or 0)
                        if "prompt_chars" in info:
                            job["prompt_chars"] = int(info.get("prompt_chars") or 0)
                        if info.get("cached"):
                            job["write_cached"] = True

            def on_delta(text: str) -> None:
                if not text:
                    return
                with JOBS_LOCK:
                    job["deltas"].append(text)
                    job["written"] += len(text)
                    p = dict(job.get("progress") or {})
                    p["stage"] = "write"
                    p["written"] = job["written"]
                    job["progress"] = p

            def on_thinking(text: str) -> None:
                if not text:
                    return
                with JOBS_LOCK:
                    job["thinking_chars"] += len(text)
                    p = dict(job.get("progress") or {})
                    p["stage"] = "write"
                    p["thinking_chars"] = job["thinking_chars"]
                    job["progress"] = p

            def should_cancel() -> bool:
                return bool(job.get("cancel"))

            try:
                result = pipeline.run_job(
                    mode=mode,
                    input_path=path or None,
                    content=content,
                    name=name or None,
                    title=title or None,
                    mock=OPTIONS["mock"],
                    map_model=job["map_model"],
                    write_model=job["write_model"],
                    log=log,
                    progress=progress,
                    should_cancel=should_cancel,
                    on_delta=on_delta,
                    on_thinking=on_thinking,
                )
                usage = result.get("usage") or job["usage_by_model"]
                if OPTIONS["mock"]:
                    cost = {"models": {}, "usd": 0.0, "inr": 0.0, "peak": False,
                            "tokens": {"in": 0, "out": 0}, "estimated": False}
                elif job.get("written") and not job.get("write_cached") and not (
                        usage.get(job["write_model"]) or {}).get("completion_tokens"):
                    # Some OpenAI-compatible endpoints do not return usage on a
                    # streamed response; price the write from the text we saw.
                    cost = costs.live(
                        usage, job["pricing"], map_model=job["map_model"],
                        write_model=job["write_model"],
                        streaming_model=job["write_model"],
                        written_chars=job["written"],
                        prompt_chars=job["prompt_chars"],
                        thinking_chars=job["thinking_chars"])
                else:
                    cost = costs.breakdown(
                        usage, job["pricing"],
                        map_model=job["map_model"], write_model=job["write_model"])
                with JOBS_LOCK:
                    job["result"] = result
                    job["usage_by_model"] = result.get("usage") or job["usage_by_model"]
                    job["cost"] = cost
                    job["status"] = "done"
            except pipeline.Cancelled:
                log("cancelled by user")
                with JOBS_LOCK:
                    job["status"] = "cancelled"
            except Exception as e:
                log(f"ERROR: {type(e).__name__}: {e}")
                with JOBS_LOCK:
                    job["error"] = f"{type(e).__name__}: {e}"
                    job["status"] = "error"

        threading.Thread(target=worker, daemon=True).start()
        return self._json(200, {"job": job_id})

    def _estimate(self, body: dict):
        mode = body.get("mode") or "complete-fresh"
        if mode not in prompts.MODE_SPECS:
            return self._json(400, {"error": f"bad mode {mode}"})

        path = (body.get("path") or "").strip()
        content = body.get("content")
        if path:
            p = Path(path).resolve()
            if not inside_base(p):
                return self._json(400, {"error": "path outside the notes folder"})
            if not p.exists():
                return self._json(400, {"error": "file not found"})
            try:
                text = p.read_text(encoding="utf-8", errors="replace")
            except OSError as e:
                return self._json(400, {"error": f"cannot read file: {e}"})
        elif isinstance(content, str) and content.strip():
            text = content
        else:
            return self._json(400, {"error": "provide a file path or file content"})

        pricing = costs.load_pricing(override=body.get("pricing"))
        est = costs.estimate(
            text, mode,
            (body.get("map_model") or "").strip() or pipeline.DEFAULT_MAP_MODEL,
            (body.get("write_model") or "").strip() or pipeline.DEFAULT_WRITE_MODEL,
            pricing=pricing)
        if OPTIONS["mock"]:
            est["usd"] = est["inr"] = est["low_usd"] = est["high_usd"] = 0.0
            for leg in est.get("legs", []):
                leg["usd"] = 0.0
            est["mock"] = True
        return self._json(200, est)

    def _cancel(self, body: dict):
        job = JOBS.get((body.get("job") or "").strip())
        if not job:
            return self._json(404, {"error": "unknown job"})
        with JOBS_LOCK:
            job["cancel"] = True
            status = job["status"]
        return self._json(200, {"ok": True, "status": status})

    # -- SSE ---------------------------------------------------------------
    def _stream(self, job_id: str):
        job = JOBS.get(job_id)
        if not job:
            return self._json(404, {"error": "unknown job"})

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Accel-Buffering", "no")
        self.send_header("Connection", "close")
        self.end_headers()
        # Stream until the job ends, then let the socket close so clients
        # (and EventSource) see EOF instead of waiting on keep-alive.
        self.close_connection = True

        sent = 0
        last_progress = None
        try:
            while True:
                with JOBS_LOCK:
                    lines = job["log"][sent:]
                    status = job["status"]
                    progress = dict(job.get("progress") or {})
                    delta = "".join(job["deltas"])
                    job["deltas"].clear()
                    usage = dict(job.get("usage_by_model") or {})
                    written = int(job.get("written") or 0)
                    prompt_chars = int(job.get("prompt_chars") or 0)
                    thinking = int(job.get("thinking_chars") or 0)
                    pricing = job.get("pricing") or costs.load_pricing()
                    map_model = job.get("map_model") or ""
                    write_model = job.get("write_model") or ""
                    write_cached = bool(job.get("write_cached"))
                    pending = len(job["log"]) - sent
                for line in lines:
                    self.wfile.write(f"data: {json.dumps(line)}\n\n".encode("utf-8"))
                sent += len(lines)

                if delta:
                    payload = json.dumps({"text": delta})
                    self.wfile.write(f"event: delta\ndata: {payload}\n\n".encode("utf-8"))

                if progress:
                    progress["cost"] = costs.live(
                        usage, pricing, map_model=map_model, write_model=write_model,
                        streaming_model=(write_model if progress.get("stage") == "write"
                                         and status == "running" and not write_cached else ""),
                        written_chars=written, prompt_chars=prompt_chars,
                        thinking_chars=thinking)
                if progress and progress != last_progress:
                    payload = json.dumps(progress)
                    self.wfile.write(f"event: progress\ndata: {payload}\n\n".encode("utf-8"))
                    last_progress = progress

                if not delta:
                    self.wfile.write(b": ping\n\n")
                self.wfile.flush()

                if status != "running" and pending <= 0:
                    self.wfile.write(
                        f"event: end\ndata: {json.dumps({'status': status})}\n\n".encode()
                    )
                    self.wfile.flush()
                    return
                time.sleep(0.2)
        except (BrokenPipeError, ConnectionResetError):
            return


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--mock", action="store_true")
    ap.add_argument("--no-browser", action="store_true")
    args = ap.parse_args()
    OPTIONS["mock"] = args.mock

    srv = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    url = f"http://127.0.0.1:{args.port}"
    print(f"Notes pipeline UI: {url}")
    print(f"Notes folder:      {BASE_DIR}")
    print(f"Mode:              {'MOCK (no API calls)' if args.mock else 'live (DEEPSEEK_API_KEY)'}")
    if not args.mock and not __import__("os").environ.get("DEEPSEEK_API_KEY"):
        print("! DEEPSEEK_API_KEY is not set - runs will fail. Use --mock to test the UI.")
    if not args.no_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nbye")


if __name__ == "__main__":
    main()
