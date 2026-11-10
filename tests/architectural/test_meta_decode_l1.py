"""L1 unit tests for :mod:`kernel.meta_decode` — the single malformed authority.

Covers, for BOTH ``str`` and ``bytes`` inputs, the three malformed classes
(bad JSON syntax, non-UTF-8 bytes, non-object top level) across all three
``on_malformed`` policies, plus the valid-dict happy path and the
``MetaDecodeError``-is-``ValueError`` inheritance contract.

The ``b"\xff\xfe\x00"`` case specifically pins the *explicit* ``raw.decode(
"utf-8")`` path: ``json.loads(bytes)`` auto-detects the encoding and would raise
``json.JSONDecodeError``, so only an explicit decode surfaces the
``UnicodeDecodeError`` the malformed contract requires.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from kernel.meta_decode import MetaDecodeError, decode_meta
from specify_cli.mission_metadata import load_meta

# ``architectural`` is the CI-gate-selected marker (no gate selects bare
# ``unit`` -- see tests/architectural/_gate_coverage.py); ``unit`` is retained as
# the authoring taxonomy. Without the ``architectural`` marker this file is an
# orphan the gate-coverage meta-tests red (WP05 closeout fix of a WP01 miss,
# matching the sibling test_saas_sync_gate_selection_invariance.py pattern).
pytestmark = [pytest.mark.architectural, pytest.mark.unit]

# Malformed inputs as (str, bytes) pairs so every case runs against both types.
_BAD_JSON_STR = "{not valid json"
_BAD_JSON_BYTES = b"{not valid json"
# Non-object top levels (valid JSON, wrong shape).
_NON_OBJECT_STR = "[1, 2, 3]"
_NON_OBJECT_BYTES = b"[1, 2, 3]"
# Invalid UTF-8 bytes — only reachable as bytes; the explicit decode raises
# UnicodeDecodeError here, not JSONDecodeError.
_BAD_BYTES = b"\xff\xfe\x00"


# --------------------------------------------------------------------------- #
# Inheritance contract
# --------------------------------------------------------------------------- #
def test_meta_decode_error_is_value_error() -> None:
    """Every existing ``except ValueError`` boundary must keep catching L1."""
    assert issubclass(MetaDecodeError, ValueError)


# --------------------------------------------------------------------------- #
# Valid dict — happy path (str + bytes)
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "raw",
    ['{"a": 1, "b": "two"}', b'{"a": 1, "b": "two"}'],
    ids=["str", "bytes"],
)
def test_valid_dict_returns_mapping(raw: str | bytes) -> None:
    assert decode_meta(raw) == {"a": 1, "b": "two"}


@pytest.mark.parametrize("on_malformed", ["raise", "empty", "none"])
def test_valid_dict_unaffected_by_policy(on_malformed: str) -> None:
    """A valid object is returned verbatim regardless of the malformed policy."""
    assert decode_meta('{"k": true}', on_malformed=on_malformed) == {"k": True}  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# on_malformed="none" -> None for each malformed class (str + bytes)
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "raw",
    [_BAD_JSON_STR, _BAD_JSON_BYTES, _NON_OBJECT_STR, _NON_OBJECT_BYTES, _BAD_BYTES],
    ids=["bad-json-str", "bad-json-bytes", "non-object-str", "non-object-bytes", "bad-bytes"],
)
def test_none_policy_absorbs_to_none(raw: str | bytes) -> None:
    assert decode_meta(raw, on_malformed="none") is None


def test_none_policy_bad_bytes_goes_through_unicode_decode_path() -> None:
    """Prove ``b"\\xff\\xfe\\x00"`` fails via L1's explicit utf-8 decode.

    L1 does ``raw.decode("utf-8")`` *before* ``json.loads`` precisely so the
    encoding failure is deterministic utf-8, independent of ``json``'s own
    encoding auto-detection (which, for these BOM-prefixed bytes, would guess
    utf-16 — a different, non-deterministic code path). The exact call L1 makes
    raises ``UnicodeDecodeError``; assert that, then that L1 absorbs it to None.
    """
    with pytest.raises(UnicodeDecodeError):
        _BAD_BYTES.decode("utf-8")
    assert decode_meta(_BAD_BYTES, on_malformed="none") is None


# --------------------------------------------------------------------------- #
# on_malformed="empty" -> {} for each malformed class (str + bytes)
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "raw",
    [_BAD_JSON_STR, _BAD_JSON_BYTES, _NON_OBJECT_STR, _NON_OBJECT_BYTES, _BAD_BYTES],
    ids=["bad-json-str", "bad-json-bytes", "non-object-str", "non-object-bytes", "bad-bytes"],
)
def test_empty_policy_absorbs_to_empty_dict(raw: str | bytes) -> None:
    assert decode_meta(raw, on_malformed="empty") == {}


# --------------------------------------------------------------------------- #
# on_malformed="raise" -> MetaDecodeError for each malformed class (str + bytes)
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "raw",
    [_BAD_JSON_STR, _BAD_JSON_BYTES, _NON_OBJECT_STR, _NON_OBJECT_BYTES, _BAD_BYTES],
    ids=["bad-json-str", "bad-json-bytes", "non-object-str", "non-object-bytes", "bad-bytes"],
)
def test_raise_policy_raises_meta_decode_error(raw: str | bytes) -> None:
    with pytest.raises(MetaDecodeError):
        decode_meta(raw, on_malformed="raise")


def test_raise_is_the_default_policy() -> None:
    with pytest.raises(MetaDecodeError):
        decode_meta(_BAD_JSON_STR)


def test_raise_non_object_names_the_type() -> None:
    """The non-object raise arm surfaces the offending type for diagnostics."""
    with pytest.raises(MetaDecodeError, match="Expected JSON object, got list"):
        decode_meta(_NON_OBJECT_STR)


def test_raise_bad_bytes_caught_by_value_error_boundary() -> None:
    """Bad bytes raise ``MetaDecodeError`` — a plain ``except ValueError`` (as at
    L3 ``load_meta_fail_closed``) must catch it by inheritance."""
    caught: ValueError | None = None
    try:
        decode_meta(_BAD_BYTES, on_malformed="raise")
    except ValueError as exc:  # the L3 boundary shape, verbatim
        caught = exc
    assert isinstance(caught, MetaDecodeError)


def test_load_meta_reads_a_bom_prefixed_meta_json(tmp_path: Path) -> None:
    """#7445: the canonical reader tolerates a UTF-8 BOM by default (an editor-saved ``meta.json``)."""
    (tmp_path / "meta.json").write_bytes(b"\xef\xbb\xbf" + b'{"mission_slug": "bom-mission"}')

    assert load_meta(tmp_path) == {"mission_slug": "bom-mission"}
