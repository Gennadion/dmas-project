from dmas.termination import (
    TerminationContext,
    all_of,
    any_of,
    human_intervention,
    max_communications,
    min_terminal_responses,
    timeout,
)
from dmas.types import Response


def _ctx(**kwargs):
    defaults = dict(responses=[], call_count=0, elapsed=0.0, human_signal=False)
    defaults.update(kwargs)
    return TerminationContext(**defaults)


def test_min_terminal_responses():
    pred = min_terminal_responses(2)
    assert not pred(_ctx(responses=[Response("a", True)]))
    assert pred(_ctx(responses=[Response("a", True), Response("b", True)]))


def test_max_communications():
    pred = max_communications(3)
    assert not pred(_ctx(call_count=2))
    assert pred(_ctx(call_count=3))


def test_timeout():
    pred = timeout(5.0)
    assert not pred(_ctx(elapsed=4.9))
    assert pred(_ctx(elapsed=5.1))


def test_human_intervention():
    pred = human_intervention()
    assert not pred(_ctx(human_signal=False))
    assert pred(_ctx(human_signal=True))


def test_any_of_is_a_disjunction():
    pred = any_of(min_terminal_responses(5), max_communications(2))
    assert pred(_ctx(call_count=2))
    assert not pred(_ctx(call_count=1))


def test_all_of_is_a_conjunction():
    pred = all_of(min_terminal_responses(1), max_communications(2))
    assert not pred(_ctx(responses=[Response("a", True)], call_count=1))
    assert pred(_ctx(responses=[Response("a", True)], call_count=2))
