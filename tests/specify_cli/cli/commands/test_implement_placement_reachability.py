"""Reachability of the implement planning-placement arms (mission implement-degod, FR-015 / #5232).

``implement`` commits dirty planning artifacts before it allocates a workspace.  Where they land
depends on the planning placement: the WP action context's placement when it resolves, and a
degrade path when it does not (``ActionContextError``).  This suite pins, through the real command
on missions built with the real CLI (``agent mission create`` + ``agent mission finalize-tasks``),
the outcome of every reachable row of research.md R-1:

* the exit code and the console lines that name the outcome;
* the planning-artifact commits: how many, which files, and which branch received each;
* ``git status`` after the run.

Every mission is made dirty the same way before the run: an edited ``spec.md`` (a PRIMARY artifact)
and an untracked ``traces/approach.md`` (a COORD-residue artifact).  The rows pin today's outcome;
they must be identical before and after the placement moves into ``coordination/planning_commit``
(C-007: any difference is an operator decision, never an implementer's).

The second half unit-tests :func:`specify_cli.coordination.planning_commit.resolve_planning_placement`
on the same real fixtures.
"""

from __future__ import annotations

import json
import re
import subprocess
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest
import typer
from click.testing import Result
from typer.testing import CliRunner

from specify_cli.charter_runtime.preflight.ambient_warning import _reset_surfaced_for_testing
from specify_cli.cli.commands.agent import mission as mission_commands
from specify_cli.cli.commands.agent.workflow import top_level_implement

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

runner = CliRunner()

PLANNING_SUBJECT = "chore: planning artifacts for "
SPEC_MD = "# Spec\n\n## Functional Requirements\n\n| ID | Requirement | Status |\n|----|-------------|--------|\n| FR-001 | It works. | Draft |\n"
TASKS_MD = "# Tasks\n\n## Work Package WP01\n\n**Dependencies**: None\n\nImplement the demo.\n"
WP01_MD = (
    "---\nwork_package_id: WP01\ntitle: Demo\ndependencies: []\nrequirement_refs: [FR-001]\n"
    "subtasks: []\nowned_files: [src/demo/**]\nauthoritative_surface: src/demo/\n"
    "execution_mode: code_change\n---\n\n# WP01\n\nImplement the demo.\n"
)
MERGED_AT = "2026-10-04T00:00:00+00:00"
NOT_FINALIZED = "WP WP01 is not finalized; run `spec-kitty agent mission finalize-tasks`"
LEGACY_LINE = "(legacy path -- mission has no coordination_branch;"
DUPLICATE_WP_REFUSAL = "Transition planned -> claimed blocked: unsatisfied dependencies"


# ---------------------------------------------------------------------------
# Fixture building: the real CLI on a real repository
# ---------------------------------------------------------------------------


def git(repo: Path, *args: str, check: bool = True) -> str:
    result = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)
    if check and result.returncode != 0:
        raise AssertionError(f"git {args} failed: {result.stderr}")
    return result.stdout.strip()


def porcelain(repo: Path) -> list[str]:
    """``git status --porcelain`` lines, keeping each line's leading status column."""
    result = subprocess.run(["git", "-C", str(repo), "status", "--porcelain"], capture_output=True, text=True, check=True)
    return result.stdout.splitlines()


def _invoke(app: typer.Typer, args: list[str]) -> Result:
    return runner.invoke(app, args, catch_exceptions=False)


def _json_payload(text: str) -> dict[str, object]:
    payload, _ = json.JSONDecoder().raw_decode(text[text.index("{") :])
    assert isinstance(payload, dict)
    return payload


@dataclass(frozen=True)
class Built:
    """A finalized mission built through the real CLI."""

    repo: Path
    slug: str
    target: str

    @property
    def feature_dir(self) -> Path:
        return self.repo / "kitty-specs" / self.slug

    @property
    def meta_path(self) -> Path:
        return self.feature_dir / "meta.json"

    def meta(self) -> dict[str, object]:
        loaded: dict[str, object] = json.loads(self.meta_path.read_text(encoding="utf-8"))
        return loaded

    @property
    def coordination_branch(self) -> str:
        value = self.meta().get("coordination_branch")
        assert isinstance(value, str), "this row needs a mission with a coordination branch"
        return value

    def set_meta(self, *, drop: tuple[str, ...] = (), **fields: object) -> None:
        meta = self.meta()
        for key in drop:
            meta.pop(key, None)
        meta.update(fields)
        self.meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
        git(self.repo, "commit", "-qam", f"state: meta {sorted(fields) + list(drop)}")

    def coord_worktrees(self) -> list[Path]:
        lines = git(self.repo, "worktree", "list", "--porcelain").splitlines()
        return [Path(line.split(" ", 1)[1]) for line in lines if line.startswith("worktree ") and line.endswith("-coord")]


#: shape -> (stored topology passed to ``mission create``, target branch, protect ``main``)
SHAPES: dict[str, tuple[str, str, bool]] = {
    "flat": ("single_branch", "topic", False),
    "single_branch": ("single_branch", "topic", False),
    "single_branch_minted": ("single_branch", "main", True),
    "lanes": ("lanes", "topic", False),
    "coord": ("coord", "topic", False),
    "lanes_with_coord": ("lanes_with_coord", "topic", False),
    "coord_protected": ("coord", "main", True),
}


def _init_repo(root: Path, *, target: str, protect_main: bool) -> Path:
    root.mkdir(parents=True)
    git(root, "init", "-q", "-b", "main")
    git(root, "config", "commit.gpgsign", "false")
    (root / "README.md").write_text("base\n", encoding="utf-8")
    (root / ".kittify").mkdir()
    config = "mission_type_activations:\n  - software-dev\n"
    if protect_main:
        config += "\nprotection:\n  protected_branches:\n    - main\n"
    (root / ".kittify" / "config.yaml").write_text(config, encoding="utf-8")
    (root / ".gitignore").write_text(".worktrees/\n.kittify/derived/\n.kittify/workspaces/\n*.lock\n.kittify/runtime/\n", encoding="utf-8")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "base")
    if target != "main":
        git(root, "checkout", "-q", "-b", target)
    return root


def build_mission(root: Path, shape: str, monkeypatch: pytest.MonkeyPatch) -> Built:
    """Create and finalize one mission of *shape* with the real ``agent mission`` commands."""
    topology, target, protect_main = SHAPES[shape]
    repo = _init_repo(root, target=target, protect_main=protect_main)
    monkeypatch.chdir(repo)
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(repo))
    with monkeypatch.context() as build_env:
        if shape == "coord_protected":
            # The build itself commits planning artifacts onto protected ``main``.
            build_env.setenv("SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS", "1")
        created = _invoke(
            mission_commands.app,
            [
                "create",
                "demo",
                "--json",
                "--friendly-name",
                "demo",
                "--purpose-tldr",
                "Deliver demo.",
                "--purpose-context",
                "Exercise the implement planning placement.",
                "--topology",
                topology,
                "--target-branch",
                target,
            ],
        )
        assert created.exit_code == 0, created.output
        slug = Path(str(_json_payload(created.stdout)["feature_dir"])).name
        built = Built(repo=repo, slug=slug, target=target)
        feature_dir = built.feature_dir
        (feature_dir / "spec.md").write_text(SPEC_MD, encoding="utf-8")
        (feature_dir / "tasks").mkdir(exist_ok=True)
        (feature_dir / "tasks.md").write_text(TASKS_MD, encoding="utf-8")
        (feature_dir / "tasks" / "WP01-demo.md").write_text(WP01_MD, encoding="utf-8")
        (feature_dir / "plan.md").write_text("# Plan\n", encoding="utf-8")
        git(repo, "add", "-A")
        git(repo, "commit", "-q", "-m", "planning", check=False)
        finalized = _invoke(mission_commands.app, ["finalize-tasks", "--mission", slug, "--json"])
        assert finalized.exit_code == 0, finalized.output
        git(repo, "add", "-A")
        git(repo, "commit", "-q", "-m", "post-finalize", check=False)
    if shape == "flat":
        # A flat mission: no stored topology at all.
        built.set_meta(drop=("topology",))
    return built


@pytest.fixture(autouse=True)
def _fresh_charter_warning() -> Iterator[None]:
    """The charter preflight warning is shown once per process; give it back afterwards.

    Without this, a run here consumes the warning that ``test_implement_preflight`` later asserts.
    """
    _reset_surfaced_for_testing()
    yield
    _reset_surfaced_for_testing()


@pytest.fixture
def build(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Callable[[str], Built]]:
    empty_config = tmp_path / "empty.gitconfig"
    empty_config.write_text("", encoding="utf-8")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(empty_config))
    for name in ("GIT_AUTHOR_NAME", "GIT_COMMITTER_NAME"):
        monkeypatch.setenv(name, "Test")
    for name in ("GIT_AUTHOR_EMAIL", "GIT_COMMITTER_EMAIL"):
        monkeypatch.setenv(name, "t@example.com")
    monkeypatch.setenv("NO_COLOR", "1")
    monkeypatch.setenv("COLUMNS", "240")
    monkeypatch.delenv("SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS", raising=False)
    yield lambda shape: build_mission(tmp_path / shape, shape, monkeypatch)


# ---------------------------------------------------------------------------
# State mutations (research harness states.py, re-created)
# ---------------------------------------------------------------------------


def duplicate_wp_prompt(built: Built) -> None:
    """Two prompts match ``WP01``: the WP action context fails with ``WORK_PACKAGE_UNRESOLVED``."""
    source = built.feature_dir / "tasks" / "WP01-demo.md"
    (source.parent / "WP01-zcopy.md").write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    git(built.repo, "add", "-A")
    git(built.repo, "commit", "-qm", "state: duplicate WP01 prompt")


def remove_coord_worktrees(built: Built) -> None:
    for worktree in built.coord_worktrees():
        git(built.repo, "worktree", "remove", "--force", str(worktree))


def delete_coordination_branch(built: Built) -> None:
    branch = built.coordination_branch
    remove_coord_worktrees(built)
    git(built.repo, "branch", "-D", branch)


def project_status_and_mark_merged(built: Built) -> None:
    """Consolidation: the status log is projected onto the primary checkout and the merge recorded."""
    coord_events = built.coord_worktrees()[0] / "kitty-specs" / built.slug / "status.events.jsonl"
    (built.feature_dir / "status.events.jsonl").write_text(coord_events.read_text(encoding="utf-8"), encoding="utf-8")
    git(built.repo, "add", "-A")
    git(built.repo, "commit", "-qm", "state: project status to primary (consolidation)")
    built.set_meta(baseline_merge_commit=git(built.repo, "rev-parse", "HEAD"), merged_at=MERGED_AT)


def publish_onto_main(built: Built) -> None:
    """PUBLISHED: terminal evidence recorded, the target merged into ``main`` and its ref deleted."""
    built.set_meta(mission_number=1)
    git(built.repo, "checkout", "-q", "main")
    git(built.repo, "merge", "-q", "--ff-only", built.target)
    git(built.repo, "branch", "-D", built.target)


def make_dirty(built: Built) -> None:
    """A dirty PRIMARY ``spec.md`` and an untracked COORD-residue trace file."""
    (built.feature_dir / "spec.md").write_text(SPEC_MD + "\nEdited after finalize.\n", encoding="utf-8")
    traces = built.feature_dir / "traces"
    traces.mkdir(exist_ok=True)
    (traces / "approach.md").write_text("# approach\n- uncommitted tracer entry\n", encoding="utf-8")


def commit_trace_on_primary(built: Built) -> None:
    """A COORD-residue file committed on the primary checkout only (never reached the coord branch)."""
    traces = built.feature_dir / "traces"
    traces.mkdir(exist_ok=True)
    (traces / "approach.md").write_text("# approach\n- tracer committed on primary only\n", encoding="utf-8")
    git(built.repo, "add", "-A")
    git(built.repo, "-c", "core.hooksPath=/dev/null", "commit", "-qm", "trace on primary", "--no-verify")


# ---------------------------------------------------------------------------
# Running implement and recording the outcome
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Outcome:
    exit_code: int
    console: str
    #: one entry per planning-artifact commit: (receiving non-lane branches, files), normalized
    planning_commits: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...]
    status: tuple[str, ...]


def _flat(text: str) -> str:
    return " ".join(re.sub(r"[│├└─╭╮╰╯●○]", " ", text).split())


def _normalizer(built: Built) -> Callable[[str], str]:
    mission_id = str(built.meta().get("mission_id", ""))

    def normalize(text: str) -> str:
        text = text.replace(str(built.repo), "<repo>").replace(built.slug, "<slug>")
        return text.replace(mission_id, "<mission_id>") if mission_id else text

    return normalize


def _all_commits(repo: Path) -> set[str]:
    return set(git(repo, "rev-list", "--all").split())


def _planning_commits(built: Built, before: set[str]) -> tuple[tuple[tuple[str, ...], tuple[str, ...]], ...]:
    normalize = _normalizer(built)
    records = []
    for sha in sorted(_all_commits(built.repo) - before):
        if not git(built.repo, "log", "-1", "--format=%s", sha).startswith(PLANNING_SUBJECT):
            continue
        receivers = git(built.repo, "for-each-ref", "--contains", sha, "--format=%(refname:short)", "refs/heads").split()
        branches = tuple(sorted(normalize(ref) for ref in receivers if "-lane-" not in ref))
        files = tuple(sorted(normalize(path) for path in git(built.repo, "show", "--name-only", "--format=", sha).split()))
        records.append((branches, files))
    return tuple(sorted(records))


def run_implement(built: Built, *, auto_commit: bool = True) -> Outcome:
    before = _all_commits(built.repo)
    app = typer.Typer()
    app.command()(top_level_implement)
    result = runner.invoke(app, ["WP01", "--mission", built.slug, "--auto-commit" if auto_commit else "--no-auto-commit"])
    normalize = _normalizer(built)
    status = tuple(sorted(normalize(line) for line in porcelain(built.repo)))
    return Outcome(
        exit_code=result.exit_code,
        console=normalize(_flat(result.output)),
        planning_commits=_planning_commits(built, before),
        status=status,
    )


def commit(branches: str | tuple[str, ...], *files: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    receivers = (branches,) if isinstance(branches, str) else branches
    return tuple(sorted(receivers)), tuple(sorted(f"kitty-specs/<slug>/{name}" for name in files))


COORD = "kitty/mission-<slug>"
SPEC = "spec.md"
TRACE = "traces/approach.md"
UNTRACKED_TRACES = "?? kitty-specs/<slug>/traces/"
DIRTY_SPEC = " M kitty-specs/<slug>/spec.md"
LEGACY_WARNING_MARKER = "?? .kittify/legacy-warning-shown-<mission_id>"
COORD_SUCCESS = "Planning artifacts committed to coordination branch kitty/mission-<slug>"
COORD_DELETED = f"Coordination branch '{COORD}' for mission '<slug>' is declared in meta.json but deleted from git."
PLACEMENT_REFUSAL = "Cannot resolve the canonical write placement for this mission's WP status claim commit"


def assert_outcome(
    outcome: Outcome,
    *,
    exit_code: int,
    commits: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...],
    status: tuple[str, ...],
    present: tuple[str, ...] = (),
    absent: tuple[str, ...] = (),
) -> None:
    assert outcome.exit_code == exit_code, outcome.console
    assert outcome.planning_commits == tuple(sorted(commits)), outcome.console
    assert outcome.status == tuple(sorted(status))
    for fragment in present:
        assert fragment in outcome.console, fragment
    for fragment in absent:
        assert fragment not in outcome.console, fragment


# ---------------------------------------------------------------------------
# Row 1: healthy missions take the resolved partition arm
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("shape", "commits", "status", "success_line", "legacy"),
    [
        pytest.param(
            "flat",
            (commit("topic", SPEC), commit("topic", TRACE)),
            (LEGACY_WARNING_MARKER,),
            "Planning artifacts committed to topic",
            True,
            id="flat",
        ),
        pytest.param(
            "single_branch",
            (commit("topic", SPEC), commit("topic", TRACE)),
            (),
            "Planning artifacts committed to topic",
            True,
            id="single_branch",
        ),
        pytest.param(
            "single_branch_minted",
            (commit(COORD, SPEC), commit(COORD, TRACE)),
            (),
            "Planning artifacts committed to kitty/mission-<slug>",
            True,
            id="single_branch_minted",
        ),
        pytest.param(
            "lanes",
            # The mission branch is cut from the target after the commits, so both carry them.
            (commit((COORD, "topic"), SPEC), commit((COORD, "topic"), TRACE)),
            (),
            "Planning artifacts committed to topic",
            True,
            id="lanes",
        ),
        pytest.param("coord", (commit(COORD, TRACE), commit("topic", SPEC)), (UNTRACKED_TRACES,), COORD_SUCCESS, False, id="coord"),
        pytest.param(
            "lanes_with_coord",
            (commit(COORD, TRACE), commit("topic", SPEC)),
            (UNTRACKED_TRACES,),
            COORD_SUCCESS,
            False,
            id="lanes_with_coord",
        ),
    ],
)
def test_healthy_mission_takes_the_resolved_partition_arm(
    build: Callable[[str], Built],
    shape: str,
    commits: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...],
    status: tuple[str, ...],
    success_line: str,
    legacy: bool,
) -> None:
    """The context resolves: PRIMARY ``spec.md`` and the COORD-residue trace commit separately."""
    built = build(shape)
    make_dirty(built)

    outcome = run_implement(built)

    assert_outcome(
        outcome,
        exit_code=0,
        commits=commits,
        status=status,
        present=(success_line, LEGACY_LINE) if legacy else (success_line,),
        absent=() if legacy else (LEGACY_LINE,),
    )


# ---------------------------------------------------------------------------
# Row 2: an unresolved WP context (duplicate prompt) takes the degrade arms
# ---------------------------------------------------------------------------


def test_duplicate_wp_on_a_flat_mission_commits_one_transaction_then_refuses(build: Callable[[str], Built]) -> None:
    """Arm (a): no coordination ref, so the whole batch lands on the planning branch in one commit."""
    built = build("flat")
    duplicate_wp_prompt(built)
    make_dirty(built)

    outcome = run_implement(built)

    assert_outcome(
        outcome,
        exit_code=1,
        commits=(commit("topic", SPEC, TRACE),),
        status=(" M kitty-specs/<slug>/meta.json", LEGACY_WARNING_MARKER),
        present=(LEGACY_LINE, "Planning artifacts committed to topic", DUPLICATE_WP_REFUSAL),
    )


def test_duplicate_wp_on_a_coord_mission_partitions_then_refuses(build: Callable[[str], Built]) -> None:
    """Arm (c): a coordination ref and an unprotected planning branch, so the batch is partitioned."""
    built = build("coord")
    duplicate_wp_prompt(built)
    make_dirty(built)

    outcome = run_implement(built)

    assert_outcome(
        outcome,
        exit_code=1,
        commits=(commit(COORD, TRACE), commit("topic", SPEC)),
        status=(" M kitty-specs/<slug>/meta.json", " M kitty-specs/<slug>/tasks/WP01-demo.md", UNTRACKED_TRACES),
        present=(COORD_SUCCESS, DUPLICATE_WP_REFUSAL),
        absent=(LEGACY_LINE,),
    )


# ---------------------------------------------------------------------------
# Row 3: a missing or corrupt lanes.json stops implement before any commit
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("damage", "status_line", "refusal"),
    [
        pytest.param(
            "missing",
            " D kitty-specs/<slug>/lanes.json",
            "lanes.json is required for <repo>/kitty-specs/<slug>. Run 'spec-kitty agent mission finalize-tasks'",
            id="missing",
        ),
        pytest.param(
            "corrupt",
            " M kitty-specs/<slug>/lanes.json",
            "lanes.json at <repo>/kitty-specs/<slug>/lanes.json is corrupt or malformed",
            id="corrupt",
        ),
    ],
)
def test_broken_lanes_json_refuses_before_any_planning_commit(build: Callable[[str], Built], damage: str, status_line: str, refusal: str) -> None:
    built = build("coord")
    lanes_json = built.feature_dir / "lanes.json"
    if damage == "missing":
        lanes_json.unlink()
    else:
        lanes_json.write_text("{not json", encoding="utf-8")
    make_dirty(built)

    outcome = run_implement(built)

    assert_outcome(outcome, exit_code=1, commits=(), status=(status_line, DIRTY_SPEC, UNTRACKED_TRACES), present=(refusal,))


# ---------------------------------------------------------------------------
# Row 4: a declared coordination branch that was never created
# ---------------------------------------------------------------------------


def test_never_created_coordination_branch_is_refused_at_the_commit(build: Callable[[str], Built]) -> None:
    """The context resolves; the PRIMARY group commits, the COORD group is refused at its missing ref."""
    built = build("coord")
    built.set_meta(coordination_branch=f"kitty/mission-{built.slug}-ghost")
    make_dirty(built)

    outcome = run_implement(built)

    assert_outcome(
        outcome,
        exit_code=1,
        commits=(commit("topic", SPEC),),
        status=(UNTRACKED_TRACES,),
        present=(
            "Bookkeeping refused: DESTINATION_REF_NOT_FOUND: Refusing to record 'planning artifacts for <slug>': "
            "destination_ref 'kitty/mission-<slug>-ghost' does not exist",
        ),
    )


# ---------------------------------------------------------------------------
# Row 5: lifecycle phases
# ---------------------------------------------------------------------------


def test_consolidated_mission_with_kept_coordination_branch(build: Callable[[str], Built]) -> None:
    built = build("coord")
    project_status_and_mark_merged(built)
    make_dirty(built)

    outcome = run_implement(built)

    assert_outcome(outcome, exit_code=0, commits=(commit(COORD, TRACE), commit("topic", SPEC)), status=(UNTRACKED_TRACES,), present=(COORD_SUCCESS,))


def test_published_mission_is_refused_on_the_protected_primary_branch(build: Callable[[str], Built]) -> None:
    """PUBLISHED (target merged into ``main`` and deleted): refused before any planning commit."""
    built = build("lanes")
    publish_onto_main(built)
    make_dirty(built)

    outcome = run_implement(built)

    assert_outcome(
        outcome,
        exit_code=1,
        commits=(),
        status=(DIRTY_SPEC, UNTRACKED_TRACES),
        present=("Refusing to start implementation status on protected branch 'main' before mutating status files.",),
    )


def test_merged_mission_with_torn_down_coordination_branch_rerun_clean(build: Callable[[str], Built]) -> None:
    built = build("coord")
    project_status_and_mark_merged(built)
    delete_coordination_branch(built)

    outcome = run_implement(built)

    assert_outcome(outcome, exit_code=0, commits=(), status=(), absent=("Planning artifacts committed",))


def test_merged_mission_with_torn_down_coordination_branch_rerun_dirty(build: Callable[[str], Built]) -> None:
    """The PRIMARY group commits first, then the COORD group hits ``CoordinationBranchDeleted``."""
    built = build("coord")
    project_status_and_mark_merged(built)
    delete_coordination_branch(built)
    make_dirty(built)

    outcome = run_implement(built)

    assert_outcome(outcome, exit_code=1, commits=(commit("topic", SPEC),), status=(UNTRACKED_TRACES,), present=(COORD_DELETED,))


# ---------------------------------------------------------------------------
# Row 6: refused before placement is ever consulted
# ---------------------------------------------------------------------------


def test_unmaterialized_coordination_worktree_is_refused_as_not_finalized(build: Callable[[str], Built]) -> None:
    built = build("coord")
    remove_coord_worktrees(built)
    make_dirty(built)

    outcome = run_implement(built)

    assert_outcome(outcome, exit_code=1, commits=(), status=(DIRTY_SPEC, UNTRACKED_TRACES), present=(NOT_FINALIZED,))


def test_coordination_branch_deleted_before_merge_is_refused_at_the_status_surface(build: Callable[[str], Built]) -> None:
    built = build("coord")
    delete_coordination_branch(built)
    make_dirty(built)

    outcome = run_implement(built)

    assert_outcome(outcome, exit_code=1, commits=(), status=(DIRTY_SPEC, UNTRACKED_TRACES), present=(COORD_DELETED,))


# ---------------------------------------------------------------------------
# Row 7: arm (b), the protected planning branch with no resolvable placement
# ---------------------------------------------------------------------------


def test_protected_planning_branch_without_a_resolved_placement_raises(build: Callable[[str], Built]) -> None:
    """Coord mission on protected ``main``, ``--no-auto-commit``, committed residue, duplicate WP."""
    built = build("coord_protected")
    commit_trace_on_primary(built)
    duplicate_wp_prompt(built)

    outcome = run_implement(built, auto_commit=False)

    assert_outcome(
        outcome,
        exit_code=1,
        commits=(),
        status=(),
        present=(PLACEMENT_REFUSAL, "Run `spec-kitty doctor coordination --mission <slug> --fix` to repair automatically"),
    )


# ---------------------------------------------------------------------------
# resolve_planning_placement (the seam that owns the placement decision)
# ---------------------------------------------------------------------------


def test_placement_resolves_on_a_healthy_coord_mission(build: Callable[[str], Built]) -> None:
    from specify_cli.coordination.planning_commit import resolve_planning_placement

    built = build("coord")

    placement = resolve_planning_placement(built.repo, mission_slug=built.slug, wp_id="WP01")

    assert placement.resolved is True
    assert placement.ref is not None
    assert placement.ref.ref == built.coordination_branch
    assert placement.coordination_ref == built.coordination_branch


def test_placement_resolves_without_a_coordination_ref_on_a_flat_mission(build: Callable[[str], Built]) -> None:
    from specify_cli.coordination.planning_commit import resolve_planning_placement

    built = build("flat")

    placement = resolve_planning_placement(built.repo, mission_slug=built.slug, wp_id="WP01")

    assert placement.resolved is True
    assert placement.ref is not None
    assert placement.ref.ref == "topic"
    assert placement.coordination_ref is None


def test_unresolved_placement_carries_the_seam_coordination_ref_on_a_coord_mission(build: Callable[[str], Built]) -> None:
    from specify_cli.coordination.planning_commit import resolve_planning_placement

    built = build("coord")
    duplicate_wp_prompt(built)

    placement = resolve_planning_placement(built.repo, mission_slug=built.slug, wp_id="WP01")

    assert placement.resolved is False
    assert placement.ref is None
    assert placement.coordination_ref == built.coordination_branch


def test_unresolved_placement_has_no_coordination_ref_on_a_flat_mission(build: Callable[[str], Built]) -> None:
    from specify_cli.coordination.planning_commit import resolve_planning_placement

    built = build("flat")
    duplicate_wp_prompt(built)

    placement = resolve_planning_placement(built.repo, mission_slug=built.slug, wp_id="WP01")

    assert placement.resolved is False
    assert placement.ref is None
    assert placement.coordination_ref is None


def test_unresolved_placement_has_no_coordination_ref_when_none_is_declared(build: Callable[[str], Built]) -> None:
    """A topology that routes through coordination but declares no branch degrades like a flat one."""
    from specify_cli.coordination.planning_commit import resolve_planning_placement

    built = build("lanes")
    built.set_meta(topology="coord")
    duplicate_wp_prompt(built)

    placement = resolve_planning_placement(built.repo, mission_slug=built.slug, wp_id="WP01")

    assert placement.resolved is False
    assert placement.coordination_ref is None


def test_unresolved_placement_raises_when_the_seam_cannot_resolve(build: Callable[[str], Built], monkeypatch: pytest.MonkeyPatch) -> None:
    from mission_runtime import ActionContextError, MissionArtifactKind
    from mission_runtime import placement_seam as real_seam

    from specify_cli.coordination import planning_commit
    from specify_cli.core.errors import PlacementResolutionRequired

    built = build("coord")
    duplicate_wp_prompt(built)

    class _WriteTargetUnresolvable:
        """The real seam, except that it cannot resolve a write target."""

        def __init__(self, repo_root: Path, mission_slug: str) -> None:
            self._real = real_seam(repo_root, mission_slug)

        def read_dir(self, kind: MissionArtifactKind) -> Path:
            return self._real.read_dir(kind)

        def write_target(self, kind: MissionArtifactKind) -> object:
            raise ActionContextError("TEST_SEAM_UNRESOLVABLE", "seam cannot resolve")

    monkeypatch.setattr(planning_commit, "placement_seam", _WriteTargetUnresolvable)

    with pytest.raises(PlacementResolutionRequired) as raised:
        planning_commit.resolve_planning_placement(built.repo, mission_slug=built.slug, wp_id="WP01")

    assert str(raised.value) == planning_commit.placement_resolution_remedy(built.slug)


def test_placement_resolution_remedy_text_is_pinned() -> None:
    from specify_cli.coordination.planning_commit import placement_resolution_remedy

    assert placement_resolution_remedy("demo-mission") == (
        "Cannot resolve the canonical write placement for this mission's "
        "WP status claim commit -- refusing to commit to the currently "
        "checked-out branch (D11 fail-closed). This usually means the "
        "mission's stored coordination topology could not be resolved "
        "(e.g. the coordination worktree has not been materialized yet, "
        "or the `coordination_branch` declared in meta.json is missing/"
        "torn down in git). Run `spec-kitty doctor coordination "
        "--mission demo-mission --fix` to repair automatically -- it "
        "materializes a present branch, or flattens (removes the stale "
        "key) if the topology was never activated; or remove "
        "`coordination_branch` from meta.json manually if you know the "
        "coordination topology was never used, then retry."
    )


def test_broken_lanes_json_propagates_out_of_the_placement(build: Callable[[str], Built]) -> None:
    """A non-``ActionContextError`` from the context resolve is today's pre-commit gate: it propagates."""
    from specify_cli.coordination.planning_commit import resolve_planning_placement
    from specify_cli.lanes.persistence import MissingLanesError

    built = build("coord")
    (built.feature_dir / "lanes.json").unlink()

    with pytest.raises(MissingLanesError):
        resolve_planning_placement(built.repo, mission_slug=built.slug, wp_id="WP01")
