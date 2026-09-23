"""Shared fixtures for end-to-end CLI smoke tests.

These tests exercise the full spec-kitty workflow via subprocess calls
against a temporary git repository, verifying that the CLI commands
compose correctly end-to-end.
"""

from __future__ import annotations

import shutil
import subprocess
import tomllib
from dataclasses import dataclass
from kernel.clock import now_utc_iso
from pathlib import Path
from textwrap import dedent

import pytest
import yaml

from tests._support.fixture_pollution import scrub_repo_mission_overrides
from tests.test_isolation_helpers import get_installed_version, run_cli_subprocess
from specify_cli.migration.schema_version import MAX_SUPPORTED_SCHEMA, SCHEMA_CAPABILITIES
from charter.activation.sync import sync as sync_charter

REPO_ROOT = Path(__file__).resolve().parents[2]
E2E_STATUS_COMMIT_BRANCH = "e2e-status-commit"


def _write_built_in_only_manifest(project: Path) -> None:
    """Seed fresh-project doctrine state for local workflow E2E fixtures."""
    manifest_path = project / ".kittify" / "charter" / "synthesis-manifest.yaml"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        dedent(
            """\
            schema_version: '2'
            mission_id: null
            created_at: '2099-01-01T00:00:00+00:00'
            run_id: 01JTESTRUNIDXXXXXXXXXXXXXX
            adapter_id: test
            adapter_version: '0.0.0'
            synthesizer_version: '0.0.0'
            manifest_hash: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
            artifacts: []
            built_in_only: true
            """
        ),
        encoding="utf-8",
    )
    (project / ".kittify" / "doctrine" / "graph.yaml").unlink(missing_ok=True)


@pytest.fixture(autouse=True)
def _disable_saas_sync_for_e2e_tests(monkeypatch: pytest.MonkeyPatch) -> None:
    """Disable hosted sync preflight for local workflow e2e tests.

    The root conftest enables SPEC_KITTY_ENABLE_SAAS_SYNC=1 so hosted
    sync/auth coverage stays live in the suites that intentionally exercise
    it. The tests in this tree drive local CLI workflows in temporary
    projects without hosted credentials, so the preflight would otherwise
    fail before the behavior under test runs.
    """
    monkeypatch.setenv("SPEC_KITTY_ENABLE_SAAS_SYNC", "0")


# ---------------------------------------------------------------------------
# Source-checkout pollution-guard helpers (T002)
# ---------------------------------------------------------------------------
#
# These helpers exist so the WP02 golden-path E2E test can verify that running
# the public spec-kitty CLI inside a temp project never writes back into the
# source checkout (REPO_ROOT). They capture both git-visible state and a
# direct on-disk inventory of pollution-prone roots so .gitignore-masked
# writes are also caught (FR-017, FR-018).
#
# Helpers are defined at module level (not bound to a fixture) so they can be
# imported by sibling test modules: `from tests.e2e.conftest import ...`.


_WATCHED_ROOTS: tuple[str, ...] = ("kitty-specs", ".kittify", ".worktrees", "docs")
_SOURCE_POLLUTION_SELF_BOOKKEEPING = frozenset(
    {".kittify/encoding-provenance/global.jsonl"}
)


@dataclass(frozen=True)
class SourcePollutionBaseline:
    """Snapshot of the source checkout's pollution-relevant state.

    Layer 1 (`git_status_short`): output of `git status --short` in the
    source checkout. Catches anything visible to git.

    Layer 2 (`inventory`): mapping of watched root -> {relative_path: (size,
    mtime_ns)}. Watched roots include each of `_WATCHED_ROOTS` plus a
    synthetic `**/kitty-ops` bucket aggregating every
    `kitty-ops` directory anywhere under the repo. This catches
    writes that a top-level `.gitignore` entry would mask from `git status`.
    """

    git_status_short: str
    inventory: dict[str, dict[str, tuple[int, int]]]


def _walk_inventory(
    root: Path,
    *,
    anchor: Path | None = None,
    excluded: frozenset[str] = frozenset(),
) -> dict[str, tuple[int, int]]:
    """Return a {relative_path: (size, mtime_ns)} map for every file under root.

    `anchor` controls the relative-path base. When omitted, paths are made
    relative to `root` itself; when supplied, paths are made relative to
    `anchor`. The latter is used for the aggregated `kitty-ops`
    bucket so paths from different subtrees stay disambiguated.
    """
    inv: dict[str, tuple[int, int]] = {}
    base = anchor if anchor is not None else root
    for path in root.rglob("*"):
        if path.is_file():
            relative = path.relative_to(base).as_posix()
            if relative in excluded:
                continue
            st = path.stat()
            inv[relative] = (st.st_size, st.st_mtime_ns)
    return inv


def capture_source_pollution_baseline(repo_root: Path) -> SourcePollutionBaseline:
    """Snapshot the source checkout's pollution-relevant state.

    Assumes `repo_root` is a git repo (the WP02 contract is that it is only
    ever called against `REPO_ROOT`). Returns a `SourcePollutionBaseline`
    suitable for later comparison via `assert_no_source_pollution`.
    """
    status = subprocess.run(
        ["git", "status", "--short"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=True,
    ).stdout

    inventory: dict[str, dict[str, tuple[int, int]]] = {}
    for root_name in _WATCHED_ROOTS:
        root = repo_root / root_name
        excluded = frozenset(
            path.removeprefix(f"{root_name}/")
            for path in _SOURCE_POLLUTION_SELF_BOOKKEEPING
            if path.startswith(f"{root_name}/")
        )
        inventory[root_name] = (
            _walk_inventory(root, excluded=excluded) if root.exists() else {}
        )

    # Aggregate every `kitty-ops` directory anywhere under repo_root.
    pi_inventory: dict[str, tuple[int, int]] = {}
    for path in repo_root.rglob("kitty-ops"):
        if path.is_dir():
            pi_inventory.update(_walk_inventory(path, anchor=repo_root))
    inventory["**/kitty-ops"] = pi_inventory

    return SourcePollutionBaseline(git_status_short=status, inventory=inventory)


def assert_no_source_pollution(baseline: SourcePollutionBaseline, repo_root: Path) -> None:
    """Compare current source-checkout state against `baseline`; raise on drift.

    Two-layer guard:
      * Layer 1 (FR-017): `git status --short` must be byte-identical to the
        baseline.
      * Layer 2 (FR-018): per-watched-root inventory must be byte-identical,
        excluding the canonical cross-worker self-bookkeeping sink; any other
        added / removed / modified file raises with a diagnostic diff.
    """
    current = capture_source_pollution_baseline(repo_root)

    if current.git_status_short != baseline.git_status_short:
        raise AssertionError(
            f"Source-checkout polluted (FR-017 / git status drift):\n  before: {baseline.git_status_short!r}\n  after:  {current.git_status_short!r}"
        )

    for watched, before in baseline.inventory.items():
        after = current.inventory.get(watched, {})
        added = sorted(set(after) - set(before))
        removed = sorted(set(before) - set(after))
        modified = sorted(p for p in set(before) & set(after) if before[p] != after[p])
        if added or removed or modified:
            raise AssertionError(f"Source-checkout polluted (FR-018 / {watched} drift):\n  added:    {added}\n  removed:  {removed}\n  modified: {modified}")


# ---------------------------------------------------------------------------
# Subprocess-failure diagnostic helper (T003)
# ---------------------------------------------------------------------------


def format_subprocess_failure(
    *,
    command: list[str] | tuple[str, ...],
    cwd: Path,
    completed: subprocess.CompletedProcess[str],
) -> str:
    """Produce a multi-line diagnostic for a failed subprocess (FR-019, NFR-004).

    The golden-path E2E test must surface command, cwd, return code, stdout,
    and stderr in any failed-subprocess assertion message so a single failed
    run is diagnosable without rerunning under a debugger.
    """
    return (
        "Subprocess failed.\n"
        f"  command: {list(command)!r}\n"
        f"  cwd:     {cwd}\n"
        f"  rc:      {completed.returncode}\n"
        f"  stdout:  {completed.stdout!r}\n"
        f"  stderr:  {completed.stderr!r}"
    )


def _checkout_e2e_status_commit_branch(project: Path) -> None:
    """Run status-commit E2E workflows away from protected main/master."""
    subprocess.run(
        ["git", "checkout", "-b", E2E_STATUS_COMMIT_BRANCH],
        cwd=project,
        check=True,
        capture_output=True,
    )


@pytest.fixture()
def e2e_project(tmp_path: Path) -> Path:
    """Create a temporary Spec Kitty project with git and .kittify initialized.

    This is the foundation fixture for E2E tests. It:
    - Copies .kittify from the real repo root
    - Copies missions from src/specify_cli/missions/
    - Initializes git with main branch and initial commit
    - Checks out an E2E status commit branch for workflow write operations
    - Aligns metadata version with source to avoid mismatch errors
    """
    project = tmp_path / "e2e-project"
    project.mkdir()

    # Copy .kittify structure from the real repo
    shutil.copytree(
        REPO_ROOT / ".kittify",
        project / ".kittify",
        symlinks=True,
    )
    scrub_repo_mission_overrides(project)
    charter_path = project / ".kittify" / "charter" / "charter.md"
    if charter_path.exists():
        sync_charter(charter_path, charter_path.parent, force=True)
    _write_built_in_only_manifest(project)

    # Synthesize charter runtime state so preflight passes normally.
    #
    # .kittify/charter/metadata.yaml is gitignored (line 108 of .gitignore) and
    # is always absent in CI clones. The preflight system treats a missing
    # metadata.yaml as charter_source=stale and blocks `spec-kitty implement`.
    #
    # Rather than disabling preflight entirely, we synthesize a valid
    # metadata.yaml from the committed charter.md so the preflight check sees a
    # consistent state (charter_source=fresh, synced_bundle=fresh,
    # synthesized_drg=built_in_only).
    #
    # Three layers must pass:
    #   1. charter_source=fresh  — metadata.yaml present with matching hash
    #   2. synced_bundle=fresh   — metadata.yaml is counted as a bundle file,
    #                              so its presence + charter_source=fresh suffices
    #   3. synthesized_drg=built_in_only — PROVENANCE.md with the legacy
    #                              fresh-seed sentinel phrases (see
    #                              charter_runtime/freshness/computer.py
    #                              _looks_like_legacy_fresh_seed)
    _charter_dir = project / ".kittify" / "charter"
    _charter_md = _charter_dir / "charter.md"
    if _charter_md.exists():
        from charter.hasher import hash_content as _hash_content  # noqa: PLC0415

        _charter_content = _charter_md.read_text(encoding="utf-8")
        _charter_hash = _hash_content(_charter_content)  # returns "sha256:<hex>"
        _now_iso = now_utc_iso()
        (_charter_dir / "metadata.yaml").write_text(
            f'charter_hash: {_charter_hash}\nextracted_at: "{_now_iso}"\n',
            encoding="utf-8",
        )

    # Write the legacy fresh-seed PROVENANCE.md so compute_freshness returns
    # synthesized_drg=built_in_only (a passing state) instead of missing.
    _doctrine_dir = project / ".kittify" / "doctrine"
    _doctrine_dir.mkdir(parents=True, exist_ok=True)
    (_doctrine_dir / "PROVENANCE.md").write_text(
        "# Spec Kitty Doctrine — Fresh Project Seed\n\n"
        "This `.kittify/doctrine/` tree was materialized by `spec-kitty charter\n"
        "synthesize` running against a **fresh project** (no LLM-authored YAML under\n"
        "`.kittify/charter/generated/`). It exists so `DoctrineService` discovers a\n"
        "project layer and the runtime can advance; it is intentionally empty.\n\n"
        "The runtime falls back to the in-package built-in doctrine\n"
        "(`src/charter/offering/`) for all artifact lookups until the LLM harness writes\n"
        "project-local artifacts under `.kittify/charter/generated/` and you re-run\n"
        "`spec-kitty charter synthesize`.\n",
        encoding="utf-8",
    )

    # Copy missions from source location
    missions_src = REPO_ROOT / "src" / "specify_cli" / "missions"
    missions_dest = project / ".kittify" / "missions"
    if missions_src.exists() and not missions_dest.exists():
        shutil.copytree(missions_src, missions_dest)

    # Create .gitignore
    (project / ".gitignore").write_text(
        "__pycache__/\n.worktrees/\n",
        encoding="utf-8",
    )

    # Initialize git
    subprocess.run(["git", "init", "-b", "main"], cwd=project, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "e2e@example.com"],
        cwd=project,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "E2E Test"],
        cwd=project,
        check=True,
        capture_output=True,
    )
    subprocess.run(["git", "add", "."], cwd=project, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial project"],
        cwd=project,
        check=True,
        capture_output=True,
    )

    # Align metadata version with source to avoid version mismatch errors
    metadata_file = project / ".kittify" / "metadata.yaml"
    if metadata_file.exists():
        with open(metadata_file, encoding="utf-8") as f:
            metadata = yaml.safe_load(f) or {}

        current_version = get_installed_version()
        if current_version is None:
            with open(REPO_ROOT / "pyproject.toml", "rb") as f:
                pyproject = tomllib.load(f)
            current_version = pyproject["project"]["version"] or "unknown"

        if "spec_kitty" not in metadata:
            metadata["spec_kitty"] = {}
        metadata["spec_kitty"]["version"] = current_version
        metadata["spec_kitty"]["schema_version"] = MAX_SUPPORTED_SCHEMA
        metadata["spec_kitty"]["schema_capabilities"] = SCHEMA_CAPABILITIES[MAX_SUPPORTED_SCHEMA]

        with open(metadata_file, "w", encoding="utf-8") as f:
            yaml.dump(metadata, f, default_flow_style=False, sort_keys=False)

        # Commit the version update
        subprocess.run(["git", "add", "."], cwd=project, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Align metadata version", "--allow-empty"],
            cwd=project,
            check=True,
            capture_output=True,
        )

    # Create a minimal source directory for realism
    src_dir = project / "src"
    src_dir.mkdir()
    (src_dir / "__init__.py").write_text("", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=project, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Add source skeleton"],
        cwd=project,
        check=True,
        capture_output=True,
    )
    _checkout_e2e_status_commit_branch(project)

    return project


# ---------------------------------------------------------------------------
# Fresh-project fixture (T001)
# ---------------------------------------------------------------------------


@pytest.fixture()
def fresh_e2e_project(tmp_path: Path) -> Path:
    """Create a temp Spec Kitty project from scratch via public CLI.

    Unlike `e2e_project`, this fixture does NOT copy `.kittify` from the
    source checkout. It runs `spec-kitty init` against a brand-new git
    repo so the test exercises the operator path from a truly clean
    starting state (FR-003, FR-020).
    """
    project = tmp_path / "fresh-e2e-project"
    project.mkdir()

    # Step 1: bare git init (spec-kitty init does NOT do this).
    subprocess.run(
        ["git", "init", "-b", "main"],
        cwd=project,
        check=True,
        capture_output=True,
    )
    # git config user.email/user.name: written directly into
    # project/.git/config's [user] section (plain text/INI append)
    # instead of two `git config` subprocess calls -- no change in
    # git's own observable state, no commit, no .kittify content.
    with (project / ".git" / "config").open("a", encoding="utf-8") as git_config:
        git_config.write("[user]\n")
        git_config.write("\temail = fresh-e2e@example.com\n")
        git_config.write("\tname = Fresh E2E Test\n")

    # Explicit, executable C-006 precondition assertions, immediately
    # before the spec-kitty init call: init must observe a repository
    # with no commits and no `.kittify` content, exactly as it does
    # today.
    assert not (project / ".kittify").exists(), "C-006: no .kittify content before init"
    assert not (project / ".git" / "refs" / "heads" / "main").exists(), "C-006: zero-commit repo before init"

    # Step 2: drive `spec-kitty init` via the same isolated invocation
    # path used by the `run_cli` fixture (PYTHONPATH -> source `src/`,
    # SPEC_KITTY_TEMPLATE_ROOT -> REPO_ROOT, SPEC_KITTY_TEST_MODE=1).
    # ^ unchanged call -- same subprocess boundary, same args (C-003).
    # Faster because main_callback()'s ensure_global_agent_commands()
    # now short-circuits on a warm, unchanged freshness stamp (see
    # WP04) instead of unconditionally re-rendering.
    result = run_cli_subprocess(
        project,
        "init",
        ".",
        "--ai",
        "codex",
        "--non-interactive",
    )
    if result.returncode != 0:
        raise AssertionError(f"spec-kitty init failed for fresh fixture:\n  rc={result.returncode}\n  stdout: {result.stdout}\n  stderr: {result.stderr}")

    # Step 3: commit the freshly seeded project state so subsequent
    # CLI commands see a clean working tree.
    subprocess.run(
        ["git", "add", "."],
        cwd=project,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "commit", "-m", "Initial spec-kitty init"],
        cwd=project,
        check=True,
        capture_output=True,
    )
    _checkout_e2e_status_commit_branch(project)

    return project
