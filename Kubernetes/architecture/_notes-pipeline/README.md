# Notes Pipeline

Turns **any source document** — a lecture transcript (.txt), a rough notes file
(.md), an article, whatever you paste — into structured study notes. A cheap
model extracts facts from chunks; a stronger model writes the document.

The point: **stop spending your chat context on long transcripts**, and keep
every generated note in one predictable place. Not tied to a course or day
number: give it a title, get a file.

---

## Quick start

> Windows blocks `.ps1` by default (`ExecutionPolicy: Restricted`), so use
> **`run.cmd`** — it bypasses the policy for that one process.

```powershell
cd _notes-pipeline

# 1) See it work with zero API calls (double-click run.cmd also works)
.\run.cmd -Mock

# 2) Real runs
$env:DEEPSEEK_API_KEY = "sk-..."     # session only
.\run.cmd
```

The browser opens `http://127.0.0.1:8765`. Bind is **127.0.0.1 only** — nothing
leaves your machine except the model API calls. Close the window (or Ctrl+C) to
stop it.

**Pasting instead of a file:** the first box on the page takes raw pasted text —
no need to save a `.txt` first. Precedence is **paste → dropped file →
dropdown**, so whatever you just pasted wins. Set a **source title** and it is
used both in the notes header and in the output file name.

### CLI, no UI

```powershell
$py = 'C:\Users\Hitesh\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe'

# transcript -> complete notes
& $py pipeline.py -i ..\..\transcripts\day44.txt -m complete-fresh -t "StatefulSets"

# existing .md -> rebuilt as incremental learning notes
& $py pipeline.py -i ..\Day_43-Helm-Charts-Values-Releases.md -m incremental-improve
```

---

## Modes

| Mode | Input | Output |
|---|---|---|
| `complete-fresh` | transcript | one self-contained narrative document (reference style) |
| `complete-improve` | existing `.md` | same style, rebuilt: keeps facts, fixes structure, adds missing sections |
| `incremental-fresh` | transcript | narrative divided into short sections, recall checks after each |
| `incremental-improve` | existing `.md` | same, rebuilt |

Both styles are defined in `prompts.py` (`HOUSE_STYLE_COMPLETE`,
`HOUSE_STYLE_INCREMENTAL`). **That file is the product.** If output feels thin,
edit the style spec — not the model.

---

## How it works

```
source
  └─ chunk        markdown heading boundaries, else ~14k-char windows w/ overlap
       └─ MAP    deepseek-chat  -> JSON facts per chunk (concepts, commands,
       │                           YAML, demos, gotchas, numbers, analogies…)
       └─ REDUCE deepseek-chat  -> flash compresses facts over ~16k chars
            └─ WRITE deepseek-reasoner + style spec -> final Markdown
                 (retries with a bigger token cap if it comes back empty/truncated)
```

Why not one straight call: your transcripts run 15–25k tokens, and notes are
another 7–8k. Chunking makes **input length irrelevant**, and the fact layer is
**cached**, so changing the writing prompt and re-running costs almost nothing.

Cache lives in `.cache/`, keyed by prompt version + model + content. Delete it
whenever you want a clean run. Bump `EXTRACT_VERSION` (extraction prompts) or
`WRITE_VERSION` (house styles) in `prompts.py` after editing the matching
prompt; each stage's cache invalidates independently, so tweaking the writing
style does not re-pay for extraction.

---

## Where things land

Everything goes to **`_notes-pipeline/output/`** — never next to your sources,
never overwriting anything:

```
output/
├── statefulsets-deep-dive.incremental.md
├── helm-upgrade-and-rollback.complete.md
└── helm-upgrade-and-rollback.complete-2.md     ← collision gets -2, -3…
```

- **Name:** `<slug-of-title>.<style>.md`. Leave the title blank and the source
  file name becomes the slug.
- **No replace button.** You review the file and update your own MD by hand —
  the pipeline only ever creates new files.
- **Library:** the bottom panel of the UI lists every output (lines, KB,
  created) and opens it in the preview with one click.

---

## Models

The UI has **two model fields** (any OpenAI-compatible model id works):

| Field | Default | Job |
|---|---|---|
| **Extraction** | `deepseek-chat` | one call per chunk → JSON facts. Cheap and fast |
| **Writing** | `deepseek-reasoner` | one call → the final notes. Slow, better prose |

`deepseek-reasoner` spends its output budget on reasoning *before* writing the
notes, so a thinking model needs headroom. The write cap defaults to 32,768
tokens (`NOTES_WRITE_MAX_TOKENS`); the log warns if the model still hits it.
If a thinking model ever returns an empty file, raise that cap or switch to
`deepseek-flash` for the write.

The defaults above are the legacy aliases. The 2026 names — `deepseek-flash`
and `deepseek-v4-pro` — are in the UI's model list and priced in
`pricing.json`; pick them if a run returns `HTTP 400` about the model.

CLI equivalents: `--map-model` / `--write-model`, or `NOTES_MAP_MODEL` /
`NOTES_WRITE_MODEL`.

---

## Cost, before and after

Nothing is sent to estimate a run. The UI chunks the source locally and prices
it from token counts:

- **Before you click Run** — estimated total, a low/high range, per-model split
  (extraction vs writing), chunk count, input/output tokens, and whether
  peak rates apply. Changing the source, style or models re-estimates.
- **While it runs** — spend so far from the tokens the API reports; the writing
  leg is labelled *live estimate* until the stream ends.
- **After it finishes** — actual cost from `usage`, with per-model input/output
  tokens and the estimated number for comparison.

Rates live in **`pricing.json`** (USD per 1M tokens, off-peak). Peak hours cost
`peak_multiplier` (2x by default): 01:00–04:00 and 06:00–10:00 UTC, Mon–Fri.
Chinese public holidays are not modelled. Edit the file and restart; no code
change is needed. `usd_inr` only affects the secondary ₹ display.

The Nov 2026 rate card is V4: `deepseek-flash` (cheap) and `deepseek-v4-pro`
(premium). The old `deepseek-chat` / `deepseek-reasoner` names are priced as
Flash aliases; `deepseek-reasoner` is Flash in thinking mode, which is why the
estimate multiplies its output tokens (reasoning is billed as output).

The estimate assumes ~3.6 characters per token and typical fact density; it is
a planning number, not a bill. Cache hits make the real number lower.

---

## Progress & metrics

The run card is a **stage rail**, not a fake percentage:

- **Split → Extract → Compress → Write**, each step marked active / done / skipped
- the chunk being worked on (`3 of 8 · 8,412 chars`), per-chunk time, `cached`,
  `split ×N`, `bullet fallback`
- **ETA during extraction** from the measured chars/second, then elapsed
- **live Markdown** — the writing call is streamed, so notes appear in the
  preview as the model produces them (`event: delta`)
- **thinking phase** — with a reasoning model, a character counter shows that
  it is reasoning before the first visible token arrives
- **Cancel** stops between chunks, or mid-stream; nothing is saved
- **job log** (collapsed, auto-opens on a warning/error) with timestamps

Progress is streamed over SSE (`event: progress` + `event: delta`), so it updates
as each chunk finishes rather than at the end. The final summary adds lines,
chars, chunks, elapsed, tokens, and both model ids.

---

## Why it can't blow up on a long transcript

- **Chunks are hard-capped at 9,000 characters.** The chunker splits on
  markdown headings, then blank-line paragraphs, then raw slices — so even a
  200k-character wall of text with no blank lines becomes ~23 chunks
  (`python pipeline.py --selftest` proves this).
- If an extraction call still returns truncated or broken JSON, the pipeline
  **halves that chunk and retries** (up to 4 levels); if that also fails it
  falls back to a **plain-bullet extraction** prompt, so a parse error can never
  kill the run.
- JSON is repaired before giving up: trailing commas, unbalanced braces,
  smart quotes, and truncated tails are all handled.

## Configuration

| Env var | Default | Notes |
|---|---|---|
| `DEEPSEEK_API_KEY` | — | required for live runs |
| `NOTES_BASE_URL` | `https://api.deepseek.com` | any OpenAI-compatible endpoint |
| `NOTES_MAP_MODEL` | `deepseek-chat` | extraction; cheap + fast |
| `NOTES_WRITE_MODEL` | `deepseek-reasoner` | writing; quality matters |
| `NOTES_WRITE_MAX_TOKENS` | `32768` | output cap for the final notes |
| `NOTES_WRITE_MAX_RETRY_CAP` | `131072` | ceiling if a truncated write is retried |
| `NOTES_COMPRESS_CHARS` | `16000` | facts above this get a flash compress pass first |

To make the key persistent for your user account:

```powershell
[Environment]::SetEnvironmentVariable('DEEPSEEK_API_KEY','sk-...','User')
```

(Restart the terminal afterwards.)

---

## Cost & limits

- A 90-minute transcript is roughly 25k input tokens; extraction is ~8–10 cheap
  calls, writing is one expensive call (plus one cheap flash-compress call when
  the extracted facts are long). Pennies per lecture at DeepSeek prices.
- **Compress-then-write:** facts over ~16k chars get a flash pass that merges
  duplicates and keeps every concrete detail before the reasoning model writes.
- **Output cap:** 32,768 tokens by default (`NOTES_WRITE_MAX_TOKENS`). A thinking
  model spends part of that budget on reasoning. If a write comes back empty or
  truncated, the pipeline retries with a larger cap (up to
  `NOTES_WRITE_MAX_RETRY_CAP`) instead of saving a blank file, and only saves
  when there is real content.
  - Fix if it still truncates: raise the cap, set `NOTES_WRITE_MODEL=deepseek-flash`,
    or run the chapter in two halves.
- Notes longer than ~600 lines are usually a sign the source should be split by
  lecture, not that the model is weak.

---

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `No API key` | set `DEEPSEEK_API_KEY`, or use `--mock` |
| `HTTP 401` | bad key |
| `HTTP 402` | no credit on the account |
| `HTTP 429` | rate limited; the client retries 4× with backoff, then fails |
| `HTTP 400` mentioning the model | the legacy `deepseek-chat` / `deepseek-reasoner` names were retired — use `deepseek-flash` or `deepseek-v4-pro` |
| Cost panel says "estimate failed" | `pricing.json` is not valid JSON; fix it and restart |
| `model did not return JSON` | handled automatically: the chunk is halved and retried, then bullet-fallback. If you still see it, the chunk was tiny — check the log |
| Output truncated / cut mid-table | see the output-cap note above |
| `path outside the notes folder` | the UI only accepts files under this directory tree |
| Port busy | `.\run.cmd -Port 8770` |

---

## Files

```
_notes-pipeline/
├── run.cmd        double-click launcher (bypasses PowerShell script policy)
├── run.ps1        real launcher (mock/live, port)
├── server.py      loopback HTTP server: SSE progress/deltas, estimate, cancel, run, save
├── pipeline.py    chunk → extract → reduce → write; streaming; caching; CLI
├── costs.py       token accounting: estimate before, price the usage after
├── pricing.json   rates (USD / 1M tokens, off-peak) — edit when prices move
├── prompts.py     extraction prompt + the two house-style specs  ← edit this
├── index.html     single-page UI (no build step, no dependencies)
├── output/        every generated note (never overwrites)
└── .cache/        extracted-fact cache (safe to delete)
```
