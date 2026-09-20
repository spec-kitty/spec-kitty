"""Targeted CLI coverage for ``spec-kitty charter resynthesize``."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands import charter as charter_module
from specify_cli.cli.commands.charter import app as charter_app

pytestmark = pytest.mark.fast


runner = CliRunner()


@pytest.fixture(autouse=True)
def _isolate_cwd_from_worktree_guard(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """#4785 Finding 3 / WP04 reconciliation: ``resynthesize.py`` now fails
    closed via the WP02 write-root guard (``resolve_charter_write_root``),
    probed against the REAL process cwd -- deliberately NOT patchable
    through this suite's ``find_repo_root`` mocks, since the guard exists
    precisely to catch cwd/``find_repo_root`` divergence. Without isolating
    cwd here, every test below would spuriously trip the guard whenever the
    test process happens to run from inside a real linked git worktree
    (e.g. a spec-kitty lane worktree) -- unrelated to anything this suite
    exercises. ``tmp_path`` is a plain (non-git) directory, so chdir'ing
    into it makes the guard's kernel ``git_topology`` probe degrade safely
    (not-a-repo -> not-a-linked-worktree, no raise).
    """
    monkeypatch.chdir(tmp_path)


@dataclass
class _EvidenceResult:
    bundle: object
    warnings: list[str]


def test_resynthesize_list_topics_checks_bundle_compatibility(tmp_path: Path, monkeypatch) -> None:
    charter_dir = tmp_path / ".kittify" / "charter"
    charter_dir.mkdir(parents=True, exist_ok=True)
    # consolidate-charter-bundle (#2773): the compat gate keys off charter.yaml
    # (the authoritative v2 bundle), NOT the retired metadata.yaml.
    (charter_dir / "charter.yaml").write_text("metadata:\n  bundle_schema_version: 2\n", encoding="utf-8")

    compatibility_calls: list[Path] = []

    monkeypatch.setattr(
        "specify_cli.cli.commands.charter.find_repo_root",
        lambda: tmp_path,
    )
    monkeypatch.setattr(
        "specify_cli.cli.commands.charter._assert_bundle_compatible",
        lambda path: compatibility_calls.append(path),
    )
    monkeypatch.setattr(
        "specify_cli.cli.commands.charter._collect_evidence_result",
        lambda *args, **kwargs: _EvidenceResult(bundle={"bundle": True}, warnings=[]),
    )
    monkeypatch.setattr(
        "specify_cli.cli.commands.charter._build_synthesis_request",
        lambda *args, **kwargs: ({"request": True}, object()),
    )
    monkeypatch.setattr(
        "specify_cli.cli.commands.charter._list_resynthesis_topics",
        lambda *args, **kwargs: {"directive": ["directive:PROJECT_001"]},
    )

    result = runner.invoke(charter_app, ["resynthesize", "--list-topics", "--json"])

    assert result.exit_code == 0, result.output
    assert compatibility_calls == [charter_dir]
    assert '"directive:PROJECT_001"' in result.output


def test_status_list_checks_bundle_compatibility(tmp_path: Path, monkeypatch) -> None:
    charter_dir = tmp_path / ".kittify" / "charter"
    charter_dir.mkdir(parents=True, exist_ok=True)
    # consolidate-charter-bundle (#2773): the compat gate keys off charter.yaml
    # (the authoritative v2 bundle), NOT the retired metadata.yaml.
    (charter_dir / "charter.yaml").write_text("metadata:\n  bundle_schema_version: 2\n", encoding="utf-8")

    compatibility_calls: list[Path] = []

    monkeypatch.setattr(
        "specify_cli.cli.commands.charter.find_repo_root",
        lambda: tmp_path,
    )
    monkeypatch.setattr(
        "specify_cli.cli.commands.charter._assert_bundle_compatible",
        lambda path: compatibility_calls.append(path),
    )
    monkeypatch.setattr(
        "specify_cli.cli.commands.charter._collect_charter_sync_status",
        lambda repo_root: {"repo_root": str(repo_root)},
    )
    monkeypatch.setattr(
        "specify_cli.cli.commands.charter._collect_synthesis_status",
        lambda repo_root, include_provenance=False: {"present": False},
    )

    result = runner.invoke(charter_app, ["status", "--json"])

    assert result.exit_code == 0, result.output
    assert compatibility_calls == [charter_dir]


def test_status_compat_gate_ignores_retired_metadata_yaml(tmp_path: Path, monkeypatch) -> None:
    """#2773 regression: metadata.yaml alone must NOT trigger the compat gate.

    The fold migration deletes ``metadata.yaml``; if the gate keyed off it, a
    real post-migration v2 project — which has ``charter.yaml`` but no
    ``metadata.yaml`` — would silently skip the bundle-compatibility check.
    """
    charter_dir = tmp_path / ".kittify" / "charter"
    charter_dir.mkdir(parents=True, exist_ok=True)
    # Only the retired metadata.yaml present; no charter.yaml.
    (charter_dir / "metadata.yaml").write_text("bundle_schema_version: 2\n", encoding="utf-8")

    compatibility_calls: list[Path] = []
    monkeypatch.setattr("specify_cli.cli.commands.charter.find_repo_root", lambda: tmp_path)
    monkeypatch.setattr(
        "specify_cli.cli.commands.charter._assert_bundle_compatible",
        lambda path: compatibility_calls.append(path),
    )
    monkeypatch.setattr(
        "specify_cli.cli.commands.charter._collect_charter_sync_status",
        lambda repo_root: {"repo_root": str(repo_root)},
    )
    monkeypatch.setattr(
        "specify_cli.cli.commands.charter._collect_synthesis_status",
        lambda repo_root, include_provenance=False: {"present": False},
    )

    result = runner.invoke(charter_app, ["status", "--json"])

    assert result.exit_code == 0, result.output
    assert compatibility_calls == [], (
        "retired metadata.yaml must not trigger the compat gate; it must key off charter.yaml (else v2 bundles silently skip the check)"
    )


def test_collect_charter_sync_status_passes_metadata_path_to_stale_check(tmp_path: Path, monkeypatch) -> None:
    charter_dir = tmp_path / ".kittify" / "charter"
    charter_dir.mkdir(parents=True, exist_ok=True)
    (charter_dir / "charter.md").write_text("# Charter\n", encoding="utf-8")
    (charter_dir / "governance.yaml").write_text("governance: true\n", encoding="utf-8")
    (charter_dir / "directives.yaml").write_text("directives: []\n", encoding="utf-8")
    metadata_path = charter_dir / "metadata.yaml"
    metadata_path.write_text("bundle_schema_version: 2\n", encoding="utf-8")

    seen_metadata_paths: list[Path] = []

    monkeypatch.setattr(
        charter_module,
        "ensure_charter_bundle_fresh",
        lambda repo_root: SimpleNamespace(canonical_root=tmp_path),
    )
    monkeypatch.setattr(
        "charter.hasher.is_stale",
        lambda charter_path, path: (
            seen_metadata_paths.append(path) or False,
            "current",
            "stored",
        ),
    )

    from glossary import entity_pages as entity_pages_module

    class _FakeRenderer:
        def __init__(self, repo_root: Path) -> None:
            self.repo_root = repo_root

        def generate_all(self) -> None:
            return None

    monkeypatch.setattr(
        entity_pages_module,
        "GlossaryEntityPageRenderer",
        _FakeRenderer,
    )
    monkeypatch.setattr(
        "ruamel.yaml.YAML.load",
        lambda self, text: {"timestamp_utc": "2026-01-01T00:00:00Z"},
    )

    status = charter_module._collect_charter_sync_status(tmp_path)

    assert seen_metadata_paths == [metadata_path]
    assert status["charter_path"] == ".kittify/charter/charter.md"
