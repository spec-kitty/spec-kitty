"""Tests for charter CLI commands."""

import json
from collections.abc import Callable
from pathlib import Path
import subprocess
from unittest.mock import patch

import pytest
import typer
from typer.testing import CliRunner

from specify_cli.cli.commands.charter import app

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

runner = CliRunner()


SAMPLE_CHARTER = """# Testing Standards

## Coverage Requirements
- Minimum 80% coverage

## Quality Gates
- Pass all linters

## Project Directives
1. Write tests for new features
"""


def _git_init(repo_root: Path) -> None:
    subprocess.run(["git", "init", "--quiet", str(repo_root)], check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_root, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_root, check=True)


@pytest.fixture
def mock_repo(tmp_path: Path) -> Path:
    repo_root = tmp_path / "mock_repo"
    repo_root.mkdir()

    charter_dir = repo_root / ".kittify" / "charter"
    charter_dir.mkdir(parents=True)

    charter_file = charter_dir / "charter.md"
    charter_file.write_text(SAMPLE_CHARTER, encoding="utf-8")

    return repo_root


def _write_charter_yaml_bundle(charter_dir: Path) -> None:
    """Materialize a minimal, schema-compatible consolidated ``charter.yaml``.

    IC-04 (#2773): the standalone derived triad (``governance.yaml`` /
    ``directives.yaml`` / ``metadata.yaml``) is retired -- ``governance`` and
    ``directives`` now live as hand-authored sections directly inside
    ``charter.yaml`` (``charter.activation.schemas.CharterYaml``). ``charter status``
    reports ``SYNCED`` off the presence of this file (see
    ``_collect_charter_sync_status`` in
    ``specify_cli.cli.commands.charter._status_collectors``), not off a
    ``metadata.yaml`` hash comparison, which is why this seed is needed for
    the "synced" status tests below. ``metadata.bundle_schema_version: 2``
    satisfies the bundle-compatibility gate (``_assert_bundle_compatible``).
    """
    (charter_dir / "charter.yaml").write_text(
        "schema_version: '2.0.0'\n"
        "governance: {}\n"
        "directives:\n"
        "  directives: []\n"
        "catalog:\n"
        "  mission: software-dev\n"
        "  template_set: software-dev-default\n"
        "  languages: []\n"
        "  references: []\n"
        "overrides: {}\n"
        "metadata:\n"
        "  generated_at: ''\n"
        "  bundle_schema_version: 2\n",
        encoding="utf-8",
    )


def test_sync_command_success(mock_repo: Path) -> None:
    """#3045: the assertion that used to live here --
    ``"Charter already in sync" in result.stdout``, defended by this test's
    prior docstring as the "current, intentional contract" -- was a STALE
    PIN. Issue #3045 identifies it as the P0 escalator for the underlying
    defect (``charter sync`` reports success unconditionally, even for a
    charter that was never synced): a test asserting the misleading message
    is *intended* means no gate could ever catch the regression. Per the
    failing-test remediation framework a stale pin is deleted/rewritten, not
    annotated -- removed here in the same commit that adds
    ``test_sync_command_human_and_json_surfaces_do_not_contradict_3045``
    below, which is the red-first replacement (see that test's docstring).
    The two must not be re-separated later: this test defends only the
    coverage that is still valid under EITHER sanctioned #3045 remedy
    (repair or honest-reporter) -- it never re-materializes the retired
    derived triad (``governance.yaml`` / ``directives.yaml`` /
    ``metadata.yaml``, retired by IC-04 / #2773). No exit-code assertion is
    kept either: ``mock_repo`` is exactly the "charter.md present,
    charter.yaml absent, never synced" state the honest-reporter remedy is
    expected to make exit non-zero for (per #3045's suggested shape) -- a
    hard ``exit_code == 0`` pin here would forbid that remedy through a
    second assertion in this file, recreating the same problem this
    remediation exists to close."""
    with patch("specify_cli.cli.commands.charter.find_repo_root") as mock_find_root:
        mock_find_root.return_value = mock_repo

        runner.invoke(app, ["sync"])

        for retired_file in ("governance.yaml", "directives.yaml", "metadata.yaml"):
            assert not (mock_repo / ".kittify" / "charter" / retired_file).exists()


def test_sync_command_is_an_explicit_noop(mock_repo: Path) -> None:
    """#4679: ``charter sync`` is a permanent no-op kept for compatibility, and
    says so -- exit 0 with an explicit "No-op" line -- instead of the
    failure-looking red "Charter was not synced" / exit 1 that #3045's
    honest-reporter remedy rendered for the same inert outcome. Idempotent:
    a second ``sync`` (and ``--force``, which does nothing) reads the same."""
    with patch("specify_cli.cli.commands.charter.find_repo_root") as mock_find_root:
        mock_find_root.return_value = mock_repo

        for args in (["sync"], ["sync"], ["sync", "--force"]):
            result = runner.invoke(app, args)
            assert result.exit_code == 0, result.stdout
            assert "No-op:" in result.stdout
            assert "kept for compatibility" in result.stdout
            assert "Nothing to do" in result.stdout
            assert "was not synced" not in result.stdout


def test_sync_command_json_output(mock_repo: Path) -> None:
    """IC-04 (#2773): mirrors ``test_sync_command_success`` -- ``sync``'s
    JSON payload reports the noop contract (``result: "noop"``, empty
    ``files_written``) because extraction is retired; ``stale_before`` stays
    ``True`` since ``metadata.yaml`` (the staleness marker ``sync()`` still
    checks) never gets created. #4679: the inert outcome is success-shaped
    (``success: True``) and carries an explicit ``message``, not the
    failure-looking ``success: False`` it used to report."""
    with patch("specify_cli.cli.commands.charter.find_repo_root") as mock_find_root:
        mock_find_root.return_value = mock_repo

        result = runner.invoke(app, ["sync", "--json"])

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["result"] == "noop"
        assert data["success"] is True
        assert "kept for compatibility" in data["message"]
        assert data["stale_before"] is True
        assert data["files_written"] == []


def test_sync_command_missing_charter(tmp_path: Path) -> None:
    repo_root = tmp_path / "no_charter"
    repo_root.mkdir()

    with patch("specify_cli.cli.commands.charter.find_repo_root") as mock_find_root:
        mock_find_root.return_value = repo_root

        result = runner.invoke(app, ["sync"])

        assert result.exit_code == 1
        assert "Charter not found" in result.stdout


def test_status_command_synced(mock_repo: Path) -> None:
    """IC-04 (#2773): ``charter status`` reports ``SYNCED`` off the presence
    of the consolidated ``charter.yaml`` (not a ``metadata.yaml`` hash match
    against the retired triad); the "Extracted files" table now lists
    ``charter.yaml``/``charter.md``, not ``governance.yaml``/
    ``directives.yaml`` (see ``_collect_charter_sync_status``)."""
    charter_dir = mock_repo / ".kittify" / "charter"
    _write_charter_yaml_bundle(charter_dir)

    with patch("specify_cli.cli.commands.charter.find_repo_root") as mock_find_root:
        mock_find_root.return_value = mock_repo

        runner.invoke(app, ["sync"])
        result = runner.invoke(app, ["status"])

        assert result.exit_code == 0
        assert "SYNCED" in result.stdout
        assert "charter.yaml" in result.stdout
        assert "charter.md" in result.stdout


def test_status_command_json_output(mock_repo: Path) -> None:
    """IC-04 (#2773): the "Extracted files" JSON array now enumerates the
    consolidated bundle files (``charter.yaml``, ``charter.md``) -- 2
    entries, not the retired 4-file triad + charter.md set."""
    charter_dir = mock_repo / ".kittify" / "charter"
    _write_charter_yaml_bundle(charter_dir)

    with patch("specify_cli.cli.commands.charter.find_repo_root") as mock_find_root:
        mock_find_root.return_value = mock_repo

        runner.invoke(app, ["sync"])
        result = runner.invoke(app, ["status", "--json"])

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["charter_sync"]["status"] == "synced"
        assert len(data["charter_sync"]["files"]) == 2


def test_interview_defaults_writes_answers(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    with patch("specify_cli.cli.commands.charter.find_repo_root") as mock_find_root:
        mock_find_root.return_value = repo_root

        result = runner.invoke(app, ["interview", "--defaults", "--json"])

        assert result.exit_code == 0
        payload = json.loads(result.stdout)
        assert payload["success"] is True
        answers_path = repo_root / payload["interview_path"]
        assert answers_path.exists()


def test_generate_command_success(tmp_path: Path, charter_cwd_isolation: Callable[..., Path]) -> None:
    """consolidate-charter-bundle WP03: ``generate`` writes ``charter.yaml`` as
    the authoritative source; ``references.yaml`` is never written (Landmine 3).

    ``charter.md`` is a display-only companion the *compiler*
    (``write_compiled_charter``) never emits — but the ``generate`` *command*
    seeds a minimal starter when absent (#2773 / ADR 2026-07-18-1), so the
    companion is discoverable and the FR-009 affordance holds. The seed is
    create-if-absent and never clobbers a curated file (that invariant is
    pinned separately by the ``--force`` preservation test below)."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _git_init(repo_root)
    (repo_root / ".kittify" / "charter").mkdir(parents=True)

    charter_cwd_isolation(repo_root)
    with patch("specify_cli.cli.commands.charter.find_repo_root") as mock_find_root:
        mock_find_root.return_value = repo_root

        result = runner.invoke(app, ["generate", "--no-from-interview"])

        assert result.exit_code == 0
        assert "generated and synced" in result.stdout
        assert (repo_root / ".kittify" / "charter" / "charter.yaml").exists()
        # charter.md seeded (was absent) as a starter companion, not resolving.
        charter_md = repo_root / ".kittify" / "charter" / "charter.md"
        assert charter_md.is_file()
        assert "curated companion" in charter_md.read_text(encoding="utf-8")
        assert not (repo_root / ".kittify" / "charter" / "references.yaml").exists()
        assert (repo_root / ".kittify" / "charter" / "library").exists()


def test_generate_does_not_require_force_when_charter_yaml_already_exists(tmp_path: Path, charter_cwd_isolation: Callable[..., Path]) -> None:
    """Landmine 3 inversion of the old force-gate test: a charter.yaml
    partial-merge refresh never needs ``--force`` -- there is nothing
    destructive left for it to gate (the whole point of the WP03 fix)."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _git_init(repo_root)
    charter_dir = repo_root / ".kittify" / "charter"
    charter_dir.mkdir(parents=True)
    (charter_dir / "charter.yaml").write_text(
        "schema_version: '2.0.0'\n"
        "governance: {}\n"
        "directives:\n"
        "  directives: []\n"
        "catalog:\n"
        "  mission: software-dev\n"
        "  template_set: software-dev-default\n"
        "  languages: []\n"
        "  references: []\n"
        "overrides: {}\n"
        "metadata:\n"
        "  generated_at: ''\n"
        "  bundle_schema_version: 2\n",
        encoding="utf-8",
    )

    charter_cwd_isolation(repo_root)
    with patch("specify_cli.cli.commands.charter.find_repo_root") as mock_find_root:
        mock_find_root.return_value = repo_root

        result = runner.invoke(app, ["generate", "--no-from-interview"])

        assert result.exit_code == 0, result.stdout


def test_generate_command_force_overwrites(tmp_path: Path, charter_cwd_isolation: Callable[..., Path]) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _git_init(repo_root)
    charter_dir = repo_root / ".kittify" / "charter"
    charter_dir.mkdir(parents=True)
    charter_file = charter_dir / "charter.md"
    charter_file.write_text("# Existing", encoding="utf-8")

    charter_cwd_isolation(repo_root)
    with patch("specify_cli.cli.commands.charter.find_repo_root") as mock_find_root:
        mock_find_root.return_value = repo_root

        result = runner.invoke(app, ["generate", "--force", "--json", "--no-from-interview"])

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["success"] is True
        assert data["template_set"]
        assert "selected_directives" in data
        assert data["references_count"] >= 1


def test_generate_force_preserves_curated_charter_prose_2772(tmp_path: Path, charter_cwd_isolation: Callable[..., Path]) -> None:
    """#2772 fixed by consolidate-charter-bundle WP03 -- was RED-FIRST P0.

    ``spec-kitty charter generate --force`` used to regenerate the
    human-facing ``charter.md`` from the interview/default template,
    DESTROYING curated prose: recompiling the bundle to add a single
    reference produced a 1237-line clobber of the curated v1.3.0 charter
    during the #2767 landing, forcing a ``git checkout HEAD -- charter.md``
    to recover it. The WP03 fix removes the write entirely (data-model.md
    Landmine 3): ``write_compiled_charter`` never writes ``charter.md`` at
    all any more (not even under ``--force``) -- ``charter.md`` is a
    curated companion, resolving authority lives in ``charter.yaml``.
    Un-marked ``@pytest.mark.regression`` now that the fix has landed.
    Tracking: #2772 (epic #2519).
    """
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _git_init(repo_root)
    charter_dir = repo_root / ".kittify" / "charter"
    charter_dir.mkdir(parents=True)
    curated_sentinel = (
        "CURATED-PROSE-SENTINEL-2772: hand-authored governance narrative "
        "that charter refresh must never destroy."
    )
    (charter_dir / "charter.md").write_text(
        f"# Curated Charter (v1.3.0)\n\n{curated_sentinel}\n", encoding="utf-8"
    )

    charter_cwd_isolation(repo_root)
    with patch("specify_cli.cli.commands.charter.find_repo_root") as mock_find_root:
        mock_find_root.return_value = repo_root

        result = runner.invoke(app, ["generate", "--force", "--json", "--no-from-interview"])

    assert result.exit_code == 0, result.stdout
    surviving = (charter_dir / "charter.md").read_text(encoding="utf-8")
    assert curated_sentinel in surviving, (
        "#2772: `charter generate --force` clobbered curated charter.md prose — "
        "the curated sentinel was destroyed by regeneration; charter.md must be "
        "preserved as a curated reference, not overwritten from the template."
    )


def test_generate_force_preserves_authored_charter_yaml_sections(tmp_path: Path, charter_cwd_isolation: Callable[..., Path]) -> None:
    """Landmine 3, one level down: ``charter generate --force`` refreshes
    ONLY charter.yaml's derived ``catalog``/``metadata`` -- authored
    ``governance``/``directives``/activation survive, exercised through the
    real CLI entry point (complements the compiler-level unit coverage in
    ``tests/charter/test_compiler_charter_yaml.py``)."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _git_init(repo_root)
    charter_dir = repo_root / ".kittify" / "charter"
    charter_dir.mkdir(parents=True)
    (charter_dir / "charter.yaml").write_text(
        "schema_version: '2.0.0'\n"
        "governance:\n"
        "  testing:\n"
        "    min_coverage: 91  # CLI-AUTHORED-GOVERNANCE-SENTINEL\n"
        "  quality: {}\n"
        "  commits: {}\n"
        "  performance: {}\n"
        "  branch_strategy: {}\n"
        "  doctrine: {}\n"
        "  activations: []\n"
        "  enforcement: {}\n"
        "directives:\n"
        "  directives: []\n"
        "catalog:\n"
        "  mission: stale-mission\n"
        "  template_set: stale-template-set\n"
        "  languages: []\n"
        "  references: []\n"
        "activated_directives:\n"
        "- 001-architectural-integrity-standard  # CLI-AUTHORED-ACTIVATION-SENTINEL\n"
        "overrides: {}\n"
        "metadata:\n"
        "  generated_at: '2020-01-01T00:00:00Z'\n"
        "  bundle_schema_version: 2\n",
        encoding="utf-8",
    )

    charter_cwd_isolation(repo_root)
    with patch("specify_cli.cli.commands.charter.find_repo_root") as mock_find_root:
        mock_find_root.return_value = repo_root

        result = runner.invoke(app, ["generate", "--force", "--json", "--no-from-interview"])

    assert result.exit_code == 0, result.stdout
    surviving = (charter_dir / "charter.yaml").read_text(encoding="utf-8")
    assert "CLI-AUTHORED-GOVERNANCE-SENTINEL" in surviving
    assert "CLI-AUTHORED-ACTIVATION-SENTINEL" in surviving
    assert "stale-mission" not in surviving, "catalog is the DERIVED section and must refresh"


def test_context_bootstrap_then_compact(tmp_path: Path, charter_cwd_isolation: Callable[..., Path]) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _git_init(repo_root)
    charter_dir = repo_root / ".kittify" / "charter"
    charter_dir.mkdir(parents=True)
    # consolidate-charter-bundle WP03: ``generate`` no longer writes
    # ``charter.md`` (Landmine 3). ``context``'s bootstrap mode still keys
    # off the legacy sync triad, which is derived from ``charter.md`` --
    # seed a curated one so the sync step this test exercises still runs.
    (charter_dir / "charter.md").write_text("# Curated Charter\n", encoding="utf-8")

    charter_cwd_isolation(repo_root)
    with patch("specify_cli.cli.commands.charter.find_repo_root") as mock_find_root:
        mock_find_root.return_value = repo_root

        generate_result = runner.invoke(app, ["generate", "--json", "--no-from-interview"])
        assert generate_result.exit_code == 0

        first = runner.invoke(app, ["context", "--action", "specify", "--json"])
        assert first.exit_code == 0
        first_payload = json.loads(first.stdout)
        assert first_payload["mode"] == "bootstrap"
        assert first_payload["first_load"] is True

        second = runner.invoke(app, ["context", "--action", "specify", "--json"])
        assert second.exit_code == 0
        second_payload = json.loads(second.stdout)
        assert second_payload["mode"] == "compact"
        assert second_payload["first_load"] is False


def test_context_compact_mode_auto_syncs_missing_extracted_artifacts(tmp_path: Path, charter_cwd_isolation: Callable[..., Path]) -> None:
    """IC-04 (#2773): the derived triad this test used to exercise
    (``governance.yaml`` / ``directives.yaml`` / ``metadata.yaml``, deleted
    then expected to auto-resync via ``ensure_charter_bundle_fresh``) is
    retired. ``charter.bundle.CANONICAL_MANIFEST.derived_files`` is now an
    empty list, so there is nothing left for the auto-sync chokepoint to
    (re)materialize -- ``governance``/``directives`` live inline in the
    hand-authored ``charter.yaml`` (``charter.activation.schemas.CharterYaml``) instead.
    This test now pins that the bootstrap -> compact transition still
    completes cleanly across repeated ``context`` calls with no derived
    triad ever appearing on disk."""
    import subprocess as _subprocess

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    # WP03: chokepoint requires a git-tracked project root (FR-003).
    _subprocess.run(["git", "init", "--quiet", str(repo_root)], check=True)
    charter_dir = repo_root / ".kittify" / "charter"
    charter_dir.mkdir(parents=True)
    # consolidate-charter-bundle WP03: ``generate`` no longer writes
    # ``charter.md`` (Landmine 3); this test exercises the legacy sync
    # triad's auto-resync, which is derived from ``charter.md`` -- seed a
    # curated one so that sync step still runs.
    (charter_dir / "charter.md").write_text("# Curated Charter\n", encoding="utf-8")

    charter_cwd_isolation(repo_root)
    with patch("specify_cli.cli.commands.charter.find_repo_root") as mock_find_root:
        mock_find_root.return_value = repo_root

        generate_result = runner.invoke(app, ["generate", "--json", "--no-from-interview"])
        assert generate_result.exit_code == 0

        first = runner.invoke(app, ["context", "--action", "plan", "--json"])
        assert first.exit_code == 0
        first_payload = json.loads(first.stdout)
        assert first_payload["mode"] == "bootstrap"

        for retired_file in ("governance.yaml", "directives.yaml", "metadata.yaml"):
            assert not (charter_dir / retired_file).exists()

        second = runner.invoke(app, ["context", "--action", "plan", "--json"])
        assert second.exit_code == 0
        second_payload = json.loads(second.stdout)
        assert second_payload["mode"] == "compact"
        assert second_payload["first_load"] is False
        for retired_file in ("governance.yaml", "directives.yaml", "metadata.yaml"):
            assert not (charter_dir / retired_file).exists()
        assert "Run 'spec-kitty charter sync'" not in second.stdout


def test_context_json_stdout_is_single_json_value_for_missing_charter(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    with patch("specify_cli.cli.commands.charter.find_repo_root") as mock_find_root:
        mock_find_root.return_value = repo_root

        result = runner.invoke(app, ["context", "--action", "specify", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["success"] is True
    assert payload["project_charter"]["present"] is False
    assert result.stdout.strip().startswith("{")
    assert result.stdout.strip().endswith("}")
    assert "WARNING" not in result.stdout
    assert "WARNING" not in result.stderr


def test_help_output() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "charter" in result.stdout.lower() or "Charter" in result.stdout
    assert "interview" in result.stdout
    assert "generate" in result.stdout
    assert "context" in result.stdout
    assert "sync" in result.stdout
    assert "status" in result.stdout


def test_sync_command_human_and_json_surfaces_do_not_contradict_3045(tmp_path: Path) -> None:
    """Regression guard for the fixed #3045 defect. ``@pytest.mark.regression``
    removed (landing fold: make the marker mean exactly one thing) now that
    this test passes as a permanent guard.

    #3045: ``charter sync`` always reports success on the human surface,
    even when the JSON surface (same repo state) reports
    ``stale_before: true`` / ``success: false``.

    ``_emit_sync_human_result``
    (``src/specify_cli/cli/commands/charter/sync.py:36-49``) unconditionally
    prints "Charter already in sync (use --force to re-extract)" whenever
    ``result.error`` is falsy -- it never branches on ``stale_before`` or
    ``synced``. ``_sync_json_payload``
    (``src/specify_cli/cli/commands/charter/sync.py:23-33``) reports
    ``success: False`` / ``stale_before: True`` for the exact same
    ``SyncResult``. The two surfaces of the SAME command, over the SAME
    result, contradict each other: one says "already in sync", the other
    says "did not sync, was stale before this call".

    The stale pin that used to defend the human-surface message as
    intentional -- ``test_sync_command_success``'s
    ``"Charter already in sync" in result.stdout`` assertion, previously
    rationalized in its own docstring as the "current, intentional
    contract" -- was REMOVED in this same commit (see that test's updated
    docstring). This test is the red-first replacement, not an addition
    alongside the old pin; the two must not be re-separated later.

    Test design, addressing three problems in an earlier draft of this test:

    1. **Single invocation, two rendered surfaces.** ``charter.activation.sync.sync()``
       is called exactly ONCE to obtain one real ``SyncResult``; both
       ``_sync_json_payload`` and ``_emit_sync_human_result`` render from
       that SAME object. An earlier draft invoked the ``sync`` CLI command
       twice against one shared ``mock_repo`` -- under a *repair*-mode fix,
       the first (``--json``) invocation would actually repair the charter,
       so the second (human) invocation would then correctly report
       "already in sync", falsely reding a fix that fully resolves #3045.
       Rendering both surfaces from one result sidesteps that ordering
       hazard entirely.
    2. **No exit-code pin.** Honest-reporter mode (the operator's stated
       preference is "loud failures with clear instructions") is expected to
       fail loudly -- non-zero exit -- when nothing was actually synced.
       Repair mode may legitimately return ``synced=True`` (and thus exit 0)
       because restoring the pre-#2773 ``sync()`` contract means a plain
       (non-``--force``) call auto-extracts whenever the charter IS stale.
       This test does not hardcode which remedy is chosen; see the
       ``payload["success"]`` branch below.
    3. **``stale_before`` is read off the payload, not hard-asserted
       ``True``.** It is a permanent constant today only because the
       staleness check targets the retired ``metadata.yaml`` (#3045 remedy
       3) -- a corrected staleness check may compute it differently.

    The substantive assertion is that the two surfaces AGREE on success vs.
    failure over the same ``SyncResult``: the human surface exits 0 iff the
    JSON surface reports ``success``. That is the remedy-agnostic form of the
    #3045 invariant and stays live under either sanctioned remedy:
    - #4679 no-op (shipped): both report inert success -- JSON ``success:
      true``, human exits 0 with the ``No-op`` line.
    - a hypothetical honest-failure / repair mode: both report the same
      outcome -- JSON ``success: false`` with the human surface exiting
      non-zero, or JSON ``success: true`` with the human surface exiting 0.

    An earlier version of this body early-returned on ``payload["success"]``
    and then asserted the human surface exited non-zero -- which encoded only
    the honest-failure remedy. The #4679 redefinition of ``success`` to
    ``result.error is None`` made that early-return fire for the no-op case,
    turning the assertion into dead code for the exact scenario this guards.
    Asserting agreement directly keeps it live.
    """
    charter_dir = tmp_path / ".kittify" / "charter"
    charter_dir.mkdir(parents=True)
    (charter_dir / "charter.md").write_text(SAMPLE_CHARTER, encoding="utf-8")

    from specify_cli.cli.commands.charter._app import console as charter_console
    from specify_cli.cli.commands.charter.sync import (
        _emit_sync_human_result,
        _sync_json_payload,
    )
    from charter.activation.sync import sync as sync_charter

    result = sync_charter(charter_dir / "charter.md", charter_dir)
    payload = _sync_json_payload(result)

    human_exit_code: int | None = None
    with charter_console.capture() as capture:
        try:
            _emit_sync_human_result(result)
        except typer.Exit as exc:
            human_exit_code = exc.exit_code
    human_text = capture.get()

    # The two surfaces must AGREE on success vs. failure: the human surface
    # exits 0 iff the JSON surface reports success. This is the #3045
    # invariant in remedy-agnostic form -- it holds for the #4679 no-op
    # (both succeed) and for any future honest-failure/repair mode (both
    # agree on the failure), and it never early-returns past the no-op
    # scenario the way the pre-#4679 ``payload["success"]`` gate did.
    human_succeeded = human_exit_code in (None, 0)
    assert human_succeeded == payload["success"], (
        "#3045: the human and JSON surfaces of `charter sync` disagree over "
        "the same SyncResult -- one reports success while the other reports "
        f"failure. human exit={human_exit_code!r} (succeeded={human_succeeded}), "
        f"json success={payload['success']!r}, stale_before={payload['stale_before']!r}. "
        f"human output: {human_text!r}, json payload: {payload!r}"
    )
