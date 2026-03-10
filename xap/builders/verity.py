"""VerityReceipt builder."""

from __future__ import annotations

from xap.crypto import XAPSigner, compute_replay_hash
from xap.errors import XAPBuilderError
from xap.schemas.validator import SchemaValidator
from xap.types import VerityId, CanonicalTimestamp


class VerityReceiptBuilder:
    """Build VerityReceipt objects. Automatically computes replay_hash."""

    def __init__(self, signer: XAPSigner) -> None:
        self._signer = signer
        self._verity_id: str | None = None
        self._settlement_id: str | None = None
        self._receipt_id: str | None = None
        self._decision_type: str | None = None
        self._input_state: dict | None = None
        self._rules_applied: dict | None = None
        self._computation: dict | None = None
        self._outcome: dict | None = None
        self._confidence_bps = 10000
        self._chain_position = 1
        self._chain_previous_verity_hash: str | None = None

    def verity_id(self, vid: VerityId) -> VerityReceiptBuilder:
        self._verity_id = str(vid)
        return self

    def settlement_id(self, sid: str) -> VerityReceiptBuilder:
        self._settlement_id = sid
        return self

    def receipt_id(self, rid: str) -> VerityReceiptBuilder:
        self._receipt_id = rid
        return self

    def decision_type(self, dt: str) -> VerityReceiptBuilder:
        self._decision_type = dt
        return self

    def input_state(self, state: dict) -> VerityReceiptBuilder:
        self._input_state = state
        return self

    def rules_applied(self, rules: dict) -> VerityReceiptBuilder:
        self._rules_applied = rules
        return self

    def computation(self, comp: dict) -> VerityReceiptBuilder:
        self._computation = comp
        return self

    def outcome(self, outcome: dict) -> VerityReceiptBuilder:
        self._outcome = outcome
        return self

    def confidence_bps(self, bps: int) -> VerityReceiptBuilder:
        self._confidence_bps = bps
        return self

    def chain_position(self, pos: int) -> VerityReceiptBuilder:
        self._chain_position = pos
        return self

    def chain_previous_verity_hash(self, h: str) -> VerityReceiptBuilder:
        self._chain_previous_verity_hash = h
        return self

    def build(self) -> dict:
        """Build, compute replay_hash, validate, sign."""
        if not self._settlement_id:
            raise XAPBuilderError("settlement_id is required")
        if not self._decision_type:
            raise XAPBuilderError("decision_type is required")
        if not self._input_state:
            raise XAPBuilderError("input_state is required")
        if not self._rules_applied:
            raise XAPBuilderError("rules_applied is required")
        if not self._computation:
            raise XAPBuilderError("computation is required")
        if not self._outcome:
            raise XAPBuilderError("outcome is required")

        replay_hash = compute_replay_hash(
            self._input_state, self._rules_applied, self._computation
        )

        now = CanonicalTimestamp.now().to_iso()
        obj: dict = {
            "verity_id": self._verity_id or str(VerityId.generate()),
            "settlement_id": self._settlement_id,
            "decision_type": self._decision_type,
            "decision_timestamp": now,
            "input_state": self._input_state,
            "rules_applied": self._rules_applied,
            "computation": self._computation,
            "outcome": self._outcome,
            "replay_hash": replay_hash,
            "confidence_bps": self._confidence_bps,
            "chain_position": self._chain_position,
            "xap_version": "0.2.0",
            "verity_engine_version": "0.2.0",
            "verity_signature": "",
        }

        if self._receipt_id:
            obj["receipt_id"] = self._receipt_id
        if self._chain_previous_verity_hash:
            obj["chain_previous_verity_hash"] = self._chain_previous_verity_hash

        # Sign everything except verity_signature
        signable = {k: v for k, v in obj.items() if k != "verity_signature"}
        obj["verity_signature"] = self._signer.sign(signable)

        SchemaValidator().validate_verity_receipt(obj)
        return obj
