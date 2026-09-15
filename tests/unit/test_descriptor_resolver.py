"""Unit tests for the IC-DESCRIPTOR shared content-descriptor resolver (#2469 WP02).

Exercises ``resolve_descriptor`` / ``descriptor_still_live`` / the S3776
pre-extraction helpers (``_candidate_lines`` / ``_select_occurrence`` /
``_assert_exactly_one``) / ``assert_descriptor_unique_within_qualname`` against
production-shaped fixtures mirroring the two disambiguation axes documented in
``research.md`` D-1/D-2 and ``plan.md``'s Post-Plan Squad Hardening table:

* RJ#1/RJ#2 shape — same qualname (``_coord_mid8``), different substring.
* TR#1-5 shape — identical token line (``subprocess . run (``), different or
  same qualname, requiring the ``occurrence`` disambiguator (D-2).

See ``kitty-specs/content-address-ratchet-allowlists-01KX8M4D/contracts/descriptor-resolver.md``
for the authoritative interface contract this test file validates against.

``tests/unit/`` was never in scope for the arch-suite gates, so this file needs no
WP05 dependency (keeping WP02 the dep-free keystone WP03/WP04 branch from).
"""

from __future__ import annotations

import pytest

from tests.architectural._ratchet_keys import (
    CompositeKey,
    ContentDescriptor,
    DescriptorResolutionError,
    _assert_exactly_one,
    _candidate_lines,
    _select_occurrence,
    assert_descriptor_unique_within_qualname,
    composite_key,
    descriptor_still_live,
    resolve_descriptor,
)

pytestmark = [pytest.mark.unit]

# --------------------------------------------------------------------------- #
# Fixtures — production-shaped source snippets, not placeholders.
# --------------------------------------------------------------------------- #

#: RJ#1/RJ#2 shape: ``coordination/surface_resolver.py``'s ``_coord_mid8`` — a
#: single qualname holding two distinct raw-join sites (plan.md's descriptor
#: feasibility table). Mirrors the real function's shape verbatim.
_RJ_SOURCE = '''\
def _coord_mid8(meta, mission_slug, repo_root):
    mid8 = resolve_declared_mid8(meta, mission_slug)
    if mid8:
        return mid8
    raise StatusReadPathNotFound(
        repo_root=repo_root,
        mission_slug=mission_slug,
        mid8="",
        coord_candidate=repo_root
        / ".worktrees"
        / f"{mission_slug}-coord"
        / KITTY_SPECS_DIR
        / mission_slug,
        primary_candidate=repo_root / KITTY_SPECS_DIR / mission_slug,
    )
'''
_RJ_REL_PATH = "src/specify_cli/coordination/surface_resolver.py"
_RJ_QUALNAME = "_coord_mid8"
_RJ_SUBSTRING_1 = "coord_candidate = repo_root"
_RJ_SUBSTRING_2 = "primary_candidate = repo_root / KITTY_SPECS_DIR / mission_slug"

#: D-2 shape: TWO byte-identical ``subprocess . run ( cmd )`` findings inside
#: ONE qualname — the case that FORCES an explicit ``occurrence`` ordinal
#: because ``composite_key`` collides by construction for identical lines.
_AMBIGUOUS_SOURCE = '''\
def _workflow_evidence_missing(paths):
    for path in paths:
        subprocess . run ( cmd )
        subprocess . run ( cmd )
    return False
'''
_AMBIGUOUS_REL_PATH = "src/specify_cli/coordination/gates_core.py"
_AMBIGUOUS_QUALNAME = "_workflow_evidence_missing"
_AMBIGUOUS_SUBSTRING = "subprocess . run ("

#: TR shape variant: shared ``subprocess . run (`` substring, but the two
#: candidate lines differ (``cmd`` vs ``cmd2``) so ``occurrence`` selects a
#: genuinely DIFFERENT composite key — proves the ordinal actually disambiguates
#: rather than being a no-op.
_OCCURRENCE_SOURCE = '''\
def _workflow_evidence_missing(paths):
    for path in paths:
        subprocess . run ( cmd )
        subprocess . run ( cmd2 )
    return False
'''

#: TR#2/TR#3 shape: identical ``subprocess . run (`` token line reused across
#: TWO DIFFERENT qualnames (``status_porcelain`` / ``show_blob``) — the
#: qualname is the ONLY disambiguator here (plan.md's descriptor table).
_TR_SOURCE = '''\
def status_porcelain(repo_root):
    result = subprocess . run (
        ["git", "status", "--porcelain"], cwd=repo_root, capture_output=True
    )
    return result.stdout

def show_blob(repo_root, ref):
    result = subprocess . run (
        ["git", "show", ref], cwd=repo_root, capture_output=True
    )
    return result.stdout
'''
_TR_REL_PATH = "src/specify_cli/coordination/gates_core.py"

#: WS#1 shape (plan.md table) for the non-vacuity self-test: a docstring
#: QUOTES the same pattern one line above the real finding — a raw-source
#: substring match would be fooled by the docstring; the normalized-token
#: match must land on the real (3rd) line.
_NON_VACUITY_SOURCE = '''\
def _resolve_write_target(coord_branch, current_branch):
    """coord_branch or _current_branch selects the target."""
    return coord_branch or _current_branch
'''
_NON_VACUITY_REL_PATH = "src/specify_cli/coordination/status_transition.py"
_NON_VACUITY_TRUE_LINE = 3


# --------------------------------------------------------------------------- #
# Axis 1 — same qualname, different substring (RJ#1/RJ#2 shape).
# --------------------------------------------------------------------------- #


def test_same_qualname_different_substring_yields_distinct_keys() -> None:
    rj1 = ContentDescriptor(_RJ_REL_PATH, _RJ_QUALNAME, _RJ_SUBSTRING_1, None, "rj1")
    rj2 = ContentDescriptor(_RJ_REL_PATH, _RJ_QUALNAME, _RJ_SUBSTRING_2, None, "rj2")

    key1 = resolve_descriptor(_RJ_SOURCE, rj1)
    key2 = resolve_descriptor(_RJ_SOURCE, rj2)

    assert key1 != key2
    assert key1[0] == key2[0] == _RJ_REL_PATH
    assert key1[1] == key2[1] == _RJ_QUALNAME  # same qualname
    assert key1[2] != key2[2]  # distinct token line is what disambiguates


# --------------------------------------------------------------------------- #
# Axis 2 — identical token line, different qualname (TR#2/TR#3 shape).
# --------------------------------------------------------------------------- #


def test_identical_token_line_different_qualname_yields_distinct_keys() -> None:
    tr2 = ContentDescriptor(_TR_REL_PATH, "status_porcelain", _AMBIGUOUS_SUBSTRING, None, "tr2")
    tr3 = ContentDescriptor(_TR_REL_PATH, "show_blob", _AMBIGUOUS_SUBSTRING, None, "tr3")

    key2 = resolve_descriptor(_TR_SOURCE, tr2)
    key3 = resolve_descriptor(_TR_SOURCE, tr3)

    assert key2 != key3
    assert key2[1] != key3[1]  # qualname is the disambiguator
    assert key2[2] == key3[2]  # SAME normalized token text in both functions


# --------------------------------------------------------------------------- #
# Exactly-one enforcement (D-1) — 0 matches, >1 matches, occurrence selection.
# --------------------------------------------------------------------------- #


def test_zero_matches_raises() -> None:
    descriptor = ContentDescriptor(_RJ_REL_PATH, _RJ_QUALNAME, "no such token anywhere", None, "r")
    with pytest.raises(DescriptorResolutionError):
        resolve_descriptor(_RJ_SOURCE, descriptor)


def test_multiple_matches_without_occurrence_raises() -> None:
    descriptor = ContentDescriptor(
        _AMBIGUOUS_REL_PATH, _AMBIGUOUS_QUALNAME, _AMBIGUOUS_SUBSTRING, None, "r"
    )
    with pytest.raises(DescriptorResolutionError):
        resolve_descriptor(_AMBIGUOUS_SOURCE, descriptor)


def test_occurrence_selects_the_correct_candidate() -> None:
    first = ContentDescriptor(_AMBIGUOUS_REL_PATH, _AMBIGUOUS_QUALNAME, _AMBIGUOUS_SUBSTRING, 0, "r")
    second = ContentDescriptor(_AMBIGUOUS_REL_PATH, _AMBIGUOUS_QUALNAME, _AMBIGUOUS_SUBSTRING, 1, "r")

    key_first = resolve_descriptor(_OCCURRENCE_SOURCE, first)
    key_second = resolve_descriptor(_OCCURRENCE_SOURCE, second)

    assert key_first != key_second
    assert key_first == (_AMBIGUOUS_REL_PATH, _AMBIGUOUS_QUALNAME, "subprocess . run ( cmd )")
    assert key_second == (_AMBIGUOUS_REL_PATH, _AMBIGUOUS_QUALNAME, "subprocess . run ( cmd2 )")


def test_occurrence_out_of_range_raises() -> None:
    descriptor = ContentDescriptor(_AMBIGUOUS_REL_PATH, _AMBIGUOUS_QUALNAME, _AMBIGUOUS_SUBSTRING, 5, "r")
    with pytest.raises(DescriptorResolutionError):
        resolve_descriptor(_OCCURRENCE_SOURCE, descriptor)


# --------------------------------------------------------------------------- #
# T009 — non-vacuity self-test.
# --------------------------------------------------------------------------- #


def test_non_vacuity_resolves_to_the_true_finding_line_not_the_docstring() -> None:
    """A docstring on line 2 QUOTES the same pattern; the resolver must land on
    the real (normalized-token) finding on line 3, proving matching is against
    normalized tokens, never raw source (the descriptor-resolver.md "Authoring
    rule" / vacuous-green failure mode)."""
    descriptor = ContentDescriptor(
        _NON_VACUITY_REL_PATH,
        "_resolve_write_target",
        "coord_branch or _current_branch",
        None,
        "non-vacuity",
    )

    resolved = resolve_descriptor(_NON_VACUITY_SOURCE, descriptor)

    qualname, token_line = composite_key(_NON_VACUITY_SOURCE, _NON_VACUITY_TRUE_LINE)
    assert resolved == (_NON_VACUITY_REL_PATH, qualname, token_line)


# --------------------------------------------------------------------------- #
# descriptor_still_live — exactly-one AND key-equal, never "≥1" (D-1).
# --------------------------------------------------------------------------- #


def test_descriptor_still_live_true_on_exact_match() -> None:
    descriptor = ContentDescriptor(_RJ_REL_PATH, _RJ_QUALNAME, _RJ_SUBSTRING_1, None, "r")
    seeded = resolve_descriptor(_RJ_SOURCE, descriptor)

    assert descriptor_still_live(_RJ_SOURCE, descriptor, seeded) is True


def test_descriptor_still_live_false_on_key_mismatch() -> None:
    descriptor = ContentDescriptor(_RJ_REL_PATH, _RJ_QUALNAME, _RJ_SUBSTRING_1, None, "r")
    seeded = resolve_descriptor(_RJ_SOURCE, descriptor)
    wrong_seed: CompositeKey = (seeded[0], seeded[1], "totally different token")

    assert descriptor_still_live(_RJ_SOURCE, descriptor, wrong_seed) is False


def test_descriptor_still_live_false_on_zero_matches() -> None:
    descriptor = ContentDescriptor(_RJ_REL_PATH, _RJ_QUALNAME, "vanished token", None, "r")

    assert descriptor_still_live(_RJ_SOURCE, descriptor, ("x", "y", "z")) is False


def test_descriptor_still_live_false_on_ambiguous_resolution_never_true_by_any_match() -> None:
    """D-1 bite hole: staleness must be False even though "a" finding with the
    seeded key genuinely exists, because the resolution itself is ambiguous
    (2 candidates, no occurrence). A forbidden "≥1 finding matches" semantics
    would wrongly read True here — this is the exact regression D-1 exists to
    prevent (a routed-away site masking a new sibling offender)."""
    descriptor = ContentDescriptor(
        _AMBIGUOUS_REL_PATH, _AMBIGUOUS_QUALNAME, _AMBIGUOUS_SUBSTRING, None, "r"
    )
    # One of the two colliding candidate lines' true composite key -- under a
    # forbidden "any match" semantics this would satisfy an "in" check.
    seeded: CompositeKey = (
        _AMBIGUOUS_REL_PATH,
        _AMBIGUOUS_QUALNAME,
        _AMBIGUOUS_SUBSTRING + " cmd )",
    )

    assert descriptor_still_live(_AMBIGUOUS_SOURCE, descriptor, seeded) is False


# --------------------------------------------------------------------------- #
# S3776 pre-extraction helpers — each gets its own direct unit test.
# --------------------------------------------------------------------------- #


def test_candidate_lines_finds_all_matches_in_file_order() -> None:
    lines = _candidate_lines(_AMBIGUOUS_SOURCE, _AMBIGUOUS_QUALNAME, _AMBIGUOUS_SUBSTRING)

    assert lines == [3, 4]


def test_candidate_lines_empty_when_qualname_does_not_match() -> None:
    lines = _candidate_lines(_AMBIGUOUS_SOURCE, "some_other_function", _AMBIGUOUS_SUBSTRING)

    assert lines == []


def test_candidate_lines_empty_when_substring_does_not_match() -> None:
    lines = _candidate_lines(_AMBIGUOUS_SOURCE, _AMBIGUOUS_QUALNAME, "no such token")

    assert lines == []


def test_candidate_lines_returns_empty_on_syntax_error() -> None:
    lines = _candidate_lines("def broken(:\n    pass", "broken", "pass")

    assert lines == []


def test_select_occurrence_defaults_to_first_when_unset() -> None:
    assert _select_occurrence([10, 20, 30], None) == 0


def test_select_occurrence_returns_given_ordinal() -> None:
    assert _select_occurrence([10, 20, 30], 2) == 2


def test_assert_exactly_one_passes_for_single_candidate() -> None:
    descriptor = ContentDescriptor("x.py", "q", "t", None, "r")

    _assert_exactly_one([42], descriptor)  # no raise


def test_assert_exactly_one_raises_for_zero_candidates() -> None:
    descriptor = ContentDescriptor("x.py", "q", "t", None, "r")

    with pytest.raises(DescriptorResolutionError):
        _assert_exactly_one([], descriptor)


def test_assert_exactly_one_raises_for_multiple_candidates_without_occurrence() -> None:
    descriptor = ContentDescriptor("x.py", "q", "t", None, "r")

    with pytest.raises(DescriptorResolutionError):
        _assert_exactly_one([1, 2], descriptor)


def test_assert_exactly_one_passes_when_occurrence_in_range() -> None:
    descriptor = ContentDescriptor("x.py", "q", "t", 1, "r")

    _assert_exactly_one([1, 2, 3], descriptor)  # no raise


def test_assert_exactly_one_raises_when_occurrence_out_of_range() -> None:
    descriptor = ContentDescriptor("x.py", "q", "t", 5, "r")

    with pytest.raises(DescriptorResolutionError):
        _assert_exactly_one([1, 2], descriptor)


def test_assert_exactly_one_raises_when_occurrence_negative() -> None:
    descriptor = ContentDescriptor("x.py", "q", "t", -1, "r")

    with pytest.raises(DescriptorResolutionError):
        _assert_exactly_one([1, 2], descriptor)


# --------------------------------------------------------------------------- #
# GAP-1 — import-time unique-within-qualname assertion helper.
# --------------------------------------------------------------------------- #


def test_assert_descriptor_unique_within_qualname_passes_for_unique_descriptor() -> None:
    descriptor = ContentDescriptor(_RJ_REL_PATH, _RJ_QUALNAME, _RJ_SUBSTRING_1, None, "r")

    assert_descriptor_unique_within_qualname(_RJ_SOURCE, descriptor)  # no raise


def test_assert_descriptor_unique_within_qualname_raises_for_ambiguous_descriptor() -> None:
    descriptor = ContentDescriptor(
        _AMBIGUOUS_REL_PATH, _AMBIGUOUS_QUALNAME, _AMBIGUOUS_SUBSTRING, None, "r"
    )

    with pytest.raises(DescriptorResolutionError):
        assert_descriptor_unique_within_qualname(_AMBIGUOUS_SOURCE, descriptor)


def test_assert_descriptor_unique_within_qualname_allows_disambiguated_occurrence() -> None:
    descriptor = ContentDescriptor(_AMBIGUOUS_REL_PATH, _AMBIGUOUS_QUALNAME, _AMBIGUOUS_SUBSTRING, 0, "r")

    assert_descriptor_unique_within_qualname(_AMBIGUOUS_SOURCE, descriptor)  # no raise
