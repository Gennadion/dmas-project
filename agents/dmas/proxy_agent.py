"""Proxy Agent (Ding et al. III-A.1.a, III-A.4): the user's stateful
interface to the runtime. Memory management is enforced exclusively on the
PA in the paper's design -- SAs are stateless -- so the PA is the only
place that accumulates context (Gamma(u)) across discovery runs.
"""

from dataclasses import dataclass, field

from dmas.discovery import DiscoveryState, Strategy, run_discovery
from dmas.termination import Predicate, any_of, max_communications, min_terminal_responses
from dmas.topology import ServiceNetwork
from dmas.types import Request, Response

DEFAULT_TERMINATION: Predicate = any_of(min_terminal_responses(3), max_communications(20))


@dataclass
class ProxyAgent:
    user_id: str
    topology: ServiceNetwork
    context: list[DiscoveryState] = field(default_factory=list)  # Gamma(u)

    def discover(
        self,
        request: Request,
        strategy: Strategy = "dfs",
        termination: Predicate = DEFAULT_TERMINATION,
    ) -> list[Response]:
        result = run_discovery(request, self.topology, strategy, termination)
        self.context.append(result)  # accumulate into Gamma(u)
        return result["responses"]
