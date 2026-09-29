"""RED-FIRST issue-pinned repros for WP02 (requirement-id-grammar-01M3NRCA).

Three defects, proven through the real ``finalize-tasks`` typer command
(``CliRunner``), never by calling the internal phase helpers directly:

- (a) #2991: a real run erases/respells an authored ``requirement_refs`` list.
- (b) #3519: a declared, unmapped suffixed FR (e.g. ``FR-006a``) does not fail
  ``--validate-only``'s FR-coverage gate. Red-first evidence for (b) lives in
  WP01 T004a (both function-level and ``finalize-tasks --validate-only``
  CLI-level); on this WP01-merged base (b) is expected GREEN already and is
  kept here only as a CLI ratchet pin (see
  ``test_validate_only_fails_on_unmapped_suffixed_fr`` below).
- (c) #2066: the failure JSON carries no parsed spec-ID set.

Fixture-patch pattern copied from
``tests/agent/test_agent_feature.py::test_uses_wp_frontmatter_requirement_refs_when_tasks_md_missing_refs``
(the only existing CliRunner real-write finalize test), plus the autouse
``SPEC_KITTY_ENABLE_SAAS_SYNC=0`` fixture from
``test_feature_finalize_bootstrap.py``.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands.agent.mission import app
from specify_cli.coordination.commit_router import CommitRouterResult
from specify_cli.core.checkout_identity import CheckoutIdentity
from specify_cli.status import read_wp_frontmatter

pytestmark = [pytest.mark.fast]

runner = CliRunner()

#: Declares FR-001, a SUFFIXED FR-006a, and two Success Criteria (one
#: suffixed) -- every declared shape the WP02 grammar consumers admit.
_SPEC_FIXTURE = """# Test Spec

## Functional Requirements

| ID | Requirement | Acceptance Criteria | Status |
| --- | --- | --- | --- |
| FR-001 | First requirement. | Covered by a WP. | proposed |
| FR-006a | A suffixed requirement. | Covered by a WP. | proposed |

## Success Criteria

- **SC-001**: First success criterion.
- **SC-002b**: A suffixed success criterion.
"""


@pytest.fixture(autouse=True)
def _disable_saas_sync_for_finalize_grammar_tests(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep these tests on the offline finalize-tasks path (see CLAUDE.md test policy)."""
    monkeypatch.setenv("SPEC_KITTY_ENABLE_SAAS_SYNC", "0")


def _seed_mission(tmp_path: Path, *, spec_md: str, wp_refs: dict[str, list[str]]) -> Path:
    """Build a minimal mission dir with spec.md + one WP file per ``wp_refs`` entry.

    Each WP's ``requirement_refs`` is authored directly as a YAML list in its
    own frontmatter -- the PRIMARY raw-ref source (T011) -- so no tasks.md
    dependency-line parsing is exercised here.
    """
    feature_dir = tmp_path / "kitty-specs" / "001-test"
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)
    (feature_dir / "spec.md").write_text(spec_md, encoding="utf-8")

    tasks_md_lines = ["# Tasks", ""]
    for wp_id in wp_refs:
        tasks_md_lines.append(f"## {wp_id}")
        tasks_md_lines.append("")
    (feature_dir / "tasks.md").write_text("\n".join(tasks_md_lines), encoding="utf-8")

    for wp_id, refs in wp_refs.items():
        # An empty block-style YAML list (`requirement_refs:` with nothing
        # indented under it) parses to `None`, not `[]`, and fails
        # WPMetadata validation outright -- inline `[]` is the only form
        # that means "explicitly empty".
        refs_yaml = " []" if not refs else "\n" + "\n".join(f"  - {ref}" for ref in refs)
        # Distinct, explicit owned_files (+ authoritative_surface, so
        # ownership inference -- gated off once owned_files is explicit --
        # is never needed) per WP so a multi-WP fixture never trips the
        # ownership-overlap gate via inferred-default globs. A GLOB (not a
        # literal path) so the ownership validator's "literal path must
        # exist on disk" check does not fire for a WP that owns nothing yet.
        owned_glob = f"src/{wp_id.lower()}/**"
        (tasks_dir / f"{wp_id}-test.md").write_text(
            f'---\nwork_package_id: "{wp_id}"\ntitle: "Test {wp_id}"\nrequirement_refs:{refs_yaml}\ndependencies: []\n'
            f'execution_mode: "code_change"\nowned_files:\n  - "{owned_glob}"\nauthoritative_surface: "{owned_glob}"\n---\n\n# {wp_id}\n',
            encoding="utf-8",
        )

    (feature_dir / "meta.json").write_text(json.dumps({"mission_slug": "001-test"}), encoding="utf-8")
    return feature_dir


def _invoke_finalize(tmp_path: Path, feature_dir: Path, *, validate_only: bool = False):
    """Invoke the real ``finalize-tasks`` typer command (never the phase helpers)."""
    args = ["finalize-tasks", "--json", "--target-branch", "main"]
    if validate_only:
        args.append("--validate-only")
    with (
        patch(
            "specify_cli.cli.commands.agent.mission.locate_project_root",
            return_value=tmp_path,
        ),
        patch(
            "specify_cli.cli.commands.agent.mission._find_feature_directory",
            return_value=feature_dir,
        ),
        patch(
            "specify_cli.cli.commands.agent.mission._show_branch_context",
            return_value=(None, "main"),
        ),
        patch(
            "specify_cli.cli.commands.agent.mission_finalize.resolve_checkout_identity",
            side_effect=lambda _cwd, intent: CheckoutIdentity(
                invoking_root=tmp_path,
                canonical_target=tmp_path,
                is_owner=True,
                intent=intent,
            ),
        ),
        patch(
            "specify_cli.coordination.commit_router.commit_for_mission",
            return_value=CommitRouterResult(status="committed", placement_ref="main", commit_hash="a" * 40),
        ),
        patch(
            "specify_cli.cli.commands.agent.mission.run_command",
            return_value=(0, "a" * 40, ""),
        ),
    ):
        return runner.invoke(app, args)


def _last_json(stdout: str) -> dict[str, object]:
    """Parse the last JSON object line -- mirrors ``test_agent_feature.py``'s convention."""
    json_lines = [line for line in stdout.splitlines() if line.strip().startswith("{")]
    assert json_lines, f"Expected JSON output, got: {stdout!r}"
    return json.loads(json_lines[-1])


# ---------------------------------------------------------------------------
# (a) #2991: a real run must never erase or respell an authored requirement_refs.
# ---------------------------------------------------------------------------


def test_real_run_never_erases_authored_refs(tmp_path: Path) -> None:
    """#2991: WP01 refs ``[FR-001, SC-001, SC-002b, FR-006A]`` (in this exact
    order) survive a real run byte-for-byte -- including the uppercase-suffix
    spelling ``FR-006A`` of the declared ``FR-006a``. Every item is valid, so
    the real write must run (non-vacuity, proven by (iii) below).

    RED on the WP01 base: WP01's ``normalize_requirement_refs_value``
    respells ``FR-006A`` -> ``FR-006a`` and finalize-tasks (pre-T010) still
    wrote the normalised list, so (ii) fails there. GREEN after T010.
    """
    seeded_refs = ["FR-001", "SC-001", "SC-002b", "FR-006A"]
    feature_dir = _seed_mission(tmp_path, spec_md=_SPEC_FIXTURE, wp_refs={"WP01": seeded_refs})

    result = _invoke_finalize(tmp_path, feature_dir)

    assert result.exit_code == 0, result.stdout
    wp_meta, _ = read_wp_frontmatter(feature_dir / "tasks" / "WP01-test.md")
    assert list(wp_meta.requirement_refs) == seeded_refs
    # Non-vacuity: other bootstrap fields were also written this run, proving
    # a real write occurred (not a false pass on an already-clean file).
    assert wp_meta.planning_base_branch == "main"
    assert "Planning artifacts" in (wp_meta.branch_strategy or "")


# ---------------------------------------------------------------------------
# (b) #3519: a declared, unmapped FR-006a fails --validate-only.
# ---------------------------------------------------------------------------


def test_validate_only_fails_on_unmapped_suffixed_fr(tmp_path: Path) -> None:
    """#3519 CLI ratchet pin: WP refs map FR-001 only; the declared, suffixed
    ``FR-006a`` is left unmapped and ``--validate-only`` fails naming it.

    Red-first evidence for this defect lives in WP01 T004a (function-level
    AND ``finalize-tasks --validate-only`` CLI-level); on this WP01-merged
    base this repro is expected GREEN already -- kept here as a ratchet, not
    as fresh red-first proof.
    """
    feature_dir = _seed_mission(tmp_path, spec_md=_SPEC_FIXTURE, wp_refs={"WP01": ["FR-001"]})

    result = _invoke_finalize(tmp_path, feature_dir, validate_only=True)

    assert result.exit_code == 1
    payload = _last_json(result.stdout)
    assert "FR-006a" in payload["unmapped_functional_requirements"]


def test_validate_only_passes_positive_control_when_suffixed_fr_mapped(tmp_path: Path) -> None:
    """Positive control for the (b) ratchet, on the same fixture: once
    ``FR-006a`` is also mapped, ``--validate-only`` passes."""
    feature_dir = _seed_mission(tmp_path, spec_md=_SPEC_FIXTURE, wp_refs={"WP01": ["FR-001", "FR-006a"]})

    result = _invoke_finalize(tmp_path, feature_dir, validate_only=True)

    assert result.exit_code == 0, result.stdout


# ---------------------------------------------------------------------------
# (c) #2066: the failure JSON has no parsed spec-ID set.
# ---------------------------------------------------------------------------


def test_validate_only_failure_json_includes_parsed_spec_ids(tmp_path: Path) -> None:
    """#2066: an unmapped ``FR-006a`` plus an undeclared ``SC-009`` WP ref
    fails ``--validate-only`` with a JSON payload that names the parsed
    spec-ID set and the per-ref rejection.

    RED on the base: the ``parsed_spec_ids``/``rejected_requirement_refs``
    keys are absent, so (i) below fails with a missing-key assertion instead
    of a ``KeyError`` -- asserted first, deliberately.
    """
    feature_dir = _seed_mission(tmp_path, spec_md=_SPEC_FIXTURE, wp_refs={"WP01": ["FR-001", "SC-009"]})

    result = _invoke_finalize(tmp_path, feature_dir, validate_only=True)

    payload = _last_json(result.stdout)
    assert "parsed_spec_ids" in payload
    assert result.exit_code == 1
    assert payload["parsed_spec_ids"] == {
        "functional": ["FR-001", "FR-006a"],
        "non_functional": [],
        "constraint": [],
        "success_criteria": ["SC-001", "SC-002b"],
    }
    assert {"ref": "SC-009", "reason": "unknown_spec_id"} in payload["rejected_requirement_refs"]["WP01"]


# ---------------------------------------------------------------------------
# Review cycle 1, item #1: a qualified citation and an uppercase-suffix FR
# both survive a REAL (non-validate-only) run byte-for-byte.
# ---------------------------------------------------------------------------


def test_real_run_keeps_qualified_citation_and_suffixed_ref(tmp_path: Path) -> None:
    """T011 (review cycle 1, blocking item #1): a real run keeps BOTH a
    foreign-qualified citation (``other-mission-01KAAAAA#FR-013``, never
    resolved locally) and an uppercase-suffix spelling (``FR-006A`` of the
    declared ``FR-006a``) on disk, item for item and in order -- FR-004's
    never-rewrite guarantee is not limited to the pure-accepted case."""
    seeded_refs = ["FR-001", "FR-006A", "other-mission-01KAAAAA#FR-013"]
    feature_dir = _seed_mission(tmp_path, spec_md=_SPEC_FIXTURE, wp_refs={"WP01": seeded_refs})

    result = _invoke_finalize(tmp_path, feature_dir)

    assert result.exit_code == 0, result.stdout
    wp_meta, _ = read_wp_frontmatter(feature_dir / "tasks" / "WP01-test.md")
    assert list(wp_meta.requirement_refs) == seeded_refs
    # Non-vacuity: another bootstrap field was also written this run.
    assert wp_meta.planning_base_branch == "main"


# ---------------------------------------------------------------------------
# Review cycle 1, item #2: a scalar-string requirement_refs becomes a list
# on a real run, items and order unchanged (T010, "Mandatory: Pin it").
# ---------------------------------------------------------------------------


def test_real_run_converts_scalar_requirement_refs_to_list(tmp_path: Path) -> None:
    """T010 mandatory pin: a legacy scalar-string ``requirement_refs`` is
    re-serialised as the canonical YAML list on a real run -- the container
    changes, the items/order/spelling do not (#3941 precedent)."""
    feature_dir = tmp_path / "kitty-specs" / "001-test"
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)
    (feature_dir / "spec.md").write_text(_SPEC_FIXTURE, encoding="utf-8")
    (feature_dir / "tasks.md").write_text("# Tasks\n\n## WP01\n\n", encoding="utf-8")
    (tasks_dir / "WP01-test.md").write_text(
        '---\nwork_package_id: "WP01"\ntitle: "Test WP01"\nrequirement_refs: "FR-001, FR-006a, SC-002b"\ndependencies: []\n---\n\n# WP01\n',
        encoding="utf-8",
    )
    (feature_dir / "meta.json").write_text(json.dumps({"mission_slug": "001-test"}), encoding="utf-8")

    result = _invoke_finalize(tmp_path, feature_dir)

    assert result.exit_code == 0, result.stdout
    wp_meta, _ = read_wp_frontmatter(feature_dir / "tasks" / "WP01-test.md")
    assert list(wp_meta.requirement_refs) == ["FR-001", "FR-006a", "SC-002b"]


# ---------------------------------------------------------------------------
# Review cycle 1, item #3: no Success Criteria section at all (spec Edge Case).
# ---------------------------------------------------------------------------

_SPEC_NO_SC = """# Test Spec

## Functional Requirements

| ID | Requirement | Acceptance Criteria | Status |
| --- | --- | --- | --- |
| FR-001 | First requirement. | Covered by a WP. | proposed |
| FR-002 | Second requirement. | Covered by a WP. | proposed |
"""


def test_mission_without_success_criteria_section_finalizes_unchanged(tmp_path: Path) -> None:
    """Spec Edge Case (T012, review cycle 1 blocking item #3): a spec.md
    with NO Success Criteria section at all finalizes cleanly -- reporting
    empty coverage rather than erroring or reporting stale figures."""
    feature_dir = _seed_mission(tmp_path, spec_md=_SPEC_NO_SC, wp_refs={"WP01": ["FR-001", "FR-002"]})

    result = _invoke_finalize(tmp_path, feature_dir, validate_only=True)

    payload = _last_json(result.stdout)
    assert result.exit_code == 0, result.stdout
    assert payload["success_criteria_coverage"] == {"referenced": {}, "unreferenced": []}
    assert payload["parsed_spec_ids"]["success_criteria"] == []
    assert payload["rejected_requirement_refs"] == {}


def test_mission_without_success_criteria_section_positive_control(tmp_path: Path) -> None:
    """Positive control for the pass above (same fixture shape): leaving
    FR-002 unmapped still fails the run and names it -- proving the clean
    pass above is not vacuous."""
    feature_dir = _seed_mission(tmp_path, spec_md=_SPEC_NO_SC, wp_refs={"WP01": ["FR-001"]})

    result = _invoke_finalize(tmp_path, feature_dir, validate_only=True)

    payload = _last_json(result.stdout)
    assert result.exit_code == 1
    assert "FR-002" in payload["unmapped_functional_requirements"]
    assert payload["success_criteria_coverage"] == {"referenced": {}, "unreferenced": []}


# ---------------------------------------------------------------------------
# Review cycle 1, item #4: a malformed ref leaves the file byte-identical
# on a REAL run (US1 AC2).
# ---------------------------------------------------------------------------


def test_real_run_malformed_ref_leaves_file_byte_identical(tmp_path: Path) -> None:
    """T011 (review cycle 1, blocking item #4): a malformed ref fails a REAL
    run before any write, leaving the WP file byte-identical to what was
    seeded."""
    feature_dir = _seed_mission(tmp_path, spec_md=_SPEC_FIXTURE, wp_refs={"WP01": ["FR-001", "C-007-mission"]})
    wp_file = feature_dir / "tasks" / "WP01-test.md"
    seeded_bytes = wp_file.read_bytes()

    result = _invoke_finalize(tmp_path, feature_dir)

    assert result.exit_code == 1
    payload = _last_json(result.stdout)
    assert payload["rejected_requirement_refs"]["WP01"] == [{"ref": "C-007-mission", "reason": "malformed"}]
    assert "FR-001" not in payload["unmapped_functional_requirements"]
    assert wp_file.read_bytes() == seeded_bytes


# ---------------------------------------------------------------------------
# Review cycle 1, item #5: FR-007 coverage -- a non-empty
# success_criteria_coverage.unreferenced is pinned (kills mutation M8, which
# hard-codes ``unreferenced: []`` in _build_success_criteria_coverage).
# ---------------------------------------------------------------------------

_SPEC_UNREFERENCED_SC = """# Test Spec

## Functional Requirements

| ID | Requirement | Acceptance Criteria | Status |
| --- | --- | --- | --- |
| FR-001 | First requirement. | Covered by a WP. | proposed |

## Success Criteria

- **SC-001**: Never referenced by any WP.
"""


def test_unreferenced_success_criterion_is_reported_and_does_not_fail(tmp_path: Path) -> None:
    """FR-007 / mutation M8 (review cycle 1, blocking item #5): a declared
    SC that no WP references appears in
    ``success_criteria_coverage.unreferenced`` -- and never fails the run.
    Kills the M8 mutant that hard-codes ``unreferenced: []``."""
    feature_dir = _seed_mission(tmp_path, spec_md=_SPEC_UNREFERENCED_SC, wp_refs={"WP01": ["FR-001"]})

    result = _invoke_finalize(tmp_path, feature_dir, validate_only=True)

    payload = _last_json(result.stdout)
    assert result.exit_code == 0, result.stdout
    assert payload["success_criteria_coverage"]["unreferenced"] == ["SC-001"]


def test_unreferenced_success_criterion_positive_control_unmapped_fr_still_fails(tmp_path: Path) -> None:
    """Positive control for the pass above (same fixture shape): an
    unmapped FR still fails the run and names it, while the SC stays
    unreferenced (non-gating) -- proving the pass above is not vacuous."""
    feature_dir = _seed_mission(tmp_path, spec_md=_SPEC_UNREFERENCED_SC, wp_refs={"WP01": []})

    result = _invoke_finalize(tmp_path, feature_dir, validate_only=True)

    payload = _last_json(result.stdout)
    assert result.exit_code == 1
    assert "FR-001" in payload["unmapped_functional_requirements"]
    assert payload["success_criteria_coverage"]["unreferenced"] == ["SC-001"]


# ---------------------------------------------------------------------------
# Review cycle 1, item #6: T011's per-ref-verdict halves, proven CLI-level
# (--validate-only) on top of the existing helper-level unit tests -- the
# WP mandates this; a helper-only pin is a non-vacuity failure mode.
# ---------------------------------------------------------------------------


def test_cli_half1_valid_sibling_counts_while_undeclared_sc_fails(tmp_path: Path) -> None:
    """T011 Half 1, CLI-level: a valid ref still counts toward coverage
    while a sibling ref on the SAME WP is rejected as an undeclared spec
    id."""
    feature_dir = _seed_mission(tmp_path, spec_md=_SPEC_FIXTURE, wp_refs={"WP01": ["FR-001", "SC-009"]})

    result = _invoke_finalize(tmp_path, feature_dir, validate_only=True)

    payload = _last_json(result.stdout)
    assert result.exit_code == 1
    assert payload["unknown_requirement_refs"] == {"WP01": ["SC-009"]}
    assert "FR-001" not in payload["unmapped_functional_requirements"]


def test_cli_half2_foreign_qualified_never_fails(tmp_path: Path) -> None:
    """T011 Half 2, CLI-level: a foreign-qualified citation is rejected but
    never a FAILING reason -- the run passes and the citation is reported
    ``foreign_qualified``."""
    feature_dir = _seed_mission(
        tmp_path,
        spec_md=_SPEC_FIXTURE,
        wp_refs={"WP01": ["FR-001", "FR-006a", "other-mission-01KAAAAA#FR-013"]},
    )

    result = _invoke_finalize(tmp_path, feature_dir, validate_only=True)

    payload = _last_json(result.stdout)
    assert result.exit_code == 0, result.stdout
    assert payload["rejected_requirement_refs"]["WP01"] == [{"ref": "other-mission-01KAAAAA#FR-013", "reason": "foreign_qualified"}]


def test_cli_sc_only_wp_counts_as_having_refs(tmp_path: Path) -> None:
    """CLI-level: a WP whose only accepted refs are Success Criteria is not
    'missing', on a 2-WP fixture where every FR is mapped by the OTHER WP."""
    feature_dir = _seed_mission(
        tmp_path,
        spec_md=_SPEC_FIXTURE,
        wp_refs={"WP01": ["FR-001", "FR-006a"], "WP02": ["SC-001"]},
    )

    result = _invoke_finalize(tmp_path, feature_dir, validate_only=True)

    payload = _last_json(result.stdout)
    assert result.exit_code == 0, result.stdout
    assert payload["success_criteria_coverage"]["referenced"] == {"SC-001": ["WP02"]}


def test_cli_foreign_only_wp_is_missing_but_not_unknown(tmp_path: Path) -> None:
    """CLI-level, Decision Moment ``01M3NYFZ1P6QBD2DX4DVDA323W``: a WP whose
    only ref is foreign-qualified is 'missing' (fails the run) but its
    citation is never reported as an ``unknown_requirement_refs`` failure --
    the SC-only case above is this rule's positive control."""
    feature_dir = _seed_mission(
        tmp_path,
        spec_md=_SPEC_FIXTURE,
        wp_refs={"WP01": ["FR-001", "FR-006a"], "WP02": ["other-mission-01KAAAAA#FR-013"]},
    )

    result = _invoke_finalize(tmp_path, feature_dir, validate_only=True)

    payload = _last_json(result.stdout)
    assert result.exit_code == 1
    assert "WP02" in payload["missing_requirement_refs_wps"]
    assert payload.get("unknown_requirement_refs", {}) == {}
    assert payload["rejected_requirement_refs"]["WP02"] == [{"ref": "other-mission-01KAAAAA#FR-013", "reason": "foreign_qualified"}]
