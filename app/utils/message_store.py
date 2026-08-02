import json
from typing import Optional

from sqlalchemy import text

from app.config.db import AsyncSessionLocal


async def get_session_id_for_thread(thread_id: str) -> Optional[str]:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            text('SELECT id FROM chat_sessions WHERE "threadId" = :thread_id'),
            {"thread_id": thread_id},
        )
        row = result.first()
        return row[0] if row else None


async def get_or_create_session_id(thread_id: str, repo_id: str, title: str) -> Optional[str]:
    
    existing = await get_session_id_for_thread(thread_id)
    if existing:
        return existing

    if not repo_id:
        return None

    trimmed_title = (title or "New chat").strip()
    if len(trimmed_title) > 80:
        trimmed_title = trimmed_title[:77] + "..."

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            text(
                """
                INSERT INTO chat_sessions (id, "repoId", "threadId", title, "createdAt", "updatedAt")
                VALUES (gen_random_uuid(), :repo_id, :thread_id, :title, now(), now())
                ON CONFLICT ("threadId") DO UPDATE SET "threadId" = EXCLUDED."threadId"
                RETURNING id
                """
            ),
            {"repo_id": repo_id, "thread_id": thread_id, "title": trimmed_title},
        )
        row = result.first()
        await db.commit()
        return row[0] if row else None


async def save_message(
    session_id: str,
    role: str,
    content: str,
    tool_calls: Optional[list] = None,
) -> None:
    """role must be one of: user | assistant | tool"""
    if not content and not tool_calls:
        return

    async with AsyncSessionLocal() as db:
        await db.execute(
            text(
                """
                INSERT INTO messages (id, "sessionId", role, content, "toolCalls", "createdAt")
                VALUES (gen_random_uuid(), :session_id, CAST(:role AS "ROLE"), :content, CAST(:tool_calls AS jsonb), now())
                """
            ),
            {
                "session_id": session_id,
                "role": role,
                "content": content or "",
                "tool_calls": json.dumps(tool_calls) if tool_calls else None,
            },
        )
        await db.execute(
            text('UPDATE chat_sessions SET "updatedAt" = now() WHERE id = :session_id'),
            {"session_id": session_id},
        )
        await db.commit()


_DEFAULT_TITLES = {"new conversation", "new chat"}


async def generate_and_save_title(session_id: str, question: str) -> None:
    
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                text('SELECT title FROM chat_sessions WHERE id = :id'),
                {"id": session_id},
            )
            row = result.first()
            if not row:
                return
            current_title = (row[0] or "").strip().lower()
            if current_title not in _DEFAULT_TITLES:
                return

        from app.llm import llm
        prompt = (
            "Summarize the following user question into a short chat title "
            "of 3 to 6 words. Plain text only \u2014 no quotes, no markdown, "
            "no trailing period, no emoji. Just the title.\n\n"
            f"Question: {question.strip()[:500]}"
        )

        response = await llm.ainvoke(prompt)
        raw_title = response.content if hasattr(response, "content") else str(response)
        if isinstance(raw_title, list):
            raw_title = " ".join(
                block.get("text", "") if isinstance(block, dict) else str(block)
                for block in raw_title
            )

        title = (raw_title or "").strip().strip('"').strip("'").strip()
        if not title:
            return
        if len(title) > 80:
            title = title[:77] + "..."

        async with AsyncSessionLocal() as db:
            await db.execute(
                text('UPDATE chat_sessions SET title = :title WHERE id = :id'),
                {"title": title, "id": session_id},
            )
            await db.commit()
    except Exception as e:
        print(f"⚠️ Title generation failed for session {session_id}: {e}")
