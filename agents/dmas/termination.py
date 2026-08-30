"""Termination predicate tau (Ding et al. III-B.1.c).

The paper defines tau as "a conjunction or disjunction over a configurable
set of atomic predicates" such as: fulfillment of the request (e.g. at
least N viable options), an SA-communication count threshold, a wall-clock
timeout, or an explicit human intervention signal. This module implements
each atomic predicate plus any_of/all_of composition.
"""

from dataclasses import dataclass
from typing import Callable

from dmas.types import Response


@dataclass(frozen=True)
class TerminationContext:
    responses: list[Response]
    call_count: int
    elapsed: float
    human_signal: bool = False


Predicate = Callable[[TerminationContext], bool]


def min_terminal_responses(n: int) -> Predicate:
    return lambda ctx: len(ctx.responses) >= n


def max_communications(n: int) -> Predicate:
    return lambda ctx: ctx.call_count >= n


def timeout(seconds: float) -> Predicate:
    return lambda ctx: ctx.elapsed >= seconds


def human_intervention() -> Predicate:
    return lambda ctx: ctx.human_signal


def any_of(*predicates: Predicate) -> Predicate:
    return lambda ctx: any(p(ctx) for p in predicates)


def all_of(*predicates: Predicate) -> Predicate:
    return lambda ctx: all(p(ctx) for p in predicates)
