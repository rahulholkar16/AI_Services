# Long-Term Memory — Implementation Status

Status: **Implemented and in production use.**
Tracks the long-term (cross-thread) memory layer added to the agent, plus related
hardening work (auth, rate limiting, connection pooling). Update this file as things change.

## What exists

- **Short-term memory**: `AsyncPostgresSaver` (checkpointer) — scoped to a single thread.
- **Chat history log**: `app/utils/message_store.py` — raw messages saved to `chat_sessions` /
  `messages` tables, used for frontend history display only. The agent itself never reads from it.
- **Long-term memory**: `AsyncPostgresStore` (LangGraph), same Postgres instance as the
  checkpointer, holding two kinds of memory per `(repo_id, user_id)`:
  - **Facts** (`app/utils/save_fact.py`, `fact_extractor.py`) — durable, overwritable
    key-value knowledge about a repo (e.g. "tech_stack", "auth_mechanism"). Key = topic
    (LLM-extracted snake_case label), so a new fact on the same topic overwrites the old
    one instead of accumulating duplicates.
  - **Episodes** (`app/utils/save_episode.py`, `episodic_extractor.py`) — append-only log
    of meaningful events (bug fixes, decisions), each with an `importance` score (1-5).
    An LLM decides per-turn whether the interaction is worth storing (`should_store`) —
    trivial/greeting turns are skipped, not saved.
  - Namespace shape: `("repo", repo_id, "user", user_id, "facts"/"episodes")`.
  - Both retrieval (`retrieve_memory`) and writes (`write_memory`) in `app/graph/nodes.py`
    are wrapped in try/except so a memory failure never blocks the chat response.
  - Facts and episodes are both retrieved via semantic search (`query=` param) against the
    current question, not a blind recent-N grab.

## Reliability / hardening also done

- **Auth**: JWT middleware (`app/middleware/auth.py`) verifies better-auth tokens via JWKS,
  protects all routes. `user_id` comes from the verified token, never the request body.
- **Rate limiting**: per-user (`slowapi` + Redis) — `/agent/chat` 10/min, `/api/repo/index` 10/hour.
- **Connection pool**: `check=AsyncConnectionPool.check_connection` + `min_size=1` in
  `db_graph.py` — health-checks connections on checkout to avoid using dead ones
  ("server closed the connection unexpectedly").
- **Episode pruning**: `_prune_episodes` in `save_episode.py` runs as a fire-and-forget
  background task after each episode save. Caps at `MAX_EPISODES_PER_REPO = 100` per
  `(repo_id, user_id)`; below the cap it's a no-op. When over, deletes lowest-`importance`,
  then-oldest episodes first.
- **Background task failures**: shared `log_task_exception` helper (`app/utils/task_utils.py`)
  attached via `task.add_done_callback(...)` on every fire-and-forget task (fact save,
  episode save, episode prune) so failures are logged instead of disappearing silently.
- **Logging**: structured `logging` (see `app/config/logging_config.py`, `dictConfig`-based)
  replaced `print()` throughout.

## Open / parked for later

- [ ] **Migrations decoupled from app startup** — `checkpointer.setup()` / `store.setup()`
      currently run every time the app starts (in `init_agent()`, `db_graph.py`). Harmless
      as a single instance, but risks a race condition if multiple replicas start
      concurrently in production (concurrent `CREATE TABLE IF NOT EXISTS`). Plan: move
      `setup()` calls into a standalone one-time script (e.g. `scripts/migrate.py`) run
      once in the deploy pipeline before app instances start; app startup then only opens
      the pool, assumes tables already exist. **Decided to revisit later, not urgent yet
      at current (single-instance) scale.**
