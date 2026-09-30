"""WP06 T034 — `charter generate` auto-tracks + non-git fail-fast (issue #841).

These tests lock in the parity contract: after `charter generate` succeeds in a
fresh git repo, the produced ``.kittify/charter/charter.md`` is auto-staged so
the immediately-following ``charter bundle validate`` accepts it without any
operator ``git add`` between the two commands. In a non-git environment,
``generate`` exits non-zero with an actionable error containing both ``git``
and ``init``.
"""

from __future__ import annotations

import contextlib
import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest
from ruamel.yaml import YAML
from typer.testing import CliRunner

from specify_cli import app as cli_app
from specify_cli.cli.commands.charter import app as charter_app
from specify_cli.cli.commands.charter_bundle import app as charter_bundle_app
from specify_cli.task_utils import TaskCliError


pytestmark = [pytest.mark.unit, pytest.mark.git_repo]

runner = CliRunner()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _git_init(repo: Path) -> None:
    """Initialize a minimal git repo with identity configured."""
    subprocess.run(
        ["git", "init", "--initial-branch=main"],
        cwd=repo, check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=repo, check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=repo, check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "config", "commit.gpgsign", "false"],
        cwd=repo, check=True, capture_output=True,
    )


def _git_initial_commit(repo: Path) -> None:
    readme = repo / "README.md"
    readme.write_text("# Test Repo\n", encoding="utf-8")
    subprocess.run(
        ["git", "add", "README.md"],
        cwd=repo, check=True, capture_output=True, text=True,
    )
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=repo, check=True, capture_output=True, text=True,
    )


def _write_minimal_interview(repo: Path) -> None:
    """Place a minimal interview answers.yaml so charter generate can run.

    The interview file shape is what ``charter.activation.interview.read_interview_answers``
    parses. We supply only the fields ``compile_charter`` consults.
    """
    interview_dir = repo / ".kittify" / "charter" / "interview"
    interview_dir.mkdir(parents=True, exist_ok=True)
    (interview_dir / "answers.yaml").write_text(
        "mission: software-dev\n"
        "profile: minimal\n"
        "selected_paradigms: []\n"
        "selected_directives: []\n"
        "available_tools: []\n"
        "answers:\n"
        "  purpose: Test charter for auto-track contract.\n",
        encoding="utf-8",
    )


def _write_curated_charter_md(repo: Path) -> None:
    """Seed a hand-authored ``charter.md`` (consolidate-charter-bundle WP03).

    ``charter.md`` is a curated companion that ``charter generate`` never
    writes (data-model.md Landmine 3 -- the #2772 clobber, one level down,
    on a tracked file). ``bundle validate`` requires it present+tracked
    (``CharterBundleManifest.tracked_files``), so tests that exercise the
    full generate -> validate contract must seed it first, mirroring a
    project where governance has already been curated.
    """
    charter_dir = repo / ".kittify" / "charter"
    charter_dir.mkdir(parents=True, exist_ok=True)
    (charter_dir / "charter.md").write_text(
        "# Curated Charter\n\nHand-authored governance prose.\n", encoding="utf-8"
    )


def _ls_files_stage(repo: Path) -> list[str]:
    """Return repo-relative paths reported by ``git ls-files --stage``."""
    result = subprocess.run(
        ["git", "ls-files", "--stage"],
        cwd=repo, check=True, capture_output=True, text=True,
    )
    paths: list[str] = []
    for line in result.stdout.splitlines():
        # format: <mode> <hash> <stage>\t<path>
        if "\t" in line:
            paths.append(line.split("\t", 1)[1])
    return paths


# ---------------------------------------------------------------------------
# T034a — generate then bundle validate succeeds in fresh git repo
# ---------------------------------------------------------------------------


def test_generate_then_bundle_validate_succeeds_in_fresh_git_repo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """After ``charter generate`` in a fresh git repo, ``bundle validate``
    accepts the bundle without any intervening ``git add``.

    ``bundle validate`` requires ``charter.md`` present+tracked
    (``CharterBundleManifest.tracked_files``), and ``generate`` never
    writes it (WP03 Landmine 3 fix) -- a curated ``charter.md`` must
    already exist, same as a real project that has authored its
    governance prose.
    """
    _git_init(tmp_path)
    _write_minimal_interview(tmp_path)
    _write_curated_charter_md(tmp_path)

    monkeypatch.chdir(tmp_path)
    gen_result = runner.invoke(
        charter_app, ["generate", "--from-interview", "--json"],
        catch_exceptions=False,
    )
    assert gen_result.exit_code == 0, (
        f"generate failed: stdout={gen_result.stdout!r} "
        f"stderr={getattr(gen_result, 'stderr', '')!r}"
    )

    # NO manual `git add` between generate and validate.
    val_result = runner.invoke(
        charter_bundle_app, ["validate", "--json"],
        catch_exceptions=False,
    )
    assert val_result.exit_code == 0, (
        f"bundle validate failed after generate: "
        f"stdout={val_result.stdout!r}"
    )


# ---------------------------------------------------------------------------
# T034b — generate in non-git dir fails fast
# ---------------------------------------------------------------------------


def test_generate_in_non_git_dir_fails_fast(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``charter generate`` outside a git repo MUST exit non-zero with a
    message containing both ``git`` and ``init``.
    """
    # NOT calling _git_init: tmp_path is a plain directory.
    _write_minimal_interview(tmp_path)

    monkeypatch.chdir(tmp_path)
    result = runner.invoke(
        charter_app, ["generate", "--from-interview"],
        catch_exceptions=False,
    )

    assert result.exit_code != 0, (
        f"generate must fail in non-git dir; got exit 0. output={result.stdout!r}"
    )
    combined = (result.stdout or "") + (result.output or "")
    lowered = combined.lower()
    assert "git" in lowered, (
        f"error message must mention 'git'. output={combined!r}"
    )
    assert "init" in lowered, (
        f"error message must mention 'init' (the remediation). output={combined!r}"
    )


# ---------------------------------------------------------------------------
# T034c — generate stages produced files
# ---------------------------------------------------------------------------


def test_generate_stages_produced_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """After ``charter generate`` succeeds, ``git ls-files --stage`` MUST
    include the generated charter commit inputs.

    ``charter.yaml`` is the sole file ``write_compiled_charter`` produces
    (WP03: ``charter.md``/``references.yaml`` are never written by
    generate); a pre-existing curated ``charter.md`` is auto-staged too
    because it is a manifest ``tracked_files`` entry.
    """
    _git_init(tmp_path)
    _write_minimal_interview(tmp_path)
    _write_curated_charter_md(tmp_path)

    monkeypatch.chdir(tmp_path)
    result = runner.invoke(
        charter_app, ["generate", "--from-interview"],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, (
        f"generate failed: output={result.stdout!r}"
    )
    staged = _ls_files_stage(tmp_path)

    expected = {
        ".kittify/charter/charter.md",
        ".kittify/charter/charter.yaml",
    }
    assert expected.issubset(set(staged)), (
        f"generated charter commit inputs must be auto-staged after generate; "
        f"expected={expected!r}, got staged paths: {staged!r}"
    )
    assert ".kittify/charter/references.yaml" not in staged, (
        "references.yaml is retired (WP03/T012) and must never be staged"
    )


def test_generate_from_interview_fails_when_answers_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``--from-interview`` must not silently fall back to defaults."""
    _git_init(tmp_path)
    # Hermetic against a stray ``.kittify`` marker anywhere above ``tmp_path``
    # (e.g. a developer's home-dir kittify root, or another test's litter
    # under the OS temp dir): without an interview file at ``tmp_path`` yet,
    # ``locate_project_root``'s walk-up would otherwise happily resolve to
    # that ambient ancestor instead of this fixture's repo.
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(tmp_path))

    monkeypatch.chdir(tmp_path)
    result = runner.invoke(
        charter_app, ["generate", "--from-interview"],
        catch_exceptions=False,
    )

    assert result.exit_code != 0
    assert "No charter interview answers found" in result.stdout
    # The slash command is an agent-session command, not a shell one (#4624):
    # the hint must say where it runs, alongside the shell alternative.
    flat = " ".join(result.stdout.split())
    assert "Run `/spec-kitty.charter` inside your coding agent (Claude Code, Codex, Cursor)" in flat
    assert "run `spec-kitty charter interview --defaults` here" in flat
    assert not (tmp_path / ".kittify" / "charter" / "charter.md").exists()


def test_generate_from_interview_missing_answers_json_is_parseable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``--json`` error output must stay machine-parseable."""
    _git_init(tmp_path)
    # See the hermeticity note in test_generate_from_interview_fails_when_answers_missing.
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(tmp_path))

    monkeypatch.chdir(tmp_path)
    result = runner.invoke(
        charter_app, ["generate", "--from-interview", "--json"],
        catch_exceptions=False,
    )

    payload = json.loads(result.stdout)
    assert result.exit_code != 0
    assert payload["success"] is False
    assert payload["result"] == "error"
    assert "No charter interview answers found" in payload["error"]


def _assert_generate_refuses_symlinked_charter_before_side_effects(tmp_path: Path) -> None:
    _git_init(tmp_path)
    public_dir = tmp_path / "spec"
    public_dir.mkdir()
    public_charter = public_dir / "constitution.md"
    public_charter.write_text("# Public Constitution\n", encoding="utf-8")

    charter_dir = tmp_path / ".kittify" / "charter"
    charter_dir.mkdir(parents=True)
    charter_link = charter_dir / "charter.md"
    try:
        charter_link.symlink_to(public_charter)
    except OSError as exc:
        pytest.skip(f"symlinks unavailable: {exc}")

    with contextlib.chdir(tmp_path):
        result = runner.invoke(
            charter_app, ["generate", "--no-from-interview", "--force", "--json"],
            catch_exceptions=False,
        )

    payload = json.loads(result.stdout)
    assert result.exit_code != 0
    assert payload["success"] is False
    assert payload["result"] == "error"
    assert "Refusing to overwrite symlinked charter" in payload["error"]
    assert public_charter.read_text(encoding="utf-8") == "# Public Constitution\n"

    assert not (tmp_path / ".kittify" / "encoding-provenance").exists()
    assert not (charter_dir / "charter.yaml").exists()
    assert not (charter_dir / "references.yaml").exists()
    assert not (charter_dir / "governance.yaml").exists()
    assert not (charter_dir / "directives.yaml").exists()
    assert not (charter_dir / "metadata.yaml").exists()
    assert not (tmp_path / ".gitignore").exists()
    assert not (tmp_path / ".kittify" / "config.yaml").exists()


@pytest.mark.requires_symlinks
def test_generate_refuses_symlinked_charter_before_side_effects(tmp_path: Path) -> None:
    """A symlinked runtime charter must fail before generate dirties the repo."""
    _assert_generate_refuses_symlinked_charter_before_side_effects(tmp_path)


@pytest.mark.requires_symlinks
@pytest.mark.windows_ci
def test_windows_generate_refuses_symlinked_charter_before_side_effects(tmp_path: Path) -> None:
    """Native Windows CI covers symlink-generate refusal when symlinks are available."""
    _assert_generate_refuses_symlinked_charter_before_side_effects(tmp_path)


def test_status_json_error_is_parseable() -> None:
    """``charter status --json`` must not emit Rich-formatted error text."""
    with patch(
        "specify_cli.cli.commands.charter.find_repo_root",
        side_effect=TaskCliError("repo root unavailable"),
    ):
        result = runner.invoke(
            charter_app, ["status", "--json"],
            catch_exceptions=False,
        )

    payload = json.loads(result.stdout)
    assert result.exit_code != 0
    assert payload == {
        "error": "repo root unavailable",
        "result": "error",
        "success": False,
    }


def test_generate_fails_when_auto_stage_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Auto-track failures must not be reported as successful generation."""
    _git_init(tmp_path)
    _write_minimal_interview(tmp_path)
    (tmp_path / ".git" / "index.lock").write_text("locked\n", encoding="utf-8")

    monkeypatch.chdir(tmp_path)
    result = runner.invoke(
        charter_app, ["generate", "--from-interview", "--json"],
        catch_exceptions=False,
    )

    assert result.exit_code != 0
    assert "Failed to stage charter file" in result.stdout


# ---------------------------------------------------------------------------
# Additional safety: pre-existing staging area not corrupted by generate
# ---------------------------------------------------------------------------


def test_generate_does_not_disturb_unrelated_staged_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Auto-track must not blow away the operator's pre-existing stage."""
    _git_init(tmp_path)
    _write_minimal_interview(tmp_path)

    # Pre-stage an unrelated file.
    unrelated = tmp_path / "README.md"
    unrelated.write_text("hello\n", encoding="utf-8")
    subprocess.run(
        ["git", "add", "README.md"],
        cwd=tmp_path, check=True, capture_output=True,
    )

    monkeypatch.chdir(tmp_path)
    result = runner.invoke(
        charter_app, ["generate", "--from-interview"],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, (
        f"generate failed: output={result.stdout!r}"
    )
    staged = _ls_files_stage(tmp_path)

    assert "README.md" in staged, (
        f"pre-staged README.md must remain staged; got {staged!r}"
    )
    assert ".kittify/charter/charter.yaml" in staged


def test_generic_safe_commit_commits_generated_charter_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``safe-commit`` creates the charter commit without raw git commit."""
    _git_init(tmp_path)
    _git_initial_commit(tmp_path)
    _write_minimal_interview(tmp_path)
    subprocess.run(
        ["git", "switch", "-c", "charter/update"],
        cwd=tmp_path, check=True, capture_output=True, text=True,
    )

    monkeypatch.chdir(tmp_path)
    gen = runner.invoke(
        charter_app, ["generate", "--from-interview"],
        catch_exceptions=False,
    )
    assert gen.exit_code == 0, f"generate failed: {gen.stdout!r}"

    committed = runner.invoke(
        cli_app,
        [
            "safe-commit",
            "--message",
            "chore: generate project charter",
            "--json",
            ".kittify/charter/interview/answers.yaml",
            ".kittify/charter/charter.yaml",
        ],
        catch_exceptions=False,
    )
    assert committed.exit_code == 0, f"commit failed: {committed.stdout!r}"
    assert '"committed": true' in committed.stdout

    log = subprocess.run(
        ["git", "log", "-1", "--pretty=%s"],
        cwd=tmp_path, check=True, capture_output=True, text=True,
    ).stdout.strip()
    assert log == "chore: generate project charter"
    stash_list = subprocess.run(
        ["git", "stash", "list"],
        cwd=tmp_path, check=True, capture_output=True, text=True,
    ).stdout
    assert "spec-kitty-safe-commit" not in stash_list


def test_generic_safe_commit_targets_current_git_worktree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``safe-commit`` must commit to the current worktree branch, not main."""
    _git_init(tmp_path)
    (tmp_path / ".kittify").mkdir()
    (tmp_path / ".kittify" / "config.json").write_text("{}\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("# Test Repo\n", encoding="utf-8")
    subprocess.run(
        ["git", "add", "README.md", ".kittify/config.json"],
        cwd=tmp_path, check=True, capture_output=True, text=True,
    )
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=tmp_path, check=True, capture_output=True, text=True,
    )
    main_head_before = subprocess.run(
        ["git", "rev-parse", "main"],
        cwd=tmp_path, check=True, capture_output=True, text=True,
    ).stdout.strip()

    worktree = tmp_path.parent / f"{tmp_path.name}-worktree"
    subprocess.run(
        ["git", "worktree", "add", "-b", "charter/update", str(worktree)],
        cwd=tmp_path, check=True, capture_output=True, text=True,
    )
    (worktree / "charter.txt").write_text("worktree charter change\n", encoding="utf-8")

    monkeypatch.chdir(worktree)
    committed = runner.invoke(
        cli_app,
        [
            "safe-commit",
            "--message",
            "chore: generate project charter",
            "--json",
            "charter.txt",
        ],
        catch_exceptions=False,
    )

    assert committed.exit_code == 0, f"commit failed: {committed.stdout!r}"
    assert '"committed": true' in committed.stdout

    worktree_subject = subprocess.run(
        ["git", "log", "-1", "--pretty=%s"],
        cwd=worktree, check=True, capture_output=True, text=True,
    ).stdout.strip()
    main_head_after = subprocess.run(
        ["git", "rev-parse", "main"],
        cwd=tmp_path, check=True, capture_output=True, text=True,
    ).stdout.strip()
    worktree_status = subprocess.run(
        ["git", "status", "--short"],
        cwd=worktree, check=True, capture_output=True, text=True,
    ).stdout

    assert worktree_subject == "chore: generate project charter"
    assert main_head_after == main_head_before
    assert "charter.txt" not in worktree_status


def test_charter_template_uses_safe_commit_command() -> None:
    """Slash prompt must route commits through Spec Kitty, not raw git commit."""
    template = Path(
        "packs/built-in/missions/mission-steps/software-dev/charter/prompt.md"
    ).read_text(encoding="utf-8")

    assert "spec-kitty safe-commit" in template
    assert "git commit" not in template
    assert "Listen intently" in template


# ---------------------------------------------------------------------------
# #2940 — the interview -> generate round-trip must hold, and a present-but-
# malformed answers.yaml must be reported HONESTLY (distinct from "missing"),
# not conflated into the "run the interview" remediation.
# ---------------------------------------------------------------------------


def test_interview_then_generate_consumes_answers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Close-by-construction (#2940): answers written by ``charter interview``
    are consumed by ``charter generate --from-interview`` in the same repo.

    The round-trip is correct on current main; this pins it so it can never
    silently regress. Invokes the REAL ``interview`` command (not a
    hand-written file) so the write->read seam is exercised end-to-end.
    """
    _git_init(tmp_path)
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(tmp_path))
    monkeypatch.setenv("SPEC_KITTY_HOME", str(tmp_path / ".home"))
    monkeypatch.setenv("SPEC_KITTY_SYNC_DISABLE", "1")

    monkeypatch.chdir(tmp_path)
    interview = runner.invoke(
        charter_app,
        [
            "interview", "--mission-type", "software-dev",
            "--profile", "minimal", "--defaults", "--json",
        ],
        catch_exceptions=False,
    )
    assert interview.exit_code == 0, interview.stdout
    assert (tmp_path / ".kittify/charter/interview/answers.yaml").exists()

    generate = runner.invoke(
        charter_app,
        ["generate", "--from-interview", "--mission-type", "software-dev", "--json"],
        catch_exceptions=False,
    )

    assert generate.exit_code == 0, generate.stdout
    payload = json.loads(generate.stdout)
    assert payload["result"] == "success"
    # The answers were CONSUMED, not silently replaced by defaults.
    assert payload["interview_source"] == "interview"
    assert "No charter interview answers found" not in generate.stdout


def test_generate_from_interview_reports_malformed_answers_distinctly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """#2940 honesty: a present-but-malformed ``answers.yaml`` must NOT be
    reported as 'No charter interview answers found'.

    That message sends the operator to re-run the interview, when the real
    problem is a corrupt/wrong-shape file that a fresh interview would just
    overwrite — masking the actual fault. The diagnostic must name the file
    and its malformed shape instead.
    """
    _git_init(tmp_path)
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(tmp_path))
    interview_dir = tmp_path / ".kittify" / "charter" / "interview"
    interview_dir.mkdir(parents=True, exist_ok=True)
    # Parses as valid YAML, but the top level is a list, not a mapping —
    # exactly the shape ``read_interview_answers`` degrades to ``None`` on.
    (interview_dir / "answers.yaml").write_text(
        "- not\n- a\n- mapping\n", encoding="utf-8"
    )

    monkeypatch.chdir(tmp_path)
    result = runner.invoke(
        charter_app, ["generate", "--from-interview", "--json"],
        catch_exceptions=False,
    )

    assert result.exit_code != 0
    payload = json.loads(result.stdout)
    assert payload["success"] is False
    assert payload["result"] == "error"
    # Honest: names the file + its malformed shape, NOT the missing-file message.
    assert "No charter interview answers found" not in payload["error"]
    assert "answers.yaml" in payload["error"]
    assert (
        "malformed" in payload["error"].lower()
        or "not a mapping" in payload["error"].lower()
    )


# ---------------------------------------------------------------------------
# WP03 T016 (#5257) — `unresolved_references` machine-readable in `--json`
# ---------------------------------------------------------------------------
#
# spec.md User Story 1 Acceptance Scenario 2: the JSON output's diagnostics
# must carry the same reference id and reason machine-readably -- so CI and
# readiness probes consuming `--json` can detect the condition without
# parsing prose. WP02 already exposes the structured records on
# `CompiledCharter.unresolved_reference_records`
# (`src/charter/activation/compiler.py`); this WP threads that field through
# `generate.py`'s `--json` emit block as a new, always-present
# `unresolved_references` key
# (contracts/charter-generate-json-diagnostics.md).


def _write_single_scope_filtered_styleguide_activation(repo: Path) -> None:
    """Activate ``styleguide/java-conventions`` directly via ``.kittify/config.yaml``.

    Legacy/unmigrated shape (no ``charter:`` pointer key) -- same convention
    ``tests/charter/test_charter_generate_scoped_reference_parity.py``'s
    ``_write_activation_config`` uses: an absent pointer means activation is
    read directly from ``config.yaml``'s own top-level ``activated_*`` keys.
    """
    config_path = repo / ".kittify" / "config.yaml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    yaml = YAML()
    yaml.default_flow_style = False
    payload = {
        "vcs": {"type": "git"},
        "activated_styleguides": ["java-conventions"],
    }
    with config_path.open("w", encoding="utf-8") as handle:
        yaml.dump(payload, handle)


def _write_python_only_interview_answers(repo: Path) -> None:
    """Persist an interview transcript naming ONLY Python.

    ``infer_repo_languages`` then resolves a real, non-empty active-language
    set (``["python"]``) that excludes java -- the actual #5257 defect
    condition (a present-on-disk id excluded solely by language scope).
    """
    answers_path = repo / ".kittify" / "charter" / "interview" / "answers.yaml"
    answers_path.parent.mkdir(parents=True, exist_ok=True)
    yaml = YAML()
    yaml.default_flow_style = False
    payload = {
        "schema_version": "1.0.0",
        "mission": "software-dev",
        "profile": "minimal",
        "answers": {"languages_frameworks": "Python services with pytest and ruff tooling"},
        "selected_paradigms": [],
        "selected_directives": [],
        "selected_tactics": [],
        "available_tools": [],
    }
    with answers_path.open("w", encoding="utf-8") as handle:
        yaml.dump(payload, handle)


def test_generate_json_reports_unresolved_references_for_scope_filtered_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FR-004 / spec.md User Story 1 Acceptance Scenario 2 (WP03 T016).

    ``charter generate --force --json`` must carry the unresolved
    reference's id and reason machine-readably in a new, always-present
    ``unresolved_references`` field -- not only as free-text in
    ``diagnostics`` -- so CI and readiness probes consuming ``--json`` can
    detect the condition without parsing prose
    (contracts/charter-generate-json-diagnostics.md).

    RED pre-T014: WP02's compiler fix already exposes
    ``compiled.unresolved_reference_records``, but ``generate.py``'s
    ``--json`` emit block does not yet thread it through at all, so this
    key is entirely absent from the payload.
    """
    _git_init(tmp_path)
    _write_curated_charter_md(tmp_path)
    _write_single_scope_filtered_styleguide_activation(tmp_path)
    _write_python_only_interview_answers(tmp_path)

    monkeypatch.chdir(tmp_path)
    result = runner.invoke(
        charter_app, ["generate", "--force", "--json"],
        catch_exceptions=False,
    )

    assert result.exit_code == 0, f"generate failed: {result.stdout!r}"
    payload = json.loads(result.stdout)

    assert "unresolved_references" in payload, (
        "'unresolved_references' key missing from --json output entirely -- "
        f"payload keys: {sorted(payload)!r}"
    )
    unresolved = payload["unresolved_references"]
    assert isinstance(unresolved, list)

    matches = [
        entry
        for entry in unresolved
        if entry.get("kind") == "styleguide" and entry.get("id") == "java-conventions"
    ]
    assert len(matches) == 1, (
        f"expected exactly one unresolved_references entry for "
        f"styleguide/java-conventions, got {matches!r} (full list: {unresolved!r})"
    )
    entry = matches[0]
    assert entry["cause"] == "scope_filtered"
    assert entry["detail"], "detail must be a non-empty, human-readable string"
    assert "python" in entry["detail"].lower(), (
        f"detail must name the active language set that excluded this id, "
        f"got: {entry['detail']!r}"
    )


# ---------------------------------------------------------------------------
# WP03 T015 (#5257) — `diagnostics` field shape unchanged by the new key
# ---------------------------------------------------------------------------


def test_generate_json_diagnostics_field_shape_unchanged_by_unresolved_references(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The additive-alongside design (contracts/charter-generate-json-
    diagnostics.md) must not widen or restructure the existing
    ``diagnostics`` field: it stays a flat ``list[str]`` -- every element a
    ``str``, never a ``dict`` -- both before and after this WP's
    ``unresolved_references`` addition. Uses the same scope-filtered
    fixture as T016, which is guaranteed to populate ``diagnostics`` with at
    least one unresolved-reference line.
    """
    _git_init(tmp_path)
    _write_curated_charter_md(tmp_path)
    _write_single_scope_filtered_styleguide_activation(tmp_path)
    _write_python_only_interview_answers(tmp_path)

    monkeypatch.chdir(tmp_path)
    result = runner.invoke(
        charter_app, ["generate", "--force", "--json"],
        catch_exceptions=False,
    )

    assert result.exit_code == 0, f"generate failed: {result.stdout!r}"
    payload = json.loads(result.stdout)

    diagnostics = payload["diagnostics"]
    assert isinstance(diagnostics, list)
    assert diagnostics, "expected at least one diagnostics line for the scope-filtered fixture"
    assert all(isinstance(line, str) for line in diagnostics), (
        f"diagnostics must remain a flat list[str] -- found a non-str element: {diagnostics!r}"
    )
    # The unresolved-reference condition is still ALSO reported as free text
    # in diagnostics -- the new key is additive, not a replacement.
    assert any("java-conventions" in line for line in diagnostics)


# ---------------------------------------------------------------------------
# Additional `unresolved_references` shape coverage (contract completeness,
# beyond T016's single red-first scenario): the always-present empty-list
# case. (A "genuine missing id" CLI-level case was deliberately NOT added
# here: an id in `activated_styleguides` that fails `resolve_config_id`
# during `_resolve_config_activated_roots` -- src/charter/activation/
# kind_vocabulary.py's `UnknownArtifactIdError` -- hard-fails generate
# BEFORE `compile_charter`'s soft classify-and-placeholder path runs at
# all, a pre-existing, unrelated-to-#5257 validation layer. The
# `missing_artifact`/`typo_suspected` CatalogMissCause classification this
# WP's new JSON key surfaces is already unit-tested at the compiler layer
# by WP01/WP02 -- see tests/charter/test_compiler_scope_filtered_placeholder.py,
# test_catalog_completeness_4785.py, test_charter_whole_kind_invariants.py --
# and WP03's own dict-shape pass-through (`list(compiled.
# unresolved_reference_records)`, identical for every cause value) is
# already exercised end-to-end by the scope_filtered fixture above.)
# ---------------------------------------------------------------------------


def test_generate_json_unresolved_references_empty_list_when_nothing_unresolved(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When there is nothing unresolved, ``unresolved_references`` must
    still be present as ``[]`` -- never omitted, never ``null`` -- matching
    ``diagnostics``'s own always-present convention so a consumer can rely
    on key presence rather than ``.get()`` with a default.
    """
    _git_init(tmp_path)
    _write_minimal_interview(tmp_path)
    _write_curated_charter_md(tmp_path)

    monkeypatch.chdir(tmp_path)
    result = runner.invoke(
        charter_app, ["generate", "--from-interview", "--force", "--json"],
        catch_exceptions=False,
    )

    assert result.exit_code == 0, f"generate failed: {result.stdout!r}"
    payload = json.loads(result.stdout)

    assert "unresolved_references" in payload
    assert payload["unresolved_references"] == []
