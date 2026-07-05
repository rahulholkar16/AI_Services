from langgraph.graph import START, StateGraph;
from .state import State;
from .nodes import call_model, tool_node;
from langgraph.prebuilt import tools_condition;


async def build_graph(checkpointer):
    graph = StateGraph(State);

    graph.add_node("planner", call_model);
    graph.add_node("tools", tool_node);

    graph.add_edge(START, "planner");

    graph.add_conditional_edges(
        "planner",
        tools_condition,
    );

    graph.add_edge("tools", "planner");

    return graph.compile(checkpointer=checkpointer);