# Deferred Loading for Tool Calling: Detailed Learning Material

## 1. The Problem: Traditional Tool Calling Is Wasteful

### 1.1 Why Tools Exist

LLMs cannot inherently:

- Check a company database
- Retrieve customer information
- Check whether a product is in stock
- Generate a live sales report
- Send an email
- Book a flight

To provide these capabilities, developers create **external functions called tools**. Using **Tool Calling**, these tools become available to the LLM when required.

> **Simple definition:** Tools are used whenever we want the LLM to perform tasks it cannot perform inherently.

### 1.2 How Traditional Tool Calling Works

Whenever an LLM is called with tools, the model must first understand **what tools are available**. It does this by reading the **tool definitions (schemas)**.

**The core problem:** Every tool definition becomes part of the **prompt**. Therefore, every time the LLM is called, **all tool definitions are processed**, even if most of them are never used.

### 1.3 Example

Suppose an application has these tools:

- Inventory Tool
- Finance Tool
- Budget Tool
- Sales Report Tool
- Customer Tool
- Order Tracking Tool

User asks:

> "Is the Acer Aspire laptop currently in stock?"

Only the **Inventory Tool** is required. But the traditional approach still sends **every tool definition** to the LLM. This unnecessarily consumes the context window.

### 1.4 Problems Caused by Traditional Tool Calling

| Problem | Explanation |
|---|---|
| **1. Larger Context Window** | Every tool definition consumes valuable tokens. |
| **2. Higher API Cost** | More input tokens increase the cost of using LLM APIs. |
| **3. Increased Latency** | Larger prompts require more processing time. |
| **4. Wasted Processing** | The LLM processes many irrelevant tool definitions. |
| **5. Context Pollution** | Less context remains for conversation history, memory, retrieved documents, and reasoning. |

---

## 2. The Solution: Deferred Loading

### 2.1 Definition

**Deferred Loading** is a performance optimisation technique in which **non-critical resources are loaded only when they are actually needed**, instead of loading everything upfront.

In software engineering, this idea is commonly used to load images, videos, scripts, or other resources only when required.

**Applied to Tool Calling:**
> Deferred Loading is the technique of loading **only the tool definitions required for the current user query** instead of loading every available tool.

### 2.2 The Search Tool

Deferred Loading introduces another function called the **Search Tool**.

- It acts like a **search engine for tools**.
- Just as Google searches billions of web pages and returns only relevant pages, the **Search Tool searches all available tools** and returns only those relevant to the user's request.

**Instead of sending every tool definition to the LLM:**
1. First identify the relevant tools.
2. Then send **only those tools** to the LLM.

---

## 3. Complete Workflow

### 3.1 Step-by-Step

1. **Create a Search Tool** that searches through all available tools.
2. **Create the schema for the Search Tool.**  
   The LLM understands functions only through their schemas.
3. **Call the LLM** with the user query and **only the Search Tool schema**.
4. If the LLM determines that an external tool is required, it generates a **tool call for the Search Tool** and provides the required parameter values.
5. **The application executes the Search Tool** using those parameters.
6. **The Search Tool returns the most relevant tool(s).**
7. **Call the LLM a second time** using the original user query together with **only the returned tool definitions**.
8. The LLM now generates the **appropriate tool call**.
9. The application executes the selected tool and returns the tool result.
10. The LLM uses the tool result to generate the **final response**.

### 3.2 Workflow Diagram

```text
User query
    │
    ▼
┌─────────────────────────────┐
│ Call LLM with:              │
│ - user query                │
│ - Search Tool schema only   │
└─────────────┬───────────────┘
              │
              ▼
   Does LLM need a tool?
      │               │
     No              Yes
      │               │
      ▼               ▼
 Final answer   LLM calls Search Tool
                  (with parameters)
                        │
                        ▼
              Application executes
              Search Tool
                        │
                        ▼
              Search Tool returns
              relevant tool(s)
                        │
                        ▼
┌─────────────────────────────┐
│ Call LLM again with:        │
│ - original user query       │
│ - only relevant tool defs   │
└─────────────┬───────────────┘
              │
              ▼
     LLM generates tool call
              │
              ▼
     Application executes tool
              │
              ▼
     Tool result returned to LLM
              │
              ▼
     LLM generates final answer
```

### 3.3 Worked Example

**User query:** "Is the Acer Aspire laptop currently in stock?"

**Available tools:** Inventory, Finance, Budget, Sales Report, Customer, Order Tracking.

**Traditional approach:**
- Send all 6 tool definitions to the LLM.
- LLM reads all 6, selects Inventory Tool, generates a tool call.

**Deferred Loading approach:**
1. Send only the Search Tool schema to the LLM.
2. LLM calls Search Tool with query: "Acer Aspire laptop stock".
3. Search Tool returns only the Inventory Tool definition.
4. Send the original query + Inventory Tool definition to the LLM.
5. LLM generates a tool call for Inventory Tool.
6. Application executes Inventory Tool, returns result.
7. LLM generates final answer.

**Savings:** The LLM never processes the Finance, Budget, Sales Report, Customer, or Order Tracking tool definitions for this query.

---

## 4. Advantages of Deferred Loading

- Reduces context window usage.
- Reduces input token consumption.
- Lowers API costs.
- Improves response speed.
- Leaves more context available for memory, RAG, and conversation history.
- Scales well for applications with **hundreds or thousands of tools**.

---

## 5. Limitations

Deferred Loading is **not always the best choice**.

### 5.1 When It May Not Be Worth It

If your application contains only a **small number of tools (around 5–6)**:

- Introducing Deferred Loading **increases implementation complexity**:
  - You need to maintain an additional **Search Tool**.
  - You need to perform an **extra LLM call**.
- The savings in tokens and cost are usually **very small** and may not justify the added complexity.

### 5.2 Conclusion

> Deferred Loading is most beneficial for applications containing a **large number of tools**.

---

## 6. Key Takeaways

1. **Tool Calling** extends the capabilities of an LLM.
2. **Traditional Tool Calling** sends every tool definition with every request.
3. This **wastes context window space, tokens, time, and money**.
4. **Deferred Loading** solves this by loading only the required tool definitions.
5. A **Search Tool** identifies the relevant tools based on the user's query.
6. Deferred Loading is recommended mainly for applications with **many tools**.

---

## 7. Glossary

| Term | Definition |
|---|---|
| **Tool** | An external function that gives the LLM capabilities it lacks inherently. |
| **Tool Calling** | The process where the LLM requests the system to execute a specific tool with specific arguments. |
| **Tool Definition / Schema** | The description of a tool, including name, purpose, parameters, and data types. |
| **Context Window** | The maximum amount of text (tokens) an LLM can process at once. |
| **Context Pollution** | Unnecessary content crowding the context window and reducing available space for useful information. |
| **Deferred Loading** | Loading only the resources needed for the current task, instead of loading everything upfront. |
| **Search Tool** | A special tool that searches all available tools and returns only the relevant ones for a given query. |
| **Token** | A unit of text that LLMs process; more tokens = higher cost and latency. |
| **Latency** | The time delay before a response is received. |
| **RAG** | Retrieval-Augmented Generation; using retrieved documents to ground LLM responses. |

---

## 8. Self-Test Questions

### Conceptual
1. What is the core problem that Deferred Loading solves?
2. What is a tool, and why do LLMs need them?
3. What is a Search Tool, and what analogy is used to describe it?
4. Why does traditional Tool Calling waste tokens?
5. What are the five problems caused by traditional Tool Calling?

### Workflow
6. List the steps of the Deferred Loading workflow in order.
7. In the typical case where a tool is needed, how many times is the LLM called?
8. What is sent to the LLM in the first call?
9. What is sent to the LLM in the second call?
10. Who executes the Search Tool and the selected tool — the LLM or the application?

### Trade-offs
11. What are the advantages of Deferred Loading?
12. When is Deferred Loading **not** recommended, and why?
13. For how many tools does Deferred Loading start to become beneficial?
14. What extra complexity does Deferred Loading introduce?

### Scenario
15. An app has 6 tools. Should you use Deferred Loading? Why or why not?
16. An app has 500 tools. Should you use Deferred Loading? Why?
17. User asks "Is the Acer Aspire laptop in stock?" with 6 tools available. Which tool is relevant? What would traditional Tool Calling send? What would Deferred Loading send?

### Answer Key
1. Traditional Tool Calling sends all tool definitions on every call, wasting tokens, cost, latency, and context.
2. A tool is an external function (e.g., Python function) that lets the LLM perform tasks it cannot do inherently.
3. A Search Tool searches all available tools and returns only relevant ones; analogy: Google searches billions of pages and returns relevant results.
4. Every tool definition becomes part of the prompt; all are processed even if unused.
5. Larger context window, higher API cost, increased latency, wasted processing, context pollution.
6. (1) Create Search Tool, (2) create its schema, (3) call LLM with user query + Search Tool schema only, (4) LLM generates tool call for Search Tool, (5) app executes Search Tool, (6) Search Tool returns relevant tool(s), (7) call LLM again with original query + only returned tool definitions, (8) LLM generates appropriate tool call, (9) app executes selected tool, (10) LLM uses tool result to generate final response.
7. Two times (first with Search Tool schema, second with relevant tool definitions).
8. The user query and only the Search Tool schema.
9. The original user query and only the relevant tool definitions returned by the Search Tool.
10. The application executes both the Search Tool and the selected tool. The LLM only requests calls.
11. Reduces context usage, reduces input tokens, lowers API costs, improves response speed, leaves more context for memory/RAG/history, scales to hundreds/thousands of tools.
12. Not recommended for small numbers of tools (~5–6) because added complexity outweighs small savings.
13. Most beneficial for applications with a large number of tools (hundreds or thousands).
14. Maintaining an additional Search Tool and performing an extra LLM call.
15. No; with only 6 tools, savings are small and added complexity is not justified.
16. Yes; with 500 tools, sending all definitions would be extremely wasteful; Deferred Loading scales well.
17. Relevant tool: Inventory Tool. Traditional: sends all 6 tool definitions. Deferred Loading: first sends only Search Tool schema; then sends only Inventory Tool definition after Search Tool returns it.

---

*End of learning material.*