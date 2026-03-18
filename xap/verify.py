"""Standalone manifest verifier for XAP v0.2.

Usage:
    from xap.verify import verify_manifest

    result = verify_manifest(manifest_json)
    assert result.valid
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from xap.manifest import AgentManifest
from xap.schemas.validator import SchemaValidator
from xap.errors import XAPValidationError


@dataclass
class VerificationResult:
    """Result of manifest verification."""
    valid: bool
    schema_valid: bool = False
    signature_valid: bool = False
    not_expired: bool = False
    errors: list[str] = field(default_factory=list)


def verify_manifest(manifest: dict | str) -> VerificationResult:
    """Verify an AgentManifest: schema, signature, and expiry.

    Args:
        manifest: Dict or JSON string of an AgentManifest.

    Returns:
        VerificationResult with detailed check results.
    """
    if isinstance(manifest, str):
        try:
            manifest = json.loads(manifest)
        except json.JSONDecodeError as e:
            return VerificationResult(valid=False, errors=[f"Invalid JSON: {e}"])

    result = VerificationResult(valid=False)

    # 1. Schema validation
    try:
        SchemaValidator().validate_agent_manifest(manifest)
        result.schema_valid = True
    except XAPValidationError as e:
        result.errors.append(f"Schema: {e}")
        return result

    # 2. Signature verification
    result.signature_valid = AgentManifest.verify(manifest)
    if not result.signature_valid:
        result.errors.append("Signature verification failed")

    # 3. Expiry check
    result.not_expired = not AgentManifest.is_expired(manifest)
    if not result.not_expired:
        result.errors.append("Manifest has expired")

    result.valid = result.schema_valid and result.signature_valid and result.not_expired
    return result
