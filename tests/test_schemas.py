"""Tests for xap.schemas — schema loading and validation."""

import pytest
from xap.schemas.loader import load_schema, load_all_schemas, SCHEMA_NAMES
from xap.schemas.validator import SchemaValidator
from xap.errors import XAPValidationError
from xap.crypto import XAPSigner
from xap.builders import AgentIdentityBuilder, RegistryQueryBuilder
from xap.types import AgentId


class TestSchemaLoader:
    def test_load_all_schemas(self):
        schemas = load_all_schemas()
        assert len(schemas) == 8

    @pytest.mark.parametrize("name", SCHEMA_NAMES)
    def test_load_each_schema(self, name):
        schema = load_schema(name)
        assert "$schema" in schema
        assert "type" in schema

    def test_load_nonexistent_raises(self):
        with pytest.raises(FileNotFoundError):
            load_schema("nonexistent")


class TestSchemaValidator:
    def test_valid_agent_identity(self):
        signer = XAPSigner.generate()
        builder = AgentIdentityBuilder(signer)
        obj = (
            builder
            .agent_id(AgentId.generate())
            .add_capability(
                name="text_summarization",
                version="1.0.0",
                pricing={"model": "fixed", "amount_minor_units": 300, "currency": "USD", "per": "request"},
                sla={"max_latency_ms": 3000, "availability_bps": 9900},
            )
            .build()
        )
        # Should not raise — builder validates internally
        SchemaValidator().validate_agent_identity(obj)

    def test_invalid_agent_identity(self):
        with pytest.raises(XAPValidationError):
            SchemaValidator().validate_agent_identity({"agent_id": "bad"})

    def test_valid_registry_query(self):
        query = (
            RegistryQueryBuilder(AgentId.generate())
            .capability("text_summarization")
            .build()
        )
        SchemaValidator().validate_registry_query(query)

    def test_invalid_registry_query(self):
        with pytest.raises(XAPValidationError):
            SchemaValidator().validate_registry_query({})

    def test_builder_output_validates(self):
        signer = XAPSigner.generate()
        builder = AgentIdentityBuilder(signer)
        obj = (
            builder
            .agent_id(AgentId.generate())
            .display_name("Test Agent")
            .add_capability(
                name="code_review",
                version="2.0.0",
                pricing={"model": "fixed", "amount_minor_units": 500, "currency": "USD", "per": "request"},
                sla={"max_latency_ms": 5000, "availability_bps": 9500},
                description="Reviews code for quality and security",
            )
            .build()
        )
        # Double validate — should still pass
        SchemaValidator().validate_agent_identity(obj)
        assert obj["agent_id"].startswith("agent_")
        assert obj["signature"].startswith("ed25519:")
