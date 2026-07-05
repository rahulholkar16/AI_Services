from pydantic import BaseModel
from typing import Optional, List

class AgentRequest(BaseModel):
    repo_url: str
    question: str
    session_id: str

class CodeBlockSchema(BaseModel):
    language: str
    code: str

class ToolCallSchema(BaseModel):
    name: str
    args: Optional[str] = None

class AgentResponse(BaseModel):
    answer: str
    codeBlock: Optional[CodeBlockSchema] = None
    toolCalls: Optional[List[ToolCallSchema]] = None