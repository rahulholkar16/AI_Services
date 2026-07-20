from langgraph.graph import START, StateGraph;
from .state import State;
from .nodes import call_model, tool_node, compact_message;
from langgraph.prebuilt import tools_condition;


async def build_graph(checkpointer):
    graph = StateGraph(State);

    graph.add_node("compact", compact_message)
    graph.add_node("planner", call_model);
    graph.add_node("tools", tool_node);

    graph.add_edge(START, "compact");
    graph.add_edge("compact", "planner");

    graph.add_conditional_edges(
        "planner",
        tools_condition,
    );

    graph.add_edge("tools", "compact");

    return graph.compile(checkpointer=checkpointer);