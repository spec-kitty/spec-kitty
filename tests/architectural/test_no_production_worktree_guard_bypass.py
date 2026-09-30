"""Architectural guardrail for the mission-creation worktree-context guard.

``create_mission_core(..., allow_worktree_context=True)`` bypasses the
operator-safety guard that refuses to scaffold a mission when the process
``cwd`` resolves inside a git worktree (protecting operators from accidentally
creating a mission inside a lane worktree instead of the project-root
checkout).  The bypass exists solely for programmatic *test* callers -- notably
``tests/_factories.make_mission()`` -- which pass an explicit isolated
``repo_root`` while the test process itself runs from within a lane worktree.

PR #2629 review (architect-alphonso, MEDIUM): the flag is an undefended
public affordance on a core API -- a future *production* caller could set it to
``True`` and silently defeat the operator-safety guard.  This guard pins the
invariant that no ``src/`` call site ever passes ``allow_worktree_context=True``.

If the ``cwd``-vs-target guard is ever reshaped to validate the resolution
target instead (so the flag can be removed entirely), delete this guard with
that change.
"""

from __future__ import annotations

import ast
import json
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

pytestmark = pytest.mark.architectural

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SRC_ROOT = _REPO_ROOT / "src"
_BYPASS_KW = "allow_worktree_context"


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def _ownership_refusal_topologies(tmp_path: Path) -> tuple[Path, dict[str, Path]]:
    """Build one primary and reusable nested/foreign/broken refusal targets."""
    primary = tmp_path / "primary"
    (primary / ".kittify" / "templates").mkdir(parents=True)
    (primary / ".kittify" / "templates" / "spec-template.md").write_text("# Spec Template\n", encoding="utf-8")
    (primary / ".kittify" / "config.yaml").write_text("mission_type_activations:\n  - software-dev\n", encoding="utf-8")
    (primary / "kitty-specs").mkdir()
    (primary / "kitty-specs" / ".gitkeep").touch()
    _git(primary, "init", "--initial-branch=main")
    _git(primary, "config", "user.name", "Spec Kitty Tests")
    _git(primary, "config", "user.email", "spec-kitty-tests@example.invalid")
    _git(primary, "add", ".")
    _git(primary, "commit", "-m", "Initial project")

    linked = tmp_path / "linked"
    _git(primary, "worktree", "add", "-b", "owned-lane", str(linked), "HEAD")
    nested = linked / "nested"
    nested.mkdir()

    foreign = tmp_path / "foreign"
    foreign.mkdir()
    _git(foreign, "init", "--initial-branch=foreign")

    broken = tmp_path / "broken"
    broken.mkdir()
    (broken / ".git").write_text(f"gitdir: {tmp_path / 'missing-gitdir'}\n", encoding="utf-8")
    return primary.resolve(), {
        "OWNERSHIP_NESTED": nested.resolve(),
        "OWNERSHIP_FOREIGN": foreign.resolve(),
        "OWNERSHIP_BROKEN_POINTER": broken.resolve(),
    }


def _json_object(output: str) -> dict[str, object]:
    for line in output.splitlines():
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    # An indented (multi-line) document, as the shared owned-checkout refusal
    # renderer (``emit_owned_refusal``) prints it: decode from the first brace.
    start = output.find("{")
    if start != -1:
        try:
            document, _end = json.JSONDecoder().raw_decode(output[start:])
        except json.JSONDecodeError:
            document = None
        if isinstance(document, dict):
            return document
    raise AssertionError(f"no JSON object in CLI output: {output!r}")


def _worktree_bypass_uses(path: Path) -> list[str]:
    """Return call sites in ``path`` that pass ``allow_worktree_context=True``."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    hits: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        for kw in node.keywords:
            if kw.arg == _BYPASS_KW and isinstance(kw.value, ast.Constant) and kw.value.value is True:
                hits.append(f"{path}:{node.lineno} passes {_BYPASS_KW}=True")
    return hits


def test_no_production_caller_bypasses_worktree_guard() -> None:
    offenders: list[str] = []
    for path in sorted(_SRC_ROOT.rglob("*.py")):
        offenders.extend(_worktree_bypass_uses(path))

    assert not offenders, (
        "Production code must not bypass the mission-creation worktree-context "
        "guard -- allow_worktree_context=True is reserved for programmatic test "
        "callers (tests/_factories.make_mission). Offending src call sites:\n" + "\n".join(offenders)
    )


def test_detector_bites_on_a_planted_bypass(tmp_path: Path) -> None:
    """Non-vacuity: the detector must FLAG a synthetic production bypass.

    Guards against the scanner silently rotting to always-green (e.g. if the
    keyword is renamed and this guard is not co-updated).
    """
    planted = tmp_path / "planted.py"
    planted.write_text(
        "create_mission_core(repo_root=root, allow_worktree_context=True)\n",
        encoding="utf-8",
    )
    assert _worktree_bypass_uses(planted), "detector failed to flag a planted bypass"

    # And it must NOT fire on the legitimate default (=False) or absence.
    clean = tmp_path / "clean.py"
    clean.write_text(
        "create_mission_core(repo_root=root, allow_worktree_context=False)\ncreate_mission_core(repo_root=root)\n",
        encoding="utf-8",
    )
    assert not _worktree_bypass_uses(clean)


@pytest.mark.parametrize(
    "expected_code",
    [
        "OWNERSHIP_NESTED",
        "OWNERSHIP_FOREIGN",
        "OWNERSHIP_BROKEN_POINTER",
    ],
)
def test_mission_create_and_next_share_structured_ownership_refusals(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    expected_code: str,
) -> None:
    """Both CLI surfaces must expose the same complete refusal envelope."""
    from specify_cli import app as root_app
    from specify_cli.cli.commands import next_cmd
    from specify_cli.cli.commands.agent import mission as mission_module

    primary, targets = _ownership_refusal_topologies(tmp_path)
    target = targets[expected_code]
    monkeypatch.chdir(primary)
    monkeypatch.setattr(mission_module, "locate_project_root", lambda *_: primary)
    monkeypatch.setattr(next_cmd, "locate_project_root", lambda: primary)
    runner = CliRunner()

    create_result = runner.invoke(
        mission_module.app,
        [
            "create",
            f"refusal-{expected_code.lower().replace('_', '-')}",
            "--owned-checkout",
            str(target),
            "--json",
        ],
    )
    next_result = runner.invoke(
        root_app,
        [
            "next",
            "--mission",
            "refusal-probe",
            "--owned-checkout",
            str(target),
            "--json",
        ],
    )

    assert create_result.exit_code == next_result.exit_code == 1
    create_payload = _json_object(create_result.stdout)
    next_payload = _json_object(next_result.stdout)
    assert create_payload["success"] is next_payload["success"] is False
    assert create_payload["error_code"] == next_payload["error_code"] == expected_code
    assert create_payload["error"]
    assert next_payload["error"]


def test_owned_refusal_never_calls_legacy_worktree_navigation_hint(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Typed ownership errors bypass the message-substring legacy hint path."""
    from specify_cli.cli.commands.agent import mission as mission_module
    from specify_cli.cli.commands.agent import mission_create

    primary, targets = _ownership_refusal_topologies(tmp_path)
    monkeypatch.chdir(primary)
    monkeypatch.setattr(mission_module, "locate_project_root", lambda *_: primary)
    hint_calls: list[tuple[str, str]] = []
    monkeypatch.setattr(
        mission_create,
        "_print_worktree_navigation_hint",
        lambda slug, message: hint_calls.append((slug, message)),
    )

    result = CliRunner().invoke(
        mission_module.app,
        [
            "create",
            "nested-refusal",
            "--owned-checkout",
            str(targets["OWNERSHIP_NESTED"]),
        ],
    )

    assert result.exit_code == 1
    assert hint_calls == []
    assert "OWNERSHIP_NESTED" not in result.stdout
