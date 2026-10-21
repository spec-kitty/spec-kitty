"""The upgrade-only legacy activation scope (WP08 T043.3/T044/T045, FR-017, C-001).

Every public
project-path method a migration subclass defines runs inside
``legacy_activation_scope`` through ``BaseMigration.__init_subclass__``, so a
shipped migration keeps reading the legacy surface without being edited
(DIRECTIVE_044). The selection entry points enter the scope too.
"""

from __future__ import annotations

import contextlib
import inspect
import subprocess
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
import typer
from typer.testing import CliRunner

from charter.activation.activation_ledger import ActiveCharterConfigError, load_activation_ledger, refuse_unmigrated_deny_write, resolve_ledger_source
from kernel.activation_ledger_store import ActivationSource, in_legacy_activation_scope
from kernel.content_digest import sha256_digest
from specify_cli.upgrade import ledger as ledger_module
from specify_cli.upgrade import registry as registry_module
from specify_cli.upgrade.migrations import base as base_module
from specify_cli.upgrade.migrations.base import BaseMigration, MigrationResult, _wraps_project_method, legacy_upgrade_scope
from specify_cli.upgrade.migrations.m_4_0_0rc6_charter_pack_cutover import CharterPackCutoverMigration
from specify_cli.upgrade.registry import MigrationRegistry
from specify_cli.upgrade.runner import MigrationRunner

pytestmark = [pytest.mark.unit]


class _Spy(BaseMigration):
    """Records whether each project-path method ran inside the scope."""

    migration_id = "zz_scope_spy"
    description = "scope spy"
    target_version = "99.0.0"

    seen: dict[str, bool] = {}

    def detect(self, project_path: Path) -> bool:
        self.seen["detect"] = in_legacy_activation_scope(project_path)
        return True

    def can_apply(self, project_path: Path) -> tuple[bool, str]:
        self.seen["can_apply"] = in_legacy_activation_scope(project_path)
        return True, ""

    def apply(self, project_path: Path, dry_run: bool = False) -> MigrationResult:
        self.detect(project_path)
        self.seen["apply"] = in_legacy_activation_scope(project_path)
        return MigrationResult(success=True)

    def structural_detect(self, project_path: Path) -> bool:
        self.seen["structural_detect"] = in_legacy_activation_scope(project_path)
        return False

    def is_first_application(self, project_path: Path) -> bool:
        self.seen["is_first_application"] = in_legacy_activation_scope(project_path)
        return False

    def reselect_when_recorded(self, project_path: Path) -> bool:
        self.seen["reselect_when_recorded"] = in_legacy_activation_scope(project_path)
        return False

    def renamed(self, repo: Path) -> bool:
        return in_legacy_activation_scope(repo)

    def label(self, text: str) -> str:
        return text

    def _private(self, project_path: Path) -> bool:
        return in_legacy_activation_scope(project_path)

    @staticmethod
    def static_probe(project_path: Path) -> bool:
        return in_legacy_activation_scope(project_path)

    @classmethod
    def class_probe(cls, project_path: Path) -> bool:
        return in_legacy_activation_scope(project_path)


@pytest.fixture(autouse=True)
def _reset_spy() -> Iterator[None]:
    _Spy.seen.clear()
    yield
    _Spy.seen.clear()


_PUBLIC_METHODS = ("detect", "can_apply", "apply", "structural_detect", "is_first_application", "reselect_when_recorded")


@pytest.mark.parametrize("name", _PUBLIC_METHODS)
def test_every_public_project_path_method_runs_inside_the_scope(tmp_path: Path, name: str) -> None:
    getattr(_Spy(), name)(tmp_path)
    assert _Spy.seen[name] is True
    assert not in_legacy_activation_scope(tmp_path)


def test_scope_is_reentrant_and_closes_after_the_outer_call(tmp_path: Path) -> None:
    _Spy().apply(tmp_path)
    assert _Spy.seen == {"detect": True, "apply": True}
    assert not in_legacy_activation_scope(tmp_path)


def test_the_project_path_is_matched_by_position_not_by_name(tmp_path: Path) -> None:
    spy = _Spy()
    assert spy.renamed(tmp_path) is True
    assert spy.renamed(repo=tmp_path) is True
    assert spy.label("x") == "x"


def test_private_static_and_class_methods_are_not_wrapped(tmp_path: Path) -> None:
    spy = _Spy()
    assert spy._private(tmp_path) is False
    assert _Spy.static_probe(tmp_path) is False
    assert _Spy.class_probe(tmp_path) is False


def test_wraps_preserves_names_and_signatures() -> None:
    for name in (*_PUBLIC_METHODS, "renamed"):
        wrapped = vars(_Spy)[name]
        assert wrapped.__name__ == name
        assert inspect.signature(wrapped) == inspect.signature(wrapped.__wrapped__)


def test_wraps_project_method_rule() -> None:
    def project(self: Any, project_path: Path) -> None: ...

    def no_argument(self: Any) -> None: ...

    def keyword_only(self: Any, *, project_path: Path) -> None: ...

    def _hidden(self: Any, project_path: Path) -> None: ...

    assert _wraps_project_method(project) is True
    assert _wraps_project_method(no_argument) is False
    assert _wraps_project_method(keyword_only) is False
    assert _wraps_project_method(_hidden) is False
    assert _wraps_project_method(staticmethod(project)) is False
    assert _wraps_project_method(classmethod(project)) is False
    assert _wraps_project_method("detect") is False
    assert _wraps_project_method(vars(_Spy)["detect"]) is False  # already wrapped: never twice


def test_the_real_rc6_migration_methods_are_wrapped() -> None:
    for name in ("detect", "can_apply", "apply", "structural_detect", "is_first_application"):
        assert hasattr(vars(CharterPackCutoverMigration)[name], "__wrapped__"), name


def test_no_migration_content_hash_changes() -> None:
    """The wrapper lives in base.py: every migration still hashes its own module bytes."""
    for migration in MigrationRegistry.get_all():
        if migration.content_hash_sources:
            continue
        source = Path(inspect.getsourcefile(type(migration)) or "")
        assert source.name.startswith(("m_", "base")), source
        digest = ledger_module.compute_content_hash(migration)
        assert digest == sha256_digest(source.read_bytes())


# --------------------------------------------------------------------------- #
# Selection entry points (T045)
# --------------------------------------------------------------------------- #


def test_get_applicable_enters_the_scope(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[bool] = []

    def _settled(_ledger: object, _migration: object) -> bool:
        seen.append(in_legacy_activation_scope(tmp_path))
        return False

    monkeypatch.setattr(registry_module, "migration_settled", _settled)
    MigrationRegistry.get_applicable("0.0.0", "99.0.0", project_path=tmp_path)
    assert seen and all(seen)
    assert not in_legacy_activation_scope(tmp_path)


def test_get_applicable_without_a_project_enters_no_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    def _refuse(_path: Path) -> Any:
        raise AssertionError("no project path: no scope, nothing resolved")

    monkeypatch.setattr(base_module, "legacy_upgrade_scope", _refuse)
    monkeypatch.setattr(base_module, "_canonical_root", _refuse)
    assert MigrationRegistry.get_applicable("0.0.0", "99.0.0", project_path=None)


def test_the_runner_enters_the_scope(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / ".kittify").mkdir()
    seen: list[bool] = []

    def _apply(self: MigrationRunner, migration: BaseMigration, metadata: object, dry_run: bool) -> tuple[MigrationResult, str]:
        seen.append(in_legacy_activation_scope(self.project_path))
        return MigrationResult(success=True), "skipped"

    monkeypatch.setattr(MigrationRunner, "_apply_migration", _apply)
    MigrationRunner(tmp_path).upgrade("99.0.0", dry_run=True, include_worktrees=False)
    assert seen and all(seen)


def test_upgrade_worktrees_only_enters_the_scope(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[bool] = []

    def _worktrees(self: MigrationRunner, *_args: Any, **_kwargs: Any) -> dict[str, Any]:
        seen.append(in_legacy_activation_scope(self.project_path))
        return {"warnings": [], "errors": [], "worktree_failures": []}

    monkeypatch.setattr(MigrationRunner, "_upgrade_worktrees", _worktrees)
    MigrationRunner(tmp_path).upgrade_worktrees_only("99.0.0", dry_run=True)
    assert seen == [True]


def test_migrate_ledger_enters_the_scope(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from specify_cli.cli.commands.migrate_cmd import app

    (tmp_path / ".kittify").mkdir()
    seen: list[bool] = []
    real = ledger_module.assemble_report

    def _report(migrations: list[object], project_root: Path) -> Any:
        seen.append(in_legacy_activation_scope(Path(project_root)))
        return real(migrations, project_root)

    monkeypatch.setattr(ledger_module, "assemble_report", _report)
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(app, ["ledger", "--json"])
    assert result.exit_code == 0, result.output
    assert seen == [True]


def test_upgrade_dry_run_preview_enters_the_scope(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from specify_cli.cli.commands import upgrade as upgrade_module
    from specify_cli.migration.schema_version import MAX_SUPPORTED_SCHEMA

    kittify = tmp_path / ".kittify"
    kittify.mkdir()
    (kittify / "config.yaml").write_text("vcs:\n  type: git\n", encoding="utf-8")
    (kittify / "metadata.yaml").write_text("spec_kitty:\n  version: 4.0.0rc7\n", encoding="utf-8")
    MigrationRunner._stamp_schema_version(kittify, MAX_SUPPORTED_SCHEMA)
    _git(tmp_path, "init", "-q", "-b", "main")
    from charter.activation import pack_manager
    from specify_cli.upgrade import assessment

    seen: dict[str, list[bool]] = {"target": [], "repairs": []}
    real_target = pack_manager.resolve_activation_write_target
    real_repairs = assessment.prepare_upgrade_repairs

    def _target(project_path: Path) -> Any:
        seen["target"].append(in_legacy_activation_scope(project_path))
        return real_target(project_path)

    def _repairs(project_path: Path, **kwargs: Any) -> Any:
        seen["repairs"].append(in_legacy_activation_scope(project_path))
        return real_repairs(project_path, **kwargs)

    monkeypatch.setattr(pack_manager, "resolve_activation_write_target", _target)
    monkeypatch.setattr(assessment, "prepare_upgrade_repairs", _repairs)
    app = typer.Typer(add_completion=False)
    app.command()(upgrade_module.upgrade)
    with contextlib.chdir(tmp_path):
        result = CliRunner().invoke(app, ["--dry-run", "--no-worktrees", "--force"], catch_exceptions=False)
    assert result.exit_code == 0, result.output
    assert seen["target"] and all(seen["target"])
    assert seen["repairs"] and all(seen["repairs"])


# --------------------------------------------------------------------------- #
# Worktrees: the scope matches the canonical root (M3)
# --------------------------------------------------------------------------- #


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


def test_a_lane_worktree_scope_covers_the_canonical_root(tmp_path: Path) -> None:
    main = tmp_path / "main"
    main.mkdir()
    _git(main, "init", "-q", "-b", "main")
    _git(main, "config", "user.email", "t@example.com")
    _git(main, "config", "user.name", "T")
    (main / "README.md").write_text("x\n", encoding="utf-8")
    _git(main, "add", "README.md")
    _git(main, "commit", "-q", "-m", "init")
    lane = main / ".worktrees" / "demo-lane-a"
    _git(main, "worktree", "add", "-q", "-b", "lane-a", str(lane))

    class _CanonicalSpy(_Spy):
        migration_id = "zz_canonical_spy"

        def detect(self, project_path: Path) -> bool:
            self.seen["canonical"] = in_legacy_activation_scope(main)
            self.seen["lane"] = in_legacy_activation_scope(project_path)
            return True

    _CanonicalSpy().detect(lane)
    assert _Spy.seen == {"canonical": True, "lane": True}


def test_legacy_upgrade_scope_tolerates_a_non_git_project(tmp_path: Path) -> None:
    with legacy_upgrade_scope(tmp_path):
        assert in_legacy_activation_scope(tmp_path)
    assert not in_legacy_activation_scope(tmp_path)


# --------------------------------------------------------------------------- #
# Transition-mode pin (WP14 T082 rewrites it): strict outside, legacy inside
# --------------------------------------------------------------------------- #


def _unmigrated(root: Path) -> Path:
    (root / ".kittify").mkdir()
    (root / ".kittify" / "config.yaml").write_text("activated_tactics:\n- T\n", encoding="utf-8")
    return root


def test_outside_the_scope_an_unmigrated_project_is_legacy_and_unmigrated(tmp_path: Path) -> None:
    root = _unmigrated(tmp_path)
    resolved = resolve_ledger_source(root)
    assert (resolved.source, resolved.unmigrated) == (ActivationSource.LEGACY, True)
    ledger = load_activation_ledger(root)
    assert ledger.source is ActivationSource.LEGACY
    assert ledger.raw() == {"activated_tactics": ["T"]}
    with pytest.raises(ActiveCharterConfigError) as caught:
        refuse_unmigrated_deny_write(root)
    assert "spec-kitty upgrade" in caught.value.body


def test_inside_the_scope_the_same_project_reads_legacy_and_is_not_unmigrated(tmp_path: Path) -> None:
    root = _unmigrated(tmp_path)
    with legacy_upgrade_scope(root):
        resolved = resolve_ledger_source(root)
        ledger = load_activation_ledger(root)
        refuse_unmigrated_deny_write(root)  # a migration is not refused here; no migration writes a deny entry
    assert (resolved.source, resolved.unmigrated) == (ActivationSource.LEGACY, False)
    assert ledger.raw() == {"activated_tactics": ["T"]}


def test_a_none_canonical_root_is_not_reused_after_git_init(tmp_path: Path) -> None:
    """Review cycle 1 (LOW): the cache key includes the presence of ``.git``."""
    assert base_module._canonical_root(tmp_path.resolve()) is None
    _git(tmp_path, "init", "-q", "-b", "main")
    assert base_module._canonical_root(tmp_path.resolve()) == tmp_path.resolve()
