"""Contract tests for the polymorphic ``load_meta`` reader (FR-006a, WP08).

These tests pin the *observable return value* of each of the three legacy error
contracts the single ``load_meta`` absorbs -- never the reader's internal call
graph (CT4/D036).  Each "absorbs / allows" assertion is paired with its negative
control ("still raises") so an over-allow mutant cannot survive.

The three contracts:
  (a) canonical     -- None-on-missing, raise-on-malformed (defaults).
  (b) strict        -- raise-on-missing, utf-8-sig BOM-tolerant decode.
  (c) silent-empty  -- ``{}`` on missing *and* malformed; never raises.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from specify_cli.mission_metadata import (
    META_FILENAME,
    load_meta,
    load_meta_or_empty,
    load_meta_strict,
    parse_meta_file,
    restore_meta_text,
    write_meta,
)
from specify_cli.status.emit import _load_mission_id

pytestmark = [pytest.mark.unit, pytest.mark.fast]

# Production-shaped identity: a real 26-char ULID + its 8-char mid8 prefix
# (testing-principles -- never a short placeholder slug).
_MISSION_ID = "01KVRJ6PQ7XB2M9K4D8N3FZ0YT"
_MID8 = _MISSION_ID[:8]  # "01KVRJ6P"
_MISSION_SLUG = f"single-authority-topology-cleanup-{_MID8}"


def _valid_meta() -> dict[str, Any]:
    """A complete, production-shaped meta.json mapping."""
    return {
        "mission_id": _MISSION_ID,
        "mission_number": None,
        "slug": _MISSION_SLUG,
        "mission_slug": _MISSION_SLUG,
        "friendly_name": "Single-Authority Topology Cleanup",
        "mission_type": "software-dev",
        "target_branch": "feat/single-authority-topology-cleanup",
        "created_at": "2026-06-23T07:37:56+00:00",
    }


def _seed_valid(feature_dir: Path) -> dict[str, Any]:
    """Write a valid meta.json via the production write seam; return its dict."""
    meta = _valid_meta()
    write_meta(feature_dir, meta)
    return meta


def _seed_malformed(feature_dir: Path) -> Path:
    """Write a *genuinely un-parseable* meta.json (identity-input trap guard).

    An empty file would hit the *missing*-content arm and mask the malformed
    branch; ``{"a":`` is truncated JSON that ``json.loads`` cannot parse.
    """
    meta_path = feature_dir / META_FILENAME
    meta_path.write_text('{"a":', encoding="utf-8")
    return meta_path


def _seed_bom_prefixed(feature_dir: Path) -> dict[str, Any]:
    """Write a valid meta.json carrying a leading UTF-8 BOM (``EF BB BF``).

    Writing with ``utf-8-sig`` prepends the BOM, so a plain ``utf-8`` decode
    leaves a leading U+FEFF that ``json.loads`` rejects (#7445).
    """
    meta = _valid_meta()
    (feature_dir / META_FILENAME).write_text(
        json.dumps(meta, ensure_ascii=False), encoding="utf-8-sig"
    )
    return meta


# ===================================================================
# Happy path -- shared by every contract
# ===================================================================


def test_load_meta_reads_valid_object(tmp_path: Path) -> None:
    meta = _seed_valid(tmp_path)
    assert load_meta(tmp_path) == meta


# ===================================================================
# Contract (a): canonical -- None-on-missing, raise-on-malformed (defaults)
# ===================================================================


def test_contract_a_missing_returns_none(tmp_path: Path) -> None:
    # allow_missing default True, on_malformed default "raise"
    assert load_meta(tmp_path) is None


def test_contract_a_malformed_raises(tmp_path: Path) -> None:
    # Negative control for the missing arm: an existing-but-malformed file
    # must NOT be absorbed to None -- it raises.
    _seed_malformed(tmp_path)
    with pytest.raises(ValueError, match="Malformed JSON"):
        load_meta(tmp_path)


def test_contract_a_non_object_top_level_raises(tmp_path: Path) -> None:
    (tmp_path / META_FILENAME).write_text("[1, 2, 3]", encoding="utf-8")
    with pytest.raises(ValueError, match="Expected JSON object"):
        load_meta(tmp_path)


def test_contract_a_non_utf8_bytes_raise_malformed_value_error(tmp_path: Path) -> None:
    """Non-UTF-8 bytes must raise the wrapped ``Malformed JSON`` ValueError.

    Regression for #3163: ``meta_path.read_text(encoding="utf-8")`` raises
    ``UnicodeDecodeError`` on invalid UTF-8 bytes -- a ``ValueError``
    subclass, NOT an ``OSError`` subclass -- which the original
    ``except (json.JSONDecodeError, OSError)`` tuple in ``_parse_meta_text``
    did not catch, letting it escape as a raw, unwrapped
    ``UnicodeDecodeError`` instead of this reader's contracted
    ``ValueError("Malformed JSON in ...")``.
    """
    (tmp_path / META_FILENAME).write_bytes(b"\xff\xfe\x00\x01garbage")
    with pytest.raises(ValueError, match="Malformed JSON") as excinfo:
        load_meta(tmp_path)
    assert not isinstance(excinfo.value, UnicodeDecodeError)


def test_contract_a_bom_prefixed_file_loads(tmp_path: Path) -> None:
    """A BOM-prefixed meta.json loads through the canonical reader (#7445).

    A ``meta.json`` saved with a UTF-8 byte-order mark is the same file as one
    without it, so the canonical defaults must parse it -- not raise the
    historical ``ValueError("Unexpected UTF-8 BOM")``.
    """
    meta = _seed_bom_prefixed(tmp_path)
    assert load_meta(tmp_path) == meta


def test_contract_a_bom_prefixed_file_loads_on_malformed_none(tmp_path: Path) -> None:
    """The invisibility symptom (#7445): ``on_malformed="none"`` must not absorb a BOM'd file.

    A BOM-prefixed file is well-formed JSON, so callers that pass
    ``on_malformed="none"`` must see the mapping, not ``None`` -- a ``None``
    here made the whole Mission invisible to status commands.
    """
    meta = _seed_bom_prefixed(tmp_path)
    assert load_meta(tmp_path, on_malformed="none") == meta


def test_contract_a_bom_prefixed_file_parse_meta_file(tmp_path: Path) -> None:
    """The path-holding reader accepts a BOM-prefixed file too (#7445)."""
    meta = _seed_bom_prefixed(tmp_path)
    assert parse_meta_file(tmp_path / META_FILENAME) == meta


def test_contract_a_bom_prefixed_and_plain_decode_identically(tmp_path: Path) -> None:
    """Same-fixture control (FR-015): BOM'd and BOM-less files decode identically.

    The same mapping written with and without the BOM must return the identical
    dict from all three canonical readers -- a non-BOM file decodes
    byte-identically to today.
    """
    meta = _valid_meta()
    bom_dir = tmp_path / "with-bom"
    plain_dir = tmp_path / "without-bom"
    bom_dir.mkdir()
    plain_dir.mkdir()
    (bom_dir / META_FILENAME).write_text(
        json.dumps(meta, ensure_ascii=False), encoding="utf-8-sig"
    )
    (plain_dir / META_FILENAME).write_text(
        json.dumps(meta, ensure_ascii=False), encoding="utf-8"
    )
    for mission_dir in (bom_dir, plain_dir):
        assert load_meta(mission_dir) == meta
        assert load_meta(mission_dir, on_malformed="none") == meta
        assert parse_meta_file(mission_dir / META_FILENAME) == meta


def test_load_mission_id_reads_bom_prefixed_meta(tmp_path: Path) -> None:
    """Symptom level (#7445): a real caller sees the mission_id of a BOM'd file.

    ``status.emit._load_mission_id`` reads through ``on_malformed="none"``, so
    on the base a BOM-prefixed ``meta.json`` made the Mission's identity
    resolve to ``None``.
    """
    meta = _seed_bom_prefixed(tmp_path)
    assert _load_mission_id(tmp_path) == meta["mission_id"]


# ===================================================================
# Contract (b): strict -- raise-on-missing + utf-8-sig BOM tolerance
# ===================================================================


def test_contract_b_missing_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_meta(tmp_path, allow_missing=False)


def test_contract_b_strict_adapter_missing_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_meta_strict(tmp_path)


def test_contract_b_present_returns_dict(tmp_path: Path) -> None:
    # Negative control for the missing arm: a present file does NOT raise.
    meta = _seed_valid(tmp_path)
    assert load_meta_strict(tmp_path) == meta


def test_contract_b_bom_tolerant_decode(tmp_path: Path) -> None:
    """A UTF-8 BOM-prefixed meta.json decodes cleanly under the strict adapter.

    Writing with ``utf-8-sig`` prepends the BOM; a plain ``utf-8`` json.loads
    would choke on it, so a successful parse proves the BOM-tolerant decode is
    preserved.
    """
    meta = _valid_meta()

    (tmp_path / META_FILENAME).write_text(
        json.dumps(meta, ensure_ascii=False), encoding="utf-8-sig"
    )
    assert load_meta_strict(tmp_path) == meta


def test_contract_b_bom_intolerant_when_disabled(tmp_path: Path) -> None:
    """Negative control: with ``bom_tolerant=False`` the BOM is NOT swallowed.

    The strict adapter coerces malformed content to ``{}`` (legacy isinstance
    guard), so a BOM that breaks the plain utf-8 decode yields ``{}`` rather
    than the parsed object -- proving the tolerance is opt-in, not unconditional.
    """
    meta = _valid_meta()

    (tmp_path / META_FILENAME).write_text(
        json.dumps(meta, ensure_ascii=False), encoding="utf-8-sig"
    )
    assert load_meta_strict(tmp_path, bom_tolerant=False) == {}


# ===================================================================
# Contract (c): silent -- {} on missing AND malformed; never raises
# ===================================================================


def test_contract_c_missing_returns_empty(tmp_path: Path) -> None:
    assert load_meta(tmp_path, on_malformed="empty") == {}


def test_contract_c_malformed_returns_empty(tmp_path: Path) -> None:
    # Negative control vs contract (a): the SAME malformed input that raises
    # under "raise" is absorbed to {} under "empty".
    _seed_malformed(tmp_path)
    assert load_meta(tmp_path, on_malformed="empty") == {}


def test_contract_c_adapter_missing_and_malformed_return_empty(tmp_path: Path) -> None:
    assert load_meta_or_empty(tmp_path) == {}
    _seed_malformed(tmp_path)
    assert load_meta_or_empty(tmp_path) == {}


def test_contract_c_adapter_valid_returns_object(tmp_path: Path) -> None:
    # Negative control: a valid file is NOT flattened to {} by the silent adapter.
    meta = _seed_valid(tmp_path)
    assert load_meta_or_empty(tmp_path) == meta


def test_contract_c_non_object_returns_empty(tmp_path: Path) -> None:
    (tmp_path / META_FILENAME).write_text('"a bare string"', encoding="utf-8")
    assert load_meta(tmp_path, on_malformed="empty") == {}


# ===================================================================
# on_malformed="none" -- absorb to None (third malformed policy)
# ===================================================================


def test_on_malformed_none_missing_returns_none(tmp_path: Path) -> None:
    assert load_meta(tmp_path, on_malformed="none") is None


def test_on_malformed_none_malformed_returns_none(tmp_path: Path) -> None:
    # Negative control vs "raise": malformed is absorbed to None, not raised.
    _seed_malformed(tmp_path)
    assert load_meta(tmp_path, on_malformed="none") is None


# ===================================================================
# Cross-contract behavior-neutrality: a valid object reads identically
# regardless of which contract is selected.
# ===================================================================


def test_valid_object_identical_across_contracts(tmp_path: Path) -> None:
    meta = _seed_valid(tmp_path)
    assert load_meta(tmp_path) == meta
    assert load_meta(tmp_path, allow_missing=False) == meta
    assert load_meta(tmp_path, on_malformed="empty") == meta
    assert load_meta(tmp_path, on_malformed="none") == meta
    assert load_meta_strict(tmp_path) == meta
    assert load_meta_or_empty(tmp_path) == meta


# ===================================================================
# restore_meta_text -- byte-exact rollback primitive (SK3466-R-001).
#
# Unlike write_meta (parse -> mutate -> re-serialize via
# json.dumps(indent=2, sort_keys=True)), restore_meta_text writes its input
# verbatim. These tests pin that it is NOT a write_meta-style writer: no
# re-serialization, no key sorting/indentation normalization, and no JSON
# validation -- because its whole purpose is undoing a prior write back to
# PRECISELY the caller's captured pre-write bytes, not producing canonically
# formatted output.
# ===================================================================


def test_restore_meta_text_writes_bytes_verbatim(tmp_path: Path) -> None:
    """The exact captured string is written back -- no re-serialization."""
    _seed_valid(tmp_path)
    # Deliberately NOT canonical write_meta formatting: compact, unsorted
    # keys, no trailing newline -- mimics an "original_text" a caller
    # captured from a foreign writer (e.g. a test's own json.dumps(meta)).
    captured_original = '{"target_branch": "main", "zeta": 1, "alpha": 2}'

    restore_meta_text(tmp_path, captured_original)

    restored_bytes = (tmp_path / META_FILENAME).read_text(encoding="utf-8")
    assert restored_bytes == captured_original


def test_restore_meta_text_overwrites_a_different_on_disk_write(tmp_path: Path) -> None:
    """Restores over whatever write_meta most recently wrote (the revert case)."""
    meta = _seed_valid(tmp_path)
    original_text = (tmp_path / META_FILENAME).read_text(encoding="utf-8")

    # Simulate a persisted override overwriting the captured original.
    mutated = dict(meta)
    mutated["target_branch"] = "some-other-branch"
    write_meta(tmp_path, mutated)
    assert load_meta(tmp_path)["target_branch"] == "some-other-branch"

    restore_meta_text(tmp_path, original_text)

    assert (tmp_path / META_FILENAME).read_text(encoding="utf-8") == original_text
    assert load_meta(tmp_path) == meta
