"""#2650 (WP04) -- FR-005 ref half: read/write PRIMARY-ref unification.

Pre-unification, the read side (``implement_cores.py::resolve_precondition_ref``)
hard-coded the git-rev shorthand ``"HEAD"`` inline and the write side
(``implement.py::_commit_planning_artifacts_transaction``'s PRIMARY-group
commit destination) hard-coded the mission's ``planning_branch`` name inline
-- two independently-written literals that happen to agree only because a
real claim always runs from a checkout whose ``HEAD`` IS ``planning_branch``.
This module pins the fix: both sides now derive the PRIMARY-partition ref
from ONE cli-local, module-private expression --
``implement_cores.py::_commit_target_ref_for`` -- so they cannot silently diverge
(e.g. under a detached-HEAD or off-target-branch checkout).

C-008 (no net-new PUBLIC symbol): ``_commit_target_ref_for`` is `_`-prefixed,
module-private, and re-exported through the EXISTING ``implement.py`` shim
import block alongside the other implement_cores.py helpers -- no new public
API surface.

C-009 (no default-BRANCH fallback): an absent/empty ``planning_branch``
resolves to the LOCAL CHECKOUT (``"HEAD"``), never a hardcoded branch name
such as ``main`` -- pinned explicitly below.
"""

from __future__ import annotations

import inspect
import json
import subprocess
from pathlib import Path

import pytest

from specify_cli.coordination.planning_commit import PlanningPlacement

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]

_PLANNING_BRANCH = "mission/2650-wp04-ref-unification-demo"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True
    ).stdout.strip()


def _init_repo(repo: Path, *, branch: str) -> None:
    repo.mkdir()
    _git(repo, "init", "-q", "-b", branch)
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "seed.txt").write_text("seed\n", encoding="utf-8")
    _git(repo, "add", "seed.txt")
    _git(repo, "commit", "-q", "-m", "initial")


def _make_meta(
    feature_dir: Path,
    *,
    mission_id: str,
    mission_slug: str,
    target_branch: str,
) -> None:
    feature_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "mission_id": mission_id,
        "mission_slug": mission_slug,
        "mid8": mission_id[:8],
        "mission_type": "software-dev",
        "target_branch": target_branch,
        "created_at": "2026-07-15T00:00:00+00:00",
        "friendly_name": "WP04 ref-unification test",
    }
    (feature_dir / "meta.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")


class _FakeTxn:
    """Records the (destination_ref, [paths written]) of one ``acquire()`` call."""

    def __init__(self, destination_ref: str, calls: list[tuple[str, list[str]]]) -> None:
        self._destination_ref = destination_ref
        self._paths: list[str] = []
        self._calls = calls

    def __enter__(self) -> _FakeTxn:
        return self

    def __exit__(self, *_exc: object) -> None:
        self._calls.append((self._destination_ref, list(self._paths)))

    def write_artifact(self, repo_path: Path, _content: bytes) -> None:
        self._paths.append(repo_path.as_posix())

    def commit(self, _msg: str) -> None:
        return None

    def commit_idempotent(self, _msg: str) -> None:
        # write-path-integrity WP02 switched the production commit call from
        # ``txn.commit`` to ``txn.commit_idempotent`` (FR-001 crash-recovery
        # re-drive); the fake mirrors that so the write-side ref-derivation
        # characterization exercises the same seam (WP04 fold).
        return None


def _fake_bookkeeping_transaction(calls: list[tuple[str, list[str]]]) -> type:
    class _FakeBookkeepingTransaction:
        @classmethod
        def acquire(cls, **kwargs: object) -> _FakeTxn:
            return _FakeTxn(str(kwargs["destination_ref"]), calls)

    return _FakeBookkeepingTransaction


class TestPrimaryRefForExpression:
    """T019 -- the shared expression itself: pure, module-private, no
    default-BRANCH fallback."""

    def test_none_resolves_to_head(self) -> None:
        from specify_cli.cli.commands.implement_cores import _commit_target_ref_for

        assert _commit_target_ref_for(None) == "HEAD"

    def test_empty_string_resolves_to_head_not_a_default_branch(self) -> None:
        """C-009: an empty/falsy ``planning_branch`` is NOT coerced to a
        hardcoded default branch (``main``) -- it resolves to the local
        checkout, exactly like ``None``."""
        from specify_cli.cli.commands.implement_cores import _commit_target_ref_for

        assert _commit_target_ref_for("") == "HEAD"
        assert _commit_target_ref_for("") != "main"

    def test_named_branch_resolves_to_itself(self) -> None:
        from specify_cli.cli.commands.implement_cores import _commit_target_ref_for

        assert _commit_target_ref_for(_PLANNING_BRANCH) == _PLANNING_BRANCH

    def test_helper_is_module_private(self) -> None:
        """C-008: no net-new PUBLIC symbol -- ``_`` prefix, not re-exported
        under a public name from either module."""
        from specify_cli.cli.commands import implement, implement_cores

        assert not hasattr(implement_cores, "commit_target_ref_for")
        assert not hasattr(implement, "commit_target_ref_for")
        assert "_commit_target_ref_for" not in getattr(implement_cores, "__all__", [])
        assert "_commit_target_ref_for" not in getattr(implement, "__all__", [])


class TestReadSideDerivesFromTheSharedExpression:
    """T020 -- structural: no independent ``"HEAD"`` literal remains in the
    read path; it is now the ONE literal inside ``_commit_target_ref_for``."""

    def test_resolve_precondition_ref_has_no_inline_head_literal(self) -> None:
        from specify_cli.cli.commands.implement_cores import resolve_precondition_ref

        source = inspect.getsource(resolve_precondition_ref)
        # The docstring may still mention ``"HEAD"`` as prose; the CODE body
        # (after the closing docstring) must not restate the literal -- it
        # calls the shared expression instead.
        body = source.split('"""', 2)[-1]
        assert '"HEAD"' not in body, f"unexpected inline HEAD literal in resolve_precondition_ref body:\n{body}"
        assert "_commit_target_ref_for" in body

    def test_files_changed_vs_precondition_ref_has_no_inline_head_literal(self) -> None:
        from specify_cli.cli.commands.implement_cores import (
            _files_changed_vs_precondition_ref,
        )

        source = inspect.getsource(_files_changed_vs_precondition_ref)
        body = source.split('"""', 2)[-1]
        assert '"HEAD"' not in body, f"unexpected inline HEAD literal in _files_changed_vs_precondition_ref body:\n{body}"
        assert "_commit_target_ref_for" in body

    def test_resolve_precondition_ref_still_returns_head_for_primary_paths(self) -> None:
        """Behavior-preserving (NFR-001): the observable return value is
        byte-identical pre/post unification."""
        from specify_cli.cli.commands.implement_cores import resolve_precondition_ref

        coord_branch = "kitty/mission-m-AAAA1111"
        assert resolve_precondition_ref("kitty-specs/m/spec.md", coord_branch) == "HEAD"
        assert resolve_precondition_ref("kitty-specs/m/meta.json", coord_branch) == "HEAD"
        assert resolve_precondition_ref("kitty-specs/m/unknown-file.txt", coord_branch) == "HEAD"
        assert resolve_precondition_ref("kitty-specs/m/status.events.jsonl", coord_branch) == coord_branch


class TestWriteSideDerivesFromTheSharedExpression:
    """T020/T021 -- structural + behavioral: the write-side PRIMARY-group
    commit destination is no longer an independent inline ``planning_branch``
    reference -- it goes through ``_commit_target_ref_for`` too."""

    def test_commit_planning_artifacts_transaction_calls_the_shared_expression(self) -> None:
        from specify_cli.cli.commands.implement_planning_commit import _commit_planning_artifacts_transaction

        source = inspect.getsource(_commit_planning_artifacts_transaction)
        body = source.split('"""', 2)[-1]
        # Neither PRIMARY-group destination_ref assignment writes the bare
        # ``planning_branch`` variable directly any more -- both route
        # through ``_commit_target_ref_for(planning_branch)``.
        assert "destination_ref=planning_branch," not in body, (
            "a write-side call site still assigns destination_ref=planning_branch "
            "directly instead of _commit_target_ref_for(planning_branch)"
        )
        assert source.count("_commit_target_ref_for(planning_branch)") >= 2, (
            "expected BOTH the flat/legacy (755) and partition-split (790) "
            "PRIMARY-group call sites to route through _commit_target_ref_for"
        )

    def test_flat_legacy_commit_still_lands_on_planning_branch(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Behavior-preserving (NFR-001): a flat/legacy mission's single
        transaction still lands on ``planning_branch`` byte-identically."""
        from specify_cli.cli.commands.implement_planning_commit import _commit_planning_artifacts_transaction

        repo = tmp_path / "repo"
        _init_repo(repo, branch=_PLANNING_BRANCH)
        mission_slug = "wp04-flat-demo"
        mission_id = "01J9WP04FLATDEMOXXXXXXXXXX"
        feature_dir = repo / "kitty-specs" / mission_slug
        _make_meta(feature_dir, mission_id=mission_id, mission_slug=mission_slug, target_branch=_PLANNING_BRANCH)
        spec_md = feature_dir / "spec.md"
        spec_md.write_text("# Spec\n", encoding="utf-8")

        calls: list[tuple[str, list[str]]] = []
        monkeypatch.setattr(
            "specify_cli.coordination.transaction.BookkeepingTransaction",
            _fake_bookkeeping_transaction(calls),
        )
        spec_rel = f"kitty-specs/{mission_slug}/spec.md"

        _commit_planning_artifacts_transaction(
            repo_root=repo,
            feature_dir=feature_dir,
            mission_slug=mission_slug,
            planning_branch=_PLANNING_BRANCH,
            files_to_commit=[spec_rel],
            commit_msg="chore: planning artifacts for wp04-flat-demo",
            placement=PlanningPlacement(resolved=False, ref=None, coordination_ref=None),
        )

        assert calls == [(_PLANNING_BRANCH, [spec_rel])]


class TestDetachedHeadRegression:
    """T020 -- the named regression: a detached-HEAD (or off-target-branch)
    checkout must not risk read/write disagreement.

    Read-side idempotency compares stay local-checkout-relative (``"HEAD"``,
    unchanged) while the write-side commit destination is ALWAYS the
    explicitly-named ``planning_branch`` -- never derived from whatever is
    physically checked out. Pre-unification this was true only because the
    two literals were written independently and happened to match; post-
    unification it is guaranteed BY CONSTRUCTION because the write side
    always supplies a non-empty ``planning_branch`` argument to the one
    shared expression, which prioritises it over the ``"HEAD"`` default.
    """

    def test_write_side_targets_the_named_branch_even_when_head_is_detached(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from specify_cli.cli.commands.implement_planning_commit import _commit_planning_artifacts_transaction

        repo = tmp_path / "repo"
        _init_repo(repo, branch=_PLANNING_BRANCH)

        # Advance planning_branch with a second commit, then detach HEAD onto
        # the FIRST commit -- so the local checkout's "HEAD" no longer points
        # at planning_branch's tip.
        first_commit = _git(repo, "rev-parse", "HEAD")
        (repo / "seed2.txt").write_text("seed2\n", encoding="utf-8")
        _git(repo, "add", "seed2.txt")
        _git(repo, "commit", "-q", "-m", "advance planning_branch")
        _git(repo, "checkout", "-q", "--detach", first_commit)
        # Sanity: the checkout really is detached, not "on" planning_branch.
        head_branch = subprocess.run(
            ["git", "symbolic-ref", "-q", "--short", "HEAD"], cwd=repo, capture_output=True, text=True
        )
        assert head_branch.returncode != 0, "expected a detached HEAD (no symbolic ref)"

        mission_slug = "wp04-detached-demo"
        mission_id = "01J9WP04DETACHEDDEMOXXXXXX"
        feature_dir = repo / "kitty-specs" / mission_slug
        _make_meta(feature_dir, mission_id=mission_id, mission_slug=mission_slug, target_branch=_PLANNING_BRANCH)
        spec_md = feature_dir / "spec.md"
        spec_md.write_text("# Spec\ndetached-checkout edit\n", encoding="utf-8")

        calls: list[tuple[str, list[str]]] = []
        monkeypatch.setattr(
            "specify_cli.coordination.transaction.BookkeepingTransaction",
            _fake_bookkeeping_transaction(calls),
        )
        spec_rel = f"kitty-specs/{mission_slug}/spec.md"

        _commit_planning_artifacts_transaction(
            repo_root=repo,
            feature_dir=feature_dir,
            mission_slug=mission_slug,
            planning_branch=_PLANNING_BRANCH,
            files_to_commit=[spec_rel],
            commit_msg="chore: planning artifacts for wp04-detached-demo",
            placement=PlanningPlacement(resolved=False, ref=None, coordination_ref=None),
        )

        # Even with HEAD detached, the write-side destination is the named
        # planning_branch -- never the literal "HEAD" (which, detached,
        # names no branch at all and could never receive this commit).
        assert calls == [(_PLANNING_BRANCH, [spec_rel])]
        assert all(ref != "HEAD" for ref, _paths in calls)

    def test_commit_target_ref_for_prioritises_the_named_branch_over_ambient_checkout(self) -> None:
        """The shared expression itself never consults ambient git state --
        it is pure and argument-driven, which is WHY the write side cannot
        accidentally pick up a detached "HEAD" (T020's structural guarantee,
        independent of any particular git fixture)."""
        from specify_cli.cli.commands.implement_cores import _commit_target_ref_for

        assert _commit_target_ref_for(_PLANNING_BRANCH) == _PLANNING_BRANCH
        assert _commit_target_ref_for(_PLANNING_BRANCH) != "HEAD"


class TestVerbatimRefReadMatchesWriteSurface:
    """PR #2662 squad (paula LOW-1 / renata HIGH): the idempotency READ must
    compare against the SAME surface the WRITE lands on. On the healthy
    ``placement_ref is not None`` verbatim path the whole batch is committed to
    one ref, so ``verbatim_ref`` makes the filter compare EVERY file against
    that ref — a PRIMARY file already-identical on the write ref but differing
    from ``HEAD`` is dropped (not re-committed into an empty commit)."""

    def _seed_divergent_primary(self, tmp_path: Path) -> tuple[Path, str, str]:
        """spec.md == content A on branch ``write-surface`` and in the working
        tree, but == content B on HEAD. Returns (repo, spec_rel, write_ref)."""
        repo = tmp_path / "repo"
        _init_repo(repo, branch="main")
        spec = repo / "spec.md"
        spec.write_text("A\n", encoding="utf-8")
        _git(repo, "add", "spec.md")
        _git(repo, "commit", "-q", "-m", "spec=A")
        _git(repo, "branch", "write-surface")  # write-surface:spec.md == A
        spec.write_text("B\n", encoding="utf-8")
        _git(repo, "add", "spec.md")
        _git(repo, "commit", "-q", "-m", "spec=B (HEAD)")  # HEAD:spec.md == B
        spec.write_text("A\n", encoding="utf-8")  # working tree == A (== write-surface, != HEAD)
        return repo, "spec.md", "write-surface"

    def test_file_identical_on_write_ref_is_dropped_via_verbatim_ref(self, tmp_path: Path) -> None:
        from specify_cli.cli.commands.implement_cores import _files_changed_vs_precondition_ref

        repo, spec_rel, write_ref = self._seed_divergent_primary(tmp_path)

        # verbatim_ref = the write surface -> spec.md is identical there -> dropped.
        dropped = _files_changed_vs_precondition_ref(repo, [spec_rel], None, verbatim_ref=write_ref)
        assert dropped == [], "a file identical on the verbatim write ref must be dropped"

    def test_without_verbatim_ref_the_primary_vs_head_split_still_sees_it_changed(self, tmp_path: Path) -> None:
        from specify_cli.cli.commands.implement_cores import _files_changed_vs_precondition_ref

        repo, spec_rel, _write_ref = self._seed_divergent_primary(tmp_path)

        # No verbatim_ref -> PRIMARY compares vs HEAD (content B) -> "changed".
        # This is the divergence the verbatim path would turn into an empty commit.
        changed = _files_changed_vs_precondition_ref(repo, [spec_rel], None)
        assert changed == [spec_rel]
