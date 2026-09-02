# ATA — Agent Testing Agent

**Playwright for conversational agents.** ATA is a black-box, **outside-in** testing
framework for conversational agents. It talks to an agent the way a real user would —
over HTTP or WebSocket — and verifies that the agent behaves correctly across a range
of generated positive and negative scenarios. No access to the agent's source code,
prompts, or internals is required.

Unlike instrumentation-based eval tools, ATA does not wrap your agent in decorators or
SDKs. It talks to your agent over its real interface — an HTTP/WebSocket endpoint, or a
plain Python callable — runs real conversations, and evaluates the outcomes. It only ever
observes inputs and outputs; it never inspects internals. ATA is itself an agent — a
system of six coordinated LLM agents orchestrated with LangGraph, testing the agent under
test from the outside.

> This repository is the **framework** (an installable Python library). A separate
> server/UI that adds persistence, dashboards, and multi-user runs is layered on top
> of this library and lives elsewhere.

---

## Install

```bash
pip install ata          # or: uv add ata
```

Set the API key for whichever provider you'll drive ATA with:

```bash
export ANTHROPIC_API_KEY=sk-ant-...    # or OPENAI_API_KEY / GOOGLE_API_KEY / OPENROUTER_API_KEY
```

Requires Python 3.12+.

---

## Quick start

Describe the agent, its world, and how many scenarios to run in a single YAML file
(see [`examples/`](examples/) for complete ones), then:

```python
import asyncio
from ata import run_suite

report = asyncio.run(run_suite(open("examples/booking_agent.yaml").read()))

print(report["verdict_counts"])   # {'success': 4, 'failure': 1, ...}
print(report["metrics"])          # task completion, boundary adherence, ...
```

`run_suite` runs the whole pipeline in-process — no database, no broker, no
external services. It returns a plain report dict you can serialize, assert on in a
test, or render however you like.

### Testing a Python callable directly

No server to stand up: if your agent is a Python function or object, hand it straight
to ATA. Set `protocol: callable` in the YAML (no `url` needed) and pass the callable as
`agent=`. It may be sync or async, and take either `(message)` or `(message, history)`,
where `history` is the prior turns as `{"user": ..., "agent": ...}` dicts:

```python
async def my_agent(message: str, history: list[dict]) -> str:
    # your LangGraph graph, LangChain agent, LLM call, whatever
    return await my_graph.ainvoke(message, history)

report = asyncio.run(run_suite(open("config.yaml").read(), agent=my_agent))
```

This stays fully black-box — ATA only sees what the callable returns for each message.

---

## How it works

You provide a single YAML file: the **agent under test** (name, endpoint, protocol,
capabilities, known limitations), a **world_state** (the entities it knows, the catalog
it can offer, the rules it must follow, and read-only context), how many scenarios to
run, and which **LLM** drives ATA. ATA then:

1. **Generates** a frozen set of positive and negative scenarios from your world_state.
2. **Runs** each scenario as a live conversation against your agent's endpoint.
3. **Scores** each transcript against its assertions and applies a deterministic verdict flow.
4. **Probes** stateful successes with a follow-up conversation to confirm the change
   really persisted — and fires *defensive probes* to catch state corruption when an
   agent wrongly accepts an invalid request.
5. **Patches** world_state from each transcript (RFC 6902 JSON Patch) so later scenarios
   see the changes.
6. **Reports** quantitative metrics, per-scenario verdicts, and a failure analysis.

```
user YAML
  → OrchestratorAgent      parse + validate, load world_state
  → ScenarioGeneratorAgent generate all scenarios (frozen before execution)
  → for each scenario in DAG order:
      → UserSimulatorAgent      run the conversation via HTTP/WS
      → ScorerAgent             evaluate assertions → verdict
      → WorldStatePatcherAgent  transcript → JSON Patch → apply
  → ReporterAgent          synthesise the final report
```

### The metrics

The report quantifies six things rather than handing back a vague pass/fail:

| Metric | Question it answers |
|--------|---------------------|
| **Task completion** | Did it do what it was supposed to do? |
| **Boundary adherence** | Does it correctly refuse what it should refuse? |
| **Verification rate** | When it says it did something, did the state actually change? |
| **Constraint violations** | Which rules does it break the most? |
| **Recovery behavior** | On adversarial input, clean refusal vs. confused / error / info-leak? |
| **Conversation efficiency** | Avg turns to completion / to refusal? |

---

## The input YAML

See [`examples/booking_agent.yaml`](examples/booking_agent.yaml) (a stateful WebSocket
booking agent) and [`examples/faq_agent.yaml`](examples/faq_agent.yaml) (a stateless
HTTP FAQ agent) for complete, working files.

```yaml
agent_under_test:
  name: "CRM Booking Assistant"
  url: "wss://crm.example.com/chat"    # omit for protocol: callable
  protocol: websocket          # http | websocket | callable
  description: "Books appointments for registered customers..."
  capabilities: [appointment booking, customer lookup]
  known_limitations: [does not handle rescheduling]

world_state:
  entities:                    # actors the agent looks up (have attributes)
    - id: customer_1
      phone: "+33612345678"
      verified: true
  catalog:                     # the finite set it can offer / act on
    available_slots: ["2026-05-20T10:00", "2026-05-20T14:00"]
  constraints:                 # natural-language rules ATA deliberately crosses
    - "only verified entities can book"
  context:                     # read-only runtime facts
    current_time: "2026-05-16T08:00"
    language: "fr"

test_config:
  total: 20                    # must equal positive + negative
  positive: 14
  negative: 6

llm_config:
  provider: anthropic          # anthropic | openai | google | openrouter | ollama
  model: claude-sonnet-4-20250514
  # API keys come from the environment, never from this file.
```

Validation is strict: `total` must equal `positive + negative`, `total >= 1`, and the
reserved `rag` key must not be present (deferred to a future release).

---

## Public API

```python
from ata import (
    run_suite,          # async: YAML string -> report dict
    OrchestratorAgent,  # the LangGraph pipeline, if you want finer control
    parse_and_validate, # YAML string -> validated model (+ hash)
    create_llm_client,  # provider/model -> a unified LLM client
    compute_all_metrics,
    # domain models: WorldState, Scenario, Verdict, Assertion, Transcript, Turn, ...
)
```

Provider and model are chosen per run via `llm_config`. Anthropic, OpenAI, Google,
OpenRouter, and Ollama are supported behind one common `LLMClient` interface.

---

## Development

```bash
git clone https://github.com/Bissmella/ata
cd ata
uv sync --extra dev
uv run pytest            # unit tests mock the LLM — no API key needed
uv run ruff check .
```

---

## Project layout

```
ata/
  models/        domain models — world_state, suite, transcript, yaml_input
  agents/        the six ATA agents + the LangGraph orchestrator + graph state
  adapters/      HTTP and WebSocket protocol adapters (same Transcript out of both)
  llm/           common LLM interface (Anthropic / OpenAI / Google / OpenRouter / Ollama)
  services/      yaml parsing, placeholder resolution, execution DAG
  metrics.py     the six quantitative report metrics
examples/        ready-to-run YAML inputs
tests/           unit tests (LLM mocked)
```

---

## Roadmap

- [ ] `ata` CLI (`ata run config.yaml`) with CI-friendly exit codes
- [ ] Standalone HTML report renderer for local runs
- [ ] Scenario snapshot + LLM record/replay for reproducible, low-cost CI runs
- [ ] pytest plugin and GitHub Action

---

## What ATA is NOT

- Not a metric library, not an observability tool (no instrumentation, no SDK wrappers).
- Not a load-testing tool.
- Not a single prompt/response evaluator — it tests behavior over whole conversations.

---

## License

[Apache-2.0](LICENSE).
