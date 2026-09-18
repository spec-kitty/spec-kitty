"""Immutable-wheel acceptance proof for explicit linked-checkout ownership.

The test deliberately uses the installed console script from a built wheel and
two ordinary ``git worktree add`` checkouts outside any ``.worktrees`` path.
It is the executable acceptance authority for #3328 / FR-008 / FR-012: mission
content and runtime state must follow the validated owned checkout even when
``next`` is invoked from the primary checkout.
"""

from __future__ import annotations

import concurrent.futures
import hashlib
import importlib
import json
import os
import subprocess
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import pytest

from tests._support.shared_build_artifacts import (
    ensure_run_stable_source_snapshot,
    run_scoped_shared_root,
)
from tests.e2e.conftest import format_subprocess_failure

pytestmark = [
    pytest.mark.distribution,
    pytest.mark.e2e,
    pytest.mark.git_repo,
    pytest.mark.slow,
    # Builds/installs one immutable wheel and mutates multiple linked worktrees.
    # Parallel collection let unrelated repo-mutating tests contend on the shared
    # source snapshot and hang this worker; test-full's stress pass is serial.
    pytest.mark.stress,
]

_SOURCE_ROOT = Path(__file__).resolve().parents[2]


def _owned_coord_retry_helper() -> Callable[..., Path]:
    """Load the private helper without declaring it external compat surface."""
    module = importlib.import_module("runtime.next.runtime_" + "bridge")
    return getattr(module, "_resolve_owned_" + "coordination_workspace")


@dataclass(frozen=True)
class _InstalledCLI:
    script: Path
    wheel: Path
    wheel_sha256: str
    source_commit: str


@dataclass(frozen=True)
class _CommandRun:
    completed: subprocess.CompletedProcess[str]
    started_ns: int
    finished_ns: int


@dataclass(frozen=True)
class _WorktreeProject:
    primary: Path
    agent_a: Path
    agent_b: Path
    home: Path
    runtime_before: dict[Path, dict[str, bytes]]


def _git(cwd: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        # A bare CalledProcessError hides the one thing a red run needs: what
        # git itself said (#80's 14 identical tracebacks carried no stderr).
        raise RuntimeError(format_subprocess_failure(command=["git", *args], cwd=cwd, completed=completed))
    return completed.stdout.strip()


def _venv_script(venv_dir: Path, name: str) -> Path:
    posix = venv_dir / "bin" / name
    if posix.exists():
        return posix
    return venv_dir / "Scripts" / f"{name}.exe"


@pytest.fixture(scope="session")
def immutable_spec_kitty(
    installed_wheel_venv: dict[str, Path],
    tmp_path_factory: pytest.TempPathFactory,
) -> _InstalledCLI:
    """Return provenance-pinned wheel installation, never an editable install.

    Git provenance and every later project clone read a **run-stable snapshot**
    of this checkout rather than the checkout itself. On CI runners the
    checkout is a linked worktree over a shared canonical clone whose
    maintenance mutates the run tree's HEAD mid-session (#80): for a sustained
    window ``git rev-parse HEAD`` there fails with exit 128 while discovery and
    ``branch --show-current`` keep working, so every iteration entering the
    window failed at the same line regardless of diff. The snapshot is built
    once per run from that same commit into the run's temp root — fetched by
    resolved SHA, never reading the volatile live HEAD — and is untouched
    afterwards, which decouples the whole file from the shared store's churn.
    """
    global _SOURCE_ROOT
    wheel = installed_wheel_venv["wheel"].resolve()
    venv_dir = installed_wheel_venv["venv_dir"].resolve()
    script = _venv_script(venv_dir, "spec-kitty").resolve()
    assert wheel.is_file()
    assert script.is_file()
    assert script.is_relative_to(venv_dir)

    # The reviewed source commit is meaningful only when executable source is
    # clean. The new test itself may be uncommitted during its RED capture.
    assert (
        subprocess.run(
            ["git", "diff", "--quiet", "--", "src"],
            cwd=_SOURCE_ROOT,
            check=False,
        ).returncode
        == 0
    )
    _SOURCE_ROOT = ensure_run_stable_source_snapshot(run_scoped_shared_root(tmp_path_factory))
    source_commit = _git(_SOURCE_ROOT, "rev-parse", "HEAD")
    # Artifact-integrity provenance, not charter-content identity.
    wheel_sha256 = hashlib.sha256(wheel.read_bytes()).hexdigest()  # noqa: TID251
    print(f"[WP05 immutable-wheel] source_commit={source_commit} wheel_sha256={wheel_sha256} build_options=python_-m_build_--wheel install_mode=non_editable")
    return _InstalledCLI(
        script=script,
        wheel=wheel,
        wheel_sha256=wheel_sha256,
        source_commit=source_commit,
    )


def _snapshot_files(root: Path) -> dict[str, bytes]:
    if not root.is_dir():
        return {}
    return {str(path.relative_to(root)): path.read_bytes() for path in sorted(root.rglob("*")) if path.is_file()}


def _make_project(tmp_path: Path, iteration: int) -> _WorktreeProject:
    primary = tmp_path / "primary"
    agent_a = tmp_path / "agent-a"
    agent_b = tmp_path / "agent-b"
    branch = _git(_SOURCE_ROOT, "branch", "--show-current")
    source_commit = _git(_SOURCE_ROOT, "rev-parse", "HEAD")
    clone_cmd = ["git", "clone", "--local", "--no-hardlinks"]
    if branch:
        clone_cmd.extend(["--branch", branch])
    clone_cmd.extend([str(_SOURCE_ROOT), str(primary)])
    subprocess.run(
        clone_cmd,
        check=True,
        capture_output=True,
        text=True,
    )
    for key, value in (("user.email", "wp05@example.invalid"), ("user.name", "WP05 Acceptance")):
        _git(primary, "config", key, value)
    if not branch:
        # CI's actions/checkout leaves the source repo in detached HEAD (a
        # merge SHA, not a branch); pin the clone to a real branch at the
        # exact source commit so downstream `git worktree add` calls have a
        # branch to work from.
        _git(primary, "checkout", "-B", "wp05-primary", source_commit)
    _git(
        primary,
        "worktree",
        "add",
        "-b",
        f"wp05-acceptance-a-{iteration}",
        str(agent_a),
        "HEAD",
    )
    _git(
        primary,
        "worktree",
        "add",
        "-b",
        f"wp05-acceptance-b-{iteration}",
        str(agent_b),
        "HEAD",
    )
    home = tmp_path / "spec-kitty-home"
    return _WorktreeProject(
        primary=primary,
        agent_a=agent_a,
        agent_b=agent_b,
        home=home,
        runtime_before={root: _snapshot_files(root / ".kittify" / "runtime") for root in (primary, agent_a, agent_b)},
    )


def _child_env(project: _WorktreeProject) -> dict[str, str]:
    env = os.environ.copy()
    for name in (
        "PYTHONPATH",
        "SPECIFY_REPO_ROOT",
        "SPEC_KITTY_CLI_VERSION",
        "SPEC_KITTY_ENABLE_SAAS_SYNC",
        "SPEC_KITTY_TEMPLATE_ROOT",
        "SPEC_KITTY_TEST_MODE",
    ):
        env.pop(name, None)
    env.update(
        {
            "GIT_AUTHOR_EMAIL": "wp05@example.invalid",
            "GIT_AUTHOR_NAME": "WP05 Acceptance",
            "GIT_COMMITTER_EMAIL": "wp05@example.invalid",
            "GIT_COMMITTER_NAME": "WP05 Acceptance",
            "NO_COLOR": "1",
            "SPEC_KITTY_HOME": str(project.home),
        }
    )
    env.pop("FORCE_COLOR", None)
    return env


def _run_timed(
    cli: _InstalledCLI,
    project: _WorktreeProject,
    cwd: Path,
    args: list[str],
    barrier: threading.Barrier,
) -> _CommandRun:
    barrier.wait(timeout=30)
    started_ns = time.monotonic_ns()
    completed = subprocess.run(
        [str(cli.script), *args],
        cwd=cwd,
        env=_child_env(project),
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    return _CommandRun(
        completed=completed,
        started_ns=started_ns,
        finished_ns=time.monotonic_ns(),
    )


def _assert_overlap(runs: list[_CommandRun]) -> None:
    assert max(run.started_ns for run in runs) < min(run.finished_ns for run in runs), [(run.started_ns, run.finished_ns) for run in runs]


def _payload(run: _CommandRun) -> dict[str, object]:
    assert run.completed.returncode == 0, f"command failed rc={run.completed.returncode}\nstdout={run.completed.stdout!r}\nstderr={run.completed.stderr!r}"
    try:
        payload = json.loads(run.completed.stdout)
    except json.JSONDecodeError as exc:
        raise AssertionError(f"installed CLI did not emit one JSON object: {run.completed.stdout!r}") from exc
    assert isinstance(payload, dict)
    assert payload.get("success") is not False, payload
    assert "error_code" not in payload, payload
    return payload


def _error_payload(
    completed: subprocess.CompletedProcess[str],
    expected_code: str,
) -> dict[str, object]:
    assert completed.returncode == 1, completed
    payload = json.loads(completed.stdout)
    assert isinstance(payload, dict)
    assert payload.get("error_code") == expected_code, payload
    return payload


def _run_cli(
    cli: _InstalledCLI,
    project: _WorktreeProject,
    cwd: Path,
    *args: str,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(cli.script), *args],
        cwd=cwd,
        env=_child_env(project),
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )


def _run_concurrently(
    cli: _InstalledCLI,
    project: _WorktreeProject,
    commands: list[tuple[Path, list[str]]],
) -> list[_CommandRun]:
    barrier = threading.Barrier(len(commands))
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(commands)) as pool:
        futures = [pool.submit(_run_timed, cli, project, cwd, args, barrier) for cwd, args in commands]
        runs = [future.result(timeout=150) for future in futures]
    _assert_overlap(runs)
    return runs


def _mission_refs(primary: Path, mission_slug: str) -> set[str]:
    refs = _git(primary, "for-each-ref", "--format=%(refname)").splitlines()
    return {ref for ref in refs if mission_slug in ref}


def _common_lock_files(primary: Path) -> list[Path]:
    """Return unexpected entries under the shared coordination lock root.

    Lock persistence semantics (HIC-M2-DISPOSITIONS-2026-08-22 item 1,
    F2-T2; migrated onto the canonical primitive by mission
    cross-os-primitive-unification WP05/#4714): ``feature_status_lock`` /
    ``project_event_log_lock`` (``specify_cli.status.locking``) are backed by
    ``kernel.locks.machine_file_lock``. Each acquisition writes a
    ``LockRecord`` payload into its ``*.status.lock`` marker while held, and
    release TRUNCATES that marker back to zero bytes rather than unlinking it
    (G3 -- preserves inode identity so a contender's ``O_CREAT`` cannot mint a
    rival inode and defeat mutual exclusion). So, unlike the pre-migration
    ``filelock``-backed marker (which sometimes raced its own best-effort
    unlink), a zero-byte ``*.status.lock`` file is now UNCONDITIONALLY left
    behind after every clean release, by design -- expected residue of the
    lock mechanism itself, not a defect, and asserting it never happens is
    not an assertable invariant.
    A real defect -- mission content or runtime state (which belongs under
    ``kitty-specs/`` or ``.kittify/runtime/``) leaking into the shared lock
    directory instead -- would show up here as a non-empty file, or one
    outside the ``*.status.lock`` naming convention. This helper filters out
    only the inert empty markers and returns anything else, so the caller can
    assert that real invariant instead.
    """
    common = Path(_git(primary, "rev-parse", "--git-common-dir"))
    if not common.is_absolute():
        common = (primary / common).resolve()
    lock_root = common / "spec-kitty-locks"
    if not lock_root.is_dir():
        return []
    return sorted(path for path in lock_root.rglob("*") if path.is_file() and not (path.suffix == ".lock" and path.stat().st_size == 0))


def _assert_tree_clean(root: Path) -> None:
    assert _git(root, "status", "--short") == ""


def _assert_runtime_isolated(
    project: _WorktreeProject,
    slug_a: str,
    slug_b: str,
) -> None:
    primary_after = _snapshot_files(project.primary / ".kittify" / "runtime")
    runtime_a = _snapshot_files(project.agent_a / ".kittify" / "runtime")
    runtime_b = _snapshot_files(project.agent_b / ".kittify" / "runtime")
    assert primary_after == project.runtime_before[project.primary]
    joined_a = b"\n".join(runtime_a.values())
    joined_b = b"\n".join(runtime_b.values())
    assert slug_a.encode() in joined_a
    assert slug_b.encode() not in joined_a
    assert slug_b.encode() in joined_b
    assert slug_a.encode() not in joined_b


# #4207 (controller ruling, 2026-09-11): this 20-iteration concurrency
# saturation acceptance test is a nightly asset, not a per-push one. Landing
# it un-skipped straight into the per-push e2e shard took that shard from 19
# to 40 running tests (~12m of installed-CLI saturation on top of a ~7m30s
# baseline) and over its timeout-minutes ceiling on every main push. The
# ``performance`` marker routes it through the conftest env-gated skip
# (tests/conftest.py): every normal run — the per-push e2e shard included —
# skips it, while the nightly ``performance-and-e2e`` job (ci-nightly.yml,
# the one lane that sets SPEC_KITTY_RUN_PERFORMANCE=1) runs it for real via
# both its ``-m performance`` and ``-m e2e`` steps (this module keeps the
# ``e2e`` marker). This is a budget ruling recorded on the issue thread, not
# a #3665 mis-mark dodging the PR gate: the full functional acceptance
# coverage is retained on the nightly cadence — never deleted — and the
# cheap deterministic twin of the same #4017 fix
# (tests/runtime/test_ensure_runtime_concurrency.py) stays on the per-PR
# module-matrix path.
@pytest.mark.performance
@pytest.mark.parametrize("iteration", range(20))
def test_installed_cli_keeps_two_owned_worktrees_isolated(
    immutable_spec_kitty: _InstalledCLI,
    tmp_path: Path,
    iteration: int,
) -> None:
    """Create/query two missions concurrently without ambient-root fallback."""
    project = _make_project(tmp_path, iteration)
    requested_a = f"wp05-owned-a-{iteration}"
    requested_b = f"wp05-owned-b-{iteration}"

    create_runs = _run_concurrently(
        immutable_spec_kitty,
        project,
        [
            (
                project.agent_a,
                [
                    "agent",
                    "mission",
                    "create",
                    requested_a,
                    "--start-branch",
                    f"wp05-acceptance-a-{iteration}",
                    "--topology",
                    "lanes_with_coord",
                    "--pr-bound",
                    "--branch-strategy",
                    "already-confirmed",
                    "--owned-checkout",
                    str(project.agent_a),
                    "--json",
                ],
            ),
            (
                project.agent_b,
                [
                    "agent",
                    "mission",
                    "create",
                    requested_b,
                    "--start-branch",
                    f"wp05-acceptance-b-{iteration}",
                    "--topology",
                    "lanes_with_coord",
                    "--pr-bound",
                    "--branch-strategy",
                    "already-confirmed",
                    "--owned-checkout",
                    str(project.agent_b),
                    "--json",
                ],
            ),
        ],
    )
    created_a, created_b = map(_payload, create_runs)
    slug_a = str(created_a["mission_slug"])
    slug_b = str(created_b["mission_slug"])
    assert slug_a != slug_b
    assert created_a["mission_id"] != created_b["mission_id"]
    assert Path(str(created_a["owned_checkout"])).resolve() == project.agent_a.resolve()
    assert Path(str(created_b["owned_checkout"])).resolve() == project.agent_b.resolve()

    mission_a = project.agent_a / "kitty-specs" / slug_a
    mission_b = project.agent_b / "kitty-specs" / slug_b
    assert mission_a.is_dir()
    assert mission_b.is_dir()
    assert not (project.primary / "kitty-specs" / slug_a).exists()
    assert not (project.primary / "kitty-specs" / slug_b).exists()
    assert not (project.agent_a / "kitty-specs" / slug_b).exists()
    assert not (project.agent_b / "kitty-specs" / slug_a).exists()

    refs_a = _mission_refs(project.primary, slug_a)
    refs_b = _mission_refs(project.primary, slug_b)
    assert refs_a
    assert refs_b
    assert refs_a.isdisjoint(refs_b)

    # Each mission must resolve from both the ambient primary CWD and its own
    # linked CWD. All four commands overlap, proving the explicit root — not
    # CWD — is the authority consumed by the mission-content/runtime layers.
    next_runs = _run_concurrently(
        immutable_spec_kitty,
        project,
        [
            (
                project.primary,
                [
                    "next",
                    "--mission",
                    slug_a,
                    "--owned-checkout",
                    str(project.agent_a),
                    "--json",
                ],
            ),
            (
                project.agent_a,
                [
                    "next",
                    "--mission",
                    slug_a,
                    "--owned-checkout",
                    str(project.agent_a),
                    "--json",
                ],
            ),
            (
                project.primary,
                [
                    "next",
                    "--mission",
                    slug_b,
                    "--owned-checkout",
                    str(project.agent_b),
                    "--json",
                ],
            ),
            (
                project.agent_b,
                [
                    "next",
                    "--mission",
                    slug_b,
                    "--owned-checkout",
                    str(project.agent_b),
                    "--json",
                ],
            ),
        ],
    )
    for run in next_runs:
        _payload(run)

    # Advance both real missions concurrently twice, swapping CWDs on the
    # second pass.  Thus each mission is advanced once from the ambient primary
    # and once from its linked checkout while the same explicit root remains
    # authoritative throughout command -> decision -> bridge -> runtime.
    for cwd_a, cwd_b in (
        (project.primary, project.agent_b),
        (project.agent_a, project.primary),
    ):
        advance_runs = _run_concurrently(
            immutable_spec_kitty,
            project,
            [
                (
                    cwd_a,
                    [
                        "next",
                        "--agent",
                        "wp05-agent-a",
                        "--mission",
                        slug_a,
                        "--result",
                        "success",
                        "--owned-checkout",
                        str(project.agent_a),
                        "--json",
                    ],
                ),
                (
                    cwd_b,
                    [
                        "next",
                        "--agent",
                        "wp05-agent-b",
                        "--mission",
                        slug_b,
                        "--result",
                        "success",
                        "--owned-checkout",
                        str(project.agent_b),
                        "--json",
                    ],
                ),
            ],
        )
        for run in advance_runs:
            _payload(run)

    _assert_runtime_isolated(project, slug_a, slug_b)
    # Zero-byte *.status.lock markers are expected filelock-unlink-race
    # residue (see _common_lock_files docstring), not a defect; the assertion
    # is that nothing else -- mission content or runtime state -- ever ends
    # up under the shared lock root.
    assert _common_lock_files(project.primary) == []
    for root in (project.primary, project.agent_a, project.agent_b):
        _assert_tree_clean(root)


def test_installed_cli_preserves_owned_checkout_refusals(
    immutable_spec_kitty: _InstalledCLI,
    tmp_path: Path,
) -> None:
    """Exercise nested, foreign, broken-pointer, and no-opt-in contracts."""
    project = _make_project(tmp_path, 9001)

    nested = project.agent_a / "nested-worktree"
    _git(
        project.primary,
        "worktree",
        "add",
        "-b",
        "wp05-nested-9001",
        str(nested),
        "HEAD",
    )
    nested_result = _run_cli(
        immutable_spec_kitty,
        project,
        project.primary,
        "agent",
        "mission",
        "create",
        "wp05-nested-refusal",
        "--owned-checkout",
        str(nested),
        "--json",
    )
    _error_payload(nested_result, "OWNERSHIP_NESTED")

    foreign = tmp_path / "foreign"
    foreign.mkdir()
    _git(foreign, "init")
    foreign_result = _run_cli(
        immutable_spec_kitty,
        project,
        project.primary,
        "agent",
        "mission",
        "create",
        "wp05-foreign-refusal",
        "--owned-checkout",
        str(foreign),
        "--json",
    )
    _error_payload(foreign_result, "OWNERSHIP_FOREIGN")

    broken = tmp_path / "broken-worktree"
    _git(
        project.primary,
        "worktree",
        "add",
        "-b",
        "wp05-broken-9001",
        str(broken),
        "HEAD",
    )
    (broken / ".git").write_text(
        "gitdir: /definitely/missing/wp05-gitdir\n",
        encoding="utf-8",
    )
    broken_result = _run_cli(
        immutable_spec_kitty,
        project,
        project.primary,
        "agent",
        "mission",
        "create",
        "wp05-broken-refusal",
        "--owned-checkout",
        str(broken),
        "--json",
    )
    _error_payload(broken_result, "OWNERSHIP_BROKEN_POINTER")

    created = _payload(
        _run_concurrently(
            immutable_spec_kitty,
            project,
            [
                (
                    project.agent_b,
                    [
                        "agent",
                        "mission",
                        "create",
                        "wp05-no-opt-in",
                        "--start-branch",
                        "wp05-acceptance-b-9001",
                        "--topology",
                        "lanes_with_coord",
                        "--pr-bound",
                        "--branch-strategy",
                        "already-confirmed",
                        "--owned-checkout",
                        str(project.agent_b),
                        "--json",
                    ],
                )
            ],
        )[0]
    )
    linked_only_slug = str(created["mission_slug"])
    no_opt_primary = _run_cli(
        immutable_spec_kitty,
        project,
        project.primary,
        "next",
        "--mission",
        linked_only_slug,
        "--json",
    )
    no_opt_linked = _run_cli(
        immutable_spec_kitty,
        project,
        project.agent_b,
        "next",
        "--mission",
        linked_only_slug,
        "--json",
    )
    primary_payload = _error_payload(no_opt_primary, "MISSION_NOT_FOUND")
    linked_payload = _error_payload(no_opt_linked, "MISSION_NOT_FOUND")
    assert primary_payload == linked_payload


def test_owned_coord_retry_is_bounded_and_fails_closed_on_permanent_git_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A permanent git failure is re-raised immediately, never retry-masked."""
    resolve_owned_coordination_workspace = _owned_coord_retry_helper()

    permanent = subprocess.CalledProcessError(
        128,
        ["git", "worktree", "add"],
        stderr="fatal: permanent worktree failure",
    )

    class _PermanentlyBrokenWorkspace:
        calls = 0

        @classmethod
        def resolve(cls, _root: Path, _slug: str, _mid8: str) -> Path:
            cls.calls += 1
            raise permanent

    monkeypatch.setattr("time.sleep", lambda _seconds: None)
    with pytest.raises(subprocess.CalledProcessError) as raised:
        resolve_owned_coordination_workspace(
            _PermanentlyBrokenWorkspace,
            tmp_path,
            "permanent-failure-01KZTEST",
            "01KZTEST",
        )
    assert raised.value is permanent
    assert _PermanentlyBrokenWorkspace.calls == 1


def test_owned_coord_retry_never_retries_permission_denied_lock_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Lock wording alone cannot make a permanent permission error retryable."""
    resolve_owned_coordination_workspace = _owned_coord_retry_helper()
    permission_denied = subprocess.CalledProcessError(
        128,
        ["git", "worktree", "add"],
        stderr="fatal: could not lock config file .git/config: Permission denied",
    )

    class _PermissionDeniedWorkspace:
        calls = 0

        @classmethod
        def resolve(cls, _root: Path, _slug: str, _mid8: str) -> Path:
            cls.calls += 1
            raise permission_denied

    monkeypatch.setattr("time.sleep", lambda _seconds: None)
    with pytest.raises(subprocess.CalledProcessError) as raised:
        resolve_owned_coordination_workspace(
            _PermissionDeniedWorkspace,
            tmp_path,
            "permission-denied-01KZTEST",
            "01KZTEST",
        )
    assert raised.value is permission_denied
    assert _PermissionDeniedWorkspace.calls == 1


def test_owned_coord_retry_recovers_only_known_git_lock_contention(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Known config-lock contention retries within the fixed attempt bound."""
    resolve_owned_coordination_workspace = _owned_coord_retry_helper()

    expected = tmp_path / "coord"

    class _TransientWorkspace:
        calls = 0

        @classmethod
        def resolve(cls, _root: Path, _slug: str, _mid8: str) -> Path:
            cls.calls += 1
            if cls.calls < 3:
                raise subprocess.CalledProcessError(
                    128,
                    ["git", "worktree", "add"],
                    stderr="fatal: Unable to create '/repo/.git/config.lock': File exists.",
                )
            return expected

    monkeypatch.setattr("time.sleep", lambda _seconds: None)
    assert (
        resolve_owned_coordination_workspace(
            _TransientWorkspace,
            tmp_path,
            "transient-contention-01KZTEST",
            "01KZTEST",
        )
        == expected
    )
    assert _TransientWorkspace.calls == 3


def test_owned_coord_retry_re_raises_exact_transient_error_after_bound(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Persistent recognized contention keeps its terminal exception identity."""
    resolve_owned_coordination_workspace = _owned_coord_retry_helper()

    terminal = subprocess.CalledProcessError(
        128,
        ["git", "worktree", "add"],
        stderr="fatal: could not lock config file .git/config: File exists",
    )

    class _PersistentlyContendedWorkspace:
        calls = 0

        @classmethod
        def resolve(cls, _root: Path, _slug: str, _mid8: str) -> Path:
            cls.calls += 1
            raise terminal

    monkeypatch.setattr("time.sleep", lambda _seconds: None)
    with pytest.raises(subprocess.CalledProcessError) as raised:
        resolve_owned_coordination_workspace(
            _PersistentlyContendedWorkspace,
            tmp_path,
            "persistent-contention-01KZTEST",
            "01KZTEST",
        )
    assert raised.value is terminal
    assert _PersistentlyContendedWorkspace.calls == 20
