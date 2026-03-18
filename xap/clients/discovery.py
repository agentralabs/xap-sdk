"""DiscoveryClient — query the agent registry."""

from __future__ import annotations

from typing import TYPE_CHECKING

from xap.builders.registry import RegistryQueryBuilder, RegistryResponseBuilder
from xap.types import CanonicalTimestamp

if TYPE_CHECKING:
    from xap.client import XAPClient


class DiscoveryClient:
    """Query the agent registry.

    In sandbox mode, uses an in-memory registry.
    In production, queries the Agentra Rail API.
    """

    def __init__(self, xap_client: XAPClient) -> None:
        self._client = xap_client
        self._registry: dict[str, dict] = {}  # agent_id -> identity
        self._manifests: dict[str, dict] = {}  # agent_id -> manifest

    def register(self, identity: dict, manifest: dict | None = None) -> None:
        """Register an agent identity (and optional manifest) in the sandbox registry."""
        self._registry[identity["agent_id"]] = identity
        if manifest:
            self._manifests[identity["agent_id"]] = manifest

    def search(
        self,
        capability: str | None = None,
        min_reputation_bps: int | None = None,
        max_price_minor_units: int | None = None,
        max_latency_ms: int | None = None,
        limit: int = 20,
        include_manifest: bool = False,
    ) -> dict:
        """Search for agents matching criteria.

        Returns a RegistryResponse with ranked results.
        When include_manifest is True, each result includes the agent's manifest.
        """
        # Build query for validation
        query_builder = RegistryQueryBuilder(self._client.agent_id)
        if capability:
            query_builder.capability(capability)
        if min_reputation_bps is not None:
            query_builder.min_reputation(min_reputation_bps)
        if max_price_minor_units is not None:
            query_builder.max_price(max_price_minor_units)
        if max_latency_ms is not None:
            query_builder.max_latency(max_latency_ms)
        query_builder.limit(limit)
        query = query_builder.build()

        # Filter in-memory registry
        matches = []
        manifest_map: dict[int, dict] = {}  # index -> manifest
        for agent_id, identity in self._registry.items():
            if self._matches_filters(identity, capability, min_reputation_bps, max_price_minor_units, max_latency_ms):
                summary = self._to_summary(identity)
                if include_manifest and agent_id in self._manifests:
                    manifest_map[len(matches)] = self._manifests[agent_id]
                matches.append(summary)

        matches = matches[:limit]

        # Build response (validates against schema without manifest)
        resp_builder = RegistryResponseBuilder(query["query_id"])
        resp_builder.limit(limit)
        for m in matches:
            resp_builder.add_result(m)

        response = resp_builder.build()

        # Attach manifests after validation
        for idx, manifest in manifest_map.items():
            if idx < len(response["results"]):
                response["results"][idx]["manifest"] = manifest

        return response

    def _matches_filters(
        self,
        identity: dict,
        capability: str | None,
        min_reputation_bps: int | None,
        max_price_minor_units: int | None,
        max_latency_ms: int | None,
    ) -> bool:
        if capability:
            cap_names = [c["name"] for c in identity.get("capabilities", [])]
            if capability not in cap_names:
                return False

        if min_reputation_bps is not None:
            rep = identity.get("reputation", {}).get("success_rate_bps", 0)
            if rep < min_reputation_bps:
                return False

        if max_price_minor_units is not None and capability:
            for cap in identity.get("capabilities", []):
                if cap["name"] == capability:
                    price = cap.get("pricing", {}).get("amount_minor_units", 0)
                    if price > max_price_minor_units:
                        return False

        if max_latency_ms is not None and capability:
            for cap in identity.get("capabilities", []):
                if cap["name"] == capability:
                    latency = cap.get("sla", {}).get("max_latency_ms", 0)
                    if latency > max_latency_ms:
                        return False

        return True

    def _to_summary(self, identity: dict) -> dict:
        caps = []
        for cap in identity.get("capabilities", []):
            caps.append({
                "name": cap["name"],
                "version": cap["version"],
                "pricing": cap["pricing"],
                "sla": cap["sla"],
            })

        rep = identity.get("reputation", {})
        return {
            "agent_id": identity["agent_id"],
            "display_name": identity.get("display_name"),
            "capabilities_matched": caps,
            "reputation_summary": {
                "success_rate_bps": rep.get("success_rate_bps", 0),
                "total_settlements": rep.get("total_settlements", 0),
                "dispute_rate_bps": 0,
                "avg_quality_score_bps": rep.get("avg_quality_bps", 0),
            },
            "status": identity.get("status", "active"),
            "relevance_score_bps": 9000,
            "registered_at": identity.get("registered_at", CanonicalTimestamp.now().to_iso()),
        }
