"""Executed audit: every migration that resolves the canonical repo root declares the flag (#6539).

The audit runs the full shipped registry against a project that is not inside
any git repository, with ``charter.resolution.resolve_canonical_repo_root``
instrumented at every import site. It records which migration was executing
when the resolver was reached (directly or transitively) and requires each of
them to declare ``requires_git_repository``. This is an execution, not a grep:
transitive callers through ``charter.activation.*`` are caught as well.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

import charter.resolution as resolution
from specify_cli.upgrade.migrations import auto_discover_migrations
from specify_cli.upgrade.migrations.base import BaseMigration
from specify_cli.upgrade.registry import MigrationRegistry
from specify_cli.upgrade.runner import MigrationRunner

pytestmark = [pytest.mark.unit, pytest.mark.slow]


def _manifest_ids() -> list[str]:
    manifest = Path(sys.modules[BaseMigration.__module__].__file__ or "").parent / "order_manifest.txt"
    ids = []
    for line in manifest.read_text(encoding="utf-8").splitlines():
        entry = line.split("#", 1)[0].strip()
        if entry:
            ids.append(entry)
    return ids


def _project(root: Path, *, populated: bool = False) -> Path:
    kittify = root / ".kittify"
    kittify.mkdir(parents=True)
    (kittify / "metadata.yaml").write_text("spec_kitty:\n  version: 0.1.0\n", encoding="utf-8")
    if populated:
        # Charter, config, specs and ignore file present, so migrations that early-return on a
        # bare project reach their real code paths.
        (kittify / "charter").mkdir()
        (kittify / "charter" / "charter.md").write_text("# Charter\n", encoding="utf-8")
        (kittify / "config.yaml").write_text("agents:\n  available:\n    - claude\n", encoding="utf-8")
        (root / "kitty-specs").mkdir()
        (root / ".gitignore").write_text(".worktrees/\n", encoding="utf-8")
        (root / ".claude" / "commands").mkdir(parents=True)
    return root


def _instrument(monkeypatch: pytest.MonkeyPatch, current: list[str | None], callers: set[str]) -> None:
    original = resolution.resolve_canonical_repo_root

    def recording(path: Path) -> Path:
        if current[0] is not None:
            callers.add(current[0])
        return original(path)

    recording.__dict__["cache_clear"] = original.cache_clear  # mirror the resolver's public attribute
    # Rebind every module attribute that IS the resolver (covers ``from ... import`` aliases).
    for module in list(sys.modules.values()):
        namespace = getattr(module, "__dict__", None)
        if not isinstance(namespace, dict):
            continue
        for name, value in list(namespace.items()):
            if value is original:
                monkeypatch.setattr(module, name, recording, raising=True)


def _track(monkeypatch: pytest.MonkeyPatch, migration_cls: type[BaseMigration], current: list[str | None]) -> None:
    for method in ("detect", "can_apply", "apply"):
        original: Callable[..., Any] = getattr(migration_cls, method)

        def wrapper(self: BaseMigration, *args: Any, _original: Callable[..., Any] = original, **kwargs: Any) -> Any:
            previous = current[0]
            current[0] = self.migration_id
            try:
                return _original(self, *args, **kwargs)
            finally:
                current[0] = previous

        monkeypatch.setattr(migration_cls, method, wrapper)


@pytest.mark.parametrize("populated", [False, True], ids=["bare", "populated"])
def test_every_resolver_caller_declares_requires_git_repository(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, populated: bool) -> None:
    auto_discover_migrations()
    project = _project(tmp_path, populated=populated)
    current: list[str | None] = [None]
    callers: set[str] = set()
    _instrument(monkeypatch, current, callers)

    migrations = MigrationRegistry.get_all()
    assert [m.migration_id for m in migrations] == _manifest_ids()
    for migration in migrations:
        _track(monkeypatch, type(migration), current)

    # Exercise every detect/can_apply/apply directly (bypassing the runner's gate, so the
    # audit judges what the migration really does, not what the flag already hides).
    for migration in migrations:
        for step in (
            lambda m=migration: m.detect(project),
            lambda m=migration: m.can_apply(project),
            lambda m=migration: m.apply(project, dry_run=True),
        ):
            try:
                step()
            except Exception:
                # audit probe: only the resolver call matters, not the migration's own outcome
                continue

    flagged = {m.migration_id for m in migrations if m.requires_git_repository}
    undeclared = sorted(callers - flagged)
    assert not undeclared, f"migrations reaching resolve_canonical_repo_root without requires_git_repository: {undeclared}"
    assert "3.2.0rc35_unified_bundle" in callers, "the instrument must observe the known direct caller"


def test_full_registry_run_outside_a_repository_reaches_the_last_migration(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    auto_discover_migrations()
    project = _project(tmp_path)
    ids = _manifest_ids()
    reached: list[str] = []
    runner = MigrationRunner(project)
    original = runner._apply_migration

    def spy(migration: BaseMigration, metadata: Any, dry_run: bool) -> Any:
        reached.append(migration.migration_id)
        return original(migration, metadata, dry_run)

    monkeypatch.setattr(runner, "_apply_migration", spy)
    result = runner.upgrade(_latest_target(), include_worktrees=False)

    assert not result.errors, result.errors
    assert reached and reached[-1] == ids[-1]


def _latest_target() -> str:
    from specify_cli import __version__

    return __version__
