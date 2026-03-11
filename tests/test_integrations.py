"""Tests for XAP framework integrations."""

import pytest

from xap import XAPClient
from xap.integrations.base import XAPIntegrationBase

# Check framework availability
try:
    from langchain.tools import tool as _lc_tool
    HAS_LANGCHAIN = True
except ImportError:
    HAS_LANGCHAIN = False

try:
    from crewai.tools import tool as _cr_tool
    HAS_CREWAI = True
except ImportError:
    try:
        from crewai_tools import tool as _cr_tool
        HAS_CREWAI = True
    except ImportError:
        HAS_CREWAI = False


# --- Base integration tests (no framework dependencies) ---


class TestIntegrationBase:
    def _setup_base_with_provider(self):
        """Create a base integration with a registered provider."""
        base = XAPIntegrationBase.sandbox(balance=1_000_000)
        provider = XAPClient.sandbox(balance=0)
        provider.adapter = base.client.adapter
        provider_identity = provider.identity(
            display_name="TestProvider",
            capabilities=[{
                "name": "text_summarization",
                "version": "1.0.0",
                "pricing": {"model": "fixed", "amount_minor_units": 500, "currency": "USD", "per": "request"},
                "sla": {"max_latency_ms": 2000, "availability_bps": 9900},
            }],
        )
        base.client.discovery.register(provider_identity)
        provider.discovery._registry = base.client.discovery._registry
        return base, provider

    def test_sandbox_creates_client(self):
        base = XAPIntegrationBase.sandbox()
        assert base.client is not None
        assert base.client.agent_id is not None

    def test_sandbox_balance(self):
        base = XAPIntegrationBase.sandbox(balance=500_000)
        balance = base.check_balance()
        assert balance == 500_000

    def test_discover(self):
        base, provider = self._setup_base_with_provider()
        results = base.discover("text_summarization")
        assert len(results["results"]) == 1
        assert results["results"][0]["display_name"] == "TestProvider"

    def test_discover_no_results(self):
        base = XAPIntegrationBase.sandbox()
        results = base.discover("nonexistent_capability")
        assert len(results["results"]) == 0

    def test_create_offer(self):
        base, provider = self._setup_base_with_provider()
        contract = base.create_offer(str(provider.agent_id), "text_summarization", 500)
        assert contract["state"] == "OFFER"
        assert contract["pricing"]["amount_minor_units"] == 500

    def test_accept_offer(self):
        base, provider = self._setup_base_with_provider()
        contract = base.create_offer(str(provider.agent_id), "text_summarization", 500)
        accepted = base.accept_offer(contract)
        assert accepted["state"] == "ACCEPT"

    def test_reject_offer(self):
        base, provider = self._setup_base_with_provider()
        contract = base.create_offer(str(provider.agent_id), "text_summarization", 500)
        rejected = base.reject_offer(contract, reason="Too expensive")
        assert rejected["state"] == "REJECT"

    def test_counter_offer(self):
        base, provider = self._setup_base_with_provider()
        contract = base.create_offer(str(provider.agent_id), "text_summarization", 500)
        counter = base.counter_offer(contract, new_amount=600)
        assert counter["state"] == "COUNTER"
        assert counter["pricing"]["amount_minor_units"] == 600

    def test_respond_to_offer_accept(self):
        base, provider = self._setup_base_with_provider()
        contract = base.create_offer(str(provider.agent_id), "text_summarization", 500)
        result = base.respond_to_offer(contract, "accept")
        assert result["state"] == "ACCEPT"

    def test_respond_to_offer_reject(self):
        base, provider = self._setup_base_with_provider()
        contract = base.create_offer(str(provider.agent_id), "text_summarization", 500)
        result = base.respond_to_offer(contract, "reject", reason="No thanks")
        assert result["state"] == "REJECT"

    def test_respond_to_offer_counter(self):
        base, provider = self._setup_base_with_provider()
        contract = base.create_offer(str(provider.agent_id), "text_summarization", 500)
        result = base.respond_to_offer(contract, "counter", new_amount=700)
        assert result["state"] == "COUNTER"

    def test_respond_to_offer_invalid_action(self):
        base, provider = self._setup_base_with_provider()
        contract = base.create_offer(str(provider.agent_id), "text_summarization", 500)
        with pytest.raises(ValueError, match="Invalid action"):
            base.respond_to_offer(contract, "invalid")

    @pytest.mark.asyncio
    async def test_settle_async(self):
        base, provider = self._setup_base_with_provider()
        contract = base.create_offer(str(provider.agent_id), "text_summarization", 500)
        accepted = provider.negotiation.accept(contract)
        result = await base.settle_async(accepted)
        assert result["outcome"] == "SETTLED"
        assert result["replay_verified"] is True
        assert result["total_paid"] == 500

    @pytest.mark.asyncio
    async def test_settle_async_wrong_state(self):
        base, provider = self._setup_base_with_provider()
        contract = base.create_offer(str(provider.agent_id), "text_summarization", 500)
        with pytest.raises(ValueError, match="ACCEPT state"):
            await base.settle_async(contract)

    def test_full_flow(self):
        """Test discover -> offer -> accept -> settle -> verify via base."""
        base, provider = self._setup_base_with_provider()

        # Discover
        results = base.discover("text_summarization")
        assert len(results["results"]) >= 1

        # Offer
        contract = base.create_offer(str(provider.agent_id), "text_summarization", 500)
        assert contract["state"] == "OFFER"

        # Accept (provider side)
        accepted = provider.negotiation.accept(contract)
        assert accepted["state"] == "ACCEPT"

        # Settle
        result = base.settle(accepted)
        assert result["outcome"] == "SETTLED"
        assert result["replay_verified"] is True
        assert result["receipt_id"].startswith("rcpt_")
        assert result["verity_id"].startswith("vrt_")
        assert result["total_paid"] == 500

        # Balance check
        buyer_balance = base.check_balance()
        assert buyer_balance == 1_000_000 - 500

    def test_format_result_dict(self):
        base = XAPIntegrationBase.sandbox()
        result = base._format_result({"key": "value"})
        assert '"key"' in result
        assert '"value"' in result

    def test_format_result_bool(self):
        base = XAPIntegrationBase.sandbox()
        result = base._format_result(True)
        assert '"result": true' in result

    def test_format_result_int(self):
        base = XAPIntegrationBase.sandbox()
        result = base._format_result(42)
        assert '"balance": 42' in result


# --- LangChain integration tests ---


class TestLangChainIntegration:
    def test_import_error_without_langchain(self):
        """Verify clean error message if langchain not installed."""
        if HAS_LANGCHAIN:
            pytest.skip("langchain is installed")
        from xap.integrations.langchain import XAPToolkit
        toolkit = XAPToolkit.sandbox()
        with pytest.raises(ImportError, match="langchain is required"):
            toolkit.get_tools()

    @pytest.mark.skipif(not HAS_LANGCHAIN, reason="langchain not installed")
    def test_toolkit_returns_six_tools(self):
        from xap.integrations.langchain import XAPToolkit
        toolkit = XAPToolkit.sandbox()
        tools = toolkit.get_tools()
        assert len(tools) == 6

    @pytest.mark.skipif(not HAS_LANGCHAIN, reason="langchain not installed")
    def test_toolkit_tool_names(self):
        from xap.integrations.langchain import XAPToolkit
        toolkit = XAPToolkit.sandbox()
        tools = toolkit.get_tools()
        names = {t.name for t in tools}
        expected = {
            "xap_discover_agents",
            "xap_create_offer",
            "xap_respond_to_offer",
            "xap_settle",
            "xap_verify_receipt",
            "xap_check_balance",
        }
        assert names == expected

    @pytest.mark.skipif(not HAS_LANGCHAIN, reason="langchain not installed")
    def test_toolkit_discover_invocation(self):
        from xap.integrations.langchain import XAPToolkit
        toolkit = XAPToolkit.sandbox()

        provider = XAPClient.sandbox()
        provider.adapter = toolkit.client.adapter
        identity = provider.identity(
            display_name="LCTestBot",
            capabilities=[{
                "name": "test_cap",
                "version": "1.0.0",
                "pricing": {"model": "fixed", "amount_minor_units": 100, "currency": "USD", "per": "request"},
                "sla": {"max_latency_ms": 1000, "availability_bps": 9900},
            }],
        )
        toolkit.client.discovery.register(identity)

        tools = toolkit.get_tools()
        result = tools[0].invoke({"capability": "test_cap"})
        assert "LCTestBot" in result


# --- CrewAI integration tests ---


class TestCrewAIIntegration:
    def test_import_error_without_crewai(self):
        """Verify clean error message if crewai not installed."""
        if HAS_CREWAI:
            pytest.skip("crewai is installed")
        from xap.integrations.crewai import XAPCrewTools
        crew_tools = XAPCrewTools.sandbox()
        with pytest.raises(ImportError, match="crewai is required"):
            crew_tools.get_tools()

    @pytest.mark.skipif(not HAS_CREWAI, reason="crewai not installed")
    def test_crew_tools_returns_six(self):
        from xap.integrations.crewai import XAPCrewTools
        crew_tools = XAPCrewTools.sandbox()
        tools = crew_tools.get_tools()
        assert len(tools) == 6

    @pytest.mark.skipif(not HAS_CREWAI, reason="crewai not installed")
    def test_crew_tool_names(self):
        from xap.integrations.crewai import XAPCrewTools
        crew_tools = XAPCrewTools.sandbox()
        tools = crew_tools.get_tools()
        names = {t.name for t in tools}
        expected = {
            "XAP Discover Agents",
            "XAP Create Offer",
            "XAP Respond to Offer",
            "XAP Settle",
            "XAP Verify Receipt",
            "XAP Check Balance",
        }
        assert names == expected
