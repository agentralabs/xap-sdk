"""NegotiationContract builder."""

from __future__ import annotations

from xap.crypto import XAPSigner, canonical_hash
from xap.errors import XAPBuilderError
from xap.schemas.validator import SchemaValidator
from xap.types import AgentId, ContractId, CanonicalTimestamp


class NegotiationContractBuilder:
    """Build negotiation offers, counters, accepts, rejects."""

    def __init__(self, signer: XAPSigner) -> None:
        self._signer = signer
        self._data: dict = {}
        self._state: str | None = None

    def new_offer(
        self,
        proposer: AgentId,
        responder: AgentId,
        task: dict,
        pricing: dict,
        sla: dict,
        expires_in_minutes: int = 60,
    ) -> NegotiationContractBuilder:
        """Create a new OFFER."""
        self._state = "OFFER"
        now = CanonicalTimestamp.now()
        self._data = {
            "negotiation_id": str(ContractId.generate()),
            "state": "OFFER",
            "round_number": 1,
            "max_rounds": 20,
            "from_agent": str(proposer),
            "to_agent": str(responder),
            "task": task,
            "pricing": pricing,
            "sla": sla,
            "expires_at": now.add_minutes(expires_in_minutes).to_iso(),
            "xap_version": "0.2.0",
            "created_at": now.to_iso(),
        }
        return self

    def counter(
        self,
        previous_contract: dict,
        new_pricing: dict | None = None,
        new_sla: dict | None = None,
        expires_in_minutes: int = 60,
    ) -> NegotiationContractBuilder:
        """Create a COUNTER based on a previous contract."""
        self._state = "COUNTER"
        now = CanonicalTimestamp.now()
        prev_hash = canonical_hash(previous_contract)
        self._data = {
            "negotiation_id": previous_contract["negotiation_id"],
            "state": "COUNTER",
            "round_number": previous_contract["round_number"] + 1,
            "max_rounds": previous_contract.get("max_rounds", 20),
            "from_agent": previous_contract["to_agent"],
            "to_agent": previous_contract["from_agent"],
            "task": previous_contract["task"],
            "pricing": new_pricing or previous_contract["pricing"],
            "sla": new_sla or previous_contract["sla"],
            "expires_at": now.add_minutes(expires_in_minutes).to_iso(),
            "previous_state_hash": prev_hash,
            "xap_version": "0.2.0",
            "created_at": now.to_iso(),
        }
        return self

    def accept(self, contract: dict) -> dict:
        """Accept a contract. Returns the ACCEPT message."""
        now = CanonicalTimestamp.now()
        prev_hash = canonical_hash(contract)
        obj: dict = {
            "negotiation_id": contract["negotiation_id"],
            "state": "ACCEPT",
            "round_number": contract["round_number"] + 1,
            "from_agent": contract["to_agent"],
            "to_agent": contract["from_agent"],
            "task": contract["task"],
            "pricing": contract["pricing"],
            "sla": contract["sla"],
            "expires_at": now.add_minutes(60).to_iso(),
            "previous_state_hash": prev_hash,
            "xap_version": "0.2.0",
            "created_at": now.to_iso(),
            "signature": "",
        }
        SchemaValidator().validate_negotiation_contract(obj)
        signable = {k: v for k, v in obj.items() if k != "signature"}
        obj["signature"] = self._signer.sign(signable)
        return obj

    def reject(self, contract: dict, reason: str | None = None) -> dict:
        """Reject a contract. Returns the REJECT message."""
        now = CanonicalTimestamp.now()
        prev_hash = canonical_hash(contract)
        obj: dict = {
            "negotiation_id": contract["negotiation_id"],
            "state": "REJECT",
            "round_number": contract["round_number"] + 1,
            "from_agent": contract["to_agent"],
            "to_agent": contract["from_agent"],
            "task": contract["task"],
            "pricing": contract["pricing"],
            "sla": contract["sla"],
            "expires_at": now.add_minutes(60).to_iso(),
            "previous_state_hash": prev_hash,
            "xap_version": "0.2.0",
            "created_at": now.to_iso(),
            "signature": "",
        }
        SchemaValidator().validate_negotiation_contract(obj)
        signable = {k: v for k, v in obj.items() if k != "signature"}
        obj["signature"] = self._signer.sign(signable)
        return obj

    def build(self) -> dict:
        """Build and sign the current contract message."""
        if not self._data:
            raise XAPBuilderError("No contract data set. Call new_offer() or counter() first.")
        obj = {**self._data, "signature": ""}
        SchemaValidator().validate_negotiation_contract(obj)
        signable = {k: v for k, v in obj.items() if k != "signature"}
        obj["signature"] = self._signer.sign(signable)
        return obj
