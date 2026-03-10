"""ReceiptClient — generate and verify receipts and verity decisions."""

from __future__ import annotations

from typing import TYPE_CHECKING

from xap.builders.receipt import ExecutionReceiptBuilder
from xap.builders.verity import VerityReceiptBuilder
from xap.crypto import compute_replay_hash, canonical_hash
from xap.types import ReceiptId, VerityId, CanonicalTimestamp

if TYPE_CHECKING:
    from xap.client import XAPClient


class ReceiptClient:
    """Generate and verify receipts and verity decisions."""

    def __init__(self, xap_client: XAPClient) -> None:
        self._client = xap_client
        self._chains: dict[str, list[dict]] = {}  # settlement_id -> verity chain

    def generate_receipt(
        self,
        settlement: dict,
        outcome: str,
        condition_results: list[dict],
        payouts: list[dict],
        adapter_response: dict,
        verity_hash: str | None = None,
    ) -> dict:
        """Generate a signed ExecutionReceipt."""
        now_iso = CanonicalTimestamp.now().to_iso()

        builder = (
            ExecutionReceiptBuilder(self._client.signer)
            .settlement_id(settlement["settlement_id"])
            .negotiation_id(settlement["negotiation_id"])
            .payer_agent(settlement["payer_agent"])
            .outcome(outcome)
            .execution_metrics({
                "execution_started_at": now_iso,
                "execution_completed_at": now_iso,
                "execution_duration_ms": 1,
                "verification_duration_ms": 1,
                "total_duration_ms": 2,
                "timeout_triggered": False,
                "retries_attempted": 0,
            })
            .adapter_used(settlement.get("adapter", "test"))
        )

        if verity_hash:
            builder.verity_hash(verity_hash)

        for cr in condition_results:
            builder.add_condition_result(cr)

        for payout in payouts:
            builder.add_payout(payout)

        # Reputation impacts
        payee_agents = settlement.get("payee_agents", [])
        builder.add_reputation_impact({
            "agent_id": settlement["payer_agent"],
            "role_in_settlement": "payer",
            "outcome_for_agent": "positive" if outcome == "SETTLED" else "neutral",
            "success_rate_delta_bps": 0,
            "dispute_filed": False,
        })
        for pa in payee_agents:
            builder.add_reputation_impact({
                "agent_id": pa["agent_id"],
                "role_in_settlement": pa.get("role", "primary_executor"),
                "outcome_for_agent": "positive" if outcome == "SETTLED" else "negative",
                "success_rate_delta_bps": 100 if outcome == "SETTLED" else -50,
                "dispute_filed": False,
            })

        # Chain position
        stl_id = settlement["settlement_id"]
        chain = self._chains.get(stl_id, [])
        pos = len(chain) + 1
        builder.chain_position(pos)
        if chain:
            builder.chain_previous_hash(canonical_hash(chain[-1]))

        return builder.build()

    def generate_verity_receipt(
        self,
        settlement: dict,
        decision_type: str,
        input_state: dict,
        rules_applied: dict,
        computation: dict,
        outcome: dict,
        confidence_bps: int = 10000,
    ) -> dict:
        """Generate a signed VerityReceipt with replay hash.

        Automatically computes replay_hash, appends to chain, signs.
        """
        stl_id = settlement["settlement_id"]
        chain = self._chains.setdefault(stl_id, [])
        pos = len(chain) + 1

        builder = (
            VerityReceiptBuilder(self._client.signer)
            .settlement_id(stl_id)
            .decision_type(decision_type)
            .input_state(input_state)
            .rules_applied(rules_applied)
            .computation(computation)
            .outcome(outcome)
            .confidence_bps(confidence_bps)
            .chain_position(pos)
        )

        if chain:
            builder.chain_previous_verity_hash(canonical_hash(chain[-1]))

        receipt = builder.build()
        chain.append(receipt)
        return receipt

    def verify_replay(self, verity_receipt: dict) -> bool:
        """Verify a VerityReceipt's replay hash.

        Recomputes SHA-256(input_state + rules + computation)
        and compares with stored replay_hash.
        """
        computed = compute_replay_hash(
            verity_receipt["input_state"],
            verity_receipt["rules_applied"],
            verity_receipt["computation"],
        )
        return computed == verity_receipt["replay_hash"]

    def verify_chain(self, settlement_id: str) -> bool:
        """Verify the entire verity chain for a settlement."""
        chain = self._chains.get(settlement_id, [])
        if not chain:
            return True

        for i, entry in enumerate(chain):
            if i == 0:
                if "chain_previous_verity_hash" in entry:
                    return False
            else:
                expected_prev = canonical_hash(chain[i - 1])
                if entry.get("chain_previous_verity_hash") != expected_prev:
                    return False
        return True
