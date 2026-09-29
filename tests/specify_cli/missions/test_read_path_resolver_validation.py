"""NFR-002 tests: rejection fires INSIDE the read primitives, not at a caller.

T004 — prove that:
  (a) the module-private ``_compose_primary_feature_dir`` leaf raises
      ValueError for malformed slugs.
  (b) resolve_mission_read_path raises ValueError for malformed slugs.
  (c) The guard fires BEFORE _resolve_existing_for_slug is called — a guard
      placed AFTER composition would satisfy (a)/(b) while a malformed slug
      had already flowed through path composition (the squad-flagged gaming
      path). The spy assertion makes this un-fakeable.
  (d) A valid real-format slug still returns the composed kitty-specs/<slug>
      path unchanged (NFR-006 regression guard).

read-side-seam-primary-primitive-closure-01KYKMMT WP08 (T035): the public
wrapper ``primary_feature_dir_for_mission`` this file's (a)/(d)/(e)/(f)-group
tests originally targeted is DELETED (SC-001). Its topology-blind,
handle-blind, traversal-guarded composition contract did not disappear with
it — it moved to the module-private ``_compose_primary_feature_dir`` leaf
(C-004: the PERMANENT sanctioned owner of this join), which is what these
tests now exercise directly. ``test_primary_anchor_has_single_canonical_
definition`` (WP03/T012, "the shim now resolves to the canonical object") is
DELETED per DIRECTIVE_041 (PATCHWORK): its entire subject was proving the
now-deleted wrapper had no second, shadow implementation — there is no
wrapper left for a shadow to duplicate.

Fixtures use a real temp git repo + full-ULID-bearing real-format slug
(NFR-003: topology-true, production-shaped data only).
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from specify_cli.missions._read_path_resolver import (
    _compose_primary_feature_dir,
    _resolve_mission_read_path as resolve_mission_read_path,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

# Production-shaped slugs (NFR-003: no fabricated short ids)
_REAL_SLUG = "canonical-seams-path-trust-guard-capability-01KVBBT6"
_REAL_MID8 = "01KVBBT6"
_REAL_MISSION_ID = "01KVBBT6FEQ01NHNSQD7X8JTPE"

_TRAVERSAL_SLUGS = [
    "../escape",
    "..",
    ".",
    "a/b",
    ".hidden",
    "..foo",
    "foo..",
    "a..b",
    "",
    "   ",
]


@pytest.fixture()
def real_git_repo(tmp_path: Path) -> Path:
    """Create a minimal real git repo with kitty-specs directory."""
    subprocess.run(["git", "init", str(tmp_path)], check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        check=True,
        capture_output=True,
        cwd=str(tmp_path),
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        check=True,
        capture_output=True,
        cwd=str(tmp_path),
    )
    # Create the .kittify marker so locate_project_root finds this root
    (tmp_path / ".kittify").mkdir()
    (tmp_path / "kitty-specs").mkdir()
    return tmp_path


# ---------------------------------------------------------------------------
# (a) _compose_primary_feature_dir raises for malformed slugs
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("bad_slug", _TRAVERSAL_SLUGS)
def test_primary_raises_for_malformed_slug(
    real_git_repo: Path,
    bad_slug: str,
) -> None:
    """_compose_primary_feature_dir must raise ValueError for traversal slugs."""
    with pytest.raises(ValueError, match="safe path segment"):
        _compose_primary_feature_dir(real_git_repo, bad_slug)


# ---------------------------------------------------------------------------
# (b) resolve_mission_read_path raises for malformed slugs
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("bad_slug", _TRAVERSAL_SLUGS)
def test_resolve_raises_for_malformed_slug(
    real_git_repo: Path,
    bad_slug: str,
) -> None:
    """resolve_mission_read_path must raise ValueError for traversal slugs."""
    with pytest.raises(ValueError, match="safe path segment"):
        resolve_mission_read_path(real_git_repo, bad_slug, "")


# ---------------------------------------------------------------------------
# (c) Guard fires BEFORE _resolve_existing_for_slug (topology-proof)
# ---------------------------------------------------------------------------
def test_guard_fires_before_resolve_existing_for_slug(real_git_repo: Path) -> None:
    """Spy on _resolve_existing_for_slug: it must NEVER be called with a malformed slug.

    A guard placed AFTER composition would still let the slug flow through
    ``_resolve_existing_for_slug`` before raising. This assertion proves
    the guard is truly at the front of ``resolve_mission_read_path``.
    """
    mock_spy = MagicMock(return_value=None)
    with patch(
        "specify_cli.missions._read_path_resolver._resolve_existing_for_slug",
        mock_spy,
    ), pytest.raises(ValueError, match="safe path segment"):
        resolve_mission_read_path(real_git_repo, "../escape", "")

    # The critical assertion: _resolve_existing_for_slug must NOT have been called
    mock_spy.assert_not_called()


def test_guard_fires_before_resolve_existing_for_various_traversal(
    real_git_repo: Path,
) -> None:
    """Spy asserts _resolve_existing_for_slug not called for any traversal slug."""
    bad_slugs = ["../escape", ".hidden", "..foo", "a..b", "a/b"]
    for bad_slug in bad_slugs:
        mock_spy = MagicMock(return_value=None)
        with (
            patch(
                "specify_cli.missions._read_path_resolver._resolve_existing_for_slug",
                mock_spy,
            ),
            pytest.raises(ValueError, match="safe path segment"),
        ):
            resolve_mission_read_path(real_git_repo, bad_slug, "")
        assert not mock_spy.called, (
            f"_resolve_existing_for_slug was called with malformed slug {bad_slug!r} — "
            f"the guard must fire BEFORE composition"
        )


# ---------------------------------------------------------------------------
# (d) Valid real-format slugs return the composed kitty-specs/<slug> path
# ---------------------------------------------------------------------------
def test_valid_slug_returns_composed_path(real_git_repo: Path) -> None:
    """A valid real-format slug returns the expected kitty-specs/<slug> path (NFR-006).

    Uses resolve_mission_read_path (not candidate_*) to test the primitive
    directly; no coord worktree materialized so it falls through to the primary
    candidate path.
    """
    result = resolve_mission_read_path(
        real_git_repo, _REAL_SLUG, _REAL_MID8, require_exists=False
    )
    # The path should be the kitty-specs/ candidate for this slug
    assert "kitty-specs" in str(result), (
        f"Expected kitty-specs in path, got {result}"
    )
    # Must contain the slug (or a slug-mid8 composite)
    assert _REAL_SLUG in str(result) or _REAL_MID8 in str(result), (
        f"Expected slug {_REAL_SLUG!r} or mid8 {_REAL_MID8!r} in path, got {result}"
    )


def test_primary_valid_slug_returns_composed_path(real_git_repo: Path) -> None:
    """_compose_primary_feature_dir returns kitty-specs/<slug> for valid slug."""
    result = _compose_primary_feature_dir(real_git_repo, _REAL_SLUG)
    assert result.name == _REAL_SLUG, (
        f"Expected directory name {_REAL_SLUG!r}, got {result.name!r}"
    )
    assert "kitty-specs" in str(result), (
        f"Expected kitty-specs in path, got {result}"
    )


def test_primary_full_ulid_returns_composed_path(real_git_repo: Path) -> None:
    """_compose_primary_feature_dir accepts a full 26-char ULID (NFR-006)."""
    result = _compose_primary_feature_dir(real_git_repo, _REAL_MISSION_ID)
    assert result.name == _REAL_MISSION_ID
    assert "kitty-specs" in str(result)


# ===========================================================================
# WP03 / T012 — topology-blind contract + delegator policy
# ===========================================================================
#
# FR-009/T1: these tests prove (a) every primary-anchored caller still reads
# its primary ``meta.json`` through the leaf, and (b) the mutation that
# injects mid8 composition into the primary anchor BREAKS those
# primary-anchored reads.


# ---------------------------------------------------------------------------
# (e) The single canonical raw-slug primary anchor (T009; shim retired in WP07)
# ---------------------------------------------------------------------------
def test_primary_anchor_is_topology_blind_raw_slug(real_git_repo: Path) -> None:
    """The primary anchor returns the RAW slug dir, never a coord path.

    The previous shadow implementation trusted ``repo_root`` verbatim and
    composed via ``compose_meta_json_path``; the canonical form re-anchors to the
    primary checkout and returns ``kitty-specs/<raw-slug>``.
    """
    result = _compose_primary_feature_dir(real_git_repo, _REAL_SLUG)
    assert result.name == _REAL_SLUG
    assert ".worktrees" not in str(result)
    assert "kitty-specs" in str(result)


def test_primary_anchor_applies_safe_segment_guard(real_git_repo: Path) -> None:
    """The canonical anchor applies its traversal guard (NFR-002).

    The old shim composed the path WITHOUT ``assert_safe_path_segment``; the
    canonical anchor guards first. This is a strict safety improvement and proves
    the guarded body is wired, not a guard-less twin.
    """
    with pytest.raises(ValueError, match="safe path segment"):
        _compose_primary_feature_dir(real_git_repo, "../escape")


# ---------------------------------------------------------------------------
# (f) Primary-anchored callers still read the primary meta.json (T012)
# ---------------------------------------------------------------------------
def _write_primary_meta(repo_root: Path, slug: str, **fields: object) -> Path:
    feature_dir = repo_root / "kitty-specs" / slug
    feature_dir.mkdir(parents=True, exist_ok=True)
    import json

    (feature_dir / "meta.json").write_text(json.dumps(fields), encoding="utf-8")
    return feature_dir


def test_mid8_from_primary_meta_reads_primary_anchor(real_git_repo: Path) -> None:
    """``_mid8_from_primary_meta`` derives the mid8 from the PRIMARY meta.json.

    This is the canonical caller the topology-blind contract protects: it reads
    the primary ``meta.json`` to DERIVE the mid8 — so the primary anchor MUST be
    raw-slug (composing the mid8 inside the anchor would be circular).
    """
    from mission_runtime.resolution import _mid8_from_primary_meta

    _write_primary_meta(real_git_repo, _REAL_SLUG, mission_id=_REAL_MISSION_ID)
    assert _mid8_from_primary_meta(real_git_repo, _REAL_SLUG) == _REAL_MID8


def test_mid8_from_primary_meta_degrades_to_empty_on_malformed_meta(
    real_git_repo: Path,
) -> None:
    """A malformed PRIMARY ``meta.json`` degrades to ``""`` (FR-006 contract).

    ``_mid8_from_primary_meta`` composes the primary anchor then calls the ONE
    fail-closed reader ``load_meta_fail_closed(primary_dir)`` (FR-007 / #3162
    routing). The ``except MissionMetaReadError: return ""`` arm reproduces the
    historical malformed→"" degrade (landing-fold coverage:
    read-side-seam-primary-primitive-closure-01KYKMMT's wrapper→leaf swap
    re-attributed this pre-existing, behaviour-unchanged arm to the new leaf
    call (``_compose_primary_feature_dir``) without any test driving it through
    the malformed-meta path). No mocking of the compose/load primitives --
    only the ``meta.json`` CONTENTS are invalid, so the exact same
    malformed-meta branch the routed reader contract documents is what
    actually fires.
    """
    from mission_runtime.resolution import _mid8_from_primary_meta

    feature_dir = real_git_repo / "kitty-specs" / _REAL_SLUG
    feature_dir.mkdir(parents=True, exist_ok=True)
    # Not valid JSON -- the fail-closed reader's contract turns this into a
    # typed MissionMetaReadError at the parse boundary, degraded to "" here.
    (feature_dir / "meta.json").write_text("{not valid json", encoding="utf-8")

    assert _mid8_from_primary_meta(real_git_repo, _REAL_SLUG) == ""


def test_resolve_coordination_branch_reads_primary_anchor(
    real_git_repo: Path,
) -> None:
    """``_resolve_coordination_branch`` reads the primary ``meta.json`` (FR-003)."""
    from mission_runtime.resolution import _resolve_coordination_branch

    branch = f"kitty/mission-{_REAL_SLUG}"
    _write_primary_meta(
        real_git_repo,
        _REAL_SLUG,
        mission_id=_REAL_MISSION_ID,
        coordination_branch=branch,
    )
    assert _resolve_coordination_branch(real_git_repo, _REAL_SLUG) == branch


def test_resolve_mission_id_reads_primary_anchor(real_git_repo: Path) -> None:
    """``_resolve_mission_id`` reads the primary ``meta.json`` (FR-003)."""
    from mission_runtime.resolution import _resolve_mission_id

    _write_primary_meta(real_git_repo, _REAL_SLUG, mission_id=_REAL_MISSION_ID)
    assert _resolve_mission_id(real_git_repo, _REAL_SLUG) == _REAL_MISSION_ID


# ---------------------------------------------------------------------------
# (g) Mutation: inject mid8 composition into the primary anchor → reads FAIL
# ---------------------------------------------------------------------------
def test_mutation_mid8_composition_breaks_primary_anchored_reads(
    real_git_repo: Path,
) -> None:
    """Topology-blind contract is load-bearing (the mutation MUST bite).

    Mutate the topology-blind primary-dir assembler to compose ``<slug>-<mid8>``
    (the REVERSED-direction change the corrected premise forbids). The mission
    here uses a BARE human slug (no embedded mid8) whose primary ``meta.json``
    lives at ``kitty-specs/<bare-slug>/`` — exactly the real layout where the
    mid8 is declared in meta but NOT in the directory name. The mutated anchor
    composes ``kitty-specs/<bare-slug>-<mid8>/`` (which does not exist), so
    ``_mid8_from_primary_meta`` can no longer read the meta and the mid8 is LOST.
    If this test does NOT fail under the mutation, the contract is not actually
    load-bearing and the disambiguation is decorative.

    (For an already-mid8-embedded slug the raw and composed dir names coincide,
    so the mutation is silent — proving precisely why the anchor MUST stay
    raw-slug for the bare-slug-with-declared-mid8 case.)

    read-side-seam-primary-primitive-closure-01KYKMMT WP03 (T016/T021): the
    patch target is the module-private leaf ``_compose_primary_feature_dir``,
    not the public wrapper ``primary_feature_dir_for_mission``. WP03 re-points
    ``_mid8_from_primary_meta``'s function-local import at the leaf directly
    (so the seam's PRIMARY leg cannot recurse through the wrapper) — patching
    the wrapper name here would silently stop intercepting this call and the
    mutation would go unnoticed (a vacuous-gate hazard, tactic:architectural-
    gate-non-vacuity). Verified red-first against the pre-fix patch target: the
    old ``primary_feature_dir_for_mission`` patch string leaves this assertion
    failing (``mutated == _REAL_MID8``) because the mutation is silently never
    invoked.
    """
    from unittest.mock import patch

    from specify_cli.lanes.branch_naming import mid8_from_slug

    # Bare human slug; mid8 declared in meta only (NOT in the dir name).
    bare_slug = "canonical-seams-path-trust-guard-capability"
    assert mid8_from_slug(bare_slug) == "", "bare slug must carry no parseable tail"
    _write_primary_meta(real_git_repo, bare_slug, mission_id=_REAL_MISSION_ID)

    # Baseline: with the real raw-slug anchor, the mid8 derives correctly.
    from mission_runtime.resolution import _mid8_from_primary_meta

    assert _mid8_from_primary_meta(real_git_repo, bare_slug) == _REAL_MID8

    def _mid8_composing_anchor(repo_root: Path, slug: str) -> Path:
        # The forbidden mutation: compose <slug>-<mid8> into the primary anchor.
        derived = mid8_from_slug(slug) or _REAL_MID8
        composed = slug if slug.endswith(f"-{derived}") else f"{slug}-{derived}"
        return repo_root / "kitty-specs" / composed

    # ``_mid8_from_primary_meta`` imports ``_compose_primary_feature_dir``
    # function-locally from ``_read_path_resolver`` (WP03 T016), so the mutation
    # patches the canonical source module (where the late import resolves),
    # proving the primary anchor leaf — not a copy — is the load-bearing
    # contract surface.
    with patch(
        "specify_cli.missions._read_path_resolver._compose_primary_feature_dir",
        _mid8_composing_anchor,
    ):
        # The mutated anchor points at kitty-specs/<bare-slug>-<mid8>/ which has
        # no meta.json → the derive silently returns "" (the mid8 is LOST).
        mutated = _mid8_from_primary_meta(real_git_repo, bare_slug)
    assert mutated != _REAL_MID8, (
        "mutation injecting mid8 composition into the primary anchor did NOT "
        "break the primary-anchored read — the topology-blind contract is not "
        "load-bearing (regression: the reversed-direction change would pass)"
    )


# ---------------------------------------------------------------------------
# (h) Shared resolve-dir-or-typed-error delegator policy (T011)
# ---------------------------------------------------------------------------
def test_delegator_returns_surface_parent_when_meta_present(
    real_git_repo: Path,
) -> None:
    """The delegator returns the surface DIR (``surface.parent``) on the happy path.

    No coord branch declared + primary meta present → the surface resolver yields
    the primary status surface, and the delegator returns its containing dir.
    """
    from specify_cli.missions._read_path_resolver import (
        resolve_surface_dir_or_typed_error,
    )

    feature_dir = _write_primary_meta(
        real_git_repo, _REAL_SLUG, mission_id=_REAL_MISSION_ID
    )
    sentinel = real_git_repo / "kitty-specs" / "SENTINEL-NOT-USED"
    result = resolve_surface_dir_or_typed_error(
        real_git_repo, _REAL_SLUG, on_missing_meta=sentinel
    )
    assert result.resolve() == feature_dir.resolve()


def test_delegator_returns_on_missing_meta_in_first_write_window(
    real_git_repo: Path,
) -> None:
    """No ``meta.json`` yet → the delegator returns the caller's primary fallback.

    Reconciled UNION policy: the create→first-write window (FileNotFoundError)
    returns ``on_missing_meta``. The two old wrappers differed only in how they
    spelled that fallback; the delegator delegates the spelling to the caller.
    """
    from specify_cli.missions._read_path_resolver import (
        resolve_surface_dir_or_typed_error,
    )

    fallback = real_git_repo / "kitty-specs" / _REAL_SLUG
    result = resolve_surface_dir_or_typed_error(
        real_git_repo, _REAL_SLUG, on_missing_meta=fallback
    )
    assert result == fallback


def test_delegator_returns_on_missing_meta_for_malformed_slug(
    real_git_repo: Path,
) -> None:
    """Malformed slug (ValueError) is in the reconciled UNION → fallback returned.

    ``aggregate._resolve_read_dir`` did NOT catch ValueError while
    ``resolution._resolve_status_surface_dir`` did; the delegator's documented
    union catches both FileNotFoundError and ValueError.
    """
    from specify_cli.missions._read_path_resolver import (
        resolve_surface_dir_or_typed_error,
    )

    fallback = real_git_repo / "kitty-specs" / "fallback-marker"
    result = resolve_surface_dir_or_typed_error(
        real_git_repo, "../escape", on_missing_meta=fallback
    )
    assert result == fallback


def test_delegator_propagates_status_read_path_not_found(
    real_git_repo: Path,
) -> None:
    """Surface fail-closed propagates StatusReadPathNotFound UNCHANGED (no translation).

    The delegator does NOT pick a boundary translation (aggregate →
    CoordAuthorityUnavailable; mission_runtime → ActionContextError) — typed-error
    convergence is WP06. It propagates the raw StatusReadPathNotFound so each
    caller translates it (and the ``error_code`` survives).
    """
    from unittest.mock import patch

    import specify_cli.missions._read_path_resolver as rpr
    from specify_cli.missions._read_path_resolver import (
        StatusReadPathNotFound,
        resolve_surface_dir_or_typed_error,
    )

    exc = StatusReadPathNotFound(
        repo_root=real_git_repo,
        mission_slug=_REAL_SLUG,
        mid8=_REAL_MID8,
        coord_candidate=real_git_repo / "coord",
        primary_candidate=real_git_repo / "primary",
    )

    def _raise(_repo: Path, _slug: str) -> Path:
        raise exc

    with patch(
        "specify_cli.coordination.surface_resolver.resolve_status_surface",
        _raise,
    ), pytest.raises(StatusReadPathNotFound) as caught:
        resolve_surface_dir_or_typed_error(
            real_git_repo, _REAL_SLUG, on_missing_meta=real_git_repo
        )
    assert caught.value.error_code == rpr.STATUS_READ_PATH_NOT_FOUND_CODE
    # Pin the diagnostic message frame operators/callers rely on.
    message = str(caught.value)
    assert "Status read path not found for" in message
    assert _REAL_SLUG in message


def test_delegator_propagates_ambiguous_selector(real_git_repo: Path) -> None:
    """Ambiguous handle propagates MissionSelectorAmbiguous (no silent first-match)."""
    from unittest.mock import patch

    from specify_cli.missions._read_path_resolver import (
        MissionSelectorAmbiguous,
        resolve_surface_dir_or_typed_error,
    )

    exc = MissionSelectorAmbiguous(handle="01KTAMBG", candidates=["a", "b"])

    def _raise(_repo: Path, _slug: str) -> Path:
        raise exc

    with patch(
        "specify_cli.coordination.surface_resolver.resolve_status_surface",
        _raise,
    ), pytest.raises(MissionSelectorAmbiguous):
        resolve_surface_dir_or_typed_error(
            real_git_repo, "01KTAMBG", on_missing_meta=real_git_repo
        )
