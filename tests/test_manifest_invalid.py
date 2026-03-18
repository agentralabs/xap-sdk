"""Invalid manifest tests — edge cases that must be rejected."""

import pytest

from xap import AgentManifest, XAPSigner, XAPValidationError


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


class TestAgentManifestInvalid:
    """Invalid manifest construction tests."""

    def test_empty_capabilities_rejected(self):
        signer = XAPSigner.generate()
        with pytest.raises(XAPValidationError):
            AgentManifest.build(
                agent_id="a1b2c3d4",
                signer=signer,
                capabilities=[],
                economic_terms=_economic_terms(),
            )

    def test_missing_accepted_currencies_rejected(self):
        signer = XAPSigner.generate()
        with pytest.raises(XAPValidationError):
            AgentManifest.build(
                agent_id="a1b2c3d4",
                signer=signer,
                capabilities=_capabilities(),
                economic_terms={"accepted_condition_types": ["deterministic"], "min_amount_minor": 100, "max_amount_minor": 50000},
            )

    def test_zero_min_amount_rejected(self):
        signer = XAPSigner.generate()
        with pytest.raises(XAPValidationError):
            AgentManifest.build(
                agent_id="a1b2c3d4",
                signer=signer,
                capabilities=_capabilities(),
                economic_terms=_economic_terms(min_amount_minor=0),
            )

    def test_invalid_condition_type_rejected(self):
        signer = XAPSigner.generate()
        with pytest.raises(XAPValidationError):
            AgentManifest.build(
                agent_id="a1b2c3d4",
                signer=signer,
                capabilities=_capabilities(),
                economic_terms=_economic_terms(accepted_condition_types=["magic"]),
            )

    def test_success_rate_over_10000_rejected(self):
        signer = XAPSigner.generate()
        bad_caps = [{
            "name": "test", "version": "1.0.0",
            "attestation": {"total_settlements": 10, "success_rate_bps": 15000, "window_days": 90, "receipt_hashes": []},
        }]
        with pytest.raises(XAPValidationError):
            AgentManifest.build(
                agent_id="a1b2c3d4", signer=signer, capabilities=bad_caps, economic_terms=_economic_terms(),
            )

    def test_negative_settlements_rejected(self):
        signer = XAPSigner.generate()
        bad_caps = [{
            "name": "test", "version": "1.0.0",
            "attestation": {"total_settlements": -1, "success_rate_bps": 0, "window_days": 90, "receipt_hashes": []},
        }]
        with pytest.raises(XAPValidationError):
            AgentManifest.build(
                agent_id="a1b2c3d4", signer=signer, capabilities=bad_caps, economic_terms=_economic_terms(),
            )

    def test_bad_manifest_id_format_rejected(self):
        signer = XAPSigner.generate()
        with pytest.raises(XAPValidationError):
            AgentManifest.build(
                agent_id="a1b2c3d4", signer=signer, capabilities=_capabilities(),
                economic_terms=_economic_terms(), manifest_id="INVALID",
            )

    def test_window_days_zero_rejected(self):
        signer = XAPSigner.generate()
        bad_caps = [{
            "name": "test", "version": "1.0.0",
            "attestation": {"total_settlements": 0, "success_rate_bps": 0, "window_days": 0, "receipt_hashes": []},
        }]
        with pytest.raises(XAPValidationError):
            AgentManifest.build(
                agent_id="a1b2c3d4", signer=signer, capabilities=bad_caps, economic_terms=_economic_terms(),
            )

    def test_missing_attestation_rejected(self):
        signer = XAPSigner.generate()
        with pytest.raises(XAPValidationError):
            AgentManifest.build(
                agent_id="a1b2c3d4", signer=signer, capabilities=[{"name": "test", "version": "1.0.0"}],
                economic_terms=_economic_terms(),
            )

    def test_too_many_receipt_hashes_rejected(self):
        signer = XAPSigner.generate()
        bad_caps = [{
            "name": "test", "version": "1.0.0",
            "attestation": {
                "total_settlements": 100, "success_rate_bps": 9000, "window_days": 90,
                "receipt_hashes": [f"vrt_{'a' * 64}" for _ in range(11)],
            },
        }]
        with pytest.raises(XAPValidationError):
            AgentManifest.build(
                agent_id="a1b2c3d4", signer=signer, capabilities=bad_caps, economic_terms=_economic_terms(),
            )
