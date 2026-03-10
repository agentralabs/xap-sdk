"""SettlementClient — manage the settlement lifecycle."""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from typing import TYPE_CHECKING

from xap.builders.settlement import SettlementIntentBuilder
from xap.errors import XAPError, XAPStateError
from xap.types import AgentId, SettlementId, CanonicalTimestamp

if TYPE_CHECKING:
    from xap.client import XAPClient


@dataclass
class SettlementResult:
    """The complete result of a settlement."""
    settlement: dict
    receipt: dict
    verity_receipt: dict
    adapter_response: dict


class SettlementClient:
    """Manage the settlement lifecycle."""

    def __init__(self, xap_client: XAPClient) -> None:
        self._client = xap_client

    def create_from_contract(
        self,
        accepted_contract: dict,
        payees: list[dict],
        conditions: list[dict] | None = None,
        chargeback_policy: str = "proportional",
    ) -> dict:
        """Create a SettlementIntent from an accepted NegotiationContract.

        Validates that contract is in ACCEPT state.
        Validates that payee shares sum to 10000.
        """
        if accepted_contract.get("state") != "ACCEPT":
            raise XAPStateError(
                f"Contract must be in ACCEPT state, got {accepted_contract.get('state')}"
            )

        share_sum = sum(p["share_bps"] for p in payees)
        if share_sum != 10000:
            raise XAPError(f"Payee shares must sum to 10000, got {share_sum}")

        amount = accepted_contract["pricing"]["amount_minor_units"]
        currency = accepted_contract["pricing"]["currency"]

        # Build default conditions if none provided
        if conditions is None:
            conditions = [{
                "condition_id": "cond_0001",
                "type": "deterministic",
                "check": "output_delivered",
                "verifier": "engine",
                "required": True,
            }]

        builder = SettlementIntentBuilder(self._client.signer)
        builder.from_contract(accepted_contract)
        builder.payer(self._client.agent_id)
        builder.amount(amount, currency)
        builder.chargeback_policy(chargeback_policy)

        for payee in payees:
            builder.add_payee(
                AgentId(payee["agent_id"]),
                payee["share_bps"],
                payee.get("role", "primary_executor"),
            )

        for condition in conditions:
            builder.add_condition(condition)

        return builder.build()

    async def lock(self, settlement: dict) -> dict:
        """Lock funds via the adapter. Transitions PENDING_LOCK -> FUNDS_LOCKED."""
        if settlement["state"] != "PENDING_LOCK":
            raise XAPStateError(
                f"Settlement must be in PENDING_LOCK state, got {settlement['state']}"
            )

        await self._client.adapter.lock_funds(settlement)
        settlement = {**settlement, "state": "FUNDS_LOCKED"}
        return settlement

    async def verify_and_settle(
        self,
        settlement: dict,
        condition_results: list[dict],
    ) -> SettlementResult:
        """Verify conditions and execute settlement.

        1. FUNDS_LOCKED -> EXECUTING -> PENDING_VERIFICATION
        2. Evaluate conditions
        3. If all pass: SETTLED (release funds)
        4. If some fail: PARTIAL (pro-rata)
        5. If all fail: REFUNDED
        """
        if settlement["state"] != "FUNDS_LOCKED":
            raise XAPStateError(
                f"Settlement must be in FUNDS_LOCKED state, got {settlement['state']}"
            )

        # Transition through states
        settlement = {**settlement, "state": "EXECUTING"}
        settlement = {**settlement, "state": "PENDING_VERIFICATION"}

        # Evaluate conditions
        all_passed = all(cr.get("passed", False) for cr in condition_results)
        any_passed = any(cr.get("passed", False) for cr in condition_results)
        passed_count = sum(1 for cr in condition_results if cr.get("passed", False))
        total_count = len(condition_results)

        # Determine outcome and compute payouts
        total_amount = settlement["total_amount_minor_units"]
        payee_agents = settlement["payee_agents"]

        if all_passed:
            outcome = "SETTLED"
            settlement = {**settlement, "state": "PENDING_RELEASE"}
            # Full payout according to shares
            payouts = [
                {
                    "agent_id": p["agent_id"],
                    "amount_minor_units": total_amount * p["share_bps"] // 10000,
                }
                for p in payee_agents
            ]
            # Handle remainder — first payee gets it
            distributed = sum(po["amount_minor_units"] for po in payouts)
            if distributed < total_amount and payouts:
                payouts[0]["amount_minor_units"] += total_amount - distributed

            adapter_response = await self._client.adapter.release_funds(settlement, payouts)
            settlement = {**settlement, "state": "SETTLED"}

        elif any_passed:
            outcome = "PARTIAL"
            # Pro-rata based on passed conditions
            ratio_bps = (passed_count * 10000) // total_count
            partial_amount = total_amount * ratio_bps // 10000
            refund_amount = total_amount - partial_amount

            payouts = [
                {
                    "agent_id": p["agent_id"],
                    "amount_minor_units": partial_amount * p["share_bps"] // 10000,
                }
                for p in payee_agents
            ]
            distributed = sum(po["amount_minor_units"] for po in payouts)
            if distributed < partial_amount and payouts:
                payouts[0]["amount_minor_units"] += partial_amount - distributed

            adapter_response = await self._client.adapter.release_funds(settlement, payouts)
            settlement = {**settlement, "state": "PARTIAL"}

        else:
            outcome = "REFUNDED"
            payouts = []
            adapter_response = await self._client.adapter.refund(settlement, total_amount)
            settlement = {**settlement, "state": "REFUNDED"}

        # Determine confidence
        confidence_bps = 10000
        for cr in condition_results:
            if cr.get("type") == "probabilistic":
                confidence_bps = min(confidence_bps, cr.get("confidence_bps", 10000))

        # Format condition results for receipt
        now_iso = CanonicalTimestamp.now().to_iso()
        receipt_condition_results = []
        for cr in condition_results:
            rcr = {
                "condition_id": cr.get("condition_id", "cond_0001"),
                "type": cr.get("type", "deterministic"),
                "check": cr.get("check", "output_delivered"),
                "passed": cr.get("passed", False),
                "verified_by": cr.get("verified_by", "engine"),
                "verified_at": now_iso,
            }
            if "confidence_bps" in cr:
                rcr["confidence_bps"] = cr["confidence_bps"]
            if "actual_value" in cr:
                rcr["actual_value"] = cr["actual_value"]
            if "threshold" in cr:
                rcr["threshold"] = cr["threshold"]
            if "operator" in cr:
                rcr["operator"] = cr["operator"]
            receipt_condition_results.append(rcr)

        # Generate verity receipt first (we need the hash)
        verity_receipt = self._client.receipts.generate_verity_receipt(
            settlement=settlement,
            decision_type="condition_verification",
            input_state={
                "settlement_state": "PENDING_VERIFICATION",
                "contract_terms": {
                    "pricing": {"amount_minor_units": total_amount, "currency": settlement["currency"]},
                    "sla": {},
                    "conditions": settlement["conditions"],
                },
                "agent_states": [
                    {"agent_id": settlement["payer_agent"], "role": "payer"},
                ] + [
                    {"agent_id": p["agent_id"], "role": p["role"]}
                    for p in payee_agents
                ],
            },
            rules_applied={
                "rules_version": "0.2.0",
                "rules_hash": f"sha256:{'a' * 64}",
                "applicable_rules": [
                    {
                        "rule_id": "all_conditions_check",
                        "rule_description": "Evaluate all settlement conditions",
                        "evaluated": True,
                        "result": "pass" if all_passed else "fail",
                    }
                ],
            },
            computation={
                "steps": [
                    {
                        "step_number": i + 1,
                        "operation": f"evaluate_{cr.get('check', 'condition')}",
                        "inputs": {"condition_id": cr.get("condition_id", f"cond_{i:04d}")},
                        "output": {"passed": cr.get("passed", False)},
                        "deterministic": cr.get("type", "deterministic") == "deterministic",
                    }
                    for i, cr in enumerate(condition_results)
                ],
                "total_steps": len(condition_results),
                "computation_duration_ms": 1,
            },
            outcome={
                "decision": "release_funds" if all_passed else ("pro_rata" if any_passed else "full_refund"),
                "settlement_state_after": settlement["state"],
                "outcome_classification": "SUCCESS" if all_passed else ("PARTIAL" if any_passed else "FAIL"),
            },
            confidence_bps=confidence_bps,
        )

        # Generate execution receipt
        receipt = self._client.receipts.generate_receipt(
            settlement=settlement,
            outcome=outcome,
            condition_results=receipt_condition_results,
            payouts=[
                {
                    "agent_id": p["agent_id"],
                    "role": next(
                        (pa["role"] for pa in payee_agents if pa["agent_id"] == p["agent_id"]),
                        "primary_executor",
                    ),
                    "declared_share_bps": next(
                        (pa["share_bps"] for pa in payee_agents if pa["agent_id"] == p["agent_id"]),
                        10000,
                    ),
                    "base_amount_minor_units": p["amount_minor_units"],
                    "final_amount_minor_units": p["amount_minor_units"],
                    "currency": settlement["currency"],
                    "status": "paid",
                }
                for p in payouts
            ],
            adapter_response=adapter_response,
            verity_hash=verity_receipt["replay_hash"],
        )

        return SettlementResult(
            settlement=settlement,
            receipt=receipt,
            verity_receipt=verity_receipt,
            adapter_response=adapter_response,
        )

    async def refund(self, settlement: dict, reason: str | None = None) -> dict:
        """Full refund. Transitions to REFUNDED."""
        amount = settlement["total_amount_minor_units"]
        await self._client.adapter.refund(settlement, amount)
        return {**settlement, "state": "REFUNDED"}
