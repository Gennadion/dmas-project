from dmas.discovery import run_discovery
from dmas.termination import max_communications
from dmas.topology import example_topology
from dmas.types import Request

NEVER = max_communications(1000)


def test_dfs_visits_in_stack_order():
    result = run_discovery(Request("code", "payload"), example_topology(), "dfs", NEVER)
    ids = [r.sa_id for r in result["responses"]]
    # LIFO: the last child pushed is the first one popped.
    assert ids == ["term-code-3", "term-code-2", "term-code-1"]


def test_bfs_visits_in_queue_order():
    result = run_discovery(Request("code", "payload"), example_topology(), "bfs", NEVER)
    ids = [r.sa_id for r in result["responses"]]
    # FIFO: children are visited in the order they were forwarded.
    assert ids == ["term-code-1", "term-code-2", "term-code-3"]


def test_termination_predicate_halts_discovery_early():
    result = run_discovery(Request("code", "payload"), example_topology(), "dfs", max_communications(2))

    assert result["call_count"] == 2
    assert [r.sa_id for r in result["responses"]] == ["term-code-3"]


def test_first_select_falls_back_to_all_routing_agents():
    # No routing SA advertises "unknown-capability", so FirstSelect should
    # fall back to every routing agent rather than returning nothing.
    result = run_discovery(Request("unknown-capability", "payload"), example_topology(), "dfs", NEVER)
    assert "FirstSelect(u, req) -> ['router-data', 'router-code']" in result["trace"]
