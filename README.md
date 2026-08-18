# RepoMind AI Services

FastAPI backend for indexing GitHub repositories and chatting with an AI agent about their code. The service fetches repository files from GitHub, chunks and embeds them into Pinecone, and uses LangGraph/LangChain with Postgres-backed memory to stream agent responses over SSE.

## Features

- Index public or token-accessible GitHub repositories into a Pinecone vector index.
- Fetch repository metadata and filtered file trees for frontend views.
- Stream AI chat responses from `/agent/chat`.
- Persist conversation sessions and agent checkpoints in Postgres.
- Apply request authentication and Redis-backed rate limiting.

## Tech Stack

- Python 3.12
- FastAPI and Uvicorn
- LangChain and LangGraph
- PostgreSQL with SQLAlchemy, asyncpg, psycopg, and LangGraph checkpointing
- Pinecone vector store
- Google Generative AI embeddings and Gemini chat models
- Redis for rate limiting

## Getting Started

### 1. Install dependencies

Using uv:

```bash
uv sync
```

Or with pip:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure environment

Create a `.env` file in the project root:

```env
DATABASE_URL=postgresql://user:password@localhost:5432/repomind
CHECKPOINT_DATABASE_URL=postgresql://user:password@localhost:5432/repomind
REDIS_URL=redis://localhost:6379
FRONTEND_URL=http://localhost:3000

PINECONE_API_KEY=your-pinecone-api-key
GOOGLE_API_KEY=your-google-api-key
GEMINI_API_KEY=your-gemini-api-key

# Optional, but recommended for private repos or higher GitHub API limits.
GITHUB_TOKEN=your-github-token

# Optional
ENV=development
LOG_LEVEL=DEBUG
```

`DATABASE_URL` is used by the application database connection. `CHECKPOINT_DATABASE_URL` is used by LangGraph checkpointing and memory setup.

### 3. Run the API

```bash
uvicorn app.main:app --reload
```

The service starts at `http://127.0.0.1:8000`.

Health check:

```bash
curl http://127.0.0.1:8000/
```

Expected response:

```json
{"status":"ok"}
```

## API Endpoints

### `POST /api/repo/index`

Indexes a GitHub repository into Pinecone.

```json
{
  "repo_url": "https://github.com/owner/repo",
  "force": false
}
```

Set `force` to `true` to clear an existing namespace and re-index the repository.

### `POST /api/repo/tree`

Returns a filtered file tree for a GitHub repository.

```json
{
  "repo_url": "https://github.com/owner/repo"
}
```

### `POST /api/repo/info`

Returns basic repository metadata.

```json
{
  "repo_url": "https://github.com/owner/repo"
}
```

### `POST /agent/chat`

Streams agent responses as server-sent events.

```json
{
  "repo_url": "https://github.com/owner/repo",
  "question": "How is authentication implemented?",
  "thread_id": "thread-123",
  "repo_id": "repo-123"
}
```

Events include:

- `message`
- `tool_call`
- `tool_result`
- `done`
- `error`

## Project Structure

```text
app/
  api/          FastAPI routers
  config/       database, checkpoint, logging, and store setup
  graph/        LangGraph agent builder and nodes
  middleware/   auth and rate limiting
  rag/          chunking, embeddings, and Pinecone vector store
  tools/        repository file and RAG tools
  utils/        persistence, extraction, summarization, and helper utilities
history/        older or experimental implementation
test/           local test files
```

## Development Notes

- The Pinecone index name is `github-repo`.
- The embedding dimension is `768`.
- Repository indexing skips common build/cache folders and only includes supported source/documentation extensions.
- Auth expects JWKS from `${FRONTEND_URL}/api/auth/jwks`.
- Rate limits are configured in route decorators and backed by `REDIS_URL`.
