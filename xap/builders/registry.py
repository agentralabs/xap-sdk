"""Registry query and response builders."""

from __future__ import annotations

from xap.errors import XAPBuilderError
from xap.schemas.validator import SchemaValidator
from xap.types import AgentId, QueryId, CanonicalTimestamp


class RegistryQueryBuilder:
    """Build RegistryQuery objects."""

    def __init__(self, querying_agent: AgentId) -> None:
        self._querying_agent = str(querying_agent)
        self._query_id = str(QueryId.generate())
        self._filters: dict = {}
        self._sort: dict | None = None
        self._pagination: dict | None = None

    def capability(self, name: str) -> RegistryQueryBuilder:
        """Filter by capability name."""
        self._filters.setdefault("capability", {})["name"] = name
        return self

    def capabilities(self, names: list[str]) -> RegistryQueryBuilder:
        """Filter by multiple capability names (OR)."""
        self._filters.setdefault("capability", {})["names"] = names
        return self

    def min_reputation(self, success_rate_bps: int) -> RegistryQueryBuilder:
        """Filter by minimum reputation."""
        self._filters.setdefault("reputation", {})["min_success_rate_bps"] = success_rate_bps
        return self

    def max_price(self, minor_units: int, currency: str = "USD") -> RegistryQueryBuilder:
        """Filter by maximum price."""
        pricing = self._filters.setdefault("pricing", {})
        pricing["max_amount_minor_units"] = minor_units
        pricing["currency"] = currency
        return self

    def max_latency(self, ms: int) -> RegistryQueryBuilder:
        """Filter by maximum latency."""
        self._filters.setdefault("sla", {})["max_latency_ms"] = ms
        return self

    def sort_by(self, field: str) -> RegistryQueryBuilder:
        """Set sort field."""
        self._sort = {"field": field}
        return self

    def limit(self, n: int) -> RegistryQueryBuilder:
        """Set pagination limit."""
        self._pagination = {"limit": n}
        return self

    def build(self) -> dict:
        """Build and validate."""
        obj: dict = {
            "query_id": self._query_id,
            "querying_agent_id": self._querying_agent,
            "filters": self._filters,
            "xap_version": "0.2.0",
        }

        if self._sort:
            obj["sort"] = self._sort
        if self._pagination:
            obj["pagination"] = self._pagination

        SchemaValidator().validate_registry_query(obj)
        return obj


class RegistryResponseBuilder:
    """Build RegistryResponse objects."""

    def __init__(self, query_id: str) -> None:
        self._query_id = query_id
        self._results: list[dict] = []
        self._limit = 20

    def add_result(self, result: dict) -> RegistryResponseBuilder:
        """Add an agent summary to results."""
        self._results.append(result)
        return self

    def limit(self, n: int) -> RegistryResponseBuilder:
        self._limit = n
        return self

    def build(self) -> dict:
        """Build and validate."""
        obj: dict = {
            "query_id": self._query_id,
            "results": self._results,
            "total_count": len(self._results),
            "pagination": {
                "has_more": False,
                "limit": self._limit,
            },
            "responded_at": CanonicalTimestamp.now().to_iso(),
            "xap_version": "0.2.0",
        }

        SchemaValidator().validate_registry_response(obj)
        return obj
