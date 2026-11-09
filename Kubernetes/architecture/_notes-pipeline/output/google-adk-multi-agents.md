# Google ADK: Building and Running Your First Agent - Study Notes

> **In a sentence:** Google ADK (Agent Development Kit) lets you scaffold a working Gemini-backed agent from three prompt answers, run it three different ways without writing extra code, and swap the underlying model in a single line.
> Source: Google_ADK_Multi_agents_4.
> Generated: 2026-11-09.
> **How to use:** read one numbered section, answer its questions, then continue.

## The short version

Building an agent by hand means writing provider SDK calls, a chat loop, a UI, session handling and tracing yourself. ADK removes that scaffolding: you install it, run one create command, answer three prompts (model, backend, API key), and get a folder containing a runnable *root agent*. That same agent can then be started in a terminal, in a browser-based chat UI with full event tracing, or as a FastAPI service on a port — no extra code for any of the three. Because ADK is primarily built around Gemini, the default path uses a Gemini model and a free-tier Google API key, but a strong LiteLLM integration lets you point the same unchanged agent at OpenAI, Anthropic or open-source models. The last two steps are model configuration (temperature and output-token limits) and the habit of reading the trace to see what actually happened.

```
  adk create campusx_bot
        │
        ▼
  campusx_bot/                       ┌── adk run         → terminal chat
   ├── __init__.py   (package)       │
   ├── .env          (API key)       ├── adk web         → browser UI + tracing
   └── agent.py      (root agent) ───┤
                                     └── adk api server  → FastAPI on a port
                │
                └── model line ──► Gemini   ◄── or ──►  LiteLLM ──► OpenAI / Anthropic / OSS
```

## 1) Preparing the toolchain

**Why this matters:** an agent project fails at the very first command if the ADK package is installed into the wrong Python or not installed at all, so install and verify before anything else.

Start with a project folder — in the demonstration, one called `GoogleADK course` on the desktop — opened in VS Code, then open a terminal inside it. A *virtual environment* is an isolated Python installation with its own set of packages, so what you install for this project does not collide with other projects on the same machine. Create one named `venv`:

```bash
python3 -m venv venv
```

Then activate it. **Context:** activation is what makes `pip` and `python` in this terminal point at the environment rather than the system Python; it is the step people most often skip, and skipping it is why an install "disappears" later.

The activation command is different on macOS and on Windows, and the exact commands are not spelled out here — use the form that matches your machine (the Windows form is typically a script inside `venv\Scripts\`, the macOS/Linux form a `source` of a script inside `venv/bin/`). With the environment active, install ADK and confirm it landed:

```bash
pip install googleadk
adk
adk --version
adk --help
```

Running `adk` with no arguments lists the keywords ADK accepts as commands — a quick smoke test that the install worked. `adk --version` prints the installed version; the demonstration reported **2.12**. ADK exists in a version 1 and a version 2, and this material uses version 2, so anything in the 2.x range is what you want. `adk --help` prints usage help.

If `adk` is not recognised as a command, the install did not succeed: reinstall with `pip install googleadk` and re-run `adk --version` to confirm.

**Terms**
| Term | Meaning |
|---|---|
| ADK | Google's Agent Development Kit, a framework for building agents, primarily built around Gemini models |
| virtual environment (`venv`) | An isolated Python package set for one project |
| `pip` | Python's package installer |

**Check yourself**
1. What does `adk` with no arguments tell you that `adk --version` does not?
2. The `adk` command is not found on your machine. What is the single most likely cause, and what do you do?
3. You have two agent projects on one laptop and want their dependencies never to interfere. Which step in this section gives you that, and why?

**Practice:** from an empty folder, write out the exact sequence of commands you would type, on your own operating system, to reach a verified 2.x ADK install.

## 2) Scaffolding the agent with one command

**Why this matters:** `adk create` is the boundary between "I have a framework installed" and "I have an agent", and it decides which model your agent will call for the rest of the session.

From inside the project folder, with the environment active, run:

```bash
adk create campusx_bot
```

`campusx_bot` is the name of the agent, and the command is interactive — it asks three things in sequence:

1. **The model.** In the demonstration, **Gemini 3.5 Flash** was selected.
2. **The backend.** In the demonstration, **Google AI** was selected.
3. **A Google API key.** An *API key* is a secret string that identifies your account to a paid or rate-limited service; the model provider uses it to attribute your requests. Get one from Google AI Studio, whose URL the prompt shows: open it, go to the API keys section, click create API key, give the key or its project a name, choose either an imported project or a new one, click create key, copy it, and paste it back into the prompt.

Pasting the key closes the prompt, and a new folder named `campusx_bot` appears with three files:

| File | Role |
|---|---|
| `__init__.py` | Contains a single line of code; it exists so Python treats the folder as a module/package |
| `.env` | Holds exactly the API key you supplied |
| `agent.py` | The main agent file — the *root agent* |

**Context:** keeping the key in `.env` rather than inside `agent.py` is the conventional separation of secrets from code, and `.env` files are normally kept out of version control so a key is never committed to a repository.

**Terms**
| Term | Meaning |
|---|---|
| root agent | The starting point of a multi-agent system in ADK; the agent defined in `agent.py` |
| `.env` | A file of environment variables; here it stores the API key |
| `__init__.py` | Marker file that makes a folder importable as a package |

**Check yourself**
1. Which three questions does `adk create` ask, and what does each answer control?
2. Why does the generated folder need an `__init__.py` at all?
3. You already have a Gemini API key from another project. Do you still have to visit Google AI Studio during `adk create`? Explain what the prompt is actually waiting for.

**Practice:** list the three generated files and, in one sentence each, state what would break if that file were deleted.

## 3) Reading `agent.py`: what an agent actually is

**Why this matters:** the file is small, and every capability you add later is a change to it — so the field you care about is the one that lets *other* agents find this one.

Every ADK project begins with a root agent, and a family of agents can grow out from it. In the demonstrated setup, four things are handed to the agent class object when it is constructed. Three of them are named explicitly in this material: the **model** (the LLM the agent calls), the **description**, and the **system instruction**.

The *description* is more than documentation. In a multi-agent system, one agent searches for another agent to assign a task based on that other agent's description — so the description is the routing signal, the text that decides whether work gets delegated to this agent or somewhere else. The *system instruction* is the part of the setup that tells the agent how it will work, and it is what controls the agent's behaviour: tone, scope, rules, refusals.

The instructor calls this configuration "the vanilla setup" — the base `agent.py` with nothing added. And an honest label matters here: what this file currently produces is technically a **chatbot**, not an agent. It has no tools and no capabilities; it only exchanges messages with a model. The distinction is the whole point of the rest of the course — tools and capabilities are what turn the chatbot into an agent.

**Context:** "agent" in this context usually means a model plus the ability to *act* (call tools, fetch data, hand off to other agents). A model that can only reply in text is a chatbot; ADK's scaffolding gives you the chatbot first and the actuators later.

**Terms**
| Term | Meaning |
|---|---|
| agent description | A field on the agent describing what it does; used by other agents to decide task assignment |
| system instruction | The setup text that tells the agent how to work; controls behaviour |
| chatbot vs agent | A chatbot only converses; an agent additionally has tools and capabilities |

**Check yourself**
1. Which field would another agent read to decide whether to hand your agent a task?
2. Which field would you edit to change the agent's tone or refuse off-topic questions?
3. Is the freshly generated `campusx_bot` an agent or a chatbot, and what exactly is missing?

**Practice:** write a one-line description for an agent that answers questions about a college campus, phrased so that a coordinating agent would route campus questions to it and nothing else.

## 4) Running it in the terminal

**Why this matters:** the fastest feedback loop is the console, and it is also the cheapest way to discover that your key or model is not working before you blame your code.

There are **three ways** to run an agent in ADK, and they all use the same agent definition:

- **console/terminal** — the `adk run` command,
- **web UI** — the `adk web` command,
- **as a service** — the `adk API server` command, which produces a FastAPI-based API server.

Start with the console. Clear the terminal, then:

```bash
adk run campusx_bot
```

The agent starts and you can type. In the demonstration, "Hi, my name is Nitish" was answered with something like "Hi Nitish, nice to meet you" and "How can I help you" — the agent replies and remembers the name within the conversation. Asking "What is an AI agent" first returned a **503 unavailable** error; re-running the same request returned the answer, rendered in markdown.

A 503 here is a server-side "service unavailable". Gemini 3.5 Flash on the free tier occasionally times out or crashes while serving free users — as the instructor puts it, "This is not our fault, not our setup. This is a fault on Google's side." The remedy is simply to run the request again; switching to another Gemini model, or to OpenAI or Anthropic through LiteLLM, is also possible.

**Terms**
| Term | Meaning |
|---|---|
| 503 unavailable | Error returned when the Gemini model times out or crashes while serving free-tier users |
| markdown format | Plain-text formatting (headings, bold, lists) that chat surfaces render as rich text |

**Check yourself**
1. Name the three ways to run an ADK agent and the command behind each.
2. You ask a question and get `503 unavailable`. What are the two reasonable responses, and which one would you try first?
3. Why does the terminal run remember the name you gave it earlier in the same conversation?

**Practice:** predict what happens if you run `adk run` followed by the name of an agent folder that does not exist, then explain which of the three run modes would fail the same way.

## 5) The web UI: where the agent becomes observable

**Why this matters:** a chat reply tells you *what* the agent said; the web UI tells you *why* — the request, the response, the tokens, the trace and the timing, with no tracing code written by you.

Exit the console chat, clear the screen, and run:

```bash
adk web
```

No project name is required: the command starts the ADK web server and prints a URL, which you open in a browser. You get a proper chat window. The demonstrated flow: say "hi", then "my name is NITISH", then ask "what is my name" — it answers correctly. Start a **new session**, say "hi my name is Rahul", ask again, and it answers "Your name is Rahul"; both sessions are visible side by side. In other words, *short-term memory* works out of the box and is scoped to the session: each session is its own conversation with its own history.

The real power is in the **events** panel. Every message sent by the user and every reply by the agent is recorded as an event. Selecting an event lets you inspect:

| What you can open | What it shows |
|---|---|
| Graph | The agent graph — currently a single root agent |
| Request / Response | Exactly what was sent to the model and what came back |
| Metadata | Details such as how many tokens went in and came out |
| Info tab | The author of the message — the root agent or the user |
| Trace | The root agent calling the LLM, and how long it took |
| State | State variables tracked across turns |
| Artifacts | Files/data tracked alongside the conversation |
| Evaluation sets | Creation of sets for evaluating the agent |

Tracing in particular comes by default here; comparable tracing elsewhere required a separate setup. Building the same chat window with sessions in LangGraph is described as taking two or three videos and a lot of custom code. Hence the analogy: this web UI is the USB of ADK — one plug-in interface that makes the developer's life easier. And "the more you work with ADK, the more you will like this web UI."

**Context:** a *session* is one conversation thread with its own message history and state; an *event* is one recorded turn inside it; a *trace* is the timeline of internal calls (here, the root agent invoking the LLM) with durations; *tokens* are the chunks of text models are billed and limited by; *evaluation sets* are saved inputs you re-run later to check the agent still behaves.

**Terms**
| Term | Meaning |
|---|---|
| `adk web` | Command that starts the ADK web server and serves the web UI; project name not required |
| event | A tracked record of each user message and agent reply, with metadata, request, response and trace |
| session | One conversation with its own history, visible separately in the UI |

**Check yourself**
1. Two browser sessions each told the agent a different name. Why do the answers not cross-contaminate?
2. Which panel would you open to prove that a slow reply was the model's latency rather than your code?
3. You need to demonstrate to a colleague exactly what prompt text reached the model. Where do you click, and why is that more convincing than the chat transcript?

**Practice:** open any event and write down, from what you see, the token counts in and out, the author of the message, and the duration of the LLM call.

## 6) Running it as a service

**Why this matters:** the console and the browser are for you; an API server is what lets another system — a frontend, a backend, a scheduler — actually call your agent.

The third way to run an agent is:

```bash
adk API server
```

This starts a FastAPI-based API server for the agent. *FastAPI* is a Python web framework for building HTTP APIs; ADK generates the server for you, so a deployable backend exists as soon as the agent does. The server defaults to port **8000**, and in the demonstration that port was already taken by the web interface, so a separate port — **8003** — was assigned. This is a general ports lesson: a port can only be bound by one process at a time, so a second service needs a second number.

Opening the URL shows that the service is live and that API endpoints are available; the root path itself does not show details. With this, the three ways to run an agent resolve into a practical story: you can run the agent via the available endpoints, from your own backend, or integrated into an existing backend — and as you build the agent, your backend is being created along with it.

How to actually call those endpoints to run the agent, and how to integrate it from your own backend, is not covered here.

**Terms**
| Term | Meaning |
|---|---|
| API server | ADK's automatically generated FastAPI service exposing endpoints for the agent |
| port | A numbered channel on a machine; one process per port at a time |
| FastAPI | A Python framework for HTTP APIs |

**Check yourself**
1. Why did the API server need a port other than 8000 in the demonstration?
2. What does the API server give you that `adk run` does not?
3. You want a web frontend and a nightly batch job to both use the same agent. Which run mode do you choose, and why?

**Practice:** list the three ports/commands involved in this section and the previous one, and state which process owns which.

## 7) Changing the model without changing the agent

**Why this matters:** a free tier that is "on and off" is not a foundation for a project, and provider lock-in is the usual reason teams rewrite working code. A one-line change removes both problems.

ADK is "primarily built around Gemini models" — Google wants you to live in its ecosystem — but you are not tied to it. ADK has a strong integration with **LiteLLM**, a library that lets your code talk to **100 plus** LLM providers through one standard interface. Without LiteLLM, every provider ships its own SDK and its own calling code; with it, switching models is a one-line change. LiteLLM's repository has around **61,000** GitHub stars, and its popularity with companies is why ADK integrates with it strongly.

The demonstrated switch from Gemini to an OpenAI model:

```bash
pip install litellm
```

1. In the code file, replace the model line with the LiteLLM model line, specifying **GPT-4O**.
2. Import LiteLLM if the import is missing.
3. Go to `platform.openai.com` → API keys → create a new secret key (a 30-day expiry was chosen).
4. Put the key in the same `.env` file where API keys are stored, under the OpenAI API key name, and save.
5. Run the agent again from the web UI, open events, start a new session, and ask "Hi, who are you".

The reply was "Hello I am a helpful assistant", and to "Are you from OpenAI" it answered "Yes I am created by OpenAI". The instructor's summary is the mental model to keep: "Agent is still the same but your model has changed." Note the practical detail — a new session was started, because the model is part of how the agent is constructed and old history belongs to the old configuration. If the OpenAI model misbehaves on the first run in the web UI, running it again is the demonstrated remedy.

**Context:** the model line is a *reference to a model*, resolved at call time by the library, so swapping the reference redirects every subsequent LLM call the agent makes. Prompts, instructions and session plumbing stay exactly as they were.

**Terms**
| Term | Meaning |
|---|---|
| LiteLLM | A library that lets your code talk to 100+ LLM providers through one standard interface |
| provider | The company or runtime serving a model, e.g. Google, OpenAI, Anthropic, or a local runtime like Ollama |

**Check yourself**
1. What exactly changes in your project when you switch from Gemini to GPT-4O through LiteLLM, and what stays the same?
2. Why is the API key written to `.env` instead of into the model line in `agent.py`?
3. Your Gemini free tier keeps returning 503s during a demo. Which is the smaller change: retrying per request, or moving to another provider — and what does each cost you?

**Practice:** write the ordered checklist (commands, files, websites) for moving an existing Gemini-based agent to an Anthropic model, keeping every step in the same shape as the OpenAI switch above.

## 8) Tuning how the model behaves

**Why this matters:** the same model can be terse or rambling, cheap or expensive, purely because of two numbers — and setting them on the agent means every run inherits them.

The agent's model carries configuration, and two parameters are demonstrated. **Temperature** controls randomness in the model's output; the demonstrated agent's default is **0.3**, a fairly conservative setting. **Max output token** limits how many tokens the model is allowed to produce; the demonstrated default is **800**. A *token* is the unit models read and generate — roughly a word fragment — and it is both the billing unit and the length limit.

The change is made by copying the configuration snippet into the code, taking the import from `google.
