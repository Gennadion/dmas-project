"""Service discovery (Ding et al. III-B.1), as a single parameterized
LangGraph StateGraph. The paper presents depth-first (Algorithm 1, a LIFO
stack) and breadth-first (a queue) as symmetric strategies differing only
in *which end* of the candidate list is popped -- so one graph handles
both, selected via `strategy` in the initial state rather than two graphs.

Graph shape:

    select_candidates (FirstSelect, runs once)
        -> [tau or no candidates?] -> END
        -> pop_and_communicate (Pop + Com(u, s))
            -> [IsTerminal?] -> record_response -> back to the tau check
                              -> push_candidates (Push(S, SA(r))) -> back to the tau check
"""

from __future__ import annotations

import time
from typing import Literal, TypedDict

from langgraph.graph import END, StateGraph

from dmas.termination import Predicate, TerminationContext
from dmas.topology import ServiceNetwork
from dmas.types import Request, Response

Strategy = Literal["dfs", "bfs"]


class DiscoveryState(TypedDict):
    request: Request
    topology: ServiceNetwork
    strategy: Strategy
    termination: Predicate
    candidates: list[str]
    responses: list[Response]
    call_count: int
    start_time: float
    last_response: Response | None
    trace: list[str]


def _select_candidates(state: DiscoveryState) -> dict:
    candidates = state["topology"].first_select(state["request"])
    trace = state["trace"] + [f"FirstSelect(u, req) -> {candidates}"]
    return {"candidates": candidates, "trace": trace}


def _pop_and_communicate(state: DiscoveryState) -> dict:
    candidates = list(state["candidates"])
    # DFS (Algorithm 1): LIFO stack, pop from the end.
    # BFS: queue, pop from the front. Push always appends to the end (see
    # _push_candidates), so this is the only place the two strategies differ.
    sa_id = candidates.pop() if state["strategy"] == "dfs" else candidates.pop(0)

    response = state["topology"].communicate(sa_id, state["request"])

    if response.is_terminal:
        step = f"Com(u, {sa_id}) -> terminal: {response.payload}"
    else:
        step = f"Com(u, {sa_id}) -> forward -> {response.forwarded}"
    if response.commitment:
        c = response.commitment
        step += f"  [req {c.request_id.hex()[:10]}, resp {c.response_id.hex()[:10]}, eta {c.eta_wei} wei]"

    return {
        "candidates": candidates,
        "call_count": state["call_count"] + 1,
        "last_response": response,
        "trace": state["trace"] + [step],
    }


def _record_response(state: DiscoveryState) -> dict:
    return {"responses": state["responses"] + [state["last_response"]]}


def _push_candidates(state: DiscoveryState) -> dict:
    return {"candidates": state["candidates"] + state["last_response"].forwarded}


def _route_after_pop(state: DiscoveryState) -> str:
    return "record_response" if state["last_response"].is_terminal else "push_candidates"


def _route_after_termination_check(state: DiscoveryState) -> str:
    ctx = TerminationContext(
        responses=state["responses"],
        call_count=state["call_count"],
        elapsed=time.monotonic() - state["start_time"],
    )
    if not state["candidates"] or state["termination"](ctx):
        return END
    return "pop_and_communicate"


def build_discovery_graph():
    graph = StateGraph(DiscoveryState)
    graph.add_node("select_candidates", _select_candidates)
    graph.add_node("pop_and_communicate", _pop_and_communicate)
    graph.add_node("record_response", _record_response)
    graph.add_node("push_candidates", _push_candidates)

    graph.set_entry_point("select_candidates")

    termination_map = {"pop_and_communicate": "pop_and_communicate", END: END}
    graph.add_conditional_edges("select_candidates", _route_after_termination_check, termination_map)
    graph.add_conditional_edges("record_response", _route_after_termination_check, termination_map)
    graph.add_conditional_edges("push_candidates", _route_after_termination_check, termination_map)

    graph.add_conditional_edges(
        "pop_and_communicate",
        _route_after_pop,
        {"record_response": "record_response", "push_candidates": "push_candidates"},
    )

    return graph.compile()


_COMPILED_GRAPH = build_discovery_graph()


def run_discovery(
    request: Request,
    topology: ServiceNetwork,
    strategy: Strategy,
    termination: Predicate,
) -> DiscoveryState:
    initial_state: DiscoveryState = {
        "request": request,
        "topology": topology,
        "strategy": strategy,
        "termination": termination,
        "candidates": [],
        "responses": [],
        "call_count": 0,
        "start_time": time.monotonic(),
        "last_response": None,
        "trace": [],
    }
    return _COMPILED_GRAPH.invoke(initial_state)
