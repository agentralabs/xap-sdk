"""Tests for xap.types — Money, BasisPoints, IDs, Timestamps."""

import pytest
from xap.types import (
    Money, Currency, BasisPoints, validate_shares,
    AgentId, SettlementId, ReceiptId, VerityId, ContractId, QueryId,
    CanonicalTimestamp,
)
from xap.errors import XAPError


class TestMoney:
    def test_integer_enforcement(self):
        m = Money(500, Currency.USD)
        assert m.amount_minor_units == 500

    def test_float_raises_error(self):
        with pytest.raises(XAPError, match="integer"):
            Money(5.0, Currency.USD)

    def test_add_same_currency(self):
        a = Money(500, Currency.USD)
        b = Money(300, Currency.USD)
        result = a.add(b)
        assert result.amount_minor_units == 800
        assert result.currency == Currency.USD

    def test_add_different_currency_raises(self):
        a = Money(500, Currency.USD)
        b = Money(300, Currency.EUR)
        with pytest.raises(XAPError, match="Currency mismatch"):
            a.add(b)

    def test_subtract(self):
        a = Money(500, Currency.USD)
        b = Money(300, Currency.USD)
        result = a.subtract(b)
        assert result.amount_minor_units == 200

    def test_subtract_different_currency_raises(self):
        with pytest.raises(XAPError):
            Money(500, Currency.USD).subtract(Money(300, Currency.EUR))

    def test_split_bps(self):
        m = Money(10000, Currency.USD)
        splits = m.split_bps([6000, 2500, 1500])
        assert splits[0].amount_minor_units == 6000
        assert splits[1].amount_minor_units == 2500
        assert splits[2].amount_minor_units == 1500

    def test_split_bps_remainder(self):
        m = Money(1000, Currency.USD)
        splits = m.split_bps([3333, 3333, 3334])
        total = sum(s.amount_minor_units for s in splits)
        assert total == 1000
        # First payee gets remainder
        assert splits[0].amount_minor_units == 334

    def test_split_bps_invalid_shares(self):
        with pytest.raises(XAPError, match="10000"):
            Money(1000, Currency.USD).split_bps([5000, 3000])

    def test_apply_modifier_bps(self):
        m = Money(10000, Currency.USD)
        result = m.apply_modifier_bps(9788)
        assert result.amount_minor_units == 9788

    def test_frozen(self):
        m = Money(500, Currency.USD)
        with pytest.raises(AttributeError):
            m.amount_minor_units = 600


class TestBasisPoints:
    def test_valid_range(self):
        assert BasisPoints(0).value == 0
        assert BasisPoints(5000).value == 5000
        assert BasisPoints(10000).value == 10000

    def test_out_of_range(self):
        with pytest.raises(XAPError):
            BasisPoints(10001)
        with pytest.raises(XAPError):
            BasisPoints(-1)

    def test_non_integer(self):
        with pytest.raises(XAPError):
            BasisPoints(50.5)


class TestValidateShares:
    def test_valid(self):
        validate_shares([6000, 4000])

    def test_invalid(self):
        with pytest.raises(XAPError, match="10000"):
            validate_shares([5000, 3000])


class TestIds:
    def test_valid_agent_id(self):
        aid = AgentId("agent_7f3a9b2c")
        assert str(aid) == "agent_7f3a9b2c"

    def test_invalid_prefix(self):
        with pytest.raises(XAPError, match="Invalid"):
            AgentId("user_7f3a9b2c")

    def test_invalid_hex(self):
        with pytest.raises(XAPError):
            AgentId("agent_ZZZZZZZZ")

    def test_invalid_uppercase(self):
        with pytest.raises(XAPError):
            AgentId("agent_7F3A9B2C")

    def test_invalid_length(self):
        with pytest.raises(XAPError):
            AgentId("agent_7f3a")

    def test_generate(self):
        aid = AgentId.generate()
        assert str(aid).startswith("agent_")
        assert len(str(aid)) == 14  # agent_ + 8 hex

    def test_equality(self):
        a = AgentId("agent_7f3a9b2c")
        b = AgentId("agent_7f3a9b2c")
        assert a == b
        assert hash(a) == hash(b)

    def test_inequality(self):
        a = AgentId("agent_7f3a9b2c")
        b = AgentId("agent_11111111")
        assert a != b

    def test_all_id_types(self):
        assert str(SettlementId("stl_4b7c9e2f")).startswith("stl_")
        assert str(ReceiptId("rcpt_6d1e8f3a")).startswith("rcpt_")
        assert str(VerityId("vrt_a1b2c3d4")).startswith("vrt_")
        assert str(ContractId("neg_8a2f4c1d")).startswith("neg_")
        assert str(QueryId("qry_a1b2c3d4")).startswith("qry_")

    def test_generate_all_types(self):
        assert str(SettlementId.generate()).startswith("stl_")
        assert str(ReceiptId.generate()).startswith("rcpt_")
        assert str(VerityId.generate()).startswith("vrt_")
        assert str(ContractId.generate()).startswith("neg_")
        assert str(QueryId.generate()).startswith("qry_")


class TestCanonicalTimestamp:
    def test_now(self):
        ts = CanonicalTimestamp.now()
        iso = ts.to_iso()
        assert iso.endswith("Z")

    def test_from_iso(self):
        ts = CanonicalTimestamp.from_iso("2026-03-15T14:30:00+00:00")
        iso = ts.to_iso()
        assert "2026-03-15" in iso

    def test_naive_raises(self):
        from datetime import datetime
        with pytest.raises(XAPError, match="timezone"):
            CanonicalTimestamp(datetime(2026, 1, 1))

    def test_roundtrip(self):
        ts1 = CanonicalTimestamp.now()
        ts2 = CanonicalTimestamp.from_iso(ts1.to_iso())
        assert ts1.to_iso() == ts2.to_iso()

    def test_is_expired(self):
        past = CanonicalTimestamp.from_iso("2020-01-01T00:00:00+00:00")
        assert past.is_expired()
        future = CanonicalTimestamp.from_iso("2099-01-01T00:00:00+00:00")
        assert not future.is_expired()

    def test_add_days(self):
        ts = CanonicalTimestamp.from_iso("2026-03-01T00:00:00+00:00")
        later = ts.add_days(10)
        assert "2026-03-11" in later.to_iso()

    def test_add_minutes(self):
        ts = CanonicalTimestamp.from_iso("2026-03-01T00:00:00+00:00")
        later = ts.add_minutes(30)
        assert "00:30:00" in later.to_iso()
