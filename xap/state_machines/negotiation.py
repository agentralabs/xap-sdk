"""Negotiation state machine: OFFER → COUNTER → ACCEPT/REJECT."""

from __future__ import annotations

from enum import Enum

from xap.errors import XAPStateError


class NegotiationState(str, Enum):
    OFFER = "OFFER"
    COUNTER = "COUNTER"
    ACCEPT = "ACCEPT"
    REJECT = "REJECT"


VALID_TRANSITIONS: dict[NegotiationState, list[NegotiationState]] = {
    NegotiationState.OFFER: [NegotiationState.COUNTER, NegotiationState.ACCEPT, NegotiationState.REJECT],
    NegotiationState.COUNTER: [NegotiationState.COUNTER, NegotiationState.ACCEPT, NegotiationState.REJECT],
    NegotiationState.ACCEPT: [],
    NegotiationState.REJECT: [],
}


class NegotiationStateMachine:
    """Enforces negotiation state transitions."""

    def __init__(self, max_rounds: int = 20) -> None:
        self._state = NegotiationState.OFFER
        self._round = 1
        self._max_rounds = max_rounds
        self._history: list[tuple[NegotiationState, NegotiationState]] = []

    def transition(self, to: NegotiationState) -> None:
        """Transition to a new state. Raises XAPStateError on invalid transition."""
        if to not in VALID_TRANSITIONS[self._state]:
            raise XAPStateError(
                f"Invalid transition: {self._state.value} → {to.value}"
            )
        if to == NegotiationState.COUNTER and self._round >= self._max_rounds:
            raise XAPStateError(
                f"Maximum rounds ({self._max_rounds}) reached — auto-reject"
            )
        self._history.append((self._state, to))
        self._state = to
        if to == NegotiationState.COUNTER:
            self._round += 1

    @property
    def current(self) -> NegotiationState:
        return self._state

    @property
    def round(self) -> int:
        return self._round

    @property
    def is_terminal(self) -> bool:
        return self._state in (NegotiationState.ACCEPT, NegotiationState.REJECT)

    @property
    def history(self) -> list[tuple[NegotiationState, NegotiationState]]:
        return list(self._history)
