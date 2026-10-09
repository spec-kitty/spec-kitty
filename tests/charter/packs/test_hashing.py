"""Golden digests for the pack/synthesis manifest hashers (#3732, WP04 T021).

The expected values were computed once from the pre-move implementation in
``charter.activation.synthesizer.manifest``; moving the two functions to
``charter.offering.packs.hashing`` must not change a single byte of output.
"""

from __future__ import annotations

import pytest

from charter.offering.packs.hashing import hash_content_bytes, hash_manifest_payload

pytestmark = pytest.mark.fast

_PAYLOAD = {"b": [1, {"z": 2, "a": "x"}], "a": "é", "manifest_hash": "zz", "generated_at": "t"}


def test_hash_manifest_payload_matches_pre_move_golden_digest() -> None:
    digest = hash_manifest_payload(_PAYLOAD, exclude_keys=frozenset({"manifest_hash", "generated_at"}))
    assert digest == "91871a6165142aed8814cda79da03365a84adda27bd27ed76241add4179fe3cc"


def test_hash_manifest_payload_ignores_excluded_keys() -> None:
    excluded = frozenset({"manifest_hash", "generated_at"})
    changed = {**_PAYLOAD, "manifest_hash": "other", "generated_at": "later"}
    assert hash_manifest_payload(changed, exclude_keys=excluded) == hash_manifest_payload(_PAYLOAD, exclude_keys=excluded)
    assert hash_manifest_payload(_PAYLOAD, exclude_keys=frozenset()) != hash_manifest_payload(_PAYLOAD, exclude_keys=excluded)


def test_hash_content_bytes_matches_pre_move_golden_digest() -> None:
    assert hash_content_bytes(b"hello\npack\n") == "f7ad2ff61f7a3694d27fe2f1c617256d42d420673274032263218da6e708ec62"
