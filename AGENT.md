# Long-Term Memory — Implementation Plan

Status: **Planning phase — not yet implemented.**
This file tracks the plan for adding long-term (cross-thread) memory to the agent.
Update this file as the plan changes or as steps get implemented.

## Goal

Currently the agent only has:
- **Short-term memory**: `AsyncPostgresSaver` (checkpointer) — scoped to a single thread.
- **Chat history log**: `app/utils/message_store.py` — raw messages saved to `chat_sessions` /
  `messages` tables, used for frontend history display only. The agent itself never reads from it.

We are adding a **Store**-based long-term memory layer, scoped per-repo, holding two kinds of memory:

- **Facts** — durable, overwritable key-value knowledge about a repo (e.g. "auth uses JWT",
  "tech stack is Next.js + Postgres"). One fact per key, latest write wins.
- **Episodes** — append-only log of past interactions (user question + agent's finding),
  semantically searchable, so the agent can recall "have I answered something like this before
  for this repo".

Namespaces: `(repo_id, "facts")` and `(repo_id, "episodes")` — repo-scoped so memory never leaks
across repos.

## Files to be created

### `app/config/db_store.py` — **new**
- Sets up `AsyncPostgresStore` (LangGraph) using the existing `CHECKPOINT_DATABASE_URL`
  (same Postgres instance the checkpointer already uses — no new infra).
- `init_store()` async context manager, calls `store.setup()` on startup.
- Configures embedding index (for episodes' semantic search) — facts don't need embedding
  since they're looked up by known keys.

## Files to be modified

### `app/state.py`
- Add `store = None` next to the existing `agent = None`.

### `app/config/db_graph.py`
- `init_agent()` also initializes the store via `init_store()`.
- Sets `state.store = store`.
- `build_graph(checkpointer, store)` — store now passed through to the graph.

### `app/graph/builder.py`
- Signature becomes `async def build_graph(checkpointer, store):`
- Two new nodes added: `retrieve_memory`, `write_memory`.
- New edge flow:
  - Before: `compact → planner → tools → compact`
  - After: `compact → retrieve_memory → planner → tools → compact`, with `write_memory`
    running after the planner's final response (before END).
- `graph.compile(checkpointer=checkpointer, store=store)`.

### `app/graph/nodes.py`
- New function `retrieve_memory(state, *, store)`:
  - Looks up facts + episodes for `state["repo_id"]`.
  - Injects them as a `SystemMessage` into the conversation before the planner runs.
- New function `write_memory(state, *, store)`:
  - Always logs an episode for the turn (user question + agent's answer).
  - Simple rule-based check (v1) decides if anything is fact-worthy and saves it;
    can be upgraded later to an LLM-based classifier (similar pattern to
    `app/utils/summarize_model.py`).
- Existing functions (`call_model`, `compact_message`, `tool_node`) are untouched.

## Files intentionally NOT touched

- `app/graph/state.py` — `repo_id` already exists in state, no new field needed.
- `app/utils/message_store.py` — separate concern (chat history for UI), unrelated to agent memory.
- `app/tools/*`, `app/rag/*`, `app/api/*` — no changes needed.

## Open decisions / follow-ups

- [ ] `write_memory` fact-detection is rule-based for v1 — revisit with an LLM classifier if needed.
- [ ] Decide if `write_memory` should run as a blocking graph step or as a fire-and-forget
      background task (similar to how title generation in `agent.py` uses `asyncio.create_task`)
      to avoid adding latency to the user-facing response.
- [ ] Fact key naming convention needs to be decided so facts overwrite cleanly instead of colliding.
