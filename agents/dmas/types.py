"""Request/response types for the DMAS discovery protocol (Ding et al. III-B.1)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field


def canonical_json(obj) -> bytes:
    """Deterministic encoding, so both sides of Com(u, s) hash identical bytes."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")


@dataclass(frozen=True)
class Request:
    """Stands in for the user request (triangle-right symbol) / P(triangle-right)."""

    capability: str
    payload: str

    def to_bytes(self) -> bytes:
        return canonical_json({"capability": self.capability, "payload": self.payload})

    @classmethod
    def from_bytes(cls, data: bytes) -> Request:
        return cls(**json.loads(data))


@dataclass(frozen=True)
class Commitment:
    """On-chain evidence of one Com(u, s) exchange (III-B.2): the ids of the
    request/response commitments on CommunicationLedger and the condition
    eta (wei) the PA paid to release the response key."""

    request_id: bytes
    response_id: bytes
    eta_wei: int


@dataclass(frozen=True)
class Response:
    """Stands in for an SA's response, tagged terminal/non-terminal per III-B.1.

    A non-terminal response carries no payload, only the SA ids to forward
    to next (SA(r) in Algorithm 1). A terminal response carries the SA's
    stub result and no further candidates. `commitment` is set only when the
    response was obtained through the on-chain protocol; it is the PA's
    non-repudiation evidence and is not part of the encrypted response itself.
    """

    sa_id: str
    is_terminal: bool
    payload: str | None = None
    forwarded: list[str] = field(default_factory=list)
    commitment: Commitment | None = None

    def to_bytes(self) -> bytes:
        return canonical_json(
            {
                "sa_id": self.sa_id,
                "is_terminal": self.is_terminal,
                "payload": self.payload,
                "forwarded": self.forwarded,
            }
        )

    @classmethod
    def from_bytes(cls, data: bytes) -> Response:
        return cls(**json.loads(data))
