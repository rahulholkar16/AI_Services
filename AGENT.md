# AI-Services — Implementation Status

Status: **In active development.** Tracks major implementation decisions so future work
(or future-you) doesn't have to rediscover context. Update this file as things change.

## Long-term memory

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
  - **Episode pruning**: `_prune_episodes` in `save_episode.py` runs as a fire-and-forget
    background task after each episode save. Caps at `MAX_EPISODES_PER_REPO = 100` per
    `(repo_id, user_id)`; below the cap it's a no-op. When over, deletes lowest-`importance`,
    then-oldest episodes first.

## Auth, rate limiting, reliability

- **Auth**: JWT middleware (`app/middleware/auth.py`) verifies better-auth tokens via JWKS,
  protects all routes. `user_id` comes from the verified token, never the request body.
- **Rate limiting**: per-user (`slowapi` + Redis) — `/agent/chat` 10/min, `/api/repo/index` 10/hour.
- **Connection pool**: `check=AsyncConnectionPool.check_connection` + `min_size=1` in
  `db_graph.py` — health-checks connections on checkout to avoid using dead ones
  ("server closed the connection unexpectedly").
- **Background task failures**: shared `log_task_exception` helper (`app/utils/task_utils.py`)
  attached via `task.add_done_callback(...)` on every fire-and-forget task (fact save,
  episode save, episode prune) so failures are logged instead of disappearing silently.
- **Logging**: structured `logging` (see `app/config/logging_config.py`, `dictConfig`-based)
  replaced `print()` throughout.

## Branch support

- Indexing (`/api/repo/index`) and chat (`/agent/chat`) both accept a `branch`. Pinecone
  namespace is `f"{repo_full_name}#{branch}"` when a branch is given, so different branches
  of the same repo index into separate namespaces (no data mixing).
- GitHub file/tree tools (`files_tool.py`) and RAG (`rag_tool.py`) read `branch` from graph
  `state`, not from an LLM-supplied tool argument — branch is a user/session-level choice,
  not something the model decides mid-conversation.
- Frontend has a branch-picker (searchable popup) shown right after a repo URL is submitted,
  before indexing starts.

## Async conversion (GitHub calls + Pinecone)

- All GitHub-hitting functions (`files_tool.py`: `get_default_branch`, `list_directory`,
  `read_file`, `search_file`, `search_code`; `chunker.py`: `get_repo_files`,
  `fetch_file_content`, `load_repo_documents`) converted from sync `requests` to
  `httpx.AsyncClient`, all `async def` now. `chunk_documents` stays sync (pure CPU, no I/O).
- `repo.py`'s `/tree` and `/info` routes also converted to `httpx`. Fixed a real bug in the
  process: `index_repo` was `async def` but used blocking `time.sleep()` — replaced with
  `asyncio.sleep()` (the old code froze the whole server for all users while one repo was
  indexing).
- **Pinecone migrated to native async** (`PineconeAsyncio` / `IndexAsyncio`, not the old
  `langchain_pinecone.PineconeVectorStore` sync wrapper):
  - `app/rag/vectorstore.py` — cached `PineconeAsyncio` client + `IndexAsyncio` handle
    (`get_index()`), plus `close_index()` called on app shutdown (aiohttp session cleanup
    in `main.py`'s lifespan).
  - `app/rag/upsert.py` — `embed_and_build_vectors()` replaces LangChain's automatic
    embed-on-add; embeds a batch via `get_embeddings().aembed_documents()` and builds
    Pinecone-ready `{id, values, metadata}` dicts. Since raw Pinecone doesn't store text,
    the chunk's content is stored under `metadata["text"]` manually.
  - `app/tools/rag_tool.py`'s `search_codebase` — embeds the query via `aembed_query`,
    calls `index.query(...)` directly. Note: relevance score changed from
    `(1 - score) * 100` (old langchain distance-based) to `score * 100` (raw Pinecone
    cosine similarity — higher score already means more similar, no inversion needed).
  - Installed version is `pinecone==7.3.0`, whose async client class is named
    `PineconeAsyncio` (not `AsyncPinecone` — that name is from a newer release not
    installed here; watch for this if bumping the pinecone package later).
  - `langchain-pinecone` is no longer imported anywhere but is still listed as a
    dependency — harmless, can be removed later.

## Open / parked for later

- [ ] **Redis-based caching** — discussed adding a `cache_get`/`cache_set` helper backed by
      Redis (already used for rate limiting) to cache `get_default_branch()` (and possibly
      the `/tree`/`/info` GitHub calls) to cut down repeat GitHub API hits. **Not implemented
      yet** — got sidetracked into the async conversion + Pinecone migration above. When
      picking this up: since the relevant functions are now `async def` (using `httpx`),
      the cache helper should use `redis.asyncio`, not the sync `redis` client discussed
      earlier when these functions were still sync.
- [ ] **Migrations decoupled from app startup** — `checkpointer.setup()` / `store.setup()`
      currently run every time the app starts (in `init_agent()`, `db_graph.py`). Harmless
      as a single instance, but risks a race condition if multiple replicas start
      concurrently in production (concurrent `CREATE TABLE IF NOT EXISTS`). Plan: move
      `setup()` calls into a standalone one-time script (e.g. `scripts/migrate.py`) run
      once in the deploy pipeline before app instances start; app startup then only opens
      the pool, assumes tables already exist. Not urgent at current (single-instance) scale.
