"""Tests for the post-merge docs regeneration bot (``scripts/ci/regen_docs_index.py``)
and its workflow (``.github/workflows/docs-index-regen.yml``).

The bot regenerates the docs retrieval index, the page inventory and the ADR era table
rows on ``main`` and proposes them on the fixed branch ``ci/regen-docs-index``, so pull
requests stop editing (and conflicting on) them. The pure decisions are tested directly;
the generators run over a staged docs tree; the publish phase runs against a real
throwaway git repository with ``git push`` and ``gh`` replaced by recorders.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from textwrap import dedent
from typing import Any

import pytest
import yaml

from scripts.ci import regen_docs_index as regen
from scripts.docs import inventory_lockfile
from scripts.docs.docs_index import generate_index
from specify_cli.docs.index_model import DEFAULT_INDEX_PATH, render_index

pytestmark = pytest.mark.fast

FAKE_TOKEN = "fake-regen-token-not-a-real-secret"  # noqa: S105 (obviously-fake test value)
WORKFLOW_PATH = regen.REPO_ROOT / ".github" / "workflows" / "docs-index-regen.yml"
RECAPTURE_WORKFLOW_PATH = regen.REPO_ROOT / ".github" / "workflows" / "ci-shard-recapture.yml"
_REAL_RUN = subprocess.run


# --------------------------------------------------------------------------- #
# Pure decisions                                                              #
# --------------------------------------------------------------------------- #


def test_generated_paths_match_the_generators_own_constants() -> None:
    assert regen.DOCS_INDEX_PATH == DEFAULT_INDEX_PATH
    assert regen.PAGE_INVENTORY_PATH == inventory_lockfile.DEFAULT_INVENTORY_PATH


def test_secret_is_the_shared_recapture_pat_never_github_token() -> None:
    assert regen.SECRET_NAME == "CHARTER_SHARD_RECAPTURE_TOKEN"
    assert regen.REGEN_BRANCH == "ci/regen-docs-index"


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("docs/development/docs-retrieval-index.yaml", True),
        ("docs/development/page-inventory.yaml", True),
        ("docs/adr/4.x/index.md", True),
        ("docs/adr/1.x/README.md", True),
        ("docs/adr/4.x/2026-11-01-1-some-adr.md", False),
        ("docs/adr/index.md", False),
        ("docs/development/index.md", False),
        ("scripts/docs/docs_index.py", False),
    ],
)
def test_is_generated_surface(path: str, expected: bool) -> None:
    assert regen.is_generated_surface(path) is expected


def test_classify_changes_splits_sorts_and_dedupes() -> None:
    changes = regen.classify_changes(["docs/adr/4.x/index.md", "README.md", DEFAULT_INDEX_PATH, "docs/adr/4.x/index.md"])
    assert changes.generated == ("docs/adr/4.x/index.md", DEFAULT_INDEX_PATH)
    assert changes.unexpected == ("README.md",)


def test_parse_porcelain_reads_nul_records_and_skips_rename_sources() -> None:
    output = " M docs/a.md\0?? docs/new.md\0R  docs/to.md\0docs/from.md\0"
    assert regen.parse_porcelain(output) == ["docs/a.md", "docs/new.md", "docs/to.md"]
    assert regen.parse_porcelain("") == []


def test_pr_body_lists_paths_and_run() -> None:
    body = regen.pr_body(["docs/a.yaml"], "https://run")
    assert "- `docs/a.yaml`" in body
    assert "`https://run`" in body


# --------------------------------------------------------------------------- #
# Regeneration over a staged docs tree                                        #
# --------------------------------------------------------------------------- #

_ERA_INDEX = dedent(
    """\
    ---
    title: 4.x ADRs
    description: ADRs of the 4.x era.
    ---

    # 4.x ADRs

    ## Index

    | Date | Title |
    |---|---|
    | 2026-10-01 | [First](2026-10-01-1-first.md) |
    """
)


def _adr(title: str, date: str) -> str:
    return f"---\ntitle: {title}\ndate: '{date}'\n---\n\n## Context\n\nBody.\n"


def _stage_repo(root: Path) -> Path:
    era = root / "docs" / "adr" / "4.x"
    era.mkdir(parents=True)
    (era / "index.md").write_text(_ERA_INDEX, encoding="utf-8")
    (era / "2026-10-01-1-first.md").write_text(_adr("First", "2026-10-01"), encoding="utf-8")
    (root / "docs" / "guide.md").write_text("---\ntitle: Guide\ntype: how-to\n---\n\n## Intro\n\nText.\n", encoding="utf-8")
    (root / "docs" / "development").mkdir()
    (root / regen.DOCS_INDEX_PATH).write_text("[]\n", encoding="utf-8")
    (root / regen.PAGE_INVENTORY_PATH).write_text("[]\n", encoding="utf-8")
    return root


def test_regenerate_reconciles_all_three_surfaces_idempotently(tmp_path: Path) -> None:
    root = _stage_repo(tmp_path)
    (root / "docs" / "adr" / "4.x" / "2026-10-20-1-second.md").write_text(_adr("Second", "2026-10-20"), encoding="utf-8")

    regen.regenerate(root)

    era_index = (root / "docs" / "adr" / "4.x" / "index.md").read_text(encoding="utf-8")
    assert "| 2026-10-20 | [Second](2026-10-20-1-second.md) |" in era_index
    docs_root = root / "docs"
    assert (root / regen.DOCS_INDEX_PATH).read_text(encoding="utf-8") == render_index(generate_index(docs_root, repo_root=root))
    assert (root / regen.PAGE_INVENTORY_PATH).read_text(encoding="utf-8") == inventory_lockfile.render_lockfile(
        inventory_lockfile.generate_inventory(docs_root, repo_root=root)
    )

    snapshot = {p: p.read_bytes() for p in docs_root.rglob("*") if p.is_file()}
    regen.regenerate(root)
    assert {p: p.read_bytes() for p in docs_root.rglob("*") if p.is_file()} == snapshot


def test_regenerate_phase_refuses_when_the_pat_is_present(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(regen.SECRET_NAME, FAKE_TOKEN)
    called: list[Path] = []
    monkeypatch.setattr(regen, "regenerate", called.append)
    assert regen.main([regen.PHASE_REGENERATE]) == 1
    assert called == []


# --------------------------------------------------------------------------- #
# Phases against a real throwaway git repository                              #
# --------------------------------------------------------------------------- #


def _git(root: Path, *args: str) -> str:
    return _REAL_RUN(["git", *args], cwd=root, capture_output=True, text=True, check=True).stdout


@pytest.fixture()
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = _stage_repo(tmp_path / "repo")
    _git(root, "init", "-q", "-b", "main")
    _git(root, "add", "-A")
    _git(root, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "seed")
    monkeypatch.setattr(regen, "REPO_ROOT", root)
    for name in ("GITHUB_OUTPUT", "GITHUB_STEP_SUMMARY", "GH_TOKEN", "GITHUB_TOKEN"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("GITHUB_REPOSITORY", "spec-kitty/spec-kitty")
    return root


class _Recorder:
    """Replaces ``subprocess.run``: real for local git, recorded for push and gh."""

    def __init__(self, open_prs: str = "[]") -> None:
        self.calls: list[tuple[list[str], dict[str, str] | None]] = []
        self.open_prs = open_prs

    def __call__(self, cmd: list[str], **kwargs: Any) -> Any:
        if cmd[:2] == ["git", "push"] or cmd[0] == "gh":
            self.calls.append((cmd, kwargs.get("env")))
            stdout = self.open_prs if cmd[:3] == ["gh", "pr", "list"] else ""
            return subprocess.CompletedProcess(cmd, 0, stdout=stdout, stderr="")
        return _REAL_RUN(cmd, **kwargs)

    def commands(self) -> list[list[str]]:
        return [cmd for cmd, _env in self.calls]


def test_regenerate_phase_reports_changed_for_a_stale_tree(repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.delenv(regen.SECRET_NAME, raising=False)
    assert regen.main([regen.PHASE_REGENERATE]) == 0
    assert "changed=true" in capsys.readouterr().out


def test_regenerate_phase_reports_unchanged_when_fresh(repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.delenv(regen.SECRET_NAME, raising=False)
    regen.regenerate(repo)
    _git(repo, "add", "-A")
    _git(repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "fresh")
    assert regen.main([regen.PHASE_REGENERATE]) == 0
    assert "changed=false" in capsys.readouterr().out


def test_regenerate_phase_fails_on_a_path_it_does_not_own(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(regen.SECRET_NAME, raising=False)
    (repo / "stray.txt").write_text("x", encoding="utf-8")
    assert regen.main([regen.PHASE_REGENERATE]) == 1


def test_publish_commits_force_pushes_and_opens_a_pr(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    regen.regenerate(repo)
    recorder = _Recorder()
    monkeypatch.setattr(subprocess, "run", recorder)
    monkeypatch.setenv(regen.SECRET_NAME, FAKE_TOKEN)

    assert regen.main([regen.PHASE_PUBLISH]) == 0

    assert _git(repo, "log", "-1", "--format=%an|%s").strip() == f"spec-kitty-ci-bot|{regen.COMMIT_MESSAGE}"
    assert _git(repo, "status", "--porcelain") == ""
    commands = recorder.commands()
    assert commands[0] == ["git", "push", "--force", "origin", f"HEAD:refs/heads/{regen.REGEN_BRANCH}"]
    assert commands[1][:3] == ["gh", "pr", "list"]
    create = commands[2]
    assert create[:3] == ["gh", "pr", "create"]
    assert create[create.index("--head") + 1] == regen.REGEN_BRANCH
    assert create[create.index("--base") + 1] == "main"
    assert all(FAKE_TOKEN not in " ".join(cmd) for cmd in commands)
    push_env = recorder.calls[0][1]
    assert push_env is not None
    assert regen.SECRET_NAME not in push_env
    last = int(push_env["GIT_CONFIG_COUNT"]) - 1
    assert push_env[f"GIT_CONFIG_KEY_{last}"].endswith(".extraheader")


def test_publish_refreshes_an_open_pr_without_creating_another(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    regen.regenerate(repo)
    recorder = _Recorder(open_prs=f'[{{"headRefName": "{regen.REGEN_BRANCH}", "number": 42}}]')
    monkeypatch.setattr(subprocess, "run", recorder)
    monkeypatch.setenv(regen.SECRET_NAME, FAKE_TOKEN)

    assert regen.main([regen.PHASE_PUBLISH]) == 0

    assert [cmd[:3] for cmd in recorder.commands()] == [["git", "push", "--force"], ["gh", "pr", "list"]]


def test_publish_is_a_no_op_when_nothing_changed(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    recorder = _Recorder()
    monkeypatch.setattr(subprocess, "run", recorder)
    monkeypatch.setenv(regen.SECRET_NAME, FAKE_TOKEN)
    head = _git(repo, "rev-parse", "HEAD")

    assert regen.main([regen.PHASE_PUBLISH]) == 0

    assert recorder.commands() == []
    assert _git(repo, "rev-parse", "HEAD") == head


def test_publish_refuses_a_path_outside_the_generated_surfaces(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    regen.regenerate(repo)
    (repo / "docs" / "guide.md").write_text("tampered\n", encoding="utf-8")
    recorder = _Recorder()
    monkeypatch.setattr(subprocess, "run", recorder)
    monkeypatch.setenv(regen.SECRET_NAME, FAKE_TOKEN)

    assert regen.main([regen.PHASE_PUBLISH]) == 1
    assert recorder.commands() == []


def test_publish_requires_the_pat(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(regen.SECRET_NAME, raising=False)
    with pytest.raises(SystemExit):
        regen.main([regen.PHASE_PUBLISH])


def test_failed_push_names_the_secret_and_redacts_the_token(repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    regen.regenerate(repo)

    def _fake(cmd: list[str], **kwargs: Any) -> Any:
        if cmd[:2] == ["git", "push"]:
            raise subprocess.CalledProcessError(128, cmd, stderr=f"remote: Permission denied for {FAKE_TOKEN} (403)")
        return _REAL_RUN(cmd, **kwargs)

    monkeypatch.setattr(subprocess, "run", _fake)
    monkeypatch.setenv(regen.SECRET_NAME, FAKE_TOKEN)

    with pytest.raises(SystemExit):
        regen.main([regen.PHASE_PUBLISH])
    err = capsys.readouterr().err
    assert regen.SECRET_NAME in err
    assert FAKE_TOKEN not in err


# --------------------------------------------------------------------------- #
# Workflow shape                                                              #
# --------------------------------------------------------------------------- #


@pytest.fixture(scope="module")
def workflow() -> dict[Any, Any]:
    loaded: dict[Any, Any] = yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))
    return loaded


def _job(workflow: dict[Any, Any]) -> dict[str, Any]:
    jobs: dict[str, Any] = workflow["jobs"]
    assert list(jobs) == ["regenerate-docs-index"]
    job: dict[str, Any] = jobs["regenerate-docs-index"]
    return job


def test_workflow_triggers_on_docs_pushes_to_main_schedule_and_dispatch(workflow: dict[Any, Any]) -> None:
    on = workflow.get("on", workflow.get(True))
    assert set(on) == {"push", "schedule", "workflow_dispatch"}
    assert on["push"] == {"branches": ["main"], "paths": ["docs/**"]}
    assert len(on["schedule"]) == 1


def test_workflow_concurrency_is_static_and_permissions_minimal(workflow: dict[Any, Any]) -> None:
    assert workflow["concurrency"] == {"group": "docs-index-regen", "cancel-in-progress": False}
    assert workflow["permissions"] == {"contents": "read"}
    assert "permissions" not in _job(workflow)


def test_workflow_job_is_main_only(workflow: dict[Any, Any]) -> None:
    assert "github.ref == 'refs/heads/main'" in _job(workflow)["if"]


def test_workflow_hands_the_pat_to_the_publish_step_only(workflow: dict[Any, Any]) -> None:
    steps = _job(workflow)["steps"]
    secret_steps = [step for step in steps if "secrets." in str(step)]
    assert len(secret_steps) == 1
    publish = secret_steps[0]
    assert publish["env"] == {regen.SECRET_NAME: "${{ secrets.CHARTER_SHARD_RECAPTURE_TOKEN }}"}
    assert "regen_docs_index publish" in publish["run"]
    assert publish["if"] == "${{ steps.regen.outputs.changed == 'true' }}"
    regenerate = next(step for step in steps if step.get("id") == "regen")
    assert "regen_docs_index regenerate" in regenerate["run"]
    assert "env" not in regenerate
    assert "GITHUB_TOKEN" not in WORKFLOW_PATH.read_text(encoding="utf-8").split("jobs:", 1)[1]


def test_workflow_checkout_persists_no_credential_and_pins_the_recapture_actions(workflow: dict[Any, Any]) -> None:
    steps = _job(workflow)["steps"]
    checkout = next(step for step in steps if str(step.get("uses", "")).startswith("actions/checkout@"))
    assert checkout["with"] == {"persist-credentials": False}
    recapture_text = RECAPTURE_WORKFLOW_PATH.read_text(encoding="utf-8")
    for step in steps:
        if "uses" in step:
            assert f"uses: {step['uses']}" in recapture_text, f"{step['uses']} is not the SHA ci-shard-recapture.yml pins"


def test_workflow_header_marks_the_shared_token_as_interim() -> None:
    header = WORKFLOW_PATH.read_text(encoding="utf-8").split("name:", 1)[0]
    assert "CHARTER_SHARD_RECAPTURE_TOKEN" in header
    assert "spec-kitty/spec-kitty#6986" in header
    assert "INTERIM" in header
