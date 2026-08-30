"""Request/response types for the DMAS discovery protocol (Ding et al. III-B.1)."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Request:
    """Stands in for the user request (triangle-right symbol) / P(triangle-right)."""

    capability: str
    payload: str


@dataclass(frozen=True)
class Response:
    """Stands in for an SA's response, tagged terminal/non-terminal per III-B.1.

    A non-terminal response carries no payload, only the SA ids to forward
    to next (SA(r) in Algorithm 1). A terminal response carries the SA's
    stub result and no further candidates.
    """

    sa_id: str
    is_terminal: bool
    payload: str | None = None
    forwarded: list[str] = field(default_factory=list)
