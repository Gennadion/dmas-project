from dmas.service_agent import ServiceAgent
from dmas.types import Request


def test_routing_agent_forwards_to_children():
    sa = ServiceAgent("router", "code", children=["a", "b"])
    response = sa.handle(Request("code", "payload"))

    assert response.is_terminal is False
    assert response.forwarded == ["a", "b"]
    assert response.payload is None


def test_terminal_agent_returns_a_payload():
    sa = ServiceAgent("term", "code")
    response = sa.handle(Request("code", "payload"))

    assert response.is_terminal is True
    assert response.forwarded == []
    assert response.payload is not None
