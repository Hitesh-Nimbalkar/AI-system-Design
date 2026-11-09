# Caching Failures in an AI Assistant: Detailed Learning Material

## 1. Why Caching Matters in AI Assistants

An AI assistant that answers user questions typically involves several expensive steps:

1. **Retrieval** — searching a vector database for relevant document chunks.
2. **Context construction** — assembling retrieved chunks into a prompt.
3. **LLM generation** — calling a large language model to produce an answer.

Each step costs time, tokens, and money. Caching stores the results of previous work so that repeated or similar requests can be served faster and cheaper.

But caching introduces a fundamental trade-off:

> **Freshness vs. Cost.**  
> The more you cache, the cheaper and faster your system becomes — but the higher the risk that users receive stale or incorrect answers.

This material analyzes two real caching failures in an AI support assistant and teaches how to design a safer caching strategy.

---

## 2. The Original Three-Layer Cache Architecture

The assistant uses three caches in sequence.

### 2.1 Exact Response Cache

- **Purpose:** If a user asks the exact same question word-for-word that was asked before, return the stored answer immediately.
- **Key:** The exact query text.
- **TTL:** 24 hours.
- **How it works:** The system hashes the query and looks it up. If found and not expired, return the cached answer without calling the model.

**Example:**
- Cached query: `"What is the refund window?"`
- New query: `"What is the refund window?"` → exact match → return cached answer.

**Limitation:** Tiny wording changes cause a miss.

### 2.2 Semantic Response Cache

- **Purpose:** Catch paraphrased questions that mean the same thing.
- **Key:** The query embedding.
- **Matching rule:** Compute cosine similarity between the new query embedding and stored query embeddings. If similarity ≥ **0.92**, treat the questions as the same and return the previous answer.
- **TTL:** 24 hours.

**Example:**
- Cached: `"What is the refund window?"`
- New: `"How long do I have to get a refund?"`
- If cosine similarity ≥ 0.92 → cache hit.

**Limitation:** Similarity of meaning is not the same as similarity of intent. This caused Failure 2.

### 2.3 Retrieval Cache

- **Purpose:** Cache the retrieved document chunks for a query so retrieval does not run again.
- **Key:** The query.
- **TTL:** 7 days.
- **How it works:** When a query is first processed, the system retrieves relevant chunks from the vector database and stores them under the query key. Later identical queries reuse those chunks.

**Limitation:** If the underlying documents change and the cache is not invalidated, the system serves old chunks. This caused Failure 1.

### 2.4 Architecture Diagram

```text
┌─────────────┐      ┌──────────────────┐      ┌─────────────────────┐
│ Browser /   │─────▶│ Assistant        │─────▶│ Exact response cache│
│ Chat UI     │      │ Service          │      │ TTL = 24h           │
└─────────────┘      │                  │      └─────────────────────┘
                     │                  │      ┌─────────────────────┐
                     │                  │─────▶│ Semantic response   │
                     │                  │      │ cache TTL = 24h     │
                     │                  │      │ cosine ≥ 0.92       │
                     │                  │      └─────────────────────┘
                     │                  │      ┌─────────────────────┐
                     │                  │─────▶│ Retrieval cache     │
                     │                  │      │ TTL = 7 days        │
                     └────────┬─────────┘      └─────────────────────┘
                              │
                              ▼
                     ┌──────────────────┐
                     │ Model            │
                     └──────────────────┘
                              ▲
                              │ context
                     ┌──────────────────┐
                     │ Vector DB        │
                     └──────────────────┘
                              ▲
                              │ write
                     ┌──────────────────┐
                     │ Indexer: chunk → │
                     │ embed → write    │
                     └──────────────────┘
                              ▲
                              │ policy doc
                     ┌──────────────────┐
                     │ Policy document  │
                     └──────────────────┘
```

**Critical missing arrow:** When the vector DB/index is updated, there is **no direct trigger** to invalidate the retrieval cache.

---

## 3. Failure 1 — Stale Refund Policy

### 3.1 Symptom

Users asked: *"What is the refund window?"*  
The assistant answered: **30 days**.  
The actual policy had changed to **14 days** on Monday.

Wrong answers persisted from Monday through Wednesday.

### 3.2 Timeline and Evidence

| Time | Event |
|---|---|
| Sunday | Retrieval cache entry created at **version 3** for the refund window. |
| Monday 9:05 | Refund policy updated. Index rebuilt to **version 4**. |
| Monday–Wednesday | Retrieval cache still serves **version 3** content. |
| 55 hours later | Cache still at version 3. |
| Eventually | Cache flushed manually; issue temporarily fixed. |

The retrieval cache TTL was **7 days**. Without a manual flush, stale data could have persisted up to 7 days.

### 3.3 Root Cause

The index was at **version 4**, but the cached content was at **version 3**.

There was **no invalidation trigger** from the index update to the retrieval cache. The system had no mechanism to say: *"The refund document changed — purge all cache entries derived from it."*

### 3.4 Why This Was Not Hallucination

A common first hypothesis is: *"The model is hallucinating."*

This is wrong for two reasons:

1. The model returned the **exact old number (30 days)**. Hallucination typically produces plausible-sounding but fabricated content, not a precise previous value.
2. **The model output is a function of its context.** The model does not independently fetch new information. It answers from:
   - Its training data, and
   - The context you provide.

If the context contains version 3 data saying *"30 days,"* the model will answer *"30 days."* The model did exactly what it was supposed to do. The bug was upstream: the context was stale.

> **Rule:** When an AI assistant gives a wrong answer, check the context first. Bad input produces bad output.

### 3.5 Correct Debugging Order

Do not start randomly at a component. Trace backward from the symptom:

1. **Inspect the wrong answer.** What exactly is wrong?
2. **Inspect the context** that was sent to the model.
3. **Trace where the context came from.** Was it live retrieval? Retrieval cache? Semantic cache? Exact cache?
4. **Inspect the cache key.**
5. **Find the root cause** — in this case, a version mismatch between index and cache.

---

## 4. Failure 2 — Pause vs. Cancel Semantic Cache

### 4.1 Symptom

User asks: *"How do I pause my subscription?"*  
Assistant gives instructions to **cancel** the subscription.

This is a serious business risk: legal and financial consequences.

### 4.2 Root Cause

The semantic response cache works as follows:

1. Embed the new query.
2. Compare its cosine similarity with cached queries.
3. If similarity ≥ **0.92**, return the cached answer.

For *"pause my subscription"* and *"cancel my subscription,"* cosine similarity was about **0.94**.

Since 0.94 ≥ 0.92, the system treated them as the same query and returned the cancel answer.

### 4.3 The Core Misconception: Similarity vs. Intent

Embeddings capture **similarity of meaning**, not **similarity of intent**.

- **Similarity of meaning:** The queries are about the same topic (actions on a subscription).
- **Similarity of intent:** The user wants to achieve the same outcome (pause ≠ cancel).

These are different. Two people can look similar but are not the same person. Two queries can be semantically similar but have completely different intents.

### 4.4 Embedding-Space Clustering

If you plot these queries in embedding space, they cluster together:

- `stop my subscription`
- `pause my subscription`
- `end my subscription`
- `delete my subscription`

They are all *"actions on subscription."* Their embeddings are close. But their intents differ. Cosine similarity above a threshold does **not** guarantee identical intent.

> **Key lesson:** Do not assume that crossing a similarity threshold means the intent is the same. Similar ≠ same.

---

## 5. Cache Invalidation Strategies

Invalidation is how you prevent stale data. There are four main strategies.

### 5.1 TTL (Time To Live)

- **How it works:** Cached data expires automatically after a fixed duration.
- **Staleness risk:** Bounded by TTL. If data changes before TTL expires, stale data remains until expiry.
- **Coordination required:** None. The cache system handles expiry.
- **When it fails:** When data changes faster than the TTL. This is exactly what happened in Failure 1: policy changed, but TTL was 7 days.
- **Best use case:** Data that changes slowly or where bounded staleness is acceptable.

### 5.2 Explicit Purge on Write

- **How it works:** When a source document is updated, actively purge all cache keys associated with that document.
- **Staleness risk:** Zero, if maintained perfectly.
- **Coordination required:** High. You need a **dependency index** mapping documents to cache keys. If you forget one key, stale data remains.
- **When it fails:** When the dependency index is incomplete or out of date.
- **Best use case:** Systems where documents have clear key associations and immediate freshness is required.

### 5.3 Versioning / Generation Counter

- **How it works:** Maintain a generation counter. When content changes, bump the generation. Include the generation in every cache key. New queries use the new generation, so they never hit old cache entries.
- **Staleness risk:** Zero for old generations.
- **Coordination required:** A reliable counter and bump mechanism.
- **When it fails:** If the generation bump is missed, or the counter is wrong.
- **Best use case:** Policy or index updates where all old cached content should be ignored.

**Example:**
- Generation 41: cache key = `tenant:ACME:gen:41:hash(query)`
- Policy changes → generation bumps to 42.
- New query produces key = `tenant:ACME:gen:42:hash(query)`
- Old generation-41 entry is never hit. System recomputes and caches under generation 42.

### 5.4 Content-Hash Cache

- **How it works:** The cache key is a hash of the content itself.
- **Staleness risk:** Self-invalidating. If content changes, hash changes, so the old key is never hit.
- **Coordination required:** None.
- **When it fails:** If the cached value is not a direct function of the content.
- **Best use case:** Embedding cache. Embedding is a direct function of chunk text. If chunk text changes, hash changes, and the system re-embeds.

### 5.5 Comparison Table

| Strategy | Staleness risk | Coordination | When it fails | Best use case |
|---|---|---|---|---|
| TTL | Bounded by TTL | None | Data changes faster than TTL | Slow-changing data |
| Explicit purge | Zero if perfect | High (dependency index) | Missing a key | Document-linked caches |
| Versioning | Zero for old generation | Counter/bump | Missed bump | Policy/index updates |
| Content hash | Self-invalidating | None | Content not directly related to value | Embedding cache |

---

## 6. Improved Cache Key Design

### 6.1 Why the Old Key Was Too Naive

The original key was just the query. This is insufficient because:

- The same question from different tenants may have different answers.
- Old-generation content may be returned after a policy change.

### 6.2 New Key Components

A robust key includes:

1. **Tenant** — identifies the company/merchant. Same question, different tenant → different answer.
2. **Generation** — the current content version. Prevents old-generation cache hits.
3. **Normalized query** — lowercase, punctuation removed, special characters stripped.

**Normalization example:**
- `"What is your refund?"`
- `"what is your refund"`
- `"what is your refund?"`

All normalize to the same string.

**Example key:**
```
tenant = ACME
generation = 42
hash = normalized_query
```

### 6.3 Why Generation Bumping Prevents Stale Hits

Suppose a cache entry exists for generation 41. The policy changes, and the generation bumps to 42. The same query now produces a different key because the generation component changed. The old entry is never hit. The system recomputes and caches under generation 42.

> **Key design itself enforces freshness.** You do not need to explicitly purge old entries; they simply become unreachable.

### 6.4 Embedding Cache Exception

For the embedding cache, the key is **only the hash of the chunk text**. No tenant or generation is needed because embedding is a direct function of the text. If the text changes, the hash changes, and the system re-embeds.

---

## 7. Cache Expiry Is a Load Event

### 7.1 The Vicious Cycle

When many cache entries expire or are invalidated at once:

```text
Cache expiry / invalidation
        ↓
More cache misses
        ↓
More model calls / full processing
        ↓
Higher load
        ↓
Higher latency
        ↓
More timeouts
        ↓
More retries
        ↓
Even more load
```

This can cause the system to crash.

> **Key formula:** Cache expiry is a load event. Design for it.

### 7.2 Mitigation 1 — Singleflight

- **Problem:** Many concurrent requests for the same key cause duplicate work.
- **Solution:** Collapse identical concurrent requests into one computation. All waiting requests receive the same result.
- **Example from transcript:** 1,400 requests but only 38 unique keys. Singleflight reduces 1,400 model calls to 38.

### 7.3 Mitigation 2 — TTL Jitter

- **Problem:** If all keys have exactly the same TTL, they expire at the same time, creating a "TTL wall."
- **Solution:** Add randomness to TTL. Instead of 24 hours, use 24 hours ± 10% (e.g., 21.6 to 26.4 hours).
- **Effect:** Expiries spread over time, avoiding sudden load spikes.

### 7.4 Mitigation 3 — Warm-Up Job

- **Problem:** A generation bump invalidates all cache entries at once.
- **Solution:** Before flipping to the new generation, pre-populate the cache with the most common queries for the new generation.
- **Effect:** When traffic switches, common queries hit the warm cache; only tail queries go through full processing.

---

## 8. Choosing a Semantic Similarity Threshold

### 8.1 The Trade-Off

| Threshold | Hit rate | Wrong hits | Notes |
|---|---|---|---|
| Low (e.g., 0.90) | High | Many | More wrong answers |
| Medium | Moderate | Moderate | Balance point |
| High (e.g., 0.99) | Very low | Very few | Cache may become useless |

### 8.2 Cost Calculation

To choose a threshold, calculate the cost per 1,000 requests.

- **Cost of a wrong cache hit:** Support ticket + human time. Example: **$8**.
- **Cost of a cache miss:** Model call + latency. Example: **$0.026**.

**Example calculation:**
- 640 model calls
- 34 wrong answers × $8 = **$289**

As the threshold rises, wrong answers decrease, so cost falls. But eventually, hit rate becomes so low that the cache provides little value, and cost rises again.

### 8.3 Choosing the Balance Point

The optimal threshold depends on:

- How important correctness is for your application.
- Legal requirements.
- Business tolerance for wrong answers.
- Cost of misses vs. wrong hits.

> There is no universal threshold. It is a business and engineering decision.

---

## 9. Debugging Playbook

When an AI assistant gives a wrong answer, follow this checklist:

1. **Confirm the symptom.** What exactly is wrong?
2. **Inspect the context** sent to the model.
3. **Trace the context source:** retrieval cache? semantic cache? exact cache? live retrieval?
4. **Inspect the cache key.**
5. **Check version/generation mismatch** between index and cache.
6. **Check TTL and invalidation path.**
7. **Check semantic threshold and wrong hits.**
8. **Check load spikes after invalidation.**
9. **Fix the source**, not just the symptom.
10. **Verify with a trace** from source to output.

---

## 10. Key Takeaways

1. Don’t blame hallucination first — inspect context and cache.
2. Model output is a function of context; bad context produces bad output.
3. Version mismatch between index and cache causes stale answers.
4. TTL alone is insufficient when content changes faster than TTL.
5. Explicit purge requires a reliable dependency index.
6. Generation/versioned keys prevent stale cache hits automatically.
7. Content-hash keys work well for embedding caches.
8. Cache expiry is a load event; design for it.
9. Singleflight collapses duplicate concurrent requests.
10. TTL jitter spreads expiry and avoids load spikes.
11. Warm-up jobs pre-populate common keys before generation flip.
12. Semantic similarity is not intent similarity.
13. Tune semantic thresholds with cost/correctness data.
14. Key design is central to any caching strategy.
15. No system is perfectly fixed; every strategy has trade-offs.

---

## 11. Glossary

| Term | Definition |
|---|---|
| **TTL** | Time To Live; how long cached data remains valid. |
| **Cache hit / miss** | Hit = key found in cache; miss = not found. |
| **Staleness** | Cached data is old or inaccurate relative to source of truth. |
| **Invalidation** | Removing or marking cached data as unusable. |
| **Explicit purge** | Actively deleting cache entries when source data changes. |
| **Generation / version bump** | Incrementing a counter when content changes. |
| **Content hash** | Hash of content used as cache key. |
| **Embedding** | Vector representation of text capturing semantic meaning. |
| **Cosine similarity** | Measure of similarity between two vectors. |
| **Semantic cache** | Cache that returns answers for semantically similar queries. |
| **Retrieval cache** | Cache of retrieved chunks/context for a query. |
| **Singleflight** | Collapsing concurrent identical requests into one computation. |
| **TTL jitter** | Adding randomness to TTL to spread expiry. |
| **Warm-up job** | Pre-populating cache with common keys before traffic arrives. |
| **Cache stampede** | Many requests miss cache simultaneously and overwhelm backend. |
| **Normalized query** | Query transformed to a canonical form. |
| **Tenant** | Customer/company/merchant whose data is isolated. |

---

## 12. Self-Test Questions

### Conceptual
1. What are the three caches, and what does each store?
2. Why is "model is hallucinating" a poor first hypothesis?
3. What is the difference between similarity of meaning and similarity of intent?
4. Why does a content-hash cache work well for embeddings?
5. What does "cache expiry is a load event" mean?

### Scenario-Based
6. A policy changes at 9 AM. The index updates at 9:05 AM. Users still get old answers at 3 PM. What likely happened?
7. Users ask "pause my subscription" and get cancel instructions. What cache and threshold are involved?
8. A generation bump causes a traffic spike. What three mitigations could help?
9. Same question from two tenants returns the same answer, but it should differ. What is missing from the key?
10. 1,400 requests but only 38 unique keys. How can singleflight help?

### Debugging
11. List the correct debugging order for a wrong AI answer.
12. How do you check for a version mismatch?
13. What evidence shows the refund issue was not hallucination?
14. How would you detect wrong semantic cache hits?
15. What should you inspect first when a cache miss causes high load?

### Design/Trade-Off
16. Compare TTL and versioning for policy documents.
17. When would explicit purge be better than TTL?
18. How do you choose a semantic similarity threshold?
19. Why can't you set the threshold to 1.0?
20. What are the pros and cons of a warm-up job?

### Answer Key
1. Exact response (exact query → answer, TTL 24h); semantic response (similar query → answer, cosine ≥ 0.92, TTL 24h); retrieval (query → chunks, TTL 7 days).
2. The model returned the exact old number, indicating stale context, not fabrication.
3. Embeddings capture meaning similarity; intent similarity requires understanding the user's goal.
4. Embedding is a direct function of chunk text; text change → hash change → re-embed.
5. Mass invalidation causes many misses at once, increasing load, latency, timeouts, retries.
6. Retrieval cache was not invalidated; index v4, cache v3.
7. Semantic response cache; cosine ≈ 0.94 exceeded 0.92.
8. Singleflight, TTL jitter, warm-up job.
9. Tenant is missing from the key.
10. Singleflight computes once per unique key and shares the result.
11. Inspect answer → context → source → key → root cause.
12. Compare index version with cache content version.
13. The answer matched the exact previous policy value.
14. Track wrong hits per threshold; compare cached answer intent with query intent.
15. Check for mass invalidation or generation bump; check singleflight, jitter, warm-up.
16. TTL is simple but allows staleness; versioning prevents stale hits immediately but needs a reliable counter.
17. When documents have clear key associations and immediate freshness is required.
18. Build a threshold vs. hit rate vs. wrong hits table; calculate cost per 1,000 requests; choose based on business tolerance.
19. Hit rate would collapse; cache becomes useless.
20. Pros: reduces load spike, improves hit rate for common questions. Cons: extra computation, only covers common keys.

---

*End of learning material.*