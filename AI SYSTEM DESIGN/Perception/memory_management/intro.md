# Very Detailed Incremental Notes: Memory in GenAI — Why It Matters and How It Works

> **Source:** Hindi transcript, "Introduction: Why Memory Matters in GenAI" (Nitesh, AI system design channel)
> **Scope:** Foundational, framework-agnostic treatment of memory for LLM applications.
> **Teaching style:** First-principles — the transcript builds memory "as if inventing it from scratch."

---

## 0. Video Framing and Promise

### 0.1 The Speaker's Setup

- Topic: **Memory** in Generative AI.
- Claim: **Memory is one of those things without which no GenAI application can function.**
- Examples given: chatbots, agents — none work without memory.
- The video is designed as a **single, deep, foundational pass** over memory.

### 0.2 Design Choices of the Video

| Choice | What it means |
|---|---|
| **Framework-agnostic** | Not tied to a single library (LangChain, LlamaIndex, etc.) |
| **First-principles** | Builds memory "as if inventing it" |
| **Story-like** | Progressive problem → solution → new problem → new solution |
| **End goal** | Deep understanding so you can implement memory in any GenAI app |

### 0.3 The Narrative Arc (Preview)

```text
LLM is stateless
   → but GenAI apps need memory
   → so we build memory externally
   → short-term memory (conversation buffer)
   → short-term memory has 3 limitations
   → we need long-term memory
   → long-term memory has 3 types
   → long-term memory works in 4 steps
   → building it is hard → libraries emerge
   → future: LLMs with intrinsic memory
```

---

## 1. How LLMs Work at Inference — The Mathematical Foundation

### 1.1 The Core Statement

> **"An LLM at inference is just a parameterized math function."**

Represented as:

```text
y = f(x; θ)
```

Where:

| Symbol | Meaning |
|---|---|
| **y** | Output tokens |
| **x** | Input tokens (the prompt) |
| **θ (theta)** | The model's parameters (billions of values) |
| **f** | A very complex mathematical function |

### 1.2 What Is a Parameterized Math Function?

**Definition (from the transcript):** A function whose output depends **not only on its input** but **also on additional parameters**.

**Simple example:**

```text
y = a·x²
```

To compute `y`, you need:
- `x` — provided by the user
- `a` — a parameter, provided from elsewhere (e.g., learned from data)

### 1.3 Concrete Example: Linear Regression

**Setup:** You have data points and want to find the **best-fit line**.

**Known form of the line:**

```text
y = mx + b
```

Where:

| Symbol | Role | Where the value comes from |
|---|---|---|
| **x** | Input | User |
| **m** | Slope (parameter) | Learned from data |
| **b** | Intercept (parameter) | Learned from data |

**Key insight:** The parameters `m` and `b` are **not given by the user**. They are **learned from data during training**.

### 1.4 Extending to LLMs

**LLM is also a machine learning / deep learning model.** So the same setup applies:

```text
y = f(x; θ)
```

| Component | In linear regression | In an LLM |
|---|---|---|
| Parameters | `m`, `b` (2 values) | **Billions of values** |
| Where they come from | Learned from data | Learned from training data |
| Who provides them at inference | Nobody — fixed | Nobody — fixed |
| Who provides input `x` | User | User (the prompt) |

**Hence the naming:** "70 billion parameter model," "100 billion parameter model" — these refer to the size of θ.

### 1.5 The Three Components of the Inference Equation

| Component | Symbol | Meaning | Who controls it at inference |
|---|---|---|---|
| Parameters | **θ** | Billions of learned values | **Fixed** — nobody changes them |
| Input | **x** | Input tokens / prompt | **User** — fully changeable |
| Output | **y** | Output tokens | Determined by θ and x |

### 1.6 The Crucial Observation

> **y depends on both θ and x. But θ is fixed at inference. The user can only change x.**

**This is why changing the prompt changes the output** — you are changing `x`, and the model recomputes `y`.

### 1.7 Why This Mathematical View Matters

- It is the **foundation** for everything that follows.
- It explains why the model cannot "remember" anything on its own.
- It shows that memory must be implemented **outside** the model — in `x`.

---

## 2. The Stateless Property — LLMs Have No Intrinsic Memory

### 2.1 Definition of Stateless

> **"A system is stateless if its output depends only on the current input and not on anything that has happened before."**

### 2.2 Applying It to the LLM

**Sequence of calls:**

```text
Call 1:  x1  +  θ  →  y1
Call 2:  x2  +  θ  →  y2
Call 3:  x3  +  θ  →  y3
```

**Key observation:**

> **y2 depends only on x2 and θ. It does NOT depend on x1 or y1.**

This is what it means to be stateless.

### 2.3 Practical Demonstration from the Transcript

**Code sketch:**

```python
# Call 1
x1 = "My name is Nitesh"
y1 = llm.invoke(x1)
# Output: "Nice to meet you, Nitesh"

# Call 2 (new, independent call)
x2 = "What is my name?"
y2 = llm.invoke(x2)
# Output: "I'm sorry, I do not know your name."
```

**What this proves:**

| Observation | Meaning |
|---|---|
| The LLM answered y1 correctly | It processed x1 |
| The LLM did **not** know the name in Call 2 | It did **not** remember x1 or y1 |
| Each call is independent | The system is **stateless** |

### 2.4 The "Very Important Realization"

> **Every next function call is unique. It is independent. It is not related to the previous call.**

This is the moment the transcript asks the viewer to **internalize**:

> **LLMs at inference are stateless by nature.**

### 2.5 Two Things Learned So Far

1. **How to represent an LLM at inference mathematically** — `y = f(x; θ)`.
2. **That equation is stateless by nature** — output depends only on current input and fixed parameters.

### 2.6 The Fact We Can Now Establish

> **If LLMs are stateless at inference, then LLMs have no intrinsic memory.**

As simple as that.

---

## 3. The Core Problem — A Deadlock

### 3.1 Fact 1: LLMs Have No Memory

- They cannot remember past conversations.
- They have no built-in mechanism for state.
- Every call is fresh.

### 3.2 Fact 2: Every GenAI Application Needs Memory

The transcript states:

> **"Hardly any GenAI application in the world exists that does not need memory."**

**Concrete failure case — a chatbot without memory:**

| User experience | Problem |
|---|---|
| Must re-explain everything every time | Frustrating |
| No continuity | Feels broken |
| Personalization impossible | Generic responses |
| Cannot reference previous context | Repeated questions |

**The verdict:** A memoryless chat application is **"highly frustrating"** and **"not possible to build"** as a usable product.

### 3.3 Why a Memoryless Chatbot Fails Technically

**Architecture of a memoryless chatbot:**

```text
User message 1 (x1) → LLM → y1
User message 2 (x2) → LLM → y2   (x1, y1 NOT included)
User message 3 (x3) → LLM → y3   (x1, y1, x2, y2 NOT included)
```

**Result:** Every message is treated as a **brand-new conversation**. The chatbot has no idea what was discussed before.

### 3.4 The Deadlock

```text
LLMs have no memory
        +
GenAI apps cannot function without memory
        =
We are stuck.
```

> **"Essentially we are in a deadlock. We are stuck."**

### 3.5 Fact 3: Memory Must Be Built Externally

**The logical conclusion:**

> **If LLMs don't have their own memory, but we need memory, then we must develop the memory feature externally.**

**What this means architecturally:**

- Keep the **LLM at the center**.
- Build a **system around it** that acts like memory.
- The LLM itself stays stateless; the **surrounding system provides state**.

**Analogy (not from transcript, but helpful):** The LLM is like a brilliant consultant with amnesia. You don't cure the amnesia; you hand them a detailed briefing folder before every meeting.

---

## 4. The First-Principles Approach to Building Memory

### 4.1 The Plan

> **"We will invent a system that gives LLMs the power of memory."**

**Method:** Build it **as if inventing memory for the first time**.

**Shift in focus:**

| Before | Now |
|---|---|
| **Why** memory is needed | **What** memory is and **how** to build it |

### 4.2 Two Concepts to Understand First

Before building the solution, the transcript says you must understand:

1. **Context Window**
2. **In-Context Learning**

These two concepts are the **building blocks** of the first memory solution.

---

## 5. Concept 1 — The Context Window

### 5.1 The Question That Introduces It

> Recall the equation `y = f(x; θ)`, where `x` is the input tokens.
> **How many tokens can you send in `x`? Is there a limit?**

**Answer:** Yes — the **context window**.

### 5.2 Definition

> **"The context window is the amount of text an LLM can read and remember at one time before answering."**

**In other words:** The maximum text the LLM can process, read, and hold before generating its answer.

### 5.3 The Camera Analogy

| Camera part | LLM equivalent |
|---|---|
| **Camera** | The LLM |
| **Lens** | The context window |

**Explanation:**

- A **small lens** captures only a small portion of the scene.
- A **large lens** captures a much larger portion.
- Similarly:
  - A **small context window** lets the LLM "see" only a small amount of text.
  - A **large context window** lets the LLM "see" much more.

### 5.4 Real Numbers from the Transcript

| Model class | Context window |
|---|---|
| Modern LLMs | **~128k tokens** or more |
| Gemini models | **~1 million tokens** |

**Practical equivalence:**

> **A 128k-token context window can hold roughly a 200-page PDF.**

### 5.5 Why This Matters for Memory

> **"The fact that we can send a lot of tokens in the input is a very, very important power that will help us in the future."**

**Translation:** The large context window is the **raw material** for building the first memory solution.

### 5.6 The Connection to Memory

```text
If x can hold many tokens,
and we can put past conversation into x,
then the LLM can "see" the past.
→ That is the seed of memory.
```

---

## 6. Concept 2 — In-Context Learning

### 6.1 What Happens During Training

| Step | What happens |
|---|---|
| 1 | Huge amounts of data (basically the entire internet) are provided |
| 2 | The LLM searches for **patterns** in the data |
| 3 | It **gathers knowledge** |
| 4 | That knowledge is **stored in the parameters** |

**Terminology:** This stored knowledge is called **parametric knowledge**.

### 6.2 What Happens During Inference (Default Mode)

- You send a prompt.
- The prompt effectively **searches the parametric knowledge**.
- If the answer is there, the answer is returned.

### 6.3 The Emergent Phenomenon

> As LLMs grew larger (in size, training data), people observed something **emergent**:

> **LLMs don't only use their parametric knowledge. Sometimes they can also use details hidden inside the prompt itself to answer the question.**

### 6.4 The PDF Example

**Setup:**

- You have a **100-page PDF** of **private company data**.
- The LLM has **never seen** this data.
- You put the entire PDF into the prompt.
- You also ask a question **from that PDF**.

**Why this is interesting:**

- The answer is **not** in the LLM's parametric knowledge.
- The LLM has never been trained on this private data.

**What the LLM can do:**

- It **reads the 100-page PDF**.
- It **answers the question** using information from the PDF.

**This is in-context learning.**

### 6.5 Definition

> **"In-context learning is an emergent ability that allows an LLM to use information and patterns present in the prompt itself, in addition to its trained parametric knowledge, to generate an answer."**

### 6.6 Default Mode vs. In-Context Mode

| Mode | Source of answer | When it applies |
|---|---|---|
| **Default (parametric)** | The model's learned knowledge | Question is answerable from training |
| **In-context** | Information inside the prompt | Question needs prompt-specific info |

### 6.7 Why This Matters for Memory

> **If the LLM can use information inside the prompt, then we can put past conversation into the prompt, and the LLM will use it.**

This is the **second building block** for the first memory solution.

---

## 7. Short-Term Memory — The First Solution

### 7.1 The Two Building Blocks

| Concept | What it contributes to the solution |
|---|---|
| **Context window** | Enough space to hold the past conversation |
| **In-context learning** | The LLM can use that past conversation to answer |

### 7.2 The Solution

> **When invoking the LLM, concatenate the entire conversation so far and send it as `x`.**

### 7.3 The Equation Change

**Before (stateless):**

```text
Call 1: y1 = f(x1; θ)
Call 2: y2 = f(x2; θ)       ← only x2
```

**After (with conversation history):**

```text
Call 1: y1 = f(x1; θ)
Call 2: y2 = f(x1 · y1 · x2; θ)    ← entire history concatenated
```

Where `·` means concatenation.

### 7.4 The Walkthrough

**Step 1 — First user message:**

- No conversation exists yet.
- Send `x1` directly.
- Get `y1`.

**Step 2 — Second user message:**

- Do **not** send `x2` alone.
- Instead, send `x1`, `y1`, and `x2` together.
- Get `y2`.

**Step 3 — Third user message:**

- Send `x1`, `y1`, `x2`, `y2`, and `x3`.
- Get `y3`.

**In general:**

```text
y_n = f(x1, y1, x2, y2, ..., x_n; θ)
```

### 7.5 Why This Works — Both Concepts Apply

| Concept | How it applies |
|---|---|
| **Context window** | Large enough to hold `x1`, `y1`, `x2` without issue |
| **In-context learning** | The LLM reads `x1` and `y1`, and uses them to answer `x2` |

### 7.6 The Name-Example Walkthrough

**Setup:**

- `x1` = "My name is Nitesh"
- `y1` = "Nice to meet you, Nitesh"
- `x2` = "What is my name?"

**Traditional (stateless) call:**

```text
y2 = f(x2; θ)    → "I don't know your name"
```

**Memory-based call:**

```text
y2 = f(x1, y1, x2; θ)    → "Your name is Nitesh"
```

**Why it works:**

- The LLM's parametric knowledge has **no idea** who the user is.
- But the **context** contains `x1` ("My name is Nitesh").
- The LLM **reads** the context and answers correctly.

### 7.7 The Key Insight

> **"We are not telling the LLM to remember anything. We are simply providing continuity in its context window by passing the entire conversation at every point in time."**

The LLM stays stateless. **The system provides the continuity.**

---

## 8. Implementing Short-Term Memory in Code

### 8.1 The `messages` Variable

**Structure:**

```python
messages = []
```

**Step 1 — Add first user message:**

```python
messages.append("My name is Nitesh")   # x1
response = llm.invoke(messages)        # y1
# Output: "Nice to meet you, Nitesh"
```

**Step 2 — Append the model's response:**

```python
messages.append(response)              # y1
```

**Step 3 — Add next user message:**

```python
messages.append("What is my name?")    # x2
response = llm.invoke(messages)        # y2
# Output: "Your name is Nitesh"
```

### 8.2 What the `messages` Variable Contains

| Step | Contents of `messages` |
|---|---|
| After step 1 | `[x1]` |
| After step 2 | `[x1, y1]` |
| After step 3 | `[x1, y1, x2]` |

### 8.3 The Stateful Transformation

| Before | After |
|---|---|
| The system was **stateless** | The system has **become stateful** |
| Each call was independent | Each call includes history |
| No memory | `messages` acts as memory |

> **"Because of this `messages` variable, it has become stateful. Because this `messages` is acting as the state."**

### 8.4 Alternative Terminology

> **The `messages` variable is also called the **conversation buffer**.**

**Why:** It dynamically loads the entire conversation history.

### 8.5 The Important Caveat — Temporary Memory

> **"This memory is also temporary."**

**Demonstration:**

- If you **restart the file**, the `messages` variable resets.
- The LLM will **refuse to recognize you** again.
- Because the messages are gone.

**Hence the name:** **Short-term memory**.

### 8.6 The Formal Definition

> **Short-term memory = a conversation buffer that holds the current conversation's history and is passed to the LLM on every call.**

**In the transcript's words:**

> **"This is nothing but a conversation buffer."**

---

## 9. How Chatbots Implement Short-Term Memory

### 9.1 The Concept of a Conversation

**Definition from transcript:**

> **"One session with the chatbot."**

**Examples:**

- Open ChatGPT → discuss a topic → close → that is **one conversation**.
- Next day → open ChatGPT → discuss something else → close → that is a **second conversation**.

**In ChatGPT's UI:** All conversations are listed in the sidebar.

### 9.2 The Key Principle

> **"Short-term memory is conversation-scoped."**

**In other words:**

| Inside a conversation | Outside a conversation |
|---|---|
| Short-term memory exists | Short-term memory does **not** exist |
| History is tracked | History is lost |

**Every conversation has its own short-term memory.**

### 9.3 How It Works Mechanically

**Within a conversation:**

- The `messages` variable accumulates only **this conversation's** messages.

**Switching to a new conversation:**

- The `messages` variable is **emptied**.
- The new conversation's messages begin accumulating.

**Switching back to the old conversation:**

- The old `messages` are **restored** (if persisted — see Section 10).

### 9.4 Why Each Conversation Gets Its Own Short-Term Memory

> **"You would not want a single short-term memory for your entire chatbot."**

**The scenario that illustrates the problem:**

- Suppose you have **1,000 conversations** with ChatGPT.
- Suppose you use a **single `messages` variable** to hold all 1,000 conversations.

**Two problems arise:**

| Problem | Explanation |
|---|---|
| **Too long** | The `messages` variable becomes enormous |
| **Incoherent** | The LLM cannot answer correctly when the context mixes many unrelated conversations |

### 9.5 The Logical Boundary

> **"You create a logical boundary. One conversation is one boundary, and within it, short-term memory exists."**

**What this achieves:**

- Inside this conversation, the LLM knows what is happening.
- Other conversations are **irrelevant** to this one.

### 9.6 Terminology — "Thread"

**In many places, a conversation is called a **thread**.**

| Term | Meaning |
|---|---|
| **Thread** | A conversation |
| **Thread-scoped** | Restricted to one conversation |

**Therefore, in many places you will read:**

> **"Short-term memory is thread-scoped."**

**Meaning:** The scope of a short-term memory is a **single thread**. Outside a thread, short-term memory does not exist.

### 9.7 Summary of This Section

Two things established:

1. **What short-term memory is** — a conversation buffer.
2. **How it is implemented** — scoped within a conversation (thread).

---

## 10. Limitations of Short-Term Memory — Three Problems

### 10.1 Problem 1: Fragility

**The setup:**

- Short-term memory is implemented as a `messages` variable in code.
- All conversation history is stored in that variable.

**The problem:**

> **If the code resets, or the server crashes, everything in the `messages` variable is lost.**

**What this means:**

- The entire conversation context **disappears**.
- The user's history is **gone**.

### 10.2 The New-Chat Scenario (Illustrating Fragility)

**Step 1 — Ongoing conversation:**

- User is chatting in a conversation.
- Every new message is added to `messages`.

**Step 2 — User starts a new chat:**

- User clicks "New Chat."
- The window goes blank.
- The `messages` from the previous conversation are **removed**.

**Step 3 — New conversation accumulates:**

- User sends messages in the new chat.
- The new `messages` variable fills up.

**Step 4 — User returns to the old chat:**

- User clicks back on the previous conversation.
- **What displays?** **Nothing.**
- Why? Because the previous conversation was **never stored anywhere**.
- It was completely removed from memory.

**Step 5 — User types in the old chat:**

- The LLM treats the message as **brand new**.
- The old context is **not retained**.

> **"This is the biggest problem."**

### 10.3 The Solution to Fragility: Persistence

> **"The solution is very simple: use persistence."**

**What it means:**

> **Connect a database to the short-term memory.**

### 10.4 How Persistence Works — Step by Step

**Step 1 — Create a thread ID:**

- Example: `thread_id = 1`.

**Step 2 — When leaving a conversation:**

- Before switching away, **save** all messages in `messages` to the database.
- Store them **against `thread_id = 1`**.

**Step 3 — Start a new conversation:**

- A new `messages` variable is populated for the new chat.
- A new `thread_id` (e.g., `thread_id = 2`) is created.

**Step 4 — Before leaving the new conversation:**

- Save those messages against `thread_id = 2`.

**Step 5 — Return to the old conversation:**

- **Load** the messages stored against `thread_id = 1` from the database.
- Populate `messages` with them.

**Step 6 — Continue chatting:**

- The next question operates **in continuity**.
- The LLM understands the previous context and answers accordingly.

### 10.5 Persistence Flow Diagram

```text
Conversation 1
  ├── messages = [x1, y1, x2, y2, ...]
  └── thread_id = 1
        │
        ▼
  Save to database against thread_id = 1
        │
        ▼
Conversation 2
  ├── messages = [x1', y1', x2', ...]   (new)
  └── thread_id = 2
        │
        ▼
  Save to database against thread_id = 2
        │
        ▼
Return to Conversation 1
  ├── Load messages for thread_id = 1
  ├── Populate messages
  └── Continue chatting with continuity
```

### 10.6 The Transcript's Reference to LangGraph

> The speaker notes that this persistence pattern was already demonstrated in his **LangGraph playlist**.

### 10.7 Problem 2: The Context Window Problem

**Recap:** The context window is the **maximum number of tokens** an LLM can process while generating an answer.

**The scenario:**

- A conversation grows very long.
- Many messages are exchanged.
- The LLM sends long responses.
- The user keeps asking new questions.

**What happens over time:**

- The `messages` list becomes **very large**.
- On **every** LLM call, the **entire** conversation history is attached.

**The critical threshold:**

> **If the total token size exceeds the LLM's context window, the LLM suddenly stops understanding things.**

### 10.8 Symptoms of Context Window Overflow

| Symptom | Description |
|---|---|
| **Incoherent replies** | The model produces nonsense |
| **Hallucination** | The model invents information |
| **Loss of comprehension** | The model fails to understand the conversation |

### 10.9 The Basic Problem Statement

> **You have a long-running chat, and you are repeatedly sending the entire conversation history to the LLM. But it has accumulated to become very large.**

### 10.10 The Solution — Two Techniques Merged

The transcript says the widely used solution **merges two approaches**:

1. **Trimming**
2. **Summarization**

### 10.11 Trimming

**What it is:**

> **Decide to send only the most recent `n` messages to the LLM.**

**Example from transcript:**

- Instead of sending the entire conversation (which has 500 messages), send only the **last 50 messages**.
- Rationale: the most recent context is in those 50 messages. Older 450 messages add no value.

**Visualization:**

```text
Before trimming:
  [m1, m2, m3, ..., m448, m449, m450, m451, ..., m500]

After trimming (last 50 only):
  [m451, m452, ..., m500]
```

### 10.12 The Problem with Trimming Alone

> **Since you removed all previous messages, you might miss some important context or information.**

**The risk:** The summary might omit facts needed for future reasoning.

### 10.13 The Improvement — Summarization

**The approach:**

> **Send the messages being removed to another LLM and generate a summary.**

**How it works:**

1. Take the old messages being trimmed out.
2. Summarize them with a second LLM.
3. Attach the summary **on top of** the recent messages.

### 10.14 The Combined Solution

```text
Final context =
  Summary of old messages
  + Last 50 recent messages
```

**Why this works:**

- The summary is **much smaller** than the 450 messages it replaces.
- The total token count **automatically stays within the limit**.
- The LLM gives **coherent responses** again.

### 10.15 Example Summary from Transcript

**Summary shown:** "Discussed project X, task Y, deadline Z, and feature W."

**Key observation:** The summary captures **facts**, not the full wording.

### 10.16 Why This Is the Widely Accepted Solution

> **"This is the most widely accepted solution for this problem."**

**The trade-off:**

| Benefit | Cost |
|---|---|
| Fits context window | Lossy — details may be lost |
| Preserves key facts | Requires a second LLM call |
| Enables long conversations | Summary quality matters |

### 10.17 Problem 3: Thread-Scoped Memory (The Most Critical Problem)

**Recap:** Short-term memory is **thread-scoped**.

- Each conversation/thread has its own short-term memory.
- Switching conversations makes the current short-term memory **disappear**.
- The new conversation adapts to the new short-term memory.

### 10.18 Why Thread-Scoping Is Both a Feature and a Bug

**It is a feature because:**

> **It lets us continue conversations. Without it, conversations would blur together.**

**It is a bug because:**

> **It creates negative impacts.**

### 10.19 The Three Negative Impacts

The transcript discusses **three pointers**.

#### Pointer 1 — No Continuity Between Conversations

**What it means:**

- Any user preference is **not retained** across conversations.
- Each conversation starts fresh.

**The Python vs. Java example:**

| Conversation | What happened | What the LLM did |
|---|---|---|
| **Conversation 1** | User started studying an algorithm | LLM gave all code in **Java** |
| **Same conversation** | User explicitly said: "I don't know Java. Give me Python." | LLM then consistently gave **Python** |
| **Conversation 2 (2 days later)** | User started a new conversation about a different programming topic | LLM again gave **JavaScript / Java / C++** — **forgot** the Python preference |

**The conclusion:**

> **Since short-term memory only remembers things within a single conversation, it cannot remember user preferences by definition. It cannot personalize.**

#### Pointer 2 — Learning Never Compounds Over Time

**What it means:**

- Whatever effort you put into teaching the LLM is **lost at the next conversation**.
- You must re-teach from scratch every time.

**The SQL example:**

| Conversation | What happened | What the LLM did |
|---|---|---|
| **Conversation 1** | User asked for a top-5 customer query | LLM gave a **subquery** — working but **unoptimized** |
| **Same conversation** | User asked for an **optimized** query using a **window function** | LLM gave the optimized window-function version |
| **Conversation 2 (2 days later, different dataset)** | User asked a similar query | LLM again gave the **subquery** version |
| **Result** | The LLM **never adopted** the user's optimization preference | The user must **re-teach every time** |

**The verdict:**

> **Its learning never evolves with me. It falls behind, and I have to hand-hold it from the start every time.**

#### Pointer 3 — Cross-Thread Reasoning Is Impossible

**What it means:**

> **You can never ask the LLM: "What did we talk about yesterday?" or "Last time we hit this kind of problem, what was the solution?"**

**Why it is impossible:**

- The past conversation is in a different thread.
- Short-term memory is thread-scoped.
- When you are in a different conversation, the past conversation is **forgotten**.

**The verdict:**

> **As soon as I start a new conversation with my LLM, I become a stranger to it again. This is the biggest problem.**

### 10.20 The Personal Assistant Paradox

**The scenario:**

> **"If I want to build a personal assistant for my user, the biggest quality of a personal assistant is that it understands its user inside and out."**

**What a personal assistant should know about the user:**

| Preference | How it is learned |
|---|---|
| Likes Python | From one conversation |
| Is a software developer | From another conversation |
| Likes simple explanations | From another conversation |
| Likes to travel | From another conversation |

**What the personal assistant needs:**

> **Small facts from many different conversations, combined into a personalized user profile.**

**Why short-term memory cannot deliver this:**

> **Because short-term memory is locked inside a single conversation.**

**The verdict:**

> **"This personalization is by definition not possible with short-term memory. And this is the biggest drawback of short-term memory."**

### 10.21 Summary of Short-Term Memory's Three Limitations

| # | Limitation | Core issue | Solution direction |
|---|---|---|---|
| 1 | **Fragility** | Resets/crashes lose memory | Persistence (database + thread ID) |
| 2 | **Context window overflow** | Long conversations exceed token limit | Trimming + summarization |
| 3 | **Thread-scoped** | No cross-conversation memory | **Long-term memory (the big one)** |

---

## 11. Why We Need Long-Term Memory

### 11.1 The Conclusion

> **"We need a completely new type of memory. Short-term memory cannot solve this problem."**

### 11.2 The Two Required Properties

| # | Property | What it means |
|---|---|---|
| 1 | **Store special information for a long time** | Information that survives beyond a single conversation/session |
| 2 | **Be very, very selective** | Do not blindly store everything; extract only the important parts |

### 11.3 Property 1 — Long-Lasting Special Information

**What "special information" means:**

> **Information that can survive beyond a single conversation, beyond a single session, and can remain useful for many days.**

**The book-writing example:**

| Element | Details |
|---|---|
| **Scenario** | You are writing a book |
| **Interaction** | You will chat with the chatbot many times during the process |
| **Lifespan of information** | As long as the book is not complete — could be **months** |
| **Requirement** | The memory must store this information across all that time |

### 11.4 What Kind of Information Is Stored

The transcript lists several categories.

#### Category 1 — User Identity

> **"Identify who the user is."**

**Examples (for a user named Nitesh):**

| Fact | Relevance |
|---|---|
| Male | Long-term identity |
| Indian | Long-term identity |
| YouTuber | Long-term identity |
| Teacher | Long-term identity |
| Teaches AI | Long-term identity |

**Why:** These are facts about the user that will be important across multiple days.

#### Category 2 — System Behavior Preferences

> **"How the chatbot/assistant will behave according to our user."**

**Examples:**

- Tone of voice
- Level of detail
- Formatting preferences
- Interaction style

#### Category 3 — What Works and What Fails

> **"What things work for our user? What things fail?"**

**Examples:**

- Which solutions the user accepted
- Which solutions the user rejected
- Which approaches succeeded
- Which approaches failed

#### Category 4 — Past Decisions and Work

> **"What kind of decisions were made in the past? What kind of work was done? What was the output? What processes were implemented?"**

**Examples:**

- Past architectural decisions
- Past implementations
- Past outputs
- Past processes

### 11.5 Property 2 — Selectivity

> **"This new memory has to be very, very selective."**

**What it means:**

> **We will not blindly store the entire conversation in this memory.**

**The selection criteria:**

| Criterion | Description |
|---|---|
| **Stable** | The information is not going to change soon |
| **Useful** | It actually helps future reasoning |
| **Reusable** | It can be applied across many future conversations |

**What to do with everything else:**

> **"Everything else, we will ignore."**

### 11.6 The Definition of Long-Term Memory

> **A memory that:**
> - **Exists outside a single conversation**
> - **Persists for a long period of time**
> - **Stores only stable, useful, reusable information**

**Hence the name "long-term memory."**

### 11.7 The Contrast

| Aspect | Short-term memory | Long-term memory |
|---|---|---|
| Lifetime | One conversation | Across conversations, days/months |
| Scope | Thread-scoped | User/system-level |
| Content | All messages | Selected important facts |
| Selectivity | Stores everything | Stores only stable/useful/reusable |
| Fragility | Fragile | Designed for persistence |
| Size | Grows unboundedly | Curated |

---

## 12. Types of Long-Term Memory — Three Categories

### 12.1 Overview

> **"Precisely, there are three different types of long-term memory."**

| # | Type | Core question it answers |
|---|---|---|
| 1 | **Episodic memory** | *What happened in the past?* |
| 2 | **Semantic memory** | *What is true about the user and system?* |
| 3 | **Procedural memory** | *How to do things for this user and system?* |

### 12.2 Episodic Memory

**Definition:**

> **"Episodic memory simply tells you what happened in the past."**

**Purpose:**

> **Knowing this improves the current conversation.**

**Examples of what is stored:**

| Example | Why it matters |
|---|---|
| Last session, user rejected a particular solution | Avoid suggesting it again |
| The deployment failed because credentials were wrong | Avoid the same mistake |
| A particular solution worked | Reuse it |
| A particular solution didn't work | Avoid it |

**Benefit:**

> **It lets you answer questions like:**
> - "What did we do last time?"
> - "What approach did we use last time?"
> - "Has this happened before?"
> - "Have we already used this technique?"

**The effect:**

> **The agent can act better in the current conversation because it knows the history.**

### 12.3 Semantic Memory

**The transcript's assessment:**

> **"This is the most common and most important type of long-term memory."**

**What it is built from:**

> **Facts.**

**What facts:**

> **Facts about the user and the system.**

**Examples:**

| Fact type | Example |
|---|---|
| User preference | "User prefers Python" |
| User skill level | "User is a beginner in software" |
| System fact | "We are using PostgreSQL" |
| Task constraint | "Budget constraint is ₹10,000 for ticket booking" |

**What this memory stores:**

> **"What is true about the system and the user."**

**Level:**

> **User-level or system-level memory.**

### 12.4 Procedural Memory

**Definition:**

> **"This tells you how to do things."**

**What is stored:**

| Element | Example |
|---|---|
| **Strategies** | Preferred approach for a type of task |
| **Rules** | "If tool X fails, always try tool Y" |
| **Learned behaviors** | "Always explain step-by-step to this user" |
| **Preferred workflows** | "Preferred workflow for task Z is ..." |

**Examples from the transcript:**

- The user wants to avoid subqueries when solving SQL problems.
- If tool X fails, always try tool Y.
- Always explain things step-by-step to the current user.
- Preferred workflow for task Z is [some specific flow].

**Why this memory exists:**

> **Because it tells the LLM: "Which way of working is the right one?"**

**The transcript's insight:**

> **"This is the memory that makes an agent feel better over time. You start to feel comfortable with it, or you adapt to it."**

### 12.5 The Three Types at a Glance

| Type | Stores | Answers | Example |
|---|---|---|---|
| **Episodic** | Past events | "What happened?" | "Last time we used approach A, and it worked." |
| **Semantic** | Facts | "What is true?" | "User prefers Python; we use PostgreSQL." |
| **Procedural** | How-to knowledge | "How should I work?" | "Avoid subqueries; explain step-by-step." |

### 12.6 Combined Summary

> **In total, you store these three types of memory in long-term memory:**
> - **Episodic** — past events
> - **Semantic** — facts
> - **Procedural** — how to do things for a particular user and system

---

## 13. How Long-Term Memory Works — The Four-Step Architecture

### 13.1 The Four Steps

| # | Step | Purpose |
|---|---|---|
| 1 | **Creation** (or Update) | Extract memory candidates from the conversation |
| 2 | **Storage** | Save them durably with metadata |
| 3 | **Retrieval** | Select relevant memories for the current query |
| 4 | **Injection** | Place selected memories into the context window |

### 13.2 Step 1 — Creation / Update

**When it happens:** **During** a conversation, while the user is interacting with the chatbot.

**The architect's job:**

> **Understand which pieces of this conversation could become part of long-term memory.**

**The main goal:**

> **"You have to find out if there is anything that has just happened worth remembering beyond this conversation."**

**The guiding question:**

> **"Is anything in this conversation something that should survive beyond this conversation?"**

### 13.3 What You Check

| Source | What you look for |
|---|---|
| **User messages** | Preferences, facts, requests |
| **Model responses** | Confirmed answers, decisions |
| **Tool outputs** (if tool-based/agentic) | Data, results, errors |

### 13.4 The Four Sub-Steps Within Creation

#### Sub-step 1 — Extract Memory Candidates

**What you do:**

> **Extract memory candidates from the messages being exchanged.**

**Example from transcript:**

> **During chat, the user says: "I prefer Python over Java."**
> **This is now a **memory candidate**.**

#### Sub-step 2 — Filter Out Noise

**What you do:**

> **Remove the noise. Extract the **core fact** or **core information**.**

**Why:** Messages contain a lot of noise. Only the core fact should go into long-term memory.

#### Sub-step 3 — Decide the Scope

**What you do:**

> **Decide whether the memory is:**
> - **User-level**
> - **App-level**
> - **Agent-level**

**This is called tagging.**

#### Sub-step 4 — Decide the Action

**Three possible decisions:**

| Decision | When |
|---|---|
| **Create a new memory** | The fact is new |
| **Update an existing memory** | The fact refines or replaces an existing one |
| **Ignore** | The candidate fails the stability/usefulness/reusability test |

### 13.5 Creation Flow Diagram

```text
Conversation in progress
        │
        ▼
Extract memory candidates
        │
        ▼
Filter out noise → extract core fact
        │
        ▼
Decide scope (user / app / agent)
        │
        ▼
Decide action:
   ├── Create new
   ├── Update existing
   └── Ignore
```

### 13.6 Step 2 — Storage

**When it happens:** After Step 1 decides a memory should be stored.

**Why store:**

> **"You have to reuse it in the future. You cannot lose it."**

**Two functions performed in storage:**

| Function | Description |
|---|---|
| **Save durably** | Write the memory to a durable store |
| **Tag with identifiers and metadata** | So future retrieval is easy |

**The main purpose:**

> **"You want this particular piece of memory to survive any risks or crashes."**

### 13.7 Storage Options by Memory Type

| Storage type | When it is used |
|---|---|
| **Relational database** | Structured facts, strong consistency |
| **Key-value store** | Simple lookups, speed |
| **Logs / text files** | Append-only records, audits |
| **Vector database** | Semantic search over memory contents |

**The transcript's key point:**

> **"Different options depending on what type of memory you are storing."**

**Specifically:**

- Episodic memory → different store
- Procedural memory → different store
- Semantic memory → different store

### 13.8 Step 3 — Retrieval

**When it happens:** When the user starts a **new conversation** or sends a **new query**.

**What happens:**

> **"As the user chats, before the model replies, it thinks: Do I need any type of memory to answer this particular question?"**

**The entire focus:**

> **"Given the current situation, what should I remember right now?"**

### 13.9 What Happens in Retrieval

| Sub-step | Description |
|---|---|
| 1 | Look at the **current user input** |
| 2 | **Decide** whether memory is needed |
| 3 | If needed, **search** the memory store |
| 4 | **Extract a small relevant subset** from the memory store |

### 13.10 The Key Property — Retrieval Is Selective

> **"You do not take everything in the memory store. You perform a search and bring relevant pieces of information from the memory store."**

**The transcript's explicit statement:**

> **"Retrieval is selective, not exhaustive. You do not take everything like short-term memory. You do selective search."**

### 13.11 Contrast with Short-Term Memory

| Aspect | Short-term memory | Long-term memory retrieval |
|---|---|---|
| Behavior | **Exhaustive** — sends everything | **Selective** — sends only relevant pieces |
| Basis | Entire conversation buffer | Search based on current query |
| Cost | Grows with conversation length | Bounded by relevance |

### 13.12 Step 4 — Injection

**The transcript's most emphasized point:**

> **"Very, very important thing to always remember: You never let long-term memory interact directly with the LLM."**

### 13.13 How Injection Works

**The sequence:**

1. **Search** long-term memory.
2. **Get** relevant information.
3. **Pull** that information into **short-term memory**.
4. Short-term memory becomes part of the **context window**.
5. The **context window** reaches the LLM.

**In other words:**

> **Long-term memory first becomes part of short-term memory. It becomes part of the conversation buffer.**

### 13.14 The Prompt-Building View

> **"The user wrote a prompt. Additional things are added by the system, and then the entire thing is sent to the model."**

**So injection is:**

> **Retrieving memory and putting it into short-term memory. It becomes part of the prompt.**

**The model sees it as:**

> **"Just more tokens. Input tokens."**

### 13.15 The Four-Step Flow Diagram

```text
DURING CONVERSATION
  User + LLM exchange messages
        │
        ▼
  STEP 1 — CREATION / UPDATE
  Extract candidates → filter noise → tag scope → decide action
        │
        ▼
  STEP 2 — STORAGE
  Save durably with identifiers and metadata
        │
        ▼
NEW QUERY ARRIVES
        │
        ▼
  STEP 3 — RETRIEVAL
  Analyze query → decide if memory needed → search → extract small subset
        │
        ▼
  STEP 4 — INJECTION
  Pull memory into short-term memory → becomes part of context → reaches LLM
```

### 13.16 Framework-Agnostic Note

> **"This is a high-level overview, which is kind of framework-agnostic. In different libraries, you will see different implementations."**

**The core insight:** The **four steps** are universal, even if the implementation differs.

---

## 14. Challenges in Building Memory Systems

### 14.1 The Three Challenges

| # | Challenge | Where it arises |
|---|---|---|
| 1 | **Memory creation** | Deciding what to remember |
| 2 | **Real-time retrieval** | Selecting the right memories per query |
| 3 | **Orchestration** | Integrating memory into an already-complex system |

### 14.2 Challenge 1 — Memory Creation

**The core difficulty:**

> **"Figuring out which things to convert into memory and which not. This is itself a very difficult task."**

**Why it is hard:**

| Sub-challenge | Explanation |
|---|---|
| **Noise in normal chat** | Users chat casually; most of it is not memorable |
| **Stability judgment** | "Will this thing last long, or not?" |
| **Context dependence** | The same statement may or may not be worth remembering depending on context |

**The verdict:**

> **"Memory creation in itself is a very, very challenging task."**

### 14.3 Challenge 2 — Real-Time Retrieval

**The core difficulty:**

> **"Even if you created memory and stored it properly, how do you figure out, in real time during a conversation, which pieces from the entire long-term memory to extract and bring back so that it helps the current conversation?"**

**Why it is hard:**

| Sub-challenge | Explanation |
|---|---|
| **Selectivity** | Must pick only the relevant subset |
| **Relevance judgment** | Must judge relevance **on the fly** |
| **Latency** | Must do it fast enough to feel responsive |

**The verdict:**

> **"This is itself a very challenging task."**

### 14.4 Challenge 3 — Orchestration

**The core difficulty:**

> **"You are already building a very complex system — an agentic AI system, an agent, a chatbot. Building this entire memory system on top of it becomes a very challenging task."**

**Why it is hard:**

| Sub-challenge | Explanation |
|---|---|
| **Many moving parts** | Memory store, retrieval, injection, prompt building |
| **Engineering complexity** | Connecting memory stores to your system |
| **Coordination** | Ensuring each piece works with the others |

**The verdict:**

> **"You need to put a lot of thought into it. The engineering side is also very difficult."**

---

## 15. Tools and Libraries for Memory Systems

### 15.1 The Market Shift

> **"Recently, some new libraries have come into the market. Some new managed solutions have come in."**

### 15.2 What These Tools Promise

> **"You focus on building your application. Leave the tension of integrating the entire long-term memory system to us."**

**What they handle:**

| Function | Description |
|---|---|
| **Creating memory** | Extract and decide what to store |
| **Storing memory** | Manage the memory store |
| **Retrieving at the right time** | Query memory relevantly |

> **"You simply call our functions."**

### 15.3 Specific Libraries Mentioned

| Library | Notes from Transcript |
|---|---|
| **LangMem** | From the LangChain family; integrates easily with LangGraph for building AI agents |
| **MemZero** | Recently very popular; same purpose — memory layer for GenAI apps |
| **SuperMemory** | Founder is a **15-year-old Indian kid**; manages long-term memory for GenAI apps |

### 15.4 The Trend

> **"These managed solutions are entering the market, and their funding is also going very well."**

**The prediction:**

> **"This particular field — memory around LLMs — will grow rapidly in the next one to two years."**

---

## 16. The Future of Memory in LLMs

### 16.1 The Root Observation

> **"All of these problems are arising because LLMs do not have their own default memory. They do not have their own intrinsic memory."**

### 16.2 The Research Direction

> **"Now, gradually, research is also going on in this direction: building LLMs that have their own memory."**

### 16.3 The Google Paper

| Detail | Value |
|---|---|
| Paper name | **Titans + Mirage** (per transcript) |
| Goal | Build a different kind of transformer architecture |
| Key feature | **Intrinsic memory** inside the model |

**The hope:**

> **If LLMs have their own memory, then we would not need to build so many external systems.**

### 16.4 Why This Research Matters

> **"A lot of work is happening in this particular domain. Mostly because it is very important — without memory, you cannot build GenAI and agentic AI applications."**

### 16.5 The Speaker's Closing Thought

> **"That is why I made this video — a one to one-and-a-half-hour overview of memory. I really hope this entire overview is helpful to you."**

---

## 17. Key Takeaways

1. **An LLM at inference is a parameterized math function:** `y = f(x; θ)`.
2. **θ (parameters) is fixed** at inference; the user can only change `x` (the prompt).
3. **LLMs are stateless by nature:** output depends only on current input and fixed parameters.
4. **Therefore, LLMs have no intrinsic memory.**
5. **GenAI applications cannot function without memory.**
6. **This is a deadlock:** no memory in the LLM, but memory is required → build it externally.
7. **Context window** is the maximum text the LLM can read before answering (e.g., 128k, 1M tokens; ~200-page PDF).
8. **In-context learning** lets the LLM use information in the prompt, in addition to parametric knowledge.
9. **Short-term memory** = conversation buffer (`messages` variable) passed on every LLM call.
10. **Short-term memory is stateful but temporary:** resets on restart.
11. **Chatbots scope short-term memory per conversation (thread).**
12. **Short-term memory has three limitations:**
    - **Fragility** → solution: persistence (database + thread ID)
    - **Context window overflow** → solution: trimming + summarization
    - **Thread-scoped** → solution: long-term memory
13. **Long-term memory** must:
    - Survive across conversations/sessions (days/months)
    - Be **selective** — store only stable, useful, reusable information
14. **Three types of long-term memory:**
    - **Episodic** — what happened
    - **Semantic** — what is true (most common and important)
    - **Procedural** — how to do things
15. **Long-term memory works in four steps:**
    - **Creation/Update** → extract, filter, tag, decide
    - **Storage** → durable save with metadata
    - **Retrieval** → selective search, not exhaustive
    - **Injection** → pull into short-term memory, becomes part of context
16. **Long-term memory never interacts directly with the LLM.** It always passes through short-term memory.
17. **Three challenges:** memory creation, real-time retrieval, orchestration.
18. **Libraries emerging:** LangMem, MemZero, SuperMemory.
19. **Future:** LLMs with intrinsic memory (Google's Titans + Mirage) may reduce the need for external systems.
20. **Memory is essential** — without it, GenAI and agentic AI applications cannot be built.

---

## 18. Glossary

| Term | Definition |
|---|---|
| **Parameterized math function** | A function whose output depends on input plus additional learned parameters. |
| **θ (theta)** | The parameter set of the LLM (billions of values). |
| **Stateless** | A system whose output depends only on current input, not on past events. |
| **Parametric knowledge** | Knowledge stored in the model's parameters during training. |
| **Context window** | The maximum text an LLM can read and remember at one time before answering. |
| **In-context learning** | An emergent ability to use information in the prompt to answer, beyond parametric knowledge. |
| **Short-term memory** | The conversation buffer passed to the LLM on every call; thread-scoped; temporary. |
| **Conversation buffer** | The `messages` variable that accumulates the current conversation. |
| **Thread** | A single conversation; short-term memory is thread-scoped. |
| **Persistence** | Storing memory durably (e.g., database) so it survives restarts. |
| **Trimming** | Sending only the most recent N messages to fit the context window. |
| **Summarization** | Replacing old messages with a compact summary to fit the context window. |
| **Long-term memory** | Memory that persists beyond a conversation and stores only stable, useful, reusable information. |
| **Episodic memory** | Long-term memory of what happened in the past. |
| **Semantic memory** | Long-term memory of facts about the user and system. |
| **Procedural memory** | Long-term memory of how to do things (strategies, rules, behaviors). |
| **Creation (memory)** | Extracting and deciding what to store in long-term memory. |
| **Storage (memory)** | Durably saving memory with identifiers and metadata. |
| **Retrieval (memory)** | Selectively finding relevant memory for the current query. |
| **Injection (memory)** | Pulling retrieved memory into short-term memory so it becomes part of the context. |
| **Selective retrieval** | Retrieving only relevant memory pieces, not everything. |
| **Exhaustive** | Sending everything, as short-term memory does. |
| **Intrinsic memory** | Memory built into the model itself (future research direction). |

---

## 19. Self-Test Questions

### Foundations
1. Write the mathematical representation of an LLM at inference.
2. What is a parameterized math function? Give a linear regression example.
3. In `y = f(x; θ)`, who controls θ at inference? Who controls x?
4. Define "stateless" in the context of an LLM.
5. Why does changing the prompt change the output?

### The Deadlock
6. What two facts create the deadlock?
7. What is the logical conclusion (Fact 3) of the deadlock?
8. Why is a memoryless chatbot frustrating for users?

### Context Window and In-Context Learning
9. Define context window. What is the camera analogy?
10. What are typical context window sizes today?
11. Define in-context learning.
12. What is the PDF example, and why does it demonstrate in-context learning?

### Short-Term Memory
13. What is the equation change when short-term memory is introduced?
14. What is the `messages` variable, and what does it do?
15. Why is short-term memory called temporary?
16. Why is each conversation given its own short-term memory?
17. What does "thread-scoped" mean?

### Limitations
18. List the three limitations of short-term memory.
19. How does persistence solve fragility? Describe the thread ID approach.
20. Why does the context window problem arise?
21. What is trimming, and what is its weakness?
22. How does summarization improve on trimming?
23. Give two examples from the transcript that illustrate thread-scoped memory problems.
24. Why is personalization impossible with short-term memory?

### Long-Term Memory
25. What two properties must long-term memory have?
26. What does "selective" mean in this context?
27. What three criteria must stored information meet?
28. Name the three types of long-term memory.
29. What does episodic memory store? Give two examples.
30. What does semantic memory store? Why is it considered the most important?
31. What does procedural memory store? Give three examples.

### Architecture
32. What are the four steps of long-term memory?
33. What are the four sub-steps of creation?
34. What are the three possible decisions in creation?
35. What is the purpose of storage, and what two functions does it perform?
36. Why is retrieval described as selective, not exhaustive?
37. Why does long-term memory never interact directly with the LLM?
38. How does injection work?

### Challenges and Tools
39. What are the three challenges of building memory systems?
40. Why is memory creation itself difficult?
41. Name three libraries that manage memory for GenAI apps.
42. What is the Google paper that aims to build LLMs with intrinsic memory?

### Answer Key
1. `y = f(x; θ)`.
2. A function whose output depends on input plus additional parameters; e.g., `y = mx + b`, where `m` and `b` are learned from data.
3. θ is fixed at inference (nobody changes it); the user controls x (the prompt).
4. Output depends only on current input, not on anything that happened before.
5. Because x changed, and y is a function of x (and fixed θ).
6. LLMs have no memory; GenAI applications cannot function without memory.
7. Build memory externally, around the LLM.
8. Every message feels brand new; the user must re-explain everything.
9. The maximum text an LLM can read and remember at one time; camera/lens analogy — lens size = how much of the scene can be captured.
10. ~128k tokens or more; Gemini ~1M tokens; ~200-page PDF fits in 128k.
11. An emergent ability to use information in the prompt, in addition to parametric knowledge.
12. A 100-page private PDF placed in the prompt; the LLM reads it and answers from it, despite never being trained on it.
13. From `y2 = f(x2; θ)` to `y2 = f(x1, y1, x2; θ)`.
14. A list that stores the conversation history; passed to the LLM on every call; acts as state.
15. Because it resets when the code restarts or the server crashes.
16. Otherwise the `messages` list becomes too long and incoherent across unrelated conversations.
17. Restricted to a single conversation/thread; does not exist outside it.
18. Fragility; context window overflow; thread-scoped.
19. Store messages in a database against a thread ID; reload them when returning to that conversation.
20. Long-running conversations accumulate; sending the full history on every call exceeds the token limit; the LLM stops understanding.
21. Send only the last N messages; risk of losing important context.
22. Summarize the removed messages and attach the summary to the recent messages; the total stays within the limit.
23. Python vs. Java preference lost in a new conversation; SQL optimization preference (window function) forgotten in a new conversation.
24. Because user preferences are spread across many conversations, and short-term memory is locked inside one conversation.
25. Long-lasting storage of special information; very selective storage.
26. Not blindly storing everything; extracting only what matters.
27. Stable; useful; reusable.
28. Episodic; semantic; procedural.
29. Past events; e.g., a rejected solution, a failed deployment due to wrong credentials.
30. Facts about the user and system; e.g., user prefers Python, system uses PostgreSQL. It is the most common and most important type.
31. Strategies, rules, learned behaviors; e.g., avoid subqueries, try tool Y if tool X fails, explain step-by-step.
32. Creation/Update; Storage; Retrieval; Injection.
33. Extract candidates; filter noise; decide scope (user/app/agent); decide action (create/update/ignore).
34. Create new; update existing; ignore.
35. To persist memory for future reuse; saves durably and tags with identifiers and metadata.
36. Because taking everything would be expensive and irrelevant; only relevant pieces are searched and extracted.
37. Because the LLM should see only what is relevant; memory must first pass through short-term memory and become part of the context.
38. Retrieval pulls memory into short-term memory; it becomes part of the prompt and is seen by the model as input tokens.
39. Memory creation; real-time retrieval; orchestration.
40. Because users chat with noise; deciding what is stable, useful, and reusable is hard.
41. LangMem, MemZero, SuperMemory.
42. Titans + Mirage (per transcript).

---

## 20. Mental Model Summary

```text
THE FOUNDATION
  LLM at inference = y = f(x; θ)
  θ is fixed; x is the only lever.
  Therefore: LLM is stateless.
  Therefore: LLM has no intrinsic memory.

THE DEADLOCK
  No memory in LLM + memory required by apps = stuck.
  Resolution: build memory externally, around the LLM.

TWO BUILDING BLOCKS
  Context window      → space to carry history
  In-context learning → ability to use history in the prompt

SHORT-TERM MEMORY
  messages = [x1, y1, x2, y2, ...] passed on every call.
  Makes the system stateful.
  But: temporary, fragile, thread-scoped.

THREE LIMITATIONS
  1. Fragility        → persistence (DB + thread ID)
  2. Context overflow → trimming + summarization
  3. Thread-scoped    → long-term memory

LONG-TERM MEMORY
  Properties: long-lasting + selective.
  Types: episodic / semantic / procedural.
  Steps: creation → storage → retrieval → injection.
  Never touches the LLM directly; always flows through short-term memory.

CHALLENGES
  Creation is hard (what to remember?).
  Retrieval is hard (what is relevant now?).
  Orchestration is hard (many moving parts).

TOOLS
  LangMem, MemZero, SuperMemory.

FUTURE
  LLMs with intrinsic memory (Titans + Mirage).

BOTTOM LINE
  Without memory, you cannot build GenAI or agentic AI applications.
```

---

*End of very detailed incremental notes.*