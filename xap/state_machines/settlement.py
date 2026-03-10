"""Settlement state machine: 12 states from the SettlementIntent schema."""

from __future__ import annotations

from enum import Enum

from xap.errors import XAPStateError


class SettlementState(str, Enum):
    PENDING_LOCK = "PENDING_LOCK"
    FUNDS_LOCKED = "FUNDS_LOCKED"
    EXECUTING = "EXECUTING"
    PENDING_VERIFICATION = "PENDING_VERIFICATION"
    PENDING_RELEASE = "PENDING_RELEASE"
    SETTLED = "SETTLED"
    REFUNDED = "REFUNDED"
    PARTIAL = "PARTIAL"
    TIMEOUT = "TIMEOUT"
    FAILED_LOCK = "FAILED_LOCK"
    RELEASE_FAILED = "RELEASE_FAILED"
    DISPUTED = "DISPUTED"


VALID_TRANSITIONS: dict[SettlementState, list[SettlementState]] = {
    SettlementState.PENDING_LOCK: [
        SettlementState.FUNDS_LOCKED,
        SettlementState.FAILED_LOCK,
    ],
    SettlementState.FUNDS_LOCKED: [
        SettlementState.EXECUTING,
        SettlementState.REFUNDED,
        SettlementState.TIMEOUT,
    ],
    SettlementState.EXECUTING: [
        SettlementState.PENDING_VERIFICATION,
        SettlementState.TIMEOUT,
    ],
    SettlementState.PENDING_VERIFICATION: [
        SettlementState.PENDING_RELEASE,
        SettlementState.REFUNDED,
        SettlementState.PARTIAL,
        SettlementState.TIMEOUT,
    ],
    SettlementState.PENDING_RELEASE: [
        SettlementState.SETTLED,
        SettlementState.RELEASE_FAILED,
    ],
    SettlementState.SETTLED: [
        SettlementState.DISPUTED,
    ],
    SettlementState.REFUNDED: [],
    SettlementState.PARTIAL: [
        SettlementState.DISPUTED,
    ],
    SettlementState.TIMEOUT: [
        SettlementState.REFUNDED,
        SettlementState.DISPUTED,
    ],
    SettlementState.FAILED_LOCK: [],
    SettlementState.RELEASE_FAILED: [
        SettlementState.DISPUTED,
        SettlementState.REFUNDED,
    ],
    SettlementState.DISPUTED: [
        SettlementState.SETTLED,
        SettlementState.REFUNDED,
        SettlementState.PARTIAL,
    ],
}

TERMINAL_STATES = {
    SettlementState.REFUNDED,
    SettlementState.FAILED_LOCK,
}


class SettlementStateMachine:
    """Enforces settlement state transitions."""

    def __init__(self) -> None:
        self._state = SettlementState.PENDING_LOCK
        self._history: list[tuple[SettlementState, SettlementState]] = []

    def transition(self, to: SettlementState) -> None:
        """Transition to a new state. Raises XAPStateError on invalid transition."""
        if to not in VALID_TRANSITIONS[self._state]:
            raise XAPStateError(
                f"Invalid transition: {self._state.value} → {to.value}"
            )
        self._history.append((self._state, to))
        self._state = to

    @property
    def current(self) -> SettlementState:
        return self._state

    @property
    def is_terminal(self) -> bool:
        return self._state in TERMINAL_STATES

    @property
    def history(self) -> list[tuple[SettlementState, SettlementState]]:
        return list(self._history)
