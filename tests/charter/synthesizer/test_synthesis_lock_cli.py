"""``charter synthesize`` / ``resynthesize`` hold the run-wide synthesis lock (#6453, WP02).

The lock is held from ANOTHER thread (same-thread re-entry would make every refusal test vacuous)
and the wait is monkeypatched down, so no test waits the real 10 s. Every refusal test is paired
with a lock-free positive control on the same fixture.
"""

from __future__ import annotations

import json
import subprocess
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

import charter.activation.synthesizer.synthesis_lock as lock_module
from charter.activation.synthesizer import FixtureAdapter, synthesize
from charter.activation.synthesizer.manifest import MANIFEST_PATH
from charter.activation.synthesizer.synthesis_lock import synthesis_lock, synthesis_lock_path
from specify_cli.cli.commands.charter import charter_app
from tests.charter.synthesizer.test_synthesize_activation_append import _TACTIC, _invoke, _request, _seed_project

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

runner = CliRunner()

_HELD = "CHARTER_SYNTHESIS_LOCK_HELD"
_RUN_ID = "01BBBBBBBBBBBBBBBBBBBBBBBBB"


@pytest.fixture(autouse=True)
def _short_wait(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(lock_module, "_SYNTHESIS_LOCK_TIMEOUT_S", 0.2)


@contextmanager
def _held_by_other_thread(repo_root: Path) -> Iterator[Path]:
    acquired = threading.Event()
    release = threading.Event()

    def _holder() -> None:
        with synthesis_lock(repo_root):
            acquired.set()
            release.wait(timeout=60)

    thread = threading.Thread(target=_holder, daemon=True)
    thread.start()
    assert acquired.wait(timeout=10), "holder thread never acquired the lock"
    try:
        yield synthesis_lock_path(repo_root)
    finally:
        release.set()
        thread.join(timeout=10)


def _snapshot(repo_root: Path) -> dict[str, bytes]:
    """Every file under the worktree (git metadata, where the lock file lives, excluded), by bytes."""
    return {str(p.relative_to(repo_root)): p.read_bytes() for p in sorted(repo_root.rglob("*")) if p.is_file() and ".git" not in p.relative_to(repo_root).parts}


def _synthesize(isolate: Callable[..., Path], *extra: str) -> Any:
    return _invoke(isolate, ["synthesize", "--adapter", "fixture", *extra], _request(_RUN_ID))


def _resynthesize_tactic(isolate: Callable[..., Path], *extra: str) -> Any:
    return _invoke(isolate, ["resynthesize", "--adapter", "fixture", "--topic", f"tactic:{_TACTIC}", *extra], _request("01CCCCCCCCCCCCCCCCCCCCCCCCC"))


def test_synthesize_refuses_when_lock_held_and_writes_nothing(tmp_path: Path, charter_cwd_isolation: Callable[..., Path]) -> None:
    _seed_project(tmp_path, activated_tactics=None)
    before = _snapshot(tmp_path)

    with _held_by_other_thread(tmp_path) as lock_path:
        result = _synthesize(charter_cwd_isolation)

    assert result.exit_code == 1, result.output
    assert _HELD in result.output
    assert str(lock_path) in "".join(result.output.split())  # rich wraps long lines; compare without whitespace
    assert _snapshot(tmp_path) == before


def test_synthesize_with_lock_free_writes_files(tmp_path: Path, charter_cwd_isolation: Callable[..., Path]) -> None:
    """Positive control for the refusal test: same fixture, lock free."""
    _seed_project(tmp_path, activated_tactics=None)
    before = _snapshot(tmp_path)

    result = _synthesize(charter_cwd_isolation)

    assert result.exit_code == 0, result.output
    assert _HELD not in result.output
    assert (tmp_path / MANIFEST_PATH).is_file()
    assert _snapshot(tmp_path) != before


def test_synthesize_json_envelope_carries_the_lock_code(tmp_path: Path, charter_cwd_isolation: Callable[..., Path]) -> None:
    _seed_project(tmp_path, activated_tactics=None)

    with _held_by_other_thread(tmp_path) as lock_path:
        result = _synthesize(charter_cwd_isolation, "--json")

    assert result.exit_code == 1, result.output
    envelope = json.loads(result.stdout)
    assert envelope["result"] == "failure"
    assert envelope["code"] == _HELD
    assert any(str(lock_path) in warning for warning in envelope["warnings"])
    assert envelope["written_artifacts"] == []


def test_synthesize_dry_run_takes_no_lock(tmp_path: Path, charter_cwd_isolation: Callable[..., Path]) -> None:
    _seed_project(tmp_path, activated_tactics=None)
    before = _snapshot(tmp_path)

    with _held_by_other_thread(tmp_path):
        result = _synthesize(charter_cwd_isolation, "--dry-run")

    assert _HELD not in result.output
    assert result.exit_code == 0, result.output
    assert _snapshot(tmp_path) == before


def test_synthesize_dry_run_evidence_takes_no_lock(tmp_path: Path, charter_cwd_isolation: Callable[..., Path]) -> None:
    """Unpatched evidence path (as in the #6443 dry-run-evidence test): needs interview answers on disk."""
    _seed_project(tmp_path, activated_tactics=None)
    answers = tmp_path / ".kittify" / "charter" / "interview" / "answers.yaml"
    answers.parent.mkdir(parents=True, exist_ok=True)
    answers.write_text(
        "schema_version: '1'\nmission: software-dev\nprofile: minimal\nanswers:\n"
        "  mission_type: software_dev\nselected_paradigms: []\nselected_directives: []\navailable_tools: []\n",
        encoding="utf-8",
    )
    charter_cwd_isolation(tmp_path)
    args = ["synthesize", "--dry-run-evidence", "--skip-code-evidence", "--skip-corpus", "--json"]
    before = _snapshot(tmp_path)

    control = runner.invoke(charter_app, args)  # lock free
    with _held_by_other_thread(tmp_path):
        held = runner.invoke(charter_app, args)

    assert control.exit_code == 0, control.output
    assert held.exit_code == 0, held.output
    assert _HELD not in held.output
    assert _snapshot(tmp_path) == before


def test_resynthesize_topic_refuses_when_lock_held_and_writes_nothing(tmp_path: Path, charter_cwd_isolation: Callable[..., Path]) -> None:
    _seed_project(tmp_path, activated_tactics=None)
    synthesize(_request("01AAAAAAAAAAAAAAAAAAAAAAAAA"), adapter=FixtureAdapter(), repo_root=tmp_path)
    before = _snapshot(tmp_path)

    with _held_by_other_thread(tmp_path):
        result = _resynthesize_tactic(charter_cwd_isolation)

    assert result.exit_code == 1, result.output
    assert _HELD in result.output
    assert _snapshot(tmp_path) == before

    # Positive control on the same fixture, lock free.
    free = _resynthesize_tactic(charter_cwd_isolation)
    assert free.exit_code == 0, free.output
    assert _HELD not in free.output


def test_resynthesize_list_topics_takes_no_lock(tmp_path: Path, charter_cwd_isolation: Callable[..., Path]) -> None:
    _seed_project(tmp_path, activated_tactics=None)
    synthesize(_request("01AAAAAAAAAAAAAAAAAAAAAAAAA"), adapter=FixtureAdapter(), repo_root=tmp_path)
    before = _snapshot(tmp_path)

    with _held_by_other_thread(tmp_path):
        result = _invoke(charter_cwd_isolation, ["resynthesize", "--adapter", "fixture", "--list-topics"], _request("01CCCCCCCCCCCCCCCCCCCCCCCCC"))

    assert _HELD not in result.output
    assert result.exit_code == 0, result.output
    assert _snapshot(tmp_path) == before


# --- FR-002 ordering: the lock is taken BEFORE the legacy convergence (#6453, cycle 2) -----------

_LEGACY_DIRECTIVE = "002-mission-type-scope-directive.directive.yaml"
_RENAMED_DIRECTIVE = "002-project-intent-directive.directive.yaml"
_LEGACY_DIRS = (Path(".kittify") / "charter-packs" / "directive", Path(".kittify") / "charter" / "generated" / "directives")
_LEGACY_BODY = "id: PROJECT_002\ntitle: Mission Type Scope Directive\nintent: keep the scope\nschema_version: '1.0'\n"


def _seed_legacy_directive(repo_root: Path) -> None:
    """Add a legacy ``mission-type-scope-directive`` that ``rename_legacy_project_intent_directive`` reports pending."""
    for directory in _LEGACY_DIRS:
        (repo_root / directory).mkdir(parents=True, exist_ok=True)
        (repo_root / directory / _LEGACY_DIRECTIVE).write_text(_LEGACY_BODY, encoding="utf-8")


def _legacy_files(repo_root: Path) -> list[bool]:
    return [(repo_root / d / _LEGACY_DIRECTIVE).exists() for d in _LEGACY_DIRS]


def _renamed_files(repo_root: Path) -> list[bool]:
    return [(repo_root / d / _RENAMED_DIRECTIVE).exists() for d in _LEGACY_DIRS]


def _assert_legacy_untouched(repo_root: Path) -> None:
    assert _legacy_files(repo_root) == [True, True]
    assert _renamed_files(repo_root) == [False, False]


def test_synthesize_takes_the_lock_before_the_legacy_convergence(tmp_path: Path, charter_cwd_isolation: Callable[..., Path]) -> None:
    _seed_project(tmp_path, activated_tactics=None)
    _seed_legacy_directive(tmp_path)
    before = _snapshot(tmp_path)

    with _held_by_other_thread(tmp_path):
        result = _synthesize(charter_cwd_isolation)

    assert result.exit_code == 1, result.output
    assert _HELD in result.output
    _assert_legacy_untouched(tmp_path)  # the convergence did not run ahead of the lock
    assert _snapshot(tmp_path) == before

    # Positive control, same fixture, lock free: the convergence does write.
    free = _synthesize(charter_cwd_isolation)
    assert free.exit_code == 0, free.output
    assert _renamed_files(tmp_path) == [True, True]
    assert _legacy_files(tmp_path) == [False, False]


def test_resynthesize_takes_the_lock_before_the_legacy_convergence(tmp_path: Path, charter_cwd_isolation: Callable[..., Path]) -> None:
    _seed_project(tmp_path, activated_tactics=None)
    synthesize(_request("01AAAAAAAAAAAAAAAAAAAAAAAAA"), adapter=FixtureAdapter(), repo_root=tmp_path)
    _seed_legacy_directive(tmp_path)
    before = _snapshot(tmp_path)

    with _held_by_other_thread(tmp_path):
        result = _resynthesize_tactic(charter_cwd_isolation)

    assert result.exit_code == 1, result.output
    assert _HELD in result.output
    _assert_legacy_untouched(tmp_path)
    assert _snapshot(tmp_path) == before

    # Positive control, same fixture, lock free: the convergence does write.
    free = _resynthesize_tactic(charter_cwd_isolation)
    assert free.exit_code == 0, free.output
    assert _renamed_files(tmp_path) == [True, True]
    assert _legacy_files(tmp_path) == [False, False]


# --- resynthesize --json carries the lock code (#6453) ---------------------------------------------


def test_resynthesize_json_envelope_carries_the_lock_code(tmp_path: Path, charter_cwd_isolation: Callable[..., Path]) -> None:
    _seed_project(tmp_path, activated_tactics=None)
    synthesize(_request("01AAAAAAAAAAAAAAAAAAAAAAAAA"), adapter=FixtureAdapter(), repo_root=tmp_path)

    with _held_by_other_thread(tmp_path) as lock_path:
        result = _resynthesize_tactic(charter_cwd_isolation, "--json")

    assert result.exit_code == 1, result.output
    envelope = json.loads(result.stdout)
    assert envelope["code"] == _HELD
    assert str(lock_path) in "".join(json.dumps(envelope).split()).replace("\\\\", "\\")


# --- activation restamp warns and skips while a synthesis run holds the lock (#6453) --------------

_WARNING_FRAGMENT = "bundle hash was not refreshed"


def test_activate_saves_warns_and_skips_restamp_while_lock_is_held(tmp_path: Path) -> None:
    from charter.activation.synthesizer.manifest import load_yaml
    from charter.bundle import compute_bundle_content_hash
    from tests.charter.test_activate_restamps_bundle_hash import _project

    repo = _project(tmp_path)
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True, capture_output=True)
    stamped = load_yaml(repo / MANIFEST_PATH).bundle_content_hash
    args = ["activate", "--repo-root", str(repo), "--no-compile", "directive", "010-specification-fidelity-requirement"]

    with _held_by_other_thread(repo) as lock_path:
        result = runner.invoke(charter_app, args)

    assert result.exit_code == 0, result.output
    assert "Traceback" not in result.output
    assert _WARNING_FRAGMENT in " ".join(result.output.split())
    assert str(lock_path) in "".join(result.output.split())
    assert "010-specification-fidelity-requirement" in (repo / ".kittify" / "charter" / "charter.yaml").read_text(encoding="utf-8")
    assert load_yaml(repo / MANIFEST_PATH).bundle_content_hash == stamped  # restamp skipped
    assert compute_bundle_content_hash(repo) != stamped  # so the manifest is genuinely stale

    # Positive control, lock free: the next activation change restamps.
    free = runner.invoke(charter_app, args)
    assert free.exit_code == 0, free.output
    assert _WARNING_FRAGMENT not in " ".join(free.output.split())
    assert load_yaml(repo / MANIFEST_PATH).bundle_content_hash == compute_bundle_content_hash(repo)
