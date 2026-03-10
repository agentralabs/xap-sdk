"""Outcome state machine: 7 states from verity-outcomes Rust crate."""

from __future__ import annotations

from enum import Enum

from xap.errors import XAPStateError


class OutcomeClassification(str, Enum):
    SUCCESS = "SUCCESS"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"
    DISPUTED = "DISPUTED"
    REVERSED = "REVERSED"
    TIMEOUT = "TIMEOUT"
    PARTIAL = "PARTIAL"


VALID_TRANSITIONS: dict[OutcomeClassification, list[OutcomeClassification]] = {
    OutcomeClassification.UNKNOWN: [
        OutcomeClassification.SUCCESS,
        OutcomeClassification.FAIL,
        OutcomeClassification.PARTIAL,
        OutcomeClassification.TIMEOUT,
        OutcomeClassification.DISPUTED,
        OutcomeClassification.UNKNOWN,
    ],
    OutcomeClassification.SUCCESS: [
        OutcomeClassification.REVERSED,
    ],
    OutcomeClassification.FAIL: [
        OutcomeClassification.REVERSED,
    ],
    OutcomeClassification.PARTIAL: [
        OutcomeClassification.REVERSED,
    ],
    OutcomeClassification.DISPUTED: [
        OutcomeClassification.SUCCESS,
        OutcomeClassification.FAIL,
        OutcomeClassification.PARTIAL,
    ],
    OutcomeClassification.TIMEOUT: [
        OutcomeClassification.DISPUTED,
    ],
    OutcomeClassification.REVERSED: [],
}


class OutcomeStateMachine:
    """Enforces Verity outcome state transitions."""

    def __init__(self) -> None:
        self._state = OutcomeClassification.UNKNOWN
        self._history: list[tuple[OutcomeClassification, OutcomeClassification]] = []

    def transition(self, to: OutcomeClassification) -> None:
        """Transition to a new state. Raises XAPStateError on invalid transition."""
        if to not in VALID_TRANSITIONS[self._state]:
            raise XAPStateError(
                f"Invalid transition: {self._state.value} → {to.value}"
            )
        self._history.append((self._state, to))
        self._state = to

    @property
    def current(self) -> OutcomeClassification:
        return self._state

    @property
    def is_terminal(self) -> bool:
        return self._state == OutcomeClassification.REVERSED

    @property
    def history(self) -> list[tuple[OutcomeClassification, OutcomeClassification]]:
        return list(self._history)
