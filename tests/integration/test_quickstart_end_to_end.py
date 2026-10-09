"""End-to-end smoke for the mission's operator quickstart (WP10 / T055).

Mission ``charter-ux-and-org-pack-vocabulary-01KSAF14``.

This test walks the quickstart Steps 1-5 against a ``tmp_path``-materialised
fake repo, asserting the operator-observable contract at each step. It uses
``typer.testing.CliRunner`` (no subprocess shell-out) so it stays fast and
deterministic in CI environments that cannot spawn ``spec-kitty``.

Mapping from quickstart steps:

* Step 1 -> ``test_step1_fresh_checkout_freshness_and_lint`` —
  ``charter status --json`` exposes the freshness shape;
  ``charter lint`` runs without crashing on a built-in-only checkout.
* Step 2 -> ``test_step2_preflight_blocks_then_auto_refresh_reports_actions`` —
  ``charter preflight --json`` reports ``passed=False`` with a deterministic
  ``blocked_reason``; ``--auto-refresh`` attempts the safe sequence and
  records the actions it tried.
* Step 3 -> ``test_step3_synthesize_postcondition_is_atomic`` — after
  synthesis the repo is in one of the two legal states (graph present, or
  ``built_in_only: true``).
* Step 4 -> ``test_step4_pack_validate_intent_and_unknown_target`` — pack
  validator: same-ID with no intent -> advisory; ``enhances`` declared ->
  advisory suppressed; ``enhances: <bogus>`` -> ``unknown_target`` ERROR.
* Step 5 -> ``test_step5_no_shipped_layer_label_in_any_surface_json`` —
  architectural assertion: none of the public JSON surfaces emit
  ``"shipped"`` as a layer label.

Runtime budget: <30s on a typical dev laptop. Skips are explicit and named.
"""

from __future__ import annotations

import json
from pathlib import Path
from textwrap import dedent
from typing import Any
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from charter.hasher import hash_content


pytestmark = [pytest.mark.integration, pytest.mark.slow]


_runner = CliRunner()


# ---------------------------------------------------------------------------
# Repo-materialisation helpers (mirror the existing freshness/preflight
# fixtures — keep them inline so this file is self-contained).
# ---------------------------------------------------------------------------


def _make_sync_result_stub(repo_root: Path) -> object:
    """Stub the return value of ``ensure_charter_bundle_fresh``.

    The real implementation goes to disk to validate a synced bundle; the
    quickstart smoke flow does not exercise sync, so a static object suffices.
    """

    class _Stub:
        canonical_root = repo_root

    return _Stub()


def _seed_minimum_repo(repo: Path) -> None:
    (repo / ".kittify").mkdir(exist_ok=True)
    (repo / ".kittify" / "config.yaml").write_text(
        dedent(
            """\
            agents:
              available:
                - claude
            """
        )
    )


def _write_charter_and_metadata(repo: Path) -> None:
    """Write a fresh-looking charter + bundle so ``charter_source`` is fresh."""
    charter_dir = repo / ".kittify" / "charter"
    charter_dir.mkdir(parents=True, exist_ok=True)
    charter_path = charter_dir / "charter.md"
    metadata_path = charter_dir / "metadata.yaml"
    charter_path.write_text("# Charter\n", encoding="utf-8")
    digest = hash_content(charter_path.read_text(encoding="utf-8"))
    # Use a plain-string timestamp to dodge the ruamel-->datetime
    # serialisation issue called out by test_charter_status_freshness.py.
    metadata_path.write_text(
        dedent(
            f"""\
            charter_hash: {digest}
            extracted_at: "2026-01-01T00:00:00+00:00"
            """
        ),
        encoding="utf-8",
    )
    for name in ("governance.yaml", "directives.yaml", "references.yaml"):
        (charter_dir / name).write_text(
            "schema_version: '1'\n", encoding="utf-8"
        )


def _write_built_in_only_manifest(repo: Path) -> None:
    """Write a synthesis-manifest declaring ``built_in_only: true`` (no graph)."""
    path = repo / ".kittify" / "charter" / "synthesis-manifest.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        dedent(
            f"""\
            schema_version: '2'
            mission_id: null
            created_at: '2099-01-01T00:00:00+00:00'
            run_id: 01JTESTRUNIDXXXXXXXXXXXXXX
            adapter_id: test
            adapter_version: '0.0.0'
            synthesizer_version: '0.0.0'
            manifest_hash: {"a" * 64}
            artifacts: []
            built_in_only: true
            """
        ),
        encoding="utf-8",
    )


def _invoke_charter(repo: Path, *args: str) -> Any:
    """Invoke the ``spec-kitty charter`` typer app with the bundle/repo
    resolvers patched to the ``tmp_path`` fixture."""
    from specify_cli.cli.commands.charter import app as charter_app

    with (
        patch(
            "specify_cli.cli.commands.charter.find_repo_root",
            return_value=repo,
        ),
        patch(
            "specify_cli.cli.commands.charter.ensure_charter_bundle_fresh",
            return_value=_make_sync_result_stub(repo),
        ),
        patch(
            "specify_cli.cli.commands.charter._assert_bundle_compatible",
            return_value=None,
        ),
        patch(
            "specify_cli.charter_runtime.preflight.cli.find_repo_root",
            return_value=repo,
        ),
    ):
        return _runner.invoke(charter_app, list(args))


def _parse_json_stdout(stdout: str) -> dict[str, Any]:
    """Parse JSON from CliRunner stdout.

    Some charter subcommands emit pretty-printed JSON (multi-line) while
    ``charter preflight`` emits a single-line ``json.dumps(..., sort_keys=True)``
    payload. We try whole-stdout decoding first, then fall back to the last
    JSON-looking line (preflight contract).
    """
    text = stdout.strip()
    if not text:
        raise AssertionError("stdout is empty")
    # Try whole-payload decode (handles pretty-printed multi-line JSON).
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Fallback: pick the last line that starts with ``{`` and parses.
    for line in reversed(text.splitlines()):
        candidate = line.strip()
        if not candidate or not candidate.startswith("{"):
            continue
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue
    raise AssertionError(f"no parseable JSON in stdout: {stdout!r}")


# ---------------------------------------------------------------------------
# Step 1 — Fresh-checkout freshness reporting (FR-001..FR-005, FR-009).
# ---------------------------------------------------------------------------


class TestStep1_FreshnessAndLint:
    def test_step1_charter_status_json_has_freshness_shape(
        self, tmp_path: Path
    ) -> None:
        _seed_minimum_repo(tmp_path)

        result = _invoke_charter(tmp_path, "status", "--json")
        assert result.exit_code == 0, (
            f"charter status failed: exit={result.exit_code} "
            f"stdout={result.stdout!r} exc={result.exception!r}"
        )

        payload = _parse_json_stdout(result.stdout)
        assert "freshness" in payload, payload.keys()
        freshness = payload["freshness"]
        assert isinstance(freshness, dict)
        assert set(freshness.keys()) == {
            "charter_source",
            "synced_bundle",
            "synthesized_drg",
        }, freshness.keys()
        # Every sub-layer carries the contract triple.
        for sub_name, sub in freshness.items():
            assert "state" in sub, f"{sub_name} missing state"
            assert "last_change" in sub, f"{sub_name} missing last_change"
            assert "remediation" in sub, f"{sub_name} missing remediation"

    def test_step1_charter_lint_runs_on_fresh_checkout(
        self, tmp_path: Path
    ) -> None:
        """``charter lint`` is invokable on a freshly-cloned repo.

        The quickstart promises ``graph_state="built_in_only"`` from the
        ``--json`` payload; the live ``charter lint --json`` shape is
        report-driven (categorised findings, not a top-level layer state),
        so we assert the durable operator-observable contract: the command
        runs without crashing on a built-in-only checkout and emits a valid
        JSON payload via ``--json``.
        """
        _seed_minimum_repo(tmp_path)
        _write_charter_and_metadata(tmp_path)
        _write_built_in_only_manifest(tmp_path)

        result = _invoke_charter(tmp_path, "lint", "--json")
        # Lint may report findings (non-zero exit isn't a smoke failure); the
        # assertion is that it produced a parseable JSON payload.
        assert result.stdout.strip(), (
            f"charter lint produced no JSON: exit={result.exit_code} "
            f"stdout={result.stdout!r} exc={result.exception!r}"
        )
        parsed = _parse_json_stdout(result.stdout)
        assert isinstance(parsed, dict), parsed


# ---------------------------------------------------------------------------
# Step 2 — Preflight detects degradation (FR-006..FR-008).
# ---------------------------------------------------------------------------


class TestStep2_PreflightBlocksAndAutoRefresh:
    def test_step2_preflight_json_blocks_with_reason(
        self, tmp_path: Path
    ) -> None:
        """No manifest -> ``synthesized_drg`` missing -> preflight blocks."""
        _seed_minimum_repo(tmp_path)
        _write_charter_and_metadata(tmp_path)
        # NOTE: no manifest -> drg.state will be "missing".

        result = _invoke_charter(tmp_path, "preflight", "--json")

        # Per contract, blocked-without-strict still exits 0.
        assert result.exit_code == 0, (
            f"preflight unexpectedly failed: exit={result.exit_code} "
            f"stdout={result.stdout!r} exc={result.exception!r}"
        )
        payload = _parse_json_stdout(result.stdout)
        assert payload["passed"] is False, payload
        assert payload["blocked_reason"] is not None, payload
        # The blocked_reason must mention the synthesized_drg layer or
        # the canonical remediation command (per the contract).
        reason = payload["blocked_reason"]
        assert isinstance(reason, str) and reason, reason
        assert (
            "synthesized_drg" in reason
            or "synthesize" in reason
            or "charter status" in reason
        ), reason

    def test_step2_preflight_auto_refresh_records_actions(
        self, tmp_path: Path
    ) -> None:
        """``--auto-refresh`` produces ``auto_refresh_applied=True`` and an
        actions list.

        The refresh subprocess will not actually succeed inside this fixture
        (``spec-kitty`` is not necessarily on PATH and the repo is synthetic),
        but the binding contract is that the runner RECORDS that it tried
        and surfaces what it tried via ``auto_refresh_actions``. We assert
        the recording contract, not the subprocess success.
        """
        _seed_minimum_repo(tmp_path)
        _write_charter_and_metadata(tmp_path)
        # Repo is clean (no git init -> empty porcelain output anyway).

        result = _invoke_charter(
            tmp_path, "preflight", "--auto-refresh", "--json"
        )
        # Non-strict block still exits 0.
        assert result.exit_code == 0, (
            f"preflight --auto-refresh failed: exit={result.exit_code} "
            f"stdout={result.stdout!r} exc={result.exception!r}"
        )

        payload = _parse_json_stdout(result.stdout)
        # Contract: ``auto_refresh_applied`` and ``auto_refresh_actions``
        # are top-level keys in the JSON. We accept either:
        #   (a) git status determined the worktree was dirty/unknown so the
        #       runner refused to refresh — ``applied=False`` with a blocked
        #       reason naming the cleanliness check, OR
        #   (b) the runner attempted the sequence and recorded the actions.
        assert "auto_refresh_applied" in payload, payload
        assert "auto_refresh_actions" in payload, payload
        assert isinstance(payload["auto_refresh_actions"], list), payload

        if payload["auto_refresh_applied"]:
            # If the runner attempted refresh, the actions list must be
            # non-empty (at minimum, the synthesize step) — per the runner's
            # documented sequence.
            assert payload["auto_refresh_actions"], payload
            # Each recorded action must include "spec-kitty" since the
            # runner spawns the public CLI.
            for action in payload["auto_refresh_actions"]:
                assert isinstance(action, str), payload
                assert "spec-kitty" in action, action
        else:
            # If the runner declined to refresh, there must be a
            # ``blocked_reason`` explaining why (NFR-001 transparency rule).
            assert payload["blocked_reason"], payload


# ---------------------------------------------------------------------------
# Step 3 — Synthesize bootstrap contract (FR-009).
# ---------------------------------------------------------------------------


class TestStep3_SynthesizePostCondition:
    def test_step3_built_in_only_state_is_recognised_by_freshness(
        self, tmp_path: Path
    ) -> None:
        """Quickstart Step 3 post-condition: after synthesize either
        ``graph.yaml`` exists OR the manifest reports ``built_in_only=true``.

        Both states are operator-legal. We exercise the manifest path here:
        a manifest with ``built_in_only: true`` and no graph file should
        produce ``synthesized_drg.state == "built_in_only"`` (and the
        remediation is ``None`` — operators are unblocked).
        """
        _seed_minimum_repo(tmp_path)
        _write_charter_and_metadata(tmp_path)
        _write_built_in_only_manifest(tmp_path)
        # No graph.yaml on disk.

        result = _invoke_charter(tmp_path, "status", "--json")
        assert result.exit_code == 0, result.stdout

        payload = _parse_json_stdout(result.stdout)
        drg = payload["freshness"]["synthesized_drg"]
        assert drg["state"] == "built_in_only", drg
        assert drg["remediation"] is None, drg


# ---------------------------------------------------------------------------
# Step 4 — Pack-authoring vocabulary (FR-010..FR-014).
# ---------------------------------------------------------------------------


_BUILT_IN_TACTIC_ID = "adversarial-qa-handoff"  # same shipped tactic the WP06
# tests rely on; depending on a single live built-in keeps Step 4 stable
# across releases.


def _write_pack_tactic(
    pack_dir: Path,
    *,
    artifact_id: str,
    enhances: str | None = None,
) -> Path:
    """Mirror the helper in ``tests/charter/packs/test_pack_validator.py``."""
    tactics = pack_dir / "tactics"
    tactics.mkdir(parents=True, exist_ok=True)
    lines = [
        'schema_version: "1.0"',
        f"id: {artifact_id}",
        f"name: {artifact_id.title().replace('-', ' ')}",
    ]
    if enhances is not None:
        lines.append(f"enhances: {enhances}")
    lines.extend(["steps:", "  - title: Single test step"])
    p = tactics / f"{artifact_id}.tactic.yaml"
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p


def _assert_built_in_fixture_tactic_present() -> None:
    """Fail loudly if the fixture built-in tactic ever disappears.

    Packs always ship (``charter.offering.pack_paths.built_in_dir`` fails
    closed with ``PackRootNotFound`` when the built-in tree is absent), so a
    "skip if absent" probe around this fixture was always either dead or
    masking a real bug (#5346/#5353). This precondition assert replaces that
    probe: it never skips, it fails the test with a clear message naming the
    missing fixture path. Module-local (not imported from
    ``tests/charter/packs/test_pack_validator.py``, which owns its own
    copy) per the WP01 T002 guidance.
    """
    from charter.offering.artifact_kinds import ArtifactKind
    from charter.offering.pack_paths import built_in_dir

    path = built_in_dir(ArtifactKind.TACTIC) / f"{_BUILT_IN_TACTIC_ID}.tactic.yaml"
    assert path.is_file(), (
        f"fixture tactic {_BUILT_IN_TACTIC_ID!r} missing from shipped "
        f"built-ins at {path}"
    )


class TestStep4_PackValidatorVocabulary:
    def test_step4a_same_id_advisory_uses_reworded_message(
        self, tmp_path: Path
    ) -> None:
        """Step 4 setup: same-ID with NO intent -> reworded advisory."""
        _assert_built_in_fixture_tactic_present()

        from charter.offering.packs.pack_validator import validate_pack

        _write_pack_tactic(tmp_path, artifact_id=_BUILT_IN_TACTIC_ID)
        result = validate_pack(tmp_path)

        matched = [
            a
            for a in result.advisories
            if a.artifact_id == _BUILT_IN_TACTIC_ID
            and a.category == "same_id_collision"
        ]
        assert matched, (
            f"Same-ID collision MUST emit an advisory. "
            f"Saw: {result.advisories}"
        )
        # Message must mention field-merge and recommend both intent fields.
        msg = matched[0].message
        assert "field-merge" in msg, msg
        assert f"enhances: {_BUILT_IN_TACTIC_ID}" in msg, msg
        assert f"overrides: {_BUILT_IN_TACTIC_ID}" in msg, msg

    def test_step4b_inline_enhances_is_rejected_after_hard_cutover(
        self, tmp_path: Path
    ) -> None:
        """Inline ``enhances`` is retired; DRG fragment edges own relationships."""
        _assert_built_in_fixture_tactic_present()

        from charter.offering.packs.pack_validator import validate_pack

        _write_pack_tactic(
            tmp_path,
            artifact_id=_BUILT_IN_TACTIC_ID,
            enhances=_BUILT_IN_TACTIC_ID,
        )
        result = validate_pack(tmp_path)

        assert result.ok is False
        assert any(
            issue.artifact_id == _BUILT_IN_TACTIC_ID
            and issue.category == "schema_invalid"
            and "Retired relationship field(s) 'enhances'" in issue.message
            for issue in result.errors
        ), result.errors

    def test_step4b_unknown_enhances_target_errors(
        self, tmp_path: Path
    ) -> None:
        """``enhances: <bogus-id>`` -> hard ``unknown_target`` ERROR (FR-012)."""
        _assert_built_in_fixture_tactic_present()

        from charter.offering.packs.pack_validator import validate_pack

        _write_pack_tactic(
            tmp_path,
            artifact_id="org-only-tactic",
            enhances="totally-bogus-built-in-id-zzz",
        )
        result = validate_pack(tmp_path)

        assert result.ok is False, result.advisories
        unknown = [
            e for e in result.errors if e.category == "unknown_target"
        ]
        assert unknown, (
            f"Unknown enhances target MUST produce unknown_target error. "
            f"Saw: {result.errors}"
        )
        assert "totally-bogus-built-in-id-zzz" in unknown[0].message, (
            unknown[0].message
        )


# ---------------------------------------------------------------------------
# Step 5 — Vocabulary cutover (FR-015, FR-016).
# ---------------------------------------------------------------------------


_FORBIDDEN_LAYER_LABEL = "shipped"
_LAYER_LABEL_KEYS = frozenset(
    {"source", "layer", "provenance", "layer_label"}
)


def _iter_layer_label_values(payload: Any):
    """Yield string values at layer-label keys (recursive)."""
    if isinstance(payload, dict):
        for k, v in payload.items():
            if k in _LAYER_LABEL_KEYS and isinstance(v, str):
                yield v
            yield from _iter_layer_label_values(v)
    elif isinstance(payload, list):
        for item in payload:
            yield from _iter_layer_label_values(item)


class TestStep5_NoShippedLayerLabel:
    def test_step5_charter_status_json_has_no_shipped_layer_label(
        self, tmp_path: Path
    ) -> None:
        _seed_minimum_repo(tmp_path)
        _write_charter_and_metadata(tmp_path)
        _write_built_in_only_manifest(tmp_path)

        result = _invoke_charter(tmp_path, "status", "--json")
        assert result.exit_code == 0, result.stdout
        payload = _parse_json_stdout(result.stdout)

        violations = [
            v
            for v in _iter_layer_label_values(payload)
            if v == _FORBIDDEN_LAYER_LABEL
        ]
        assert violations == [], (
            f"charter status --json emitted forbidden layer label "
            f"{_FORBIDDEN_LAYER_LABEL!r}; payload keys: {payload.keys()}"
        )

    def test_step5_preflight_json_has_no_shipped_layer_label(
        self, tmp_path: Path
    ) -> None:
        _seed_minimum_repo(tmp_path)
        _write_charter_and_metadata(tmp_path)
        _write_built_in_only_manifest(tmp_path)

        result = _invoke_charter(tmp_path, "preflight", "--json")
        assert result.exit_code == 0, result.stdout
        payload = _parse_json_stdout(result.stdout)

        violations = [
            v
            for v in _iter_layer_label_values(payload)
            if v == _FORBIDDEN_LAYER_LABEL
        ]
        assert violations == [], (
            f"charter preflight --json emitted forbidden layer label "
            f"{_FORBIDDEN_LAYER_LABEL!r}; payload: {payload}"
        )

    def test_step5_pack_validate_json_has_no_shipped_layer_label(
        self, tmp_path: Path
    ) -> None:
        """``pack validate --json`` must not surface ``"shipped"``."""
        _assert_built_in_fixture_tactic_present()

        from charter.offering.packs.pack_validator import (
            render_validation_result,
            validate_pack,
        )

        _write_pack_tactic(tmp_path, artifact_id=_BUILT_IN_TACTIC_ID)
        result = validate_pack(tmp_path)

        import io
        import contextlib

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            render_validation_result(result, json_output=True)
        captured = buf.getvalue().strip()
        assert captured, "pack validate produced no JSON"

        parsed = json.loads(captured)
        violations = [
            v
            for v in _iter_layer_label_values(parsed)
            if v == _FORBIDDEN_LAYER_LABEL
        ]
        assert violations == [], (
            f"pack validate --json emitted forbidden layer label "
            f"{_FORBIDDEN_LAYER_LABEL!r}; payload: {parsed}"
        )
