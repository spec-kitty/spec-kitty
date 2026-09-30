"""References-parity auto-refresh completion (#2777, FR-011, NFR-006, WP06).

Covers ``preflight.references_refresh`` — WP06's implementation of the
extension point WP04 installed at ``preflight.runner.refresh_references_if_needed``
(see ``test_boundary_heal.py``'s T019 section for the call-site wiring pin).

* ``test_references_parity_drift_recompiles_the_catalog``: end to end
  against the REAL ``charter generate`` code path (``compile_charter`` +
  ``write_compiled_charter``, invoked in-process through
  ``typer.testing.CliRunner`` rather than a hand-faked stand-in) — a
  references-parity cause recompiles ``charter.yaml``'s ``catalog.references``
  back to the current, real doctrine-derived content, and leaves a curated
  ``charter.md`` byte-for-byte unchanged (NFR-006 / #2772).
* ``test_non_references_parity_cause_is_a_true_noop``: the "never
  unconditionally" gate (T024) — a cause that does not name
  ``synthesized_drg`` never spawns ``generate`` and never touches the
  filesystem.
* ``test_is_references_parity_cause_*``: direct unit coverage of the pure
  gating predicate across the reachable cause-set combinations (see
  ``references_refresh``'s module docstring for why a bare ``built_in_only``
  project reaches a stale-without-``synthesized_drg`` cause set).
* ``test_auto_refresh_reports_failure_when_generate_fails`` (T019, WP04
  auto-refresh swallow fold-in, #5257): pins the pre-existing swallow bug at
  ``preflight.runner._attempt_auto_refresh``'s references-parity extension
  point -- a non-zero targeted ``generate`` exit must reach the boundary
  heal's ``passed``/``blocked_reason`` contract, never be logged-and-
  swallowed behind an unconditional manifest re-stamp.
"""

from __future__ import annotations

import contextlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from ruamel.yaml import YAML
from typer.testing import CliRunner

from specify_cli.charter_runtime.freshness import CharterFreshness, FreshnessSubState
from specify_cli.charter_runtime.preflight import references_refresh
from specify_cli.charter_runtime.preflight import runner as runner_module
from specify_cli.charter_runtime.preflight.result import CharterPreflightCheck
from specify_cli.cli.commands.charter import app as charter_app

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]

_runner = CliRunner()

_CURATED_CHARTER_MD = "# Curated Charter\n\nHand-authored governance prose.\n"

#: Mirrors ``_GENERATE_CMD_PREFIX`` -- kept as an
#: independent literal (not a reach into the module's private attribute) so
#: this test asserts on the OBSERVABLE argv shape, not an implementation
#: detail.
_GENERATE_CMD_PREFIX: tuple[str, ...] = ("spec-kitty", "charter", "generate")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _git_init(repo: Path) -> None:
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=repo, check=True)
    subprocess.run(["git", "config", "commit.gpgsign", "false"], cwd=repo, check=True)


def _write_curated_charter_md(repo: Path) -> Path:
    """Seed a hand-authored ``charter.md`` -- ``generate`` must never write it
    (data-model.md Landmine 3 / #2772)."""
    charter_dir = repo / ".kittify" / "charter"
    charter_dir.mkdir(parents=True, exist_ok=True)
    path = charter_dir / "charter.md"
    path.write_text(_CURATED_CHARTER_MD, encoding="utf-8")
    return path


def _invoke_generate_in_process(repo: Path, argv: list[str]) -> subprocess.CompletedProcess[str]:
    """Run the REAL ``generate`` Typer command in-process via ``CliRunner``.

    ``find_repo_root()`` resolves from ``os.getcwd()`` (see
    ``test_charter_generate_autotrack.py``'s established convention), so the
    process cwd is switched to *repo* for the duration of the call and
    restored afterwards.
    """
    with contextlib.chdir(repo):
        result = _runner.invoke(charter_app, argv, catch_exceptions=False)
    return subprocess.CompletedProcess(
        args=["spec-kitty", "charter", *argv],
        returncode=result.exit_code,
        stdout=result.stdout,
        stderr="",
    )


def _make_generate_subprocess_fake(repo: Path, seen_calls: list[list[str]]) -> Any:
    """Fake ``subprocess.run`` that lets real ``git`` calls through and routes
    ``spec-kitty charter generate`` to the real command in-process (no real
    OS subprocess spawned, matching the ``test_boundary_heal.py`` convention
    for ``spec-kitty charter synthesize``)."""
    real_run = subprocess.run

    def fake_run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        if cmd[:1] == ["git"]:
            return real_run(cmd, **kwargs)
        seen_calls.append(list(cmd))
        if tuple(cmd[:3]) == _GENERATE_CMD_PREFIX:
            return _invoke_generate_in_process(repo, cmd[2:])
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    return fake_run


def _load_yaml(path: Path) -> dict[str, Any]:
    yaml = YAML(typ="safe")
    data = yaml.load(path.read_text(encoding="utf-8"))
    return dict(data) if data else {}


def _dump_yaml(path: Path, data: dict[str, Any]) -> None:
    yaml = YAML(typ="safe")
    with path.open("w", encoding="utf-8") as handle:
        yaml.dump(data, handle)


def _seed_baseline_repo(repo: Path, seen_calls: list[list[str]]) -> Path:
    """Real git repo + curated charter.md + a real, freshly-generated
    charter.yaml (via the in-process fake, so the baseline itself already
    exercises the exact same code path the hook under test will use).

    Returns the ``charter.yaml`` path.
    """
    _git_init(repo)
    _write_curated_charter_md(repo)

    fake = _make_generate_subprocess_fake(repo, seen_calls)
    result = fake(["spec-kitty", "charter", "generate", "--no-from-interview"])
    assert result.returncode == 0, f"baseline generate failed: {result.stdout!r}"
    seen_calls.clear()  # baseline call doesn't count toward the assertions below

    charter_yaml_path = repo / ".kittify" / "charter" / "charter.yaml"
    assert charter_yaml_path.exists()
    return charter_yaml_path


# ---------------------------------------------------------------------------
# End-to-end: references-parity drift recompiles the catalog, honors #2772
# ---------------------------------------------------------------------------


def test_references_parity_drift_recompiles_the_catalog(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    seen_calls: list[list[str]] = []
    charter_yaml_path = _seed_baseline_repo(tmp_path, seen_calls)
    charter_md_path = tmp_path / ".kittify" / "charter" / "charter.md"

    baseline = _load_yaml(charter_yaml_path)
    baseline_references = baseline["catalog"]["references"]
    assert baseline_references, "fixture sanity: baseline generate produced no references"

    # Simulate references-parity drift: truncate the compiled catalog's
    # references so it no longer reflects current activation.
    drifted = _load_yaml(charter_yaml_path)
    drifted["catalog"]["references"] = []
    _dump_yaml(charter_yaml_path, drifted)
    assert _load_yaml(charter_yaml_path)["catalog"]["references"] == []

    charter_md_before = charter_md_path.read_bytes()

    monkeypatch.setattr(subprocess, "run", _make_generate_subprocess_fake(tmp_path, seen_calls))

    outcome = references_refresh.refresh_references_if_needed(tmp_path, cause="synthesized_drg")

    assert outcome.attempted is True
    assert outcome.succeeded is True
    assert outcome.detail is None
    assert any(tuple(c[:3]) == _GENERATE_CMD_PREFIX for c in seen_calls), seen_calls

    healed = _load_yaml(charter_yaml_path)
    healed_references = healed["catalog"]["references"]
    # Compare by activated-id SET, not full deep equality: a pre-existing,
    # WP06-unrelated quirk in `compile_charter`'s language-scoped doctrine
    # lookup (repro'd directly against plain `spec-kitty charter generate
    # --no-from-interview` run twice against the same repo, with no
    # references_refresh code involved at all) degrades a handful of
    # python/typescript-specific styleguide/toolguide `title`/`summary`
    # strings to a "Definition unavailable in bundled doctrine" placeholder
    # on a SECOND generate call -- `id`/`kind`/`source_path`/`local_path`
    # stay stable. The id-set comparison is what AS3 actually requires
    # ("content reflects current activation" -- i.e. the SAME activated set
    # is recompiled, not left as the injected empty/truncated drift) without
    # coupling this test to that separate, out-of-scope defect.
    assert {ref["id"] for ref in healed_references} == {ref["id"] for ref in baseline_references}, (
        "references-parity refresh must recompile the catalog back to current activation, not leave the drifted/truncated content"
    )
    assert len(healed_references) == len(baseline_references)

    charter_md_after = charter_md_path.read_bytes()
    assert charter_md_after == charter_md_before, "NFR-006: curated charter.md must be 0 bytes changed by the refresh"


def test_references_parity_drift_recompiles_using_the_existing_mission_and_template_set(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The targeted refresh must not silently reset a non-default mission
    type / template set to ``generate``'s hardcoded ``software-dev``
    fallback -- it reads the existing ``catalog.mission``/``template_set``
    and threads them through explicitly."""
    seen_calls: list[list[str]] = []
    charter_yaml_path = _seed_baseline_repo(tmp_path, seen_calls)

    baseline = _load_yaml(charter_yaml_path)
    assert baseline["catalog"]["mission"] == "software-dev"
    assert baseline["catalog"]["template_set"]

    monkeypatch.setattr(subprocess, "run", _make_generate_subprocess_fake(tmp_path, seen_calls))
    references_refresh.refresh_references_if_needed(tmp_path, cause="synthesized_drg")

    generate_call = next(c for c in seen_calls if tuple(c[:3]) == _GENERATE_CMD_PREFIX)
    assert "--mission-type" in generate_call
    assert generate_call[generate_call.index("--mission-type") + 1] == "software-dev"
    assert "--template-set" in generate_call
    assert generate_call[generate_call.index("--template-set") + 1] == baseline["catalog"]["template_set"]


# ---------------------------------------------------------------------------
# Gating -- "never unconditionally" (T024)
# ---------------------------------------------------------------------------


def test_non_references_parity_cause_is_a_true_noop(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    seen_calls: list[list[str]] = []
    charter_yaml_path = _seed_baseline_repo(tmp_path, seen_calls)

    # Same drift simulation as the positive test -- if this cause spuriously
    # triggered `generate`, the drifted marker would disappear.
    drifted = _load_yaml(charter_yaml_path)
    drifted["catalog"]["references"] = []
    _dump_yaml(charter_yaml_path, drifted)

    monkeypatch.setattr(subprocess, "run", _make_generate_subprocess_fake(tmp_path, seen_calls))

    outcome = references_refresh.refresh_references_if_needed(tmp_path, cause="charter_source,synced_bundle")

    assert outcome.attempted is False
    assert outcome.succeeded is False
    assert outcome.detail is None
    assert seen_calls == [], "a non-references-parity cause must never invoke generate"
    assert _load_yaml(charter_yaml_path)["catalog"]["references"] == [], "no-op must leave the drifted content exactly as-is"


# ---------------------------------------------------------------------------
# Unit coverage: the pure gating predicate
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("cause", "expected"),
    [
        ("synthesized_drg", True),
        ("charter_source,synced_bundle,synthesized_drg", True),
        ("charter_source,synced_bundle", False),
        ("charter_source", False),
        ("", False),
    ],
)
def test_is_references_parity_cause(cause: str, expected: bool) -> None:
    assert references_refresh.is_references_parity_cause(cause) is expected


def test_references_parity_cause_name_is_a_runner_layer() -> None:
    """The references-parity cause name must be a real runner layer name.

    ``references_refresh._REFERENCES_PARITY_CAUSE_NAME`` is sourced from
    ``preflight.runner.SYNTHESIZED_DRG_LAYER`` rather than re-declared as its
    own literal (see the module docstring's mapping note and this fold's
    single-source refactor). This is the binding test that makes a future
    rename of the layer name fail loudly instead of silently no-op'ing the
    references-parity heal: assert the cause name is a member of the
    runner's own ``_LAYER_ORDER`` layer-key set, not just equal to a
    hardcoded string.
    """
    from specify_cli.charter_runtime.preflight import runner as runner_module

    layer_keys = {key for key, _label in runner_module._LAYER_ORDER}
    assert references_refresh._REFERENCES_PARITY_CAUSE_NAME in layer_keys
    assert references_refresh._REFERENCES_PARITY_CAUSE_NAME == runner_module.SYNTHESIZED_DRG_LAYER


# ---------------------------------------------------------------------------
# T010 -- shared ``catalog.mission``/``catalog.template_set`` accessor parity
# (Finding B, #4993)
# ---------------------------------------------------------------------------


def test_read_catalog_mission_and_template_set_matches_shared_accessor(
    tmp_path: Path,
) -> None:
    """AC-B1: this module's ``catalog.mission``/``catalog.template_set``
    reader must resolve the identical value the shared accessor
    (``charter.activation.charter_yaml_io.read_catalog_field``, Finding B /
    #4993) returns directly for the same repo -- both now read through the
    one canonical parser rather than this module's former ad-hoc
    ``YAML(typ="safe")`` read."""
    from charter.activation.charter_yaml_io import read_catalog_field

    seen_calls: list[list[str]] = []
    _seed_baseline_repo(tmp_path, seen_calls)

    mission, template_set = references_refresh._read_catalog_mission_and_template_set(tmp_path)

    assert mission == read_catalog_field(tmp_path, "mission") == "software-dev"
    assert template_set == read_catalog_field(tmp_path, "template_set")
    assert template_set is not None


def test_read_catalog_mission_and_template_set_absent_charter_yaml(tmp_path: Path) -> None:
    """AC-B2: an absent ``charter.yaml`` yields the same absent
    ``(None, None)`` result as before the refactor."""
    assert references_refresh._read_catalog_mission_and_template_set(tmp_path) == (None, None)


# ---------------------------------------------------------------------------
# T019 -- auto-refresh swallow fold-in (WP04, #5257): a non-zero targeted
# `generate` exit inside `_attempt_auto_refresh`'s references-parity
# extension point must reach the boundary heal's `passed`/`blocked_reason`
# contract, never be logged-and-swallowed behind an unconditional manifest
# re-stamp.
# ---------------------------------------------------------------------------


def _make_generate_failure_subprocess_fake(seen_calls: list[list[str]], *, failure_detail: str) -> Any:
    """Like :func:`_make_generate_subprocess_fake`, but the faked
    ``spec-kitty charter generate`` invocation exits non-zero instead of
    routing to the real in-process command -- for pinning T019 (the WP04
    auto-refresh swallow fold-in). Every OTHER ``spec-kitty charter``
    subcommand still no-ops successfully (returncode 0), isolating the
    assertion to the generate-failure branch alone.
    """
    real_run = subprocess.run

    def fake_run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        if cmd[:1] == ["git"]:
            return real_run(cmd, **kwargs)
        seen_calls.append(list(cmd))
        if tuple(cmd[:3]) == _GENERATE_CMD_PREFIX:
            return subprocess.CompletedProcess(args=cmd, returncode=1, stdout="", stderr=f"{failure_detail}\n")
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    return fake_run


def test_auto_refresh_reports_failure_when_generate_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Pins the pre-existing swallow bug at ``_attempt_auto_refresh``'s
    references-parity extension point (``runner.py`` ~line 733): today,
    ``refresh_references_if_needed`` never inspects the targeted `generate`
    subprocess's ``CompletedProcess`` and unconditionally reports success,
    so a genuine failure there is masked behind an unconditional manifest
    re-stamp instead of reaching ``passed=False``/``blocked_reason``.

    RED (pre-fix, verified against
    ``af847be71d97c8a126e91c31a7d05629c69c93ba``): the swallow means
    ``passed`` reports ``True`` despite the underlying ``generate``
    failure. The post-refresh freshness recompute (faked below to report a
    fully coherent repo, isolating the assertion from real doctrine-fixture
    setup) simply re-observes "everything is fine" and reports success --
    exactly the masking mechanism this fold-in removes (the WP's own
    description: "the recompute afterward sees synthesized_drg='fresh'
    even though generate FAILED to actually reconcile anything").

    GREEN (post T017+T018): ``passed=False`` and ``blocked_reason`` names
    the failure detail; the manifest restamp (a second ``synthesize`` call
    after the failed ``generate``) never runs, and the freshness recompute
    is never even reached.
    """
    _git_init(tmp_path)

    seen_calls: list[list[str]] = []
    failure_detail = "generate: doctrine pack root misconfigured (fixture-induced failure)"
    monkeypatch.setattr(
        subprocess,
        "run",
        _make_generate_failure_subprocess_fake(seen_calls, failure_detail=failure_detail),
    )

    # Isolate the assertion from real freshness computation: the
    # post-refresh recompute (``runner.compute_freshness``) reads real
    # repo files, which this fixture never populates. Faking it to report
    # a fully coherent repo means the ONLY thing that can make `passed`
    # False is `_attempt_auto_refresh` itself reaching the fail-closed
    # branch this fold-in adds -- not an unrelated missing-DRG artifact.
    all_fresh = FreshnessSubState(state="fresh", last_change=None, remediation=None)
    monkeypatch.setattr(
        runner_module,
        "compute_freshness",
        lambda _repo_root: CharterFreshness(charter_source=all_fresh, synced_bundle=all_fresh, synthesized_drg=all_fresh),
    )

    fresh = FreshnessSubState(state="fresh", last_change=None, remediation=None)
    stale_drg = FreshnessSubState(
        state="stale",
        last_change=None,
        remediation="spec-kitty charter synthesize",
    )
    freshness = CharterFreshness(charter_source=fresh, synced_bundle=fresh, synthesized_drg=stale_drg)
    initial_checks = [
        CharterPreflightCheck(name="charter_source", state="fresh", detail="ok", remediation=None),
        CharterPreflightCheck(name="synced_bundle", state="fresh", detail="ok", remediation=None),
        CharterPreflightCheck(
            name="synthesized_drg",
            state="stale",
            detail="synthesized DRG is stale",
            remediation="spec-kitty charter synthesize",
        ),
    ]

    result = runner_module._attempt_auto_refresh(tmp_path, freshness, initial_checks)

    assert any(tuple(c[:3]) == _GENERATE_CMD_PREFIX for c in seen_calls), f"fixture sanity: the targeted generate must actually be invoked; saw {seen_calls!r}"
    assert result.auto_refresh_applied is True
    assert result.passed is False, "a failed targeted `generate` must not let the boundary heal report success -- the swallow bug lets `passed` report True here"
    assert result.blocked_reason is not None
    assert failure_detail in result.blocked_reason, result.blocked_reason

    synthesize_calls = [c for c in seen_calls if tuple(c[:3]) == ("spec-kitty", "charter", "synthesize")]
    assert len(synthesize_calls) == 1, (
        "the manifest restamp must be skipped when the targeted generate "
        "failed -- restamping over unregenerated content is exactly the "
        f"masking bug being fixed; saw {synthesize_calls!r}"
    )


# ---------------------------------------------------------------------------
# WP04 rejection-cycle-2 fold-in (#5257, wp-WP04.yaml WP04-C1-002): the
# `except (OSError, subprocess.TimeoutExpired)` branch inside
# `references_refresh.refresh_references_if_needed` (~lines 247-257) --
# reached when the targeted `generate` subprocess cannot even be
# spawned/completed, not merely exits non-zero -- had zero test coverage.
# These tests pin BOTH exception types at the unit level (the outcome
# `refresh_references_if_needed` itself returns) and at the integration
# level (that the failure still reaches `_attempt_auto_refresh`'s
# `passed=False`/`blocked_reason` contract, the same way a non-zero exit
# already does above).
# ---------------------------------------------------------------------------


def _make_generate_invocation_error_subprocess_fake(seen_calls: list[list[str]], *, error: OSError | subprocess.TimeoutExpired) -> Any:
    """Like :func:`_make_generate_failure_subprocess_fake`, but the faked
    ``spec-kitty charter generate`` invocation never returns a
    ``CompletedProcess`` at all -- it raises *error* instead, pinning the
    ``except (OSError, subprocess.TimeoutExpired)`` branch
    (``references_refresh.py`` ~247-257) rather than the non-zero-exit
    branch :func:`_make_generate_failure_subprocess_fake` pins. Every other
    ``spec-kitty charter`` subcommand still no-ops successfully.
    """
    real_run = subprocess.run

    def fake_run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        if cmd[:1] == ["git"]:
            return real_run(cmd, **kwargs)
        seen_calls.append(list(cmd))
        if tuple(cmd[:3]) == _GENERATE_CMD_PREFIX:
            raise error
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    return fake_run


def _invocation_error_cases() -> list[Any]:
    """The two exception types `refresh_references_if_needed` must convert
    into a failed `ReferencesRefreshOutcome` instead of propagating (mirrors the
    module's own ``except (OSError, subprocess.TimeoutExpired)`` tuple)."""
    return [
        pytest.param(OSError("no such file or directory"), id="oserror"),
        pytest.param(
            subprocess.TimeoutExpired(cmd=list(_GENERATE_CMD_PREFIX), timeout=30.0),
            id="timeout_expired",
        ),
    ]


@pytest.mark.parametrize("error", _invocation_error_cases())
def test_generate_invocation_error_yields_failed_outcome(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, error: OSError | subprocess.TimeoutExpired) -> None:
    """Unit-level pin for WP04-C1-002: when the targeted `generate`
    subprocess cannot even complete -- `subprocess.run` itself raises
    *error* -- `refresh_references_if_needed` must report
    `attempted=True, succeeded=False` with a non-empty, informative
    `detail`, never propagate the exception and never report success.
    """
    _git_init(tmp_path)
    seen_calls: list[list[str]] = []
    monkeypatch.setattr(
        subprocess,
        "run",
        _make_generate_invocation_error_subprocess_fake(seen_calls, error=error),
    )

    outcome = references_refresh.refresh_references_if_needed(tmp_path, cause="synthesized_drg")

    assert any(tuple(c[:3]) == _GENERATE_CMD_PREFIX for c in seen_calls), seen_calls
    assert outcome.attempted is True
    assert outcome.succeeded is False
    assert outcome.detail, "the invocation-error branch must not report an empty detail"
    assert "invocation failed" in outcome.detail
    assert str(error) in outcome.detail, f"detail must name the exception that was actually raised; got {outcome.detail!r}"


@pytest.mark.parametrize("error", _invocation_error_cases())
def test_auto_refresh_reports_failure_when_generate_invocation_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, error: OSError | subprocess.TimeoutExpired
) -> None:
    """Integration-level pin for WP04-C1-002: an invocation-level failure
    (``subprocess.run`` raising, not merely exiting non-zero) must reach
    `_attempt_auto_refresh`'s `passed=False`/`blocked_reason` contract the
    same way `test_auto_refresh_reports_failure_when_generate_fails` pins
    for a non-zero exit -- and the manifest restamp must still be skipped.
    """
    _git_init(tmp_path)
    seen_calls: list[list[str]] = []
    monkeypatch.setattr(
        subprocess,
        "run",
        _make_generate_invocation_error_subprocess_fake(seen_calls, error=error),
    )

    all_fresh = FreshnessSubState(state="fresh", last_change=None, remediation=None)
    monkeypatch.setattr(
        runner_module,
        "compute_freshness",
        lambda _repo_root: CharterFreshness(charter_source=all_fresh, synced_bundle=all_fresh, synthesized_drg=all_fresh),
    )

    fresh = FreshnessSubState(state="fresh", last_change=None, remediation=None)
    stale_drg = FreshnessSubState(
        state="stale",
        last_change=None,
        remediation="spec-kitty charter synthesize",
    )
    freshness = CharterFreshness(charter_source=fresh, synced_bundle=fresh, synthesized_drg=stale_drg)
    initial_checks = [
        CharterPreflightCheck(name="charter_source", state="fresh", detail="ok", remediation=None),
        CharterPreflightCheck(name="synced_bundle", state="fresh", detail="ok", remediation=None),
        CharterPreflightCheck(
            name="synthesized_drg",
            state="stale",
            detail="synthesized DRG is stale",
            remediation="spec-kitty charter synthesize",
        ),
    ]

    result = runner_module._attempt_auto_refresh(tmp_path, freshness, initial_checks)

    assert any(tuple(c[:3]) == _GENERATE_CMD_PREFIX for c in seen_calls), seen_calls
    assert result.auto_refresh_applied is True
    assert result.passed is False, (
        "an invocation-level generate failure must not let the boundary heal report success -- it must fail closed exactly like a non-zero exit"
    )
    assert result.blocked_reason is not None
    assert "invocation failed" in result.blocked_reason
    assert str(error) in result.blocked_reason, result.blocked_reason

    synthesize_calls = [c for c in seen_calls if tuple(c[:3]) == ("spec-kitty", "charter", "synthesize")]
    assert len(synthesize_calls) == 1, f"the manifest restamp must be skipped when the targeted generate invocation itself failed; saw {synthesize_calls!r}"


# ---------------------------------------------------------------------------
# PR-TESTS-003 (#5257 pre-merge squad): direct unit coverage for the two
# `_extract_failure_detail` branches every failure-path fixture above leaves
# dead -- every faked `CompletedProcess` for the failure path above sets a
# non-empty `stderr`, so the stdout-fallback branch (stderr empty, stdout
# non-empty) and the "no captured output" branch (both streams empty) never
# execute anywhere else in this suite.
# ---------------------------------------------------------------------------


def test_extract_failure_detail_falls_back_to_stdout_when_stderr_is_empty() -> None:
    """`_extract_failure_detail` uses the last non-empty `stdout` line when
    `stderr` is empty (references_refresh.py's `for stream in
    (completed.stderr, completed.stdout): if not stream: continue` loop --
    the ``continue`` on the empty `stderr` entry is the branch under test).
    """
    completed = subprocess.CompletedProcess(
        args=["spec-kitty", "charter", "generate"],
        returncode=1,
        stdout="first stdout line\nlast stdout line\n",
        stderr="",
    )

    assert references_refresh._extract_failure_detail(completed) == "last stdout line"


def test_extract_failure_detail_reports_no_captured_output_when_both_streams_are_empty() -> None:
    """`_extract_failure_detail` falls back to the "no captured output"
    summary when BOTH `stderr` and `stdout` are empty -- the final
    ``return f"generate exited {completed.returncode} with no captured
    output"`` line, unreachable whenever either stream carries content.
    """
    completed = subprocess.CompletedProcess(
        args=["spec-kitty", "charter", "generate"],
        returncode=3,
        stdout="",
        stderr="",
    )

    assert references_refresh._extract_failure_detail(completed) == "generate exited 3 with no captured output"


# ---------------------------------------------------------------------------
# WP04 rejection-cycle-2 fold-in (#5257, wp-WP04.yaml WP04-C1-003):
# `ReferencesRefreshOutcome.__bool__` deliberately raises `TypeError` rather than
# coercing to a truthiness value -- pin the guard's own contract directly,
# not only via the absence of any truthiness use at call sites.
# ---------------------------------------------------------------------------


def test_refresh_outcome_bool_raises_type_error() -> None:
    """`ReferencesRefreshOutcome` refuses truthiness coercion outright: a caller that
    writes ``if outcome:`` instead of checking ``.attempted``/``.succeeded``
    explicitly must get a loud `TypeError`, never a silent (and wrong)
    "always truthy" read.
    """
    outcome = references_refresh.ReferencesRefreshOutcome(attempted=True, succeeded=True, detail=None)

    with pytest.raises(TypeError, match="no truth value"):
        bool(outcome)


# ---------------------------------------------------------------------------
# #5257 landing fold: the failure detail must be the real error, not a wrapped
# fragment. `charter generate` prints errors through rich, which hard-wraps at
# 80 columns when stdout is not a TTY, and a stray stderr warning must not
# outrank the real error. The refresh therefore asks for `--json` and reads
# the `error` field, falling back to an unwrapped tail for non-JSON output.
# ---------------------------------------------------------------------------

_LONG_ERROR = "Refusing to overwrite symlinked charter at /work/repo/.kittify/charter/charter.md. Remove the symlink."


def _completed(*, returncode: int = 1, stdout: str = "", stderr: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=list(_GENERATE_CMD_PREFIX), returncode=returncode, stdout=stdout, stderr=stderr)


def test_build_generate_command_requests_json_output(tmp_path: Path) -> None:
    cmd = references_refresh._build_generate_command(tmp_path)

    assert "--json" in cmd


def test_extract_failure_detail_reads_the_json_error_field() -> None:
    payload = json.dumps({"result": "error", "success": False, "error": _LONG_ERROR})

    detail = references_refresh._extract_failure_detail(_completed(stdout=payload + "\n"))

    assert detail == _LONG_ERROR


def test_extract_failure_detail_prefers_json_error_over_a_stray_stderr_warning() -> None:
    payload = json.dumps({"result": "error", "success": False, "error": _LONG_ERROR})

    detail = references_refresh._extract_failure_detail(_completed(stdout=payload + "\n", stderr="DeprecationWarning: something unrelated\n"))

    assert detail == _LONG_ERROR


def test_extract_failure_detail_unwraps_a_hard_wrapped_rich_error() -> None:
    """RED before the fold: the last stdout line alone was a wrapped fragment
    (``"...er.yaml."``), so ``blocked_reason`` read as noise."""
    wrapped = "Error: generate could not write the compiled charter because the target\nfile /work/repo/.kittify/charter/charter.yaml is read-only.\n"

    detail = references_refresh._extract_failure_detail(_completed(stdout=wrapped))

    assert detail == "Error: generate could not write the compiled charter because the target file /work/repo/.kittify/charter/charter.yaml is read-only."


def test_extract_failure_detail_wrapped_stdout_error_beats_a_stray_stderr_warning() -> None:
    """RED before the fold: the stderr-first rule let an unrelated warning win."""
    wrapped = "Error: generate could not write the compiled charter because the target\nfile is read-only.\n"

    detail = references_refresh._extract_failure_detail(_completed(stdout=wrapped, stderr="UserWarning: cache miss\n"))

    assert detail == "Error: generate could not write the compiled charter because the target file is read-only."


def test_extract_failure_detail_ignores_non_error_json_and_falls_back_to_tail() -> None:
    detail = references_refresh._extract_failure_detail(_completed(stdout='{"result": "success"}\n', stderr="boom\n"))

    assert detail == "boom"


def test_generate_output_with_invalid_utf8_never_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """RED before the fold: ``subprocess.run(text=True)`` raised an uncaught
    ``UnicodeDecodeError`` on non-UTF-8 child output, breaking the package's
    "MUST NOT raise on subprocess errors" contract. Real subprocess, no fake."""
    script = "import sys; sys.stdout.buffer.write(b'Error: bad byte \\xff\\xfe here\\n'); sys.exit(1)"
    monkeypatch.setattr(references_refresh, "_GENERATE_CMD_PREFIX", (sys.executable, "-c", script))
    monkeypatch.setattr(references_refresh, "_read_catalog_mission_and_template_set", lambda _repo_root: (None, None))

    outcome = references_refresh.refresh_references_if_needed(tmp_path, cause="synthesized_drg")

    assert outcome.attempted is True
    assert outcome.succeeded is False
    assert outcome.detail is not None
    assert outcome.detail.startswith("Error: bad byte")
    assert "here" in outcome.detail


# ---------------------------------------------------------------------------
# #5257 landing fold: `ReferencesRefreshOutcome` must not be able to represent
# the impossible states its two booleans otherwise allow.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("attempted", "succeeded", "detail"),
    [
        pytest.param(False, True, None, id="succeeded-without-attempt"),
        pytest.param(False, False, "why", id="detail-without-attempt"),
        pytest.param(True, True, "why", id="detail-on-success"),
    ],
)
def test_refresh_outcome_rejects_impossible_states(attempted: bool, succeeded: bool, detail: str | None) -> None:
    with pytest.raises(ValueError, match="impossible"):
        references_refresh.ReferencesRefreshOutcome(attempted=attempted, succeeded=succeeded, detail=detail)


@pytest.mark.parametrize(
    ("attempted", "succeeded", "detail"),
    [
        pytest.param(False, False, None, id="not-attempted"),
        pytest.param(True, True, None, id="succeeded"),
        pytest.param(True, False, "why", id="failed"),
        pytest.param(True, False, None, id="failed-without-detail"),
    ],
)
def test_refresh_outcome_accepts_the_reachable_states(attempted: bool, succeeded: bool, detail: str | None) -> None:
    outcome = references_refresh.ReferencesRefreshOutcome(attempted=attempted, succeeded=succeeded, detail=detail)

    assert (outcome.attempted, outcome.succeeded, outcome.detail) == (attempted, succeeded, detail)
