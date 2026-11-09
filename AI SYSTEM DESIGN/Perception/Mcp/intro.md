# Incremental Notes: Limitations of Traditional Tool Calling & Model Context Protocol (MCP)

## 1. The Limitations of Traditional Tool Calling

### 1.1 When Traditional Tool Calling Works

Tool calling is **effective** for:

- Customized or simple tasks
- Calculating totals from bills
- Generating blog articles based on web searches

These are cases where the tool set is small, the workflow is simple, and the developer controls the integration.

### 1.2 When Traditional Tool Calling Breaks Down

Using traditional tool calling to connect AI applications to **external services** (Gmail, Google Drive, Slack, Notion) presents **three major challenges**.

---

### Challenge 1 — Requirement for Customized Functions

**The problem:** For every action in an external service — **reading, writing, deleting, searching** — a developer must write a **specific, additional function**.

**The consequence:** A massive amount of **"glue code"** that is difficult to manage.

**Example:**

| Action | Custom function needed |
|---|---|
| Read an email | `gmail_read_email()` |
| Write a draft | `gmail_create_draft()` |
| Delete an email | `gmail_delete_email()` |
| Search emails | `gmail_search_emails()` |

Every service × every action = a new function. With multiple services, this grows exponentially.

**Why it is bad:**
- Code duplication
- Maintenance burden
- Hard to keep consistent across services
- Easy to introduce bugs

---

### Challenge 2 — Authentication Issues

**The problem:** If an external service like Gmail **changes its authentication method**, all existing custom functions may **break**.

**The consequence:** You must **rewrite all tools** to follow the new method. During that time, the **AI application remains down**.

**Why it is bad:**
- Downtime for users
- Emergency engineering work
- Risk of introducing new bugs during the rewrite
- No graceful degradation

**Key insight:** Authentication is controlled by the **service provider**, not by you. You cannot prevent them from changing it.

---

### Challenge 3 — LLM Incompatibility

**The problem:** Different LLMs — OpenAI, Anthropic, Ollama — have **different formats** for accepting tools.

**The consequence:** Changing the LLM in an application often requires **manually rewriting all tools** to match the new model's schema.

**Example:**

| Provider | Parameter format |
|---|---|
| Anthropic | `input_schema` |
| Ollama | `parameters` |
| OpenAI | `function.parameters` (similar but not identical) |

**Why it is bad:**
- Vendor lock-in
- Expensive migrations
- Slows down experimentation
- Prevents easy model switching

---

### 1.3 Summary: The Root Cause

The core issue behind all three problems is the **lack of a standard protocol or rulebook** for connecting AI applications to external services.

Each integration is bespoke:

```text
AI app ──custom glue──▶ Gmail
AI app ──custom glue──▶ Slack
AI app ──custom glue──▶ Drive
AI app ──custom glue──▶ Notion
```

This does not scale.

---

## 2. Understanding Model Context Protocol (MCP)

### 2.1 What Is a Protocol?

**Definition:** A protocol is an **agreed-upon set of rules for communication** between two parties.

**Analogies from the transcript:**

| Analogy | How it maps to MCP |
|---|---|
| **Traffic rules** allow police and drivers to communicate | A shared rulebook lets two parties interact predictably |
| **MOU (Memorandum of Understanding)** facilitates business partnerships | A formal agreement that defines how parties work together |

**Key property of a protocol:** Both parties must follow the **same rules** for communication to work.

---

### 2.2 What Is MCP?

**Definition:** MCP is an **open standard** that provides a **common language** for AI applications to connect with external tools and data sources.

**Key properties:**
- **Open standard** — not proprietary
- **Common language** — one format for all integrations
- **Connects AI applications to services** — not the model directly

---

### 2.3 The Bridge Analogy

MCP acts as a **bridge** between:

- An **AI application** on one side
- An **external service provider** on the other side

**What the bridge enables:** Seamless connection **without custom integrations** for every tool or model.

```text
Without MCP:

AI app ──custom glue──▶ Gmail
AI app ──custom glue──▶ Slack
AI app ──custom glue──▶ Drive

With MCP:

AI app ──MCP──▶ Gmail MCP Server
       ──MCP──▶ Slack MCP Server
       ──MCP──▶ Drive MCP Server
```

Every connection uses the **same protocol**.

---

### 2.4 Key Distinction: Application vs. Model

> **MCP is a protocol designed to connect AI applications (like Claude Desktop or Cursor) to services, rather than connecting the AI model (the LLM itself) directly.**

| What MCP connects | What MCP does NOT connect |
|---|---|
| AI **applications** (Claude Desktop, Cursor, chatbots) | The **LLM** directly |
| External **service providers** (Gmail, Slack, Drive) | Raw model APIs |

**Why this matters:** MCP sits at the **application layer**, not the model layer. The model still sees tools in its own format; the application translates via MCP.

---

## 3. MCP Architecture: The Two Parties

The implementation of MCP involves **two main participants**.

---

### 3.1 Party 1 — AI Applications

**Introduced by:** Anthropic, then **open-sourced**.

**Adoption:** Major AI providers have adopted it.

**What "MCP-enabled" means:** The application **"speaks" the MCP language**.

**Examples:**
- Claude Desktop
- Claude Code
- Cursor
- Various AI chatbots

**Role:** The AI application is the **client** that connects to MCP servers and uses the tools/resources/prompts they expose.

---

### 3.2 Party 2 — External Service Providers (MCP Servers)

External services like **Google Drive, Slack, and Gmail** create **MCP Servers**.

**Definition:** An MCP server is a **repository** that exposes specific elements to the AI application.

**What an MCP server exposes:**

| Element | Description | Example |
|---|---|---|
| **Tools** | Executable functions that allow the AI to **perform actions** | `create_draft` in Gmail; `search_files` in Drive |
| **Resources** | Textual data or static information about the service | Versioning info, policies |
| **Prompts** | Pre-defined prompts that can be used by the application | Template prompts for common tasks |

**Key distinction:** **Resources cannot perform actions.** They provide information. Only **tools** can perform actions.

---

### 3.3 Architecture Diagram

```text
┌─────────────────────────┐
│ AI Application          │
│ (MCP-enabled client)    │
│                         │
│ - Claude Desktop        │
│ - Claude Code           │
│ - Cursor                │
│ - AI chatbots           │
└───────────┬─────────────┘
            │
            │  MCP Protocol
            │  (common language)
            │
   ┌────────┴────────┬─────────────┐
   │                 │             │
   ▼                 ▼             ▼
┌──────────┐   ┌──────────┐   ┌──────────┐
│ Gmail    │   │ Slack    │   │ Drive    │
│ MCP      │   │ MCP      │   │ MCP      │
│ Server   │   │ Server   │   │ Server   │
│          │   │          │   │          │
│ Tools    │   │ Tools    │   │ Tools    │
│ Resources│   │ Resources│   │ Resources│
│ Prompts  │   │ Prompts  │   │ Prompts  │
└──────────┘   └──────────┘   └──────────┘
```

---

## 4. Benefits of Using MCP

### 4.1 Seamless Integration

**What it means:** AI applications and external services can **communicate effortlessly** because they follow the **same rulebook**.

**Why it matters:** No bespoke glue code for each integration.

---

### 4.2 Reduced Development Workload

**What it means:** Developers **no longer need to manually write or manage complex tool code** for every task.

**How:** They can simply **connect to an existing MCP server** and use the tools provided by the service.

**Example:** Use Gmail's **pre-built `create_draft` tool** instead of writing your own.

**Contrast:**

| Without MCP | With MCP |
|---|---|
| Write `gmail_create_draft()` yourself | Connect to Gmail MCP server, use its `create_draft` |
| Write `slack_post_message()` yourself | Connect to Slack MCP server |
| Maintain all glue code | Provider maintains the server |

---

### 4.3 Consistency

**What it means:** Because the **service provider** (Google, Slack) maintains the server, the tools **remain updated** even if authentication methods change.

**Why it matters:** Solves **Challenge 2** (Authentication Issues) from Section 1.

**Who bears the maintenance burden:** The **service provider**, not the AI application developer.

**Contrast:**

| Without MCP | With MCP |
|---|---|
| You rewrite tools when Gmail changes auth | Gmail updates its MCP server; you just reconnect |
| Your app may be down during rewrite | Provider handles updates; less downtime for you |

---

### 4.4 Benefits Mapped to Challenges

| Original Challenge | How MCP Solves It |
|---|---|
| **Customized functions** (glue code) | Provider exposes tools via MCP server; no per-action glue code |
| **Authentication issues** | Provider maintains the server; you reconnect instead of rewriting |
| **LLM incompatibility** | MCP is a common language; the protocol abstracts provider-specific schemas |

---

## 5. MCP vs. Traditional Tool Calling: Comparison

| Aspect | Traditional Tool Calling | MCP |
|---|---|---|
| Integration style | Bespoke per service | Standardized protocol |
| Glue code | Massive | Minimal (connect to server) |
| Authentication changes | You rewrite all tools | Provider updates server |
| LLM switching | Rewrite all tools | MCP abstracts the format |
| Who maintains tools | You | Service provider |
| Scalability | Poor (grows with services × actions) | Good (one protocol for all) |
| Best for | Custom, simple tasks | Connecting to external services |

---

## 6. Next Step (Preview from the Transcript)

> While MCP solves many integration issues, the next lecture will examine how it can **become a problem for the context window** and how to manage that effectively.

**Why this matters:** MCP servers can expose **many tools, resources, and prompts**. If all of them are loaded into the context, you get the **same context bloat problems** discussed in earlier material (tool definition bloat, deferred loading, etc.).

**Connecting the dots:**

| Problem | Technique |
|---|---|
| Too many MCP tools exposed | **Deferred Loading** (search tool to select relevant tools) |
| Verbose MCP tool results | **Output Filtering** |
| Multi-step MCP workflows | **Programmatic Tool Calling** |

MCP solves the **integration** problem. It does not automatically solve the **context** problem. That is the next layer.

---

## 7. Key Takeaways

1. Traditional Tool Calling works for **simple, customized tasks** but breaks down for **external service integrations**.
2. Three challenges: **customized functions (glue code)**, **authentication issues**, and **LLM incompatibility**.
3. The root cause is the **lack of a standard protocol**.
4. **MCP** is an **open standard** that provides a **common language** for AI applications to connect with external services.
5. MCP acts as a **bridge** between AI applications and service providers.
6. MCP connects **AI applications**, not the **LLM directly**.
7. MCP has **two parties:** AI applications (clients) and MCP servers (service providers).
8. MCP servers expose **Tools** (actions), **Resources** (information), and **Prompts** (templates).
9. **Resources cannot perform actions**; only tools can.
10. Benefits: **seamless integration, reduced development workload, consistency**.
11. MCP is **open-sourced** and adopted by major AI providers.
12. MCP solves the **integration** problem, but the **context window** problem remains — that is the next topic.

---

## 8. Glossary

| Term | Definition |
|---|---|
| **Tool Calling** | The process where an LLM requests the system to execute a specific external function with arguments. |
| **Glue Code** | Custom code written to connect two systems; often brittle and hard to maintain. |
| **Authentication** | The process of verifying identity and permissions when accessing an external service. |
| **Protocol** | An agreed-upon set of rules for communication between two parties. |
| **MCP (Model Context Protocol)** | An open standard providing a common language for AI applications to connect with external tools and data sources. |
| **MCP Server** | A repository created by a service provider that exposes tools, resources, and prompts to MCP-enabled AI applications. |
| **MCP-Enabled** | An AI application that "speaks" the MCP protocol. |
| **Tools (in MCP)** | Executable functions that allow the AI to perform actions. |
| **Resources (in MCP)** | Textual data or static information about the service; cannot perform actions. |
| **Prompts (in MCP)** | Pre-defined prompts that can be used by the application. |
| **Client (MCP)** | The AI application that connects to MCP servers. |
| **LLM Incompatibility** | The problem that different LLMs accept tools in different formats. |

---

## 9. Self-Test Questions

### Traditional Tool Calling Limitations
1. What are the three major challenges of traditional tool calling for external services?
2. What is "glue code," and why is it a problem?
3. Why do authentication changes break custom tools?
4. Give an example of LLM incompatibility in tool schemas.
5. What is the root cause behind all three challenges?

### MCP Fundamentals
6. What is a protocol?
7. What is MCP?
8. What is the bridge analogy for MCP?
9. What does MCP connect — the AI application or the LLM directly?
10. Who introduced MCP, and what happened to it?

### MCP Architecture
11. What are the two parties in MCP architecture?
12. What does an MCP server expose? Name the three elements.
13. What is the difference between a tool and a resource in MCP?
14. Name three examples of MCP-enabled AI applications.
15. Name three examples of services that create MCP servers.

### Benefits
16. How does MCP reduce development workload?
17. How does MCP provide consistency when authentication changes?
18. Map each of the three original challenges to how MCP solves it.

### Connections
19. Why does MCP not automatically solve the context window problem?
20. Which techniques from earlier material could help manage MCP context bloat?

### Answer Key
1. Customized functions (glue code), authentication issues, LLM incompatibility.
2. Custom code connecting systems; it is hard to manage and grows with every service × action.
3. Because the service changes its auth method, and your tools were written for the old method.
4. Anthropic uses `input_schema`; Ollama uses `parameters`.
5. The lack of a standard protocol for connecting AI applications to external services.
6. An agreed-upon set of rules for communication between two parties.
7. An open standard providing a common language for AI applications to connect with external tools and data sources.
8. MCP acts as a bridge between an AI application and an external service provider.
9. The AI application, not the LLM directly.
10. Introduced by Anthropic, then open-sourced and adopted by major AI providers.
11. AI applications (clients) and external service providers (MCP servers).
12. Tools, resources, and prompts.
13. Tools perform actions; resources provide information and cannot perform actions.
14. Claude Desktop, Claude Code, Cursor, various AI chatbots.
15. Google Drive, Slack, Gmail.
16. Developers connect to existing MCP servers and use provider-built tools instead of writing glue code.
17. The service provider maintains the server, so tools remain updated; developers reconnect instead of rewriting.
18. Glue code → provider exposes tools; auth changes → provider updates server; LLM incompatibility → MCP is a common language.
19. Because MCP servers can expose many tools/resources/prompts, which can bloat the context window.
20. Deferred Loading, Output Filtering, Programmatic Tool Calling.

---

## 10. Mental Model Summary

```text
BEFORE MCP:
  Every AI app ↔ service integration is bespoke.
  N services × M actions = N×M custom functions.
  Auth change → rewrite everything.
  LLM change → rewrite everything.

WITH MCP:
  AI apps speak MCP.
  Service providers expose MCP servers.
  MCP servers expose tools, resources, prompts.
  Auth change → provider updates server.
  LLM change → MCP abstracts the format.
  Integration problem solved.

REMAINING PROBLEM:
  MCP servers can expose many tools.
  Many tools = context bloat.
  → Next topic: managing MCP context.
```

---

*End of incremental notes.*