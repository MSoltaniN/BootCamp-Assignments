"""A real LangGraph StateGraph wiring the nodes, with conditional edges for deny/clarify/unsupported.

Node order:
    authorize -> route -> [history_tool | research_tool] -> generate -> validate -> END

Conditional edges short-circuit straight to `generate` when authorization fails or the route needs
no tool, so a denied request physically cannot reach a retrieval node.
"""
from __future__ import annotations

from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from work.sec11_langgraph.workflow import (
    WorkflowState,
    authorize,
    emit_events,
    generate,
    history_tool,
    research_tool,
    route_query,
    validate_node,
)


class GraphState(TypedDict, total=False):
    """Only plain data crosses LangGraph's channel boundaries; the dataclass is rebuilt inside."""

    request: dict


def build_graph(*, adapter, con, retriever, principal_for, evidence_text: dict[str, str]):
    """Compile the graph. Dependencies are injected so nothing is global or shared between runs."""

    def _state(payload: dict) -> WorkflowState:
        return WorkflowState(**payload)

    def node_authorize(payload: GraphState) -> GraphState:
        state = _state(payload["request"])
        authorize(state, adapter)
        return {"request": state.__dict__}

    def node_route(payload: GraphState) -> GraphState:
        state = _state(payload["request"])
        if state.denied:
            state.add_trace("route", "skipped:denied")
        else:
            route_query(state)
        return {"request": state.__dict__}

    def node_history(payload: GraphState) -> GraphState:
        state = _state(payload["request"])
        history_tool(state, con)
        return {"request": state.__dict__}

    def node_research(payload: GraphState) -> GraphState:
        state = _state(payload["request"])
        research_tool(state, retriever, principal_for(state.user_id))
        return {"request": state.__dict__}

    def node_generate(payload: GraphState) -> GraphState:
        state = _state(payload["request"])
        generate(state)
        return {"request": state.__dict__}

    def node_validate(payload: GraphState) -> GraphState:
        state = _state(payload["request"])
        validate_node(state, evidence_text, extractive=True)
        return {"request": state.__dict__}

    graph = StateGraph(GraphState)
    graph.add_node("authorize", node_authorize)
    graph.add_node("route", node_route)
    graph.add_node("history_tool", node_history)
    graph.add_node("research_tool", node_research)
    graph.add_node("generate", node_generate)
    graph.add_node("validate", node_validate)

    graph.add_edge(START, "authorize")
    graph.add_edge("authorize", "route")

    def after_route(payload: GraphState) -> str:
        state = _state(payload["request"])
        if state.denied:
            return "generate"
        if state.route == "history":
            return "history_tool"
        if state.route == "research":
            return "research_tool"
        if state.route == "both":
            return "history_tool"        # history first, then research via the edge below
        return "generate"                # clarify / unsupported need no tool

    graph.add_conditional_edges("route", after_route,
                                {"history_tool": "history_tool", "research_tool": "research_tool",
                                 "generate": "generate"})

    def after_history(payload: GraphState) -> str:
        state = _state(payload["request"])
        return "research_tool" if state.route == "both" else "generate"

    graph.add_conditional_edges("history_tool", after_history,
                                {"research_tool": "research_tool", "generate": "generate"})
    graph.add_edge("research_tool", "generate")
    graph.add_edge("generate", "validate")
    graph.add_edge("validate", END)

    return graph.compile()


def run(compiled, **payload) -> WorkflowState:
    """Invoke the graph and rebuild the dataclass, so callers see a typed state."""
    final = compiled.invoke({"request": payload})
    return WorkflowState(**final["request"])


def topology(compiled) -> str:
    """Mermaid source of the compiled graph, for the architecture note."""
    return compiled.get_graph().draw_mermaid()
