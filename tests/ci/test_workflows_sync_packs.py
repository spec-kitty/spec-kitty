"""FR-006 / NFR-004: every CI job that reads a pack syncs it first (#6451).

``packs/built-in`` and ``packs/internal`` are fetched from the commits pinned in
``packs/*.source.yaml``; they are not authored here. A job that runs ``pytest``,
builds a distribution, or drives a ``spec-kitty`` pack command on a checkout that
never synced reads an empty or stale tree and goes red only after cutover.

The guard parses every workflow and walks each job's steps in order. A step counts
as a sync when it ``uses`` the warmup or sync-packs composite action, or runs
``scripts/sync_packs.py``. A pack-reading command appearing before any sync is a
violation. The planted-violation cases prove the guard is not vacuous.
"""

from __future__ import annotations

import ast
import re
from collections.abc import Iterator
from functools import cache
from pathlib import Path
from typing import Any

import pytest
import yaml

from tests.architectural._ast_scan import parse_file

pytestmark = pytest.mark.fast

_REPO = Path(__file__).resolve().parents[2]
_WORKFLOWS = _REPO / ".github" / "workflows"
_ACTIONS = _REPO / ".github" / "actions"
_SYNC_ACTIONS = ("./.github/actions/warmup", "./.github/actions/sync-packs")
_SYNC_SCRIPT = "sync_packs.py"

# Command-position tokens that read pack content. ``pytest`` must stand alone (not
# ``no_pytest_scan``, ``pytest.ini``, ``pytest-cov``, ``@pytest.mark``).
_READS_PACKS = re.compile(
    r"(?:^|[\s;&|(\"])pytest(?=\s|$)"
    r"|\buv\s+build\b"
    r"|-m\s+build\b"
    r"|(?:^\s*|\buv\s+run\s+(?:--[\w-]+\s+)*)spec-kitty\s+[a-z]"
)
_NON_COMMAND = re.compile(r"^\s*(?:echo\b|printf\b|#|(?:python3?\s+-m\s+)?pip3?\s+install\b|uv\s+pip\s+install\b|pipx\s+(?:install|inject)\b)")

# Lint/format/type tools run through ``uv run`` that never import project code.
_PURE_TOOLS = frozenset({"ruff", "mypy", "actionlint", "codespell", "yamllint", "shellcheck", "black", "isort", "twine"})
# Top-level packages whose import pulls in charter and so reads packs/built-in.
# ``kernel`` is the stdlib-only root layer (imports nothing upward), so it is not here.
_PROJECT_PACKAGES = frozenset({"specify_cli", "charter", "runtime", "mission_runtime", "glossary", "doctrine"})
_RUNNER = r"(?:uv\s+run\s+(?:--[\w-]+\s+)*)?"
_PY = r"(?:\.venv/bin/)?python3?"
_SCRIPT_CALL = re.compile(rf"(?:^|[\s;&|(\"]){_RUNNER}{_PY}\s+(?:-[IuOB]+\s+)*(?P<path>[\w./-]+\.py)\b")
_MODULE_CALL = re.compile(rf"(?:^|[\s;&|(\"]){_RUNNER}{_PY}\s+-m\s+(?P<mod>[\w.]+)")
_UV_RUN = re.compile(r"(?:^|[\s;&|(\"])uv\s+run\s+(?:--[\w-]+(?:\s+(?:3\.\d+|[\w./-]+\.txt))?\s+)*(?P<tool>[\w./-]+)")
_CLI_CALL = re.compile(r"(?:^\s*|\buv\s+run\s+(?:--[\w-]+\s+)*)spec-kitty\s+[a-z]")

# Jobs that genuinely read no pack, keyed by (workflow file, job id) with the reason.
_ALLOWLIST: dict[tuple[str, str], str] = {}


def _imports_project(path: Path, seen: frozenset[Path] = frozenset()) -> bool:
    """True when *path* imports a project package, directly or via a sibling local script module."""
    if path in seen or not path.is_file():
        return False
    tree = parse_file(path)  # fails closed: an unparseable script is an error, not a guess
    seen = seen | {path}
    for node in ast.walk(tree):
        names = [a.name for a in node.names] if isinstance(node, ast.Import) else []
        if isinstance(node, ast.ImportFrom) and node.module and not node.level:
            names = [node.module] + [f"{node.module}.{a.name}" for a in node.names]
        for name in names:
            if name.split(".")[0] in _PROJECT_PACKAGES:
                return True
            for cand in (_REPO / (name.replace(".", "/") + ".py"), path.parent / (name.split(".")[0] + ".py")):
                if cand.name != "__init__.py" and _imports_project(cand, seen):
                    return True
    return False


@cache
def _script_reads_packs(rel: str) -> bool:
    return _imports_project(_REPO / rel)


def reads_packs(line: str) -> bool:
    """True when *line* executes project code (and so needs ``packs/`` populated)."""
    if _READS_PACKS.search(line) or _CLI_CALL.search(line):
        return True
    module = _MODULE_CALL.search(line)
    if module:
        mod = module.group("mod")
        if mod.split(".")[0] in _PROJECT_PACKAGES:
            return True
        return mod.startswith("scripts.") and _script_reads_packs(mod.replace(".", "/") + ".py")
    if re.search(rf"{_RUNNER}{_PY}\s+(?:-c\b|-\s*<<)", line):
        return any(re.search(rf"\b(?:from|import)\s+{pkg}\b", line) for pkg in _PROJECT_PACKAGES)
    script = _SCRIPT_CALL.search(line)
    if script:
        return _script_reads_packs(script.group("path").lstrip("./"))
    uv = _UV_RUN.search(line)
    # ``uv run <tool>``: pure lint tools and python (judged above) are exempt; anything else is project code.
    return bool(uv and uv.group("tool") not in _PURE_TOOLS and not re.fullmatch(r"python3?|spec-kitty", uv.group("tool")))


def _commands(run: str) -> Iterator[str]:
    """Yield the command lines of a ``run:`` block (comments and prose dropped).

    Heredoc bodies are dropped too, except that a ``python - <<EOF`` body is folded into its
    opener line so ``reads_packs`` can see which packages the inline program imports.
    """
    lines = run.splitlines()
    index = 0
    while index < len(lines):
        raw = lines[index]
        index += 1
        opener = re.search(r"<<-?\s*['\"]?(\w+)['\"]?", raw)
        body: list[str] = []
        if opener:
            while index < len(lines):
                done = lines[index].strip() == opener.group(1)
                index += 1
                if done:
                    break
                body.append(lines[index - 1])
        if not _NON_COMMAND.match(raw):
            yield " ".join([raw, *body]) if re.search(rf"{_PY}\s+-\s*<<", raw) else raw


def _uses_sync_action(step: dict[str, Any]) -> bool:
    return str(step.get("uses", "")).startswith(_SYNC_ACTIONS)


def _is_sync_step(step: dict[str, Any]) -> bool:
    return _uses_sync_action(step) or any(_SYNC_SCRIPT in line for line in _commands(str(step.get("run", ""))))


def job_violations(job: dict[str, Any]) -> list[str]:
    """Return the pack-reading commands that run before any sync in *job*."""
    synced = False
    found: list[str] = []
    for step in job.get("steps") or []:
        if _uses_sync_action(step):
            synced = True
            continue
        for line in _commands(str(step.get("run", ""))):
            if _SYNC_SCRIPT in line:
                synced = True
            elif not synced and reads_packs(line):
                found.append(line.strip())
    return found


def _load(path: Path) -> dict[str, Any]:
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict), path
    return loaded


def _workflow_jobs() -> list[tuple[str, str, dict[str, Any]]]:
    out: list[tuple[str, str, dict[str, Any]]] = []
    for path in sorted(_WORKFLOWS.glob("*.yml")):
        for job_id, job in (_load(path).get("jobs") or {}).items():
            if isinstance(job, dict) and "steps" in job:
                out.append((path.name, job_id, job))
    return out


def _all_violations() -> list[str]:
    return [f"{name}:{job_id}: {cmd}" for name, job_id, job in _workflow_jobs() if (name, job_id) not in _ALLOWLIST for cmd in job_violations(job)]


def test_every_pack_reading_job_syncs_first() -> None:
    assert _all_violations() == []


def test_allowlist_entries_are_real_jobs_with_reasons() -> None:
    known = {(name, job_id) for name, job_id, _ in _workflow_jobs()}
    for key, reason in _ALLOWLIST.items():
        assert key in known, key
        assert reason.strip(), key


def test_scan_sees_the_known_pack_reading_workflows() -> None:
    """Non-vacuity on the real tree: the scan must see pack-reading jobs, not an empty set."""
    reading = {name for name, _, job in _workflow_jobs() if any(reads_packs(c) for s in job["steps"] for c in _commands(str(s.get("run", ""))))}
    assert {"ci-nightly.yml", "packs.yml", "release.yml", "ci-windows.yml", "ci-router.yml"} <= reading


def test_warmup_action_syncs_packs() -> None:
    steps = _load(_ACTIONS / "warmup" / "action.yml")["runs"]["steps"]
    assert any(_is_sync_step(step) for step in steps)


def test_sync_action_caches_on_the_pin_files() -> None:
    steps = _load(_ACTIONS / "sync-packs" / "action.yml")["runs"]["steps"]
    cache = [s for s in steps if str(s.get("uses", "")).startswith("actions/cache@")]
    assert len(cache) == 1
    assert re.search(r"@[0-9a-f]{40}\b", cache[0]["uses"]), "action must be SHA-pinned (DIRECTIVE_051)"
    assert "hashFiles('packs/*.source.yaml')" in cache[0]["with"]["key"]
    assert cache[0]["with"]["path"] == "~/.cache/spec-kitty/open-packs"
    assert any(_SYNC_SCRIPT in str(s.get("run", "")) for s in steps)


def test_pin_gate_checks_placed_trees_after_a_sync() -> None:
    job = _load(_WORKFLOWS / "packs.yml")["jobs"]["built-in-pin-check"]
    assert job_violations(job) == []
    runs = "\n".join(str(s.get("run", "")) for s in job["steps"])
    assert re.search(r"sync_packs\.py\b.*--check", runs)


# --- planted violations: the guard must go red on each -------------------------------


def _job(*steps: dict[str, Any]) -> dict[str, Any]:
    return {"steps": list(steps)}


@pytest.mark.parametrize(
    "run",
    [
        "uv run --frozen pytest tests/x -q",
        "python -m pytest tests/x",
        "uv build --wheel",
        "python -m build",
        "uv run --frozen spec-kitty charter pack regenerate-graph --check",
        "spec-kitty doctor mission-state --audit",
        "python -m specify_cli --help",
        "uv run --frozen python scripts/ci/mission_state_audit_report.py",
        "uv run --frozen mkdocs build",
        "PYTHONPATH=src python - <<'PY'\nfrom specify_cli.cli.commands.cutover_guard import cutover_guard\nPY",
    ],
)
def test_planted_unsynced_command_is_flagged(run: str) -> None:
    assert job_violations(_job({"run": "uv sync --frozen"}, {"run": run})) != []


def test_planted_sync_after_the_command_is_still_flagged() -> None:
    job = _job({"run": "uv run pytest -q"}, {"run": "python scripts/sync_packs.py --pack all"})
    assert job_violations(job) != []


def test_planted_sync_after_command_in_one_run_block_is_flagged() -> None:
    job = _job({"run": "uv run pytest -q\npython scripts/sync_packs.py --pack all"})
    assert job_violations(job) != []


@pytest.mark.parametrize(
    "steps",
    [
        [{"run": "python scripts/sync_packs.py --pack all"}, {"run": "uv run pytest -q"}],
        [{"uses": "./.github/actions/warmup"}, {"run": "python -m pytest x"}],
        [{"uses": "./.github/actions/sync-packs"}, {"run": "uv build"}],
        [{"run": "python scripts/sync_packs.py --pack all\nuv run pytest -q"}],
    ],
)
def test_synced_jobs_pass(steps: list[dict[str, Any]]) -> None:
    assert job_violations(_job(*steps)) == []


@pytest.mark.parametrize(
    "run",
    [
        "pipx inject spec-kitty-cli pytest pytest-cov",
        "pip install pytest",
        "echo pytest-output.txt",
        "uv run --frozen --no-sync python contracts/tools/no_pytest_scan.py",
        "git grep -l '@pytest.mark.windows_ci' -- tests",
    ],
)
def test_non_commands_are_not_flagged(run: str) -> None:
    assert job_violations(_job({"run": run})) == []
