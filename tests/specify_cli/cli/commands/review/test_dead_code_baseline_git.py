"""Real-git half of the dead-code baseline regression suite (issue #989).

Split out of ``test_dead_code_baseline.py``: every test here drives the real
``git`` binary through ``subprocess`` (directly via :func:`_git`, or indirectly
by letting ``scan_dead_code``'s ``git diff`` run against a real repository), so
the module carries ``git_repo`` and must NOT carry ``fast`` — see
``tests/architectural/test_pytest_marker_correctness.py`` (Rules 1 and 2) and
``docs/context/testing-taxonomy.md`` under "Fast" / "Git Repo". The
subprocess-free half — including the FR-016 ``FileNotFoundError``-injection
guard — stays ``fast`` in ``test_dead_code_baseline.py``.

What this half pins:

* A failed ``git diff`` (no repository at all) is *undeterminable*, never a
  clean zero (FR-015).
* The changed-source discovery walks every supported Python path, including
  files outside a ``src/`` marker directory, and reports a non-Python-only
  change set as undeterminable rather than clean (FR-016's non-Python-layout
  fixture).
* The installed ``python -m specify_cli review`` command path invokes ``git``
  and nothing else — no external reference-search executable (FR-014).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from specify_cli.cli.commands.review._dead_code import _discover_changed_symbols
from tests._support.ansi import strip_ansi
from tests.specify_cli.cli.commands.review._dead_code_fixtures import scan

# ``non_sandbox``: these tests spawn the real git binary and the installed CLI,
# which mutmut's forked sandbox cannot host (ADR 2026-04-20-1).
pytestmark = [
    pytest.mark.integration,
    pytest.mark.git_repo,
    pytest.mark.non_sandbox,
]


def _git(repo_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )


def _git_repo(tmp_path: Path) -> tuple[Path, str]:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _git(repo_root, "init", "-q")
    _git(repo_root, "config", "user.name", "Dead Code Test")
    _git(repo_root, "config", "user.email", "dead-code-test@example.invalid")
    (repo_root / "README.md").write_text("# baseline\n", encoding="utf-8")
    _git(repo_root, "add", "README.md")
    _git(repo_root, "commit", "-qm", "baseline")
    baseline = _git(repo_root, "rev-parse", "HEAD").stdout.strip()
    return repo_root, baseline


def test_non_git_repository_is_undeterminable(
    tmp_path: Path,
) -> None:
    """A failed Git diff must never collapse to the clean-zero verdict."""
    findings, output = scan(
        tmp_path,
        "0000000000000000000000000000000000000000",
    )

    assert findings == [
        {
            "type": "dead_code_undeterminable",
            "diagnostic_code": "MISSION_REVIEW_DEAD_CODE_UNDETERMINABLE",
            "reason": "git diff failed",
            "remediation": (
                "Verify the baseline commit and Git repository, then rerun "
                "`spec-kitty review`."
            ),
        }
    ]
    assert "MISSION_REVIEW_DEAD_CODE_UNDETERMINABLE" in output
    assert "0 unreferenced public symbols" not in output


def test_unsupported_non_python_change_is_not_applicable(tmp_path: Path) -> None:
    """A docs-only change is not applicable (#5283), never a false clean zero.

    Re-pinned from ``..._is_undeterminable``: #2987 FR-015/016 still forbids a
    false "0 unreferenced" clean zero, which this keeps; the verdict weight
    changes from a hard undeterminable failure to a non-failing note.
    """
    repo_root, baseline = _git_repo(tmp_path)
    docs_dir = repo_root / "docs"
    docs_dir.mkdir()
    (docs_dir / "guide.md").write_text("not Python\n", encoding="utf-8")
    _git(repo_root, "add", "docs/guide.md")
    _git(repo_root, "commit", "-qm", "add docs")

    findings, output = scan(repo_root, baseline)

    assert [f["type"] for f in findings] == ["dead_code_not_applicable"]
    assert findings[0]["diagnostic_code"] == "MISSION_REVIEW_DEAD_CODE_NOT_APPLICABLE"
    assert findings[0]["unsupported_extensions"] == ".md"
    assert findings[0]["excluded_test_paths"] == "0"
    assert "not applicable" in output
    assert "0 unreferenced public symbols" not in output


def test_supported_python_change_with_no_public_symbols_is_clean(tmp_path: Path) -> None:
    repo_root, baseline = _git_repo(tmp_path)
    package_dir = repo_root / "package"
    package_dir.mkdir()
    (package_dir / "private.py").write_text(
        "def _private_helper() -> None:\n    return None\n",
        encoding="utf-8",
    )
    _git(repo_root, "add", "package/private.py")
    _git(repo_root, "commit", "-qm", "add private helper")

    findings, output = scan(repo_root, baseline)

    assert findings == []
    assert "0 unreferenced public symbols" in output


def test_mixed_python_layout_discovers_every_supported_path(tmp_path: Path) -> None:
    """A src marker must not hide a public symbol added outside src."""
    repo_root, baseline = _git_repo(tmp_path)
    src_dir = repo_root / "src"
    src_dir.mkdir()
    (src_dir / "marker.py").write_text("VALUE = 1\n", encoding="utf-8")
    package_dir = repo_root / "package"
    package_dir.mkdir()
    (package_dir / "dead.py").write_text(
        "def PublicMixedDead() -> None:\n    return None\n",
        encoding="utf-8",
    )
    _git(repo_root, "add", "src/marker.py", "package/dead.py")
    _git(repo_root, "commit", "-qm", "add mixed Python layout")

    discovery = _discover_changed_symbols(repo_root, baseline)
    findings, output = scan(repo_root, baseline)

    assert discovery.error is None
    assert set(discovery.changed_paths) == {"src/marker.py", "package/dead.py"}
    assert discovery.symbols == (("PublicMixedDead", "package/dead.py"),)
    assert findings == [
        {
            "type": "dead_code",
            "symbol": "PublicMixedDead",
            "file": "package/dead.py",
        }
    ]
    assert "0 unreferenced public symbols" not in output


def test_supported_symbol_result_set_matches_posix_baseline(tmp_path: Path) -> None:
    """Pin the pre-refactor POSIX result: only ``PublicDead`` is unreferenced."""
    repo_root, baseline = _git_repo(tmp_path)
    source_dir = repo_root / "src"
    source_dir.mkdir()
    (source_dir / "consumer.py").write_text(
        "from module import PublicUsed\n\nVALUE = PublicUsed\n",
        encoding="utf-8",
    )
    _git(repo_root, "add", "src/consumer.py")
    _git(repo_root, "commit", "-qm", "add caller")
    baseline = _git(repo_root, "rev-parse", "HEAD").stdout.strip()
    (source_dir / "module.py").write_text(
        "def PublicUsed() -> None:\n"
        "    return None\n\n"
        "def PublicUntrackedUsed() -> None:\n"
        "    return None\n\n"
        "class PublicDead:\n"
        "    pass\n",
        encoding="utf-8",
    )
    # Keep this caller untracked: legacy ``grep -r src/`` included it, and the
    # portable scanner must preserve that filesystem-based behavior.
    (source_dir / "untracked_consumer.py").write_text(
        "VALUE = PublicUntrackedUsed\n",
        encoding="utf-8",
    )
    # The legacy POSIX command searched ``src/`` only. A top-level Python file
    # must not become a new caller when the changed source set is src-rooted.
    (repo_root / "unrelated_tool.py").write_text(
        "VALUE = PublicDead\n",
        encoding="utf-8",
    )
    test_dir = repo_root / "tests"
    test_dir.mkdir()
    (test_dir / "test_module.py").write_text(
        "def test_PublicDead() -> None:\n    assert PublicDead\n",
        encoding="utf-8",
    )
    _git(repo_root, "add", "src/module.py")
    _git(repo_root, "add", "tests/test_module.py")
    _git(repo_root, "commit", "-qm", "add public symbols")

    findings, output = scan(repo_root, baseline)

    assert findings == [
        {"type": "dead_code", "symbol": "PublicDead", "file": "src/module.py"}
    ]
    assert "1 unreferenced public symbol(s)" in output


def test_unreadable_python_corpus_is_undeterminable(tmp_path: Path) -> None:
    repo_root, baseline = _git_repo(tmp_path)
    source_dir = repo_root / "src"
    source_dir.mkdir()
    (source_dir / "module.py").write_text(
        "def PublicDead() -> None:\n    return None\n",
        encoding="utf-8",
    )
    (source_dir / "undecodable.py").write_bytes(b"\xff\xfe")
    _git(repo_root, "add", "src/module.py", "src/undecodable.py")
    _git(repo_root, "commit", "-qm", "add undecodable source")

    findings, output = scan(repo_root, baseline)

    assert findings[0]["type"] == "dead_code_undeterminable"
    assert findings[0]["reason"].startswith("could not read Python source:")
    assert "0 unreferenced public symbols" not in output


def _write_executable_spy(
    path: Path,
    *,
    executable_name: str,
    log_path: Path,
    delegate: str | None,
) -> None:
    body = [
        f"#!{sys.executable}",
        "import os",
        "import sys",
        "from pathlib import Path",
        f"with Path({str(log_path)!r}).open('a', encoding='utf-8') as stream:",
        f"    stream.write({executable_name!r} + '\\n')",
    ]
    if delegate is None:
        body.append("raise SystemExit(86)")
    else:
        body.append(f"os.execv({delegate!r}, [{delegate!r}, *sys.argv[1:]])")
    path.write_text("\n".join(body) + "\n", encoding="utf-8")
    path.chmod(0o755)


def test_real_post_merge_cli_uses_git_as_only_path_executable(tmp_path: Path) -> None:
    """The installed command path must not invoke an external reference search."""
    real_git = shutil.which("git")
    if real_git is None:
        pytest.skip("Git is required for the post-merge review contract")

    repo_root, baseline = _git_repo(tmp_path)
    (repo_root / ".kittify").mkdir()
    (repo_root / ".kittify" / "config.yaml").write_text("{}\n", encoding="utf-8")
    source_dir = repo_root / "package"
    source_dir.mkdir()
    (source_dir / "module.py").write_text(
        "def DeliberatelyUnreferenced() -> None:\n    return None\n",
        encoding="utf-8",
    )
    src_dir = repo_root / "src"
    src_dir.mkdir()
    (src_dir / "marker.py").write_text("VALUE = 1\n", encoding="utf-8")

    mission_slug = "dead-code-cli-01KTEST0"
    mission_id = "01KTEST0000000000000000000"
    mission_dir = repo_root / "kitty-specs" / mission_slug
    mission_dir.mkdir(parents=True)
    (mission_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_id": mission_id,
                "mission_slug": mission_slug,
                "friendly_name": "Dead Code CLI",
                "mission_type": "software-dev",
                "mission_number": None,
                "baseline_merge_commit": baseline,
            }
        ),
        encoding="utf-8",
    )
    (mission_dir / "status.events.jsonl").write_text(
        json.dumps(
            {
                "actor": "test-agent",
                "at": "2026-07-27T12:00:00+00:00",
                "event_id": "01KTEST0000000000000000001",
                "execution_mode": "worktree",
                "force": False,
                "from_lane": "planned",
                "mission_id": mission_id,
                "mission_slug": mission_slug,
                "to_lane": "done",
                "wp_id": "WP01",
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    (mission_dir / "issue-matrix.md").write_text(
        "| issue | verdict | evidence_ref |\n"
        "|---|---|---|\n"
        "| #2987 | fixed | WP02 regression test |\n",
        encoding="utf-8",
    )
    _git(repo_root, "add", ".")
    _git(repo_root, "commit", "-qm", "add review fixture")

    spy_dir = tmp_path / "path"
    spy_dir.mkdir()
    executable_log = tmp_path / "executables.log"
    _write_executable_spy(
        spy_dir / "git",
        executable_name="git",
        log_path=executable_log,
        delegate=real_git,
    )
    _write_executable_spy(
        spy_dir / "grep",
        executable_name="grep",
        log_path=executable_log,
        delegate=None,
    )
    source_root = Path(__file__).parents[5] / "src"
    cli_home = tmp_path / "cli-home"
    cli_home.mkdir()
    xdg_config_home = cli_home / ".config"
    xdg_data_home = cli_home / ".local" / "share"
    xdg_state_home = cli_home / ".local" / "state"
    for directory in (xdg_config_home, xdg_data_home, xdg_state_home):
        directory.mkdir(parents=True)
    env = {
        **os.environ,
        "HOME": str(cli_home),
        "PATH": str(spy_dir),
        "PYTHONPATH": str(source_root),
        "SPEC_KITTY_ENV_SKEW_FAIL_CLOSED": "0",
        "USERPROFILE": str(cli_home),
        "XDG_CONFIG_HOME": str(xdg_config_home),
        "XDG_DATA_HOME": str(xdg_data_home),
        "XDG_STATE_HOME": str(xdg_state_home),
    }
    # Colour-neutralise the CHILD env (#2632 pattern, mirrored from the
    # ``isolated_env`` fixture in ``tests/conftest.py``). This spawns the real
    # CLI, so the in-process ``CliConsole.set_all_plain`` seam cannot reach it;
    # inheriting ``os.environ`` wholesale would let a colour-forcing harness
    # (the Claude Code harness exports ``FORCE_COLOR=3``) splice SGR codes into
    # the child's stdout. Curating this explicit child-env dict is not an
    # ``os.environ`` mutation, so it cannot leak into sibling in-process tests.
    env.pop("FORCE_COLOR", None)
    env.pop("CLICOLOR_FORCE", None)
    env["NO_COLOR"] = "1"

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "specify_cli",
            "review",
            "--mission",
            mission_slug,
            "--mode",
            "post-merge",
        ],
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    # Belt to the child-env braces above: assert on the plain text the user
    # reads. This matters most for the negative assertion -- with SGR codes
    # present it could pass *vacuously* (Rich splices styling inside the
    # phrase), reporting success while the guarded regression was live.
    stdout = strip_ansi(result.stdout)
    assert "1 unreferenced public symbol(s)" in stdout
    assert "DeliberatelyUnreferenced" in stdout
    assert "0 unreferenced public symbols" not in stdout
    assert set(executable_log.read_text(encoding="utf-8").splitlines()) == {"git"}
