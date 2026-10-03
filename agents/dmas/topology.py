"""Example SA registry: routing SAs delegating to terminal SAs.

Scaled-down stand-in for the paper's performance-section topology (4
routing agents x 7 terminal agents each, III-A/V-A) -- small enough to
read a full discovery trace, structured the same way so it's trivial to
grow later. This is the in-process stand-in for the on-chain
AgentRegistry/VAR (III-A.2), kept so the discovery graph can be tested
without a chain; `dmas.chain_topology.ChainTopology` is the on-chain one.
"""

from dataclasses import dataclass
from typing import Protocol

from dmas.service_agent import ServiceAgent
from dmas.types import Request, Response


class ServiceNetwork(Protocol):
    """What the discovery graph needs from an SA registry."""

    def first_select(self, request: Request) -> list[str]: ...

    def communicate(self, sa_id: str, request: Request) -> Response:
        """Com(u, s) with the SA identified by `sa_id`."""
        ...


@dataclass(frozen=True)
class Topology:
    agents: dict[str, ServiceAgent]

    def get(self, sa_id: str) -> ServiceAgent:
        return self.agents[sa_id]

    def routing_agents(self) -> list[ServiceAgent]:
        return [a for a in self.agents.values() if a.is_routing()]

    def first_select(self, request: Request) -> list[str]:
        """FirstSelect(u, triangle-right) (III-B.1.a): hardcoded-list match
        on capability, falling back to all routing agents if none match."""
        matches = [a.sa_id for a in self.routing_agents() if a.capability == request.capability]
        return matches or [a.sa_id for a in self.routing_agents()]

    def communicate(self, sa_id: str, request: Request) -> Response:
        """Com(u, s) stub: a plain call into the SA, no chain."""
        return self.get(sa_id).handle(request)


def example_topology() -> Topology:
    agents = {
        "router-data": ServiceAgent("router-data", "data", children=["term-data-1", "term-data-2"]),
        "term-data-1": ServiceAgent("term-data-1", "data"),
        "term-data-2": ServiceAgent("term-data-2", "data"),
        "router-code": ServiceAgent(
            "router-code", "code", children=["term-code-1", "term-code-2", "term-code-3"]
        ),
        "term-code-1": ServiceAgent("term-code-1", "code"),
        "term-code-2": ServiceAgent("term-code-2", "code"),
        "term-code-3": ServiceAgent("term-code-3", "code"),
    }
    return Topology(agents)
