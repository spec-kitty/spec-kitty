"""Invariant tests for EvidenceBundle and related frozen dataclasses.

Nine test cases covering:
1. EvidenceBundle.is_empty is True for all defaults.
2. EvidenceBundle.is_empty is False when any field is non-empty.
3. CodeSignals raises ValueError when scope_tag != primary_language.
4. CodeSignals raises ValueError for invalid stack_id format.
5. CodeSignals raises ValueError for representative_files with leading slash.
6. CorpusSnapshot raises ValueError for invalid snapshot_id format.
7. EvidenceBundle raises ValueError for url_list with empty strings.
8. All four dataclasses are frozen (FrozenInstanceError on mutation).
9. All four dataclasses are hashable (usable as dict keys / in sets).
"""

from __future__ import annotations

import pytest

from charter.activation.synthesizer.evidence import (
    CodeSignals,
    CorpusEntry,
    CorpusSnapshot,
    EvidenceBundle,
)


# ---------------------------------------------------------------------------
# Helpers — minimal valid instances
# ---------------------------------------------------------------------------

pytestmark = [pytest.mark.unit]

def _make_code_signals(**overrides: object) -> CodeSignals:
    defaults = dict(
        stack_id="python",
        primary_language="python",
        frameworks=("django",),
        test_frameworks=("pytest",),
        scope_tag="python",
        representative_files=("src/main.py",),
        detected_at="2026-04-19T10:00:00+00:00",
    )
    defaults.update(overrides)  # type: ignore[arg-type]
    return CodeSignals(**defaults)  # type: ignore[arg-type]


def _make_corpus_entry(**overrides: object) -> CorpusEntry:
    defaults = dict(
        topic="testing",
        tags=("quality", "coverage"),
        guidance="Write tests for all public APIs.",
    )
    defaults.update(overrides)  # type: ignore[arg-type]
    return CorpusEntry(**defaults)  # type: ignore[arg-type]


def _make_corpus_snapshot(**overrides: object) -> CorpusSnapshot:
    defaults = dict(
        snapshot_id="python-v1.0.0",
        profile_key="python",
        entries=(_make_corpus_entry(),),
        loaded_at="2026-04-19T10:00:00+00:00",
    )
    defaults.update(overrides)  # type: ignore[arg-type]
    return CorpusSnapshot(**defaults)  # type: ignore[arg-type]


def _make_bundle(**overrides: object) -> EvidenceBundle:
    return EvidenceBundle(**overrides)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Case 1: is_empty True when all defaults
# ---------------------------------------------------------------------------

def test_evidence_bundle_default_is_empty() -> None:
    """EvidenceBundle() with all defaults reports is_empty=True."""
    bundle = EvidenceBundle()
    assert bundle.is_empty is True


# ---------------------------------------------------------------------------
# Case 2: is_empty False when any field is non-empty
# ---------------------------------------------------------------------------

def test_evidence_bundle_not_empty_with_code_signals() -> None:
    bundle = EvidenceBundle(code_signals=_make_code_signals())
    assert bundle.is_empty is False


def test_evidence_bundle_not_empty_with_url_list() -> None:
    bundle = EvidenceBundle(url_list=("https://example.com",))
    assert bundle.is_empty is False


def test_evidence_bundle_not_empty_with_corpus_snapshot() -> None:
    bundle = EvidenceBundle(corpus_snapshot=_make_corpus_snapshot())
    assert bundle.is_empty is False


# ---------------------------------------------------------------------------
# Case 3: scope_tag != primary_language raises ValueError
# ---------------------------------------------------------------------------

def test_code_signals_scope_tag_mismatch_raises() -> None:
    with pytest.raises(ValueError, match="scope_tag must equal primary_language"):
        _make_code_signals(scope_tag="javascript")


# ---------------------------------------------------------------------------
# Case 4: Invalid stack_id format raises ValueError
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("bad_stack_id", [
    "Python",       # uppercase
    "123python",    # starts with digit
    "",             # empty string
    "py thon",      # space
    "_python",      # leading underscore
])
def test_code_signals_invalid_stack_id_raises(bad_stack_id: str) -> None:
    with pytest.raises(ValueError, match="Invalid stack_id format"):
        _make_code_signals(stack_id=bad_stack_id)


def test_code_signals_valid_stack_id_with_plus() -> None:
    """stack_id may contain '+' (e.g. 'c++')."""
    cs = _make_code_signals(stack_id="c++", primary_language="c++", scope_tag="c++")
    assert cs.stack_id == "c++"


# ---------------------------------------------------------------------------
# Case 5: representative_files with leading slash raises ValueError
# ---------------------------------------------------------------------------

def test_code_signals_leading_slash_in_files_raises() -> None:
    with pytest.raises(ValueError, match="repo-relative paths without leading slash"):
        _make_code_signals(representative_files=("/absolute/path.py",))


def test_code_signals_empty_string_in_files_raises() -> None:
    with pytest.raises(ValueError, match="repo-relative paths without leading slash"):
        _make_code_signals(representative_files=("",))


# ---------------------------------------------------------------------------
# Case 6: Invalid snapshot_id format raises ValueError
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("bad_snapshot_id", [
    "Python-v1.0.0",    # uppercase
    "python-1.0.0",     # missing 'v' prefix
    "python-v1",        # incomplete semver
    "python-v1.0",      # incomplete semver (two parts only)
    "",                 # empty string
    "python_v1.0.0",    # underscore instead of hyphen before v
])
def test_corpus_snapshot_invalid_id_raises(bad_snapshot_id: str) -> None:
    with pytest.raises(ValueError, match="Invalid snapshot_id format"):
        _make_corpus_snapshot(snapshot_id=bad_snapshot_id)


def test_corpus_snapshot_valid_id() -> None:
    snap = _make_corpus_snapshot(snapshot_id="python-v2.10.3")
    assert snap.snapshot_id == "python-v2.10.3"


# ---------------------------------------------------------------------------
# Case 7: url_list with empty string raises ValueError
# ---------------------------------------------------------------------------

def test_evidence_bundle_empty_url_raises() -> None:
    with pytest.raises(ValueError, match="url_list must not contain empty strings"):
        EvidenceBundle(url_list=("https://example.com", ""))


# ---------------------------------------------------------------------------
# Case 8: Frozen dataclasses raise FrozenInstanceError on mutation
# ---------------------------------------------------------------------------

def test_code_signals_is_frozen() -> None:
    cs = _make_code_signals()
    with pytest.raises(Exception):  # FrozenInstanceError
        cs.stack_id = "new-id"  # type: ignore[misc]


def test_corpus_entry_is_frozen() -> None:
    entry = _make_corpus_entry()
    with pytest.raises(Exception):
        entry.topic = "other"  # type: ignore[misc]


def test_corpus_snapshot_is_frozen() -> None:
    snap = _make_corpus_snapshot()
    with pytest.raises(Exception):
        snap.snapshot_id = "other-v1.0.0"  # type: ignore[misc]


def test_evidence_bundle_is_frozen() -> None:
    bundle = EvidenceBundle()
    with pytest.raises(Exception):
        bundle.collected_at = "2026-01-01T00:00:00+00:00"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Case 9: All dataclasses are hashable
# ---------------------------------------------------------------------------

def test_all_dataclasses_are_hashable() -> None:
    cs = _make_code_signals()
    entry = _make_corpus_entry()
    snap = _make_corpus_snapshot()
    bundle = EvidenceBundle(
        code_signals=cs,
        url_list=("https://example.com",),
        corpus_snapshot=snap,
    )

    # Usable as dict keys
    d = {cs: "code_signals", entry: "entry", snap: "snap", bundle: "bundle"}
    assert len(d) == 4

    # Usable in sets
    s = {cs, entry, snap, bundle}
    assert len(s) == 4


def test_identical_bundles_have_same_hash() -> None:
    """Two EvidenceBundles with identical content hash to the same value."""
    b1 = EvidenceBundle(url_list=("https://a.com", "https://b.com"))
    b2 = EvidenceBundle(url_list=("https://a.com", "https://b.com"))
    assert hash(b1) == hash(b2)
    assert b1 == b2
