"""Tests for xap.state_machines — negotiation, settlement, outcome."""

import pytest
from xap.state_machines import (
    NegotiationState, NegotiationStateMachine,
    SettlementState, SettlementStateMachine,
    OutcomeClassification, OutcomeStateMachine,
)
from xap.errors import XAPStateError


class TestNegotiationStateMachine:
    def test_initial_state(self):
        sm = NegotiationStateMachine()
        assert sm.current == NegotiationState.OFFER

    def test_offer_to_counter(self):
        sm = NegotiationStateMachine()
        sm.transition(NegotiationState.COUNTER)
        assert sm.current == NegotiationState.COUNTER
        assert sm.round == 2

    def test_offer_to_accept(self):
        sm = NegotiationStateMachine()
        sm.transition(NegotiationState.ACCEPT)
        assert sm.current == NegotiationState.ACCEPT
        assert sm.is_terminal

    def test_offer_to_reject(self):
        sm = NegotiationStateMachine()
        sm.transition(NegotiationState.REJECT)
        assert sm.current == NegotiationState.REJECT
        assert sm.is_terminal

    def test_counter_to_counter(self):
        sm = NegotiationStateMachine()
        sm.transition(NegotiationState.COUNTER)
        sm.transition(NegotiationState.COUNTER)
        assert sm.round == 3

    def test_counter_to_accept(self):
        sm = NegotiationStateMachine()
        sm.transition(NegotiationState.COUNTER)
        sm.transition(NegotiationState.ACCEPT)
        assert sm.is_terminal

    def test_accept_is_terminal(self):
        sm = NegotiationStateMachine()
        sm.transition(NegotiationState.ACCEPT)
        with pytest.raises(XAPStateError):
            sm.transition(NegotiationState.COUNTER)

    def test_reject_is_terminal(self):
        sm = NegotiationStateMachine()
        sm.transition(NegotiationState.REJECT)
        with pytest.raises(XAPStateError):
            sm.transition(NegotiationState.OFFER)

    def test_invalid_offer_to_offer(self):
        sm = NegotiationStateMachine()
        with pytest.raises(XAPStateError):
            sm.transition(NegotiationState.OFFER)

    def test_max_rounds(self):
        sm = NegotiationStateMachine(max_rounds=3)
        sm.transition(NegotiationState.COUNTER)  # round 2
        sm.transition(NegotiationState.COUNTER)  # round 3
        with pytest.raises(XAPStateError, match="Maximum rounds"):
            sm.transition(NegotiationState.COUNTER)  # round 4 blocked

    def test_history(self):
        sm = NegotiationStateMachine()
        sm.transition(NegotiationState.COUNTER)
        sm.transition(NegotiationState.ACCEPT)
        assert len(sm.history) == 2


class TestSettlementStateMachine:
    def test_initial_state(self):
        sm = SettlementStateMachine()
        assert sm.current == SettlementState.PENDING_LOCK

    def test_happy_path(self):
        sm = SettlementStateMachine()
        sm.transition(SettlementState.FUNDS_LOCKED)
        sm.transition(SettlementState.EXECUTING)
        sm.transition(SettlementState.PENDING_VERIFICATION)
        sm.transition(SettlementState.PENDING_RELEASE)
        sm.transition(SettlementState.SETTLED)
        assert sm.current == SettlementState.SETTLED

    def test_failed_lock(self):
        sm = SettlementStateMachine()
        sm.transition(SettlementState.FAILED_LOCK)
        assert sm.is_terminal

    def test_timeout_from_executing(self):
        sm = SettlementStateMachine()
        sm.transition(SettlementState.FUNDS_LOCKED)
        sm.transition(SettlementState.EXECUTING)
        sm.transition(SettlementState.TIMEOUT)
        assert sm.current == SettlementState.TIMEOUT

    def test_timeout_to_refund(self):
        sm = SettlementStateMachine()
        sm.transition(SettlementState.FUNDS_LOCKED)
        sm.transition(SettlementState.EXECUTING)
        sm.transition(SettlementState.TIMEOUT)
        sm.transition(SettlementState.REFUNDED)
        assert sm.is_terminal

    def test_dispute_after_settled(self):
        sm = SettlementStateMachine()
        sm.transition(SettlementState.FUNDS_LOCKED)
        sm.transition(SettlementState.EXECUTING)
        sm.transition(SettlementState.PENDING_VERIFICATION)
        sm.transition(SettlementState.PENDING_RELEASE)
        sm.transition(SettlementState.SETTLED)
        sm.transition(SettlementState.DISPUTED)
        assert sm.current == SettlementState.DISPUTED

    def test_dispute_resolution_to_settled(self):
        sm = SettlementStateMachine()
        sm.transition(SettlementState.FUNDS_LOCKED)
        sm.transition(SettlementState.EXECUTING)
        sm.transition(SettlementState.PENDING_VERIFICATION)
        sm.transition(SettlementState.PENDING_RELEASE)
        sm.transition(SettlementState.SETTLED)
        sm.transition(SettlementState.DISPUTED)
        sm.transition(SettlementState.SETTLED)
        assert sm.current == SettlementState.SETTLED

    def test_invalid_jump(self):
        sm = SettlementStateMachine()
        with pytest.raises(XAPStateError):
            sm.transition(SettlementState.SETTLED)

    def test_refunded_is_terminal(self):
        sm = SettlementStateMachine()
        sm.transition(SettlementState.FUNDS_LOCKED)
        sm.transition(SettlementState.REFUNDED)
        assert sm.is_terminal

    def test_all_12_states_exist(self):
        assert len(SettlementState) == 12

    def test_history(self):
        sm = SettlementStateMachine()
        sm.transition(SettlementState.FUNDS_LOCKED)
        sm.transition(SettlementState.EXECUTING)
        assert len(sm.history) == 2


class TestOutcomeStateMachine:
    def test_initial_unknown(self):
        sm = OutcomeStateMachine()
        assert sm.current == OutcomeClassification.UNKNOWN

    def test_unknown_to_success(self):
        sm = OutcomeStateMachine()
        sm.transition(OutcomeClassification.SUCCESS)
        assert sm.current == OutcomeClassification.SUCCESS

    def test_unknown_to_fail(self):
        sm = OutcomeStateMachine()
        sm.transition(OutcomeClassification.FAIL)
        assert sm.current == OutcomeClassification.FAIL

    def test_unknown_to_partial(self):
        sm = OutcomeStateMachine()
        sm.transition(OutcomeClassification.PARTIAL)
        assert sm.current == OutcomeClassification.PARTIAL

    def test_unknown_to_timeout(self):
        sm = OutcomeStateMachine()
        sm.transition(OutcomeClassification.TIMEOUT)
        assert sm.current == OutcomeClassification.TIMEOUT

    def test_unknown_to_disputed(self):
        sm = OutcomeStateMachine()
        sm.transition(OutcomeClassification.DISPUTED)
        assert sm.current == OutcomeClassification.DISPUTED

    def test_unknown_to_unknown(self):
        sm = OutcomeStateMachine()
        sm.transition(OutcomeClassification.UNKNOWN)
        assert sm.current == OutcomeClassification.UNKNOWN

    def test_success_to_reversed(self):
        sm = OutcomeStateMachine()
        sm.transition(OutcomeClassification.SUCCESS)
        sm.transition(OutcomeClassification.REVERSED)
        assert sm.is_terminal

    def test_reversed_is_terminal(self):
        sm = OutcomeStateMachine()
        sm.transition(OutcomeClassification.SUCCESS)
        sm.transition(OutcomeClassification.REVERSED)
        with pytest.raises(XAPStateError):
            sm.transition(OutcomeClassification.SUCCESS)

    def test_timeout_only_allows_disputed(self):
        sm = OutcomeStateMachine()
        sm.transition(OutcomeClassification.TIMEOUT)
        for target in [
            OutcomeClassification.SUCCESS,
            OutcomeClassification.FAIL,
            OutcomeClassification.PARTIAL,
            OutcomeClassification.REVERSED,
            OutcomeClassification.TIMEOUT,
            OutcomeClassification.UNKNOWN,
        ]:
            sm2 = OutcomeStateMachine()
            sm2.transition(OutcomeClassification.TIMEOUT)
            with pytest.raises(XAPStateError):
                sm2.transition(target)
        # Only DISPUTED is allowed
        sm.transition(OutcomeClassification.DISPUTED)
        assert sm.current == OutcomeClassification.DISPUTED

    def test_disputed_resolution(self):
        sm = OutcomeStateMachine()
        sm.transition(OutcomeClassification.DISPUTED)
        sm.transition(OutcomeClassification.SUCCESS)
        assert sm.current == OutcomeClassification.SUCCESS

    def test_success_to_fail_invalid(self):
        sm = OutcomeStateMachine()
        sm.transition(OutcomeClassification.SUCCESS)
        with pytest.raises(XAPStateError):
            sm.transition(OutcomeClassification.FAIL)

    def test_seven_states(self):
        assert len(OutcomeClassification) == 7

    def test_history(self):
        sm = OutcomeStateMachine()
        sm.transition(OutcomeClassification.DISPUTED)
        sm.transition(OutcomeClassification.SUCCESS)
        assert len(sm.history) == 2
