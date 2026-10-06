"""Cross-command reason parity: finalize-tasks / map-requirements / runtime (T038).

Mission ``requirement-id-grammar-01M3NRCA`` / WP06 / T038 (US3 AC3, SC-007).

WP02 (finalize-tasks), WP03 (map-requirements) and WP04 (the runtime
readiness check) each independently wired the shared FR-019 verdict table
into their own lane. WP06's lane base is the first that holds all three
together, so this is the standing proof, once, that the three production
entry points agree: the same pass/fail verdict AND -- for every rejected
ref -- the same shared reason (``malformed`` / ``unknown_spec_id`` /
``foreign_qualified``, FR-010). Entry points only, never the pure cores
directly (``runtime_bridge_cores``/``tasks_mapping_core`` helpers).

Carries forward a WP04 review finding: the "a rejected ref never un-maps a
valid sibling" rule was pinned at cores level only, in WP04's
``tests/runtime/test_requirement_grammar_parity.py``. This file additionally
proves it across ALL THREE gates -- the malformed-ref fixture's valid
sibling ``FR-001`` is asserted MAPPED (never unmapped/missing) in finalize,
map-requirements AND the runtime.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands.agent.mission import app as finalize_app
from specify_cli.cli.commands.agent.tasks import app as tasks_app
from specify_cli.coordination.commit_router import CommitRouterResult
from specify_cli.core.checkout_identity import CheckoutIdentity

pytestmark = [pytest.mark.git_repo]

runner = CliRunner()

#: Declares FR-001, FR-002 (table rows) and SC-001 (bold bullet) -- every
#: declared shape this repro needs. Fixture is intentionally NOT shared by
#: import with any other test module's own copy (each file owns its own).
_SPEC_FIXTURE = """# Test Spec

## Functional Requirements

| ID | Requirement | Acceptance Criteria | Status |
| --- | --- | --- | --- |
| FR-001 | First requirement. | Covered by a WP. | proposed |
| FR-002 | Second requirement. | Covered by a WP. | proposed |

## Success Criteria

- **SC-001**: First success criterion.
"""


@pytest.fixture(autouse=True)
def _disable_saas_sync(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep every gate on its offline path (CLAUDE.md test policy).

    The map-requirements fixtures commit on ``main`` in a non-git ``tmp_path``
    -- the documented operator escape hatch is the ONE sanctioned waiver for
    this shape (PR #1850 guard-bypass fix; pattern copied from
    ``tests/specify_cli/test_cli/test_map_requirements.py``).
    """
    monkeypatch.setenv("SPEC_KITTY_ENABLE_SAAS_SYNC", "0")
    monkeypatch.setenv("SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS", "1")


def _write_wp_frontmatter(tasks_dir: Path, wp_id: str, refs: list[str]) -> None:
    """One WP file, ``requirement_refs`` authored directly in frontmatter
    (T011's PRIMARY source). Pattern copied from
    ``tests/runtime/test_requirement_grammar_parity.py::_write_wp_frontmatter``
    -- distinct ``owned_files``/``authoritative_surface`` per WP keeps the
    ownership-overlap gate from firing on inferred-default globs."""
    refs_yaml = " []" if not refs else "\n" + "\n".join(f"  - {ref}" for ref in refs)
    owned_glob = f"src/{wp_id.lower()}/**"
    (tasks_dir / f"{wp_id}-test.md").write_text(
        f'---\nwork_package_id: "{wp_id}"\ntitle: "Test {wp_id}"\nrequirement_refs:{refs_yaml}\ndependencies: []\n'
        f'execution_mode: "code_change"\nowned_files:\n  - "{owned_glob}"\nauthoritative_surface: "{owned_glob}"\n---\n\n# {wp_id}\n',
        encoding="utf-8",
    )


def _build_fixture(tmp_path: Path, *, wp01_refs: list[str], wp02_refs: list[str]) -> Path:
    """One mission dir: ``spec.md`` (FR-001/FR-002/SC-001) + WP01/WP02
    frontmatter refs. Every gate in this module builds its OWN fresh copy,
    because map-requirements writes to disk."""
    feature_dir = tmp_path / "kitty-specs" / "001-test"
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)
    (feature_dir / "spec.md").write_text(_SPEC_FIXTURE, encoding="utf-8")
    _write_wp_frontmatter(tasks_dir, "WP01", wp01_refs)
    _write_wp_frontmatter(tasks_dir, "WP02", wp02_refs)
    (feature_dir / "tasks.md").write_text("# Tasks\n\n## WP01\n\n## WP02\n", encoding="utf-8")
    (feature_dir / "meta.json").write_text(json.dumps({"mission_slug": "001-test"}), encoding="utf-8")
    return feature_dir


def _invoke_finalize_validate_only(tmp_path: Path, feature_dir: Path):
    """The real ``finalize-tasks --validate-only`` typer command (production
    entry point, never the phase helpers). Patch set copied from
    ``tests/runtime/test_requirement_grammar_parity.py::
    _invoke_finalize_validate_only`` (itself copied from
    ``test_finalize_requirement_id_grammar.py::_invoke_finalize`` -- the
    only existing CliRunner finalize harness that exercises
    ``--validate-only`` without a real git repository)."""
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
        return runner.invoke(
            finalize_app,
            ["finalize-tasks", "--json", "--target-branch", "main", "--validate-only"],
        )


def _invoke_map_requirements(tmp_path: Path, *, wp: str, refs: str):
    """The real ``map-requirements`` typer command (production entry
    point). Patch set copied from
    ``tests/specify_cli/test_cli/test_map_requirements.py::
    TestMapRequirementsIndividual.test_writes_to_frontmatter``."""
    with (
        patch(
            "specify_cli.cli.commands.agent.tasks.locate_project_root",
            return_value=tmp_path,
        ),
        patch(
            "specify_cli.cli.commands.agent.tasks._find_mission_slug",
            return_value="001-test",
        ),
        patch(
            "specify_cli.cli.commands.agent.tasks._ensure_target_branch_checked_out",
            return_value=(tmp_path, "main"),
        ),
    ):
        return runner.invoke(
            tasks_app,
            ["map-requirements", "--wp", wp, "--refs", refs, "--json"],
        )


def _runtime_findings(feature_dir: Path) -> list[str]:
    """The SAME function ``runtime_bridge_io.py`` calls for ``spec-kitty next``."""
    from runtime.next.runtime_bridge_guards import _check_requirement_mapping_ready

    return _check_requirement_mapping_ready(feature_dir)


def _last_json(stdout: str) -> dict[str, object]:
    json_lines = [line for line in stdout.splitlines() if line.strip().startswith("{")]
    assert json_lines, f"Expected JSON output, got: {stdout!r}"
    return json.loads(json_lines[-1])


# ---------------------------------------------------------------------------
# Main scenario: WP01 carries one ref of each shape -- valid, malformed,
# unknown_spec_id, foreign_qualified. WP02 carries the valid sibling FR-002.
# ---------------------------------------------------------------------------

_WP01_REFS = ["FR-001", "FR_009", "FR-099", "other-mission-01KAAAAA#FR-013"]
_WP02_REFS = ["FR-002"]


def test_all_three_gates_agree_same_verdict_and_reason(tmp_path: Path) -> None:
    """Assertions 1-3 (T038): same pass/fail verdict, same reason per ref,
    and the valid sibling FR-001 is unmapped/missing in NO gate (the WP04
    review finding, carried forward here to all three gates, not just the
    cores)."""
    # A fresh copy per gate: map-requirements writes to disk.
    finalize_dir = _build_fixture(tmp_path / "finalize", wp01_refs=_WP01_REFS, wp02_refs=_WP02_REFS)
    finalize_result = _invoke_finalize_validate_only(tmp_path / "finalize", finalize_dir)
    finalize_payload = _last_json(finalize_result.stdout)

    _build_fixture(tmp_path / "maprq", wp01_refs=_WP01_REFS, wp02_refs=_WP02_REFS)
    # A NEW, valid ref for WP02 so the write actually happens; the post-write
    # stale gate then evaluates ALL WPs, including the untouched WP01.
    map_result = _invoke_map_requirements(tmp_path / "maprq", wp="WP02", refs="SC-001")
    map_payload = _last_json(map_result.stdout)

    runtime_dir = _build_fixture(tmp_path / "runtime", wp01_refs=_WP01_REFS, wp02_refs=_WP02_REFS)
    runtime_findings = _runtime_findings(runtime_dir)

    # 1. Same verdict: all three gates fail.
    assert finalize_result.exit_code == 1, finalize_result.stdout
    assert map_result.exit_code == 1, map_result.stdout
    assert runtime_findings != []

    # 2. Same reason per ref.
    wp01_rejections = finalize_payload["rejected_requirement_refs"]["WP01"]  # type: ignore[index]
    assert {"ref": "FR_009", "reason": "malformed"} in wp01_rejections
    assert {"ref": "FR-099", "reason": "unknown_spec_id"} in wp01_rejections
    assert {"ref": "other-mission-01KAAAAA#FR-013", "reason": "foreign_qualified"} in wp01_rejections

    stale_reasons = map_payload["stale_ref_reasons"]["WP01"]  # type: ignore[index]
    assert "FR_009" in stale_reasons["malformed"]
    assert "FR-099" in stale_reasons["unknown_spec_id"]
    assert "other-mission-01KAAAAA#FR-013" in stale_reasons["foreign_qualified"]

    runtime_text = " ".join(runtime_findings)
    assert "FR_009 (malformed)" in runtime_text
    assert "FR-099 (unknown_spec_id)" in runtime_text
    # The runtime reports only FAILING reasons (FR-010): foreign_qualified
    # never fails, so the citation never appears as a rejected entry.
    assert "other-mission-01KAAAAA#FR-013" not in runtime_text

    # 3. Valid sibling FR-001 counts in every gate: never unmapped/missing.
    assert "FR-001" not in finalize_payload.get("unmapped_functional_requirements", [])  # type: ignore[operator]
    assert "WP01" not in finalize_payload.get("missing_requirement_refs_wps", [])  # type: ignore[operator]
    assert "FR-001" not in stale_reasons["malformed"]
    assert "FR-001" not in stale_reasons["unknown_spec_id"]
    assert "unmapped FRs: FR-001" not in runtime_text
    assert "missing refs for WPs: WP01" not in runtime_text


# ---------------------------------------------------------------------------
# Positive control (same builder): only the valid ref + a foreign citation.
# All three gates pass; finalize still reports the citation as
# foreign_qualified (never silently dropped even on the passing path).
# ---------------------------------------------------------------------------

_WP01_REFS_CONTROL = ["FR-001", "other-mission-01KAAAAA#FR-013"]


def test_positive_control_all_three_gates_pass(tmp_path: Path) -> None:
    """Assertion 4 (T038): same builder, WP01 refs trimmed to the valid ref
    plus a foreign citation -- all three gates pass, and finalize still
    reports the citation as ``foreign_qualified``."""
    finalize_dir = _build_fixture(tmp_path / "finalize", wp01_refs=_WP01_REFS_CONTROL, wp02_refs=_WP02_REFS)
    finalize_result = _invoke_finalize_validate_only(tmp_path / "finalize", finalize_dir)
    finalize_payload = _last_json(finalize_result.stdout)

    _build_fixture(tmp_path / "maprq", wp01_refs=_WP01_REFS_CONTROL, wp02_refs=_WP02_REFS)
    map_result = _invoke_map_requirements(tmp_path / "maprq", wp="WP02", refs="SC-001")

    runtime_dir = _build_fixture(tmp_path / "runtime", wp01_refs=_WP01_REFS_CONTROL, wp02_refs=_WP02_REFS)
    runtime_findings = _runtime_findings(runtime_dir)

    assert finalize_result.exit_code == 0, finalize_result.stdout
    assert map_result.exit_code == 0, map_result.stdout
    assert runtime_findings == []

    assert finalize_payload["rejected_requirement_refs"]["WP01"] == [  # type: ignore[index]
        {"ref": "other-mission-01KAAAAA#FR-013", "reason": "foreign_qualified"}
    ]
