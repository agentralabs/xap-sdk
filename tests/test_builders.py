"""Tests for xap.builders — object builders."""

import pytest
from xap.crypto import XAPSigner
from xap.types import AgentId, SettlementId, ContractId
from xap.errors import XAPBuilderError
from xap.builders import (
    AgentIdentityBuilder,
    NegotiationContractBuilder,
    SettlementIntentBuilder,
    VerityReceiptBuilder,
    RegistryQueryBuilder,
    RegistryResponseBuilder,
)


class TestAgentIdentityBuilder:
    def test_minimal_build(self):
        signer = XAPSigner.generate()
        obj = (
            AgentIdentityBuilder(signer)
            .agent_id(AgentId.generate())
            .add_capability(
                name="summarize",
                version="1.0.0",
                pricing={"model": "fixed", "amount_minor_units": 100, "currency": "USD", "per": "request"},
                sla={"max_latency_ms": 2000, "availability_bps": 9900},
            )
            .build()
        )
        assert obj["xap_version"] == "0.2.0"
        assert obj["signature"].startswith("ed25519:")
        assert len(obj["capabilities"]) == 1

    def test_full_build_with_org(self):
        signer = XAPSigner.generate()
        obj = (
            AgentIdentityBuilder(signer)
            .agent_id(AgentId.generate())
            .display_name("OrgBot")
            .org("org_12345678", "team_abcdef01")
            .add_capability(
                name="translate",
                version="2.0.0",
                pricing={"model": "dynamic", "amount_minor_units": 50, "currency": "EUR", "per": "token"},
                sla={"max_latency_ms": 1000, "availability_bps": 9950},
            )
            .build()
        )
        assert obj["org_id"] == "org_12345678"
        assert obj["team_id"] == "team_abcdef01"
        assert obj["display_name"] == "OrgBot"

    def test_missing_agent_id_raises(self):
        signer = XAPSigner.generate()
        with pytest.raises(XAPBuilderError, match="agent_id"):
            (
                AgentIdentityBuilder(signer)
                .add_capability(
                    name="test",
                    version="1.0.0",
                    pricing={"model": "fixed", "amount_minor_units": 100, "currency": "USD", "per": "request"},
                    sla={"max_latency_ms": 1000, "availability_bps": 9000},
                )
                .build()
            )

    def test_missing_capability_raises(self):
        signer = XAPSigner.generate()
        with pytest.raises(XAPBuilderError, match="capability"):
            AgentIdentityBuilder(signer).agent_id(AgentId.generate()).build()


class TestNegotiationContractBuilder:
    def _make_task(self):
        return {"type": "text_summarization"}

    def _make_pricing(self):
        return {"amount_minor_units": 300, "currency": "USD", "model": "fixed", "per": "request"}

    def _make_sla(self):
        return {"max_latency_ms": 3000}

    def test_offer(self):
        signer = XAPSigner.generate()
        builder = NegotiationContractBuilder(signer)
        offer = (
            builder
            .new_offer(
                AgentId.generate(),
                AgentId.generate(),
                self._make_task(),
                self._make_pricing(),
                self._make_sla(),
            )
            .build()
        )
        assert offer["state"] == "OFFER"
        assert offer["round_number"] == 1
        assert offer["signature"].startswith("ed25519:")

    def test_counter(self):
        signer1 = XAPSigner.generate()
        signer2 = XAPSigner.generate()
        offer = (
            NegotiationContractBuilder(signer1)
            .new_offer(
                AgentId.generate(),
                AgentId.generate(),
                self._make_task(),
                self._make_pricing(),
                self._make_sla(),
            )
            .build()
        )
        counter = (
            NegotiationContractBuilder(signer2)
            .counter(offer, new_pricing={"amount_minor_units": 250, "currency": "USD", "model": "fixed", "per": "request"})
            .build()
        )
        assert counter["state"] == "COUNTER"
        assert counter["round_number"] == 2
        assert counter["pricing"]["amount_minor_units"] == 250
        assert "previous_state_hash" in counter

    def test_accept(self):
        signer1 = XAPSigner.generate()
        signer2 = XAPSigner.generate()
        offer = (
            NegotiationContractBuilder(signer1)
            .new_offer(
                AgentId.generate(),
                AgentId.generate(),
                self._make_task(),
                self._make_pricing(),
                self._make_sla(),
            )
            .build()
        )
        accepted = NegotiationContractBuilder(signer2).accept(offer)
        assert accepted["state"] == "ACCEPT"
        assert "previous_state_hash" in accepted

    def test_reject(self):
        signer1 = XAPSigner.generate()
        signer2 = XAPSigner.generate()
        offer = (
            NegotiationContractBuilder(signer1)
            .new_offer(
                AgentId.generate(),
                AgentId.generate(),
                self._make_task(),
                self._make_pricing(),
                self._make_sla(),
            )
            .build()
        )
        rejected = NegotiationContractBuilder(signer2).reject(offer)
        assert rejected["state"] == "REJECT"


class TestSettlementIntentBuilder:
    def test_single_payee(self):
        signer = XAPSigner.generate()
        obj = (
            SettlementIntentBuilder(signer)
            .payer(AgentId.generate())
            .add_payee(AgentId.generate(), 10000, "primary_executor")
            .amount(50000, "USD")
            .add_condition({
                "condition_id": "cond_0001",
                "type": "deterministic",
                "check": "http_200",
                "verifier": "engine",
                "required": True,
            })
            .build()
        )
        assert obj["state"] == "PENDING_LOCK"
        assert obj["total_amount_minor_units"] == 50000
        assert len(obj["payee_agents"]) == 1
        assert obj["signature"].startswith("ed25519:")

    def test_multi_payee(self):
        signer = XAPSigner.generate()
        obj = (
            SettlementIntentBuilder(signer)
            .payer(AgentId.generate())
            .add_payee(AgentId.generate(), 6000, "primary_executor")
            .add_payee(AgentId.generate(), 2500, "data_provider")
            .add_payee(AgentId.generate(), 1500, "platform")
            .amount(100000, "USD")
            .add_condition({
                "condition_id": "cond_0001",
                "type": "deterministic",
                "check": "task_complete",
                "verifier": "engine",
                "required": True,
            })
            .build()
        )
        assert len(obj["payee_agents"]) == 3
        shares = [p["share_bps"] for p in obj["payee_agents"]]
        assert sum(shares) == 10000

    def test_missing_payer_raises(self):
        signer = XAPSigner.generate()
        with pytest.raises(XAPBuilderError, match="payer"):
            (
                SettlementIntentBuilder(signer)
                .add_payee(AgentId.generate(), 10000)
                .amount(1000)
                .add_condition({"condition_id": "cond_0001", "type": "deterministic", "check": "x", "verifier": "engine", "required": True})
                .build()
            )


class TestVerityReceiptBuilder:
    def test_build_with_auto_replay_hash(self):
        signer = XAPSigner.generate()
        obj = (
            VerityReceiptBuilder(signer)
            .settlement_id(str(SettlementId.generate()))
            .decision_type("condition_verification")
            .input_state({
                "settlement_state": "PENDING_VERIFICATION",
                "contract_terms": {"pricing": {}, "sla": {}, "conditions": []},
                "agent_states": [{"agent_id": "agent_00000001", "role": "payer"}],
            })
            .rules_applied({
                "rules_version": "1.0.0",
                "rules_hash": "sha256:" + "a" * 64,
                "applicable_rules": [{"rule_id": "r1", "rule_description": "check all", "evaluated": True, "result": "pass"}],
            })
            .computation({
                "steps": [{"step_number": 1, "operation": "evaluate", "inputs": {}, "output": {"result": "pass"}, "deterministic": True}],
                "total_steps": 1,
                "computation_duration_ms": 5,
            })
            .outcome({
                "decision": "release_funds",
                "settlement_state_after": "SETTLED",
                "outcome_classification": "SUCCESS",
            })
            .build()
        )
        assert obj["replay_hash"].startswith("sha256:")
        assert obj["verity_signature"].startswith("ed25519:")
        assert obj["confidence_bps"] == 10000


class TestRegistryQueryBuilder:
    def test_simple_query(self):
        query = (
            RegistryQueryBuilder(AgentId.generate())
            .capability("text_summarization")
            .build()
        )
        assert query["filters"]["capability"]["name"] == "text_summarization"
        assert query["xap_version"] == "0.2.0"

    def test_complex_query(self):
        query = (
            RegistryQueryBuilder(AgentId.generate())
            .capability("translate")
            .min_reputation(9500)
            .max_price(1000, "USD")
            .max_latency(2000)
            .limit(10)
            .build()
        )
        assert query["filters"]["capability"]["name"] == "translate"
        assert query["filters"]["reputation"]["min_success_rate_bps"] == 9500
        assert query["filters"]["pricing"]["max_amount_minor_units"] == 1000
        assert query["filters"]["sla"]["max_latency_ms"] == 2000
        assert query["pagination"]["limit"] == 10


class TestRegistryResponseBuilder:
    def test_empty_response(self):
        resp = RegistryResponseBuilder("qry_12345678").build()
        assert resp["total_count"] == 0
        assert resp["results"] == []

    def test_with_results(self):
        resp = (
            RegistryResponseBuilder("qry_12345678")
            .add_result({
                "agent_id": "agent_aabbccdd",
                "capabilities_matched": [{
                    "name": "summarize",
                    "version": "1.0.0",
                    "pricing": {"model": "fixed", "amount_minor_units": 300, "currency": "USD", "per": "request"},
                    "sla": {"max_latency_ms": 2000, "availability_bps": 9900},
                }],
                "reputation_summary": {
                    "success_rate_bps": 9700,
                    "total_settlements": 150,
                    "dispute_rate_bps": 100,
                    "avg_quality_score_bps": 8500,
                },
                "status": "active",
                "relevance_score_bps": 8900,
                "registered_at": "2026-01-01T00:00:00Z",
            })
            .build()
        )
        assert resp["total_count"] == 1
        assert resp["results"][0]["agent_id"] == "agent_aabbccdd"
