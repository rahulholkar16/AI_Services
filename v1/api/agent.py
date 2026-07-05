from fastapi import APIRouter, HTTPException
from app.schemas.agent import AgentRequest, AgentResponse, CodeBlockSchema
from app.github.getRepo import set_repository
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
import app.state as state
import re
from typing import Optional

router = APIRouter();
MAX_QUESTION_CHARS = 2000


def trim_question(question: str) -> str:
    question = question.strip()
    if len(question) <= MAX_QUESTION_CHARS:
        return question
    return (
        question[:MAX_QUESTION_CHARS].rstrip()
        + "\n... [question truncated to stay within model token limits]"
    )


def is_token_limit_error(error: Exception) -> bool:
    message = str(error).lower()
    return (
        "request too large" in message
        or "tokens per minute" in message
        or "rate_limit_exceeded" in message
    )

def fix_messages(messages: list) -> list:
    """
    Empty tool messages remove karo — Groq crash karta hai inpe.
    """
    fixed = []
    for msg in messages:
        # ToolMessage empty hai toh fix karo
        if isinstance(msg, ToolMessage):
            if not msg.content or msg.content.strip() == "":
                msg.content = "No results found."  # ✅ Empty nahi
        
        # AIMessage mein empty content fix karo
        if isinstance(msg, AIMessage):
            if not msg.content and not msg.tool_calls:
                continue  # Skip karo
        
        fixed.append(msg)
    return fixed

def extract_tool_calls(messages: list) -> list:
    """
    Extract tool calls from the latest turn (since the last HumanMessage).
    """
    tool_calls = []
    last_human_idx = -1
    for idx in range(len(messages) - 1, -1, -1):
        if isinstance(messages[idx], HumanMessage):
            last_human_idx = idx
            break

    if last_human_idx != -1:
        for idx in range(last_human_idx + 1, len(messages)):
            msg = messages[idx]
            if isinstance(msg, AIMessage) and getattr(msg, "tool_calls", None):
                for tc in msg.tool_calls:
                    tool_calls.append({
                        "name": tc.get("name", ""),
                        "args": str(tc.get("args", ""))
                    })
    return tool_calls


def parse_code_blocks(answer: str) -> tuple[str, Optional[CodeBlockSchema]]:
    """
    Parse markdown code blocks out of the text response.
    """
    pattern = r"```([a-zA-Z0-9+#-]+)?\n([\s\S]+?)\n```"
    match = re.search(pattern, answer)

    if match:
        lang = match.group(1) or "tsx"
        code = match.group(2)
        explanation = re.sub(pattern, "", answer).strip()
        explanation = re.sub(r"\n{3,}", "\n\n", explanation)
        return explanation, CodeBlockSchema(language=lang, code=code)
    
    return answer, None


@router.post("/agent/chat", response_model=AgentResponse)
async def agent_chat(request: AgentRequest):
    try:
        set_repository(request.repo_url);
        session_id = request.session_id or request.repo_url
        config = {"configurable": {"thread_id": session_id}}
        input_messages = fix_messages([
            HumanMessage(content=trim_question(request.question))
        ])
        try:
            response = await state.agent.ainvoke({
                "messages": input_messages
            }, config=config)
        except Exception as e:
            if not is_token_limit_error(e):
                raise

            retry_config = {
                "configurable": {
                    "thread_id": f"{session_id}:token-limit-retry"
                }
            }
            response = await state.agent.ainvoke({
                "messages": input_messages
            }, config=retry_config)

        all_messages = fix_messages(response["messages"])
        answer = all_messages[-1].content

        # Extract tool calls and parse code blocks using helper functions
        tool_calls = extract_tool_calls(all_messages)
        explanation, code_block = parse_code_blocks(answer)

        return AgentResponse(
            answer=explanation,
            codeBlock=code_block,
            toolCalls=tool_calls
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
