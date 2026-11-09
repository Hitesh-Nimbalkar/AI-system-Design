# Incremental Notes: AI vs. AI Applications & How MCP Becomes a Context Problem

## 1. AI vs. AI Applications

To understand MCP, it is essential to distinguish between the AI **"brain"** and the **application** that uses it.

### 1.1 AI — The Brain

**Definition:** The Large Language Model (LLM) itself — e.g., Claude, Gemini, GPT-4.

**Primary role:** Process input and generate output.

**What it does:**
- Reads the context it is given
- Reasons over that context
- Decides what to say or which step to take next

**What it does NOT do:**
- Handle user input directly
- Run tools
- Display results
- Manage connections to external services

### 1.2 AI Application — The Program

**Definition:** The entire engineering framework built **around** the LLM.

**Examples:**
- ChatGPT
- Claude Desktop
- Gemini's web interface

**Key insight:** Users **never interact with the AI directly**. They interact through applications.

### 1.3 Division of Labour

| Responsibility | AI Application (Program) | LLM (Brain) |
|---|---|---|
| Handle user input | ✅ | ❌ |
| Run tools | ✅ | ❌ |
| Display results | ✅ | ❌ |
| Connect to external services | ✅ | ❌ |
| Decide which step to take | ❌ | ✅ |
| Decide which tool to call | ❌ | ✅ |
| Generate final text | ❌ | ✅ |

### 1.4 Why This Distinction Matters

- **MCP connects applications, not models.** (This was the key distinction in the previous file.)
- The application is the layer that "speaks" MCP.
- The LLM only sees what the application **chooses to put in its context**.
- This is the root of the **context problem** discussed later: the application controls what the LLM knows about available tools.

### 1.5 Mental Model

```text
┌─────────────────────────────────────────┐
│ AI APPLICATION (the program)            │
│                                         │
│  - Handles input                        │
│  - Runs tools                           │
│  - Displays results                     │
│  - Speaks MCP                           │
│  - Decides what to put in context       │
│                                         │
│        ┌───────────────────────┐        │
│        │ LLM (the brain)       │        │
│        │                       │        │
│        │ - Reasons             │        │
│        │ - Decides next step   │        │
│        │ - Generates output    │        │
│        └───────────────────────┘        │
└─────────────────────────────────────────┘
```

The LLM is **inside** the application. It does not talk to the outside world directly. The application mediates everything.

---

## 2. MCP Core Concepts: Host and Server

### 2.1 Host

**Technical term:** In MCP terminology, the **AI Application** is called the **Host**.

**Role:** The Host is the client that initiates connections, discovers resources, and decides what to send to the LLM.

**Examples:** Claude Desktop, Cursor, ChatGPT (if MCP-enabled), any MCP-enabled chatbot.

### 2.2 Server

**Technical term:** The **External Service Provider** is called the **Server**.

**Examples:**
- Google Drive
- GitHub
- A local file system
- Slack
- Gmail

**Role:** The Server exposes Tools, Resources, and Prompts to the Host.

### 2.3 MCP Protocol

**Definition:** A **rulebook** that allows the Host to connect **seamlessly and flawlessly** to any Server.

**Key property:** Any MCP-enabled Host can connect to any MCP Server using the same rules. No bespoke integration needed.

### 2.4 Host vs. Server Summary

| Role | Technical term | What it is | Examples |
|---|---|---|---|
| Client | **Host** | The AI Application | Claude Desktop, Cursor |
| Provider | **Server** | The External Service | Google Drive, GitHub, local FS |
| Rulebook | **MCP Protocol** | The agreed-upon rules | The MCP standard |

### 2.5 Architecture Diagram

```text
┌─────────────────────────┐
│ HOST                    │
│ (AI Application)        │
│                         │
│  - Claude Desktop       │
│  - Cursor               │
│  - ChatGPT (MCP)        │
└───────────┬─────────────┘
            │
            │  MCP Protocol
            │  (the rulebook)
            │
   ┌────────┴────────┬─────────────┐
   │                 │             │
   ▼                 ▼             ▼
┌──────────┐   ┌──────────┐   ┌──────────┐
│ SERVER   │   │ SERVER   │   │ SERVER   │
│ Google   │   │ GitHub   │   │ Local    │
│ Drive    │   │          │   │ File     │
│          │   │          │   │ System   │
└──────────┘   └──────────┘   └──────────┘
```

---

## 3. The MCP Connection Workflow

The connection between a Host and a Server happens in **specific steps**, often **automatically**.

### Step 1 — Initiation

**What happens:** When the AI Application starts, it sends an **MCP request** to the server.

**What the request includes:**
- The MCP version it supports
- Operating system details

**Why:** The server needs to know what protocol version to use and what environment it is talking to.

### Step 2 — Handshake

**What happens:** The server responds, and a **connection is established** between the Host and the Server.

**Why:** Both parties confirm they can communicate using the same protocol version.

### Step 3 — Resource Discovery

**What happens:** Once connected, the Application **requests a list** of all available **Tools, Resources, and Prompts** from the server.

**Why:** The Host needs to know what the server can offer before deciding what to expose to the LLM.

### Step 4 — Data Transfer

**What happens:** The server **provides all these elements** to the AI Application.

**What arrives at the Host:**
- Tool definitions (schemas)
- Resource descriptions
- Prompt templates

**Important:** At this stage, these are stored in the **AI Application's "warehouse"**, not yet in the LLM's context.

### 3.1 Workflow Diagram

```text
HOST                                    SERVER
  │                                       │
  │  1. Initiation                        │
  │  (MCP version + OS details)           │
  │ ─────────────────────────────────────▶│
  │                                       │
  │  2. Handshake                         │
  │ ◀─────────────────────────────────────│
  │  (connection established)             │
  │                                       │
  │  3. Resource Discovery                │
  │  (request list of Tools/Resources/    │
  │   Prompts)                            │
  │ ─────────────────────────────────────▶│
  │                                       │
  │  4. Data Transfer                     │
  │ ◀─────────────────────────────────────│
  │  (all Tools, Resources, Prompts)      │
  │                                       │
  ▼                                       │
Host now has the data                   │
in its "warehouse"                      │
```

### 3.2 Key Observation

The workflow is **automatic**. Developers do not manually perform these steps; the MCP client library handles them.

The **critical moment** is Step 4: the Host now has **all** the server's elements in its warehouse. What it does with them next determines whether the system is efficient or bloated.

---

## 4. How MCP Becomes a "Context Problem"

This is the **central insight** of the file.

### 4.1 The Problem of Knowledge

**Initial state:** The tools and resources from the server are stored in the **AI Application's "warehouse"**, not the LLM.

**The gap:** The LLM **cannot make decisions or call tools unless it knows they exist.**

**Why this is a gap:**

| Where the data is | What the LLM knows |
|---|---|
| Host's warehouse | Nothing (unless told) |
| LLM's context window | Everything placed there |

The warehouse is invisible to the LLM. The LLM only sees its context window.

### 4.2 Context Dumping

**What happens:** To solve the knowledge gap, the AI Application **dumps the entire context** into the LLM's context window.

**What gets dumped:**
- Definitions of **all** tools
- Descriptions of **all** resources
- **All** prompt templates

**The reasoning behind it:** "If the LLM might need any tool, it must know about all of them."

**Why it is problematic:** The LLM rarely needs all of them. Most of the dumped context is irrelevant to the current query.

### 4.3 Context Pollution and Dilution

**The scenario:** Even if a user only needs **one specific tool**, the application might dump **60+ tools** and **thousands of tokens** into the context window.

**The result:** **Context Pollution**.

**The mechanism:**

```text
User asks: "Create a draft email"

What the LLM actually needs:
  └─ 1 tool: gmail_create_draft

What the LLM receives:
  ├─ gmail_create_draft
  ├─ gmail_read_email
  ├─ gmail_delete_email
  ├─ gmail_search_emails
  ├─ gmail_list_labels
  ├─ drive_search_files
  ├─ drive_create_folder
  ├─ slack_post_message
  ├─ slack_list_channels
  ├─ github_create_issue
  ├─ github_list_repos
  ├─ ... (50+ more)
  └─ Total: thousands of tokens

The one tool it needs is buried among 60+ it does not.
```

**Consequences:**
- **Wasted tokens** — the LLM processes descriptions it does not need.
- **Higher cost** — input tokens are billed.
- **Higher latency** — larger prompts take longer.
- **Diluted attention** — the relevant tool is harder to find.
- **"Lost in the Middle" risk** — the needed tool may be buried in the middle of a long list.

### 4.4 The Irony

MCP was designed to **solve** the integration problem (glue code, authentication, LLM incompatibility).

But the **current method** of using MCP — dumping everything into the context — creates a **new problem**: context management.

> MCP solves the **connection** problem. It does not automatically solve the **context** problem. That is an engineering responsibility on top of MCP.

---

## 5. Server Elements and Token Consumption

Servers typically offer **three types of entities** that contribute to token usage.

### 5.1 Tools

**Definition:** Executable functions.

**Examples:**
- `Read File`
- `Create Directory`
- `gmail_create_draft`
- `slack_post_message`

**Token impact:** Each tool schema includes name, description, and parameter definitions. Complex tools with many parameters consume more tokens.

### 5.2 Resources

**Definition:** Static data or documents that the AI can read.

**Examples:**
- Version information
- Policies
- Documentation
- Static configuration

**Token impact:** Resource descriptions add tokens. Resources cannot perform actions, but their metadata still enters the context.

### 5.3 Prompts

**Definition:** Pre-defined instruction templates.

**Examples:**
- Templates for common tasks
- Standardized prompts the server recommends

**Token impact:** Prompt templates add tokens, sometimes significant if they are detailed.

### 5.4 The Three Elements at a Glance

| Element | Can perform actions? | What it provides | Token impact |
|---|---|---|---|
| **Tools** | ✅ Yes | Executable functions | Schemas with descriptions and parameters |
| **Resources** | ❌ No | Static data/documents | Descriptions and metadata |
| **Prompts** | ❌ No | Instruction templates | Template text |

### 5.5 Impact on Token Count — Real Numbers

| Server | Approximate tokens |
|---|---|
| GitHub MCP server | **~17,600 tokens** |
| Chrome DevTools MCP server | **~18,000 tokens** |

**What this means:** A single server can consume nearly **18,000 tokens** before the user even asks a question. That is a substantial portion of a typical context window.

### 5.6 Real-World Instance

**Reported by Anthropic:**

> MCP tools occupied approximately **132,000 tokens** out of a **200,000-token** context window.

**What this means:**

| Metric | Value |
|---|---|
| Total context window | 200,000 tokens |
| Consumed by MCP tools | ~132,000 tokens |
| **Percentage consumed** | **~66%** |
| Remaining for actual work | ~68,000 tokens |

**Implications:**
- Two-thirds of the context is gone before any real work begins.
- The remaining space must hold the user query, conversation history, retrieved documents, reasoning, and the final answer.
- The model's effective capacity is drastically reduced.

### 5.7 The Scaling Problem

```text
1 server   → ~17,600 tokens
2 servers  → ~35,200 tokens
3 servers  → ~52,800 tokens
...
8 servers  → ~140,800 tokens  ← approaching the Anthropic case
```

The more servers connected, the worse the problem becomes. And MCP's whole value proposition is connecting to **many** servers.

### 5.8 Visualizing the Anthropic Case

```text
┌──────────────────────────────────────────────┐
│ 200k context window                          │
│                                              │
│ ████████████████████████████████████░░░░░░░░ │
│ │                                │           │
│ │ MCP tools: ~132k (66%)         │ Remaining │
│ │                                │ ~68k (34%)│
│ └────────────────────────────────┘           │
│                                              │
│ The model has only 34% left for:             │
│  - user query                                │
│  - conversation history                      │
│  - retrieved documents                       │
│  - reasoning                                 │
│  - final answer                              │
└──────────────────────────────────────────────┘
```

---

## 6. The Conclusion and the Challenge

### 6.1 What the File Concludes

> While MCP is a **highly efficient protocol** for connecting systems, the **current method of dumping everything into the LLM** creates a **significant context management challenge** for engineers.

### 6.2 The Two Truths

| Truth | Explanation |
|---|---|
| **MCP is efficient** | It solves the integration problem: glue code, authentication, LLM incompatibility |
| **Current usage is inefficient** | Dumping all tools/resources/prompts into context pollutes the window |

These are not contradictory. MCP is a good protocol; the **way it is currently used** needs engineering work.

### 6.3 The Engineering Challenge

Engineers must find ways to:

1. **Know what the LLM needs** for the current query.
2. **Send only that** to the context window.
3. **Keep the rest in the Host's warehouse**, ready to be fetched if needed.

This is exactly the **deferred loading** pattern applied to MCP.

### 6.4 Connecting to Previous Material

| Problem | Technique |
|---|---|
| Too many MCP tool definitions dumped | **Deferred Loading** (Search Tool selects relevant tools) |
| Verbose MCP tool results | **Output Filtering** |
| Multi-step MCP workflows | **Programmatic Tool Calling** |
| Long conversations with MCP | **Summarization (Cure)** |

MCP solves **integration**. These techniques solve **context**.

---

## 7. Key Takeaways

1. **AI (the brain)** = the LLM. **AI Application (the program)** = the framework around it.
2. Users interact with **applications**, never with the LLM directly.
3. The application handles input, runs tools, and displays results; the LLM decides steps.
4. In MCP terminology, the AI Application is the **Host**; the external service is the **Server**.
5. **MCP Protocol** is the rulebook connecting Host to Server.
6. Connection workflow: **Initiation → Handshake → Resource Discovery → Data Transfer**.
7. After discovery, the Host holds all tools/resources/prompts in its **warehouse** — but the LLM knows nothing.
8. To let the LLM decide, the Host **dumps everything** into the context window.
9. This causes **context pollution and dilution**: 60+ tools and thousands of tokens for a query needing one tool.
10. Server elements — **Tools, Resources, Prompts** — all consume tokens.
11. Real numbers: GitHub ~**17,600** tokens; Chrome DevTools ~**18,000** tokens; Anthropic case ~**132k / 200k** (~66%).
12. MCP solves the **integration** problem but creates a **context management** problem.
13. Engineers must apply context optimization techniques (deferred loading, filtering, programmatic calling) **on top of** MCP.

---

## 8. Glossary

| Term | Definition |
|---|---|
| **AI (the brain)** | The Large Language Model (LLM) that reasons and generates output. |
| **AI Application (the program)** | The engineering framework around the LLM that handles input, tools, and output. |
| **Host** | MCP term for the AI Application (the client). |
| **Server** | MCP term for the external service provider. |
| **MCP Protocol** | The rulebook allowing Hosts to connect to Servers. |
| **Initiation** | The Host's initial MCP request with version and OS details. |
| **Handshake** | The server's response establishing the connection. |
| **Resource Discovery** | The Host requesting the list of Tools, Resources, and Prompts. |
| **Data Transfer** | The server sending all elements to the Host. |
| **Warehouse** | The Host's internal storage of tools/resources/prompts, invisible to the LLM. |
| **Context Dumping** | Placing all tool/resource/prompt definitions into the LLM's context window. |
| **Context Pollution** | Unnecessary content crowding the context window. |
| **Context Dilution** | The relevant tool becoming harder to find among many irrelevant ones. |
| **Tools** | Executable functions exposed by a server. |
| **Resources** | Static data/documents exposed by a server; cannot perform actions. |
| **Prompts** | Pre-defined instruction templates exposed by a server. |
| **Context Window** | The maximum text (tokens) an LLM can process at once. |

---

## 9. Self-Test Questions

### AI vs. AI Applications
1. What is the difference between AI (the brain) and an AI Application (the program)?
2. Name three examples of AI Applications.
3. Who handles input, runs tools, and displays results — the LLM or the application?
4. What is the LLM's sole role in the division of labour?
5. Why do users never interact with the LLM directly?

### Host and Server
6. In MCP terminology, what is the Host?
7. In MCP terminology, what is the Server?
8. What is the MCP Protocol?
9. Give three examples of MCP Servers.
10. Give three examples of MCP Hosts.

### Connection Workflow
11. List the four steps of the MCP connection workflow in order.
12. What is included in the initiation request?
13. What happens during the handshake?
14. What does the Host request during resource discovery?
15. What does the server provide during data transfer?
16. Where are the tools/resources/prompts stored after data transfer?
17. Why can't the LLM use them yet at that point?

### Context Problem
18. What is the "problem of knowledge" in MCP?
19. What is context dumping?
20. What is context pollution?
21. Why does context dilution harm reasoning?
22. Give an example of a query needing one tool but receiving 60+.

### Token Consumption
23. What three server elements consume tokens?
24. How many tokens does a GitHub server consume approximately?
25. How many tokens does a Chrome DevTools server consume approximately?
26. What was the Anthropic real-world case, and what percentage did MCP consume?
27. Why does the problem get worse with more servers?

### Conclusion
28. What does MCP solve, and what does it not solve?
29. What is the engineering challenge created by MCP's current usage?
30. Which techniques can help manage MCP context bloat?

### Answer Key
1. AI = the LLM (brain); AI Application = the framework around it (program).
2. ChatGPT, Claude Desktop, Gemini's web interface.
3. The application.
4. Deciding which step to take.
5. Because interaction happens through applications that mediate input, tools, and output.
6. The AI Application (the client).
7. The external service provider.
8. The rulebook connecting Hosts to Servers.
9. Google Drive, GitHub, local file system (also Slack, Gmail).
10. Claude Desktop, Cursor, MCP-enabled ChatGPT/chatbots.
11. Initiation → Handshake → Resource Discovery → Data Transfer.
12. MCP version and OS details.
13. The server responds and the connection is established.
14. A list of all available Tools, Resources, and Prompts.
15. All Tools, Resources, and Prompts.
16. In the Host's "warehouse."
17. Because they have not been placed in the LLM's context window.
18. The LLM cannot decide or call tools unless it knows they exist, but they are stored in the Host, not the LLM.
19. The Host placing all tool/resource/prompt definitions into the LLM's context window.
20. Unnecessary content crowding the context window.
21. The relevant tool becomes harder to find among many irrelevant ones; attention is diluted.
22. "Create a draft email" needs one tool but receives all Gmail/Drive/Slack/GitHub tools.
23. Tools, Resources, Prompts.
24. ~17,600 tokens.
25. ~18,000 tokens.
26. ~132k of 200k tokens, about 66%.
27. Each server adds its own tokens; connecting more servers multiplies the cost.
28. MCP solves integration (glue code, auth, LLM incompatibility); it does not solve context management.
29. Sending only what the LLM needs to the context window while keeping the rest in the Host's warehouse.
30. Deferred Loading, Output Filtering, Programmatic Tool Calling, Summarization.

---

## 10. Mental Model Summary

```text
WHO DOES WHAT:
  Application (Host) ── handles input, tools, output, MCP
  LLM (Brain)        ── decides steps, generates text

MCP CONNECTION:
  Initiation → Handshake → Resource Discovery → Data Transfer
  Result: Host warehouse has all Tools/Resources/Prompts.

THE GAP:
  Warehouse (Host)  ── LLM cannot see it
  Context Window    ── LLM can see only what is placed here

THE MISTAKE:
  Dump everything from warehouse into context.
  → Context pollution
  → Context dilution
  → 60+ tools for a 1-tool query

THE NUMBERS:
  GitHub server        ~17,600 tokens
  Chrome DevTools      ~18,000 tokens
  Anthropic real case  ~132k / 200k (66%)

THE LESSON:
  MCP solves integration.
  MCP does NOT solve context.
  Engineers must apply context optimization on top of MCP.
```

---

*End of incremental notes.*