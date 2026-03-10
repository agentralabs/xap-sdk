"""Cryptographic operations: Ed25519 signing, SHA-256 hashing, canonical serialization."""

from __future__ import annotations

import hashlib
import json

from nacl.signing import SigningKey, VerifyKey
from nacl.encoding import Base64Encoder
from nacl.exceptions import BadSignatureError

from xap.errors import XAPCryptoError


def canonical_serialize(obj: dict) -> bytes:
    """Deterministic JSON serialization: sorted keys, compact, UTF-8.
    Same object always produces same bytes. Critical for hash computation."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def canonical_hash(obj: dict) -> str:
    """SHA-256 of canonical serialization. Returns 'sha256:{hex}'."""
    data = canonical_serialize(obj)
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


def compute_replay_hash(input_state: dict, rules_applied: dict, computation: dict) -> str:
    """Core replayability primitive. SHA-256 of (input_state + rules + computation).
    Any party can recompute this to verify a VerityReceipt."""
    combined = (
        canonical_serialize(input_state)
        + canonical_serialize(rules_applied)
        + canonical_serialize(computation)
    )
    return f"sha256:{hashlib.sha256(combined).hexdigest()}"


class XAPSigner:
    """Ed25519 signing for XAP objects."""

    def __init__(self, signing_key: SigningKey | None = None) -> None:
        self._key = signing_key or SigningKey.generate()

    @classmethod
    def generate(cls) -> XAPSigner:
        """Generate a new random signing key."""
        return cls(SigningKey.generate())

    def sign(self, obj: dict) -> str:
        """Sign canonical serialization. Returns 'ed25519:{base64_signature}'."""
        data = canonical_serialize(obj)
        signed = self._key.sign(data)
        sig_b64 = Base64Encoder.encode(signed.signature).decode()
        return f"ed25519:{sig_b64}"

    def public_key_bytes(self) -> bytes:
        """Raw public key bytes."""
        return bytes(self._key.verify_key)

    def public_key_base64(self) -> str:
        """Base64-encoded public key."""
        return Base64Encoder.encode(self.public_key_bytes()).decode()

    @staticmethod
    def verify(public_key_b64: str, obj: dict, signature: str) -> bool:
        """Verify signature against public key and content."""
        if not signature.startswith("ed25519:"):
            raise XAPCryptoError("Signature must start with 'ed25519:'")
        sig_b64 = signature[len("ed25519:"):]
        try:
            sig_bytes = Base64Encoder.decode(sig_b64.encode())
            vk = VerifyKey(Base64Encoder.decode(public_key_b64.encode()))
            data = canonical_serialize(obj)
            vk.verify(data, sig_bytes)
            return True
        except (BadSignatureError, Exception):
            return False
