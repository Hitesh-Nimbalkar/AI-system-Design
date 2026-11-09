# Incremental Detailed Notes: Understanding MCP — The Filtration Layer and Context Engineering

## 1. Understanding MCP — What It Is and What It Is Not

### 1.1 Nature of MCP

**Definition:** MCP is essentially a **protocol** — a set of rules — designed to allow two parties to connect and share information seamlessly:

- **Party 1:** An AI application (the Host)
- **Party 2:** An external server (the MCP Server)

**Key property:** It is a **rulebook**, not an engine, not a database, and not a context manager.

### 1.2 Core Purpose

The primary function of MCP is to enable an AI application to **access resources, prompts, and tools** residing on a server so they can be utilized within the AI's environment.

**What MCP provides:**

| Element | Description |
|---|---|
| **Tools** | Executable functions (e.g., write email, run code) |
| **Resources** | Static textual data |
| **Prompts** | Pre-defined instruction templates |

**What MCP does:** It defines **how the Host and Server talk to each other**. It does not decide what enters the LLM's context window.

### 1.3 The "Context Problem" Misconception

> **MCP itself is NOT the cause of context problems or context window bloat.**

This is a crucial correction. Many engineers blame MCP when they see a bloated context window. But MCP **successfully fulfills its role** of seamless integration and communication.

**What MCP does correctly:**
- Establishes connection
- Handshakes properly
- Discovers resources
- Transfers data to the Host

**What MCP does NOT do (and was never designed to do):**
- Decide what to send to the LLM
- Filter irrelevant tools
- Manage the context window
- Prioritize information based on the user query

### 1.4 The Actual Root Cause of Bloat

> The problem arises at the **AI Application level**.

**The mechanism:**

1. The MCP server sends **all elements** (tools, resources, prompts) to the AI application.
2. The AI application **"dumps" everything** into the LLM's context window **simultaneously**.
3. This leads to:
   - **Context pollution** — irrelevant content crowding the window
   - **Excessive token usage** — thousands of tokens wasted
   - **Diluted attention** — the relevant element is buried

### 1.5 Responsibility Split

| Layer | Responsibility | Does it correctly in the naive setup? |
|---|---|---|
| **MCP Protocol** | Connecting Host and Server | ✅ Yes |
| **MCP Server** | Exposing tools/resources/prompts | ✅ Yes |
| **AI Application** | Deciding what enters the LLM context | ❌ **No — this is the failure point** |
| **LLM** | Reasoning over what it receives | ✅ Yes (given what it is given) |

**The lesson:** Blaming MCP is like blaming the postal service for a cluttered desk. The mail arrived correctly; the desk owner failed to sort it.

### 1.6 The Correct Framing

```text
WRONG framing:
  "MCP causes context bloat."

CORRECT framing:
  "MCP delivers all available elements correctly.
   The AI Application then dumps all of them into the context.
   The AI Application must be redesigned to filter."
```

---

## 2. The Engineering Strategy: The Filtration Layer

### 2.1 The Need

To prevent context pollution, the AI application must be designed with an **Engineering / Filtration Layer** that sits **between** the incoming MCP data and the LLM.

### 2.2 Architecture Position

```text
┌─────────────────┐
│ MCP Server      │
│ (all tools,     │
│  resources,     │
│  prompts)       │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────┐
│ AI APPLICATION                      │
│                                     │
│  ┌───────────────────────────────┐  │
│  │ FILTRATION LAYER              │  │
│  │ (the "Watchman")              │  │
│  │                               │  │
│  │ - Receives everything         │  │
│  │ - Decides what is relevant    │  │
│  │ - Passes only that forward    │  │
│  └───────────────┬───────────────┘  │
│                  │                  │
│                  ▼                  │
│  ┌───────────────────────────────┐  │
│  │ LLM CONTEXT WINDOW            │  │
│  │ (only relevant elements)      │  │
│  └───────────────────────────────┘  │
└─────────────────────────────────────┘
```

### 2.3 The "Watchman" Concept

**What it is:** The filtration layer acts as a **gatekeeper**.

**Its job:** Ensure that **only information strictly relevant to the user's specific query** is passed to the LLM.

**Why a gatekeeper, not a dump truck:**

| Naive behavior | Watchman behavior |
|---|---|
| Receives 60 tools → sends 60 tools | Receives 60 tools → sends 2 relevant tools |
| Receives 100 documents → sends all | Receives 100 documents → sends only those above threshold |
| Context polluted | Context focused |

**The gatekeeper metaphor:**
- A building has hundreds of visitors a day.
- The watchman checks each one at the door.
- Only those with legitimate business enter.
- The result: a clean, focused interior.

### 2.4 Categorization of MCP Elements

For effective management, MCP elements are divided into **two broad categories**.

| Category | Contains | Nature | Management approach |
|---|---|---|---|
| **Tools** | Executable functions | Action-oriented | Deferred Loading, Programmatic Tool Calling, Pagination |
| **Textual Data** | Resources and Prompts | Information-oriented | RAG pipeline with similarity thresholding |

**Why this split matters:** Tools and textual data have different shapes, different risks, and different filtering techniques. Managing them together is inefficient; managing them separately allows targeted techniques.

### 2.5 The Two Management Streams

```text
MCP Server delivers:
  ├── Tools (executable)
  │     └── Managed by: Deferred Loading / Programmatic Calling / Pagination
  │
  └── Textual Data (Resources + Prompts)
        └── Managed by: RAG pipeline + similarity thresholding
```

---

## 3. Theoretical Management of Tools

When an application has access to a **vast array of tools** via MCP, loading all of them into the context window is inefficient.

**The following techniques are used to manage this.**

### 3.1 Deferred Loading

**What it is:** Instead of providing the LLM with the **full definitions of every available tool**, the system provides only:

- A **"Search Tool"**, or
- A **high-level list** of tools.

**How it works:**

1. LLM sees a Search Tool schema (small).
2. LLM calls Search Tool with the user's intent.
3. Search Tool returns the relevant tool definition(s).
4. LLM calls the actual tool.

**Why it works:** The LLM never carries the full schemas of irrelevant tools.

### 3.2 Programmatic Tool Calling

**What it is:** The system uses **logic** to determine which specific tool is required based on the query, **before** loading its full schema into the context.

**How it works:**

1. Application analyzes the query programmatically.
2. It identifies the tool needed.
3. Only that tool's schema is loaded into the context.
4. The LLM calls the tool.

**Key property:** The **decision** about which tool to load happens **outside the LLM**. The LLM only sees the tool it needs.

### 3.3 Pagination

**What it is:** If there are many tools, they can be managed **in segments** rather than as a single massive block.

**How it works:**

1. Tools are grouped into pages (e.g., 10 tools per page).
2. Only the relevant page is loaded.
3. If needed, more pages are fetched.

**When it applies:** Large tool collections where tools are naturally grouped (e.g., by service, by category).

### 3.4 Tool Management Comparison

| Technique | Who decides the relevant tool | What the LLM sees | Best for |
|---|---|---|---|
| **Deferred Loading** | The LLM via Search Tool | Search Tool schema, then one tool | Many tools, unpredictable queries |
| **Programmatic Tool Calling** | The application logic | Only the chosen tool | Deterministic workflows, predictable patterns |
| **Pagination** | The application / LLM | One page of tools at a time | Large grouped tool collections |

### 3.5 Tool Management Flow

```text
All tools from MCP server (e.g., 60+)
        │
        ▼
┌──────────────────────────────────────┐
│ Filtration Layer for Tools           │
│                                      │
│  Option A: Deferred Loading          │
│    - LLM sees Search Tool only       │
│    - Search Tool returns relevant    │
│                                      │
│  Option B: Programmatic Calling      │
│    - App decides which tool          │
│    - Loads only that schema          │
│                                      │
│  Option C: Pagination                │
│    - Loads relevant page only        │
│                                      │
└──────────────┬───────────────────────┘
               │
               ▼
      Only relevant tool(s) enter context
```

---

## 4. Theoretical Management of Textual Data (RAG Optimization)

For large amounts of **textual data** (Resources and Prompts) from an MCP server, a **standard RAG pipeline** is implemented. However, the source suggests a **more refined theoretical approach** to retrieval.

### 4.1 The Standard RAG Problem: Top-K Retrieval

**How standard RAG works:**

1. User query is embedded.
2. The system retrieves the **Top K** most similar documents (e.g., Top 3).
3. Those Top K results are placed in the context window.
4. The LLM reads them and generates an answer.

**The problem:**

> If the **most relevant** result is still **highly irrelevant** (low similarity), the system **still dumps** those low-value results into the context window.

**Why this is bad:**

| Scenario | Top-K behavior | Result |
|---|---|---|
| Query: "Refund policy" | Top 3 docs retrieved | Docs 1–3 are about refunds → good |
| Query: "Refund policy for Mars" | Top 3 docs retrieved, all low similarity | Docs 1–3 are unrelated → still dumped → context polluted |

**The core flaw:** Top-K always returns *something*, even when *nothing* is relevant. It has no **rejection mechanism**.

### 4.2 The Threshold Solution

**What it is:** A **minimum benchmark (threshold)** is set — e.g., **0.45** or **45% similarity**.

**The rule:**

> Only results that meet or exceed this score are passed to the context window.

**Behavior:**

| Query | Top-K result similarity | With threshold 0.45 | Context outcome |
|---|---|---|---|
| "Refund policy" | 0.85, 0.72, 0.60 | All pass | ✅ 3 relevant docs |
| "Refund policy for Mars" | 0.30, 0.25, 0.20 | None pass | ✅ Empty context |
| Mixed relevance | 0.70, 0.30, 0.28 | Only 0.70 passes | ✅ 1 relevant doc |

### 4.3 Why This Is a Major Improvement

> If no truly relevant information exists, the **context remains unpolluted** by "best-of-the-bad" matches.

**Benefits:**

| Without threshold | With threshold |
|---|---|
| Always sends Top-K | Sends only relevant docs |
| Pollutes context with irrelevant docs | Keeps context clean |
| Model may hallucinate based on irrelevant docs | Model says "I don't know" or uses other sources |
| Harder to detect low-quality answers | Clear signal when no relevant data exists |

### 4.4 The "Best-of-the-Bad" Concept

**Definition:** When Top-K is forced to return results even when the best available match is poor, the system sends **low-quality matches** to the LLM.

**Why this is harmful:**
- The LLM may treat low-quality matches as relevant.
- It may generate an answer grounded in irrelevant data.
- The user gets a confident wrong answer.
- The context window is filled with noise that could have been left out.

**Thresholding prevents this** by allowing the system to return **nothing** when nothing is relevant.

### 4.5 RAG Optimization Summary

| Aspect | Top-K | Threshold |
|---|---|---|
| Always returns results | ✅ Yes | ❌ Only if above threshold |
| Rejection possible | ❌ No | ✅ Yes |
| Context pollution risk | High | Low |
| Best for | General retrieval | High-precision tasks |
| Risk | "Best-of-the-bad" | May return nothing if threshold too high |

---

## 5. Agentic Decision-Making Logic

The AI application follows a **structured theoretical framework** to decide how to handle an incoming input. This is governed by **detailed system instructions** that categorize inputs into **three cases**.

### 5.1 The Three Cases

```text
User input arrives
        │
        ▼
┌──────────────────────────────────────┐
│ System instruction classifies input  │
└──────────────┬───────────────────────┘
               │
       ┌───────┼───────────────┐
       │       │               │
       ▼       ▼               ▼
   Case 1    Case 2          Case 3
   Knowledge Actions /    General
   / Policy  Live Data    Conversation
```

### 5.2 Case 1 — Knowledge or Policy Questions

**What it is:** The user is asking a factual question, policy question, or knowledge question.

**The process:**

1. The system checks the **Reference Information** provided by the RAG pipeline.
2. **If relevant data exists**, it answers **based only on that data**.
3. This avoids hallucination.

**Key property:** The answer is **grounded** in retrieved reference information. The LLM is instructed not to invent.

**Example:**
- User: "What is your refund policy?"
- System: Retrieves refund policy documents above threshold.
- LLM: Answers based on those documents.

### 5.3 Case 2 — Actions or Live Data

**What it is:** The user wants the system to **perform an action** or retrieve **live data**.

**The process:**

1. The system **recognizes the need for a tool**.
2. It first uses a **Search Tool** to identify the **correct tool** among available MCP resources.
3. It then **executes** that tool.

**Key property:** The system does not expose all tools to the LLM. It uses a **Search Tool** to find the right one, then acts.

**Example:**
- User: "Send an email to John."
- System: Recognizes tool needed → Search Tool finds `send_email` → executes → returns result.

### 5.4 Case 3 — General Conversation

**What it is:** The input is **conversational** — e.g., "Hi, how are you?"

**The process:**

1. The system **bypasses both RAG and Tool Calling**.
2. It responds **directly**.

**Why:** There is no need to retrieve documents or call tools for a greeting. Doing so would waste tokens and add latency.

**Key property:** The system is smart enough to **recognize low-complexity inputs** and avoid unnecessary work.

**Example:**
- User: "Hi, how are you?"
- System: No RAG, no tools → LLM responds directly → save tokens.

### 5.5 The Decision Logic at a Glance

| Case | Requires RAG? | Requires tools? | What the LLM sees |
|---|---|---|---|
| **1. Knowledge/Policy** | ✅ Yes (above threshold) | ❌ No | User query + relevant reference docs |
| **2. Actions/Live Data** | ❌ No | ✅ Yes (via Search Tool) | User query + Search Tool → chosen tool |
| **3. General Conversation** | ❌ No | ❌ No | User query only |

### 5.6 Why This Framework Is Powerful

**Without this framework:**

- Every query gets RAG results (even greetings).
- Every query gets all tools (even policy questions).
- Context is polluted for every input.

**With this framework:**

- Each query gets exactly what it needs.
- Unnecessary paths are bypassed.
- Tokens are saved at every step.

**The insight:** Most efficiency gains come not from making each step faster, but from **skipping steps that don't apply**.

---

## 6. Benefits of Context Engineering

Implementing this theoretical filtration layer leads to **significant improvements** in AI performance.

### 6.1 Token Efficiency

**What it means:** By only sending relevant data, token consumption can **drop drastically**.

**The data from the source:**

> Reduction from ~**8,500 tokens** to ~**1,000 tokens** for similar tasks.

**What that means:**

| Metric | Before | After | Improvement |
|---|---|---|---|
| Tokens per task | ~8,500 | ~1,000 | **~88% reduction** |
| Relative cost | 100% | ~12% | **~8.5× cheaper** |
| Context used | High | Low | More room for reasoning |

**Why this is huge:**

- **Cost:** API costs scale with tokens.
- **Latency:** Smaller prompts process faster.
- **Reasoning quality:** Less noise → better focus.
- **Scalability:** More headroom before hitting limits.

### 6.2 Context Health

**What it means:** The context window stays **"healthy"** and **focused**.

**Why it matters:** The risk of the model getting confused by irrelevant **"noise"** is reduced.

**What "healthy" looks like:**

| Unhealthy context | Healthy context |
|---|---|
| 60 tool schemas | 2 relevant tool schemas |
| All documents from RAG | Only documents above threshold |
| Old conversation history | Summarized history |
| Mixed relevant and irrelevant | Focused, relevant only |

**The result:** Better reasoning, fewer hallucinations, clearer answers.

### 6.3 Scalability

**What it means:** This approach allows an application to connect to **multiple MCP servers** with **hundreds of tools and resources** without ever hitting context limits.

**Why this works:**

| Without filtration | With filtration |
|---|---|
| 10 servers × 60 tools = 600 tools in context | Only 1–2 relevant tools in context |
| Context window filled | Context window manageable |
| Impossible to scale | Scales to hundreds of servers |

**The insight:** Filtration is what makes MCP's value proposition — connecting to many services — actually usable at scale.

### 6.4 Long-Term Management

**What it means:** For **long-running agents**, further techniques like **summarization** can be applied to the accumulated context to keep it manageable **over time**.

**Why this is needed:** Even with filtration, a long conversation accumulates:
- Prior tool calls
- Prior results
- Prior reasoning
- Prior reference information

**The layered approach:**

```text
Layer 1: Filtration      → prevents unnecessary elements from entering
Layer 2: Summarization   → compacts what has already accumulated
```

**The principle:** Prevention first, cure as fallback (consistent with earlier material on context management).

### 6.5 The Four Benefits at a Glance

| Benefit | What it means | Why it matters |
|---|---|---|
| **Token Efficiency** | ~8.5k → ~1k tokens | ~8.5× cheaper per task |
| **Context Health** | Focused, low-noise context | Better reasoning, fewer hallucinations |
| **Scalability** | Hundreds of tools across many servers | MCP's value becomes usable |
| **Long-term Management** | Summarization for long agents | Sustainable over time |

---

## 7. The Full Architecture: Everything Together

```text
┌─────────────────────────────────────────────────┐
│ MCP SERVERS (many)                              │
│   - Tools (executable)                          │
│   - Resources (textual)                         │
│   - Prompts (textual)                           │
└───────────────────────┬─────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────┐
│ AI APPLICATION                                  │
│                                                 │
│  ┌───────────────────────────────────────────┐  │
│  │ FILTRATION LAYER ("Watchman")             │  │
│  │                                           │  │
│  │  Classify user input:                     │  │
│  │  ├─ Case 1: Knowledge → RAG threshold     │  │
│  │  ├─ Case 2: Action → Search Tool          │  │
│  │  └─ Case 3: Conversation → bypass         │  │
│  │                                           │  │
│  │  Tool management:                         │  │
│  │  ├─ Deferred Loading                      │  │
│  │  ├─ Programmatic Calling                  │  │
│  │  └─ Pagination                            │  │
│  │                                           │  │
│  │  Textual management:                      │  │
│  │  └─ RAG + similarity threshold            │  │
│  └─────────────────┬─────────────────────────┘  │
│                    │                            │
│                    ▼                            │
│  ┌───────────────────────────────────────────┐  │
│  │ LLM CONTEXT WINDOW (healthy, focused)     │  │
│  │                                           │  │
│  │  - User query                             │  │
│  │  - Only relevant tools                    │  │
│  │  - Only relevant reference info           │  │
│  │  - (Summarized history if long-running)   │  │
│  └───────────────────────────────────────────┘  │
└─────────────────────────────────────────────────┘
```

---

## 8. Key Takeaways

1. **MCP is a protocol** — a set of rules for connection and sharing between Host and Server.
2. **MCP is NOT the cause of context bloat**; it fulfills its role correctly.
3. The **root cause of bloat is at the AI Application level** — dumping everything into the context.
4. The solution is an **Engineering / Filtration Layer** ("Watchman") between MCP data and the LLM.
5. MCP elements are categorized into **Tools** (executable) and **Textual Data** (Resources + Prompts).
6. **Tools** are managed via **Deferred Loading, Programmatic Tool Calling, and Pagination**.
7. **Textual data** is managed via **RAG with similarity thresholding**.
8. **Top-K retrieval's flaw:** it always returns results, even when they are irrelevant ("best-of-the-bad").
9. **Thresholding's fix:** only results above a minimum similarity (e.g., 0.45) enter the context — or none do.
10. **Agentic logic** classifies inputs into three cases: Knowledge, Action, Conversation.
11. **Case 1 (Knowledge):** answer from RAG reference data only → avoid hallucination.
12. **Case 2 (Action):** use a Search Tool to find the correct tool → execute it.
13. **Case 3 (Conversation):** bypass RAG and tools → respond directly.
14. **Token efficiency:** ~8,500 → ~1,000 tokens (≈88% reduction).
15. **Context health:** less noise → better reasoning.
16. **Scalability:** hundreds of tools across multiple servers, without hitting limits.
17. **Long-term management:** summarization as a further layer for long-running agents.

---

## 9. Glossary

| Term | Definition |
|---|---|
| **MCP** | Model Context Protocol — the rulebook connecting Hosts to Servers. |
| **Host** | The AI Application (client). |
| **Server** | The external service provider exposing tools/resources/prompts. |
| **Filtration Layer** | The engineering layer between MCP data and the LLM that decides what enters the context. |
| **Watchman** | The gatekeeper concept — the filtration layer ensuring only relevant information reaches the LLM. |
| **Tools** | Executable functions exposed by MCP servers. |
| **Textual Data** | Resources and Prompts — static information, not executable. |
| **Deferred Loading** | Providing a Search Tool instead of all tool definitions; the LLM fetches only relevant tools. |
| **Programmatic Tool Calling** | Using application logic to decide which tool to load before exposing it to the LLM. |
| **Pagination** | Loading tools in segments rather than as one massive block. |
| **RAG** | Retrieval-Augmented Generation — retrieving relevant documents to ground the LLM's answers. |
| **Top-K Retrieval** | Fetching the K most similar documents regardless of absolute similarity. |
| **Similarity Threshold** | A minimum similarity score (e.g., 0.45) that a result must meet to enter the context. |
| **Best-of-the-Bad** | The situation where Top-K returns low-quality matches because no good match exists. |
| **Context Pollution** | Irrelevant content crowding the context window. |
| **Context Health** | The state of having a focused, low-noise context window. |
| **Summarization** | Compacting accumulated conversation history for long-running agents. |

---

## 10. Self-Test Questions

### MCP Basics
1. What is MCP, and what is its core purpose?
2. Why is MCP not the cause of context bloat?
3. Where does the root cause of context bloat actually lie?
4. What happens when an AI application receives all MCP elements?

### The Filtration Layer
5. What is the filtration layer, and where does it sit?
6. What is the "Watchman" concept?
7. Why are MCP elements categorized into two broad groups?
8. What are the two groups, and what does each contain?

### Tool Management
9. How does Deferred Loading manage tools?
10. How does Programmatic Tool Calling manage tools?
11. How does Pagination manage tools?
12. Which tool management technique gives the LLM the most decision-making power?

### Textual Data Management
13. What is the standard RAG approach, and what is its flaw?
14. What is "best-of-the-bad"?
15. How does similarity thresholding solve the Top-K problem?
16. What happens to the context when no document meets the threshold?

### Agentic Decision-Making
17. What are the three cases in the agentic decision framework?
18. What happens in Case 1 (Knowledge/Policy)?
19. What happens in Case 2 (Actions/Live Data)?
20. What happens in Case 3 (General Conversation)?
21. Why does bypassing unnecessary steps save tokens?

### Benefits
22. What is the token reduction reported in the source?
23. What is "context health," and why does it matter?
24. How does filtration enable scalability with multiple MCP servers?
25. What additional technique helps long-running agents?

### Answer Key
1. MCP is a protocol — a set of rules — enabling an AI application to connect to an external server and access its resources, prompts, and tools.
2. Because MCP correctly fulfills its integration role; the bloat happens when the application dumps everything into the LLM.
3. At the AI Application level — specifically, in how it passes data to the LLM.
4. The application dumps them all into the LLM's context window simultaneously, causing pollution and excessive token usage.
5. A layer between incoming MCP data and the LLM that passes only relevant information forward.
6. A gatekeeper concept — the layer acts as a guard ensuring only relevant information enters the LLM's context.
7. Because Tools and Textual Data have different natures and require different filtering techniques.
8. Tools (executable functions) and Textual Data (Resources and Prompts).
9. It provides a Search Tool (or high-level list) instead of all tool definitions; the LLM fetches only what it needs.
10. Application logic decides which tool is required before loading its schema.
11. Tools are loaded in segments rather than as one massive block.
12. Deferred Loading — the LLM calls the Search Tool to find relevant tools.
13. Top-K retrieval fetches the K most similar results regardless of absolute similarity; its flaw is that it always returns results, even irrelevant ones.
14. When Top-K is forced to return results even though the best available match is poor, the system sends low-quality matches to the LLM.
15. It sets a minimum similarity score; only results that meet or exceed it enter the context.
16. The context remains unpolluted — no irrelevant documents are sent.
17. Knowledge/Policy Questions, Actions/Live Data, General Conversation.
18. The system checks RAG reference information and answers based only on that data to avoid hallucination.
19. The system recognizes the need for a tool, uses a Search Tool to find it, and executes it.
20. The system bypasses RAG and tool calling, responding directly to save tokens.
21. Because each skipped path avoids loading its associated context (documents, tool schemas) into the window.
22. From ~8,500 tokens to ~1,000 tokens for similar tasks.
23. A focused, low-noise context window; it reduces the risk of confusion and improves reasoning quality.
24. By ensuring only relevant elements from each server enter the context, hundreds of tools can be connected without exhausting the window.
25. Summarization of accumulated context.

---

## 11. Mental Model Summary

```text
WHO IS AT FAULT?
  MCP          ✅ correct — connects and delivers properly
  Server       ✅ correct — exposes tools/resources/prompts
  Application  ❌ at fault — dumps everything into context
  LLM          ✅ correct — reasons over what it gets

THE FIX:
  Insert a FILTRATION LAYER ("Watchman") between MCP and LLM.
  It decides what is relevant and only lets that through.

TWO STREAMS:
  Tools         → Deferred Loading / Programmatic Calling / Pagination
  Textual Data  → RAG + similarity threshold

THREE CASES:
  Knowledge      → RAG (above threshold) → answer from reference
  Action         → Search Tool → execute tool
  Conversation   → bypass both → respond directly

THE RESULT:
  Tokens:   ~8,500 → ~1,000  (~88% reduction)
  Context:  polluted → healthy and focused
  Scaling:  impossible → hundreds of tools across servers
  Long-term: summarization keeps it sustainable
```

---

*End of incremental detailed notes.*