from pydantic import BaseModel, Field;
from typing import List;
from app.state import State;
from app.services.llm import llm;

class Step(BaseModel):
   tool_name: str = Field(description="Tool to execute")
   input: str = Field(description="Input for the tool")


class PlannerSchema(BaseModel):
   task: str = Field(description="Overall task to perform")
   steps: List[Step] = Field(description="List of execution steps")

planner_llm = llm.with_structured_output(PlannerSchema);

async def planner_node (state: State):
   """
   It is Planning nodes.
   It Generate the Plan in form of Task and Steps.
   """

   prompt = f"""
You are an expert repository analysis planner.

Your job is to create an execution plan for answering a user's question about a GitHub repository.

Available tools:

1. list_directory
   - List files and folders.

2. search_file
   - Find files by name.

3. read_file
   - Read file contents.

4. search_codebase
   - Search for keywords, functions, classes, variables, or code snippets.

5. retrieve_chunks
   - Retrieve relevant context from the vector database.

Repository Path:
{state["repo_path"]}

User Question:
{state["user_query"]}

Instructions:

- Create a clear task.
- Break the task into logical steps.
- Each step must use one of the available tools.
- Order the steps from discovery → retrieval → analysis.
- Do not generate explanations or answers.
- Do not invent tool names.
- Return only the structured output matching the schema.

Examples:

Question:
"How does authentication work?"

Task:
"Explain authentication flow"

Steps:
1. search_codebase -> "auth"
2. search_codebase -> "jwt"
3. read_file -> "auth middleware file"
4. retrieve_chunks -> "authentication flow"


Question:
"What technologies are used in this repository?"

Task:
"Identify repository tech stack"

Steps:
1. retrieve_chunks -> "tech stack"
2. read_file -> "package.json"
3. read_file -> "README.md"

Generate the execution plan.
"""

   response = await planner_llm.ainvoke(prompt)

   return {
      "plan": response
   }
