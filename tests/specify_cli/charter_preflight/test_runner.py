"""Unit tests for ``specify_cli.charter_runtime.preflight.runner`` (WP03 / FR-006..FR-008).

Test surface:

* fresh-repo path: every check fresh → ``passed=True``.
* missing-DRG path: ``synthesized_drg=missing`` → ``passed=False``,
  ``blocked_reason`` cites the synthesize command.
* dirty-worktree + ``auto_refresh=True``: no refresh runs, blocked
  reason names uncommitted artifacts.
* clean-worktree + ``auto_refresh=True``: refresh sequence runs and
  the ordered command list is captured.
* JSON serialisation (``to_dict`` / ``to_json``) is stable and matches
  the binding shape.
"""

from __future__ import annotations

import dataclasses
import json
import subprocess
from pathlib import Path

import pytest

from specify_cli.charter_runtime.preflight import (
    CharterPreflightCheck,
    CharterPreflightResult,
    run_charter_preflight,
)

pytestmark = [pytest.mark.git_repo]

from ._fixtures import (
    build_f2_legacy_bundle_no_charter_yaml,
    init_git_repo,
    make_fresh_repo,
    seed_bundle_files,
    seed_charter,
    seed_charter_yaml,
    seed_manifest,
    write_metadata,
)


# ---------------------------------------------------------------------------
# Passing path
# ---------------------------------------------------------------------------


def test_fresh_repo_passes(tmp_path: Path) -> None:
    """When charter, bundle, and synthesized DRG are all fresh, preflight passes."""
    make_fresh_repo(tmp_path)
    result = run_charter_preflight(
        tmp_path,
        auto_refresh=False,
        allow_missing_charter=True,
    )
    assert isinstance(result, CharterPreflightResult)
    assert result.passed is True
    assert result.blocked_reason is None
    assert result.auto_refresh_applied is False
    assert result.auto_refresh_actions == []
    # All three layers represented in stable order.
    assert [c.name for c in result.checks] == [
        "charter_source",
        "synced_bundle",
        "synthesized_drg",
    ]
    for check in result.checks:
        assert check.state in {"fresh", "built_in_only", "skipped"}


def test_built_in_only_passes(tmp_path: Path) -> None:
    """``built_in_only: true`` with no graph.yaml is a passing state (FR-009)."""
    init_git_repo(tmp_path)
    charter_path, metadata_path = seed_charter(tmp_path)
    write_metadata(metadata_path, charter_path)
    seed_bundle_files(tmp_path)
    # consolidate-charter-bundle WP06 (Landmine 2): charter_source/
    # synced_bundle now resolve over charter.yaml, independent of the
    # legacy charter.md/metadata.yaml pair seeded above.
    seed_charter_yaml(tmp_path)
    seed_manifest(tmp_path, built_in_only=True)
    # No graph.yaml.
    result = run_charter_preflight(tmp_path)
    assert result.passed is True
    drg = next(c for c in result.checks if c.name == "synthesized_drg")
    assert drg.state == "built_in_only"


def test_missing_charter_in_fresh_project_is_advisory_not_blocking(tmp_path: Path) -> None:
    """A never-initialized charter stack is optional and must not warn-spam callers."""
    init_git_repo(tmp_path)

    result = run_charter_preflight(
        tmp_path,
        auto_refresh=False,
        allow_missing_charter=True,
    )

    assert result.passed is True
    assert result.blocked_reason is None
    assert [c.state for c in result.checks] == ["skipped", "skipped", "skipped"]
    assert result.warnings == [
        "project charter is not initialized; run `spec-kitty charter generate` "
        "when this project is ready for charter-governed workflows"
    ]


def test_missing_charter_blocks_mutation_gates_by_default(tmp_path: Path) -> None:
    """Shared runner fails closed unless a read-only/dashboard caller opts in."""
    init_git_repo(tmp_path)

    result = run_charter_preflight(tmp_path, auto_refresh=False)

    assert result.passed is False
    assert result.blocked_reason is not None
    assert [c.state for c in result.checks] == ["missing", "missing", "missing"]


# ---------------------------------------------------------------------------
# Legacy charter.md-only bundle (T001, #3498, contracts/missing-charter-
# advisory-matrix.md)
# ---------------------------------------------------------------------------


def test_legacy_charter_bundle_is_advisory_not_blocking(tmp_path: Path) -> None:
    """A ``charter.md``-only bundle (pre-inversion, #2831's shape) is advisory.

    ``.kittify/charter/charter.md`` present, ``.kittify/charter/charter.yaml``
    absent, no synced bundle, no synthesized DRG (contract row 2 shape).
    """
    init_git_repo(tmp_path)
    seed_charter(tmp_path)  # writes charter.md only; charter.yaml stays absent.

    result = run_charter_preflight(
        tmp_path,
        auto_refresh=False,
        allow_missing_charter=True,
    )

    assert result.passed is True
    assert result.blocked_reason is None
    assert [c.state for c in result.checks] == ["skipped", "skipped", "skipped"]
    assert result.warnings != [
        "project charter is not initialized; run `spec-kitty charter generate` "
        "when this project is ready for charter-governed workflows"
    ]
    assert len(result.warnings) == 1
    assert "charter.md" in result.warnings[0]
    assert "spec-kitty charter generate --no-from-interview" in result.warnings[0]


def test_charter_md_selects_legacy_copy_after_canonical_row2_passes(tmp_path: Path) -> None:
    """Contract row 2: canonical state passes before prose selects warning copy."""
    init_git_repo(tmp_path)
    seed_charter(tmp_path)

    result = run_charter_preflight(
        tmp_path,
        auto_refresh=False,
        allow_missing_charter=True,
    )

    # Layer states are identical to the fresh-project shape...
    assert [c.state for c in result.checks] == ["skipped", "skipped", "skipped"]
    # ...but the warning must be the legacy-bundle one, not fresh-project's.
    fresh_project_warning = (
        "project charter is not initialized; run `spec-kitty charter generate` "
        "when this project is ready for charter-governed workflows"
    )
    assert fresh_project_warning not in result.warnings


def test_built_in_only_missing_stack_with_charter_md_uses_legacy_advisory(tmp_path: Path) -> None:
    """Contract row 4: built-in-only is canonically safe; prose selects legacy copy."""
    init_git_repo(tmp_path)
    seed_charter(tmp_path)
    seed_manifest(tmp_path, built_in_only=True)

    result = run_charter_preflight(
        tmp_path,
        auto_refresh=False,
        allow_missing_charter=True,
    )

    assert result.passed is True
    assert result.blocked_reason is None
    assert "charter.md" in result.warnings[0]


def test_legacy_charter_bundle_blocks_when_not_opted_in(tmp_path: Path) -> None:
    """Non-regression: mutation gates still fail closed by default (allow_missing_charter=False)."""
    init_git_repo(tmp_path)
    seed_charter(tmp_path)

    result = run_charter_preflight(tmp_path, auto_refresh=False)

    assert result.passed is False
    assert result.blocked_reason is not None
    assert [c.state for c in result.checks] == ["missing", "missing", "missing"]


def test_built_in_only_missing_stack_is_advisory_without_charter_md(tmp_path: Path) -> None:
    """A canonical built-in-only stack passes independently of prose presence."""
    init_git_repo(tmp_path)
    seed_manifest(tmp_path, built_in_only=True)  # no charter.md, no charter.yaml

    result = run_charter_preflight(
        tmp_path,
        auto_refresh=False,
        allow_missing_charter=True,
    )

    assert result.passed is True
    assert result.blocked_reason is None
    assert "not initialized" in result.warnings[0]


@pytest.mark.parametrize(
    ("synced_state", "drg_state"),
    [
        ("stale", "missing"),
        ("missing", "stale"),
        ("missing", "invalid"),
    ],
)
def test_charter_md_never_exempts_stale_or_invalid_residue(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    synced_state: str,
    drg_state: str,
) -> None:
    """C-001/FR-016: prose presence cannot turn broken canonical state into a pass."""
    from specify_cli.charter_runtime.freshness import CharterFreshness, FreshnessSubState
    from specify_cli.charter_runtime.preflight import runner as runner_mod

    init_git_repo(tmp_path)
    seed_charter(tmp_path)
    monkeypatch.setattr(
        runner_mod,
        "compute_freshness",
        lambda _root: CharterFreshness(
            charter_source=FreshnessSubState(
                state="missing",
                last_change=None,
                remediation="spec-kitty charter sync",
            ),
            synced_bundle=FreshnessSubState(
                state=synced_state,
                last_change=None,
                remediation="spec-kitty charter sync",
            ),
            synthesized_drg=FreshnessSubState(
                state=drg_state,
                last_change=None,
                remediation="spec-kitty charter synthesize",
            ),
        ),
    )

    result = runner_mod.run_charter_preflight(
        tmp_path,
        auto_refresh=False,
        allow_missing_charter=True,
    )

    assert result.passed is False
    assert result.blocked_reason is not None
    assert result.warnings == []


def test_legacy_warning_remediation_command_generates_charter_yaml(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The command emitted for a charter.md-only bundle must clear the missing source."""
    from typer.testing import CliRunner

    from specify_cli.cli.commands.charter import charter_app

    init_git_repo(tmp_path)
    seed_charter(tmp_path)
    (tmp_path / ".kittify" / "config.yaml").write_text("{}\n", encoding="utf-8")

    preflight = run_charter_preflight(
        tmp_path,
        auto_refresh=False,
        allow_missing_charter=True,
    )
    assert "`spec-kitty charter generate --no-from-interview`" in preflight.warnings[0]

    monkeypatch.chdir(tmp_path)
    generated = CliRunner().invoke(
        charter_app,
        ["generate", "--no-from-interview"],
    )

    assert generated.exit_code == 0, generated.output
    assert (tmp_path / ".kittify" / "charter" / "charter.yaml").exists()


def test_missing_charter_source_detail_costs_exactly_one_exists_call(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """NFR-001, per-consumer: THIS mission's F1/F2 detail costs one charter.md probe.

    This is the assertion that actually guards NFR-001 for the feature this
    mission adds. The integration-level test below counts every probe made
    during a whole ``run_charter_preflight`` run, so it necessarily also
    counts probes owned by *other* features (see its docstring) and cannot
    tell a regression in our code apart from an unrelated new caller
    upstream. Pinning ``_missing_charter_source_detail`` directly keeps the
    budget enforceable no matter what else main grows.
    """
    from specify_cli.charter_runtime.freshness.computer import (
        _missing_charter_source_detail,
    )

    charter_md_path = tmp_path / ".kittify" / "charter" / "charter.md"
    charter_md_path.parent.mkdir(parents=True, exist_ok=True)
    charter_md_path.write_text("# legacy prose\n", encoding="utf-8")

    real_exists = Path.exists
    call_count = 0

    def counting_exists(self: Path) -> bool:
        nonlocal call_count
        if self == charter_md_path:
            call_count += 1
        return real_exists(self)

    monkeypatch.setattr(Path, "exists", counting_exists, raising=True)

    detail = _missing_charter_source_detail(tmp_path)

    assert "charter.md" in detail, detail
    assert call_count == 1, (
        f"_missing_charter_source_detail probed charter.md {call_count} times; "
        "NFR-001 budgets exactly one."
    )


def test_legacy_bundle_detection_costs_at_most_one_probe_per_consumer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """NFR-001, integration: charter.md is probed once per legitimate consumer.

    Counts ``Path.exists()`` invocations against the exact ``charter.md``
    path during a full ``run_charter_preflight`` call.

    The budget is TWO, not one, and the second probe is not ours. Two
    independently-shipped features each legitimately probe ``charter.md``
    exactly once on this path:

    1. ``freshness.computer._missing_charter_source_detail`` -- this
       mission's F1-vs-F2 ``detail`` for the ``missing`` state (FR-005),
       pinned to exactly one probe by the per-consumer test above.
    2. ``preflight.runner._is_legacy_charter_bundle`` -- landed separately
       on main (``#3498``, same issue ``#2831``) to select advisory warning
       copy, and its own docstring likewise budgets "exactly one additional
       filesystem existence check".

    They are NOT redundant and must not be collapsed into one probe: (1)
    treats ``charter.md`` OR any of the four legacy bundle YAMLs as "you
    have a charter", while (2) is deliberately ``charter.md``-only. Feeding
    (2) from (1) would fire the legacy-bundle advisory for a project
    carrying, say, a lone ``references.yaml`` and no ``charter.md`` --
    a behaviour change to main's code, not a landing fix.

    So the ceiling is one-per-consumer. A regression that makes either
    consumer chatty still fails: this test catches a third probe appearing,
    and the per-consumer test above catches ours growing to two.
    """
    init_git_repo(tmp_path)
    seed_charter(tmp_path)

    charter_md_path = tmp_path / ".kittify" / "charter" / "charter.md"
    real_exists = Path.exists
    call_count = 0

    def counting_exists(self: Path) -> bool:
        nonlocal call_count
        if self == charter_md_path:
            call_count += 1
        return real_exists(self)

    monkeypatch.setattr(Path, "exists", counting_exists, raising=True)

    result = run_charter_preflight(
        tmp_path,
        auto_refresh=False,
        allow_missing_charter=True,
    )

    assert result.passed is True
    assert call_count <= 2, (
        f"charter.md was probed {call_count} times; NFR-001 budgets one probe "
        "per legitimate consumer and only two are sanctioned (see docstring). "
        "A third means a new caller appeared -- trace it, do not raise this."
    )


# ---------------------------------------------------------------------------
# Failure paths — no auto-refresh
# ---------------------------------------------------------------------------


def test_missing_drg_blocks_with_remediation(tmp_path: Path) -> None:
    """Missing graph + manifest absent → ``synthesized_drg=missing`` → blocked."""
    init_git_repo(tmp_path)
    charter_path, metadata_path = seed_charter(tmp_path)
    write_metadata(metadata_path, charter_path)
    seed_bundle_files(tmp_path)
    # Intentionally no manifest and no graph.

    result = run_charter_preflight(tmp_path, auto_refresh=False)

    assert result.passed is False
    assert result.auto_refresh_applied is False
    assert result.blocked_reason is not None
    assert "synthesize" in result.blocked_reason
    drg = next(c for c in result.checks if c.name == "synthesized_drg")
    assert drg.state == "missing"
    assert drg.remediation == "spec-kitty charter synthesize"


def test_invalid_charter_yaml_blocks(tmp_path: Path) -> None:
    """An unparseable ``charter.yaml`` blocks, naming the check and state.

    consolidate-charter-bundle WP06 (Landmine 2) re-pins this test: the
    retired charter.md-hash-mismatch mechanism (formerly ``"stale"``) is
    replaced by ``charter.yaml`` being present but unparseable
    (``"invalid"``) — the only non-``fresh``, non-``missing`` state
    ``charter_source`` can report post-retirement.

    WP03: ``invalid`` has no effective self-service remediation (WP02's
    exhaustive census) and is now a declared exemption (C-EFF-2) —
    ``remediation`` is ``None``, not a fabricated command.
    """
    init_git_repo(tmp_path)
    charter_path, metadata_path = seed_charter(tmp_path)
    write_metadata(metadata_path, charter_path)
    seed_bundle_files(tmp_path)
    seed_charter_yaml(tmp_path, valid=False)
    seed_manifest(tmp_path, built_in_only=True)

    result = run_charter_preflight(tmp_path)
    assert result.passed is False
    assert result.blocked_reason is not None
    assert "charter_source invalid" in result.blocked_reason
    source = next(c for c in result.checks if c.name == "charter_source")
    assert source.state == "invalid"
    assert source.remediation is None


def test_exempt_check_blocks_without_naming_a_command(tmp_path: Path) -> None:
    """WP03 (R-006 / C-EFF-2 / C-EFF-3, spec US1 Acceptance Scenario 3): a
    check with no effective self-service remediation must still be reported
    — name, state, and *why* — but the runner must not fabricate a command
    in place of the missing remediation.

    ``charter_source: invalid`` and its cascading ``synced_bundle: stale``
    are the two states WP02's exhaustive census proved unfixable by any
    write path in the codebase (every one requires ``charter.yaml`` to
    already parse). Both are declared exempt.
    """
    init_git_repo(tmp_path)
    seed_charter_yaml(tmp_path, valid=False)
    # Manifest declares built_in_only so synthesized_drg passes and does not
    # contribute its own (legitimate, non-exempt) remediation line — this
    # test isolates the two exempt checks.
    seed_manifest(tmp_path, built_in_only=True)

    result = run_charter_preflight(tmp_path, auto_refresh=False)

    assert result.passed is False
    assert result.blocked_reason is not None

    source = next(c for c in result.checks if c.name == "charter_source")
    bundle = next(c for c in result.checks if c.name == "synced_bundle")
    assert source.state == "invalid"
    assert source.remediation is None
    assert bundle.state == "stale"
    assert bundle.remediation is None

    # No fabricated instruction on either exempt line — the runner must not
    # substitute a default command (e.g. `spec-kitty charter status`) for a
    # `None` remediation.
    for line in result.blocked_reason.splitlines():
        assert "run `" not in line, f"exempt check line still names a command: {line!r}"
    assert "charter status" not in result.blocked_reason

    # Still informative — the check and its state are named, not silence.
    assert "charter_source invalid" in result.blocked_reason
    assert "synced_bundle stale" in result.blocked_reason
    assert "parse" in result.blocked_reason.lower()


# ---------------------------------------------------------------------------
# auto_refresh=True paths
# ---------------------------------------------------------------------------


def test_auto_refresh_blocked_by_dirty_worktree(tmp_path: Path) -> None:
    """FR-008 — dirty ``.kittify/charter/`` aborts auto-refresh."""
    init_git_repo(tmp_path)
    charter_path, metadata_path = seed_charter(tmp_path)
    write_metadata(metadata_path, charter_path)
    seed_bundle_files(tmp_path)
    # No manifest -> drg=missing -> not passing.

    # Add the charter directory to git (clean) then dirty it.
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "seed charter"],
        cwd=tmp_path,
        check=True,
        env={"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@x", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@x", "PATH": "/usr/bin:/bin"},
    )
    # Now dirty the charter file.
    charter_path.write_text("# Dirty edit\n", encoding="utf-8")

    result = run_charter_preflight(tmp_path, auto_refresh=True)

    assert result.passed is False
    assert result.auto_refresh_applied is False
    assert result.auto_refresh_actions == []
    assert result.blocked_reason == "uncommitted generated artifacts; commit or stash and retry"
    # And the affected file is named in a check's detail.
    sources = [c for c in result.checks if c.name in ("charter_source", "synced_bundle")]
    assert any("uncommitted:" in c.detail for c in sources)


def test_auto_refresh_clean_worktree_runs_sequence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Clean worktree + auto_refresh runs the documented command sequence in order.

    We stub ``subprocess.run`` for the spec-kitty commands so the test
    doesn't depend on a real CLI install; the git-status invocation is
    still real so we exercise the actual dirty-detection path.
    """
    init_git_repo(tmp_path)
    charter_path, metadata_path = seed_charter(tmp_path)
    write_metadata(metadata_path, charter_path)
    seed_bundle_files(tmp_path)
    # No manifest -> drg=missing -> needs refresh.

    # Commit everything so the worktree is clean.
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "seed"],
        cwd=tmp_path,
        check=True,
        env={"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@x", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@x", "PATH": "/usr/bin:/bin"},
    )

    # Stub the spec-kitty subprocesses to succeed and create the graph
    # so the post-refresh recompute observes a fresh DRG.
    real_run = subprocess.run
    seen: list[list[str]] = []

    def fake_run(cmd, **kwargs):  # type: ignore[no-untyped-def]
        # Let real git invocations through.
        if cmd[:1] == ["git"]:
            return real_run(cmd, **kwargs)
        seen.append(list(cmd))
        # When 'synthesize' is requested, materialise a graph + manifest
        # so the post-recompute sees a fresh DRG.
        if cmd[:3] == ["spec-kitty", "charter", "synthesize"]:
            seed_manifest(tmp_path, built_in_only=False)
            (tmp_path / ".kittify" / "charter-packs" / "graph.yaml").parent.mkdir(parents=True, exist_ok=True)
            (tmp_path / ".kittify" / "charter-packs" / "graph.yaml").write_text(
                "schema_version: '1.0'\nnodes: []\nedges: []\n", encoding="utf-8",
            )
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = run_charter_preflight(tmp_path, auto_refresh=True)

    # This fixture (charter.md + the four legacy governance/directives/
    # metadata/references files, no charter.yaml) is genuinely the F2
    # shape: charter_source/synced_bundle both read `missing` with
    # `remediation="spec-kitty upgrade --yes"` (H3, #2831 — a real legacy
    # bundle folds forward via `upgrade --yes`, never the F1-only `charter
    # generate --no-from-interview`). H1 (#2831): step one now runs THAT
    # command, never a hardcoded `charter sync` (a pure staleness reporter
    # that can never create `charter.yaml` — the very defect this fixture
    # used to mask, since the stub below always returns exit 0 regardless
    # of which command is asked for). synthesize then runs (drg missing),
    # then validate.
    assert result.auto_refresh_applied is True
    spec_kitty_calls = [c for c in seen if c[0] == "spec-kitty"]
    # Must include synthesize (drg missing) and bundle validate (always).
    cmds_as_strs = [" ".join(c) for c in spec_kitty_calls]
    assert "spec-kitty upgrade --yes" in cmds_as_strs
    assert "spec-kitty charter synthesize" in cmds_as_strs
    assert "spec-kitty charter bundle validate" in cmds_as_strs
    # And the result captured the runner's own tracked action sequence in
    # order: upgrade --yes, synthesize, bundle validate, then a WP06
    # re-stamp `synthesize` (#2777, MAJOR-1 rejection cycle 1) — the
    # references-parity heal's targeted `generate` rewrites charter.yaml's
    # derived catalog but never re-stamps the synthesis manifest's
    # bundle_content_hash itself, so the boundary re-runs the same flagless
    # `synthesize` once more to keep the post-refresh freshness recompute
    # manifest-coherent. That targeted `generate` call is a real executed
    # subprocess (visible above via `cmds_as_strs`, which observes every
    # "spec-kitty" call) but is issued by
    # `references_refresh.refresh_references_if_needed` — a background
    # extension-point side effect, not one of the primary steps
    # `_attempt_auto_refresh` itself tracks — so it is intentionally absent
    # from `auto_refresh_actions`.
    assert "spec-kitty charter generate --no-from-interview --json" in cmds_as_strs
    assert result.auto_refresh_actions == [
        "spec-kitty upgrade --yes",
        "spec-kitty charter synthesize",
        "spec-kitty charter bundle validate",
        "spec-kitty charter synthesize",
    ]


def test_auto_refresh_real_cli_from_f2_non_fresh_state_repairs_charter_source(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    isolated_env: dict[str, str],
) -> None:
    """H1 (#2831 HIGH finding), end-to-end proof against THIS checkout's real
    command implementations — not a stub that always returns exit 0.

    The reviewer's own repro: a real F2 legacy-bundle project (realistic
    scaffolding, per ``build_f2_legacy_bundle_no_charter_yaml``'s
    ``seed_realistic_agent_scaffolding``, so ``upgrade --yes`` does not halt
    on the unrelated ``0.10.1_populate_slash_commands`` precondition — see
    the mission's own review-cycle-1 finding) with ``auto_refresh=True``.
    Before H1, step one unconditionally ran ``spec-kitty charter sync`` — a
    pure staleness reporter that can never create ``charter.yaml`` — so this
    exact non-fresh starting state ran only ``sync``, exited 1, and left
    every state unchanged. Every existing auto-refresh test either started
    from already-fresh state or stubbed every ``spec-kitty`` subprocess call
    to unconditionally succeed regardless of which command was asked for —
    both shapes hide this exact defect (module docstring, H1). This test
    starts from NON-fresh (F2 ``missing``) and runs the real CLI.

    ``subprocess.run`` is monkeypatched only to route the runner's
    ``["spec-kitty", ...]`` argv through THIS checkout's own venv + source
    tree (mirrors ``tests.conftest.run_cli``'s ``isolated_env``/
    ``get_venv_python`` mechanism) instead of whatever ``spec-kitty``
    happens to resolve to on ``$PATH`` — which may be a stale global install
    of a different checkout (CLAUDE.md's "stale-install false reds"). Every
    command's actual implementation still runs for real; nothing about its
    behaviour is faked.

    Scope note: this asserts ``charter_source``/``synced_bundle`` genuinely
    reach ``fresh`` (H1's exact claim), NOT ``result.passed`` for the whole
    sequence. Running this real end-to-end uncovered a SEPARATE, pre-existing
    defect in ``spec-kitty charter bundle validate`` (unit 3 of the sequence,
    untouched by any of H1/H3/H5): its "Tracked files" table reports
    ``.kittify/charter/charter.yaml`` as ``[MISSING]`` even immediately after
    a real ``upgrade --yes`` that provably wrote it (confirmed by hand:
    ``ls -la .kittify/charter/`` shows the file; ``compute_freshness`` agrees
    it is ``fresh``) — it appears to still check the pre-consolidation
    v1.0.0 manifest shape (``charter.bundle``'s own docstring: "v1.0.0 scope
    is limited to the three sync-produced derivatives"), never updated for
    the charter.yaml-based bundle inversion. That defect is outside this
    mission's five HIGH findings (H1-H5) and is not fixed here; recompute
    freshness directly below rather than trusting ``result.checks``, which
    ``_attempt_auto_refresh`` returns pre-refresh/stale on ANY later-step
    failure (a separate, pre-existing return-shape property, also not part
    of H1's scope).
    """
    from specify_cli.charter_runtime.preflight import runner as runner_module
    from tests.test_isolation_helpers import get_venv_python

    build_f2_legacy_bundle_no_charter_yaml(tmp_path)

    # Commit the seeded legacy bundle so the worktree is clean (FR-008) --
    # same requirement the stubbed sibling test above satisfies.
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "seed F2 legacy bundle"],
        cwd=tmp_path,
        check=True,
        env={
            "GIT_AUTHOR_NAME": "t",
            "GIT_AUTHOR_EMAIL": "t@x",
            "GIT_COMMITTER_NAME": "t",
            "GIT_COMMITTER_EMAIL": "t@x",
            "PATH": "/usr/bin:/bin",
        },
    )

    real_run = subprocess.run
    venv_python = str(get_venv_python())

    def real_cli_run(cmd, **kwargs):  # type: ignore[no-untyped-def]
        if cmd[:1] != ["spec-kitty"]:
            return real_run(cmd, **kwargs)
        translated = [venv_python, "-m", "specify_cli.__init__", *cmd[1:]]
        kwargs["env"] = isolated_env
        return real_run(translated, **kwargs)

    monkeypatch.setattr(runner_module.subprocess, "run", real_cli_run)

    result = run_charter_preflight(tmp_path, auto_refresh=True)

    assert result.auto_refresh_applied is True
    assert result.auto_refresh_actions, "expected at least one real refresh command to run"
    assert result.auto_refresh_actions[0] == "spec-kitty upgrade --yes", (
        "H1 fix: step one must be the freshness-computed F2 remediation, never "
        f"a hardcoded `charter sync`; got {result.auto_refresh_actions!r}"
    )
    assert "spec-kitty charter sync" not in result.auto_refresh_actions

    charter_yaml_path = tmp_path / ".kittify" / "charter" / "charter.yaml"
    assert charter_yaml_path.exists(), (
        "the real `spec-kitty upgrade --yes` must have created charter.yaml -- "
        f"auto_refresh_actions={result.auto_refresh_actions!r} "
        f"blocked_reason={result.blocked_reason!r}"
    )

    # Recompute directly rather than trusting `result.checks` -- see the
    # docstring's scope note on why a later-step failure returns stale
    # pre-refresh checks.
    from specify_cli.charter_runtime.freshness import compute_freshness

    post_freshness = compute_freshness(tmp_path)
    assert post_freshness.charter_source.state == "fresh", (
        "H1: the real F2 remediation must genuinely clear charter_source -- "
        f"got {post_freshness.charter_source!r}"
    )
    assert post_freshness.synced_bundle.state == "fresh", (
        f"H1: synced_bundle must clear alongside charter_source -- got {post_freshness.synced_bundle!r}"
    )


def test_auto_refresh_failure_captures_blocked_reason(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """If a refresh subprocess exits non-zero, runner stops and reports."""
    init_git_repo(tmp_path)
    charter_path, metadata_path = seed_charter(tmp_path)
    write_metadata(metadata_path, charter_path)
    seed_bundle_files(tmp_path)
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "seed"],
        cwd=tmp_path,
        check=True,
        env={"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@x", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@x", "PATH": "/usr/bin:/bin"},
    )

    real_run = subprocess.run

    def fake_run(cmd, **kwargs):  # type: ignore[no-untyped-def]
        if cmd[:1] == ["git"]:
            return real_run(cmd, **kwargs)
        return subprocess.CompletedProcess(args=cmd, returncode=1, stdout="", stderr="boom failure\n")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = run_charter_preflight(tmp_path, auto_refresh=True)
    assert result.passed is False
    assert result.auto_refresh_applied is True
    assert result.blocked_reason is not None
    assert "boom failure" in result.blocked_reason


# ---------------------------------------------------------------------------
# JSON serialisation
# ---------------------------------------------------------------------------


def test_to_dict_and_to_json_shape(tmp_path: Path) -> None:
    """The serialised result matches the binding contract shape."""
    make_fresh_repo(tmp_path)
    result = run_charter_preflight(tmp_path)
    as_dict = result.to_dict()
    assert set(as_dict.keys()) == {
        "passed",
        "checks",
        "auto_refresh_applied",
        "auto_refresh_actions",
        "blocked_reason",
    }
    assert isinstance(as_dict["checks"], list)
    assert all({"name", "state", "detail", "remediation"} <= set(c.keys()) for c in as_dict["checks"])

    # to_json round-trips.
    parsed = json.loads(result.to_json())
    assert parsed == as_dict


def test_to_dict_includes_warnings_only_when_present(tmp_path: Path) -> None:
    """The advisory field is additive only when callers need it."""
    init_git_repo(tmp_path)
    result = run_charter_preflight(
        tmp_path,
        auto_refresh=False,
        allow_missing_charter=True,
    )

    as_dict = result.to_dict()

    assert as_dict["warnings"] == [
        "project charter is not initialized; run `spec-kitty charter generate` "
        "when this project is ready for charter-governed workflows"
    ]


def test_check_dataclass_is_frozen() -> None:
    """``CharterPreflightCheck`` must be frozen (no accidental mutation)."""
    c = CharterPreflightCheck(name="x", state="fresh", detail="d", remediation=None)
    with pytest.raises(dataclasses.FrozenInstanceError):
        c.detail = "y"  # type: ignore[misc]


def test_result_dataclass_is_frozen() -> None:
    """``CharterPreflightResult`` must be frozen."""
    r = CharterPreflightResult(passed=True)
    with pytest.raises(dataclasses.FrozenInstanceError):
        r.passed = False  # type: ignore[misc]
