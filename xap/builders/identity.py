"""AgentIdentity builder."""

from __future__ import annotations

from xap.crypto import XAPSigner, canonical_hash
from xap.errors import XAPBuilderError
from xap.schemas.validator import SchemaValidator
from xap.types import AgentId, CanonicalTimestamp


class AgentIdentityBuilder:
    """Build AgentIdentity objects with validation and signing."""

    def __init__(self, signer: XAPSigner) -> None:
        self._signer = signer
        self._agent_id: str | None = None
        self._display_name: str | None = None
        self._capabilities: list[dict] = []
        self._org_id: str | None = None
        self._team_id: str | None = None
        self._xap_version = "0.2.0"
        self._status = "active"
        self._risk_profile: dict | None = None

    def agent_id(self, id: AgentId) -> AgentIdentityBuilder:
        """Set the agent ID."""
        self._agent_id = str(id)
        return self

    def display_name(self, name: str) -> AgentIdentityBuilder:
        """Set display name."""
        self._display_name = name
        return self

    def add_capability(
        self,
        name: str,
        version: str,
        pricing: dict,
        sla: dict,
        description: str | None = None,
    ) -> AgentIdentityBuilder:
        """Add a capability declaration."""
        cap: dict = {"name": name, "version": version, "pricing": pricing, "sla": sla}
        if description:
            cap["description"] = description
        self._capabilities.append(cap)
        return self

    def org(self, org_id: str, team_id: str | None = None) -> AgentIdentityBuilder:
        """Set organization and optional team."""
        self._org_id = org_id
        self._team_id = team_id
        return self

    def xap_version(self, v: str) -> AgentIdentityBuilder:
        """Set XAP protocol version."""
        self._xap_version = v
        return self

    def status(self, s: str) -> AgentIdentityBuilder:
        """Set agent status."""
        self._status = s
        return self

    def risk_profile(self, profile: dict) -> AgentIdentityBuilder:
        """Set risk profile."""
        self._risk_profile = profile
        return self

    def build(self) -> dict:
        """Validate against schema, sign, return complete object."""
        if not self._agent_id:
            raise XAPBuilderError("agent_id is required")
        if not self._capabilities:
            raise XAPBuilderError("At least one capability is required")

        now = CanonicalTimestamp.now().to_iso()
        obj: dict = {
            "agent_id": self._agent_id,
            "public_key": f"ed25519:{self._signer.public_key_base64()}",
            "key_version": 1,
            "key_status": "active",
            "capabilities": self._capabilities,
            "reputation": {
                "total_settlements": 0,
                "success_rate_bps": 0,
                "disputes": 0,
                "dispute_resolution_rate_bps": 0,
                "last_updated": now,
            },
            "xap_version": self._xap_version,
            "status": self._status,
            "registered_at": now,
            "last_active_at": now,
            "signature": "",  # placeholder for validation
        }

        if self._display_name:
            obj["display_name"] = self._display_name
        if self._org_id:
            obj["org_id"] = self._org_id
        if self._team_id:
            obj["team_id"] = self._team_id
        if self._risk_profile:
            obj["risk_profile"] = self._risk_profile

        # Validate before signing (signature is placeholder)
        SchemaValidator().validate_agent_identity(obj)

        # Sign everything except signature field
        signable = {k: v for k, v in obj.items() if k != "signature"}
        obj["signature"] = self._signer.sign(signable)

        return obj
