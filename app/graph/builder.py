from langgraph.graph import START, END, StateGraph;
from .state import State;
from .nodes import call_model, tool_node, compact_message, retrieve_memory, write_memory;
from langgraph.prebuilt import tools_condition;


def route_after_planner(state: State) -> str:
    result = tools_condition(state)
    return "tools" if result == "tools" else "write_memory"


async def build_graph(checkpointer, store):
    graph = StateGraph(State);

    graph.add_node("compact", compact_message)
    graph.add_node("retrieve_memory", retrieve_memory)
    graph.add_node("planner", call_model);
    graph.add_node("tools", tool_node);
    graph.add_node("write_memory", write_memory)

    graph.add_edge(START, "retrieve_memory");
    graph.add_edge("retrieve_memory", "compact");
    graph.add_edge("compact", "planner");

    graph.add_conditional_edges(
        "planner",
        route_after_planner,
        {"tools": "tools", "write_memory": "write_memory"},
    );

    graph.add_edge("tools", "compact");
    graph.add_edge("write_memory", END)

    return graph.compile(checkpointer=checkpointer, store=store);