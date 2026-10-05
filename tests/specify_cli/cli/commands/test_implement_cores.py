"""Unit tests for the WP03 (coord-authority-trio-degod-01KX7094) extraction of
``implement.py``'s git-porcelain/diff and placement decision cores into
``implement_cores.py``.

T020: exercises the pure decision logic directly, injecting a fake
:class:`~specify_cli.cli.commands.implement_cores.GitPort` so no real git
subprocess or repository is needed (the ``unit`` marker's contract). Real-git
integration coverage for the same functions (via the historical, git-param-free
signatures with a default port) already lives in
``tests/specify_cli/cli/commands/test_implement.py`` and
``tests/specify_cli/cli/commands/test_implement_vcs_lock_claim.py``.
"""

from __future__ import annotations

import os
import subprocess
from collections.abc import Sequence
from pathlib import Path

import pytest

from specify_cli.cli.commands.implement_cores import (
    DEFAULT_GIT_PORT,
    GitPort,
    _SubprocessGitPort,
    PlanningArtifactStagingPlan,
    _committed_meta_mapping,
    _drop_if,
    _feature_dir_status_entries,
    _files_changed_vs_ref,
    _is_self_write_only_diff,
    _parse_porcelain_entries,
    _PorcelainEntry,
    _status_paths_for_commit,
    detect_structural_planning_changes,
    resolve_planning_artifact_staging,
    resolve_precondition_ref,
)
from kernel.meta_decode import MetaDecodeError, decode_meta
from kernel.vcs_lock import is_vcs_lock_only_change
from specify_cli.coordination.coherence import is_status_state_path
from kernel.git import GitPath, StatusEntry

pytestmark = [pytest.mark.unit]


def _entry(xy: str, path: str, *, orig: str | None = None) -> StatusEntry:
    """Build a typed status entry directly (no porcelain text is parsed in this file)."""
    return StatusEntry(xy=xy, path=GitPath.parse(path), orig_path=GitPath.parse(orig) if orig else None)


class _FakeGitPort:
    """In-memory :class:`GitPort` -- no subprocess, no real repository."""

    def __init__(
        self,
        *,
        entries: tuple[StatusEntry, ...] = (),
        blobs: dict[tuple[str, str], bytes | None] | None = None,
    ) -> None:
        self._entries = entries
        self._blobs = blobs or {}
        self.status_calls: list[tuple[Path, Path]] = []
        self.show_calls: list[tuple[Path, str, str]] = []
        self.changed_calls: list[tuple[str, tuple[str, ...]]] = []

    def status_entries(self, repo_root: Path, target: Path) -> tuple[StatusEntry, ...]:
        self.status_calls.append((repo_root, target))
        return self._entries

    def show_blob(self, repo_root: Path, ref: str, repo_rel_path: str) -> bytes | None:
        self.show_calls.append((repo_root, ref, repo_rel_path))
        return self._blobs.get((ref, repo_rel_path))

    def changed_vs_ref(self, repo_root: Path, ref: str, repo_rel_paths: Sequence[str]) -> set[str]:
        """Raw-bytes stand-in for Git's clean-filtered object-id comparison."""
        self.changed_calls.append((ref, tuple(repo_rel_paths)))
        return {p for p in repo_rel_paths if self._blobs.get((ref, p)) != (repo_root / p).read_bytes()}


def test_default_git_port_conforms_to_protocol() -> None:
    """The concrete default port satisfies the GitPort structural protocol."""
    assert isinstance(DEFAULT_GIT_PORT, GitPort)


class TestDetectStructuralPlanningChanges:
    """Squad-B1 (#2464): the git-executor fires the #1598 fail-closed guard via
    this coord-independent detector BEFORE resolving the coordination filter, so
    a topology fault never preempts the structural-refusal message."""

    def test_deletion_and_rename_are_reported(self) -> None:
        fake = _FakeGitPort(entries=(_entry(" D", "kitty-specs/m/tasks/WP01.md"), _entry("R ", "kitty-specs/m/tasks/WP02.md", orig="a.md"), ))
        structural = detect_structural_planning_changes(Path("/repo"), Path("kitty-specs/m"), git=fake)
        assert [e.is_structural for e in structural] == [True, True]
        assert {e.path for e in structural} == {
            "kitty-specs/m/tasks/WP01.md",
            "kitty-specs/m/tasks/WP02.md",
        }

    def test_modified_and_untracked_are_not_structural(self) -> None:
        fake = _FakeGitPort(entries=(_entry(" M", "kitty-specs/m/status.json"), _entry("??", "kitty-specs/m/new.md"), ))
        assert detect_structural_planning_changes(Path("/repo"), Path("kitty-specs/m"), git=fake) == []

    def test_reads_only_git_status_not_the_coordination_filter(self) -> None:
        """The detector's git surface is a single ``status`` call -- it never
        resolves coord/topology, which is what can raise (the ordering fix)."""
        fake = _FakeGitPort(entries=())
        detect_structural_planning_changes(Path("/repo"), Path("kitty-specs/m"), git=fake)
        assert len(fake.status_calls) == 1
        assert fake.show_calls == []


# ---------------------------------------------------------------------------
# _parse_porcelain_entries / _feature_dir_status_entries
# ---------------------------------------------------------------------------


class TestParsePorcelainEntries:
    def test_modified_unstaged_tracked_file_keeps_full_path(self) -> None:
        """A leading-space status code (" M path") keeps its exact path and XY."""
        entries = _parse_porcelain_entries((_entry(" M", "kitty-specs/demo/status.json"), ))
        assert entries == [_PorcelainEntry(xy=" M", path="kitty-specs/demo/status.json", is_structural=False)]

    def test_untracked_file_is_not_structural(self) -> None:
        entries = _parse_porcelain_entries((_entry("??", "kitty-specs/demo/new.md"), ))
        assert entries == [_PorcelainEntry(xy="??", path="kitty-specs/demo/new.md", is_structural=False)]

    def test_deleted_file_is_structural(self) -> None:
        entries = _parse_porcelain_entries((_entry(" D", "kitty-specs/demo/tasks/WP01.md"), ))
        assert entries[0].is_structural is True

    def test_rename_uses_new_path_and_is_structural(self) -> None:
        entries = _parse_porcelain_entries((_entry("R ", "kitty-specs/demo/tasks/WP01-renamed.md", orig="kitty-specs/demo/tasks/WP01.md"), ))
        assert entries == [_PorcelainEntry(xy="R ", path="kitty-specs/demo/tasks/WP01-renamed.md", is_structural=True)]

    def test_empty_status_yields_no_entries(self) -> None:
        assert _parse_porcelain_entries(()) == []

    def test_multiple_lines(self) -> None:
        entries = _parse_porcelain_entries(
            (
                _entry(" M", "kitty-specs/demo/status.json"),
                _entry(" D", "kitty-specs/demo/tasks/WP01.md"),
                _entry("??", "kitty-specs/demo/new.md"),
            )
        )
        assert [e.path for e in entries] == [
            "kitty-specs/demo/status.json",
            "kitty-specs/demo/tasks/WP01.md",
            "kitty-specs/demo/new.md",
        ]
        assert [e.is_structural for e in entries] == [False, True, False]


class TestFeatureDirStatusEntries:
    def test_delegates_to_injected_git_port(self, tmp_path: Path) -> None:
        fake = _FakeGitPort(entries=(_entry(" M", "kitty-specs/demo/status.json"), ))
        feature_dir = tmp_path / "kitty-specs" / "demo"
        entries = _feature_dir_status_entries(tmp_path, feature_dir, git=fake)
        assert entries == [_PorcelainEntry(xy=" M", path="kitty-specs/demo/status.json", is_structural=False)]
        assert fake.status_calls == [(tmp_path, feature_dir)]

    def test_default_git_param_is_the_module_default(self, tmp_path: Path) -> None:
        """Backward-compat: the historical 2-positional-arg call (no ``git``
        kwarg) must still resolve -- against a real (empty) status read,
        not raise."""
        subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
        feature_dir = tmp_path / "kitty-specs" / "demo"
        feature_dir.mkdir(parents=True)
        entries = _feature_dir_status_entries(tmp_path, feature_dir)
        assert entries == []

    def test_dossier_snapshot_churn_is_dropped(self) -> None:
        """FIX-M2-08: a live-dirty dossier snapshot (D1 EXCLUDE policy --
        ``contracts/dossier-snapshot-ownership.md``: "No staging, no
        committing... The file is just a file") must never surface as a
        status entry -- neither ``_structural_entries`` /
        ``detect_structural_planning_changes`` nor ``_status_paths_for_commit``
        (via ``resolve_planning_artifact_staging``) may treat a fire-and-
        forget dossier-sync re-save as something that blocks the
        implement-claim precheck. Mirrors the SAME glob ``agent tasks
        move-task``'s own preflight already strips
        (``tasks_shared.py::_strip_runtime_state_lines``,
        ``tasks_parsing_validation.py``)."""
        fake = _FakeGitPort(
            entries=(_entry(" M", "kitty-specs/m/.kittify/dossiers/m/snapshot-latest.json"), _entry(" M", "kitty-specs/m/tasks.md"), )
        )
        entries = _feature_dir_status_entries(Path("/repo"), Path("/repo/kitty-specs/m"), git=fake)
        assert entries == [_PorcelainEntry(xy=" M", path="kitty-specs/m/tasks.md", is_structural=False)]

    def test_deleted_dossier_snapshot_is_not_structural_either(self) -> None:
        """A deleted dossier snapshot must not trip the #1598 structural
        fail-closed guard -- it is "just a file", not a planning artifact
        whose loss the coordination branch needs to reconcile."""
        fake = _FakeGitPort(entries=(_entry(" D", "kitty-specs/m/.kittify/dossiers/m/snapshot-latest.json"), ))
        entries = _feature_dir_status_entries(Path("/repo"), Path("/repo/kitty-specs/m"), git=fake)
        assert entries == []


# ---------------------------------------------------------------------------
# _drop_if (WP14 / IC-07d generic filter)
# ---------------------------------------------------------------------------


class TestDropIf:
    """The ONE generic claim-time exclusion filter every retired sibling
    (``_drop_vcs_lock_only_meta`` / ``_drop_runtime_frontmatter_only_wp`` +
    its ``_is_wp_filename`` twin / ``_exclude_coord_owned``) now routes
    through -- see :class:`TestStatusPathsForCommit` and
    :class:`TestIsSelfWriteOnlyDiff` for the migrated predicate-level
    coverage."""

    def test_keeps_every_path_when_predicate_never_matches(self) -> None:
        paths = ["a.md", "b.md"]
        assert _drop_if(paths, lambda _p: False) == paths

    def test_drops_every_path_when_predicate_always_matches(self) -> None:
        assert _drop_if(["a.md", "b.md"], lambda _p: True) == []

    def test_drops_only_the_paths_the_predicate_flags(self) -> None:
        kept = _drop_if(["a.md", "b.md", "c.md"], lambda p: p == "b.md")
        assert kept == ["a.md", "c.md"]

    def test_preserves_input_order(self) -> None:
        kept = _drop_if(["z.md", "a.md", "m.md"], lambda _p: False)
        assert kept == ["z.md", "a.md", "m.md"]


# ---------------------------------------------------------------------------
# _status_paths_for_commit (retired ``_exclude_coord_owned`` onto _drop_if +
# the owner-exposed ``is_status_state_path`` leg, WP14 / IC-07d)
# ---------------------------------------------------------------------------


class TestStatusPathsForCommit:
    def test_no_coord_branch_keeps_all_paths(self) -> None:
        entries = [
            _PorcelainEntry(xy=" M", path="kitty-specs/m/status.json", is_structural=False),
            _PorcelainEntry(xy=" M", path="kitty-specs/m/tasks.md", is_structural=False),
        ]
        assert set(_status_paths_for_commit(entries, None)) == {
            "kitty-specs/m/status.json",
            "kitty-specs/m/tasks.md",
        }

    def test_coord_branch_drops_status_files_only(self) -> None:
        entries = [
            _PorcelainEntry(xy=" M", path="kitty-specs/m/status.events.jsonl", is_structural=False),
            _PorcelainEntry(xy=" M", path="kitty-specs/m/status.json", is_structural=False),
            _PorcelainEntry(xy=" M", path="kitty-specs/m/tasks.md", is_structural=False),
        ]
        kept = _status_paths_for_commit(entries, "kitty/mission-m-AAAA1111")
        assert kept == ["kitty-specs/m/tasks.md"]

    def test_routes_through_drop_if_and_the_owner_status_state_leg(self) -> None:
        """The narrow ``is_status_state_path`` leg (not the broader
        ``is_coord_residue_churn``/``is_toolchain_generated_churn`` union) is
        the predicate consulted -- a coord-residue-but-non-status kind
        (``issue-matrix.md``) survives the drop."""
        entries = [
            _PorcelainEntry(xy=" M", path="kitty-specs/m/issue-matrix.md", is_structural=False),
            _PorcelainEntry(xy=" M", path="kitty-specs/m/status.json", is_structural=False),
        ]
        assert _status_paths_for_commit(entries, "kitty/mission-m-AAAA1111") == ["kitty-specs/m/issue-matrix.md"]
        assert _drop_if(
            [e.path for e in entries], is_status_state_path
        ) == ["kitty-specs/m/issue-matrix.md"]


# ---------------------------------------------------------------------------
# vcs-lock-only meta.json diff family
# ---------------------------------------------------------------------------


class TestIsVcsLockOnlyMetaDiff:
    """WP03 / T016: the retired ``implement_cores._is_vcs_lock_only_meta_diff``
    comparator is routed onto the single canonical
    :func:`kernel.vcs_lock.is_vcs_lock_only_change` (FR-006). The kernel adopts
    the sentinel (absent != present-but-null) semantics; it also returns
    ``True`` on an EMPTY diff (two identical mappings -- the empty set of
    differences is trivially a subset of the lock fields), unlike the retired
    predicate's ``bool(changed_keys) and ...`` shape."""

    @pytest.mark.parametrize(
        ("committed", "working", "expected"),
        [
            (None, {}, True),
            ({}, {}, True),
            ({"vcs": "git"}, {"vcs": "git", "vcs_locked_at": "t0"}, True),
            ({"friendly_name": "a"}, {"friendly_name": "b"}, False),
            (
                {"friendly_name": "a", "vcs": "git"},
                {"friendly_name": "a", "vcs_locked_at": "t0", "vcs": "git"},
                True,
            ),
            (
                {"friendly_name": "a"},
                {"friendly_name": "b", "vcs": "git"},
                False,
            ),
        ],
    )
    def test_truth_table(self, committed: dict[str, str] | None, working: dict[str, str], expected: bool) -> None:
        assert is_vcs_lock_only_change(committed, working) is expected


class TestDecodeMetaRouting:
    """WP03 / T016: the retired ``implement_cores._parse_meta_mapping`` blob
    parser is routed onto the kernel L1 :func:`kernel.meta_decode.decode_meta`
    authority (FR-003). Malformed content now fails loud (``on_malformed=
    "raise"``) instead of the former silent ``None`` -- the ``"none"`` policy
        preserves a caller that deliberately wants the absorbed sentinel."""

    def test_valid_object(self) -> None:
        assert decode_meta(b'{"vcs": "git"}') == {"vcs": "git"}

    def test_non_object_json_raises(self) -> None:
        with pytest.raises(MetaDecodeError):
            decode_meta(b"[1, 2, 3]")
        assert decode_meta(b"[1, 2, 3]", on_malformed="none") is None

    def test_invalid_json_raises(self) -> None:
        with pytest.raises(MetaDecodeError):
            decode_meta(b"not json")
        assert decode_meta(b"not json", on_malformed="none") is None

    def test_bad_encoding_raises(self) -> None:
        with pytest.raises(MetaDecodeError):
            decode_meta(b"\xff\xfe\x00")
        assert decode_meta(b"\xff\xfe\x00", on_malformed="none") is None


class TestCommittedMetaMapping:
    def test_absent_blob_returns_none(self, tmp_path: Path) -> None:
        fake = _FakeGitPort(blobs={})
        assert _committed_meta_mapping(tmp_path, "kitty-specs/m/meta.json", "HEAD", git=fake) is None

    def test_present_blob_parsed(self, tmp_path: Path) -> None:
        fake = _FakeGitPort(blobs={("HEAD", "kitty-specs/m/meta.json"): b'{"vcs": "git"}'})
        result = _committed_meta_mapping(tmp_path, "kitty-specs/m/meta.json", None, git=fake)
        assert result == {"vcs": "git"}

    def test_ref_none_defaults_to_head(self, tmp_path: Path) -> None:
        fake = _FakeGitPort(blobs={("HEAD", "p"): b"{}"})
        _committed_meta_mapping(tmp_path, "p", None, git=fake)
        assert fake.show_calls == [(tmp_path, "HEAD", "p")]


class TestIsSelfWriteOnlyDiff:
    """WP14 / IC-07d: the merged predicate behind the retired
    ``_drop_vcs_lock_only_meta`` / ``_drop_runtime_frontmatter_only_wp``
    twins, consumed via :func:`_drop_if`. The ``auto_commit`` gate is now the
    CALLER's responsibility (:func:`resolve_planning_artifact_staging`
    applies :func:`_drop_if` only when ``not auto_commit`` -- see
    ``TestResolvePlanningArtifactStaging`` / ``test_implement_vcs_lock_claim.py``
    / ``test_implement_runtime_frontmatter_claim.py`` for that NFR-001
    no-op-under-auto_commit=True coverage), so this predicate is exercised
    directly, unconditionally.
    """

    def _meta_repo(self, tmp_path: Path, *, working: bytes) -> tuple[Path, str]:
        meta_rel = "kitty-specs/m/meta.json"
        meta_path = tmp_path / meta_rel
        meta_path.parent.mkdir(parents=True)
        meta_path.write_bytes(working)
        return tmp_path, meta_rel

    def test_drops_lock_only_meta_diff(self, tmp_path: Path) -> None:
        repo_root, meta_rel = self._meta_repo(
            tmp_path,
            working=b'{"friendly_name": "a", "vcs": "git", "vcs_locked_at": "t0"}',
        )
        fake = _FakeGitPort(blobs={("HEAD", meta_rel): b'{"friendly_name": "a"}'})
        assert _is_self_write_only_diff(repo_root, meta_rel, None, git=fake) is True
        assert _drop_if([meta_rel], lambda p: _is_self_write_only_diff(repo_root, p, None, git=fake)) == []

    def test_keeps_non_lock_meta_diff(self, tmp_path: Path) -> None:
        repo_root, meta_rel = self._meta_repo(
            tmp_path,
            working=b'{"friendly_name": "b"}',
        )
        fake = _FakeGitPort(blobs={("HEAD", meta_rel): b'{"friendly_name": "a"}'})
        assert _is_self_write_only_diff(repo_root, meta_rel, None, git=fake) is False
        assert _drop_if([meta_rel], lambda p: _is_self_write_only_diff(repo_root, p, None, git=fake)) == [meta_rel]

    def test_keeps_non_meta_non_wp_paths_untouched(self, tmp_path: Path) -> None:
        assert _is_self_write_only_diff(tmp_path, "kitty-specs/m/tasks.md", None, git=_FakeGitPort()) is False

    def test_missing_meta_source_is_not_dropped_defensively(self, tmp_path: Path) -> None:
        assert _is_self_write_only_diff(tmp_path, "kitty-specs/m/meta.json", None, git=_FakeGitPort()) is False

    def test_drops_runtime_frontmatter_only_wp_diff(self, tmp_path: Path) -> None:
        wp_rel = "kitty-specs/m/tasks/WP01.md"
        wp_path = tmp_path / wp_rel
        wp_path.parent.mkdir(parents=True)
        wp_path.write_text(
            "---\nwork_package_id: WP01\nshell_pid: 4242\n---\n# WP01\nbody\n",
            encoding="utf-8",
        )
        committed = b"---\nwork_package_id: WP01\n---\n# WP01\nbody\n"
        fake = _FakeGitPort(blobs={("HEAD", wp_rel): committed})
        assert _is_self_write_only_diff(tmp_path, wp_rel, None, git=fake) is True

    def test_keeps_wp_diff_with_a_non_runtime_frontmatter_key_change(self, tmp_path: Path) -> None:
        wp_rel = "kitty-specs/m/tasks/WP01.md"
        wp_path = tmp_path / wp_rel
        wp_path.parent.mkdir(parents=True)
        wp_path.write_text(
            "---\nwork_package_id: WP01\ntitle: renamed\n---\n# WP01\nbody\n",
            encoding="utf-8",
        )
        committed = b"---\nwork_package_id: WP01\ntitle: original\n---\n# WP01\nbody\n"
        fake = _FakeGitPort(blobs={("HEAD", wp_rel): committed})
        assert _is_self_write_only_diff(tmp_path, wp_rel, None, git=fake) is False

    def test_keeps_wp_diff_with_a_body_change(self, tmp_path: Path) -> None:
        wp_rel = "kitty-specs/m/tasks/WP01.md"
        wp_path = tmp_path / wp_rel
        wp_path.parent.mkdir(parents=True)
        wp_path.write_text(
            "---\nwork_package_id: WP01\nshell_pid: 4242\n---\n# WP01\nnew body\n",
            encoding="utf-8",
        )
        committed = b"---\nwork_package_id: WP01\n---\n# WP01\nold body\n"
        fake = _FakeGitPort(blobs={("HEAD", wp_rel): committed})
        assert _is_self_write_only_diff(tmp_path, wp_rel, None, git=fake) is False

    def _crlf_wp(self, tmp_path: Path, working: bytes) -> str:
        wp_rel = "kitty-specs/m/tasks/WP01.md"
        wp_path = tmp_path / wp_rel
        wp_path.parent.mkdir(parents=True)
        wp_path.write_bytes(working)
        return wp_rel

    def test_drops_crlf_checkout_of_runtime_frontmatter_only_wp_diff(self, tmp_path: Path) -> None:
        """#5576: an autocrlf checkout (CRLF working file, LF blob) whose only change is runtime frontmatter is clean."""
        wp_rel = self._crlf_wp(
            tmp_path,
            b"---\r\nwork_package_id: WP01\r\nshell_pid: 4242\r\n---\r\n\r\n# WP01\r\nbody\r\nmore\r\n",
        )
        committed = b"---\nwork_package_id: WP01\n---\n\n# WP01\nbody\nmore\n"
        fake = _FakeGitPort(blobs={("HEAD", wp_rel): committed})
        assert _is_self_write_only_diff(tmp_path, wp_rel, None, git=fake) is True

    def test_drops_lf_checkout_of_crlf_committed_runtime_frontmatter_only_wp_diff(self, tmp_path: Path) -> None:
        wp_rel = self._crlf_wp(tmp_path, b"---\nwork_package_id: WP01\nshell_pid: 1\n---\n# WP01\nbody\n")
        committed = b"---\r\nwork_package_id: WP01\r\n---\r\n# WP01\r\nbody\r\n"
        fake = _FakeGitPort(blobs={("HEAD", wp_rel): committed})
        assert _is_self_write_only_diff(tmp_path, wp_rel, None, git=fake) is True

    def test_keeps_crlf_checkout_wp_diff_with_a_real_body_edit(self, tmp_path: Path) -> None:
        wp_rel = self._crlf_wp(
            tmp_path,
            b"---\r\nwork_package_id: WP01\r\nshell_pid: 4242\r\n---\r\n# WP01\r\nnew body\r\n",
        )
        committed = b"---\nwork_package_id: WP01\n---\n# WP01\nold body\n"
        fake = _FakeGitPort(blobs={("HEAD", wp_rel): committed})
        assert _is_self_write_only_diff(tmp_path, wp_rel, None, git=fake) is False

    def test_missing_wp_source_is_not_dropped_defensively(self, tmp_path: Path) -> None:
        assert _is_self_write_only_diff(tmp_path, "kitty-specs/m/tasks/WP01.md", None, git=_FakeGitPort()) is False

    def test_missing_committed_blob_is_not_dropped_defensively(self, tmp_path: Path) -> None:
        wp_rel = "kitty-specs/m/tasks/WP02.md"
        wp_path = tmp_path / wp_rel
        wp_path.parent.mkdir(parents=True)
        wp_path.write_text("---\nwork_package_id: WP02\n---\n# WP02\n", encoding="utf-8")
        assert _is_self_write_only_diff(tmp_path, wp_rel, None, git=_FakeGitPort()) is False


class TestResolvePreconditionRef:
    """T001/T002 -- contracts/resolve-precondition-ref.md is authoritative.

    Single owner of the "compare-against-which-ref" decision, resolved PER
    FILE PATH (not once per staging call): on a coord mission
    ``coord_branch_for_filter`` is a single non-``None`` branch for every
    candidate; only the path distinguishes a PRIMARY ``spec.md`` from a COORD
    ``status.events.jsonl``.
    """

    _COORD_BRANCH = "kitty/mission-m-AAAA1111"

    def test_primary_kind_resolves_to_head(self) -> None:
        assert resolve_precondition_ref("kitty-specs/m/spec.md", self._COORD_BRANCH) == "HEAD"

    def test_meta_json_resolves_to_head_even_on_coord_mission(self) -> None:
        """BLOCKER-2 lock: ``meta.json`` is a PRIMARY-partition kind
        (``kind_for_mission_file`` cannot classify it -- routing it through
        that None-returning lookup would misroute it to coord and
        reintroduce #2533). This is the exact file
        ``_committed_meta_mapping`` exists for."""
        assert resolve_precondition_ref("kitty-specs/m/meta.json", self._COORD_BRANCH) == "HEAD"

    def test_coord_residue_kind_resolves_to_coord_branch(self) -> None:
        assert resolve_precondition_ref("kitty-specs/m/status.events.jsonl", self._COORD_BRANCH) == self._COORD_BRANCH

    def test_no_coord_branch_resolves_to_head_even_for_coord_kind(self) -> None:
        """A flattened/non-coord mission (``coord_branch_for_filter is None``)
        never routes to coord, even for an otherwise-coord-residue path."""
        assert resolve_precondition_ref("kitty-specs/m/spec.md", None) == "HEAD"

    def test_no_coord_branch_resolves_status_events_to_head_too(self) -> None:
        assert resolve_precondition_ref("kitty-specs/m/status.events.jsonl", None) == "HEAD"

    def test_unknown_path_defaults_to_head(self) -> None:
        """Fail-safe direction (NFR-004): an unrecognized path is never routed
        to coord -- everything not explicitly coord-residue defaults primary."""
        assert resolve_precondition_ref("kitty-specs/m/unknown-file.txt", self._COORD_BRANCH) == "HEAD"


class TestFilesChangedVsRef:
    def test_no_ref_returns_all_files(self, tmp_path: Path) -> None:
        files = ["a.txt", "b.txt"]
        assert _files_changed_vs_ref(tmp_path, files, None, git=_FakeGitPort()) == files

    def test_missing_source_file_is_skipped(self, tmp_path: Path) -> None:
        assert _files_changed_vs_ref(tmp_path, ["absent.txt"], "HEAD", git=_FakeGitPort()) == []

    def test_identical_content_is_dropped(self, tmp_path: Path) -> None:
        (tmp_path / "a.txt").write_bytes(b"same")
        fake = _FakeGitPort(blobs={("HEAD", "a.txt"): b"same"})
        assert _files_changed_vs_ref(tmp_path, ["a.txt"], "HEAD", git=fake) == []

    def test_differing_content_is_kept(self, tmp_path: Path) -> None:
        (tmp_path / "a.txt").write_bytes(b"new")
        fake = _FakeGitPort(blobs={("HEAD", "a.txt"): b"old"})
        assert _files_changed_vs_ref(tmp_path, ["a.txt"], "HEAD", git=fake) == ["a.txt"]

    def test_port_sees_only_existing_paths_in_one_batch_and_input_order_is_kept(self, tmp_path: Path) -> None:
        for name in ("b.txt", "a.txt"):
            (tmp_path / name).write_bytes(b"new")
        fake = _FakeGitPort(blobs={("HEAD", "a.txt"): b"old", ("HEAD", "b.txt"): b"old"})
        assert _files_changed_vs_ref(tmp_path, ["b.txt", "gone.txt", "a.txt"], "HEAD", git=fake) == ["b.txt", "a.txt"]
        assert fake.changed_calls == [("HEAD", ("b.txt", "a.txt"))]


def _real_repo(tmp_path: Path, *, attributes: str | None = None) -> Path:
    """A tiny real repository with one committed file ``d/a.txt`` (LF blob)."""
    repo = tmp_path / "repo"
    (repo / "d").mkdir(parents=True)

    def git(*args: str) -> None:
        subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)

    git("init", "-q", "-b", "main")
    git("config", "user.email", "t@example.com")
    git("config", "user.name", "Test")
    git("config", "commit.gpgsign", "false")
    git("config", "core.autocrlf", "false")
    if attributes is not None:
        (repo / ".gitattributes").write_text(attributes, encoding="utf-8")
    (repo / "d" / "a.txt").write_bytes(b"one\ntwo\n")
    git("add", "-A")
    git("commit", "-q", "-m", "seed")
    return repo


class TestSubprocessGitPortChangedVsRef:
    """Real-git adapter coverage: Git's clean view decides, and failures fail closed."""

    _PORT = _SubprocessGitPort()

    def test_crlf_checkout_of_an_unchanged_file_is_not_changed(self, tmp_path: Path) -> None:
        repo = _real_repo(tmp_path, attributes="* text=auto eol=crlf\n")
        (repo / "d" / "a.txt").write_bytes(b"one\r\ntwo\r\n")
        assert self._PORT.changed_vs_ref(repo, "HEAD", ["d/a.txt"]) == set()

    def test_real_edit_saved_with_crlf_is_changed(self, tmp_path: Path) -> None:
        repo = _real_repo(tmp_path, attributes="* text=auto eol=crlf\n")
        (repo / "d" / "a.txt").write_bytes(b"one\r\nTWO\r\n")
        assert self._PORT.changed_vs_ref(repo, "HEAD", ["d/a.txt"]) == {"d/a.txt"}

    def test_hung_hash_object_times_out_and_fails_closed(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """#5576: a hung clean filter (e.g. an LFS credential prompt) must not block implement forever."""
        repo = _real_repo(tmp_path)
        seen: list[object] = []

        def fake_run(cmd: Sequence[str], *args: object, **kwargs: object) -> subprocess.CompletedProcess[bytes]:
            if "hash-object" in cmd:
                seen.append(kwargs.get("timeout"))
            raise subprocess.TimeoutExpired(cmd, 1)

        monkeypatch.setattr("specify_cli.cli.commands.implement_cores.subprocess.run", fake_run)
        assert self._PORT.changed_vs_ref(repo, "HEAD", ["d/a.txt"]) == {"d/a.txt"}
        assert seen
        assert all(isinstance(value, (int, float)) and value > 0 for value in seen)

    def test_without_conversion_raw_difference_is_changed(self, tmp_path: Path) -> None:
        repo = _real_repo(tmp_path)
        (repo / "d" / "a.txt").write_bytes(b"one\r\ntwo\r\n")
        assert self._PORT.changed_vs_ref(repo, "HEAD", ["d/a.txt"]) == {"d/a.txt"}

    def test_batch_reports_only_the_changed_subset_and_absent_paths(self, tmp_path: Path) -> None:
        repo = _real_repo(tmp_path)
        (repo / "d" / "new.txt").write_bytes(b"not at the ref\n")
        (repo / "d" / "b.txt").write_bytes(b"two\n")
        (repo / "d" / "a.txt").write_bytes(b"one\ntwo\nthree\n")
        paths = ["d/b.txt", "d/a.txt", "d/new.txt"]
        assert self._PORT.changed_vs_ref(repo, "HEAD", paths) == {"d/b.txt", "d/a.txt", "d/new.txt"}
        (repo / "d" / "a.txt").write_bytes(b"one\ntwo\n")
        assert self._PORT.changed_vs_ref(repo, "HEAD", paths) == {"d/b.txt", "d/new.txt"}

    def test_bogus_ref_marks_every_path_changed(self, tmp_path: Path) -> None:
        repo = _real_repo(tmp_path)
        assert self._PORT.changed_vs_ref(repo, "no-such-ref", ["d/a.txt"]) == {"d/a.txt"}

    def test_unprovable_paths_fail_closed_without_aborting_the_batch(self, tmp_path: Path) -> None:
        repo = _real_repo(tmp_path)
        (repo / "d" / "target.txt").write_bytes(b"x\n")
        try:
            (repo / "d" / "link.txt").symlink_to("target.txt")
        except OSError:
            pytest.skip("symlinks unavailable on this platform")
        paths = ["d/a.txt", "d/missing.txt", "d/line\nbreak.txt", 'd/"quoted.txt', "d/link.txt"]
        expected = {"d/missing.txt", "d/line\nbreak.txt", 'd/"quoted.txt', "d/link.txt"}
        assert self._PORT.changed_vs_ref(repo, "HEAD", paths) == expected

    def test_non_utf8_filename_is_hashed_not_raised(self, tmp_path: Path) -> None:
        if os.name == "nt":
            pytest.skip("POSIX byte filenames only")
        repo = _real_repo(tmp_path)
        name = os.fsdecode(b"d/caf\xe9.txt")
        try:
            (repo / name).write_bytes(b"one\ntwo\n")
        except (OSError, UnicodeEncodeError):
            pytest.skip("filesystem rejects non-UTF-8 names")
        assert self._PORT.changed_vs_ref(repo, "HEAD", [name, "d/a.txt"]) == {name}

    def test_long_path_lists_are_chunked(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        import specify_cli.cli.commands.implement_cores as cores

        monkeypatch.setattr(cores, "_LS_TREE_CHUNK", 2)
        repo = _real_repo(tmp_path)
        for i in range(5):
            (repo / "d" / f"n{i}.txt").write_bytes(b"x\n")
        paths = ["d/a.txt", *[f"d/n{i}.txt" for i in range(5)]]
        assert self._PORT.changed_vs_ref(repo, "HEAD", paths) == set(paths[1:])

    def test_git_unavailable_marks_every_path_changed(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        repo = _real_repo(tmp_path)

        def boom(*_args: object, **_kwargs: object) -> None:
            raise OSError("git not found")

        monkeypatch.setattr(subprocess, "run", boom)
        assert self._PORT.changed_vs_ref(repo, "HEAD", ["d/a.txt"]) == {"d/a.txt"}

    def test_unparseable_ls_tree_output_fails_closed(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        import specify_cli.cli.commands.implement_cores as cores
        from kernel.git.listing import parse_tree_z

        repo = _real_repo(tmp_path)
        monkeypatch.setattr(cores, "tree_entries", lambda *_a, **_k: parse_tree_z(b"garbage\0"))
        assert self._PORT.changed_vs_ref(repo, "HEAD", ["d/a.txt"]) == {"d/a.txt"}

    def test_ls_tree_git_failure_fails_closed(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        import specify_cli.cli.commands.implement_cores as cores
        from kernel.git import GitCommandError

        def boom(*_a: object, **_k: object) -> None:
            raise GitCommandError(argv=["ls-tree"], cwd=tmp_path, returncode=128, stderr="fatal")

        repo = _real_repo(tmp_path)
        monkeypatch.setattr(cores, "tree_entries", boom)
        assert self._PORT.changed_vs_ref(repo, "HEAD", ["d/a.txt"]) == {"d/a.txt"}

    def test_hash_output_that_does_not_pair_with_input_fails_closed(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        repo = _real_repo(tmp_path)
        real = _SubprocessGitPort._run_git

        def short(self: _SubprocessGitPort, root: Path, args: Sequence[str], stdin: bytes | None) -> bytes | None:
            return b"" if args[0] == "hash-object" else real(self, root, args, stdin)

        monkeypatch.setattr(_SubprocessGitPort, "_run_git", short)
        assert self._PORT.changed_vs_ref(repo, "HEAD", ["d/a.txt"]) == {"d/a.txt"}


# ---------------------------------------------------------------------------
# resolve_planning_artifact_staging (T016 pure staging-decision core)
# ---------------------------------------------------------------------------


class TestResolvePlanningArtifactStaging:
    def test_structural_change_short_circuits(self, tmp_path: Path) -> None:
        fake = _FakeGitPort(entries=(_entry(" D", "kitty-specs/m/tasks/WP01.md"), ))
        plan = resolve_planning_artifact_staging(tmp_path, tmp_path / "kitty-specs" / "m", None, [], auto_commit=True, git=fake)
        assert plan.structural
        assert plan.files_to_commit == []
        assert plan.status_paths_to_commit == []

    def test_no_changes_yields_empty_plan(self, tmp_path: Path) -> None:
        fake = _FakeGitPort(entries=())
        plan = resolve_planning_artifact_staging(tmp_path, tmp_path / "kitty-specs" / "m", None, [], auto_commit=True, git=fake)
        assert plan == PlanningArtifactStagingPlan(structural=[], files_to_commit=[], status_paths_to_commit=[])

    def test_extra_file_paths_only_added_under_coord_branch(self, tmp_path: Path) -> None:
        artifact_dir = tmp_path / "kitty-specs" / "m"
        artifact_dir.mkdir(parents=True)
        (artifact_dir / "tasks.md").write_bytes(b"# tasks")
        # _files_changed_vs_ref's idempotency filter drops any path that does
        # not exist on disk (defensive -- see its docstring), so the extra
        # path must be materialized for it to survive the coord-branch plan.
        (artifact_dir / "extra.md").write_bytes(b"extra")
        fake = _FakeGitPort(entries=())
        no_coord_plan = resolve_planning_artifact_staging(tmp_path, artifact_dir, None, ["kitty-specs/m/extra.md"], auto_commit=True, git=fake)
        assert no_coord_plan.files_to_commit == []

        coord_plan = resolve_planning_artifact_staging(
            tmp_path,
            artifact_dir,
            "kitty/mission-m-AAAA1111",
            ["kitty-specs/m/extra.md"],
            auto_commit=True,
            git=fake,
        )
        assert coord_plan.files_to_commit == ["kitty-specs/m/extra.md"]

    def test_idempotent_when_already_matching_its_partition_ref(self, tmp_path: Path) -> None:
        """Idempotency guard: a discovered-but-already-committed edit
        (content identical to the ref for ITS OWN partition) yields an empty
        plan, not an empty-commit attempt (see _files_changed_vs_ref).

        Re-pinned (WP01 / T004): ``tasks.md`` is a PRIMARY-partition kind
        (``TASKS_INDEX``), so on a coord mission it is compared against
        ``HEAD`` -- never the coordination ref -- even though this staging
        call carries a non-``None`` ``coord_branch_for_filter`` (#2533: the
        pre-fix single-ref comparison wrongly diffed it against coord instead,
        where it is legitimately absent, and flagged it as changed).
        """
        artifact_dir = tmp_path / "kitty-specs" / "m"
        artifact_dir.mkdir(parents=True)
        tasks_path = artifact_dir / "tasks.md"
        tasks_path.write_bytes(b"# tasks")
        coord_ref = "kitty/mission-m-AAAA1111"
        fake = _FakeGitPort(
            entries=(_entry(" M", "kitty-specs/m/tasks.md"), ),
            blobs={("HEAD", "kitty-specs/m/tasks.md"): b"# tasks"},
        )
        plan = resolve_planning_artifact_staging(tmp_path, artifact_dir, coord_ref, [], auto_commit=True, git=fake)
        assert plan.files_to_commit == []

    def test_genuinely_changed_primary_file_is_kept_and_flagged_for_instructions(self, tmp_path: Path) -> None:
        """Re-pinned (WP01 / T004, INV-5): a genuinely-dirty PRIMARY artifact
        (``tasks.md``) is still detected and staged on a coord mission -- the
        fix corrects WHICH ref it compares against (``HEAD``), it must not
        blind the check entirely."""
        artifact_dir = tmp_path / "kitty-specs" / "m"
        artifact_dir.mkdir(parents=True)
        tasks_path = artifact_dir / "tasks.md"
        tasks_path.write_bytes(b"# tasks v2")
        coord_ref = "kitty/mission-m-AAAA1111"
        fake = _FakeGitPort(
            entries=(_entry(" M", "kitty-specs/m/tasks.md"), ),
            blobs={("HEAD", "kitty-specs/m/tasks.md"): b"# tasks v1"},
        )
        plan = resolve_planning_artifact_staging(tmp_path, artifact_dir, coord_ref, [], auto_commit=True, git=fake)
        assert plan.files_to_commit == ["kitty-specs/m/tasks.md"]
        assert plan.status_paths_to_commit == ["kitty-specs/m/tasks.md"]

    def test_dirty_spec_md_still_staged_against_head_on_coord_mission(self, tmp_path: Path) -> None:
        """INV-5 invariant: a genuinely-dirty PRIMARY ``spec.md`` on a coord
        mission is still staged (compared against ``HEAD``, never coord)."""
        artifact_dir = tmp_path / "kitty-specs" / "m"
        artifact_dir.mkdir(parents=True)
        (artifact_dir / "spec.md").write_bytes(b"# spec v2")
        coord_ref = "kitty/mission-m-AAAA1111"
        fake = _FakeGitPort(
            entries=(_entry(" M", "kitty-specs/m/spec.md"), ),
            blobs={("HEAD", "kitty-specs/m/spec.md"): b"# spec v1"},
        )
        plan = resolve_planning_artifact_staging(tmp_path, artifact_dir, coord_ref, [], auto_commit=True, git=fake)
        assert plan.files_to_commit == ["kitty-specs/m/spec.md"]

    def test_dirty_coord_kind_file_still_resolves_to_coord_ref(self, tmp_path: Path) -> None:
        """NFR-002 coord non-regression: a genuinely-dirty COORD-partition
        artifact (``issue-matrix.md`` -- not ``MissionArtifactKind.STATUS_STATE``,
        the narrow kind excluded earlier in the pipeline) is still diffed against
        and staged for the coordination ref, exactly as before the fix."""
        artifact_dir = tmp_path / "kitty-specs" / "m"
        artifact_dir.mkdir(parents=True)
        (artifact_dir / "issue-matrix.md").write_bytes(b"# issues v2")
        coord_ref = "kitty/mission-m-AAAA1111"
        fake = _FakeGitPort(
            entries=(_entry(" M", "kitty-specs/m/issue-matrix.md"), ),
            blobs={(coord_ref, "kitty-specs/m/issue-matrix.md"): b"# issues v1"},
        )
        plan = resolve_planning_artifact_staging(tmp_path, artifact_dir, coord_ref, [], auto_commit=True, git=fake)
        assert plan.files_to_commit == ["kitty-specs/m/issue-matrix.md"]
        # A copy identical to coord is the idempotent no-op -- confirms the
        # comparison ref really is coord, not HEAD (which the fake has no
        # blob for and would therefore always read as "changed").
        fake_idempotent = _FakeGitPort(
            entries=(_entry(" M", "kitty-specs/m/issue-matrix.md"), ),
            blobs={(coord_ref, "kitty-specs/m/issue-matrix.md"): b"# issues v2"},
        )
        idempotent_plan = resolve_planning_artifact_staging(tmp_path, artifact_dir, coord_ref, [], auto_commit=True, git=fake_idempotent)
        assert idempotent_plan.files_to_commit == []

    def test_meta_json_on_coord_mission_resolves_to_head(self, tmp_path: Path) -> None:
        """BLOCKER-2 lock, exercised at the staging-core level: a ``meta.json``
        that is clean/committed on the primary (target) branch but naturally
        absent on the (empty) coordination branch must NOT be treated as
        changed and staged -- it is compared against ``HEAD``, where its
        content matches, and drops out of the plan entirely (#2533)."""
        artifact_dir = tmp_path / "kitty-specs" / "m"
        artifact_dir.mkdir(parents=True)
        (artifact_dir / "meta.json").write_bytes(b'{"mission_slug": "m"}')
        coord_ref = "kitty/mission-m-AAAA1111"
        fake = _FakeGitPort(
            entries=(),
            blobs={("HEAD", "kitty-specs/m/meta.json"): b'{"mission_slug": "m"}'},
        )
        plan = resolve_planning_artifact_staging(
            tmp_path,
            artifact_dir,
            coord_ref,
            ["kitty-specs/m/meta.json"],
            auto_commit=True,
            git=fake,
        )
        assert plan.files_to_commit == []

    def test_dirty_dossier_snapshot_does_not_poison_the_planning_commit_refusal(self, tmp_path: Path) -> None:
        """FIX-M2-08 regression: reproduces
        ``tests/e2e/test_cli_smoke.py::test_full_workflow_sequence`` on a coord
        mission. ``spec.md``/``plan.md``/``tasks.md``/``lanes.json`` are ALREADY
        committed on the primary (target) branch -- clean in ``git status`` --
        but a dossier-sync re-save between the last commit and this claim
        (e.g. by the immediately-preceding ``finalize-tasks``, D1 EXCLUDE:
        "No staging, no committing... The file is just a file") left the
        dossier snapshot locally modified. Before the fix this single
        self-bookkeeping diff populated ``status_paths_to_commit``, which
        gates ``implement.py``'s "Planning artifacts not committed" fail-closed
        refusal -- dragging every OTHER (already-committed, undirty) planning
        artifact into that same printed refusal via ``files_to_commit``'s
        unconditional ``extra_file_paths`` leg. After the fix, the dossier
        snapshot never enters ``status_paths_to_commit`` (so the refusal never
        fires) and never enters ``files_to_commit`` either (so implement's own
        auto-commit path can never commit it -- the same D1 violation
        FIX-M2-05 closed in ``mission_finalize.py``, now also closed here)."""
        artifact_dir = tmp_path / "kitty-specs" / "m"
        artifact_dir.mkdir(parents=True)
        # Already committed, byte-identical to HEAD -- these must NOT be
        # treated as needing a commit.
        for name, content in (
            ("spec.md", b"# spec"),
            ("plan.md", b"# plan"),
            ("tasks.md", b"# tasks"),
        ):
            (artifact_dir / name).write_bytes(content)
        dossier_dir = artifact_dir / ".kittify" / "dossiers" / "m"
        dossier_dir.mkdir(parents=True)
        dossier_path = dossier_dir / "snapshot-latest.json"
        dossier_path.write_bytes(b'{"snapshot_id": "new"}')

        coord_ref = "kitty/mission-m-AAAA1111"
        fake = _FakeGitPort(
            # Only the dossier snapshot is live-dirty; the other planning
            # artifacts are clean on disk (no status entry for them).
            entries=(_entry(" M", "kitty-specs/m/.kittify/dossiers/m/snapshot-latest.json"), ),
            blobs={
                ("HEAD", "kitty-specs/m/spec.md"): b"# spec",
                ("HEAD", "kitty-specs/m/plan.md"): b"# plan",
                ("HEAD", "kitty-specs/m/tasks.md"): b"# tasks",
                # The coordination branch has never seen any of these
                # (planning artifacts are PRIMARY-partition, committed to the
                # primary/target branch only) -- absent blobs everywhere on
                # coord_ref.
            },
        )
        plan = resolve_planning_artifact_staging(
            tmp_path,
            artifact_dir,
            coord_ref,
            [
                "kitty-specs/m/spec.md",
                "kitty-specs/m/plan.md",
                "kitty-specs/m/tasks.md",
                "kitty-specs/m/.kittify/dossiers/m/snapshot-latest.json",
            ],
            auto_commit=False,
            git=fake,
        )
        # The refusal-gating field: must be empty, or implement.py prints
        # "Planning artifacts not committed" and exits 1 even though nothing
        # genuinely uncommitted exists.
        assert plan.status_paths_to_commit == []
        # The dossier snapshot must never become an auto-commit candidate
        # either (D1: it is never staged/committed by any producer).
        assert "kitty-specs/m/.kittify/dossiers/m/snapshot-latest.json" not in plan.files_to_commit
        # The already-committed, byte-identical primary artifacts correctly
        # drop out too (idempotency guard, INV-5) -- nothing needs staging.
        assert plan.files_to_commit == []
