# Detailed Notes: JSON-RPC

## 1. What JSON-RPC is
- **JSON-RPC** stands for **JavaScript Object Notation Remote Procedure Call**.
- It is a way to **call functions on another computer** using simple text messages.
- It is **lightweight**, **stateless**, and works almost anywhere.
- It solves the problem: “My code calls a function, but what if that function lives on a different machine across the internet?”
- **Core message flow:**  
  1. Client sends a request.  
  2. Server does the work.  
  3. Server sends back a response.
- JSON-RPC **does not care how messages travel**. It can use:
  - regular web traffic / HTTP,
  - a live WebSocket connection,
  - a command-line program,
  - a raw network socket.
- The message format looks the same regardless of transport.

## 2. The request object
A JSON-RPC request has **four main fields**:

| Field | Meaning |
|---|---|
| `jsonrpc` | Version, always `"2.0"` |
| `method` | Name of the function to run |
| `params` | Values passed to the function |
| `id` | Tag that connects the response back to the request |

Example request:
```json
{
  "jsonrpc": "2.0",
  "method": "subtract",
  "params": [42, 23],
  "id": 1
}
```

## 3. Successful response
- The server runs the method and returns a **result**.
- The response includes the **same ID** that was sent in the request.
- The matching ID tells the client that the answer belongs to its question.

Example:
```json
{
  "jsonrpc": "2.0",
  "result": 19,
  "id": 1
}
```

Example from the transcript: ask the server to subtract 23 from 42; server returns `19` with the same ID.

## 4. Error response
- If something goes wrong, the server returns an **error** instead of a result.
- The error includes a **code** and a **short message** explaining what happened.
- Example: sending the word `"42"` instead of the number `42`; the server cannot subtract it, so it returns an error.

Example:
```json
{
  "jsonrpc": "2.0",
  "error": {
    "code": -32602,
    "message": "Invalid params"
  },
  "id": 1
}
```

**Golden rule:**  
A response contains **either a result or an error — never both**.

## 5. Notifications
- If you **do not need an answer**, leave out the `id`.
- That turns the request into a **notification**.
- It is **fire-and-forget**: the server does the work but never replies.
- Notifications get **no response**.

## 6. Parameters: by position vs by name
Params can be sent in two ways:

### By position
- Order matters.
- The first value goes to the first argument, second value to the second argument, etc.
```json
"params": [42, 23]
```

### By name
- Each value is labeled.
- Order does not matter.
- **Names are case-sensitive.**
```json
"params": {
  "minuend": 42,
  "subtrahend": 23
}
```

## 7. Batch requests
- If you need to make many calls at once, bundle them into a **batch**.
- A batch is **one list containing many requests**.
- The server can process them all at the same time.
- Because of that, **responses can come back in any order**.
- **Notifications inside a batch still get no reply.**

## 8. Standard error codes
JSON-RPC uses a standard set of error codes:
- **Parse error** — the message is invalid.
- **Invalid Request**.
- **Method not found**.
- **Invalid params**.
- **Internal error**.
- A whole reserved range for **server errors**.
- Anything else is up to your application.

## 9. IDs, concurrency, and transport
- Responses can arrive **out of order**.
- This is why the `id` matters so much.
- **Never match responses by when they arrive.**
- **Always match responses by ID.**
- Keep IDs **unique**.
- Stick to **strings or whole numbers** for IDs.
- Transport does not matter: web, WebSocket, command line, or network socket — the same message format is used every time.

## 10. Security and validation
Important warning: **JSON-RPC does not secure itself.**

You must:
- **Authenticate every method.**
- **Validate every method name and every param.**
- Use **encrypted connections**.
- Add **rate limits** and **timeouts**.
- **Never leak secrets inside error messages.**

## 11. Implementation checklist
Before shipping, run through this checklist:
- Document your **methods** and **errors**.
- Keep **method names stable**.
- Keep **IDs unique**.
- Handle **bad messages**, **batches**, and **notifications** properly.
- **Log safely**.
- Remember: any method name starting with **`rpc.`** is **reserved**.

## 12. Recap in 4 steps
1. **Name the method.**
2. **Validate the params.**
3. **Match the ID.**
4. **Return a result or an error.**

That is JSON-RPC: a simple, transport-independent way to call functions remotely using JSON messages.