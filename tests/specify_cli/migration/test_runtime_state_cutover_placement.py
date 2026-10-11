"""ATDD unit tests for FR-001: ``_flip_phase`` routed through the placement port.

Red-first proof (contract C-WRITER-1, WP01 T001/T002) for
``migration/runtime_state_cutover.py``'s sole ``status_phase`` writer:

* a resolved PRIMARY home that disagrees with the write target fails closed
  (:class:`~specify_cli.migration.runtime_state_cutover.PlacementMismatchError`,
  writes nothing) — driven through the PRE-EXISTING public entry point
  ``cutover_mission(feature_dir, status_feature_dir=...)``, not the private
  ``_flip_phase`` directly;
* the mismatch fixture independently proves the port resolves WITHOUT raising
  (anti-scaffold: a resolver crash must never masquerade as this fail-close);
* a genuine resolver *raise* on an otherwise well-formed legacy mission (no
  enclosing git repo) degrades instead of aborting — the entire pre-existing
  ``test_runtime_state_cutover.py`` suite already pins this path (every fixture
  there is a bare ``tmp_path`` with no ``.git``), so this file adds one explicit,
  self-documenting instance of it;
* a genuine PRIMARY dir (the resolved-home == write-target case) still flips
  normally — the non-mismatch regression anchor.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from specify_cli.migration import runtime_state_cutover as rsc
from tests.unit.migration._backfill_fixture import build_mission

pytestmark = [pytest.mark.fast]

_STATUS_PHASE = "status_phase"
_SLUG = "042-demo"
_MISSION_ID = "01JMISSIONULID0000000000AA"


@pytest.fixture(autouse=True)
def _hermetic_git_ceiling(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))


def _init_bare_git_marker(repo_root: Path) -> None:
    """Create the minimal ``.git`` ancestor marker :func:`resolve_canonical_root` needs.

    :func:`~specify_cli.core.paths.resolve_canonical_root` only inspects whether
    ``.git`` is a directory or a worktree-pointer file — it never shells out to
    git — so a bare directory marker is a faithful, cheap fixture (no
    ``subprocess`` git-init needed for this contract).
    """
    (repo_root / ".git").mkdir(parents=True)


def _build_status_leg(status_dir: Path, *, slug: str = _SLUG, mission_id: str = _MISSION_ID) -> None:
    """Materialise a bare COORD-leg dir: just ``meta.json``, no ``tasks/``.

    Mirrors the FR-002 contract's "absent/stale COORD ``tasks/``" shape: the
    seed-event write/read anchor needs a mission dir + ``meta.json`` (for
    ``mission_id``), nothing else — :func:`~specify_cli.status.store.read_event_stream`
    degrades an absent ``status.events.jsonl`` to an empty stream.
    """
    status_dir.mkdir(parents=True, exist_ok=True)
    (status_dir / "meta.json").write_text(
        json.dumps({"mission_id": mission_id, "mission_slug": slug, "mission_type": "software-dev"}),
        encoding="utf-8",
    )


def _build_empty_tasks_leg(feature_dir: Path) -> None:
    """Materialise a PRIMARY-shaped dir with an empty ``tasks/`` (no WP files).

    Enough to pass the "no tasks/ directory" skip-check and produce a trivially
    empty (nothing-to-seed) legacy read — this file's tests exercise FR-001's
    placement contract, not FR-002's data-loss contract, so the read content
    itself is deliberately inert.
    """
    (feature_dir / "tasks").mkdir(parents=True)


# ---------------------------------------------------------------------------
# T001 — red-first: mismatch fails closed (through cutover_mission)
# ---------------------------------------------------------------------------


def test_mismatched_feature_dir_fails_closed_without_writing(tmp_path: Path) -> None:
    """A divergent ``feature_dir`` makes the flip fail closed; writes nothing."""
    repo_root = tmp_path / "repo"
    _init_bare_git_marker(repo_root)

    # The canonical-primary dir for this slug is PRESENT (a real, existing
    # directory) — proves the mismatch is genuine, not an artifact of a
    # nonexistent canonical home.
    canonical_dir = repo_root / "kitty-specs" / _SLUG
    _build_empty_tasks_leg(canonical_dir)

    # The DIVERGENT feature_dir: same slug, same repo, but NOT under the
    # "kitty-specs" shape — canonicalize_feature_dir short-circuits on this
    # (parent.name != KITTY_SPECS_DIR) and returns it unchanged, while the
    # port still resolves the canonical "kitty-specs/<slug>" answer above.
    divergent_dir = repo_root / "stale-worktree-copy" / _SLUG
    _build_empty_tasks_leg(divergent_dir)

    status_dir = tmp_path / "coord-leg"
    _build_status_leg(status_dir)

    # Anti-scaffold precondition (T001 CRITICAL): the port resolves WITHOUT
    # raising, and its answer is exactly the canonical dir — proving the
    # upcoming fail-close comes from the MISMATCH branch, not a masked crash.
    from mission_runtime import MissionArtifactKind, resolve_artifact_surface

    resolved = resolve_artifact_surface(repo_root, _SLUG, MissionArtifactKind.PRIMARY_METADATA)
    assert resolved.path == canonical_dir
    assert resolved.path != divergent_dir

    # The contract fails CLOSED by raising (C-WRITER-1: "the call fails closed
    # (raises, writes nothing)") — cutover_mission does not swallow this into a
    # CutoverResult, unlike the ordering/backfill errors it does catch.
    with pytest.raises(rsc.PlacementMismatchError):
        rsc.cutover_mission(divergent_dir, status_feature_dir=status_dir)

    # Nothing was written at either candidate location.
    assert not (divergent_dir / "meta.json").exists()
    assert not (canonical_dir / "meta.json").exists()


def test_flip_phase_raises_distinct_mismatch_marker(tmp_path: Path) -> None:
    """Calling ``_flip_phase`` directly raises the DISTINCT ``PlacementMismatchError``.

    Pinning the exact exception type (not a bare crash) is the anti-scaffold
    guard T001 calls for: a generic resolver raise must degrade (see
    ``test_resolver_failure_on_ordinary_mission_degrades_and_still_flips``
    below), so only this specific marker may signal the fail-close.
    """
    repo_root = tmp_path / "repo"
    _init_bare_git_marker(repo_root)
    canonical_dir = repo_root / "kitty-specs" / _SLUG
    _build_empty_tasks_leg(canonical_dir)
    divergent_dir = repo_root / "stale-worktree-copy" / _SLUG
    _build_empty_tasks_leg(divergent_dir)

    with pytest.raises(rsc.PlacementMismatchError):
        rsc._flip_phase(divergent_dir)

    assert not (divergent_dir / "meta.json").exists()


# ---------------------------------------------------------------------------
# T002 — resolver-raise degrades (does NOT fail closed)
# ---------------------------------------------------------------------------


def test_resolver_failure_on_ordinary_mission_degrades_and_still_flips(tmp_path: Path) -> None:
    """No enclosing git repo => the port raise degrades; the flip still succeeds.

    This is the sibling assertion T001 requires: a genuine resolver *raise* on
    a well-formed legacy mission (here: no ``.git`` ancestor at all, exactly
    the shape ``tests/unit/migration/_backfill_fixture.build_mission`` has
    always produced) must NOT abort the cutover — it is a resolvability
    hiccup, not a placement violation (NFR-002).
    """
    feature_dir = build_mission(tmp_path)  # no .git anywhere in tmp_path's ancestry

    result = rsc.cutover_mission(feature_dir)

    assert result.flipped is True
    assert result.error is None
    assert json.loads((feature_dir / "meta.json").read_text())[_STATUS_PHASE] == "1"


def test_flip_phase_degrades_directly_on_workspace_root_not_found(tmp_path: Path) -> None:
    """``_flip_phase`` called directly also degrades (writes via the fallback target)."""
    feature_dir = build_mission(tmp_path)
    rsc._seed_phase(feature_dir, dry_run=False)

    rsc._flip_phase(feature_dir)  # must not raise

    assert json.loads((feature_dir / "meta.json").read_text())[_STATUS_PHASE] == "1"


# ---------------------------------------------------------------------------
# Regression anchor — a genuine PRIMARY dir still flips (C-WRITER-1 positive leg)
# ---------------------------------------------------------------------------


def test_genuine_primary_dir_still_flips(tmp_path: Path) -> None:
    """feature_dir == the port's own resolved PRIMARY home: no mismatch, flips."""
    repo_root = tmp_path / "repo"
    _init_bare_git_marker(repo_root)
    feature_dir = repo_root / "kitty-specs" / _SLUG
    _build_empty_tasks_leg(feature_dir)
    (feature_dir / "meta.json").write_text(
        json.dumps({"mission_id": _MISSION_ID, "mission_slug": _SLUG, "mission_type": "software-dev"}),
        encoding="utf-8",
    )

    from mission_runtime import MissionArtifactKind, resolve_artifact_surface

    resolved = resolve_artifact_surface(repo_root, _SLUG, MissionArtifactKind.PRIMARY_METADATA)
    assert resolved.path == feature_dir

    result = rsc.cutover_mission(feature_dir)

    assert result.flipped is True
    assert result.error is None
    assert json.loads((feature_dir / "meta.json").read_text())[_STATUS_PHASE] == "1"


def test_placement_home_and_canonicalize_agree_through_symlinked_root(tmp_path: Path) -> None:
    """Defensive pin (aggregate-review NOTE 2): the FR-001 fail-close compares the
    port's resolved PRIMARY home against ``canonicalize_feature_dir(feature_dir)``.
    Its correctness depends on both normalizers producing an identically-formed path.
    If they ever diverged on symlink/``resolve()`` handling, a genuine mission reached
    through a symlinked repo root would spuriously raise ``PlacementMismatchError``.
    Pin the contract: the two normalizers agree, and the flip succeeds through the link.
    """
    real_root = tmp_path / "real-repo"
    _init_bare_git_marker(real_root)
    feature_dir_real = real_root / "kitty-specs" / _SLUG
    _build_empty_tasks_leg(feature_dir_real)
    (feature_dir_real / "meta.json").write_text(
        json.dumps({"mission_id": _MISSION_ID, "mission_slug": _SLUG, "mission_type": "software-dev"}),
        encoding="utf-8",
    )

    # A path that differs textually from the real dir but resolves to the same inode.
    link_root = tmp_path / "link-repo"
    link_root.symlink_to(real_root, target_is_directory=True)
    feature_dir_via_link = link_root / "kitty-specs" / _SLUG

    from mission_runtime import MissionArtifactKind, resolve_artifact_surface
    from specify_cli.core.paths import resolve_canonical_root
    from specify_cli.workspace import canonicalize_feature_dir

    repo_root = resolve_canonical_root(feature_dir_via_link)
    resolved_home = resolve_artifact_surface(
        repo_root, _SLUG, MissionArtifactKind.PRIMARY_METADATA
    ).path
    target = canonicalize_feature_dir(feature_dir_via_link)

    # The load-bearing contract _flip_phase relies on: identical normalization,
    # so a legitimate mission never fail-closes on a normalization mismatch.
    assert resolved_home == target

    result = rsc.cutover_mission(feature_dir_via_link)
    assert result.flipped is True
    assert result.error is None


# ---------------------------------------------------------------------------
# Landing-fold finding 1 (P1) — corpus walkers must contain the fail-close
# ---------------------------------------------------------------------------


def test_cutover_repo_continues_past_placement_mismatch_and_stays_non_zero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """One placement-mismatched mission must not abort the whole corpus walk.

    ``cutover_mission`` itself is DOCUMENTED to RAISE ``PlacementMismatchError``
    (C-WRITER-1, T001) rather than fold it into a ``CutoverResult`` — that stays
    correct (a divergent-home mission must never silently flip). The walker
    built on top of it (``cutover_repo``) must catch that raise PER MISSION:
    "alpha" (sorted first) is injected with a mismatch while "beta" (sorted
    after) is a genuinely healthy mission — proving the walk still reaches
    beta AND the overall corpus result stays fail-closed (a non-``None``
    ``error`` is exactly the signal both the CLI's ``_cutover_failed`` and the
    upgrade migration's ``_mission_failed`` predicates key on for a non-zero
    outcome).
    """
    alpha = build_mission(tmp_path, slug="alpha")
    beta = build_mission(tmp_path, slug="beta")
    real_cutover_mission = rsc.cutover_mission
    mismatch_message = (
        "_flip_phase refuses to write status_phase for 'alpha': the placement "
        "port resolved its PRIMARY home elsewhere (fail-closed, FR-001)."
    )

    def _fake_cutover_mission(
        feature_dir: Path,
        *,
        status_feature_dir: Path | None = None,
        dry_run: bool = False,
    ) -> rsc.CutoverResult:
        if feature_dir.name == "alpha":
            raise rsc.PlacementMismatchError(mismatch_message)
        return real_cutover_mission(
            feature_dir, status_feature_dir=status_feature_dir, dry_run=dry_run
        )

    monkeypatch.setattr(rsc, "cutover_mission", _fake_cutover_mission)

    results = rsc.cutover_repo(tmp_path)

    assert sorted(r.slug for r in results) == ["alpha", "beta"]
    alpha_result = next(r for r in results if r.slug == "alpha")
    beta_result = next(r for r in results if r.slug == "beta")

    # alpha: fails closed, folded into a CutoverResult — never escapes the walk
    # as a raised exception.
    assert alpha_result.flipped is False
    assert alpha_result.error == mismatch_message
    assert _STATUS_PHASE not in json.loads((alpha / "meta.json").read_text())

    # beta sorts AFTER alpha but was still visited and flipped — the walk did
    # not abort at alpha (NFR-005-style containment for THIS error class too).
    assert beta_result.flipped is True
    assert json.loads((beta / "meta.json").read_text())[_STATUS_PHASE] == "1"

    # The corpus-level signal both consumers key on for a non-zero outcome.
    assert any(r.error is not None for r in results)


# ---------------------------------------------------------------------------
# Landing-fold finding 2 (P2) — degrade catch set aligned with coord_read_dir_for
# ---------------------------------------------------------------------------


def test_resolve_primary_home_or_degrade_absorbs_action_context_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``ActionContextError`` degrades exactly like the other resolver failures.

    ``mission_runtime.coord_read_dir_for`` — the structurally equivalent
    projection over the SAME resolver — already catches
    ``(StatusReadPathNotFound, MissionSelectorAmbiguous, ActionContextError)``.
    Before this fix, ``_resolve_primary_home_or_degrade`` caught a narrower set
    and let an ``ActionContextError`` escape as a hard abort, contradicting its
    own docstring ("a resolver failure ... must NOT abort the cutover,
    NFR-002").
    """
    import mission_runtime

    feature_dir = build_mission(tmp_path)
    # A real resolvable git root, so the function reaches
    # resolve_artifact_surface instead of degrading earlier on
    # WorkspaceRootNotFound.
    _init_bare_git_marker(tmp_path)

    def _raise_action_context_error(*_args: object, **_kwargs: object) -> object:
        raise mission_runtime.ActionContextError(
            "MISSION_CONTEXT_UNRESOLVED", "synthetic unresolvable action context"
        )

    monkeypatch.setattr(mission_runtime, "resolve_artifact_surface", _raise_action_context_error)

    assert rsc._resolve_primary_home_or_degrade(feature_dir) is None


def test_flip_phase_degrades_on_action_context_error_and_still_flips(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """End-to-end sibling: the ``ActionContextError`` degrade must not block the flip."""
    import mission_runtime

    feature_dir = build_mission(tmp_path)
    _init_bare_git_marker(tmp_path)
    rsc._seed_phase(feature_dir, dry_run=False)

    def _raise_action_context_error(*_args: object, **_kwargs: object) -> object:
        raise mission_runtime.ActionContextError(
            "MISSION_CONTEXT_UNRESOLVED", "synthetic unresolvable action context"
        )

    monkeypatch.setattr(mission_runtime, "resolve_artifact_surface", _raise_action_context_error)

    rsc._flip_phase(feature_dir)  # must not raise

    assert json.loads((feature_dir / "meta.json").read_text())[_STATUS_PHASE] == "1"
