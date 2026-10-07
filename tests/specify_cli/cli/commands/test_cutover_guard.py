"""Red-first tests for the diff-scoped fail-closed cut-over guard (WP03).

Proves contracts/pre-merge-guard.md (IC-03 / IC-04; FR-002, FR-003, FR-009,
NFR-002, NFR-003) for mission runtime-state-birth-cutover-all-paths:

* (a) R2 vacuity trap — a natively-born mission with genuine event-log
  runtime evidence (a real claim) but an un-flipped ``status_phase`` is
  FLAGGED un-cut-over, even though ``verify_backfill`` is vacuously ``ok``
  (``wp_count=0``, no frontmatter at all). Keying on bare
  ``verify_backfill.ok`` would wrongly pass this mission.
* (b) an all-cut-over diff passes cleanly.
* (c) a mission with no ``mission_id`` at all fails closed, independent of
  everything else about it.

Fixtures below deliberately mirror the shape built by
``tests/specify_cli/migration/test_dogfood_corpus_backfilled.py``'s
``test_reked_lock_reds_on_born_un_reconciled_mission`` (the R2 proof this
guard shares authority with via
:mod:`specify_cli.status.cutover_eligibility`), but are independently
constructed here — this file owns its own fixtures, not a re-import of test
helpers from another test module.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import typer
from click.testing import Result
from typer.testing import CliRunner

from specify_cli.cli.commands import cutover_guard as cutover_guard_mod
from specify_cli.cli.commands.cutover_guard import (
    CutoverGuardError,
    cutover_guard,
    evaluate_touched_missions,
    remedy_command,
    remedy_for,
    touched_mission_slugs,
)
from specify_cli.status.cutover_eligibility import PRE_ACCEPT_EXEMPT_NOTE
from specify_cli.status import (
    Lane,
    StatusEvent,
    build_claim_policy_metadata,
)
from specify_cli.status._unsafe import append_events_atomic_verified

pytestmark = [pytest.mark.fast]

#: ``cutover_guard`` is registered directly on the root app
#: (``app.command(name="cutover-guard")(...)``), not as a Typer sub-app —
#: wrap it the same way ``test_intake.py`` wraps other bare-function
#: commands so ``CliRunner`` has a real Typer instance to invoke.
_guard_app = typer.Typer()
_guard_app.command()(cutover_guard)


def _write_meta(mission_dir: Path, *, mission_id: str | None, status_phase: str | None) -> None:
    payload: dict[str, object] = {"mission_slug": mission_dir.name, "mission_type": "software-dev"}
    if mission_id is not None:
        payload["mission_id"] = mission_id
    if status_phase is not None:
        payload["status_phase"] = status_phase
    mission_dir.mkdir(parents=True, exist_ok=True)
    (mission_dir / "meta.json").write_text(json.dumps(payload), encoding="utf-8")


def _seed_live_claim(mission_dir: Path, mission_id: str, *, event_id: str) -> None:
    """Append a genuine LIVE claim (real ``policy_metadata``) for WP01.

    This is the exact wire shape a real born mission gets at the WP09
    birth-cutover seam — NOT a backfill seed. Its mere presence is the
    event-log runtime evidence the shared predicate keys on.
    """
    claim = StatusEvent(
        event_id=event_id,
        mission_slug=mission_dir.name,
        mission_id=mission_id,
        wp_id="WP01",
        from_lane=Lane.PLANNED,
        to_lane=Lane.CLAIMED,
        at="2026-07-25T09:00:00+00:00",
        actor="claude:sonnet:pedro",
        force=False,
        execution_mode="worktree",
        policy_metadata=build_claim_policy_metadata(
            shell_pid=55221,
            shell_pid_created_at="2026-07-25T08:59:00+00:00",
            agent="claude:sonnet:pedro",
        ),
    )
    append_events_atomic_verified(mission_dir, [claim])


def _build_native_un_cut_over_mission(corpus: Path, *, slug: str, mission_id: str) -> Path:
    """A natively-born mission, accepted but unstamped (terminal evidence): real event-log claim, NO ``status_phase`` key.

    No frontmatter runtime state anywhere on disk (the FR-008/WP05
    authoring-retired shape), so ``verify_backfill`` reads vacuously ``ok``
    with ``wp_count=0`` — the R2 vacuous-green trap this guard must not fall
    into.
    """
    mission_dir = corpus / slug
    _write_meta(mission_dir, mission_id=mission_id, status_phase=None)
    # Accepted but never stamped: a still-pre-accept Mission is exempt (#5835), so
    # terminal evidence is what keeps this fixture un-cut-over.
    meta_path = mission_dir / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["accepted_at"] = "2026-07-25T10:00:00+00:00"
    meta_path.write_text(json.dumps(meta), encoding="utf-8")
    tasks = mission_dir / "tasks"
    tasks.mkdir()
    (tasks / "WP01-demo.md").write_text(
        "---\nwork_package_id: WP01\ntitle: Demo\nexecution_mode: code_change\n---\n\n# WP01\n",
        encoding="utf-8",
    )
    (mission_dir / "tasks.md").write_text("# Tasks\n\n## WP01 Demo\n\n", encoding="utf-8")
    _seed_live_claim(mission_dir, mission_id, event_id="01NATIVEUNCUTOVERAAAAAAAAA")
    return mission_dir


def _build_cut_over_mission(corpus: Path, *, slug: str, mission_id: str) -> Path:
    """Same shape as :func:`_build_native_un_cut_over_mission`, but flipped.

    ``status_phase`` is stamped ``"1"`` — the exact delta that must move a
    mission from un-cut-over to cut-over under the shared predicate.
    """
    mission_dir = corpus / slug
    _write_meta(mission_dir, mission_id=mission_id, status_phase="1")
    tasks = mission_dir / "tasks"
    tasks.mkdir()
    (tasks / "WP01-demo.md").write_text(
        "---\nwork_package_id: WP01\ntitle: Demo\nexecution_mode: code_change\n---\n\n# WP01\n",
        encoding="utf-8",
    )
    (mission_dir / "tasks.md").write_text("# Tasks\n\n## WP01 Demo\n\n", encoding="utf-8")
    _seed_live_claim(mission_dir, mission_id, event_id="01CUTOVERCUTOVERAAAAAAAAAA")
    return mission_dir


def _build_missing_mission_id_mission(corpus: Path, *, slug: str) -> Path:
    """A mission whose ``meta.json`` carries no ``mission_id`` key at all."""
    mission_dir = corpus / slug
    _write_meta(mission_dir, mission_id=None, status_phase="1")
    return mission_dir


# --- (a) R2 vacuity trap: native un-cut-over mission is FLAGGED ------------


def test_native_un_cut_over_mission_is_flagged(tmp_path: Path) -> None:
    corpus = tmp_path / "kitty-specs"
    corpus.mkdir()
    slug = "native-un-cut-over-01KZQXTR"
    _build_native_un_cut_over_mission(corpus, slug=slug, mission_id="01KZQXTRH8T2X6R4N9YV3D5C7B")

    changed_paths = [f"kitty-specs/{slug}/status.events.jsonl"]
    verdict = evaluate_touched_missions(tmp_path, changed_paths)

    assert verdict.passed is False
    assert verdict.touched_slugs == (slug,)
    assert len(verdict.failures) == 1
    failure = verdict.failures[0]
    assert failure.mission_slug == slug
    assert failure.cut_over is False
    # Non-vacuity: the failure reason must name the real cause (unflipped
    # status_phase), never a silent pass keyed on vacuous verify_backfill.
    assert any("status_phase" in reason for reason in failure.reasons)


def test_native_un_cut_over_mission_reds_the_cli(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Same fixture, driven through the actual Typer command (integration seam).

    ``SPECIFY_REPO_ROOT`` is the documented deterministic override for
    ``locate_project_root`` (authoritative regardless of cwd) — used here
    instead of ``os.chdir``, which would mutate global process state under a
    parallel test run.
    """
    corpus = tmp_path / "kitty-specs"
    corpus.mkdir()
    slug = "native-un-cut-over-cli-01KZQXTS"
    _build_native_un_cut_over_mission(corpus, slug=slug, mission_id="01KZQXTSH8T2X6R4N9YV3D5C7C")
    (tmp_path / ".kittify").mkdir()
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(tmp_path))

    paths_file = tmp_path / "changed-paths.txt"
    paths_file.write_text(f"kitty-specs/{slug}/meta.json\n", encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(_guard_app, ["--paths-from", str(paths_file)])

    assert result.exit_code == 1
    # Normalize away Rich's ambient-width line wrapping (the console isn't
    # pinned wide here) rather than asserting on a fragile literal substring.
    normalized_output = " ".join(result.output.split())
    assert slug in normalized_output
    assert remedy_command(slug) in normalized_output


def test_all_cut_over_diff_passes_through_the_cli(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    corpus = tmp_path / "kitty-specs"
    corpus.mkdir()
    slug = "cut-over-clean-cli-01KZQXTZ"
    _build_cut_over_mission(corpus, slug=slug, mission_id="01KZQXTZH8T2X6R4N9YV3D5C7G")
    (tmp_path / ".kittify").mkdir()
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(tmp_path))

    paths_file = tmp_path / "changed-paths.txt"
    paths_file.write_text(f"kitty-specs/{slug}/meta.json\n", encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(_guard_app, ["--paths-from", str(paths_file)])

    assert result.exit_code == 0


def test_neither_base_ref_nor_paths_from_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / ".kittify").mkdir()
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(tmp_path))
    runner = CliRunner()
    result = runner.invoke(_guard_app, [])
    assert result.exit_code == 1


def test_both_base_ref_and_paths_from_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / ".kittify").mkdir()
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(tmp_path))
    paths_file = tmp_path / "changed-paths.txt"
    paths_file.write_text("kitty-specs/whatever/meta.json\n", encoding="utf-8")
    runner = CliRunner()
    result = runner.invoke(_guard_app, ["--base-ref", "origin/main", "--paths-from", str(paths_file)])
    assert result.exit_code == 1


# --- (b) all-cut-over diff passes ------------------------------------------


def test_all_cut_over_diff_passes(tmp_path: Path) -> None:
    corpus = tmp_path / "kitty-specs"
    corpus.mkdir()
    slug = "cut-over-clean-01KZQXTU"
    _build_cut_over_mission(corpus, slug=slug, mission_id="01KZQXTUH8T2X6R4N9YV3D5C7D")

    changed_paths = [f"kitty-specs/{slug}/status.events.jsonl", f"kitty-specs/{slug}/meta.json"]
    verdict = evaluate_touched_missions(tmp_path, changed_paths)

    assert verdict.passed is True
    assert verdict.touched_slugs == (slug,)
    assert verdict.failures == ()


def test_mixed_diff_one_cut_over_one_not_fails_and_names_only_the_bad_one(
    tmp_path: Path,
) -> None:
    corpus = tmp_path / "kitty-specs"
    corpus.mkdir()
    good_slug = "cut-over-good-01KZQXTV"
    bad_slug = "native-un-cut-over-bad-01KZQXTW"
    _build_cut_over_mission(corpus, slug=good_slug, mission_id="01KZQXTVH8T2X6R4N9YV3D5C7E")
    _build_native_un_cut_over_mission(corpus, slug=bad_slug, mission_id="01KZQXTWH8T2X6R4N9YV3D5C7F")

    changed_paths = [
        f"kitty-specs/{good_slug}/meta.json",
        f"kitty-specs/{bad_slug}/meta.json",
    ]
    verdict = evaluate_touched_missions(tmp_path, changed_paths)

    assert verdict.passed is False
    assert {f.mission_slug for f in verdict.failures} == {bad_slug}


def test_no_kitty_specs_paths_touched_passes_vacuously(tmp_path: Path) -> None:
    changed_paths = ["src/specify_cli/core/paths.py", "docs/README.md"]
    verdict = evaluate_touched_missions(tmp_path, changed_paths)

    assert verdict.passed is True
    assert verdict.touched_slugs == ()
    assert verdict.failures == ()


# --- (c) absent mission_id fails closed ------------------------------------


def test_absent_mission_id_fails_closed(tmp_path: Path) -> None:
    corpus = tmp_path / "kitty-specs"
    corpus.mkdir()
    slug = "no-mission-id-01KZQXTX"
    _build_missing_mission_id_mission(corpus, slug=slug)

    changed_paths = [f"kitty-specs/{slug}/meta.json"]
    verdict = evaluate_touched_missions(tmp_path, changed_paths)

    assert verdict.passed is False
    assert len(verdict.failures) == 1
    failure = verdict.failures[0]
    assert failure.mission_slug == slug
    assert any("mission_id" in reason for reason in failure.reasons)


def test_missing_mission_directory_fails_closed(tmp_path: Path) -> None:
    """A diff naming a mission whose directory doesn't exist (ambiguous / removed)."""
    changed_paths = ["kitty-specs/never-existed-01KZQXTY/meta.json"]
    verdict = evaluate_touched_missions(tmp_path, changed_paths)

    assert verdict.passed is False
    assert len(verdict.failures) == 1
    assert verdict.failures[0].mission_slug == "never-existed-01KZQXTY"


# --- Helper unit coverage ----------------------------------------------------


def test_touched_mission_slugs_dedupes_and_ignores_non_kitty_specs_paths() -> None:
    paths = [
        "kitty-specs/alpha-01/meta.json",
        "kitty-specs/alpha-01/status.events.jsonl",
        "kitty-specs/beta-02/tasks/WP01.md",
        "src/specify_cli/foo.py",
        "kitty-specs",  # too short to name a mission
    ]
    assert touched_mission_slugs(paths) == ("alpha-01", "beta-02")


def test_remedy_command_is_exact() -> None:
    assert remedy_command("my-mission-01ABCD") == ("spec-kitty migrate backfill-runtime-state --mission my-mission-01ABCD")


# ---------------------------------------------------------------------------
# NFR-003 fail-closed paths.
#
# Every branch below is an *uncertainty* path: the guard cannot determine what
# the diff touched, or cannot decide a mission. The contract is that each one
# is a FAILURE, never a silent pass. These were the guard's whole reason for
# existing and were previously untested (the module sat at 73% with exactly
# these regions uncovered).
# ---------------------------------------------------------------------------


def test_unresolvable_merge_base_raises_rather_than_reporting_no_changes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """An unknown --base-ref must raise, not degrade to an empty diff."""
    monkeypatch.setattr(cutover_guard_mod, "git_merge_base", lambda *a, **k: None)

    with pytest.raises(CutoverGuardError) as excinfo:
        cutover_guard_mod.changed_paths_from_git(tmp_path, "no/such/ref")

    assert "merge-base" in str(excinfo.value)


def test_failed_diff_raises_rather_than_reporting_no_changes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A failed git diff must raise: an empty tuple would read as 'nothing touched, pass'."""
    monkeypatch.setattr(cutover_guard_mod, "git_merge_base", lambda *a, **k: "abc123")
    monkeypatch.setattr(cutover_guard_mod, "git_diff_names_checked", lambda *a, **k: None)

    with pytest.raises(CutoverGuardError) as excinfo:
        cutover_guard_mod.changed_paths_from_git(tmp_path, "origin/main")

    assert "git diff failed" in str(excinfo.value)


def test_unsafe_slug_in_diff_fails_closed(tmp_path: Path) -> None:
    """A traversal-shaped slug lifted from a diff path is rejected, not joined."""
    (tmp_path / "kitty-specs").mkdir()

    verdict = evaluate_touched_missions(tmp_path, ["kitty-specs/../../etc/passwd"])

    assert verdict.passed is False
    assert len(verdict.failures) == 1
    assert any("unsafe mission slug" in reason for reason in verdict.failures[0].reasons)


def test_predicate_error_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Any exception from is_cut_over is recorded as a failure, never skipped."""
    corpus = tmp_path / "kitty-specs"
    corpus.mkdir()
    slug = "boom-01KZQXTX"
    (corpus / slug).mkdir()

    def _explode(_mission_dir: Path) -> None:
        raise RuntimeError("predicate exploded")

    monkeypatch.setattr(cutover_guard_mod, "is_cut_over", _explode)

    verdict = evaluate_touched_missions(tmp_path, [f"kitty-specs/{slug}/meta.json"])

    assert verdict.passed is False
    assert any("predicate exploded" in reason for reason in verdict.failures[0].reasons)


def test_unreadable_paths_from_file_exits_one(tmp_path: Path) -> None:
    """An unreadable --paths-from is a fail-closed exit(1), not an empty diff."""
    result = CliRunner().invoke(_guard_app, ["--paths-from", str(tmp_path / "does-not-exist.txt")])

    assert result.exit_code == 1


def test_cli_surfaces_guard_error_as_exit_one(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A CutoverGuardError from the diff resolution reaches the operator as exit 1."""
    monkeypatch.setattr(cutover_guard_mod, "locate_project_root", lambda *a, **k: tmp_path)

    def _raise(*_a: object, **_k: object) -> None:
        raise CutoverGuardError("merge-base unresolvable")

    monkeypatch.setattr(cutover_guard_mod, "changed_paths_from_git", _raise)

    result = CliRunner().invoke(_guard_app, ["--base-ref", "origin/main"])

    assert result.exit_code == 1


# --- Non-mission relocation out of the corpus --------------------------------
#
# A diff that moves an identity-less, event-log-less directory OUT of
# ``kitty-specs/`` (FR-007 relocation of non-mission artifacts) names a slug
# whose directory no longer exists at HEAD. That slug was never inside the
# guard's domain — there is no mission identity and no runtime evidence at
# the merge-base for it to enforce — so it is reported as a relocation, not an
# un-cut-over mission. A directory that DID carry mission artifacts at the
# merge-base still fails closed when the diff removes it.


def _git(repo: Path, *args: str) -> str:
    import subprocess  # noqa: PLC0415 — test-local helper

    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result.stdout.strip()


def _init_relocation_repo(tmp_path: Path, *, base_files: dict[str, str]) -> tuple[Path, str]:
    """A real repo: ``main`` holds ``kitty-specs/legacy-notes/<base_files>``;
    ``topic`` relocates every one of them under ``docs/archive/`` (pure rename).

    Returns ``(repo, base_sha)`` with ``topic`` checked out.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "guard@example.com")
    _git(repo, "config", "user.name", "guard")
    (repo / ".kittify").mkdir()
    (repo / ".kittify" / "config.yaml").write_text("{}\n", encoding="utf-8")
    legacy = repo / "kitty-specs" / "legacy-notes"
    legacy.mkdir(parents=True)
    for name, body in base_files.items():
        (legacy / name).parent.mkdir(parents=True, exist_ok=True)
        (legacy / name).write_text(body, encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "base corpus")
    base_sha = _git(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", "-q", "-b", "topic")
    dest = repo / "docs" / "archive" / "legacy-notes"
    dest.mkdir(parents=True)
    for name in base_files:
        (dest / name).parent.mkdir(parents=True, exist_ok=True)
        _git(repo, "mv", f"kitty-specs/legacy-notes/{name}", f"docs/archive/legacy-notes/{name}")
    # ``git mv`` leaves the emptied source directory on disk; a real checkout
    # of the relocating commit has no such directory, so mirror that shape.
    if legacy.exists():
        for stale in sorted(legacy.rglob("*"), reverse=True):
            if stale.is_dir() and not any(stale.iterdir()):
                stale.rmdir()
        if not any(legacy.iterdir()):
            legacy.rmdir()
    _git(repo, "commit", "-q", "-m", "relocate non-mission evidence")
    return repo, base_sha


def test_changed_paths_from_git_reports_the_merge_base(tmp_path: Path) -> None:
    repo, base_sha = _init_relocation_repo(tmp_path, base_files={"notes.md": "historical\n"})

    scope = cutover_guard_mod.changed_paths_from_git(repo, "main")

    assert scope.merge_base == base_sha
    assert scope.paths == ("kitty-specs/legacy-notes/notes.md",)


def test_relocation_of_identityless_non_mission_directory_passes(tmp_path: Path) -> None:
    repo, base_sha = _init_relocation_repo(tmp_path, base_files={"notes.md": "historical\n", "manifest.md": "scope\n"})
    changed_paths = [
        "kitty-specs/legacy-notes/notes.md",
        "kitty-specs/legacy-notes/manifest.md",
    ]

    verdict = evaluate_touched_missions(repo, changed_paths, merge_base=base_sha)

    assert verdict.passed is True
    assert verdict.failures == ()
    assert verdict.touched_slugs == ("legacy-notes",)
    assert verdict.non_mission_slugs == ("legacy-notes",)


@pytest.mark.parametrize(
    "mission_artifact",
    ["meta.json", "status.events.jsonl"],
    ids=["identity-at-base", "event-log-at-base"],
)
def test_relocation_of_a_directory_carrying_mission_artifacts_fails_closed(tmp_path: Path, mission_artifact: str) -> None:
    """The negative control: a removed directory that WAS a mission at the base."""
    repo, base_sha = _init_relocation_repo(
        tmp_path,
        base_files={"notes.md": "historical\n", mission_artifact: "{}\n"},
    )
    changed_paths = [
        "kitty-specs/legacy-notes/notes.md",
        f"kitty-specs/legacy-notes/{mission_artifact}",
    ]

    verdict = evaluate_touched_missions(repo, changed_paths, merge_base=base_sha)

    assert verdict.passed is False
    assert verdict.non_mission_slugs == ()
    assert len(verdict.failures) == 1
    failure = verdict.failures[0]
    assert failure.mission_slug == "legacy-notes"
    assert any(base_sha[:12] in reason for reason in failure.reasons)
    assert any(mission_artifact in reason for reason in failure.reasons)


def test_removed_directory_with_a_nested_mission_artifact_fails_closed(tmp_path: Path) -> None:
    """The base listing is recursive: an artifact below the root keeps the dir in domain."""
    repo, base_sha = _init_relocation_repo(tmp_path, base_files={"notes.md": "historical\n", "sub/meta.json": "{}\n"})
    changed_paths = ["kitty-specs/legacy-notes/notes.md", "kitty-specs/legacy-notes/sub/meta.json"]

    verdict = evaluate_touched_missions(repo, changed_paths, merge_base=base_sha)

    assert verdict.passed is False
    assert verdict.non_mission_slugs == ()
    assert any("meta.json" in reason for reason in verdict.failures[0].reasons)


def test_missing_directory_without_a_merge_base_still_fails_closed(tmp_path: Path) -> None:
    """``--paths-from`` mode has no base tree to consult: uncertainty stays closed."""
    repo, _base_sha = _init_relocation_repo(tmp_path, base_files={"notes.md": "historical\n"})

    verdict = evaluate_touched_missions(repo, ["kitty-specs/legacy-notes/notes.md"])

    assert verdict.passed is False
    assert verdict.non_mission_slugs == ()
    assert verdict.failures[0].mission_slug == "legacy-notes"


def test_slug_absent_from_both_trees_fails_closed_even_with_a_merge_base(tmp_path: Path) -> None:
    repo, base_sha = _init_relocation_repo(tmp_path, base_files={"notes.md": "historical\n"})

    verdict = evaluate_touched_missions(repo, ["kitty-specs/never-existed-01KZQXTY/meta.json"], merge_base=base_sha)

    assert verdict.passed is False
    assert verdict.failures[0].mission_slug == "never-existed-01KZQXTY"


def test_unreadable_merge_base_tree_fails_closed(tmp_path: Path) -> None:
    repo, _base_sha = _init_relocation_repo(tmp_path, base_files={"notes.md": "historical\n"})

    verdict = evaluate_touched_missions(repo, ["kitty-specs/legacy-notes/notes.md"], merge_base="0" * 40)

    assert verdict.passed is False
    assert verdict.non_mission_slugs == ()
    assert any("merge-base" in reason for reason in verdict.failures[0].reasons)


def test_relocation_passes_through_the_cli_with_base_ref(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo, _base_sha = _init_relocation_repo(tmp_path, base_files={"notes.md": "historical\n"})
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(repo))
    monkeypatch.chdir(repo)

    runner = CliRunner()
    result = runner.invoke(_guard_app, ["--base-ref", "main", "--json"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["passed"] is True
    assert payload["non_mission_slugs"] == ["legacy-notes"]
    assert payload["failures"] == []


# --- #5835: pre-accept exemption surfaced, reason-specific remedies --------


def _invoke_guard(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, slug: str, *extra: str) -> Result:
    (tmp_path / ".kittify").mkdir(exist_ok=True)
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(tmp_path))
    paths_file = tmp_path / "changed-paths.txt"
    paths_file.write_text(f"kitty-specs/{slug}/meta.json\n", encoding="utf-8")
    return CliRunner().invoke(_guard_app, ["--paths-from", str(paths_file), *extra])


def _build_pre_accept_mission(corpus: Path, *, slug: str, mission_id: str) -> Path:
    """Claimed, never accepted, no stamp: the pre-accept shape."""
    mission_dir = _build_native_un_cut_over_mission(corpus, slug=slug, mission_id=mission_id)
    meta_path = mission_dir / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    del meta["accepted_at"]
    meta_path.write_text(json.dumps(meta), encoding="utf-8")
    return mission_dir


def test_exempt_mission_is_listed_and_exits_zero(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    corpus = tmp_path / "kitty-specs"
    corpus.mkdir()
    slug = "pre-accept-cli-01KZPRE1"
    _build_pre_accept_mission(corpus, slug=slug, mission_id="01KZPRE1H8T2X6R4N9YV3D5C7A")

    result = _invoke_guard(tmp_path, monkeypatch, slug)

    assert result.exit_code == 0
    out = " ".join(result.output.split())
    assert f"{slug}: {PRE_ACCEPT_EXEMPT_NOTE}" in out
    assert "Pre-accept (exempt) : 1" in out
    assert "All diff-touched Missions pass the cut-over check." in out
    assert "are cut over" not in out


def test_exempt_mission_json_is_additive(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    corpus = tmp_path / "kitty-specs"
    corpus.mkdir()
    slug = "pre-accept-json-01KZPRE2"
    _build_pre_accept_mission(corpus, slug=slug, mission_id="01KZPRE2H8T2X6R4N9YV3D5C7B")

    result = _invoke_guard(tmp_path, monkeypatch, slug, "--json")

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["passed"] is True
    assert payload["exempt"] == [{"slug": slug, "reasons": [PRE_ACCEPT_EXEMPT_NOTE]}]
    assert {"touched_slugs", "non_mission_slugs", "failures"} <= payload.keys()
    assert payload["failures"] == []


def test_exempt_mission_listed_alongside_a_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    corpus = tmp_path / "kitty-specs"
    corpus.mkdir()
    exempt_slug = "pre-accept-mixed-01KZPRE3"
    bad_slug = "accepted-unstamped-01KZPRE4"
    _build_pre_accept_mission(corpus, slug=exempt_slug, mission_id="01KZPRE3H8T2X6R4N9YV3D5C7C")
    _build_native_un_cut_over_mission(corpus, slug=bad_slug, mission_id="01KZPRE4H8T2X6R4N9YV3D5C7D")
    (tmp_path / ".kittify").mkdir()
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(tmp_path))
    paths_file = tmp_path / "changed-paths.txt"
    paths_file.write_text(f"kitty-specs/{exempt_slug}/meta.json\nkitty-specs/{bad_slug}/meta.json\n", encoding="utf-8")

    result = CliRunner().invoke(_guard_app, ["--paths-from", str(paths_file)])

    assert result.exit_code == 1
    out = " ".join(result.output.split())
    assert f"{exempt_slug}: {PRE_ACCEPT_EXEMPT_NOTE}" in out
    assert remedy_command(bad_slug) in out


def test_accepted_unstamped_mission_gets_the_backfill_remedy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    corpus = tmp_path / "kitty-specs"
    corpus.mkdir()
    slug = "accepted-unstamped-json-01KZPRE5"
    _build_native_un_cut_over_mission(corpus, slug=slug, mission_id="01KZPRE5H8T2X6R4N9YV3D5C7E")

    result = _invoke_guard(tmp_path, monkeypatch, slug, "--json")

    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["failures"][0]["remedy"] == remedy_command(slug)
    assert payload["exempt"] == []


def test_malformed_phase_remedy_names_meta_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    corpus = tmp_path / "kitty-specs"
    corpus.mkdir()
    slug = "malformed-phase-01KZPRE6"
    mission_dir = _build_pre_accept_mission(corpus, slug=slug, mission_id="01KZPRE6H8T2X6R4N9YV3D5C7F")
    _write_meta(mission_dir, mission_id="01KZPRE6H8T2X6R4N9YV3D5C7F", status_phase="not-a-number")

    result = _invoke_guard(tmp_path, monkeypatch, slug, "--json")

    assert result.exit_code == 1
    remedy = json.loads(result.output)["failures"][0]["remedy"]
    assert "meta.json status_phase" in remedy
    assert slug in remedy


def test_absent_mission_id_remedy_is_backfill_identity(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    corpus = tmp_path / "kitty-specs"
    corpus.mkdir()
    slug = "no-mission-id-cli-01KZPRE7"
    _build_missing_mission_id_mission(corpus, slug=slug)

    result = _invoke_guard(tmp_path, monkeypatch, slug, "--json")

    assert result.exit_code == 1
    assert json.loads(result.output)["failures"][0]["remedy"] == "spec-kitty migrate backfill-identity"


def test_remedy_for_unreadable_meta_and_unknown_reason(tmp_path: Path) -> None:
    from specify_cli.status import CutOverVerdict
    from specify_cli.status.cutover_eligibility import REASON_LEGACY_UNDECIDABLE, REASON_META_UNREADABLE

    def verdict(*reasons: str) -> CutOverVerdict:
        return CutOverVerdict(mission_dir=tmp_path, mission_slug="m-1", cut_over=False, reasons=reasons)

    for reason in (REASON_META_UNREADABLE, REASON_LEGACY_UNDECIDABLE):
        assert remedy_for(verdict(reason)) == "repair kitty-specs/m-1/meta.json or the unreadable WP file, then rerun"
    assert remedy_for(verdict("status_phase not flipped despite event-log runtime evidence")) == remedy_command("m-1")
    assert remedy_for(verdict()) == remedy_command("m-1")
