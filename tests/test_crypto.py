"""Tests for xap.crypto — canonical serialization, hashing, signing."""

import pytest
from xap.crypto import (
    canonical_serialize,
    canonical_hash,
    compute_replay_hash,
    XAPSigner,
)
from xap.errors import XAPCryptoError


class TestCanonicalSerialize:
    def test_deterministic(self):
        obj = {"b": 2, "a": 1}
        b1 = canonical_serialize(obj)
        b2 = canonical_serialize(obj)
        assert b1 == b2

    def test_sorted_keys(self):
        result = canonical_serialize({"z": 1, "a": 2})
        assert result == b'{"a":2,"z":1}'

    def test_compact(self):
        result = canonical_serialize({"key": "value"})
        assert b" " not in result

    def test_nested_sorted(self):
        obj = {"outer": {"z": 1, "a": 2}}
        result = canonical_serialize(obj)
        assert b'"a":2' in result


class TestCanonicalHash:
    def test_produces_sha256_prefix(self):
        h = canonical_hash({"test": True})
        assert h.startswith("sha256:")
        assert len(h) == len("sha256:") + 64

    def test_deterministic(self):
        h1 = canonical_hash({"a": 1, "b": 2})
        h2 = canonical_hash({"b": 2, "a": 1})
        assert h1 == h2

    def test_different_input_different_hash(self):
        h1 = canonical_hash({"a": 1})
        h2 = canonical_hash({"a": 2})
        assert h1 != h2


class TestReplayHash:
    def test_same_inputs_same_hash(self):
        inp = {"state": "PENDING"}
        rules = {"version": "0.2.0"}
        comp = {"steps": []}
        h1 = compute_replay_hash(inp, rules, comp)
        h2 = compute_replay_hash(inp, rules, comp)
        assert h1 == h2

    def test_different_inputs_different_hash(self):
        h1 = compute_replay_hash({"a": 1}, {"b": 2}, {"c": 3})
        h2 = compute_replay_hash({"a": 99}, {"b": 2}, {"c": 3})
        assert h1 != h2

    def test_key_order_independent(self):
        h1 = compute_replay_hash({"z": 1, "a": 2}, {}, {})
        h2 = compute_replay_hash({"a": 2, "z": 1}, {}, {})
        assert h1 == h2

    def test_sha256_prefix(self):
        h = compute_replay_hash({}, {}, {})
        assert h.startswith("sha256:")


class TestXAPSigner:
    def test_generate(self):
        signer = XAPSigner.generate()
        assert signer.public_key_bytes()
        assert signer.public_key_base64()

    def test_sign_and_verify(self):
        signer = XAPSigner.generate()
        obj = {"decision": "release_funds", "amount": 500}
        sig = signer.sign(obj)
        assert sig.startswith("ed25519:")
        assert XAPSigner.verify(signer.public_key_base64(), obj, sig)

    def test_wrong_key_fails(self):
        signer1 = XAPSigner.generate()
        signer2 = XAPSigner.generate()
        obj = {"decision": "release"}
        sig = signer1.sign(obj)
        assert not XAPSigner.verify(signer2.public_key_base64(), obj, sig)

    def test_wrong_content_fails(self):
        signer = XAPSigner.generate()
        obj1 = {"decision": "release"}
        obj2 = {"decision": "refund"}
        sig = signer.sign(obj1)
        assert not XAPSigner.verify(signer.public_key_base64(), obj2, sig)

    def test_invalid_prefix_raises(self):
        signer = XAPSigner.generate()
        with pytest.raises(XAPCryptoError, match="ed25519"):
            XAPSigner.verify(signer.public_key_base64(), {}, "bad:sig")
