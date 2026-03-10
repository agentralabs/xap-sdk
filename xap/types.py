"""Core XAP types. Mirrors verity-kernel Rust types exactly."""

from __future__ import annotations

import re
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from enum import Enum

from xap.errors import XAPError


class Currency(str, Enum):
    """Supported currencies."""
    USD = "USD"
    EUR = "EUR"
    GBP = "GBP"


@dataclass(frozen=True)
class Money:
    """All money in XAP is integer minor units. Never floating point."""
    amount_minor_units: int
    currency: Currency

    def __post_init__(self) -> None:
        if not isinstance(self.amount_minor_units, int):
            raise XAPError(f"Money must be integer, got {type(self.amount_minor_units).__name__}")

    def add(self, other: Money) -> Money:
        """Add two Money values. Must be same currency."""
        if self.currency != other.currency:
            raise XAPError(f"Currency mismatch: {self.currency} vs {other.currency}")
        return Money(self.amount_minor_units + other.amount_minor_units, self.currency)

    def subtract(self, other: Money) -> Money:
        """Subtract other from self. Must be same currency."""
        if self.currency != other.currency:
            raise XAPError(f"Currency mismatch: {self.currency} vs {other.currency}")
        return Money(self.amount_minor_units - other.amount_minor_units, self.currency)

    def split_bps(self, shares_bps: list[int]) -> list[Money]:
        """Split by basis points. Shares must sum to 10000.
        Deterministic remainder allocation: first payee gets remainder."""
        validate_shares(shares_bps)
        total = self.amount_minor_units
        results = [Money(total * s // 10000, self.currency) for s in shares_bps]
        distributed = sum(m.amount_minor_units for m in results)
        remainder = total - distributed
        if remainder != 0:
            results[0] = Money(results[0].amount_minor_units + remainder, self.currency)
        return results

    def apply_modifier_bps(self, modifier_bps: int) -> Money:
        """Apply a basis point modifier (e.g., 9788 bps = 97.88%)."""
        if not (0 <= modifier_bps <= 10000):
            raise XAPError(f"Modifier must be 0-10000, got {modifier_bps}")
        return Money(self.amount_minor_units * modifier_bps // 10000, self.currency)


@dataclass(frozen=True)
class BasisPoints:
    """0-10000. Used for shares, modifiers, confidence, rates."""
    value: int

    def __post_init__(self) -> None:
        if not isinstance(self.value, int) or not (0 <= self.value <= 10000):
            raise XAPError(f"BasisPoints must be integer 0-10000, got {self.value}")


def validate_shares(shares: list[int]) -> None:
    """Shares must sum to exactly 10000."""
    total = sum(shares)
    if total != 10000:
        raise XAPError(f"Shares must sum to 10000, got {total}")


class _TypedId:
    """Base class for type-safe XAP identifiers."""

    PREFIX: str = ""
    HEX_LEN: int = 8

    def __init__(self, value: str) -> None:
        pattern = re.compile(f"^{self.PREFIX}_[a-f0-9]{{{self.HEX_LEN}}}$")
        if not pattern.match(value):
            raise XAPError(f"Invalid {type(self).__name__} format: {value}")
        self._value = value

    @classmethod
    def generate(cls) -> _TypedId:
        """Generate a new random ID."""
        hex_part = secrets.token_hex(cls.HEX_LEN // 2)
        return cls(f"{cls.PREFIX}_{hex_part}")

    def __str__(self) -> str:
        return self._value

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self._value!r})"

    def __eq__(self, other: object) -> bool:
        return isinstance(other, type(self)) and self._value == other._value

    def __hash__(self) -> int:
        return hash(self._value)


class AgentId(_TypedId):
    PREFIX = "agent"


class SettlementId(_TypedId):
    PREFIX = "stl"


class ReceiptId(_TypedId):
    PREFIX = "rcpt"


class VerityId(_TypedId):
    PREFIX = "vrt"


class ContractId(_TypedId):
    PREFIX = "neg"


class QueryId(_TypedId):
    PREFIX = "qry"


class CanonicalTimestamp:
    """Canonical timestamps. Always UTC. Never local time."""

    def __init__(self, dt: datetime | None = None) -> None:
        self._dt = dt or datetime.now(timezone.utc)
        if self._dt.tzinfo is None:
            raise XAPError("Timestamps must be timezone-aware (UTC)")

    @classmethod
    def now(cls) -> CanonicalTimestamp:
        """Current UTC time."""
        return cls(datetime.now(timezone.utc))

    @classmethod
    def from_iso(cls, s: str) -> CanonicalTimestamp:
        """Parse an ISO 8601 timestamp string."""
        # Python 3.10 doesn't support trailing 'Z' in fromisoformat
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            raise XAPError("Timestamps must be timezone-aware (UTC)")
        return cls(dt.astimezone(timezone.utc))

    def to_iso(self) -> str:
        """ISO 8601 string with Z suffix."""
        return self._dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    def is_expired(self) -> bool:
        """True if this timestamp is in the past."""
        return self._dt < datetime.now(timezone.utc)

    def add_days(self, days: int) -> CanonicalTimestamp:
        return CanonicalTimestamp(self._dt + timedelta(days=days))

    def add_minutes(self, minutes: int) -> CanonicalTimestamp:
        return CanonicalTimestamp(self._dt + timedelta(minutes=minutes))

    def __eq__(self, other: object) -> bool:
        return isinstance(other, CanonicalTimestamp) and self._dt == other._dt

    def __hash__(self) -> int:
        return hash(self._dt)

    def __repr__(self) -> str:
        return f"CanonicalTimestamp({self.to_iso()!r})"
