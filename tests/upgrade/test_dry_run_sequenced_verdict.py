"""The dry run reports the verdict a real run reaches, not the pre-run tree (#6552).

``spec-kitty upgrade --dry-run`` runs the real, ordered migration loop, but every
``apply(dry_run=True)`` returns without writing (``_merge_driver_seeding.py``'s
seeding ``apply`` does exactly that). A migration whose ``detect()`` reads state an
*earlier* migration in the same run writes therefore sees the pre-run tree in the dry
run and the sequenced tree in the real run: the preview reports it as
``not needed (project already in target state)`` and the real run applies it.

These tests pin the one sequencing decision that closes that gap
(:meth:`specify_cli.upgrade.runner.MigrationRunner._apply_migration`):

* a migration that declares the migrations whose writes its ``detect()`` reads
  (``BaseMigration.sequenced_after``) is reported **applied** — with the change line
  ``dry-run: would apply after <id>`` — when a declared predecessor was reported
  applied earlier in the same dry run;
* an *undeclared* dry-run skip no longer claims target state; it claims only the
  current tree;
* a real run's verdicts do not change, and a dry run still writes nothing.

The reported pair is the real ``3.2.6_gate_artifact_merge_drivers`` →
``3.2.6_issue_matrix_driver_repoint`` relationship: the gate migration rewrites
``merge.spec-kitty-issue-matrix.name`` to its own value, which is precisely the write
the repoint migration's ``detect()`` reads.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from charter.hasher import hash_content
from specify_cli.migration.schema_version import MAX_SUPPORTED_SCHEMA
from specify_cli.upgrade.ledger import MigrationLedger, build_record
from specify_cli.upgrade.migrations.base import BaseMigration, MigrationResult
from specify_cli.upgrade.migrations.m_3_2_6_gate_artifact_merge_drivers import (
    GateArtifactMergeDriverMigration,
)
from specify_cli.upgrade.migrations.m_3_2_6_issue_matrix_driver_repoint import (
    IssueMatrixDriverRepointMigration,
)
from specify_cli.upgrade.manifest import load_order_manifest
from specify_cli.upgrade.migrations import auto_discover_migrations
from specify_cli.upgrade.registry import MigrationRegistry
from specify_cli.upgrade.runner import MigrationRunner, UpgradeResult

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_TARGET = "3.2.6rc1"
_GATE = "3.2.6_gate_artifact_merge_drivers"
_REPOINT = "3.2.6_issue_matrix_driver_repoint"

#: The tracked .gitattributes lines ``init`` seeds, so the pair is pending for its
#: *config* half only (the gate migration declares the filled-side driver name).
_SEEDED_ATTRIBUTES = (
    "kitty-specs/**/acceptance-matrix.json merge=spec-kitty-acceptance-matrix",
    "kitty-specs/**/issue-matrix.json merge=spec-kitty-issue-matrix",
    "kitty-specs/**/issue-matrix.md merge=spec-kitty-issue-matrix",
)

#: The clone-local state ``init`` seeds: the *row-aware* driver name, so the gate
#: migration's detect() is True (it declares the *filled-side* name) while the
#: repoint migration's detect() is False (it wants the row-aware name).
_SEEDED_CONFIG = {
    "merge.spec-kitty-issue-matrix.name": "Spec Kitty issue matrix row-aware merge",
    "merge.spec-kitty-issue-matrix.driver": "spec-kitty merge-driver-issue-matrix %O %A %B",
}


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #


def _git(*args: str, cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def _write_metadata(project: Path, version: str) -> None:
    kittify = project / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)
    (kittify / "metadata.yaml").write_text(
        f"spec_kitty:\n  version: \"{version}\"\n  schema_version: {MAX_SUPPORTED_SCHEMA}\n  initialized_at: '2026-01-01T00:00:00+00:00'\n",
        encoding="utf-8",
    )


def _project(path: Path, *, version: str = "3.2.5", config: dict[str, str] | None = None) -> Path:
    """A git project carrying the clone-local state a fresh ``init`` seeds."""
    path.mkdir(parents=True, exist_ok=True)
    _git("init", "-q", "-b", "main", cwd=path)
    for key, value in (config if config is not None else _SEEDED_CONFIG).items():
        _git("config", "--local", key, value, cwd=path)
    _write_metadata(path, version)
    (path / ".gitattributes").write_text("\n".join(_SEEDED_ATTRIBUTES) + "\n", encoding="utf-8")
    return path


def _pair_project(tmp_path: Path, name: str = "project") -> Path:
    """The reported pair's state: the gate migration pending, the repoint pending-but-undetected."""
    project = _project(tmp_path / name)
    gate, repoint = GateArtifactMergeDriverMigration(), IssueMatrixDriverRepointMigration()
    # Preconditions, asserted so fixture drift fails loudly instead of passing vacuously.
    assert gate.detect(project) is True, "gate migration must be pending (its .gitattributes lines are absent)"
    assert repoint.detect(project) is False, "repoint migration must be undetected on the pre-run tree"
    return project


def _copy(source: Path, destination: Path) -> Path:
    shutil.copytree(source, destination, symlinks=True)
    return destination


def _only(*migration_classes: type[BaseMigration]) -> None:
    """Replace the process-global registry with *migration_classes* (restored by tests/upgrade/conftest.py)."""
    MigrationRegistry.clear()
    for migration_class in migration_classes:
        MigrationRegistry.register(migration_class)


def _run(project: Path, *, dry_run: bool) -> UpgradeResult:
    return MigrationRunner(project).upgrade(_TARGET, dry_run=dry_run, include_worktrees=False)


def _tree_digest(project: Path) -> dict[str, str]:
    """Every file's content digest under the project, excluding git's object store and index churn."""
    digest: dict[str, str] = {}
    for path in sorted(project.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        relative = path.relative_to(project).as_posix()
        if relative.startswith(".git/objects/") or relative in {".git/index", ".git/ORIG_HEAD"}:
            continue
        digest[relative] = hash_content(path.read_bytes().decode("utf-8", "surrogateescape"))
    return digest


def _local_config(project: Path, key: str) -> str | None:
    result = subprocess.run(["git", "config", "--local", "--get", key], cwd=project, capture_output=True, text=True, check=False)
    return result.stdout.strip() if result.returncode == 0 else None


# --------------------------------------------------------------------------- #
# Synthetic ordering pair: an undeclared and a declared dependent
# --------------------------------------------------------------------------- #


class _WritesMarker(BaseMigration):
    """Applies by writing ``marker.txt`` — the state the dependent's detect() reads."""

    migration_id = "9.9.9_writes_marker"
    description = "Write the marker file a later migration detects"
    target_version = "9.9.9"

    def detect(self, project_path: Path) -> bool:
        return not (Path(project_path) / "marker.txt").exists()

    def can_apply(self, project_path: Path) -> tuple[bool, str]:
        return True, ""

    def apply(self, project_path: Path, dry_run: bool = False) -> MigrationResult:
        if not dry_run:
            (Path(project_path) / "marker.txt").write_text("written\n", encoding="utf-8")
        return MigrationResult(success=True, changes_made=[] if dry_run else ["wrote marker.txt"])


class _ReadsMarker(BaseMigration):
    """Needed only once ``_WritesMarker`` has written the marker."""

    migration_id = "9.9.9_reads_marker"
    description = "Rewrites the marker file a predecessor writes"
    target_version = "9.9.9"
    sequenced_after: tuple[str, ...] = ()

    def detect(self, project_path: Path) -> bool:
        return (Path(project_path) / "marker.txt").exists()

    def can_apply(self, project_path: Path) -> tuple[bool, str]:
        return True, ""

    def apply(self, project_path: Path, dry_run: bool = False) -> MigrationResult:  # noqa: ARG002
        return MigrationResult(success=True, changes_made=["rewrote marker.txt"])


class _DeclaredReadsMarker(_ReadsMarker):
    """``_ReadsMarker`` declaring the predecessor whose write re-selects it."""

    sequenced_after = (_WritesMarker.migration_id,)


class _RefusingReadsMarker(_DeclaredReadsMarker):
    """A declared dependent the project refuses, so the prediction must honour ``can_apply``."""

    def can_apply(self, project_path: Path) -> tuple[bool, str]:  # noqa: ARG002
        return False, "not this project"


# --------------------------------------------------------------------------- #
# US1 — the reported pair: the dry run agrees with the real run
# --------------------------------------------------------------------------- #


def test_the_dry_run_lists_the_migration_the_real_run_applies(tmp_path: Path) -> None:
    """Red-first: on the pre-fix tree the dry run reports the repoint as not needed."""
    original = _pair_project(tmp_path)
    dry_project = _copy(original, tmp_path / "dry")
    real_project = _copy(original, tmp_path / "real")
    _only(GateArtifactMergeDriverMigration, IssueMatrixDriverRepointMigration)

    dry = _run(dry_project, dry_run=True)
    real = _run(real_project, dry_run=False)

    assert dry.success is True, dry.errors
    assert real.success is True, real.errors
    assert real.migrations_applied == [_GATE, _REPOINT], real.migrations_skipped
    assert dry.migrations_applied == real.migrations_applied
    assert dry.migrations_skipped == real.migrations_skipped == []


def test_the_predicted_verdict_names_the_predecessor(tmp_path: Path) -> None:
    """A predicted verdict is tellable from a direct detection: it says what it follows."""
    project = _pair_project(tmp_path)
    _only(GateArtifactMergeDriverMigration, IssueMatrixDriverRepointMigration)

    result = _run(project, dry_run=True)

    predicted = result.migration_results[_REPOINT]
    assert predicted.success is True
    assert predicted.changes_made == [f"dry-run: would apply after {_GATE}"]
    # The provenance is data, not prose: the surfaces that render a verdict read this.
    assert predicted.predicted_after == (_GATE,)
    assert result.migration_results[_GATE].predicted_after == (), "a directly detected verdict is never marked predicted"


def test_a_dry_run_writes_nothing(tmp_path: Path) -> None:
    """NFR-001: the prediction is a verdict, not a write — and the real run is the positive control."""
    original = _pair_project(tmp_path)
    dry_project = _copy(original, tmp_path / "dry")
    real_project = _copy(original, tmp_path / "real")
    _only(GateArtifactMergeDriverMigration, IssueMatrixDriverRepointMigration)

    before = _tree_digest(dry_project)
    ledger_before = {
        "tracked": MigrationLedger(dry_project).read_tracked(),
        "clone_local": MigrationLedger(dry_project).read_clone_local(),
    }
    _run(dry_project, dry_run=True)

    assert _tree_digest(dry_project) == before
    assert MigrationLedger(dry_project).read_tracked() == ledger_before["tracked"]
    assert MigrationLedger(dry_project).read_clone_local() == ledger_before["clone_local"]
    assert _local_config(dry_project, "merge.spec-kitty-issue-matrix.name") == _SEEDED_CONFIG["merge.spec-kitty-issue-matrix.name"]

    real_before = _tree_digest(real_project)
    _run(real_project, dry_run=False)
    assert _tree_digest(real_project) != real_before, "the real run must change the tree, or the no-writes check is vacuous"


# --------------------------------------------------------------------------- #
# US2 — an undeclared dependency: honest wording, real run unchanged
# --------------------------------------------------------------------------- #


def test_an_undeclared_ordering_pair_claims_only_the_current_tree(tmp_path: Path) -> None:
    """A dry-run skip cannot claim target state when a predecessor's write is unsimulated."""
    original = _project(tmp_path / "original", version="9.9.8")
    dry_project = _copy(original, tmp_path / "dry")
    real_project = _copy(original, tmp_path / "real")
    _only(_WritesMarker, _ReadsMarker)

    dry = MigrationRunner(dry_project).upgrade("9.9.9", dry_run=True, include_worktrees=False)
    real = MigrationRunner(real_project).upgrade("9.9.9", dry_run=False, include_worktrees=False)

    assert dry.migrations_skipped == [_ReadsMarker.migration_id]
    assert any("not needed on the current tree" in warning for warning in dry.warnings), dry.warnings
    assert not any("project already in target state" in warning for warning in dry.warnings), dry.warnings
    # Positive control on the same fixture: the real run selects the dependent, so the
    # dry run's "not needed" was a look-ahead it could not support.
    assert real.migrations_applied == [_WritesMarker.migration_id, _ReadsMarker.migration_id]


def test_an_undeclared_dependent_stays_skipped_when_nothing_re_selects_it(tmp_path: Path) -> None:
    """The wording is not a blanket "would apply": with no applied predecessor the skip stands."""
    project = _project(tmp_path / "project", version="9.9.8")
    _only(_ReadsMarker)

    result = MigrationRunner(project).upgrade("9.9.9", dry_run=True, include_worktrees=False)

    assert result.migrations_skipped == [_ReadsMarker.migration_id]
    assert any("not needed on the current tree" in warning for warning in result.warnings), result.warnings


def test_a_declared_dependent_of_an_applied_predecessor_is_predicted(tmp_path: Path) -> None:
    """The declared synthetic pair behaves like the reported one."""
    original = _project(tmp_path / "original", version="9.9.8")
    dry_project = _copy(original, tmp_path / "dry")
    real_project = _copy(original, tmp_path / "real")
    _only(_WritesMarker, _DeclaredReadsMarker)

    dry = MigrationRunner(dry_project).upgrade("9.9.9", dry_run=True, include_worktrees=False)
    real = MigrationRunner(real_project).upgrade("9.9.9", dry_run=False, include_worktrees=False)

    assert dry.migrations_applied == [_WritesMarker.migration_id, _DeclaredReadsMarker.migration_id]
    assert dry.migrations_applied == real.migrations_applied
    assert dry.migration_results[_DeclaredReadsMarker.migration_id].changes_made == [f"dry-run: would apply after {_WritesMarker.migration_id}"]


def test_a_prediction_honours_can_apply(tmp_path: Path) -> None:
    """A dependent this project refuses stays skipped, with its own reason."""
    project = _project(tmp_path / "project", version="9.9.8")
    _only(_WritesMarker, _RefusingReadsMarker)

    result = MigrationRunner(project).upgrade("9.9.9", dry_run=True, include_worktrees=False)

    assert result.migrations_applied == [_WritesMarker.migration_id]
    assert result.migrations_skipped == [_RefusingReadsMarker.migration_id]
    assert any("not applicable here (not this project)" in warning for warning in result.warnings), result.warnings


def test_a_settled_predecessor_predicts_nothing(tmp_path: Path) -> None:
    """A predecessor outside this run's selection cannot change the tree, so it predicts nothing."""
    project = _project(tmp_path / "project", version="9.9.8")
    MigrationLedger(project).append(build_record(_WritesMarker(), "success"))
    _only(_WritesMarker, _DeclaredReadsMarker)

    result = MigrationRunner(project).upgrade("9.9.9", dry_run=True, include_worktrees=False)

    assert _WritesMarker.migration_id not in result.migrations_applied
    assert result.migrations_skipped == [_DeclaredReadsMarker.migration_id]
    assert any("not needed on the current tree" in warning for warning in result.warnings), result.warnings


def test_a_real_run_keeps_its_target_state_wording(tmp_path: Path) -> None:
    """C-002: the honest dry-run wording does not leak into a real run."""
    project = _project(tmp_path / "project", version="9.9.8")
    _only(_ReadsMarker)

    result = MigrationRunner(project).upgrade("9.9.9", dry_run=False, include_worktrees=False)

    assert result.migrations_skipped == [_ReadsMarker.migration_id]
    assert any("not needed (project already in target state)" in warning for warning in result.warnings), result.warnings
    assert not any("not needed on the current tree" in warning for warning in result.warnings), result.warnings


# --------------------------------------------------------------------------- #
# Declaration audit — a declaration that can never fire is a silent no-op
# --------------------------------------------------------------------------- #


def _declarations() -> list[tuple[str, tuple[str, ...]]]:
    """Every declared ``sequenced_after`` in the discovered registry, in manifest order."""
    auto_discover_migrations()
    return [(migration.migration_id, tuple(migration.sequenced_after)) for migration in MigrationRegistry.get_all() if migration.sequenced_after]


def test_every_declared_predecessor_is_a_registered_earlier_migration() -> None:
    """A typo, a rename, or a later-ordered predecessor would silently disable the prediction.

    The declaration asserts "this predecessor's write happens before my ``detect()`` reads
    it", so the id must exist in the registry (or the dry run can never match it) and be
    ordered BEFORE its declarer by ``order_manifest.txt`` (or the dry run matches it only
    after the dependent has already been decided).
    """
    order = {migration_id: position for position, migration_id in enumerate(load_order_manifest())}
    registered = {migration.migration_id for migration in MigrationRegistry.get_all()}
    declarations = _declarations()
    assert declarations, "the reported pair must keep its declaration, or the audit is vacuous"

    for declarer, predecessors in declarations:
        for predecessor in predecessors:
            assert predecessor in registered, f"{declarer} declares unknown predecessor {predecessor}"
            assert predecessor in order, f"{declarer} declares {predecessor}, which order_manifest.txt does not order"
            assert order[predecessor] < order[declarer], f"{declarer} declares {predecessor}, which the manifest orders after it"


def test_the_reported_pair_declares_its_detect_input() -> None:
    """The measured case stays declared: without it the preview under-reports #6552 again."""
    assert (_REPOINT, (_GATE,)) in _declarations()
