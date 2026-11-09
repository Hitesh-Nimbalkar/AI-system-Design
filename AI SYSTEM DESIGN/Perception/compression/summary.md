# Summarization as Context Compression — Very Detailed Notes

> **Topic:** Lossy summarization for LLM context management
> **Scope:** What summarization is, why it is used, how to architect it, how to evaluate it, and how to avoid its failure modes.
> **Audience:** AI engineers building persistent, multi-turn agentic systems.
> **Companion files:** Context Compression (lossless techniques), Lossy Summarization theory, Memory Architectures.

---

## 1. What Summarization Is

### 1.1 Definition

> **Summarization is the controlled, intentional reduction of conversation history into a compact representation that preserves semantic meaning, conversational essence, and core intelligence, while discarding peripheral details.**

**Key words:**

| Word | Meaning |
|---|---|
| **Controlled** | It is deliberate, not accidental |
| **Intentional** | It is planned and triggered |
| **Reduction** | The goal is fewer tokens |
| **Compact representation** | A shorter form of the same history |
| **Preserves** | Meaning, essence, intelligence |
| **Discards** | Peripheral details |

### 1.2 What Summarization Is Not

| It is not | Why |
|---|---|
| **Deletion** | Deletion removes content entirely; summarization preserves meaning |
| **Truncation** | Truncation cuts at a boundary; summarization condenses |
| **Compression of syntax** | That is lossless compression; summarization is lossy |
| **Paraphrasing** | Paraphrasing keeps length; summarization reduces it |
| **Keyword extraction** | Keywords lose narrative; summarization keeps the "plot" |

### 1.3 The Core Trade-Off

```text
More tokens  ←──────────────→  Fewer tokens
More detail                    Less detail
More context                   More headroom
Higher cost                    Lower cost
Slower TTFT                    Faster TTFT
```

Summarization moves the system **rightward** on this spectrum, deliberately.

---

## 2. Why Summarization Is Needed

### 2.1 The Fundamental Problem

LLM context windows are **finite**. Conversations, tool calls, and RAG results accumulate **linearly**. Without intervention:

- The window fills.
- The model loses distal context.
- The agent fragments.
- Costs rise.
- Latency increases.

### 2.2 The Four Drivers

| Driver | What summarization does |
|---|---|
| **Cost** | Fewer tokens → lower API spend |
| **Latency** | Smaller input → faster TTFT |
| **Quality** | Less noise → sharper reasoning |
| **Hard wall** | Stays under the token limit |

### 2.3 Why Lossless Is Not Enough

Lossless compression (stripping ANSI, HTML, timestamps, whitespace) removes **structural** noise. But it cannot remove:

- Redundant conversational content.
- Repeated explanations.
- Obsolete decisions.
- Resolved questions.
- Verbatim filler ("hello," "thank you," "got it").

**Summarization handles what lossless cannot:** the **semantic** volume.

### 2.4 The Two-Layer Defense

```text
Layer 1: Lossless  → removes structural noise (facts preserved)
Layer 2: Lossy     → removes semantic volume (meaning preserved)
```

Summarization is **Layer 2**. It runs **after** lossless, never instead of it.

---

## 3. What Summarization Must Preserve

### 3.1 The Three Pillars

| Pillar | What it means | Example |
|---|---|---|
| **Semantic Meaning** | The fundamental message and intent | "User wants a vegetarian hotel in Colombo" |
| **Conversational Essence** | The tone, style, and persona | The agent stays polite and consistent |
| **Core Intelligence** | The knowledge and logic needed | Budget, constraints, decisions |

### 3.2 The Golden Rule

> **Granular information may be discarded, but the fundamental semantic essence must remain immutable.**

**What can be discarded:**

- Verbatim wording.
- Filler phrases.
- Repeated information.
- Peripheral details.
- Redundant syntax.

**What must remain:**

- Decisions.
- Facts.
- Preferences.
- Pending tasks.
- Goal and progress.

### 3.3 The Consequence of Violation

| Failure | Result |
|---|---|
| Meaning lost | The agent answers the wrong question |
| Essence lost | The persona drifts |
| Intelligence lost | The agent cannot execute its mandate |
| Truth lost | The agent contradicts itself or the user |

---

## 4. The Five Heuristics of a High-Quality Summary

A generic summary is **insufficient** for task-oriented agents. The summary must be a **state-tracking** document.

### 4.1 The Five Elements

| # | Element | What it captures | Example |
|---|---|---|---|
| 1 | **Established Decisions** | Documented choices | "Hotel in Colombo booked and paid" |
| 2 | **Established Facts** | Fixed data points | "User is Ajay; flying from Delhi" |
| 3 | **User Preferences** | Nuanced requirements | "Vegetarian; prefers quiet gardens over nightlife" |
| 4 | **Pending Tasks** | What remains | "Flights and local transport unbooked" |
| 5 | **Goal & Progress** | Objective and status | "7-day Sri Lanka trip, 60% complete" |

### 4.2 Why Each Element Matters

#### 4.2.1 Established Decisions

**Prevents:** Re-opening settled choices.
**Why it matters:** Decisions are expensive to reach; re-opening them wastes time and erodes trust.

#### 4.2.2 Established Facts

**Prevents:** Re-asking for known data.
**Why it matters:** Re-asking signals memory failure.

#### 4.2.3 User Preferences

**Prevents:** Ignoring personal requirements.
**Why it matters:** Preferences define the quality of recommendations.

#### 4.2.4 Pending Tasks

**Prevents:** Forgetting what remains.
**Why it matters:** Pending tasks define the next steps.

#### 4.2.5 Goal & Progress

**Prevents:** Losing direction.
**Why it matters:** The goal defines what "done" means.

### 4.3 Generic vs. State-Tracking Summary

| Generic | State-Tracking |
|---|---|
| "The user discussed a trip." | "7-day Sri Lanka trip, 60% complete, hotel booked, flights pending, vegetarian, quiet gardens preferred." |
| Vague | Specific |
| Not actionable | Actionable |
| Requires re-asking | Enables continuation |

### 4.4 The Summary Template

```text
GOAL: [overarching objective]
PROGRESS: [percentage or status]

DECISIONS:
- [decision 1]
- [decision 2]

FACTS:
- [fact 1]
- [fact 2]

PREFERENCES:
- [preference 1]
- [preference 2]

PENDING:
- [task 1]
- [task 2]
```

---

## 5. Architecture — The Three-Phase Pipeline

### 5.1 Phase 1 — Trigger

Compression is invoked by a **threshold**.

| Trigger type | Description | Example |
|---|---|---|
| **Token-based** | Invoke when token count reaches a limit | 1,200 (small), 30,000+ (enterprise) |
| **Turn-based** | Invoke every N turns | Every 10 turns |
| **Hybrid** | Either condition | 1,200 tokens OR 10 turns |

**Design considerations:**

- Trigger **before** the window fills, not after.
- Leave headroom for the summary itself and the next few turns.
- Tune the threshold to the model's context window.

### 5.2 Phase 2 — Segmentation and Exclusion

Before summarizing, **protect** the elements that must never change.

| Protected element | Why |
|---|---|
| **System Instructions** | Core persona — must never be altered |
| **Tool Definitions** | Operational capabilities — must never change |
| **Last N Messages** | Immediate context — must not be disrupted |

**Typical N:** 1 to 4 messages.

**Why exclude the last N:**

- Maintains local coherence.
- Preserves pronoun resolution.
- Keeps the "short-term memory" intact.
- Prevents the summary from disrupting the live thread.

### 5.3 Phase 3 — Summarization and Reconstruction

#### 5.3.1 The Summarization Call

The **distal** (old) history is sent to a **secondary LLM**.

**Why a secondary LLM:**

| Reason | Explanation |
|---|---|
| **Lower cost** | Smaller model, cheaper tokens |
| **Lower latency** | Faster inference |
| **Specialization** | Can be tuned for summarization |
| **Frees the primary model** | The main model is not burdened |

**Typical secondary model size:** 7B–8B parameters.

#### 5.3.2 The Reconstruction Formula

```text
New Context =
    [System Instructions + Tool Definitions]
  + [Summary of Distal Conversation]
  + [Last N Messages]
```

#### 5.3.3 The Pipeline Diagram

```text
BEFORE
┌─────────────────────────────────────────┐
│ [System] [Tools]                        │
│ [Old 1] [Old 2] ... [Old N]             │
│ [Recent 1] [Recent 2] [Recent 3]        │
└─────────────────────┬───────────────────┘
                      │
                      ▼
             Identify distal history
             (exclude System, Tools, Last N)
                      │
                      ▼
             Send to Secondary LLM
                      │
                      ▼
                 Get Summary
                      │
                      ▼
AFTER
┌─────────────────────────────────────────┐
│ [System] [Tools]                        │
│ [Summary of Distal Conversation]        │
│ [Recent 1] [Recent 2] [Recent 3]        │
└─────────────────────────────────────────┘
```

---

## 6. Implementation Patterns

### 6.1 Basic Pattern — Single Summary

```python
def compress(messages, system, tools, last_n=4, threshold=1200):
    if count_tokens(messages) < threshold:
        return messages

    distal = messages[:-last_n]
    recent = messages[-last_n:]

    summary = secondary_llm.summarize(distal)

    return [system] + [tools] + [summary] + recent
```

### 6.2 Recursive Summarization

For very long sessions, summaries themselves can be summarized.

```text
Session start
    │
    ▼
[Summary A] ─── grows ───▶ [Summary A + new content]
    │
    ▼
[Summary B] ─── grows ───▶ [Summary B + new content]
    │
    ▼
[Summary C] (increasingly condensed)
```

**Risk:** Each generation loses fidelity. Use sparingly and evaluate.

### 6.3 Rolling Summary

Keep a **persistent summary** that is updated incrementally.

```text
State:
  summary = "..."

On each turn:
  summary = update_summary(summary, new_turn)
```

**Advantage:** No sudden compression event.
**Risk:** The summary may drift over time.

### 6.4 Hierarchical Summary

Maintain summaries at multiple levels.

```text
Level 1: Per-turn summary
Level 2: Per-10-turn summary
Level 3: Whole-session summary
```

**Advantage:** Granularity when needed.
**Risk:** Complexity and storage overhead.

### 6.5 Pattern Comparison

| Pattern | Best for | Risk |
|---|---|---|
| **Single summary** | Moderate sessions | Sudden compression |
| **Recursive** | Very long sessions | Fidelity loss |
| **Rolling** | Continuous agents | Drift |
| **Hierarchical** | Complex workflows | Complexity |

---

## 7. Prompt Design for Summarization

### 7.1 The Summarization Prompt

The prompt must instruct the summarizer to produce a **state-tracking** summary, not a literary one.

```text
You are a summarization engine for a task-oriented AI agent.
Condense the following conversation into a state-tracking summary.

Include ONLY:
1. Established decisions (what was chosen and finalized)
2. Established facts (fixed data about the user or task)
3. User preferences (nuanced requirements)
4. Pending tasks (what remains to be done)
5. Goal and progress (objective and current status)

Do NOT include:
- Greetings or filler
- Repeated information
- Verbatim dialogue
- Speculation or opinions

Output format:
GOAL: ...
PROGRESS: ...
DECISIONS: ...
FACTS: ...
PREFERENCES: ...
PENDING: ...

Conversation:
{history}
```

### 7.2 Prompt Design Principles

| Principle | Why |
|---|---|
| **Specify the output format** | Ensures consistency |
| **List what to include** | Prevents omission of key elements |
| **List what to exclude** | Prevents noise |
| **Use a structured template** | Makes the summary machine-readable |
| **Keep instructions explicit** | Reduces variability |

### 7.3 What to Avoid in the Prompt

| Anti-pattern | Why |
|---|---|
| "Summarize this" | Too vague; produces literary summaries |
| "Be brief" | May drop critical facts |
| "Capture the gist" | Ambiguous; may lose decisions |
| No format | Inconsistent output |

---

## 8. Evaluation of Summaries

### 8.1 Why Evaluation Is Necessary

Summarization is **lossy**. Without evaluation, you cannot know:

- Whether critical facts were preserved.
- Whether the summary is actionable.
- Whether the agent can continue the task.

### 8.2 Evaluation Dimensions

| Dimension | Question |
|---|---|
| **Factual fidelity** | Are all established facts present? |
| **Decision fidelity** | Are all decisions present? |
| **Preference fidelity** | Are all preferences present? |
| **Task fidelity** | Are pending tasks and progress present? |
| **Conciseness** | Is the summary significantly shorter? |
| **Actionability** | Can the agent continue without re-asking? |

### 8.3 The Fidelity Test

**Method:**

1. Take a conversation with known facts, decisions, preferences, and pending tasks.
2. Summarize it.
3. Check whether each item is present in the summary.

**Scoring:**

```text
Fidelity = (items preserved) / (items in original)
```

### 8.4 The Continuation Test

**Method:**

1. Summarize the conversation.
2. Ask the agent a follow-up question that depends on the summary.
3. Check whether the agent answers correctly without re-asking.

**Example:**

- Original: "User is vegetarian, budget ₹2 lakh, hotel booked."
- Follow-up: "What's next?"
- Correct response: "Flights and local transport."
- Incorrect response: "What's your budget?" (re-asking)

### 8.5 The Compression Ratio

```text
Ratio = post_compression_tokens / pre_compression_tokens
```

**Benchmark from the Tara experiment:**

| Metric | Value |
|---|---|
| Pre | 1,272 |
| Post | 736 |
| Ratio | 0.579 |
| Reduction | 42.1% |

### 8.6 Evaluation Checklist

- [ ] All decisions preserved
- [ ] All facts preserved
- [ ] All preferences preserved
- [ ] Pending tasks listed
- [ ] Goal and progress stated
- [ ] Compression ratio acceptable
- [ ] Agent can continue without re-asking
- [ ] Tone and persona consistent

---

## 9. Failure Modes

### 9.1 Failure Mode 1 — Fact Loss

| Aspect | Detail |
|---|---|
| **Symptom** | Agent re-asks for known information |
| **Cause** | Summarizer omitted a fact |
| **Fix** | Strengthen the prompt; add a fidelity check |

### 9.2 Failure Mode 2 — Decision Reversal

| Aspect | Detail |
|---|---|
| **Symptom** | Agent re-opens a settled decision |
| **Cause** | Decision not captured or captured ambiguously |
| **Fix** | Explicit "decisions" section in the prompt |

### 9.3 Failure Mode 3 — Preference Drift

| Aspect | Detail |
|---|---|
| **Symptom** | Agent suggests something the user rejected |
| **Cause** | Preference omitted or softened |
| **Fix** | Explicit "preferences" section; preserve exact constraints |

### 9.4 Failure Mode 4 — Goal Drift

| Aspect | Detail |
|---|---|
| **Symptom** | Agent loses sight of the objective |
| **Cause** | Goal not stated in the summary |
| **Fix** | Require "GOAL" at the top of the summary |

### 9.5 Failure Mode 5 — Persona Drift

| Aspect | Detail |
|---|---|
| **Symptom** | Tone or style changes after compression |
| **Cause** | Conversational essence not preserved |
| **Fix** | Include tone/style in the summary prompt; keep system instructions protected |

### 9.6 Failure Mode 6 — Summary Hallucination

| Aspect | Detail |
|---|---|
| **Symptom** | Summary contains facts not in the conversation |
| **Cause** | Summarizer invented details |
| **Fix** | Use a constrained prompt; evaluate with fidelity tests |

### 9.7 Failure Mode 7 — Recursive Degradation

| Aspect | Detail |
|---|---|
| **Symptom** | Quality drops after repeated summarization |
| **Cause** | Each generation loses fidelity |
| **Fix** | Limit recursion depth; use hierarchical summaries |

### 9.8 Failure Mode Summary

| # | Failure | Cause | Fix |
|---|---|---|---|
| 1 | Fact loss | Omission | Fidelity check |
| 2 | Decision reversal | Ambiguity | Decisions section |
| 3 | Preference drift | Softening | Exact constraints |
| 4 | Goal drift | Missing goal | GOAL at top |
| 5 | Persona drift | Essence lost | Tone preservation |
| 6 | Hallucination | Invention | Constrained prompt |
| 7 | Recursive degradation | Repeated loss | Depth limit |

---

## 10. Summarization vs. Other Techniques

### 10.1 The Full Comparison

| Technique | What it removes | What it preserves | When to use |
|---|---|---|---|
| **Lossless compression** | Structural noise | All facts | Always first |
| **Deletion / sliding window** | Entire segments | Nothing from removed content | Rarely; only for non-critical history |
| **Summarization** | Semantic volume | Meaning, essence, intelligence | When lossless is insufficient |
| **Retrieval (RAG)** | Everything except top-k | Relevant chunks | When history is searchable |
| **Programmatic tool calling** | Intermediate results | Final result | Multi-step tool workflows |

### 10.2 Summarization vs. RAG

| Aspect | Summarization | RAG |
|---|---|---|
| **What it does** | Condenses history into one summary | Retrieves relevant chunks on demand |
| **When it runs** | At a threshold | Every query |
| **What it preserves** | The "plot" | Relevant facts |
| **What it loses** | Peripheral details | Everything not retrieved |
| **Best for** | Long conversations | Large knowledge bases |
| **Risk** | Lossy | Irrelevant retrieval |

### 10.3 Summarization vs. Deletion

| Aspect | Summarization | Deletion |
|---|---|---|
| **Cost** | LLM call | Free |
| **Speed** | Slower | Instant |
| **Risk** | Controlled loss | Catastrophic loss |
| **Preserves plot** | ✅ Yes | ❌ No |
| **Recommended** | ✅ Yes | ❌ No (for stateful agents) |

### 10.4 When Summarization Is the Right Choice

- Long multi-turn conversations.
- Task-oriented agents with state.
- Workflows that span more than one context window.
- Sessions that must persist across hours, days, or weeks.
- When decisions, facts, and preferences must survive compression.

### 10.5 When Summarization Is Not the Right Choice

- The conversation is short.
- Lossless compression is sufficient.
- The user's verbatim wording matters (legal, medical).
- The summary cannot be evaluated.
- A RAG system already handles history retrieval.

---

## 11. Best Practices

### 11.1 Architecture

1. **Run lossless first.** Strip noise before summarizing.
2. **Protect system instructions and tools.** Never summarize them.
3. **Exclude the last N messages.** Preserve immediate context.
4. **Use a secondary, lightweight LLM.** Do not burden the primary model.
5. **Trigger before the window fills.** Leave headroom.

### 11.2 Prompt Design

6. **Specify a structured output format.**
7. **List what to include and exclude.**
8. **Require the five heuristic elements.**
9. **Keep the prompt explicit and deterministic.**

### 11.3 Evaluation

10. **Measure fidelity.** Check that facts, decisions, preferences, and tasks are preserved.
11. **Run continuation tests.** Verify the agent can proceed without re-asking.
12. **Track compression ratio.** Ensure meaningful savings.

### 11.4 Operations

13. **Log summaries.** Enable debugging and auditing.
14. **Version the summarization prompt.** Changes affect quality.
15. **Monitor failure modes.** Watch for re-asking, drift, and hallucination.

### 11.5 Hybrid Strategy

16. **Combine lossless and lossy.** They are partners, not rivals.
17. **Place static facts in System Instructions.** Avoid RAG for identity.
18. **Summarize dynamic history.** Keep the context lean.

---

## 12. Worked Example — The Tara Experiment

### 12.1 Setup

| Element | Value |
|---|---|
| **Model** | Gemma-based, 31B class |
| **Persona** | Tara, travel planner |
| **Task** | 7-day Japan trip |
| **Budget** | ₹2 lakh |
| **Trigger** | 1,200 tokens |

### 12.2 Metrics

| Metric | Value |
|---|---|
| **Pre-compression** | 1,272 tokens |
| **Post-compression** | 736 tokens |
| **Reduction** | 42.1% |

### 12.3 What Was Preserved

| Preserved element | Value |
|---|---|
| **Diet** | Vegetarian |
| **Budget** | ₹2 lakh |
| **Preference** | Temples/nature over nightlife |

### 12.4 What Was Gained

- **Lower latency.** The leaner prompt processed faster.
- **Same thread.** The agent did not lose the plot.

### 12.5 The Lesson

> A well-designed summary can cut **42%** of the context while preserving **100%** of the task-critical facts.

---

## 13. Key Takeaways

1. **Summarization is controlled, intentional, lossy compression.**
2. **It preserves meaning, essence, and intelligence — not verbatim wording.**
3. **It is the second line of defense, after lossless compression.**
4. **It addresses semantic volume, which lossless cannot remove.**
5. **The Golden Rule:** semantic essence must remain immutable.
6. **High-quality summaries are state-tracking, not literary.**
7. **The five heuristics:** decisions, facts, preferences, pending tasks, goal & progress.
8. **The pipeline is three-phase:** trigger, segment/exclude, reconstruct.
9. **Protect system instructions, tools, and the last N messages.**
10. **Use a secondary, lightweight LLM for summarization.**
11. **The reconstruction formula is:** `[System] + [Summary] + [Last N]`.
12. **Prompt design must be explicit and structured.**
13. **Evaluation requires fidelity and continuation tests.**
14. **Seven failure modes exist:** fact loss, decision reversal, preference drift, goal drift, persona drift, hallucination, recursive degradation.
15. **Summarization complements RAG, lossless, and programmatic calling.**
16. **The Tara experiment showed 42.1% reduction with full fidelity.**
17. **Best practice is a hybrid framework:** lossless first, lossy second.
18. **Summaries must be logged, versioned, and monitored.**
19. **Summarization is essential for persistent, long-running agents.**
20. **A generic summary is insufficient; a state-tracking summary is required.**

---

## 14. Glossary

| Term | Definition |
|---|---|
| **Summarization** | Controlled lossy compression of conversation history into a compact state-tracking representation. |
| **Lossy compression** | Reducing tokens by discarding peripheral details while preserving meaning. |
| **Semantic meaning** | The fundamental message and intent. |
| **Conversational essence** | Tone, style, and persona of the interaction. |
| **Core intelligence** | The knowledge and logic required to execute the mandate. |
| **Golden Rule** | Semantic essence must remain immutable even as details are discarded. |
| **State-tracking summary** | A summary that captures decisions, facts, preferences, pending tasks, and goal/progress. |
| **Trigger threshold** | The token count or turn count that invokes summarization. |
| **Segmentation** | Isolating protected elements before summarizing. |
| **Exclusion** | Protecting system instructions, tools, and the last N messages. |
| **Secondary LLM** | A smaller, lightweight model used for summarization. |
| **Reconstruction formula** | `[System/Tools] + [Summary] + [Last N Messages]`. |
| **Fidelity** | The degree to which a summary preserves original facts. |
| **Compression ratio** | Post-compression tokens divided by pre-compression tokens. |
| **Continuation test** | Checking whether the agent can proceed without re-asking. |
| **Recursive summarization** | Summarizing summaries for very long sessions. |
| **Rolling summary** | A persistent summary updated incrementally. |
| **Hierarchical summary** | Summaries at multiple levels of granularity. |
| **Fact loss** | A failure mode where a known fact is missing from the summary. |
| **Decision reversal** | A failure mode where a settled decision is re-opened. |
| **Preference drift** | A failure mode where user preferences are lost. |
| **Goal drift** | A failure mode where the objective is lost. |
| **Persona drift** | A failure mode where tone or style changes. |
| **Summary hallucination** | A failure mode where the summary invents facts. |
| **Recursive degradation** | A failure mode where repeated summarization loses fidelity. |

---

## 15. Self-Test Questions

### Definition
1. What is summarization in the context of LLM context management?
2. What are the three things summarization must preserve?
3. What is the Golden Rule of summarization?
4. How does summarization differ from deletion?

### Why Summarization
5. Why is lossless compression insufficient on its own?
6. What are the four drivers that make summarization necessary?
7. Why is summarization described as the "second line of defense"?

### Heuristics
8. What are the five elements of a high-quality summary?
9. Give an example of an established decision.
10. Give an example of an established fact.
11. Give an example of a user preference.
12. Give an example of a pending task.
13. Give an example of goal and progress.
14. Why is a generic summary insufficient?

### Architecture
15. What are the three phases of the summarization pipeline?
16. What are the two types of triggers?
17. What is protected from summarization?
18. Why are the last N messages excluded?
19. Why is a secondary LLM used?
20. What is the reconstruction formula?

### Implementation
21. What is the basic single-summary pattern?
22. What is recursive summarization, and what is its risk?
23. What is a rolling summary?
24. What is a hierarchical summary?

### Prompt Design
25. What should a summarization prompt include?
26. What should a summarization prompt exclude?
27. Why is a structured output format important?

### Evaluation
28. What are the evaluation dimensions for a summary?
29. What is the fidelity test?
30. What is the continuation test?
31. What is the compression ratio?

### Failure Modes
32. What are the seven failure modes of summarization?
33. What causes fact loss, and how is it fixed?
34. What causes recursive degradation, and how is it fixed?

### Comparison
35. How does summarization compare with RAG?
36. When is summarization not the right choice?

### Case Study
37. What were the metrics of the Tara experiment?
38. What was preserved despite compression?

### Answer Key
1. Controlled, intentional, lossy compression of conversation history into a compact state-tracking representation.
2. Semantic meaning, conversational essence, core intelligence.
3. Granular information may be discarded, but semantic essence must remain immutable.
4. Deletion removes segments entirely; summarization condenses while preserving meaning.
5. Lossless removes structural noise but cannot remove semantic volume like redundant dialogue, obsolete decisions, or filler.
6. Cost, latency, quality, and the hard wall.
7. Because it runs after lossless, handling what lossless cannot.
8. Established decisions, established facts, user preferences, pending tasks, goal and progress.
9. "Hotel in Colombo booked and paid."
10. "User is Ajay; flying from Delhi."
11. "Vegetarian; prefers quiet gardens over nightlife."
12. "Flights and local transport unbooked."
13. "7-day Sri Lanka trip, 60% complete."
14. Because it lacks state-tracking and requires re-asking.
15. Trigger, segmentation/exclusion, reconstruction.
16. Token-based and turn-based.
17. System instructions, tool definitions, the last N messages.
18. To maintain local coherence and short-term memory.
19. To manage computational overhead and latency; the primary model is not burdened.
20. `[System/Tools] + [Summary] + [Last N Messages]`.
21. Trigger on threshold, split distal vs. recent, summarize distal, reconstruct.
22. Summarizing summaries for very long sessions; risk of fidelity loss.
23. A persistent summary updated incrementally; risk of drift.
24. Summaries at multiple levels; risk of complexity.
25. Include decisions, facts, preferences, pending tasks, goal and progress.
26. Exclude greetings, filler, repeated information, verbatim dialogue, speculation.
27. It ensures consistency and makes the summary machine-readable.
28. Factual fidelity, decision fidelity, preference fidelity, task fidelity, conciseness, actionability.
29. Checking whether each known fact is present in the summary.
30. Asking a follow-up question that depends on the summary and checking whether the agent answers without re-asking.
31. Post-compression tokens divided by pre-compression tokens.
32. Fact loss, decision reversal, preference drift, goal drift, persona drift, hallucination, recursive degradation.
33. Omission; fixed by fidelity checks and a stronger prompt.
34. Repeated summarization loses fidelity; fixed by limiting recursion depth and using hierarchical summaries.
35. Summarization condenses history into one summary; RAG retrieves relevant chunks on demand. They complement each other.
36. When the conversation is short, lossless is sufficient, verbatim wording matters, or a RAG system already handles history.
37. Pre 1,272 tokens, post 736 tokens, 42.1% reduction, full fidelity to diet, budget, and preference.
38. Vegetarian diet, ₹2 lakh budget, preference for temples/nature over nightlife.

---

## 16. Mental Model Summary

```text
WHAT IT IS
  Controlled, intentional, lossy compression of history.
  Preserves meaning, essence, intelligence.
  Discards peripheral details.

WHY IT EXISTS
  Context windows are finite.
  Lossless removes noise, not volume.
  Summarization handles semantic volume.

WHAT IT MUST PRESERVE
  Semantic meaning
  Conversational essence
  Core intelligence
  Golden Rule: essence is immutable.

THE FIVE HEURISTICS
  Decisions
  Facts
  Preferences
  Pending tasks
  Goal & progress

THE PIPELINE
  Phase 1: Trigger (token or turn)
  Phase 2: Segment/exclude (system, tools, last N)
  Phase 3: Summarize + reconstruct
  Formula: [System] + [Summary] + [Last N]

THE SECONDARY LLM
  Small, fast, specialized.
  Frees the primary model.

PROMPT DESIGN
  Structured output.
  Explicit include/exclude lists.
  The five elements required.

EVALUATION
  Fidelity test.
  Continuation test.
  Compression ratio.

FAILURE MODES
  Fact loss, decision reversal, preference drift,
  goal drift, persona drift, hallucination,
  recursive degradation.

THE HYBRID FRAMEWORK
  Lossless first.
  Lossy second.
  Together: intelligent and efficient.

THE LESSON
  A generic summary is insufficient.
  A state-tracking summary is required.
  Summarization is essential for persistent agents.
```

---

*End of very detailed notes on summarization.*