# When to Use Which Tool Calling Technique: The Final Guide

## 1. The Big Picture: Where Your Context Budget Goes

Every tool-using AI system spends its context window on five things:

| # | Cost Source | What It Is | Grows With |
|---|---|---|---|
| 1 | **Tool Definitions** | Schemas describing available tools | Number of tools |
| 2 | **Tool Calls** | The model's requests (function name + arguments) | Number of steps |
| 3 | **Tool Results (per call)** | Output returned by each tool | Verbosity of each tool |
| 4 | **Tool Results (across workflow)** | Accumulated intermediate results | Number of dependent steps |
| 5 | **Conversation History** | Past turns, including old tool results | Conversation length |

Each technique in this series attacks **one or more** of these cost sources. Choosing the right technique is a matter of identifying **which cost source is actually hurting you**.

> **Core principle:** Optimize the bottleneck, not everything. Applying every technique everywhere adds complexity without proportional benefit.

---

## 2. The Five Techniques at a Glance

| Technique | Attacks | Core Idea | Best For |
|---|---|---|---|
| **Traditional Tool Calling** | Nothing (baseline) | Send all tools, return every result | Simple 1–2 tool workflows |
| **Deferred Loading** | Cost source #1 (Definitions) | Send only relevant tool schemas via a Search Tool | Many tools (dozens to thousands) |
| **Tool Output Design / Filtering** | Cost source #3 (Per-call verbosity) | Return only task-relevant fields | Verbose APIs (weather, currency, CRMs) |
| **Pagination + Structured Data** | Cost source #3 (Per-call size) | Return small slices in compact formats | Large datasets, tabular data |
| **Programmatic Tool Calling** | Cost source #4 (Workflow accumulation) | Compute externally, return only the final result | Multi-step dependent workflows |
| **Conversation Summarization (Cure)** | Cost source #5 (History) | Compact old history | Long-running conversations |

---

## 3. The Master Decision Tree

Use this tree **in order**. Stop when the problem is solved.

```text
START: Is the AI system having a tool-related context problem?
│
├─ NO → Use Traditional Tool Calling. Do not over-engineer.
│
└─ YES → Which cost source is the bottleneck?
    │
    ├─ (1) TOO MANY TOOL DEFINITIONS sent every call?
    │       └─ Use DEFERRED LOADING.
    │          (Especially if you have >10–15 tools.)
    │
    ├─ (2) EACH TOOL RESULT IS TOO VERBOSE?
    │       │
    │       ├─ API returns metadata, IDs, timestamps, nested objects?
    │       │     └─ Use TOOL OUTPUT FILTERING (return only needed fields).
    │       │
    │       ├─ Dataset is large (hundreds/thousands of records)?
    │       │     └─ Use PAGINATION (return a small slice first).
    │       │
    │       └─ Data is naturally tabular (prices, forecasts, transactions)?
    │             └─ Use STRUCTURED FORMATS (table, CSV, compact JSON).
    │
    ├─ (3) WORKFLOW HAS MANY DEPENDENT TOOL CALLS and context
    │      fills up across steps?
    │       └─ Use PROGRAMMATIC TOOL CALLING.
    │          (Especially if the final answer is a small summary
    │           of a large intermediate dataset.)
    │
    └─ (4) LONG-RUNNING CONVERSATION is filling the context?
            └─ Use CONVERSATION SUMMARIZATION (Cure).
               (Prevention should already be in place.)
```

### 3.1 How to Read the Tree

- **Start at the top.** If there is no problem, do nothing.
- **Identify the bottleneck.** Measure token usage per cost source before choosing a technique.
- **Fix the biggest bottleneck first.** Usually this is #3 (verbose outputs) or #4 (workflow accumulation).
- **Combine techniques only when multiple bottlenecks exist.**

---

## 4. Technique-by-Technique: When to Use, When Not To

### 4.1 Traditional Tool Calling (Baseline)

**What it is:** Send all tool definitions with every request; return every tool result to the model; let the model decide each step.

**Use when:**
- The workflow involves **1–2 tool calls**.
- The toolset is **small** (≤5–6 tools).
- Tool outputs are **already concise**.
- Debuggability and simplicity matter more than optimization.
- You are **prototyping** and have not measured a problem yet.

**Do not use when:**
- You have many tools and context is bloated by definitions.
- You have multi-step workflows with large intermediate results.
- Long conversations are hitting the context limit.

**Why it is the default:** It is the simplest, most transparent, and easiest to debug. Optimization should be justified by measurement, not assumption.

---

### 4.2 Deferred Loading

**What it is:** Instead of sending every tool definition, send only a **Search Tool** schema. The model calls the Search Tool, which returns only the relevant tool definitions. The model then calls the actual tool.

**Attacks:** Cost source #1 — **Tool Definitions**.

**Use when:**
- You have **many tools** — roughly **more than 10–15**, and certainly in the **hundreds or thousands**.
- Each query needs only **one or a few** tools.
- Tool definitions are **large** (complex schemas, many parameters).
- You observe that a simple query like "Hi" consumes thousands of tokens just in tool descriptions.

**Do not use when:**
- You have **5–6 or fewer tools**. The savings are tiny, and the added complexity (Search Tool + extra LLM call) is not justified.
- Every query genuinely needs most of the tools.
- Latency is extremely sensitive and an extra LLM call is unacceptable.

**Key trade-off:** Saves tokens per call but adds **one extra LLM call** and a **Search Tool** to maintain.

**Rule of thumb:** *Deferred Loading pays off when the cost of carrying all tool definitions exceeds the cost of one extra LLM call.*

---

### 4.3 Tool Output Filtering

**What it is:** Redesign each tool to return **only the fields the model needs** for the current task, instead of forwarding the raw API response.

**Attacks:** Cost source #3 — **Per-call verbosity**.

**Use when:**
- The API returns **metadata, IDs, timestamps, status codes, nested objects, or debugging info**.
- The user's question requires only **a few values** from a large payload.
- You see raw API responses being forwarded to the model.
- Examples: weather APIs, currency converters, CRM lookups, payment gateways.

**Do not use when:**
- The model genuinely needs the full payload (rare).
- The filtering logic would be brittle and might strip needed fields.
- You do not control the tool implementation (then use output post-processing instead).

**Key trade-off:** Maximum token savings, but you must **know what the model needs** in advance. Over-filtering can remove information the model needs later.

**Rule of thumb:** *If the tool output contains anything the model does not need to reason about, filter it.*

---

### 4.4 Pagination

**What it is:** Return a **small, relevant slice** of a large dataset (e.g., the 10 most recent records) and fetch more only if needed.

**Attacks:** Cost source #3 — **Per-call size** for large datasets.

**Use when:**
- The dataset is **large** (hundreds or thousands of records).
- The user's question needs only a **subset** (latest, top-N, a specific record).
- The model can **request more** if the first page is insufficient.

**Do not use when:**
- The model genuinely needs the **entire dataset** to answer (then use Programmatic Tool Calling instead).
- The dataset is small enough to fit comfortably.
- Pagination would require many round trips that increase latency more than they save.

**Key trade-off:** Low context per call, but **may require multiple calls**. Requires a **cursor or page token** design.

**Rule of thumb:** *If the model needs "some" of the data, paginate. If it needs "all" of it summarized, use Programmatic Tool Calling.*

---

### 4.5 Structured Data Preservation

**What it is:** Keep naturally tabular data in **tables, CSV, or compact JSON** instead of converting it into prose.

**Attacks:** Cost source #3 — **Token waste from verbose formatting**.

**Use when:**
- The data is naturally tabular: weather forecasts, stock prices, transaction histories, analytical reports.
- The current output is **long paragraphs** describing rows of data.
- The same information can be represented with **fewer tokens** in a structured format.

**Do not use when:**
- The data is genuinely narrative (not tabular).
- The model needs prose to reason about it (rare for tabular data).
- The structured format would be harder for the model to parse than a simple table.

**Key trade-off:** Same information, fewer tokens, but requires the model to **parse structure** (modern LLMs do this well).

**Rule of thumb:** *If the data has rows and columns, keep it as rows and columns.*

---

### 4.6 Programmatic Tool Calling

**What it is:** Perform the entire multi-step computation **outside the LLM** and return only the **final processed result** to the model.

**Attacks:** Cost source #4 — **Accumulated intermediate results across a workflow**.

**Use when:**
- The workflow has **multiple dependent tool calls** (step 2 needs step 1's output).
- The application **processes large datasets** before producing a final answer.
- **Large intermediate outputs** would otherwise enter the context.
- The final answer is a **small summary** of a large intermediate dataset.
- The task involves **arithmetic, aggregation, sorting, joining** — things LLMs are bad at.
- Context fills up **across steps**, not just within one call.

**Do not use when:**
- The workflow uses **only 1–2 tool calls**. Traditional calling is simpler.
- The model **needs to inspect intermediate results** to decide the next step (i.e., the flow is genuinely exploratory, not deterministic).
- The external program would be hard to test, and correctness is critical.
- Debuggability of intermediate steps is more important than context savings.

**Key trade-off:** Huge context savings and cleaner reasoning, but the external program becomes part of the **correctness surface** — it must be tested, because the model cannot verify hidden steps.

**Rule of thumb:** *If the model only needs the final answer and not the intermediate data, compute externally.*

---

### 4.7 Conversation Summarization (Cure)

**What it is:** Summarize older conversation history, remove the detailed messages, and replace them with the summary.

**Attacks:** Cost source #5 — **Conversation history**.

**Use when:**
- The conversation is **long-running** (multi-turn, many tool calls).
- Prevention techniques are **already in place** but context still fills.
- The agent needs to continue working over many turns.
- Older turns are **no longer directly relevant** but contain decisions or facts that matter.

**Do not use when:**
- Prevention has not been tried yet. **Prevention should always come first.**
- The conversation is short.
- Every detail of the history is critical and summarization would lose needed facts.
- You cannot verify that the summary preserves necessary information.

**Key trade-off:** Enables longer conversations, but summarization is **lossy**. A bad summary can cause future reasoning errors.

**Rule of thumb:** *Cure only after prevention. Summarize facts, decisions, and unresolved questions — not wording.*

---

## 5. Combination Matrix: Which Techniques Work Together

Techniques are **complementary**, not alternatives. Here is how they combine:

| Combination | When to Combine | Why |
|---|---|---|
| **Deferred Loading + Output Filtering** | Many tools *and* verbose outputs | Reduce both definitions and per-call verbosity |
| **Output Filtering + Pagination** | Verbose API *and* large dataset | Filter fields *and* limit records |
| **Pagination + Structured Data** | Large tabular dataset | Small slices in compact format |
| **Programmatic Tool Calling + Output Filtering** | Multi-step workflow *and* verbose tools | Even the final result should be concise |
| **Programmatic Tool Calling + Deferred Loading** | Many tools *and* multi-step workflows | Reduce both definitions and intermediates |
| **All prevention + Summarization** | Long conversations despite prevention | Cure as a fallback |

### 5.1 The Layered Architecture

```text
┌──────────────────────────────────────────────────┐
│ Layer 1: Tool Definitions                        │
│   → Deferred Loading (if many tools)             │
├──────────────────────────────────────────────────┤
│ Layer 2: Per-Call Tool Results                   │
│   → Output Filtering                             │
│   → Pagination                                   │
│   → Structured Data                              │
├──────────────────────────────────────────────────┤
│ Layer 3: Across-Workflow Results                 │
│   → Programmatic Tool Calling                    │
├──────────────────────────────────────────────────┤
│ Layer 4: Conversation History                    │
│   → Summarization (Cure, last resort)            │
└──────────────────────────────────────────────────┘
```

**Design principle:** Apply prevention at the lowest layer where the problem exists. Use cure only at the top.

---

## 6. Scenario Walkthroughs

### Scenario 1 — Small Chatbot
- **Tools:** 4
- **Workflow:** 1 tool call per query
- **Outputs:** Short
- **Decision:** **Traditional Tool Calling.** No optimization needed.

---

### Scenario 2 — Enterprise Assistant with 200 Tools
- **Tools:** 200
- **Workflow:** Usually 1 tool call
- **Outputs:** Moderate
- **Decision:** **Deferred Loading.** A "Hi" query would otherwise carry all 200 schemas.

---

### Scenario 3 — Weather Assistant
- **Tools:** 5
- **Workflow:** 1 tool call
- **Outputs:** API returns 50 attributes; user needs 2
- **Decision:** **Tool Output Filtering.** Return only temperature and condition.

---

### Scenario 4 — Order History Assistant
- **Tools:** 6
- **Workflow:** 1 tool call
- **Outputs:** Customer has 500 orders; user asks for the latest
- **Decision:** **Pagination.** Return the 10 most recent orders.

---

### Scenario 5 — Financial Report Agent
- **Tools:** 10
- **Workflow:** 30 dependent tool calls
- **Outputs:** Large intermediate datasets; final answer is a summary
- **Decision:** **Programmatic Tool Calling + Output Filtering.** Compute externally; return a concise final result.

---

### Scenario 6 — Long-Running Support Agent
- **Tools:** 8
- **Workflow:** Multi-turn conversation, 40 tool calls over hours
- **Outputs:** Already filtered
- **Decision:** **Conversation Summarization (Cure).** Prevention is already in place; now compact history.

---

### Scenario 7 — Stock Analysis Agent
- **Tools:** 12
- **Workflow:** 15 tool calls, tabular data
- **Outputs:** Stock prices as paragraphs
- **Decision:** **Programmatic Tool Calling + Structured Data.** Compute externally; return a compact table.

---

### Scenario 8 — Full Enterprise System
- **Tools:** 500
- **Workflow:** Multi-step, multi-turn, long-running
- **Outputs:** Verbose APIs, large datasets
- **Decision:** **All techniques layered:**
  1. Deferred Loading for tool definitions.
  2. Output Filtering + Pagination + Structured Data for per-call results.
  3. Programmatic Tool Calling for multi-step workflows.
  4. Summarization as the final cure.

---

## 7. Anti-Patterns: What Not to Do

| Anti-Pattern | Why It Is Wrong | Better Approach |
|---|---|---|
| **Applying every technique everywhere** | Adds complexity without proportional benefit | Measure first; fix the bottleneck |
| **Using Deferred Loading for 3 tools** | Extra LLM call costs more than it saves | Traditional Tool Calling |
| **Using Programmatic Tool Calling for 2 calls** | Over-engineered; harder to debug | Traditional Tool Calling |
| **Summarizing before preventing** | You pay for waste, then pay to compress it | Filter and paginate first |
| **Forwarding raw API responses** | Metadata, IDs, timestamps waste context | Filter to needed fields |
| **Returning all records "just in case"** | Context bloat; the model rarely needs all | Paginate or compute externally |
| **Converting tables to paragraphs** | More tokens, same information | Keep as table/CSV/JSON |
| **Hiding intermediate steps without testing the program** | Confident wrong answers | Test the program; log intermediates |
| **Over-filtering tool outputs** | Strips information the model needs later | Filter to *task-relevant* fields, not arbitrary fields |
| **Setting a high semantic cache threshold without cost analysis** | Hit rate collapses; cache becomes useless | Use a cost/correctness table |

---

## 8. Decision Cheat Sheet

### 8.1 By Symptom

| Symptom | Technique |
|---|---|
| "Hi" costs 2,000+ tokens | **Deferred Loading** |
| Tool output has timestamps, IDs, metadata | **Output Filtering** |
| Tool returns 500 records when 10 suffice | **Pagination** |
| Stock/weather data returned as paragraphs | **Structured Data** |
| Context fills after 15 tool calls | **Programmatic Tool Calling** |
| Final answer is a summary of a large dataset | **Programmatic Tool Calling** |
| Long conversation hits context limit | **Summarization (Cure)** |
| Model does arithmetic and gets it wrong | **Programmatic Tool Calling** |

### 8.2 By Scale

| Scale | Recommended Default |
|---|---|
| 1–2 tools, 1–2 calls | Traditional Tool Calling |
| 3–10 tools, simple workflow | Traditional + Output Filtering |
| 10–50 tools | Deferred Loading + Output Filtering |
| 50+ tools | Deferred Loading + Output Filtering + Pagination |
| Multi-step workflows | Programmatic Tool Calling |
| Long conversations | + Summarization |

### 8.3 By Cost Source

| If the bottleneck is… | Use… |
|---|---|
| Tool definitions | Deferred Loading |
| Per-call verbosity | Output Filtering |
| Per-call dataset size | Pagination + Structured Data |
| Across-workflow accumulation | Programmatic Tool Calling |
| Conversation history | Summarization |

---

## 9. The Golden Rules

1. **Measure before optimizing.** Identify which cost source is actually the bottleneck.
2. **Start simple.** Traditional Tool Calling is the default until a problem is proven.
3. **Prevent before curing.** Filtering, pagination, and programmatic computation are cheaper than summarization.
4. **Fix the biggest bottleneck first.** Do not apply every technique everywhere.
5. **Combine techniques only when multiple bottlenecks exist.**
6. **Keep tool outputs task-relevant.** Every unnecessary token reduces reasoning space.
7. **Keep structured data structured.**
8. **Compute externally what the LLM is bad at** — arithmetic, joins, aggregation.
9. **Test the external program.** Hidden intermediate steps are a correctness surface.
10. **Summarize facts, not wording.** Summaries must preserve what future reasoning needs.

---

## 10. Final Summary

| Question | Answer |
|---|---|
| Too many tool definitions? | **Deferred Loading** |
| Tool output too verbose? | **Output Filtering** |
| Too many records in one output? | **Pagination** |
| Tabular data as paragraphs? | **Structured Data** |
| Too many intermediate results across steps? | **Programmatic Tool Calling** |
| Long conversation filling context? | **Summarization (Cure)** |
| Simple workflow? | **Traditional Tool Calling** |
| Multiple problems? | **Combine techniques, layered by cost source** |

> **The single most important idea:**  
> Tool Calling optimization is not about applying every technique. It is about **identifying which of the five context cost sources is hurting you**, and applying the **one technique that targets it** — then combining only when necessary.

---

## 11. Self-Test Questions

1. What are the five context cost sources in a tool-using AI system?
2. Which technique targets tool definitions?
3. Which technique targets per-call verbosity?
4. Which technique targets per-call dataset size?
5. Which technique targets across-workflow accumulation?
6. Which technique targets conversation history?
7. When should you use Traditional Tool Calling?
8. When is Deferred Loading not worth it?
9. When should you paginate instead of using Programmatic Tool Calling?
10. When should you use Programmatic Tool Calling instead of pagination?
11. Why is summarization a cure rather than a prevention?
12. Why should prevention come before cure?
13. What is the main risk of Programmatic Tool Calling?
14. What is the main risk of over-filtering?
15. Why should you measure before optimizing?
16. Give an example of two techniques that combine well.
17. Give an example of an anti-pattern.
18. What is the golden rule about structured data?
19. What is the golden rule about computation the LLM is bad at?
20. What is the single most important idea in this guide?

### Answer Key
1. Tool definitions; tool calls; per-call tool results; across-workflow results; conversation history.
2. Deferred Loading.
3. Tool Output Filtering.
4. Pagination.
5. Programmatic Tool Calling.
6. Conversation Summarization.
7. Simple 1–2 tool workflows, small toolsets, concise outputs, prototyping.
8. When you have 5–6 or fewer tools; the extra LLM call and Search Tool outweigh the savings.
9. When the user needs a subset (latest, top-N) and the model can request more.
10. When the final answer requires summarizing a large dataset and intermediate results should never enter context.
11. It removes information after it has already accumulated, rather than stopping it from entering.
12. Information that never enters the context never costs tokens; prevention is cheaper and more reliable.
13. The external program becomes a correctness surface; a bug can produce confident wrong answers.
14. It may strip information the model needs later.
15. Optimization adds complexity; without measurement you may optimize the wrong bottleneck.
16. Deferred Loading + Output Filtering; Programmatic Tool Calling + Structured Data.
17. Applying every technique everywhere; using Programmatic Tool Calling for 2 calls; summarizing before preventing.
18. If the data is naturally structured, keep it structured.
19. Compute externally what the LLM is bad at — arithmetic, joins, aggregation.
20. Identify which of the five context cost sources is hurting you, and apply the one technique that targets it; combine only when necessary.

---

*End of final guide.*