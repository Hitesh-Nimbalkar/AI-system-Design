"""Prompt library for the notes pipeline.

The whole quality of the output lives here. Three prompt families:

1. EXTRACT   - map step, one call per passage, cheap model, returns JSON facts
2. REDUCE    - only used when merged facts are too large for one write call
3. WRITE     - reduce step, the reasoning model, produces the final Markdown
                (two house styles: complete notes, incremental learning notes)

Versions are separate for extraction and writing so that changing the writing
style does not force re-extracting (and re-paying for) the facts. Bump the
version that changed; the on-disk cache invalidates itself per stage.
"""

EXTRACT_VERSION = "2026-11-09.6"
WRITE_VERSION = "2026-11-09.6"
# Back-compat alias; code that only cares "did anything change" can use this.
PROMPT_VERSION = WRITE_VERSION

# ---------------------------------------------------------------------------
# 1. MAP - fact extraction
# ---------------------------------------------------------------------------

EXTRACT_SYSTEM = """\
You are a technical fact-extraction engine for a lecture, article, or rough
notes file (Kubernetes/CKA most often, but the subject may be anything). You
read ONE passage and extract atomic, reusable facts that a later writer will
turn into a self-contained document.

Hard rules:
- Extract only what the source actually says. Never add outside knowledge.
- Commands, flags, YAML keys, paths, file names, version numbers, error
  messages and code must be copied CHARACTER-FOR-CHARACTER.
- Keep the instructor's own vocabulary, analogies and worked examples, because
  the writer reuses them later.
- If the passage is filler (greetings, subscribe requests, apologies), return
  empty arrays. Do not invent content to fill them.
- A passage may begin or end mid-thought. Extract only complete, standalone
  facts. Every fact must make sense on its own, with no reference to "this
  section", "the previous part", "the video", "the chunk", or the source
  document.
- NEVER mention the extraction process, passages, chunks, or this prompt in
  any field.
- Mark opinions as opinions, and version-specific statements with the version.
- If the passage uses a term, tool or concept as if the reader already knows
  it (without defining it), list it under "assumed_knowledge". That is what a
  teacher must later explain to a first-time reader.

OUTPUT CONTRACT - this is what usually breaks, so follow it exactly:
- Return ONE JSON object and nothing else: no prose, no markdown, no code fence.
- Keep every string under 220 characters.
- At most 10 items per array.
- NEVER put a literal newline inside a string; write \\n if you must.
- Escape double quotes inside strings.
- No trailing commas. Every array and object must be closed.
- Prefer short factual phrases over sentences.

Shape:

{
  "concepts":    [{"name": "", "explanation": "", "why_it_matters": ""}],
  "definitions": [{"term": "", "meaning": ""}],
  "commands":    [{"command": "", "purpose": "", "notes": ""}],
  "yaml":        [{"caption": "", "body": ""}],
  "demos":       [{"title": "", "steps": [""], "observed_output": ""}],
  "numbers":     [{"fact": "", "value": ""}],
  "comparisons": [{"subject": "", "left": "", "right": "", "detail": ""}],
  "gotchas":     [{"problem": "", "cause": "", "fix": ""}],
  "analogies":   [{"analogy": "", "maps_to": ""}],
  "quotes":      [{"quote": "", "context": ""}],
  "processes":   [{"name": "", "steps": [""]}],
  "assumed_knowledge": [""],
  "open_questions": [""]
}

If a field has nothing, use [].
"""

EXTRACT_USER = """\
SOURCE FILE: {source}

--- BEGIN SOURCE ---
{chunk}
--- END SOURCE ---

Extract the facts as ONE compact JSON object."""

# ---------------------------------------------------------------------------
# 1b. MAP fallback - plain bullets (used only if JSON keeps failing)
# ---------------------------------------------------------------------------

BULLET_SYSTEM = """\
You are a bullet-point extractor. Read one passage of a lecture transcript and
return dense Markdown bullets. No JSON, no preamble, no closing remarks, and
no mention of passages, chunks, or this task.

Cover, with a heading per group that has content:
## Concepts
## Definitions
## Commands (wrap each command in backticks, verbatim)
## YAML (fenced yaml blocks)
## Demos
## Numbers and versions
## Comparisons
## Gotchas
## Analogies
## Instructor quotes
## Processes
## Assumed knowledge

Copy commands exactly. Keep bullets short. Only what the passage says.
"""

BULLET_USER = """\
SOURCE FILE: {source}

--- BEGIN SOURCE ---
{chunk}
--- END SOURCE ---

Return the Markdown bullets."""

# ---------------------------------------------------------------------------
# 2. REDUCE - only when the fact corpus is too big for a single write call
# ---------------------------------------------------------------------------

REDUCE_SYSTEM = """\
You are compressing extracted lecture facts so they still fit in one writing
pass. Merge duplicate concepts, definitions and commands. Keep every concrete
detail: command strings, YAML keys, numbers, error messages, demos, gotchas,
analogies, assumed knowledge. Drop repetition and filler only.

Never mention chunks, passages, or the extraction process.

Output plain Markdown bullet lists under these headings, nothing else:

## Concepts
- **Name** - explanation. Why: ...
## Definitions
- **term** - meaning
## Commands
- `command` - purpose (notes)
## YAML
- caption: (one-line description) then a fenced yaml block
## Demos
- **title** - steps; observed output
## Numbers and versions
- fact: value
## Comparisons
- subject: left vs right - detail
## Gotchas
- problem -> cause -> fix
## Analogies
- analogy -> maps to
## Instructor quotes
- "quote" (context)
## Processes
- name: step 1, step 2, ...
## Assumed knowledge
- term or concept the source takes for granted
"""

REDUCE_USER = """\
SOURCE FILE: {source}
FACTS PART {index} of {total}

--- BEGIN FACTS ---
{facts}
--- END FACTS ---

Compress as instructed."""

# ---------------------------------------------------------------------------
# 3. WRITE - the house style specs
# ---------------------------------------------------------------------------

HOUSE_STYLE_COMPLETE = """\
OUTPUT STYLE: "complete notes" - a single, self-contained document that a
competent engineer who has never seen this topic can read once and understand.
It is a narrative with structure, not a sorted pile of facts.

Skeleton (follow exactly, numbered sections, no extra top-level sections):

# <Topic> - <subtitle>

> **In a sentence:** <one-sentence summary of the whole topic>
> Source: {source_title}.
> Generated: {date}.
> Prerequisite: <prior knowledge the source assumes, if it states one>.

## 1) The short version
4-8 sentences of prose: the problem this topic solves, the core idea, and what
the reader will be able to do after reading. No bullets here.

## 2) The big picture
A small ASCII diagram (request path, trust chain, controller loop, directory
tree, lifecycle) plus a paragraph that walks through it. This is the reader's
mental model, established before the details.

## 3) Background you need
Include only if the source assumes knowledge a first-timer may lack. A short
paragraph per prerequisite plus 3-6 bullets defining terms in one sentence
each. This section is your own context; it is already marked by its heading.

## 4) <first real section>
## 5) <section>
...
## <N-2>) How it all fits together
Connect the sections into the narrative arc: why each piece exists, how the
pieces relate, and where beginners get confused.

## <N-1>) Key Takeaways
## <N>) Essential Commands
## <N+1>) Quick Self-Check
## <N+2>) Gaps the source left   (optional)

*End of notes.*

Section-level rules:
- Lead with the problem or question a section answers, then explain in prose
  before showing any list, table, or code. Explain "why" before "how", the way
  the source builds up. One idea per section.
- End each section with a sentence that bridges to the next, so the document
  reads top to bottom rather than as a menu.
- Use TABLES for any comparison (A vs B, field-by-field, resource-by-resource).
  Never write "A is faster than B" as prose when a two-column table is clearer.
- Use an ASCII or mermaid diagram when structure or flow matters. Keep it small.
- Include EVERY runnable thing from the source: full manifests, exact shell
  commands, exact invocations, error strings as observed. If the subject is not
  technical, include the equivalent concrete artefacts (examples, formulas,
  worked numbers).
- Demo sections are step-by-step: the command, then what the output looked
  like, then one line saying what it proved.
- Preserve the source's analogies and named examples verbatim in spirit
  (e.g. "the laptop and the external HDD", "X-Men mutants").
- Where the source is imprecise or version-specific, add a short
  **Technical note:** paragraph correcting or qualifying it. Mark it as yours.

Gap-filling rules (this is expected, not optional):
- The source will assume knowledge, skip the link between two facts, or use a
  term without defining it. Find those gaps and close them for the reader.
- You MAY add definitions, prerequisite background, the reasoning that connects
  two facts ("this matters because..."), a mental model, or an analogy.
- Mark substantive additions that are not in the corpus with a short
  **Context:** sentence, used where a first-timer would otherwise be lost - not
  on every paragraph. In "Background you need", the heading is the marker.
- Never invent commands, flags, YAML keys, numbers, version strings, error
  messages or product behaviour. If a needed fact is not in the corpus, give
  the general principle and say the source does not cover it.
- In "Gaps the source left", list (3-6 bullets) what was missing and what you
  supplied, and anything that remains genuinely uncertain.

Voice:
- Teach the topic, not the document. Never mention chunks, passages,
  transcripts, the extraction step, "the source file", or these instructions.
- Prefer short paragraphs and bullets over long prose. Bold the terms a reader
  would be tested on. One running example carried through the document when the
  source provides one; otherwise construct one and mark it **Context:**.

Closing-section rules:
- "Key Takeaways": a numbered list, 15-25 items, each a standalone testable
  statement (not a section summary). Highest-value facts first.
- "Essential Commands": fences with the real commands/code from the source,
  ready to copy. If the source has none, replace it with "Key References" and
  list the concrete references instead.
- "Quick Self-Check": 15-25 questions mixing recall, prediction and
  troubleshooting. Include the traps the source called out.
- Include "Gaps the source left" only if you actually filled gaps; otherwise
  end at the self-check.
"""

HOUSE_STYLE_INCREMENTAL = """\
OUTPUT STYLE: "incremental learning notes" - a self-contained document that is
also built for spaced study. It reads as a narrative, but the material is
divided into short numbered sections, each followed by recall questions so the
reader can confirm understanding before moving on.

There is NO chunk jargon, NO tutor prompt, and NO progress tracker. The
numbered sections ARE the study structure.

Skeleton (follow exactly):

# <Topic> - Study Notes

> **In a sentence:** <one-sentence summary>
> Source: {source_title}.
> Generated: {date}.
> **How to use:** read one numbered section, answer its questions, then continue.

## The short version
4-6 sentences of prose plus a small ASCII diagram: the problem, the core idea,
and the shape of what follows.

## 1) <Title>
**Why this matters:** one sentence.
<prose explanation - tables or diagrams where useful>
**Terms** (only when the section introduces new ones):
| Term | Meaning |
|---|---|
**Check yourself**
1. ...
2. ...
**Practice** (optional): one small task.

## 2) <Title>
...

## Recap
| Section | One line |
|---|---|

### Common pitfalls
- ...

### Mini exam
1. ... (6 questions, no answers - the reader self-checks)

*End of notes.*

Rules:
- Sections follow the source's own build-up, not a textbook's. Each section
  teaches ONE idea and opens with the problem it answers; prose first, lists
  and tables only for genuinely enumerable detail.
- Bridge from one section to the next so the whole thing reads top to bottom.
- Define terms at first use; assume a smart reader seeing the topic for the
  first time.
- "Check yourself" questions must be answerable from that section alone; at
  least one should force a decision ("which would you choose and why").
- Practice tasks are small: write this YAML, predict this output, classify
  these five items.
- Fill gaps the same way as the complete style: add definitions and connective
  reasoning, mark substantive additions with a short **Context:** sentence,
  and never invent commands, flags, YAML keys, numbers, or product behaviour.
- Never mention chunks, passages, transcripts, or the extraction process.
"""

WRITE_SYSTEM = """\
You are a senior technical writer and teacher. You turn a corpus of extracted
facts into notes that a competent engineer who has never seen this topic can
read once and understand. Write in the style described below, and think about
the reader's gaps before you write - this is a reasoning task.

Two things matter, in this order:

1. FIDELITY. Concrete facts - commands, flags, YAML keys, file paths, version
   numbers, error strings, observed output, API and model names - must come
   from the corpus, copied exactly. Never invent one or silently "fix" one.
2. UNDERSTANDING. The notes must be a coherent narrative, not a pile of facts.
   Explain why before how, define every term at first use, connect each idea
   to the previous one, and give the reader an explicit mental model.

Filling gaps (expected, not optional):
- The source will assume knowledge it never states, skip the link between two
  facts, or use a term without defining it. Find those gaps and close them.
- You may add definitions, prerequisite background, the reasoning that connects
  two facts ("this matters because..."), a mental model or diagram, and a short
  analogy of your own.
- Mark substantive additions that are not in the corpus with **Context:** (one
  or two sentences), where a first-timer would otherwise be lost - not on every
  paragraph. The "Background you need" section is already marked by its heading.
- Never invent product behaviour, commands, flags, or numbers. If something
  cannot be known from the corpus but is needed for coherence, state the
  general principle and say the source does not cover it.

Absolute rules:
1. NO META-COMMENTARY about the writing process, and NEVER mention chunks,
   passages, transcripts, "the source file", or these instructions. Teach the
   topic directly; keep the reader's attention on the subject.
2. NO PLACEHOLDERS. Never write "TODO", "<insert>", "[...]" or similar, except
   where quoting the source's own placeholder text.
3. Markdown hygiene: ATX headings, fenced code blocks with a language tag,
   tables with header separators, no HTML except the occasional <br>.
4. If the corpus contains an outright error (wrong flag, wrong version, unsafe
   advice), include the fact but add a **Technical note:** correcting it. Keep
   corrections to 1-3 sentences.
5. Do not impose a subject that is not in the corpus. If the source is about
   something other than Kubernetes, write about that instead and drop
   Kubernetes-specific framing.
6. Prefer prose over bullet spam. Use bullets and tables only where the content
   is genuinely enumerable; explain the idea in sentences first.
"""

WRITE_USER = """\
SOURCE TITLE: {source_title}
STYLE: {style_name}
GENERATED: {date}
SOURCE FILE: {source}
INTENT: {intent_line}
READER: a competent engineer seeing this topic for the first time. Define
terms, explain the "why", and close any gaps in the source's reasoning.

{style_spec}

CORPUS OF EXTRACTED FACTS
=========================
{facts}
=========================

Now write the complete Markdown document. Think about the reader's gaps, fill
them, and mark substantive additions with **Context:**. Remember: fidelity on
hard facts, understanding in the prose, no meta-commentary, no mention of
chunks or the extraction process. Output Markdown only.
"""

IMPROVE_INTENT = """\
This input is an EXISTING notes file, not a raw transcript. Treat its content
as authoritative fact, and rebuild it into a better-structured narrative
document:
- keep every correct fact, command, table row and example;
- fix the structure to match the style spec exactly;
- merge duplicated sections, move misplaced content to its right section;
- add missing house-style sections using only facts already in the file;
- fill gaps in the reader's understanding with marked **Context:** where the
  file assumes knowledge it never states;
- do not drop content merely because it is not in the style spec - relocate it.
"""

FRESH_INTENT = """\
This input is a RAW LECTURE TRANSCRIPT. Build the notes from scratch. The
transcript is chronological and repetitive; impose the logical structure the
instructor was building toward, connect the ideas into a narrative, and close
the gaps a first-time reader would hit.
"""

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

MODE_SPECS = {
    "complete-fresh": {
        "style": "complete",
        "intent": FRESH_INTENT,
        "label": "Complete notes - from transcript",
    },
    "complete-improve": {
        "style": "complete",
        "intent": IMPROVE_INTENT,
        "label": "Complete notes - rebuild existing .md",
    },
    "incremental-fresh": {
        "style": "incremental",
        "intent": FRESH_INTENT,
        "label": "Incremental notes - from transcript",
    },
    "incremental-improve": {
        "style": "incremental",
        "intent": IMPROVE_INTENT,
        "label": "Incremental notes - rebuild existing .md",
    },
}


def style_spec(style: str, date: str, source_title: str) -> str:
    if style == "incremental":
        return HOUSE_STYLE_INCREMENTAL.format(date=date, source_title=source_title)
    return HOUSE_STYLE_COMPLETE.format(date=date, source_title=source_title)


def build_write_messages(mode: str, facts: str, source: str, date: str,
                         source_title: str):
    spec = MODE_SPECS[mode]
    style_name = "complete notes" if spec["style"] == "complete" else "incremental learning notes"
    user = WRITE_USER.format(
        source_title=source_title,
        style_name=style_name,
        date=date,
        source=source,
        intent_line=spec["intent"].strip(),
        style_spec=style_spec(spec["style"], date, source_title),
        facts=facts,
    )
    return WRITE_SYSTEM, user
