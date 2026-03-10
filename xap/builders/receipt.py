"""ExecutionReceipt builder."""

from __future__ import annotations

from xap.crypto import XAPSigner, canonical_hash
from xap.errors import XAPBuilderError
from xap.schemas.validator import SchemaValidator
from xap.types import ReceiptId, CanonicalTimestamp


class ExecutionReceiptBuilder:
    """Build ExecutionReceipt objects."""

    def __init__(self, signer: XAPSigner) -> None:
        self._signer = signer
        self._receipt_id: str | None = None
        self._settlement_id: str | None = None
        self._negotiation_id: str | None = None
        self._payer_agent: str | None = None
        self._outcome: str | None = None
        self._conditions_results: list[dict] = []
        self._payouts: list[dict] = []
        self._refunds: list[dict] = []
        self._execution_metrics: dict | None = None
        self._reputation_impacts: list[dict] = []
        self._verity_hash: str | None = None
        self._chain_position = 1
        self._chain_previous_hash: str | None = None
        self._adapter_used = "test"
        self._finality_status = "final"
        self._payee_signers: list[tuple[str, XAPSigner]] = []

    def receipt_id(self, rid: ReceiptId) -> ExecutionReceiptBuilder:
        self._receipt_id = str(rid)
        return self

    def settlement_id(self, sid: str) -> ExecutionReceiptBuilder:
        self._settlement_id = sid
        return self

    def negotiation_id(self, nid: str) -> ExecutionReceiptBuilder:
        self._negotiation_id = nid
        return self

    def payer_agent(self, agent_id: str) -> ExecutionReceiptBuilder:
        self._payer_agent = agent_id
        return self

    def outcome(self, outcome: str) -> ExecutionReceiptBuilder:
        self._outcome = outcome
        return self

    def add_condition_result(self, result: dict) -> ExecutionReceiptBuilder:
        self._conditions_results.append(result)
        return self

    def add_payout(self, payout: dict) -> ExecutionReceiptBuilder:
        self._payouts.append(payout)
        return self

    def add_refund(self, refund: dict) -> ExecutionReceiptBuilder:
        self._refunds.append(refund)
        return self

    def execution_metrics(self, metrics: dict) -> ExecutionReceiptBuilder:
        self._execution_metrics = metrics
        return self

    def add_reputation_impact(self, impact: dict) -> ExecutionReceiptBuilder:
        self._reputation_impacts.append(impact)
        return self

    def verity_hash(self, vh: str) -> ExecutionReceiptBuilder:
        self._verity_hash = vh
        return self

    def chain_position(self, pos: int) -> ExecutionReceiptBuilder:
        self._chain_position = pos
        return self

    def chain_previous_hash(self, h: str) -> ExecutionReceiptBuilder:
        self._chain_previous_hash = h
        return self

    def adapter_used(self, adapter: str) -> ExecutionReceiptBuilder:
        self._adapter_used = adapter
        return self

    def finality_status(self, status: str) -> ExecutionReceiptBuilder:
        self._finality_status = status
        return self

    def add_payee_signer(self, agent_id: str, signer: XAPSigner) -> ExecutionReceiptBuilder:
        self._payee_signers.append((agent_id, signer))
        return self

    def build(self) -> dict:
        """Build, validate, sign."""
        if not self._settlement_id:
            raise XAPBuilderError("settlement_id is required")
        if not self._outcome:
            raise XAPBuilderError("outcome is required")
        if not self._conditions_results:
            raise XAPBuilderError("At least one condition_result is required")
        if not self._execution_metrics:
            raise XAPBuilderError("execution_metrics is required")

        now = CanonicalTimestamp.now().to_iso()
        obj: dict = {
            "receipt_id": self._receipt_id or str(ReceiptId.generate()),
            "settlement_id": self._settlement_id,
            "negotiation_id": self._negotiation_id or "",
            "payer_agent": self._payer_agent or "",
            "outcome": self._outcome,
            "conditions_results": self._conditions_results,
            "payouts": self._payouts,
            "execution_metrics": self._execution_metrics,
            "reputation_impacts": self._reputation_impacts,
            "verity_hash": self._verity_hash or canonical_hash({"placeholder": True}),
            "chain_position": self._chain_position,
            "adapter_used": self._adapter_used,
            "finality_status": self._finality_status,
            "xap_version": "0.2.0",
            "issued_at": now,
            "signatures": {
                "settlement_engine": "",
                "payer": "",
                "payees": [],
            },
        }

        if self._chain_previous_hash:
            obj["chain_previous_hash"] = self._chain_previous_hash
        if self._refunds:
            obj["refunds"] = self._refunds

        # Sign
        signable = {k: v for k, v in obj.items() if k != "signatures"}
        engine_sig = self._signer.sign(signable)
        obj["signatures"]["settlement_engine"] = engine_sig
        obj["signatures"]["payer"] = engine_sig  # In production, payer signs separately
        obj["signatures"]["payees"] = [
            {"agent_id": aid, "signature": s.sign(signable)}
            for aid, s in self._payee_signers
        ] if self._payee_signers else [
            {"agent_id": self._payer_agent or "agent_00000000", "signature": engine_sig}
        ]

        SchemaValidator().validate_execution_receipt(obj)
        return obj
