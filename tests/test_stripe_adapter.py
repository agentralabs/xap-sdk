"""Tests for Stripe adapter and webhook handler.

All tests work WITHOUT a real Stripe API key.
"""

import os

import pytest

from xap.adapters.stripe_adapter import StripeAdapter
from xap.adapters.stripe_webhooks import StripeWebhookHandler


class TestStripeAdapterInit:
    def test_validates_key_format(self):
        with pytest.raises(ValueError, match="sk_test_ or sk_live_"):
            StripeAdapter(api_key="invalid_key")

    def test_rejects_empty_key(self):
        with pytest.raises(ValueError):
            StripeAdapter(api_key="")

    def test_rejects_pk_key(self):
        with pytest.raises(ValueError):
            StripeAdapter(api_key="pk_test_12345")

    def test_accepts_test_key(self):
        adapter = StripeAdapter(api_key="sk_test_fake123")
        assert adapter.api_key == "sk_test_fake123"

    def test_accepts_live_key(self):
        adapter = StripeAdapter(api_key="sk_live_fake123")
        assert adapter.api_key == "sk_live_fake123"

    def test_identifies_test_mode(self):
        adapter = StripeAdapter(api_key="sk_test_fake123")
        assert adapter.is_test is True

    def test_identifies_live_mode(self):
        adapter = StripeAdapter(api_key="sk_live_fake123")
        assert adapter.is_test is False

    def test_adapter_type(self):
        adapter = StripeAdapter(api_key="sk_test_fake123")
        assert adapter.adapter_type() == "stripe"

    def test_default_finality(self):
        adapter = StripeAdapter(api_key="sk_test_fake123")
        assert adapter.default_finality() == "within_reversal_window"

    def test_webhook_secret_stored(self):
        adapter = StripeAdapter(api_key="sk_test_fake123", webhook_secret="whsec_abc")
        assert adapter.webhook_secret == "whsec_abc"

    def test_webhook_secret_default_none(self):
        adapter = StripeAdapter(api_key="sk_test_fake123")
        assert adapter.webhook_secret is None


class TestStripeAccountMapping:
    def test_map_agent(self):
        adapter = StripeAdapter(api_key="sk_test_fake123")
        adapter.map_agent_to_stripe_account("agent_12345678", "acct_stripe123")
        assert adapter._account_map["agent_12345678"] == "acct_stripe123"

    def test_map_multiple_agents(self):
        adapter = StripeAdapter(api_key="sk_test_fake123")
        adapter.map_agent_to_stripe_account("agent_aaaaaaaa", "acct_a")
        adapter.map_agent_to_stripe_account("agent_bbbbbbbb", "acct_b")
        assert len(adapter._account_map) == 2
        assert adapter._account_map["agent_aaaaaaaa"] == "acct_a"
        assert adapter._account_map["agent_bbbbbbbb"] == "acct_b"

    def test_overwrite_mapping(self):
        adapter = StripeAdapter(api_key="sk_test_fake123")
        adapter.map_agent_to_stripe_account("agent_12345678", "acct_old")
        adapter.map_agent_to_stripe_account("agent_12345678", "acct_new")
        assert adapter._account_map["agent_12345678"] == "acct_new"

    def test_empty_map_by_default(self):
        adapter = StripeAdapter(api_key="sk_test_fake123")
        assert len(adapter._account_map) == 0


class TestStripeWebhookHandler:
    def test_payment_intent_succeeded(self):
        handler = StripeWebhookHandler(webhook_secret="whsec_fake")
        result = handler.handle_event({
            "type": "payment_intent.succeeded",
            "data": {"object": {"id": "pi_123"}},
        })
        assert result["action"] == "confirm_lock"
        assert result["data"]["id"] == "pi_123"

    def test_payment_intent_failed(self):
        handler = StripeWebhookHandler(webhook_secret="whsec_fake")
        result = handler.handle_event({
            "type": "payment_intent.payment_failed",
            "data": {"object": {"id": "pi_456"}},
        })
        assert result["action"] == "lock_failed"

    def test_charge_dispute_created(self):
        handler = StripeWebhookHandler(webhook_secret="whsec_fake")
        result = handler.handle_event({
            "type": "charge.dispute.created",
            "data": {"object": {"id": "dp_789"}},
        })
        assert result["action"] == "initiate_dispute"

    def test_charge_refunded(self):
        handler = StripeWebhookHandler(webhook_secret="whsec_fake")
        result = handler.handle_event({
            "type": "charge.refunded",
            "data": {"object": {"id": "ch_abc"}},
        })
        assert result["action"] == "confirm_refund"

    def test_transfer_created(self):
        handler = StripeWebhookHandler(webhook_secret="whsec_fake")
        result = handler.handle_event({
            "type": "transfer.created",
            "data": {"object": {"id": "tr_123"}},
        })
        assert result["action"] == "confirm_transfer"

    def test_transfer_failed(self):
        handler = StripeWebhookHandler(webhook_secret="whsec_fake")
        result = handler.handle_event({
            "type": "transfer.failed",
            "data": {"object": {"id": "tr_456"}},
        })
        assert result["action"] == "transfer_failed"

    def test_unknown_event_ignored(self):
        handler = StripeWebhookHandler(webhook_secret="whsec_fake")
        result = handler.handle_event({
            "type": "some.unknown.event",
            "data": {"object": {}},
        })
        assert result["action"] == "ignore"
        assert result["event_type"] == "some.unknown.event"

    def test_webhook_secret_stored(self):
        handler = StripeWebhookHandler(webhook_secret="whsec_test123")
        assert handler.webhook_secret == "whsec_test123"


class TestStripeAdapterLive:
    """Tests that require a real Stripe test key."""

    @pytest.mark.skipif(
        not os.environ.get("STRIPE_TEST_KEY"),
        reason="STRIPE_TEST_KEY not set",
    )
    @pytest.mark.asyncio
    async def test_stripe_live_lock(self):
        key = os.environ["STRIPE_TEST_KEY"]
        adapter = StripeAdapter(api_key=key)
        settlement = {
            "settlement_id": "stl_test1234",
            "total_amount_minor_units": 1000,
            "currency": "USD",
            "payer_agent": "agent_test1234",
            "xap_version": "0.2.0",
        }
        result = await adapter.lock_funds(settlement)
        assert result["status"] == "locked"
        assert result["payment_intent_id"].startswith("pi_")
        assert result["amount_authorized"] == 1000
