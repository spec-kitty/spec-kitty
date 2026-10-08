"""#5673: the work-package claim commit carries only the paths the claim wrote.

Cases 1-2 drive the pre-existing ``spec-kitty implement`` entry point in a child process on a real
``single_branch`` repository with unrelated staged, dirty and untracked operator work. Cases 3-5
drive the claim seam (``_commit_wp_claim_status``) directly on a real repository, for the states the
CLI cannot reach (a ``meta.json`` that is dirty before the claim, WP prompt and ``tasks.md`` edits,
``--no-auto-commit`` staging).

The claim-written set is the primary-surface status pair, plus the mission's ``meta.json`` only when
the claim itself wrote the VCS lock and it was clean before, plus the claimed WP prompt only when workspace
allocation stamped it in this claim (lanes and coord topologies) and it was clean before. Never
``.kittify/config.yaml``, another WP's prompt or ``tasks.md``. Every case that asserts the commit's file set is red on the unfixed base.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from specify_cli.cli.commands import implement_claim
from tests._support.git_cli import git_out
from tests.specify_cli.cli.commands.test_single_branch_implement_refusals import _build_mission
from tests.upgrade.preview_support.process import child_environment

pytestmark = [pytest.mark.git_repo, pytest.mark.non_sandbox, pytest.mark.regression]

_BRANCH = "work"
_SLUG = "claim-scope-01M4AKVE"
_MISSION_ID = "01M4AKVE000000000000000001"
_CLAIM_SUBJECT = "chore: WP01 claimed for implementation"
_CHECKOUT = Path(__file__).resolve().parents[4]


def _git(repo: Path, *args: str, env: dict[str, str]) -> str:
    done = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True, env=env)
    return done.stdout.strip()


def _child_env(tmp_path: Path) -> dict[str, str]:
    env = child_environment(tmp_path / "sandbox")
    home = Path(env["HOME"])
    home.mkdir(parents=True, exist_ok=True)
    (home / ".gitconfig").write_text("[user]\n\tname = Test\n\temail = t@example.com\n[commit]\n\tgpgsign = false\n", encoding="utf-8")
    env["PYTHONPATH"] = str(_CHECKOUT / "src")
    env["SPEC_KITTY_NO_UPGRADE_CHECK"] = "1"
    env["PATH"] = f"{Path(sys.executable).parent}:{env['PATH']}"
    return env


def _cli_repo(tmp_path: Path, env: dict[str, str]) -> Path:
    """A committed ``single_branch`` mission on the non-protected branch ``work``, WP01 ``planned``."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "--template=", "-b", _BRANCH, env=env)
    for key, value in (("user.name", "Test"), ("user.email", "t@example.com"), ("commit.gpgsign", "false")):
        _git(repo, "config", key, value, env=env)
    (repo / ".kittify").mkdir()
    (repo / ".kittify" / "config.yaml").write_text("agents:\n  available:\n    - claude\n", encoding="utf-8")
    (repo / "seed.txt").write_text("seed\n", encoding="utf-8")
    _git(repo, "add", "-A", env=env)
    _git(repo, "commit", "-q", "-m", "seed", env=env)
    _build_mission(repo, _SLUG, _MISSION_ID, target_branch=_BRANCH)
    return repo


def _implement(repo: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    argv = [sys.executable, "-m", "specify_cli", "implement", "WP01", "--mission", _SLUG, "--auto-commit"]
    return subprocess.run(argv, cwd=repo, env=env, capture_output=True, text=True, timeout=180, check=False)


def _claim_commit_files(repo: Path, env: dict[str, str]) -> set[str]:
    log = _git(repo, "log", "--format=%H%x00%s", env=env)
    shas = [line.split("\x00")[0] for line in log.splitlines() if line.split("\x00")[1] == _CLAIM_SUBJECT]
    assert len(shas) == 1, f"expected exactly one claim commit, log:\n{log}"
    return set(_git(repo, "show", "--name-only", "--format=", shas[0], env=env).split())


def _expected_claim_set(repo: Path) -> set[str]:
    base = {f"kitty-specs/{_SLUG}/status.events.jsonl", f"kitty-specs/{_SLUG}/meta.json"}
    snapshot = f"kitty-specs/{_SLUG}/status.json"
    return base | ({snapshot} if (repo / snapshot).exists() else set())


def test_claim_commit_leaves_a_dirty_config_and_unrelated_work_out(tmp_path: Path) -> None:
    """US4-1: a dirty ``.kittify/config.yaml`` is not swept into the claim commit.

    ``single_branch`` refuses every other dirty, staged or untracked file in the write checkout
    (``WRITE_CHECKOUT_DIRTY``), so only ``.kittify/`` edits reach the claim there; unrelated staged and
    untracked work is covered at the seam in the WP-prompt case below.

    Exact equality on the file set kills a mutant that only drops ``config.yaml`` but keeps the WP
    prompt or ``tasks.md``. Red on the base: the commit also carries ``config.yaml`` and the WP file.
    """
    env = _child_env(tmp_path)
    repo = _cli_repo(tmp_path, env)
    config = repo / ".kittify" / "config.yaml"
    with config.open("a", encoding="utf-8") as handle:
        handle.write("operator_edit: true\n")

    done = _implement(repo, env)

    assert done.returncode == 0, f"{done.stdout}\n{done.stderr}"
    assert _claim_commit_files(repo, env) == _expected_claim_set(repo)
    assert "operator_edit: true" in _git(repo, "diff", "--", ".kittify/config.yaml", env=env)
    assert _git(repo, "diff", "--cached", "--name-only", env=env) == ""


def test_claim_commit_with_clean_config_is_exactly_the_claim_written_set(tmp_path: Path) -> None:
    """US4-2 positive control. Kills a "commit nothing" mutant and a "drop meta.json although the
    claim wrote the VCS lock" mutant. Red on the base too: the WP file is in today's bundle."""
    env = _child_env(tmp_path)
    repo = _cli_repo(tmp_path, env)

    done = _implement(repo, env)

    assert done.returncode == 0, f"{done.stdout}\n{done.stderr}"
    assert _claim_commit_files(repo, env) == _expected_claim_set(repo)


# ---------------------------------------------------------------------------
# The claim seam on a real repository (cases 3-5).
# ---------------------------------------------------------------------------

_META_BASE = {"mission_id": _MISSION_ID, "mission_slug": _SLUG, "mid8": "01M4AKVE", "topology": "flat", "target_branch": _BRANCH}


@pytest.fixture
def seam(tmp_path: Path) -> SimpleNamespace:
    """A flat repo on its recorded target branch; everything committed, so each test dirties what it needs."""
    repo = tmp_path / "repo"
    repo.mkdir()
    git_out(repo, "init", "-qb", _BRANCH)
    git_out(repo, "config", "user.email", "test@test.com")
    git_out(repo, "config", "user.name", "Test")
    feature_dir = repo / "kitty-specs" / _SLUG
    (feature_dir / "tasks").mkdir(parents=True)
    wp_file = feature_dir / "tasks" / "WP01-demo.md"
    wp_file.write_text("---\nwork_package_id: WP01\n---\nbody\n", encoding="utf-8")
    (feature_dir / "tasks.md").write_text("# Tasks\n", encoding="utf-8")
    (feature_dir / "meta.json").write_text(json.dumps(_META_BASE), encoding="utf-8")
    (feature_dir / "status.events.jsonl").write_text('{"n":1}\n', encoding="utf-8")
    (feature_dir / "status.json").write_text('{"n":1}\n', encoding="utf-8")
    config = repo / ".kittify" / "config.yaml"
    config.parent.mkdir()
    config.write_text("x: 1\n", encoding="utf-8")
    git_out(repo, "add", "-A")
    git_out(repo, "commit", "-qm", "seed")
    return SimpleNamespace(repo=repo, feature_dir=feature_dir, wp_file=wp_file, config=config)


def _simulate_claim_writes(env: SimpleNamespace, *, lock_vcs: bool) -> None:
    """What the claim writes: the status pair and, on a first claim, the VCS lock in ``meta.json``."""
    (env.feature_dir / "status.events.jsonl").write_text('{"n":1}\n{"n":2}\n', encoding="utf-8")
    (env.feature_dir / "status.json").write_text('{"n":2}\n', encoding="utf-8")
    if lock_vcs:
        meta_path = env.feature_dir / "meta.json"
        meta_path.write_text(json.dumps({**json.loads(meta_path.read_text(encoding="utf-8")), "vcs": "git"}), encoding="utf-8")


def _claim(env: SimpleNamespace, *, auto_commit: bool | None = True, meta_written: bool = False, meta_dirty_before: bool = False) -> None:
    implement_claim._commit_wp_claim_status(
        repo_root=env.repo,
        feature_dir=env.feature_dir,
        mission_slug=_SLUG,
        wp_id="WP01",
        auto_commit=auto_commit,
        status_result=SimpleNamespace(status_changed=True),
        meta_written=meta_written,
        meta_dirty_before=meta_dirty_before,
    )


def _head_files(repo: Path) -> set[str]:
    return set(git_out(repo, "show", "--name-only", "--format=", "HEAD").split())


def test_a_meta_json_dirty_before_the_claim_is_left_uncommitted_with_a_warning(seam: SimpleNamespace, capsys: pytest.CaptureFixture[str]) -> None:
    """Case 3. Kills a mutant that commits ``meta.json`` whenever it exists or whenever the claim wrote it."""
    meta_path = seam.feature_dir / "meta.json"
    meta_path.write_text(json.dumps({**_META_BASE, "operator_note": "x"}), encoding="utf-8")
    _simulate_claim_writes(seam, lock_vcs=True)

    _claim(seam, meta_written=True, meta_dirty_before=True)

    assert git_out(seam.repo, "log", "-1", "--format=%s") == _CLAIM_SUBJECT
    assert _head_files(seam.repo) == {f"kitty-specs/{_SLUG}/status.events.jsonl", f"kitty-specs/{_SLUG}/status.json"}
    assert "operator_note" in git_out(seam.repo, "diff", "--", f"kitty-specs/{_SLUG}/meta.json")
    out = capsys.readouterr().out
    assert "meta.json" in out
    assert "uncommitted" in out


def test_operator_edits_to_the_wp_prompt_and_tasks_md_stay_out_of_the_claim_commit(seam: SimpleNamespace) -> None:
    """Case 4. Kills "the WP file is still bundled" and "``tasks.md`` is still bundled via the status artifacts"."""
    seam.wp_file.write_text("---\nwork_package_id: WP01\n---\noperator edit\n", encoding="utf-8")
    tasks_md = seam.feature_dir / "tasks.md"
    tasks_md.write_text("# Tasks\noperator edit\n", encoding="utf-8")
    (seam.repo / "notes").mkdir()
    (seam.repo / "notes" / "staged.md").write_text("staged\n", encoding="utf-8")
    git_out(seam.repo, "add", "notes/staged.md")
    (seam.repo / "scratch.txt").write_text("scratch\n", encoding="utf-8")
    _simulate_claim_writes(seam, lock_vcs=False)

    _claim(seam)

    assert _head_files(seam.repo) == {f"kitty-specs/{_SLUG}/status.events.jsonl", f"kitty-specs/{_SLUG}/status.json"}
    assert git_out(seam.repo, "diff", "--cached", "--name-only") == "notes/staged.md"
    assert "?? scratch.txt" in git_out(seam.repo, "status", "--porcelain")
    assert "operator edit" in seam.wp_file.read_text(encoding="utf-8")
    assert "operator edit" in tasks_md.read_text(encoding="utf-8")
    unstaged = set(git_out(seam.repo, "diff", "--name-only").split())
    assert unstaged == {f"kitty-specs/{_SLUG}/tasks/WP01-demo.md", f"kitty-specs/{_SLUG}/tasks.md"}


def test_no_auto_commit_stages_exactly_the_claim_written_set(seam: SimpleNamespace) -> None:
    """Case 5 (#3471 kept). Kills staging the WP file, ``tasks.md`` or ``config.yaml``, and dropping a written ``meta.json``."""
    seam.wp_file.write_text("---\nwork_package_id: WP01\n---\noperator edit\n", encoding="utf-8")
    (seam.feature_dir / "tasks.md").write_text("# Tasks\noperator edit\n", encoding="utf-8")
    seam.config.write_text("x: 2\n", encoding="utf-8")
    _simulate_claim_writes(seam, lock_vcs=True)
    head_before = git_out(seam.repo, "rev-parse", "HEAD")

    _claim(seam, auto_commit=False, meta_written=True)

    assert git_out(seam.repo, "rev-parse", "HEAD") == head_before
    assert set(git_out(seam.repo, "diff", "--cached", "--name-only").split()) == {
        f"kitty-specs/{_SLUG}/status.events.jsonl",
        f"kitty-specs/{_SLUG}/status.json",
        f"kitty-specs/{_SLUG}/meta.json",
    }


# ---------------------------------------------------------------------------
# Lanes / coord topologies: allocation stamps the claimed WP prompt (cycle-1 review, FR-009).
# ---------------------------------------------------------------------------

_LANES_SLUG = "lanes-claim-01M4AKVE"


def _lanes_mission(repo: Path):  # type: ignore[no-untyped-def]
    from tests.specify_cli.cli.commands._implement_fixtures import MISSION_ID, SLUG, build_mission

    return build_mission(
        repo,
        SLUG,
        MISSION_ID,
        wps={"WP01": ("code_change", []), "WP02": ("code_change", [])},
        layout=(("lane-a", ("WP01",), ()), ("lane-b", ("WP02",), ())),
        spec_text="# Spec\n",
    )


def _committed_files(repo: Path, subject: str) -> set[str]:
    from tests._support.git_cli import git_out as _g

    shas = [ln.split("\x00")[0] for ln in _g(repo, "log", "--format=%H%x00%s").splitlines() if ln.split("\x00")[1] == subject]
    assert len(shas) == 1, shas
    return set(_g(repo, "show", "--name-only", "--format=", shas[0]).split())


def test_lanes_claim_commits_the_stamped_wp_prompt_and_leaves_a_clean_tree(repo: Path) -> None:
    """(a) The stamp allocation wrote into the claimed WP prompt is the claim's own write: it rides the claim commit."""
    from tests.specify_cli.cli.commands._implement_fixtures import SLUG, implement_cli

    mission = _lanes_mission(repo)

    done = implement_cli("WP01", "--mission", SLUG, "--actor", "tester", "--auto-commit")

    assert done.exit_code == 0, done.output
    rel = f"kitty-specs/{SLUG}"
    files = _committed_files(repo, "chore: WP01 claimed for implementation")
    assert f"{rel}/tasks/WP01-test.md" in files
    assert f"{rel}/tasks/WP02-test.md" not in files
    assert f"{rel}/tasks.md" not in files
    assert "created_at:" in (mission.feature_dir / "tasks" / "WP01-test.md").read_text(encoding="utf-8")
    assert git_out(repo, "status", "--porcelain", "--untracked-files=no") == ""


def test_lanes_no_auto_commit_stages_the_stamped_wp_prompt(repo: Path) -> None:
    """(b) #3471: ``--no-auto-commit`` stages every claim write, the stamped prompt included; nothing is left unstaged."""
    from tests.specify_cli.cli.commands._implement_fixtures import SLUG, implement_cli

    _lanes_mission(repo)

    done = implement_cli("WP01", "--mission", SLUG, "--actor", "tester", "--no-auto-commit")

    assert done.exit_code == 0, done.output
    assert f"kitty-specs/{SLUG}/tasks/WP01-test.md" in set(git_out(repo, "diff", "--cached", "--name-only").splitlines())
    assert git_out(repo, "diff", "--name-only") == ""


def test_an_operator_edited_wp_prompt_is_not_staged_and_a_warning_names_it(repo: Path) -> None:
    """(c) A claimed WP prompt that was dirty before the claim keeps its bytes plus the stamp, outside the claim, and the claim warns.

    ``commit_planning_artifacts`` (out of scope, C-003) commits or refuses an ordinary operator edit before
    the claim, so the only edit that reaches the claim dirty is one the planning guard tolerates: a legacy
    runtime frontmatter key (``shell_pid``). ``--no-auto-commit`` keeps the planning step from sweeping it.
    """
    from tests.specify_cli.cli.commands._implement_fixtures import SLUG, flat, implement_cli

    mission = _lanes_mission(repo)
    prompt = mission.feature_dir / "tasks" / "WP01-test.md"
    text0 = prompt.read_text(encoding="utf-8")
    assert text0.startswith("---\n")
    prompt.write_text(text0.replace("---\n", "---\nshell_pid: '4242'\n", 1), encoding="utf-8")

    done = implement_cli("WP01", "--mission", SLUG, "--actor", "tester", "--no-auto-commit")

    assert done.exit_code == 0, done.output
    rel = f"kitty-specs/{SLUG}/tasks/WP01-test.md"
    text = prompt.read_text(encoding="utf-8")
    assert "shell_pid: '4242'" in text and "created_at:" in text
    assert rel not in set(git_out(repo, "diff", "--cached", "--name-only").splitlines())
    assert rel in git_out(repo, "diff", "--name-only")
    assert "WP01-test.md had uncommitted changes before the claim" in flat(done.output)


def test_coord_claim_exits_zero(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """(d) A coord-topology claim through ``agent action implement`` succeeds: no stamped prompt is left for the #3784 guard to refuse."""
    from typer.testing import CliRunner

    from specify_cli import app as root_app
    from tests.characterization.test_trio_json_envelope import _build_mission_repo

    repo_root, mission_dirname = _build_mission_repo(tmp_path, monkeypatch, coord=True, mission_slug="claim-scope-coord", wp_lane="planned", materialize_coord=True)
    result = CliRunner().invoke(root_app, ["agent", "action", "implement", "WP01", "--mission", mission_dirname, "--agent", "claude"])
    assert result.exit_code == 0, result.output
