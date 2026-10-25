"""``FABRICATED_IDENTITY_SUSPECTED``: a baseline-fabricated committed identity is a WARNING (#6668)."""

from __future__ import annotations

import contextlib
import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from specify_cli.audit import AuditOptions, run_audit
from specify_cli.audit.classifiers.fabricated_identity import fabricated_identity_signals
from specify_cli.audit.models import TEAMSPACE_BLOCKER_CODES
from specify_cli.cli.commands import doctor
from specify_cli.context.mission_resolver import tracked_mission_paths
from specify_cli.mission_metadata import baseline_slug_fields
from specify_cli.status import materialize_snapshot, materialize_to_json

pytestmark = [pytest.mark.git_repo]

CODE = "FABRICATED_IDENTITY_SUSPECTED"
SLUG = "my-mission-01M5JYRC"
OTHER_ID = "01M5JZWSABCDEFGHJKMNPQRSTV"


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


def _init(repo: Path) -> None:
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "T")


def _meta(slug: str = SLUG, **overrides: Any) -> dict[str, Any]:
    meta: dict[str, Any] = {**baseline_slug_fields(slug), "mission_id": OTHER_ID, "mission_type": "software-dev"}
    meta.update(overrides)
    return meta


def _write(repo: Path, slug: str = SLUG, *, meta: dict[str, Any] | None = None, extra: tuple[str, ...] = ()) -> Path:
    folder = repo / "kitty-specs" / slug
    (folder / "decisions").mkdir(parents=True)
    (folder / "meta.json").write_text(json.dumps(meta if meta is not None else _meta(slug)), encoding="utf-8")
    (folder / "status.events.jsonl").write_text("", encoding="utf-8")
    snapshot = materialize_snapshot(folder)  # the snapshot the reducer derives, so no SNAPSHOT_DRIFT
    (folder / "status.json").write_text(materialize_to_json(snapshot), encoding="utf-8")
    (folder / "decisions" / "index.json").write_text("{}\n", encoding="utf-8")
    for name in extra:
        (folder / name).write_text("x\n", encoding="utf-8")
    return folder


def _audit(repo: Path, *fail_on: str) -> tuple[int, list[dict[str, Any]]]:
    argv = ["mission-state", "--audit", "--json", *fail_on]
    with contextlib.chdir(repo):
        result = CliRunner().invoke(doctor.app, argv)
    report = json.loads(result.stdout)
    return result.exit_code, [f for m in report["missions"] for f in m["findings"] if f["code"] == CODE]


def _committed_repo(tmp_path: Path, **kwargs: Any) -> Path:
    _init(tmp_path)
    _write(tmp_path, **kwargs)
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "init")
    return tmp_path


def test_positive_reports_exactly_one_warning(tmp_path: Path) -> None:
    repo = _committed_repo(tmp_path)

    _, findings = _audit(repo)

    (finding,) = findings
    assert finding["severity"] == "warning"
    assert finding["artifact_path"] == "meta.json"
    assert "remove this folder's meta.json and status.json in a commit" in finding["detail"]
    assert CODE not in TEAMSPACE_BLOCKER_CODES


def test_detail_is_deterministic(tmp_path_factory: pytest.TempPathFactory) -> None:
    details = {_audit(_committed_repo(tmp_path_factory.mktemp("r")))[1][0]["detail"] for _ in range(2)}
    assert len(details) == 1


@pytest.mark.parametrize(
    ("name", "kwargs"),
    [
        ("extra_file", {"extra": ("research.md",)}),
        ("non_baseline_friendly_name", {"meta": _meta(friendly_name="Hand written")}),
        ("matching_mid8", {"meta": _meta(mission_id="01M5JYRCABCDEFGHJKMNPQRSTV")}),
        ("no_mid8_in_slug", {"slug": "plain-name", "meta": _meta("plain-name")}),
        ("non_baseline_number", {"slug": "042-thing-01M5JYRC", "meta": _meta("042-thing-01M5JYRC", mission_number=43)}),
    ],
)
def test_each_missing_signal_is_a_negative(tmp_path: Path, name: str, kwargs: dict[str, Any]) -> None:
    repo = _committed_repo(tmp_path, **kwargs)

    assert _audit(repo)[1] == [], name


@pytest.mark.parametrize("number", ["042", 42])
def test_numeric_prefix_matches_as_text_or_int(tmp_path: Path, number: object) -> None:
    slug = "042-thing-01M5JYRC"
    repo = _committed_repo(tmp_path, slug=slug, meta=_meta(slug, mission_number=number))

    assert len(_audit(repo)[1]) == 1


@pytest.mark.parametrize("blank", ["", None])
def test_blank_number_matches_a_slug_without_prefix(tmp_path: Path, blank: object) -> None:
    repo = _committed_repo(tmp_path, meta=_meta(mission_number=blank))

    assert len(_audit(repo)[1]) == 1


def test_absent_number_matches(tmp_path: Path) -> None:
    meta = _meta()
    del meta["mission_number"]
    repo = _committed_repo(tmp_path, meta=meta)

    assert len(_audit(repo)[1]) == 1


def test_untracked_meta_json_is_a_negative(tmp_path: Path) -> None:
    _init(tmp_path)
    folder = _write(tmp_path)
    (folder / "spec.md").write_text("# s\n", encoding="utf-8")
    _git(tmp_path, "add", "kitty-specs/*/spec.md")
    _git(tmp_path, "commit", "-q", "-m", "spec only")

    assert _audit(tmp_path)[1] == []


def test_project_outside_git_is_a_negative(tmp_path: Path) -> None:
    _write(tmp_path)

    report = run_audit(AuditOptions(repo_root=tmp_path))

    assert [f for m in report.missions for f in m.findings if f.code == CODE] == []


def test_thresholds(tmp_path: Path) -> None:
    repo = _committed_repo(tmp_path)

    assert _audit(repo, "--fail-on", "teamspace-blocker")[0] == 0
    assert _audit(repo, "--fail-on", "error")[0] == 0
    assert _audit(repo, "--fail-on", "warning")[0] != 0


def test_nothing_is_written(tmp_path: Path) -> None:
    repo = _committed_repo(tmp_path)

    _audit(repo)

    assert subprocess.run(["git", "status", "--porcelain"], cwd=repo, capture_output=True, text=True, check=True).stdout == ""


@pytest.mark.slow
def test_this_repository_corpus_has_no_matches() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    tracked = tracked_mission_paths(repo_root)
    if tracked is None:
        pytest.skip("not a git checkout")
    specs = repo_root / "kitty-specs"
    hits = []
    for folder in sorted(p for p in specs.iterdir() if p.is_dir()):
        try:
            meta = json.loads((folder / "meta.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if fabricated_identity_signals(folder, repo_root=repo_root, tracked=tracked, meta=meta):
            hits.append(folder.name)
    assert hits == []
