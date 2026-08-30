"""Example SA registry: routing SAs delegating to terminal SAs.

Scaled-down stand-in for the paper's performance-section topology (4
routing agents x 7 terminal agents each, III-A/V-A) -- small enough to
read a full discovery trace, structured the same way so it's trivial to
grow later. This is an in-process stand-in for the on-chain
AgentRegistry/VAR (III-A.2); Step 4 replaces lookups here with resolve()
calls against the deployed contract.
"""

from dataclasses import dataclass

from dmas.service_agent import ServiceAgent
from dmas.types import Request


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
