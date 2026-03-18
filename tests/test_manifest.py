"""Tests for AgentManifest builder, signer, and verifier."""

import pytest

from xap import XAPClient, AgentManifest, XAPSigner
from xap.verify import verify_manifest


def _economic_terms(**overrides):
    terms = {
        "accepted_currencies": ["USD"],
        "accepted_condition_types": ["deterministic"],
        "min_amount_minor": 100,
        "max_amount_minor": 50000,
    }
    terms.update(overrides)
    return terms


def _capabilities(total_settlements=0, success_rate_bps=0):
    return [{
        "name": "code_review",
        "version": "1.0.0",
        "attestation": {
            "total_settlements": total_settlements,
            "success_rate_bps": success_rate_bps,
            "window_days": 90,
            "receipt_hashes": [],
        },
    }]


class TestAgentManifestBuilder:
    """Valid manifest construction tests."""

    def test_build_minimal_manifest(self):
        signer = XAPSigner.generate()
        manifest = AgentManifest.build(
            agent_id="a1b2c3d4",
            signer=signer,
            capabilities=_capabilities(),
            economic_terms=_economic_terms(),
        )
        assert manifest["manifest_id"].startswith("mnf_")
        assert manifest["agent_id"] == "a1b2c3d4"
        assert manifest["xap_version"] == "0.2"
        assert manifest["signature"]["algorithm"] == "Ed25519"

    def test_build_with_registry_url(self):
        signer = XAPSigner.generate()
        manifest = AgentManifest.build(
            agent_id="a1b2c3d4",
            signer=signer,
            capabilities=_capabilities(),
            economic_terms=_economic_terms(),
            registry_url="https://app.zexrail.com",
        )
        assert manifest["registry_url"] == "https://app.zexrail.com"

    def test_build_with_federation_hints(self):
        signer = XAPSigner.generate()
        manifest = AgentManifest.build(
            agent_id="a1b2c3d4",
            signer=signer,
            capabilities=_capabilities(),
            economic_terms=_economic_terms(),
            federation_hints={"also_registered_at": [], "identity_portable_proof": "proof"},
        )
        assert "federation_hints" in manifest

    def test_build_with_full_economic_terms(self):
        signer = XAPSigner.generate()
        terms = _economic_terms(
            accepted_adapters=["stripe", "usdc"],
            chargeback_policy="PROPORTIONAL",
            min_negotiation_rounds=1,
            max_concurrent=50,
        )
        manifest = AgentManifest.build(
            agent_id="a1b2c3d4",
            signer=signer,
            capabilities=_capabilities(847, 9430),
            economic_terms=terms,
        )
        assert manifest["economic_terms"]["chargeback_policy"] == "PROPORTIONAL"
        assert manifest["capabilities"][0]["attestation"]["total_settlements"] == 847

    def test_build_with_custom_manifest_id(self):
        signer = XAPSigner.generate()
        manifest = AgentManifest.build(
            agent_id="a1b2c3d4",
            signer=signer,
            capabilities=_capabilities(),
            economic_terms=_economic_terms(),
            manifest_id="mnf_deadbeef",
        )
        assert manifest["manifest_id"] == "mnf_deadbeef"


class TestAgentManifestSignature:
    """Signature verification tests."""

    def test_verify_valid_signature(self):
        signer = XAPSigner.generate()
        manifest = AgentManifest.build(
            agent_id="a1b2c3d4",
            signer=signer,
            capabilities=_capabilities(),
            economic_terms=_economic_terms(),
        )
        assert AgentManifest.verify(manifest)

    def test_tampered_manifest_fails_verification(self):
        signer = XAPSigner.generate()
        manifest = AgentManifest.build(
            agent_id="a1b2c3d4",
            signer=signer,
            capabilities=_capabilities(),
            economic_terms=_economic_terms(),
        )
        manifest["agent_id"] = "deadbeef"
        assert not AgentManifest.verify(manifest)

    def test_wrong_key_fails_verification(self):
        signer1 = XAPSigner.generate()
        signer2 = XAPSigner.generate()
        manifest = AgentManifest.build(
            agent_id="a1b2c3d4",
            signer=signer1,
            capabilities=_capabilities(),
            economic_terms=_economic_terms(),
        )
        # Replace the public key with a different one
        manifest["signature"]["public_key"] = signer2.public_key_base64()
        assert not AgentManifest.verify(manifest)

    def test_empty_signature_fails(self):
        signer = XAPSigner.generate()
        manifest = AgentManifest.build(
            agent_id="a1b2c3d4",
            signer=signer,
            capabilities=_capabilities(),
            economic_terms=_economic_terms(),
        )
        manifest["signature"]["value"] = ""
        assert not AgentManifest.verify(manifest)


class TestAgentManifestExpiry:
    """Expiry check tests."""

    def test_fresh_manifest_not_expired(self):
        signer = XAPSigner.generate()
        manifest = AgentManifest.build(
            agent_id="a1b2c3d4",
            signer=signer,
            capabilities=_capabilities(),
            economic_terms=_economic_terms(),
        )
        assert not AgentManifest.is_expired(manifest)

    def test_old_manifest_is_expired(self):
        manifest = {
            "expires_at": "2020-01-01T00:00:00Z",
        }
        assert AgentManifest.is_expired(manifest)


class TestVerifyManifest:
    """Tests for the standalone verify_manifest function."""

    def test_valid_manifest_passes(self):
        signer = XAPSigner.generate()
        manifest = AgentManifest.build(
            agent_id="a1b2c3d4",
            signer=signer,
            capabilities=_capabilities(),
            economic_terms=_economic_terms(),
        )
        result = verify_manifest(manifest)
        assert result.valid
        assert result.schema_valid
        assert result.signature_valid
        assert result.not_expired

    def test_invalid_json_string(self):
        result = verify_manifest("{bad json")
        assert not result.valid
        assert "Invalid JSON" in result.errors[0]

    def test_tampered_manifest_fails(self):
        signer = XAPSigner.generate()
        manifest = AgentManifest.build(
            agent_id="a1b2c3d4",
            signer=signer,
            capabilities=_capabilities(),
            economic_terms=_economic_terms(),
        )
        manifest["agent_id"] = "deadbeef"
        result = verify_manifest(manifest)
        assert not result.valid
        assert result.schema_valid
        assert not result.signature_valid


class TestXAPClientManifest:
    """Tests for XAPClient.manifest property."""

    def test_client_manifest_build(self):
        client = XAPClient.sandbox()
        manifest = client.manifest.build(
            capabilities=_capabilities(),
            economic_terms=_economic_terms(),
        )
        assert manifest["agent_id"] == str(client.agent_id)
        assert manifest["xap_version"] == "0.2"

    def test_client_manifest_verify(self):
        client = XAPClient.sandbox()
        manifest = client.manifest.build(
            capabilities=_capabilities(),
            economic_terms=_economic_terms(),
        )
        assert client.manifest.verify(manifest)

    def test_client_manifest_not_expired(self):
        client = XAPClient.sandbox()
        manifest = client.manifest.build(
            capabilities=_capabilities(),
            economic_terms=_economic_terms(),
        )
        assert not client.manifest.is_expired(manifest)


class TestDiscoveryWithManifest:
    """Tests for discovery search with manifests."""

    def _cap(self, name="test_cap", amount=1000):
        return {
            "name": name,
            "version": "1.0.0",
            "pricing": {"amount_minor_units": amount, "currency": "USD", "model": "fixed", "per": "request"},
            "sla": {"max_latency_ms": 1000, "availability_bps": 9900},
        }

    def test_search_includes_manifest(self):
        client = XAPClient.sandbox()
        identity = client.identity(
            display_name="ManifestBot",
            capabilities=[self._cap("search", 100)],
        )
        manifest = client.manifest.build(
            capabilities=_capabilities(),
            economic_terms=_economic_terms(),
        )
        client.discovery.register(identity, manifest=manifest)
        results = client.discovery.search(capability="search", include_manifest=True)
        assert len(results["results"]) == 1
        assert "manifest" in results["results"][0]

    def test_search_without_manifest(self):
        client = XAPClient.sandbox()
        identity = client.identity(
            display_name="NoManifestBot",
            capabilities=[self._cap("search", 100)],
        )
        client.discovery.register(identity)
        results = client.discovery.search(capability="search", include_manifest=True)
        assert len(results["results"]) == 1
        assert "manifest" not in results["results"][0]
