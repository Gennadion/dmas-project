"""Service Agent (Ding et al. III-A.1.b): stateless, executes one request at
a time, either forwarding (SA(r) in Algorithm 1) or terminating.

This is only the SA's off-chain reasoning -- deterministic, no LLM yet.
On-chain identity and the Com(u, s) commitment protocol (III-B.2) wrap it
in dmas.commitment.ServiceEndpoint; the in-process Topology calls it
directly.
"""

from dataclasses import dataclass, field

from dmas.types import Request, Response


@dataclass(frozen=True)
class ServiceAgent:
    sa_id: str
    capability: str
    children: list[str] = field(default_factory=list)

    def is_routing(self) -> bool:
        """A routing SA has children to delegate to; a terminal SA does not."""
        return len(self.children) > 0

    def handle(self, request: Request) -> Response:
        """Stub reasoning: deterministic, no LLM."""
        if self.is_routing():
            return Response(sa_id=self.sa_id, is_terminal=False, forwarded=list(self.children))
        return Response(
            sa_id=self.sa_id,
            is_terminal=True,
            payload=f"result[{self.sa_id}] for '{request.payload}'",
        )
