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

The reported pair was the real ``3.2.6_gate_artifact_merge_drivers`` →
``3.2.6_issue_matrix_driver_repoint`` relationship (the gate migration rewrote
``merge.spec-kitty-issue-matrix.name`` to its own value, the write the repoint migration's
``detect()`` reads). #7217 superseded the gate migration -- its retired
``issue-matrix.md`` row was re-applied on every fresh clone -- so the pair no longer exists
and its ``SEQUENCED_AFTER`` declaration is gone. These tests pin the *mechanism*, so the same
shape now rides the synthetic ``_WritesMarker`` → ``_DeclaredReadsMarker`` pair below.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import ClassVar

import pytest

from charter.hasher import hash_content
from specify_cli.migration.schema_version import MAX_SUPPORTED_SCHEMA
from specify_cli.upgrade.ledger import MigrationLedger, build_record
from specify_cli.upgrade.migrations.base import BaseMigration, MigrationResult
from specify_cli.upgrade.manifest import load_order_manifest
from specify_cli.upgrade.migrations import auto_discover_migrations
from specify_cli.upgrade.registry import MigrationRegistry
from specify_cli.upgrade.runner import MigrationRunner, UpgradeResult, declared_predecessors
from specify_cli.upgrade.supersession import SUPERSEDED_MIGRATIONS

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

#: The synthetic pair's ``target_version``: no later than the installed package version, so the
#: CLI command's default target includes it and the operator-facing witness needs no ``--target``.
_TARGET = "4.0.0rc8"
_PREDECESSOR = "9.9.9_writes_marker"
_DEPENDENT = "9.9.9_reads_marker"
_SUPERSEDED_PREDECESSOR = "3.2.6_gate_artifact_merge_drivers"


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


def _project(path: Path, *, version: str = "3.2.5") -> Path:
    """A git project at *version*, with no state a migration could mistake for its own."""
    path.mkdir(parents=True, exist_ok=True)
    _git("init", "-q", "-b", "main", cwd=path)
    _write_metadata(path, version)
    return path


def _pair_project(tmp_path: Path, name: str = "project") -> Path:
    """The reported pair's shape: the predecessor pending, the dependent pending-but-undetected."""
    project = _project(tmp_path / name)
    predecessor, dependent = _WritesMarker(), _DeclaredReadsMarker()
    # Preconditions, asserted so fixture drift fails loudly instead of passing vacuously.
    assert predecessor.detect(project) is True, "the predecessor must be pending (its marker is absent)"
    assert dependent.detect(project) is False, "the dependent must be undetected on the pre-run tree"
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


# --------------------------------------------------------------------------- #
# Synthetic ordering pair: an undeclared and a declared dependent
# --------------------------------------------------------------------------- #


class _WritesMarker(BaseMigration):
    """Applies by writing ``marker.txt`` — the state the dependent's detect() reads."""

    migration_id = "9.9.9_writes_marker"
    description = "Write the marker file a later migration detects"
    target_version = _TARGET

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
    target_version = _TARGET
    sequenced_after: ClassVar[tuple[str, ...]] = ()

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
    _only(_WritesMarker, _DeclaredReadsMarker)

    dry = _run(dry_project, dry_run=True)
    real = _run(real_project, dry_run=False)

    assert dry.success is True, dry.errors
    assert real.success is True, real.errors
    assert real.migrations_applied == [_PREDECESSOR, _DEPENDENT], real.migrations_skipped
    assert dry.migrations_applied == real.migrations_applied
    assert dry.migrations_skipped == real.migrations_skipped == []


def test_the_predicted_verdict_names_the_predecessor(tmp_path: Path) -> None:
    """A predicted verdict is tellable from a direct detection: it says what it follows."""
    project = _pair_project(tmp_path)
    _only(_WritesMarker, _DeclaredReadsMarker)

    result = _run(project, dry_run=True)

    predicted = result.migration_results[_DEPENDENT]
    assert predicted.success is True
    assert predicted.changes_made == [f"dry-run: would apply after {_PREDECESSOR}"]
    # The provenance is data, not prose: the surfaces that render a verdict read this.
    assert predicted.predicted_after == (_PREDECESSOR,)
    assert result.migration_results[_PREDECESSOR].predicted_after == (), "a directly detected verdict is never marked predicted"


def test_a_dry_run_writes_nothing(tmp_path: Path) -> None:
    """NFR-001: the prediction is a verdict, not a write — and the real run is the positive control."""
    original = _pair_project(tmp_path)
    dry_project = _copy(original, tmp_path / "dry")
    real_project = _copy(original, tmp_path / "real")
    _only(_WritesMarker, _DeclaredReadsMarker)

    before = _tree_digest(dry_project)
    ledger_before = {
        "tracked": MigrationLedger(dry_project).read_tracked(),
        "clone_local": MigrationLedger(dry_project).read_clone_local(),
    }
    _run(dry_project, dry_run=True)

    assert _tree_digest(dry_project) == before
    assert MigrationLedger(dry_project).read_tracked() == ledger_before["tracked"]
    assert MigrationLedger(dry_project).read_clone_local() == ledger_before["clone_local"]
    assert not (dry_project / "marker.txt").exists(), "the dry run must not run the predecessor's apply()"

    real_before = _tree_digest(real_project)
    _run(real_project, dry_run=False)
    assert _tree_digest(real_project) != real_before, "the real run must change the tree, or the no-writes check is vacuous"


# --------------------------------------------------------------------------- #
# US2 — an undeclared dependency: honest wording, real run unchanged
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("dry_run", [True, False])
def test_an_undeclared_ordering_pair_words_its_skip_by_run_mode(tmp_path: Path, dry_run: bool) -> None:
    """A dry-run skip claims only the current tree (C-002: a real run keeps its target-state wording)."""
    project = _project(tmp_path / "project", version="3.2.5")
    _only(*((_WritesMarker, _ReadsMarker) if dry_run else (_ReadsMarker,)))

    result = MigrationRunner(project).upgrade(_TARGET, dry_run=dry_run, include_worktrees=False)

    assert result.migrations_skipped == [_ReadsMarker.migration_id]
    assert any(("not needed on the current tree" if dry_run else "not needed (project already in target state)") in w for w in result.warnings), result.warnings
    assert not any(("project already in target state" if dry_run else "not needed on the current tree") in w for w in result.warnings), result.warnings


def test_an_undeclared_dependent_stays_skipped_when_nothing_re_selects_it(tmp_path: Path) -> None:
    """The wording is not a blanket "would apply": with no applied predecessor the skip stands."""
    project = _project(tmp_path / "project", version="3.2.5")
    _only(_ReadsMarker)

    result = MigrationRunner(project).upgrade(_TARGET, dry_run=True, include_worktrees=False)

    assert result.migrations_skipped == [_ReadsMarker.migration_id]
    assert any("not needed on the current tree" in warning for warning in result.warnings), result.warnings


def test_a_declared_dependent_of_an_applied_predecessor_is_predicted(tmp_path: Path) -> None:
    """The declared synthetic pair behaves like the reported one."""
    original = _project(tmp_path / "original", version="3.2.5")
    dry_project = _copy(original, tmp_path / "dry")
    real_project = _copy(original, tmp_path / "real")
    _only(_WritesMarker, _DeclaredReadsMarker)

    dry = MigrationRunner(dry_project).upgrade(_TARGET, dry_run=True, include_worktrees=False)
    real = MigrationRunner(real_project).upgrade(_TARGET, dry_run=False, include_worktrees=False)

    assert dry.migrations_applied == [_WritesMarker.migration_id, _DeclaredReadsMarker.migration_id]
    assert dry.migrations_applied == real.migrations_applied
    assert dry.migration_results[_DeclaredReadsMarker.migration_id].changes_made == [f"dry-run: would apply after {_WritesMarker.migration_id}"]


def test_a_prediction_honours_can_apply(tmp_path: Path) -> None:
    """A dependent this project refuses stays skipped, with its own reason."""
    project = _project(tmp_path / "project", version="3.2.5")
    _only(_WritesMarker, _RefusingReadsMarker)

    result = MigrationRunner(project).upgrade(_TARGET, dry_run=True, include_worktrees=False)

    assert result.migrations_applied == [_WritesMarker.migration_id]
    assert result.migrations_skipped == [_RefusingReadsMarker.migration_id]
    assert any("not applicable here (not this project)" in warning for warning in result.warnings), result.warnings


def test_a_settled_predecessor_predicts_nothing(tmp_path: Path) -> None:
    """A predecessor outside this run's selection cannot change the tree, so it predicts nothing."""
    project = _project(tmp_path / "project", version="3.2.5")
    MigrationLedger(project).append(build_record(_WritesMarker(), "success"))
    _only(_WritesMarker, _DeclaredReadsMarker)

    result = MigrationRunner(project).upgrade(_TARGET, dry_run=True, include_worktrees=False)

    assert _WritesMarker.migration_id not in result.migrations_applied
    assert result.migrations_skipped == [_DeclaredReadsMarker.migration_id]
    assert any("not needed on the current tree" in warning for warning in result.warnings), result.warnings


# --------------------------------------------------------------------------- #
# Declaration audit — a declaration that can never fire is a silent no-op
# --------------------------------------------------------------------------- #


def _declarations() -> list[tuple[str, tuple[str, ...]]]:
    """Every declared ``sequenced_after`` in the discovered registry, in manifest order."""
    auto_discover_migrations()
    return [(migration.migration_id, declared_predecessors(migration)) for migration in MigrationRegistry.get_all() if declared_predecessors(migration)]


def _declaration_faults(
    declarations: list[tuple[str, tuple[str, ...]]],
    order: dict[str, int],
    registered: set[str],
) -> list[str]:
    """Every declared predecessor that can never fire: unknown, superseded, unordered, or later."""
    faults: list[str] = []
    for declarer, predecessors in declarations:
        for predecessor in predecessors:
            if predecessor not in registered:
                faults.append(f"{declarer} declares unknown predecessor {predecessor}")
            elif predecessor in SUPERSEDED_MIGRATIONS:
                faults.append(f"{declarer} declares superseded predecessor {predecessor}")
            elif predecessor not in order:
                faults.append(f"{declarer} declares {predecessor}, which order_manifest.txt does not order")
            elif order[predecessor] >= order.get(declarer, -1):
                faults.append(f"{declarer} declares {predecessor}, which the manifest orders after it")
    return faults


def test_every_declared_predecessor_is_a_registered_earlier_migration() -> None:
    """A typo, a rename, or a later-ordered predecessor would silently disable the prediction.

    The declaration asserts "this predecessor's write happens before my ``detect()`` reads
    it", so the id must exist in the registry (or the dry run can never match it) and be
    ordered BEFORE its declarer by ``order_manifest.txt`` (or the dry run matches it only
    after the dependent has already been decided). No shipped migration declares a
    predecessor today (#7217 retired the only one with the writer it named), so the audit's
    teeth are proven on synthetic declarations in the next test.
    """
    declarations = _declarations()
    order = {migration_id: position for position, migration_id in enumerate(load_order_manifest())}
    registered = {migration.migration_id for migration in MigrationRegistry.get_all()}

    assert _declaration_faults(declarations, order, registered) == []


@pytest.mark.parametrize(
    ("predecessor", "fault"),
    [
        ("9.9.9_typo", "declares unknown predecessor 9.9.9_typo"),
        (_SUPERSEDED_PREDECESSOR, "declares superseded predecessor 3.2.6_gate_artifact_merge_drivers"),
        ("unordered", "which order_manifest.txt does not order"),
        ("later", "which the manifest orders after it"),
    ],
)
def test_the_declaration_audit_reports_a_declaration_that_can_never_fire(predecessor: str, fault: str) -> None:
    order = {"earlier": 0, _SUPERSEDED_PREDECESSOR: 0, "declarer": 1, "later": 2}
    registered = {"earlier", _SUPERSEDED_PREDECESSOR, "declarer", "later", "unordered"}

    assert _declaration_faults([("declarer", ("earlier",))], order, registered) == []
    faults = _declaration_faults([("declarer", (predecessor,))], order, registered)
    assert len(faults) == 1 and fault in faults[0], faults
