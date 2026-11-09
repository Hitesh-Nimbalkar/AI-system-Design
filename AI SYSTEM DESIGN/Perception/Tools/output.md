# Solving Tool Output Problems: Detailed Learning Material

## 1. Why Tool Outputs Matter

Large Language Models (LLMs) become significantly more capable when connected to external tools such as:

- APIs
- Databases
- Search engines
- Business applications
- Custom software

These tools allow the model to retrieve real-time information, perform computations, and interact with external systems.

However, every tool interaction consumes part of the model's **limited context window**. Since the context window is finite, inefficient tool usage can:

- Reduce reasoning quality
- Increase latency
- Unnecessarily increase inference cost

This material focuses entirely on the **tool result** problem: why tool outputs become a bottleneck, and how they can be **prevented** or **cured**.

---

## 2. The Three Categories of Tool-Related Context Consumption

Tool-related context consumption can be divided into three categories:

1. **Tool Definitions** — the schemas describing what tools exist and how to call them.
2. **Tool Calls** — the model's requests to invoke a tool, including arguments.
3. **Tool Results** — the outputs returned by the tool and inserted back into the conversation.

Previous discussions focused on reducing the cost of **tool definitions** using deferred loading. This material focuses on **tool results**.

> **Key distinction:** Deferred loading reduces the cost of *describing* tools. Tool output optimization reduces the cost of *using* them.

---

## 3. Understanding the Tool Result Problem

### 3.1 What Happens During a Tool Call

Whenever an LLM invokes a tool:

1. The model emits a tool call (function name + arguments).
2. The tool executes **outside the model**.
3. The tool returns its output.
4. That output is **inserted back into the conversation** so the model can read it and continue reasoning.

This mechanism appears straightforward. But the returned output is often **significantly larger than what the model actually requires**.

### 3.2 Why Tool Outputs Are So Large

Most APIs are designed for **developers**, not for language models. Consequently, they return extensive metadata in addition to the actual business data, including:

- Metadata
- Identifiers
- Timestamps
- Status fields
- Configuration values
- Nested objects
- Debugging information

While this additional information may be useful for software applications, it is usually **irrelevant to the reasoning process of the LLM**.

### 3.3 The Core Mismatch

| API design goal | LLM need |
|---|---|
| Completeness for developers | Only task-relevant facts |
| Rich metadata | Minimal, focused data |
| Debuggability | Reasoning efficiency |
| Full payloads | Small, precise outputs |

The API is optimized for **software integration**. The LLM is optimized for **reasoning over a small context**. These goals conflict.

---

## 4. Why This Becomes a Serious Problem

### 4.1 Context Pollution / Context Bloat

Excessively verbose tool outputs introduce unnecessary tokens into the context window. This phenomenon is commonly referred to as **context pollution** or **context bloat**.

### 4.2 Amplification in Autonomous Agents

The issue becomes especially severe in autonomous AI agents because they may invoke **many tools** while solving a single task.

Each tool contributes additional context. Eventually, the accumulated tool outputs consume a substantial portion of the available token budget.

### 4.3 Consequences

| Consequence | Explanation |
|---|---|
| **Increased cost** | More input tokens → higher API cost |
| **Slower execution** | Larger prompts → more processing time → higher latency |
| **Reduced reasoning quality** | Less context available for reasoning; "Lost in the Middle" risk |
| **Shorter effective conversations** | Context window fills faster, forcing truncation or summarization sooner |

### 4.4 The Agentic Multiplier

In a multi-turn agent:

- Each tool call adds a tool call message **and** a tool result message.
- Dozens of tool calls can accumulate quickly.
- Both tool calls and tool results consume context.

> **Rule of thumb:** The more autonomous the agent, the more expensive each verbose tool output becomes.

---

## 5. Two Ways to Solve Tool Output Problems

There are two broad strategies:

### 5.1 Prevention
**Prevent unnecessary information from entering the context window.**

### 5.2 Cure
**Remove or compress unnecessary information after it has already accumulated.**

### 5.3 Prevention Should Always Be Preferred

> Information that never enters the context window never consumes tokens.

Prevention is cheaper, simpler, and more reliable than cure. Cure is necessary only when prevention is no longer sufficient (e.g., long-running conversations).

### 5.4 Prevention vs Cure Comparison

| Aspect | Prevention | Cure |
|---|---|---|
| When applied | Before output enters context | After output has accumulated |
| Token savings | Maximum (nothing wasted) | Partial (already spent tokens) |
| Complexity | Low to moderate (tool design) | Higher (summarization logic) |
| Risk | Low | Lossy summarization risk |
| Best for | All tools, all the time | Long-running conversations |

---

## 6. Prevention Strategy 1: Design Better Tools

### 6.1 The Principle

The most effective solution is to design every tool so that it returns **only the information required by the language model**.

Instead of forwarding an entire API response, the application should:

1. **Filter** the response.
2. **Extract** only the fields relevant to the current task.

### 6.2 Guiding Principle

> Tools should return only the information that the assistant actually needs to complete the current task.

### 6.3 Example 1 — Weather API

**Raw API response:** Fifty different attributes (temperature, humidity, pressure, wind speed, wind direction, visibility, UV index, sunrise, sunset, timestamps, provider metadata, station IDs, etc.).

**User question:** "What's the weather today?"

**Bad tool output:** The entire fifty-attribute payload.

**Good tool output:**
```json
{
  "temperature": "24°C",
  "condition": "Sunny"
}
```

Only the two values the user asked for.

### 6.4 Example 2 — Currency Conversion Tool

**Raw API response:** Converted amount, timestamps, provider metadata, exchange-rate tables, historical rates, status codes, request IDs.

**User question:** "Convert 100 USD to EUR."

**Bad tool output:** The entire response payload.

**Good tool output:**
```json
{
  "converted_amount": "92.50 EUR"
}
```

Only the converted amount.

### 6.5 Why This Works

- The model does not need metadata to reason.
- The model does not need IDs, timestamps, or status codes unless the task requires them.
- Filtering at the tool boundary is the cheapest possible optimization.

---

## 7. Prevention Strategy 2: Pagination

### 7.1 When Tool Design Is Not the Problem

Sometimes the problem is not caused by poor tool design but by the **size of the underlying dataset**.

### 7.2 Example — Customer Order Database

**Scenario:** A customer-order database contains hundreds of orders.

**User question:** "What was my latest purchase?"

**Bad approach:** Return all historical orders.

**Why it is bad:** The model only needs the latest purchase. Returning hundreds of orders wastes context.

**Good approach:** Return only a small subset — for example, the **most recent ten records**.

Additional pages are fetched **only if the assistant genuinely requires more information**.

### 7.3 Pagination Principle

> Return a small, relevant slice first. Fetch more only when needed.

### 7.4 Pagination Design Considerations

| Consideration | Guidance |
|---|---|
| Page size | Small enough to fit context; large enough to be useful (e.g., 10–50 records) |
| Ordering | Most relevant first (e.g., newest first) |
| Continuation | Provide a cursor or page token so the model can request more |
| Stopping condition | The model should stop fetching once it has enough information |

### 7.5 Pagination vs Full Return

| Approach | Context cost | Latency | Risk |
|---|---|---|---|
| Return all records | Very high | High | Context bloat, truncation |
| Paginate | Low per page | Lower per call | May need multiple calls |

---

## 8. Prevention Strategy 3: Preserve Structured Data

### 8.1 The Problem with Paragraphs

Many tool outputs are naturally tabular, including:

- Weather forecasts
- Stock prices
- Transaction histories
- Analytical reports

Converting structured information into long paragraphs often **increases token usage without adding value**.

### 8.2 Why Structured Formats Are More Efficient

Structured formats eliminate repetitive language while preserving the same information.

Efficient formats include:

- Tables
- CSV files
- Compact JSON representations

### 8.3 Example — Weather Forecast

**Inefficient (paragraph form):**
> "On Monday, the temperature will be 24 degrees Celsius and the condition will be sunny. On Tuesday, the temperature will be 25 degrees Celsius and the condition will be cloudy. On Wednesday, the temperature will be 23 degrees Celsius and the condition will be rainy."

**Efficient (table form):**

| Day | Temp | Condition |
|---|---|---|
| Mon | 24°C | Sunny |
| Tue | 25°C | Cloudy |
| Wed | 23°C | Rainy |

Same information. Far fewer tokens.

### 8.4 Example — Transaction History

**Inefficient:** Repeated sentences for each transaction.

**Efficient (CSV):**
```csv
date,amount,merchant,category
2026-01-01,45.00,Grocery Store,Food
2026-01-02,12.50,Coffee Shop,Food
2026-01-03,89.99,Electronics,Retail
```

### 8.5 Principle

> If the data is naturally structured, keep it structured. Do not convert it into prose.

---

## 9. Cure: Summarizing Conversation History

### 9.1 When Prevention Is Not Enough

Even well-designed tools accumulate context during long-running conversations. Multi-turn agents may execute **dozens of tool calls**, causing both tool calls and tool results to consume a significant portion of the context window.

When prevention is no longer sufficient, the accumulated history should be **compacted**.

### 9.2 The Standard Three-Step Approach

1. **Summarize** older conversation history.
2. **Remove** the original detailed messages.
3. **Replace** them with the summary.

### 9.3 Benefits

- Dramatically reduces token usage.
- Enables longer conversations.
- Keeps the most important context available.

### 9.4 The Critical Caveat: Summarization Is Lossy

Summarization is **inherently lossy**. Important details may be omitted if the summary is poorly generated.

> Summaries must preserve **all facts that are necessary for future reasoning**.

### 9.5 Best Practices for Summarization

| Practice | Why |
|---|---|
| Preserve facts, not wording | Facts are what matter for reasoning |
| Keep decisions and conclusions | Future reasoning depends on them |
| Keep unresolved questions | The agent may need to continue working on them |
| Keep tool results that are still relevant | Avoid losing needed data |
| Drop redundant metadata | It is not needed for reasoning |
| Test summaries against follow-up questions | Verify no critical information was lost |

### 9.6 Summarization Flow

```text
Old conversation (verbose)
        │
        ▼
┌─────────────────────┐
│ Summarize older     │
│ history             │
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│ Remove original     │
│ detailed messages   │
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│ Replace with        │
│ summary             │
└─────────┬───────────┘
          │
          ▼
Compacted conversation (concise)
```

---

## 10. Best Practices

1. **Return only task-relevant fields** from every tool.
2. **Never forward raw API responses** unless absolutely necessary.
3. **Filter metadata** before sending results to the LLM.
4. **Use pagination** for large datasets.
5. **Keep naturally structured data in structured formats** (tables, CSV, compact JSON).
6. **Periodically summarize older conversations** in long-running agents.
7. **Continuously monitor token usage and context growth.**

---

## 11. Key Takeaway

The objective of tool design is **not** to expose every piece of information available from an external system.

The objective is to provide **exactly the information that the language model needs to solve the user's problem**.

Every unnecessary token reduces the space available for reasoning. Therefore, every tool should be designed with **context efficiency as a primary design objective**.

By carefully filtering outputs, using pagination where appropriate, preserving structured data, and summarizing historical conversations, developers can build AI agents that are:

- **Cheaper**
- **Faster**
- **Significantly more effective**

---

## 12. Decision Guide: Prevention vs Cure

```text
Is the tool output larger than needed?
        │
       Yes
        │
        ▼
Can the tool be redesigned to return only relevant fields?
        │
   ┌────┴────┐
  Yes        No
   │          │
   ▼          ▼
Filter    Is the dataset large?
fields         │
          ┌────┴────┐
         Yes        No
          │          │
          ▼          ▼
      Paginate   Is the data naturally structured?
                    │
               ┌────┴────┐
              Yes        No
               │          │
               ▼          ▼
          Keep as     Accept as-is
          table/CSV   (review manually)
               │
               ▼
Is the conversation still growing too large?
        │
       Yes
        │
        ▼
Summarize older history
```

---

## 13. Worked Scenarios

### Scenario 1 — Weather Tool

**Problem:** Weather API returns 50 attributes.

**Prevention:** Filter to `temperature` and `condition`.

**Result:** 50 attributes → 2 fields. Massive token savings.

### Scenario 2 — Order History

**Problem:** Customer has 500 orders; user asks for the latest purchase.

**Prevention:** Paginate. Return the 10 most recent orders.

**Result:** Hundreds of records → 10 records.

### Scenario 3 — Stock Prices

**Problem:** Stock data is returned as long paragraphs.

**Prevention:** Return a compact table (date, price, volume).

**Result:** Prose → table. Fewer tokens, same information.

### Scenario 4 — Long-Running Agent

**Problem:** Agent has made 40 tool calls over a long conversation. Context is nearly full.

**Cure:** Summarize older conversation history, remove detailed messages, replace with summary.

**Result:** Context usage drops; conversation can continue.

**Risk:** Summary may omit important details. Must preserve critical facts.

---

## 14. Glossary

| Term | Definition |
|---|---|
| **Tool** | An external function the LLM can call to perform tasks it cannot do inherently. |
| **Tool Definition** | The schema describing a tool's name, purpose, parameters, and types. |
| **Tool Call** | The LLM's structured request to invoke a tool with specific arguments. |
| **Tool Result** | The output returned by a tool and inserted back into the conversation. |
| **Context Window** | The maximum amount of text (tokens) the model can process at once. |
| **Context Pollution / Bloat** | Unnecessary content crowding the context window and reducing available space for useful information. |
| **Prevention** | Stopping unnecessary information from entering the context window. |
| **Cure** | Removing or compressing unnecessary information after it has accumulated. |
| **Pagination** | Returning a small subset of results and fetching more only when needed. |
| **Structured Data** | Data organized as tables, CSV, or JSON rather than prose. |
| **Summarization** | Compacting conversation history into a shorter form. |
| **Lossy** | Information is lost during compression; the summary may omit details. |
| **Agentic Loop** | Autonomous loop where an AI calls tools multiple times to solve a problem. |
| **Metadata** | Descriptive information about data (IDs, timestamps, status codes) often irrelevant to reasoning. |

---

## 15. Self-Test Questions

### Conceptual
1. What are the three categories of tool-related context consumption?
2. Why are tool outputs often larger than the model needs?
3. What is context pollution / context bloat?
4. Why is prevention preferred over cure?
5. Why does summarization carry risk?

### Prevention
6. What is the guiding principle for designing better tools?
7. Give an example of filtering a weather API response.
8. When is pagination the right solution?
9. Why are tables or CSV more efficient than paragraphs for structured data?
10. What should a currency conversion tool return?

### Cure
11. What are the three steps of conversation summarization?
12. What must a summary preserve?
13. When is cure necessary instead of prevention?

### Scenario-Based
14. A customer-order database has 500 orders. The user asks for the latest purchase. What should the tool return?
15. An agent makes 40 tool calls in one conversation. Context is nearly full. What should you do?
16. A stock price API returns long paragraphs. What is the better format?
17. A weather API returns 50 attributes. The user asks for today's temperature and condition. What should the tool return?
18. A tool returns a full API response with timestamps, request IDs, and status codes. Is this acceptable? Why or why not?

### Design/Trade-Off
19. Compare prevention and cure for tool output problems.
20. What are the risks of aggressive filtering?
21. What are the risks of pagination?
22. What are the risks of summarization?

### Answer Key
1. Tool definitions, tool calls, tool results.
2. Most APIs are designed for developers and return metadata, IDs, timestamps, status fields, configuration values, nested objects, and debugging information.
3. Unnecessary content (e.g., verbose tool outputs) crowding the context window and reducing space for reasoning.
4. Information that never enters the context window never consumes tokens; prevention is cheaper and more reliable.
5. Summarization is lossy; important details may be omitted if the summary is poorly generated.
6. Tools should return only the information the assistant actually needs to complete the current task.
7. Return only `temperature` and `condition` instead of all fifty attributes.
8. When the underlying dataset is large and the model only needs a small subset.
9. They eliminate repetitive language while preserving the same information.
10. Only the converted amount, not timestamps, provider metadata, or exchange-rate tables.
11. Summarize older history, remove original detailed messages, replace with the summary.
12. All facts necessary for future reasoning.
13. When prevention is no longer sufficient, e.g., long-running conversations with many tool calls.
14. Only the most recent records (e.g., the latest ten), not all 500.
15. Summarize older conversation history, remove detailed messages, replace with summary.
16. A compact table (date, price, volume) instead of paragraphs.
17. Only the two relevant values: temperature and condition.
18. No; metadata, IDs, timestamps, and status codes are usually irrelevant to reasoning and waste context.
19. Prevention stops waste before it happens; cure removes waste after it accumulates. Prevention is preferred; cure is a fallback for long conversations.
20. Over-filtering may remove information the model needs later; balance relevance with completeness.
21. The model may need multiple calls to get enough data, increasing latency.
22. Summaries may omit critical facts; must be carefully designed and tested.

---

## 16. Exercises

### Exercise 1 — Redesign a Tool
A flight-search API returns:

- Flight number
- Airline
- Departure time
- Arrival time
- Price
- Aircraft type
- Gate
- Terminal
- Booking class
- Meal options
- Seat map
- Timestamps
- Request ID
- Status code

The user asks: "What's the cheapest flight from Delhi to Mumbai tomorrow?"

**Task:** Design the tool output to return only what is needed.

**Model answer:** Return only `flight_number`, `airline`, `departure_time`, `arrival_time`, and `price` for the cheapest option (or a small paginated list of cheap options).

### Exercise 2 — Pagination Design
A transaction history has 2,000 records. The user asks: "Show my last five transactions."

**Task:** Describe the tool behavior.

**Model answer:** Return the five most recent transactions, with a cursor for fetching more if needed.

### Exercise 3 — Structured Data
A weather forecast for seven days is currently returned as seven paragraphs.

**Task:** Convert it to a structured format.

**Model answer:** A table with columns: Day, Temperature, Condition.

### Exercise 4 — Summarization
An agent has made 30 tool calls. The conversation is near the context limit.

**Task:** Describe the summarization steps and what to preserve.

**Model answer:** Summarize older history, remove detailed messages, replace with summary. Preserve key facts, decisions, unresolved questions, and still-relevant tool results.

---

*End of learning material.*