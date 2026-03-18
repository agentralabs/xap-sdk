"""AgentManifest — builder, Ed25519 signer, and verifier for XAP v0.2 manifests."""

from __future__ import annotations

import json
import secrets

from nacl.signing import SigningKey, VerifyKey
from nacl.encoding import Base64Encoder
from nacl.exceptions import BadSignatureError

from xap.crypto import canonical_serialize, XAPSigner
from xap.errors import XAPValidationError, XAPCryptoError
from xap.schemas.validator import SchemaValidator
from xap.types import CanonicalTimestamp


class ManifestId:
    """Manifest identifier: mnf_ + 8 hex chars."""

    @staticmethod
    def generate() -> str:
        return f"mnf_{secrets.token_hex(4)}"


class AgentManifest:
    """Build, sign, and verify AgentManifest objects.

    Usage:
        manifest = AgentManifest.build(
            agent_id="a1b2c3d4e5f60001",
            signer=signer,
            capabilities=[...],
            economic_terms={...},
        )
    """

    SIGNED_FIELDS = [
        "manifest_id", "agent_id", "issued_at",
        "expires_at", "capabilities", "economic_terms",
    ]

    @classmethod
    def build(
        cls,
        agent_id: str,
        signer: XAPSigner,
        capabilities: list[dict],
        economic_terms: dict,
        *,
        manifest_id: str | None = None,
        expires_days: int = 30,
        registry_url: str | None = None,
        federation_hints: dict | None = None,
    ) -> dict:
        """Build, validate, and sign an AgentManifest."""
        now = CanonicalTimestamp.now()
        expires = now.add_days(expires_days)

        obj: dict = {
            "manifest_id": manifest_id or ManifestId.generate(),
            "agent_id": agent_id,
            "xap_version": "0.2",
            "issued_at": now.to_iso(),
            "expires_at": expires.to_iso(),
            "signature": {
                "algorithm": "Ed25519",
                "public_key": signer.public_key_base64(),
                "value": "",
                "signed_fields": cls.SIGNED_FIELDS,
            },
            "capabilities": capabilities,
            "economic_terms": economic_terms,
        }

        if registry_url:
            obj["registry_url"] = registry_url
        if federation_hints:
            obj["federation_hints"] = federation_hints

        # Validate before signing
        SchemaValidator().validate_agent_manifest(obj)

        # Sign the declared fields
        obj["signature"]["value"] = cls._sign(obj, signer)

        return obj

    @classmethod
    def _sign(cls, manifest: dict, signer: XAPSigner) -> str:
        """Sign the declared signed_fields of a manifest."""
        signable = {k: manifest[k] for k in cls.SIGNED_FIELDS if k in manifest}
        data = canonical_serialize(signable)
        signed = signer._key.sign(data)
        return Base64Encoder.encode(signed.signature).decode()

    @classmethod
    def verify(cls, manifest: dict) -> bool:
        """Verify an AgentManifest's Ed25519 signature.

        Returns True if valid, False otherwise.
        """
        try:
            sig = manifest.get("signature", {})
            if sig.get("algorithm") != "Ed25519":
                return False

            public_key_b64 = sig.get("public_key", "")
            sig_value = sig.get("value", "")
            signed_fields = sig.get("signed_fields", cls.SIGNED_FIELDS)

            signable = {k: manifest[k] for k in signed_fields if k in manifest}
            data = canonical_serialize(signable)

            sig_bytes = Base64Encoder.decode(sig_value.encode())
            vk = VerifyKey(Base64Encoder.decode(public_key_b64.encode()))
            vk.verify(data, sig_bytes)
            return True
        except (BadSignatureError, Exception):
            return False

    @classmethod
    def is_expired(cls, manifest: dict) -> bool:
        """Check if a manifest has expired."""
        expires_at = manifest.get("expires_at", "")
        if not expires_at:
            return True
        ts = CanonicalTimestamp.from_iso(expires_at)
        return ts.is_expired()
