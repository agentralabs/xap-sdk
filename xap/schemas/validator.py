"""Validate XAP objects against their JSON schemas."""

from __future__ import annotations

import jsonschema

from xap.errors import XAPValidationError
from xap.schemas.loader import load_schema


class SchemaValidator:
    """Validate XAP objects against their JSON schemas."""

    def validate_agent_identity(self, obj: dict) -> None:
        """Validate an AgentIdentity object."""
        self.validate("agent-identity", obj)

    def validate_negotiation_contract(self, obj: dict) -> None:
        """Validate a NegotiationContract object."""
        self.validate("negotiation-contract", obj)

    def validate_settlement_intent(self, obj: dict) -> None:
        """Validate a SettlementIntent object."""
        self.validate("settlement-intent", obj)

    def validate_execution_receipt(self, obj: dict) -> None:
        """Validate an ExecutionReceipt object."""
        self.validate("execution-receipt", obj)

    def validate_verity_receipt(self, obj: dict) -> None:
        """Validate a VerityReceipt object."""
        self.validate("verity-receipt", obj)

    def validate_registry_query(self, obj: dict) -> None:
        """Validate a RegistryQuery object."""
        self.validate("registry-query", obj)

    def validate_registry_response(self, obj: dict) -> None:
        """Validate a RegistryResponse object."""
        self.validate("registry-response", obj)

    def validate(self, schema_name: str, obj: dict) -> None:
        """Validate an object against a named schema."""
        schema = load_schema(schema_name)
        try:
            jsonschema.validate(instance=obj, schema=schema)
        except jsonschema.ValidationError as e:
            raise XAPValidationError(f"Schema validation failed for {schema_name}: {e.message}") from e
