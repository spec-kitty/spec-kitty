"""Tests for EvidenceOrchestrator and load_url_list_from_config."""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest
import ruamel.yaml

from charter.activation.evidence.orchestrator import (
    ConfigShapeError,
    EvidenceOrchestrator,
    EvidenceResult,
    load_url_list_from_config,
)

# Marked for mutmut sandbox skip — see ADR 2026-04-20-1.
# Reason: trampoline bug: python -m specify_cli subprocess
pytestmark = pytest.mark.non_sandbox

# ANSI SGR escape sequence, e.g. "\x1b[33m" / "\x1b[1;36m" / "\x1b[0m".
_ANSI_SGR_RE = re.compile(r"\x1b\[[0-9;]*m")


def test_full_collection_returns_bundle(tmp_path: Path) -> None:
    """With a Python project, both code signals and corpus are populated."""
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'\n")
    (tmp_path / "main.py").write_text("# main\n")
    orch = EvidenceOrchestrator(repo_root=tmp_path, url_list=("https://example.com",))
    result = orch.collect()
    assert isinstance(result, EvidenceResult)
    assert result.bundle.code_signals is not None
    assert result.bundle.code_signals.primary_language == "python"
    assert result.bundle.url_list == ("https://example.com",)
    assert result.bundle.corpus_snapshot is not None  # generic fallback at minimum
    assert result.warnings == []


def test_code_failure_emits_warning(tmp_path: Path) -> None:
    """Code-reading failure -> warning, synthesis proceeds with None code_signals."""
    orch = EvidenceOrchestrator(repo_root=tmp_path / "nonexistent")
    result = orch.collect()
    assert result.bundle.code_signals is None
    assert any("code-reading" in w.lower() for w in result.warnings)


def test_skip_code_evidence(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("")
    orch = EvidenceOrchestrator(repo_root=tmp_path, skip_code=True)
    result = orch.collect()
    assert result.bundle.code_signals is None
    assert result.warnings == [] or all("corpus" in w.lower() for w in result.warnings)


def test_skip_corpus(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("")
    orch = EvidenceOrchestrator(repo_root=tmp_path, skip_corpus=True)
    result = orch.collect()
    assert result.bundle.corpus_snapshot is None


def test_url_list_assembled(tmp_path: Path) -> None:
    urls = ("https://a.example.com", "https://b.example.com")
    orch = EvidenceOrchestrator(repo_root=tmp_path, url_list=urls)
    result = orch.collect()
    assert result.bundle.url_list == urls


def test_load_url_list_absent(tmp_path: Path) -> None:
    assert load_url_list_from_config(tmp_path) == ()


def test_load_url_list_non_mapping_config_raises_config_shape_error(
    tmp_path: Path,
) -> None:
    """SK-16 (corrected shape): a non-mapping top-level ``config.yaml`` must
    fail closed with a controlled diagnostic -- not raise a bare
    ``AttributeError``, and not silently succeed either.

    ``config.yaml`` is normally a mapping, but a corrupted or hand-edited file
    can carry a bare scalar (e.g. a plain string) at the top level. Before the
    original SK-16 guard, ``config.get("charter")`` raised
    ``AttributeError: 'str' object has no attribute 'get'`` -- this propagated
    uncaught through ``EvidenceOrchestrator.collect()`` into ``charter status
    --json``'s broad ``except Exception`` handler, leaking the raw exception
    message as the structured envelope's ``"error"`` field.

    A follow-up fix made the guard return ``()`` instead -- but that converts
    a fail-closed diagnostic gap into a fully silent success: ``charter status
    --json`` then exits 0 with a normal success envelope on a corrupted
    config file, indistinguishable from a project with no configured URLs.
    The ledger's own SK-16 entry says the pre-fix behaviour "fails closed...
    this is *not* a silent success" -- only the *leaked exception text* was
    the defect, not the fail-closed outcome. So the correct fix raises a
    typed, message-carrying exception instead of either extreme.
    """
    kittify = tmp_path / ".kittify"
    kittify.mkdir()
    (kittify / "config.yaml").write_text(
        "just-a-plain-string-not-a-mapping\n", encoding="utf-8"
    )
    with pytest.raises(ConfigShapeError) as excinfo:
        load_url_list_from_config(tmp_path)
    message = str(excinfo.value)
    assert "has no attribute" not in message, (
        f"leaked a raw AttributeError instead of a controlled diagnostic: {message}"
    )
    assert "config.yaml" in message
    assert "str" in message


def test_load_url_list_present(tmp_path: Path) -> None:
    kittify = tmp_path / ".kittify"
    kittify.mkdir()
    yaml = ruamel.yaml.YAML()
    config = {"charter": {"synthesis_inputs": {"url_list": ["https://x.com", "https://y.com"]}}}
    with (kittify / "config.yaml").open("w") as fh:
        yaml.dump(config, fh)
    result = load_url_list_from_config(tmp_path)
    assert set(result) == {"https://x.com", "https://y.com"}


def test_bundle_is_empty_when_all_skipped(tmp_path: Path) -> None:
    orch = EvidenceOrchestrator(repo_root=tmp_path, skip_code=True, skip_corpus=True)
    result = orch.collect()
    assert result.bundle.code_signals is None
    assert result.bundle.corpus_snapshot is None
    assert result.bundle.url_list == ()
    assert result.bundle.is_empty


@pytest.mark.integration
def test_dry_run_evidence_on_seeded_python_project(
    tmp_path: Path,
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    """charter synthesize --adapter fixture --dry-run-evidence exits 0 on a seeded Python project.

    The child runs in a seeded test tmp project (pyproject.toml, src/main.py, conftest.py),
    so the detector must report ``lang=python`` (acceptance criterion #9), and the dry run
    must leave that project without a synthesis manifest.

    Determinism (#2672): this test drives the CLI as a *subprocess*, so an in-process
    ``CliConsole.set_plain()``/``set_all_plain()`` call would never reach the child. The
    ``CliConsole`` seam (``src/specify_cli/cli/console.py``) documents that "determinism
    is a property of the object, not the environment" — for a subprocess, the object-level
    seam is driven by handing the child its own colour-free environment. Rich's
    ``Console`` already honours ``NO_COLOR`` at construction time (reads
    ``os.environ["NO_COLOR"]`` when ``no_color`` isn't explicitly passed), so setting it
    in the ``env`` dict built below is TEST-LOCAL to the child process — it never mutates
    the real ``os.environ`` and cannot leak into sibling tests or subprocesses. ``FORCE_COLOR``
    is also forced here so the assertion is pinned against the worst case (the Claude Code
    harness exports ``FORCE_COLOR=3``, which splices ANSI SGR codes into the
    ``lang=<value>`` token via Rich's automatic repr-highlighter — reproducible, not
    hypothetical) — ``NO_COLOR`` must win over an inherited ``FORCE_COLOR``. The stdout
    match is additionally ANSI-stripped as a second, independent layer of insensitivity.

    Auth isolation: the child gets a fresh, empty home (``HOME``, the XDG dirs and
    ``SPEC_KITTY_HOME``), so no stored session exists and the outcome never depends on
    the developer's login state. The readiness auth banner is advisory only (it never
    changes the exit code), so the test does not skip on it.
    """
    import os

    repo_root = Path(__file__).resolve().parents[3]  # the spec-kitty checkout under test
    # Run from a seeded test tmp project, not from the checkout pytest was started in:
    # ``charter synthesize`` probes its working directory and refuses a linked git
    # worktree by design (#4785), so a subprocess started in the invoking checkout fails
    # from a Spec Kitty lane worktree (#5317). ``PYTHONPATH`` still points at the
    # checkout's ``src/``, so the subprocess runs the sources under test. This directory's autouse
    # ``_git_init_tmp_path`` makes ``tmp_path`` a normal git repository.
    project = tmp_path
    (project / "pyproject.toml").write_text("[project]\nname = 'test-project'\nversion = '0.1.0'\n", encoding="utf-8")
    (project / "src").mkdir()
    (project / "src" / "main.py").write_text("# main module\n", encoding="utf-8")
    (project / "conftest.py").write_text("# pytest conftest\n", encoding="utf-8")

    src_path = str(repo_root / "src")
    env = os.environ.copy()
    existing_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = f"{src_path}:{existing_pythonpath}" if existing_pythonpath else src_path
    # Test-local env for the CHILD process only — never mutates the real os.environ.
    env["FORCE_COLOR"] = "3"  # pin the worst case: harnesses that force color on.
    env["NO_COLOR"] = "1"  # NO_COLOR must win; Rich's Console honors it at construction.
    isolated_home = tmp_path_factory.mktemp("isolated_home")  # outside the project the child reads
    env["HOME"] = str(isolated_home)
    env["SPEC_KITTY_HOME"] = str(isolated_home / ".spec-kitty")
    for xdg in ("XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME", "XDG_STATE_HOME"):
        env[xdg] = str(isolated_home / xdg.lower())

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "specify_cli",
            "charter",
            "synthesize",
            "--adapter",
            "fixture",
            "--dry-run-evidence",
        ],
        capture_output=True,
        text=True,
        cwd=str(project),
        env=env,
    )

    # The dry run is also read-only for the test tmp project the child ran in.
    project_manifest = project / ".kittify" / "charter" / "synthesis-manifest.yaml"
    assert not project_manifest.exists(), f"--dry-run-evidence must never write {project_manifest}"

    assert result.returncode == 0, f"stderr: {result.stderr}\nstdout: {result.stdout}"
    # ANSI-insensitive (#2672 mode a): strip SGR escapes before every substring match so
    # the assertions hold whether or not the child emitted color.
    stdout_plain = _ANSI_SGR_RE.sub("", result.stdout)
    assert "Evidence dry-run summary" in stdout_plain
    assert "Code signals:" in stdout_plain
    assert "lang=python" in stdout_plain, f"Expected lang=python in output, got:\n{result.stdout}"
