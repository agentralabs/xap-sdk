"""SettlementIntent builder."""

from __future__ import annotations

import secrets

from xap.crypto import XAPSigner
from xap.errors import XAPBuilderError
from xap.schemas.validator import SchemaValidator
from xap.types import AgentId, SettlementId, ContractId, CanonicalTimestamp


class SettlementIntentBuilder:
    """Build SettlementIntent objects."""

    def __init__(self, signer: XAPSigner) -> None:
        self._signer = signer
        self._settlement_id: str | None = None
        self._negotiation_id: str | None = None
        self._payer: str | None = None
        self._payees: list[dict] = []
        self._amount: int | None = None
        self._currency = "USD"
        self._adapter = "test"
        self._conditions: list[dict] = []
        self._timeout_seconds = 3600
        self._on_timeout = "full_refund"
        self._on_partial = "pro_rata"
        self._on_failure = "full_refund"
        self._chargeback_policy = "proportional"
        self._finality_class = "instant"

    def settlement_id(self, sid: SettlementId) -> SettlementIntentBuilder:
        self._settlement_id = str(sid)
        return self

    def from_contract(self, accepted_contract: dict) -> SettlementIntentBuilder:
        """Extract negotiation_id, task, pricing from an accepted contract."""
        self._negotiation_id = accepted_contract["negotiation_id"]
        return self

    def negotiation_id(self, nid: str) -> SettlementIntentBuilder:
        self._negotiation_id = nid
        return self

    def payer(self, agent_id: AgentId) -> SettlementIntentBuilder:
        self._payer = str(agent_id)
        return self

    def add_payee(self, agent_id: AgentId, share_bps: int, role: str = "primary_executor") -> SettlementIntentBuilder:
        self._payees.append({
            "agent_id": str(agent_id),
            "share_bps": share_bps,
            "role": role,
        })
        return self

    def amount(self, minor_units: int, currency: str = "USD") -> SettlementIntentBuilder:
        self._amount = minor_units
        self._currency = currency
        return self

    def adapter(self, adapter: str) -> SettlementIntentBuilder:
        self._adapter = adapter
        return self

    def add_condition(self, condition: dict) -> SettlementIntentBuilder:
        self._conditions.append(condition)
        return self

    def timeout(self, seconds: int) -> SettlementIntentBuilder:
        self._timeout_seconds = seconds
        return self

    def on_timeout(self, action: str) -> SettlementIntentBuilder:
        self._on_timeout = action
        return self

    def on_partial(self, action: str) -> SettlementIntentBuilder:
        self._on_partial = action
        return self

    def on_failure(self, action: str) -> SettlementIntentBuilder:
        self._on_failure = action
        return self

    def chargeback_policy(self, policy: str) -> SettlementIntentBuilder:
        self._chargeback_policy = policy
        return self

    def finality_class(self, fc: str) -> SettlementIntentBuilder:
        self._finality_class = fc
        return self

    def build(self) -> dict:
        """Build, validate, sign."""
        if not self._payer:
            raise XAPBuilderError("payer is required")
        if not self._payees:
            raise XAPBuilderError("At least one payee is required")
        if self._amount is None:
            raise XAPBuilderError("amount is required")
        if not self._conditions:
            raise XAPBuilderError("At least one condition is required")

        now = CanonicalTimestamp.now().to_iso()
        obj: dict = {
            "settlement_id": self._settlement_id or str(SettlementId.generate()),
            "negotiation_id": self._negotiation_id or str(ContractId.generate()),
            "state": "PENDING_LOCK",
            "payer_agent": self._payer,
            "payee_agents": self._payees,
            "total_amount_minor_units": self._amount,
            "currency": self._currency,
            "adapter": self._adapter,
            "conditions": self._conditions,
            "timeout_seconds": self._timeout_seconds,
            "on_timeout": self._on_timeout,
            "on_partial_completion": self._on_partial,
            "on_failure": self._on_failure,
            "chargeback_policy": self._chargeback_policy,
            "idempotency_key": f"idem_{secrets.token_hex(8)}",
            "finality_class": self._finality_class,
            "xap_version": "0.2.0",
            "created_at": now,
            "signature": "",
        }

        SchemaValidator().validate_settlement_intent(obj)
        signable = {k: v for k, v in obj.items() if k != "signature"}
        obj["signature"] = self._signer.sign(signable)
        return obj
