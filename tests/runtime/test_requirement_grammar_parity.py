"""Standing parity gate: runtime readiness vs. ``finalize-tasks --validate-only``.

Mission ``requirement-id-grammar-01M3NRCA`` / WP04 / T020 / T023.

Proves, through the production entry points only (never
``runtime_bridge_cores`` directly), that ``_check_requirement_mapping_ready``
(``runtime.next.runtime_bridge``, the function ``runtime_bridge_io.py``
calls for ``spec-kitty next``) and ``finalize-tasks --validate-only``
(``specify_cli.cli.commands.agent.mission``, typer ``CliRunner``) agree on
per-WP requirement-ref verdicts -- pass/fail AND, for every rejected ref,
the same shared reason (``malformed`` / ``unknown_spec_id`` /
``foreign_qualified``).

Before WP04, the runtime readiness check carried its own second
requirement-ID authority (``runtime_bridge_cores.py``'s
``_REQUIREMENT_REF_PATTERN``, ``FR|NFR|C`` only -- no ``SC``, no letter
suffix) and an all-or-nothing rule (one unknown ref un-mapped every valid
ref on that WP). WP04 injects the shared grammar (C-001/C-002) into the
runtime cores and switched to per-ref verdicts (FR-019), closing that gap;
this module is the standing regression gate that keeps it closed.

#3519 (part 2) / #2991, US6, SC-007, FR-016.
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

pytestmark = [pytest.mark.git_repo]

runner = CliRunner()

#: Declares FR-001, a SUFFIXED FR-006a, and one Success Criterion --
#: mirrors ``tests/specify_cli/cli/commands/agent/test_finalize_requirement_
#: id_grammar.py``'s ``_SPEC_FIXTURE`` shape, trimmed to what this parity
#: repro needs (copied, not imported -- this file owns its own fixture).
_SPEC_FIXTURE = """# Test Spec

## Functional Requirements

| ID | Requirement | Acceptance Criteria | Status |
| --- | --- | --- | --- |
| FR-001 | First requirement. | Covered by a WP. | proposed |
| FR-006a | A suffixed requirement. | Covered by a WP. | proposed |

## Success Criteria

- **SC-001**: First success criterion.
"""


@pytest.fixture(autouse=True)
def _disable_saas_sync(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep this repro on the offline finalize-tasks path (CLAUDE.md test policy)."""
    monkeypatch.setenv("SPEC_KITTY_ENABLE_SAAS_SYNC", "0")


def _write_wp_frontmatter(tasks_dir: Path, wp_id: str, refs: list[str]) -> None:
    """One WP file, ``requirement_refs`` authored directly in frontmatter (T011's
    PRIMARY source). Distinct ``owned_files``/``authoritative_surface`` per WP
    keeps the ownership-overlap gate from firing on inferred-default globs
    (pattern copied from ``test_finalize_requirement_id_grammar.py::_seed_mission``)."""
    refs_yaml = " []" if not refs else "\n" + "\n".join(f"  - {ref}" for ref in refs)
    owned_glob = f"src/{wp_id.lower()}/**"
    (tasks_dir / f"{wp_id}-test.md").write_text(
        f'---\nwork_package_id: "{wp_id}"\ntitle: "Test {wp_id}"\nrequirement_refs:{refs_yaml}\ndependencies: []\n'
        f'execution_mode: "code_change"\nowned_files:\n  - "{owned_glob}"\nauthoritative_surface: "{owned_glob}"\n---\n\n# {wp_id}\n',
        encoding="utf-8",
    )


def _tasks_md_section(wp_id: str, *, label_refs: list[str] | None) -> str:
    """A ``## WPxx`` heading, with an optional ``Requirement Refs:`` label
    line -- the ONE fallback shape both ``mission_parsing.py``'s
    ``_parse_requirement_refs_from_tasks_md`` and the runtime cores' own
    parse family accept (C-008: label-line form only, not heading+bullet)."""
    lines = [f"## {wp_id}", ""]
    if label_refs:
        lines.append(f"Requirement Refs: {', '.join(label_refs)}")
        lines.append("")
    return "\n".join(lines)


def _seed_fixture(tmp_path: Path, wp_refs: dict[str, list[str]], *, variant: str) -> Path:
    """Build a mission dir with ``spec.md`` + one WP file per ``wp_refs`` entry.

    ``variant`` is ``"frontmatter"`` (refs authored directly in WP
    frontmatter; tasks.md carries no label line) or ``"tasks_md"``
    (frontmatter refs are explicitly empty -- ``[]`` -- and the SAME refs
    are authored as a tasks.md ``Requirement Refs:`` label line instead;
    no ``wps.yaml`` exists in either variant, so this is genuinely the
    legacy fallback path for ``"tasks_md"``).
    """
    feature_dir = tmp_path / "kitty-specs" / "001-test"
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)
    (feature_dir / "spec.md").write_text(_SPEC_FIXTURE, encoding="utf-8")

    sections: list[str] = []
    for wp_id, refs in wp_refs.items():
        frontmatter_refs = refs if variant == "frontmatter" else []
        label_refs = refs if variant == "tasks_md" else None
        _write_wp_frontmatter(tasks_dir, wp_id, frontmatter_refs)
        sections.append(_tasks_md_section(wp_id, label_refs=label_refs))
    (feature_dir / "tasks.md").write_text("# Tasks\n\n" + "\n".join(sections), encoding="utf-8")
    (feature_dir / "meta.json").write_text(json.dumps({"mission_slug": "001-test"}), encoding="utf-8")
    return feature_dir


def _invoke_finalize_validate_only(tmp_path: Path, feature_dir: Path):
    """Invoke the real ``finalize-tasks --validate-only`` typer command.

    Patch set copied from ``test_finalize_requirement_id_grammar.py::
    _invoke_finalize`` (the only existing CliRunner finalize harness that
    already exercises ``--validate-only`` successfully without a real git
    repository)."""
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
            app,
            ["finalize-tasks", "--json", "--target-branch", "main", "--validate-only"],
        )


def _last_json(stdout: str) -> dict[str, object]:
    json_lines = [line for line in stdout.splitlines() if line.strip().startswith("{")]
    assert json_lines, f"Expected JSON output, got: {stdout!r}"
    return json.loads(json_lines[-1])


def _runtime_findings(feature_dir: Path) -> list[str]:
    """The SAME function ``runtime_bridge_io.py`` calls for ``spec-kitty next``."""
    from runtime.next.runtime_bridge import _check_requirement_mapping_ready

    return _check_requirement_mapping_ready(feature_dir)


# ---------------------------------------------------------------------------
# 1/2. Accepting case + the undeclared-SC-009 positive control, both variants.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("variant", ["frontmatter", "tasks_md"])
def test_accepting_case_both_gates_agree(tmp_path: Path, variant: str) -> None:
    """Pre-WP04 this was RED for ``variant="tasks_md"``: the cores' own
    pattern could not see ``SC-001``/``FR-006a`` (no ``SC`` kind, no letter
    suffix), so the runtime reported ``unmapped FRs: FR-006a`` while
    finalize accepted. Now both gates read the injected grammar."""
    feature_dir = _seed_fixture(tmp_path, {"WP01": ["FR-001", "SC-001"], "WP02": ["FR-006a"]}, variant=variant)

    finalize_result = _invoke_finalize_validate_only(tmp_path, feature_dir)
    runtime_findings = _runtime_findings(feature_dir)

    assert finalize_result.exit_code == 0, finalize_result.stdout
    assert runtime_findings == []


@pytest.mark.parametrize("variant", ["frontmatter", "tasks_md"])
def test_undeclared_sc_positive_control_both_gates_fail_same_reason(tmp_path: Path, variant: str) -> None:
    """Pre-WP04 this was RED: the runtime finding said ``unknown refs: ...``
    and carried no reason vocabulary, so it could never contain the literal
    ``unknown_spec_id`` finalize's ``rejected_requirement_refs`` uses. Both
    gates now share FR-010's reason vocabulary."""
    feature_dir = _seed_fixture(tmp_path, {"WP01": ["FR-001", "SC-001"], "WP02": ["FR-006a", "SC-009"]}, variant=variant)

    finalize_result = _invoke_finalize_validate_only(tmp_path, feature_dir)
    runtime_findings = _runtime_findings(feature_dir)

    assert finalize_result.exit_code == 1
    payload = _last_json(finalize_result.stdout)
    assert {"ref": "SC-009", "reason": "unknown_spec_id"} in payload["rejected_requirement_refs"]["WP02"]  # type: ignore[operator]
    assert runtime_findings != []
    assert any("SC-009" in finding and "unknown_spec_id" in finding for finding in runtime_findings)


# ---------------------------------------------------------------------------
# 3. Malformed parity (frontmatter variant only).
# ---------------------------------------------------------------------------


def test_malformed_ref_parity(tmp_path: Path) -> None:
    """Pre-WP04 this was RED: the all-or-nothing rule un-mapped the valid
    sibling ``FR-001`` too, and the finding text never named a reason."""
    feature_dir = _seed_fixture(tmp_path, {"WP01": ["FR-001", "SC-001", "C-007-mission"], "WP02": ["FR-006a"]}, variant="frontmatter")

    finalize_result = _invoke_finalize_validate_only(tmp_path, feature_dir)
    runtime_findings = _runtime_findings(feature_dir)

    assert finalize_result.exit_code == 1
    payload = _last_json(finalize_result.stdout)
    assert payload["rejected_requirement_refs"]["WP01"] == [{"ref": "C-007-mission", "reason": "malformed"}]  # type: ignore[index]
    assert "FR-001" not in payload["unmapped_functional_requirements"]  # type: ignore[operator]
    assert runtime_findings != []
    assert any("C-007-mission (malformed)" in finding for finding in runtime_findings)


# ---------------------------------------------------------------------------
# 4. Foreign parity (frontmatter variant only).
# ---------------------------------------------------------------------------


def test_foreign_qualified_ref_parity(tmp_path: Path) -> None:
    """A qualified citation never fails either gate; the citation itself is
    still reported (as ``foreign_qualified``) rather than silently dropped."""
    feature_dir = _seed_fixture(
        tmp_path,
        {"WP01": ["FR-001", "SC-001", "other-mission-01KAAAAA#FR-013"], "WP02": ["FR-006a"]},
        variant="frontmatter",
    )

    finalize_result = _invoke_finalize_validate_only(tmp_path, feature_dir)
    runtime_findings = _runtime_findings(feature_dir)

    assert finalize_result.exit_code == 0, finalize_result.stdout
    payload = _last_json(finalize_result.stdout)
    assert payload["rejected_requirement_refs"]["WP01"] == [  # type: ignore[index]
        {"ref": "other-mission-01KAAAAA#FR-013", "reason": "foreign_qualified"}
    ]
    assert runtime_findings == []


# ---------------------------------------------------------------------------
# 5. Foreign-only WP is "missing" in both gates (Decision Moment
#    01M3NYFZ1P6QBD2DX4DVDA323W), frontmatter variant only.
# ---------------------------------------------------------------------------


def test_foreign_only_wp_is_missing_in_both_gates(tmp_path: Path) -> None:
    """A WP whose only ref is a foreign-qualified citation is 'missing' in
    both gates (a citation of another mission's id traces nothing here),
    and the citation is never reported as a failing/unknown reason."""
    feature_dir = _seed_fixture(
        tmp_path,
        {"WP01": ["FR-001", "FR-006a", "SC-001"], "WP02": ["other-mission-01KAAAAA#FR-013"]},
        variant="frontmatter",
    )

    finalize_result = _invoke_finalize_validate_only(tmp_path, feature_dir)
    runtime_findings = _runtime_findings(feature_dir)

    assert finalize_result.exit_code == 1
    payload = _last_json(finalize_result.stdout)
    assert "WP02" in payload["missing_requirement_refs_wps"]  # type: ignore[operator]
    assert payload.get("unknown_requirement_refs", {}) == {}
    assert runtime_findings != []
    assert any("missing refs for WPs" in finding and "WP02" in finding for finding in runtime_findings)
    assert not any("unknown_spec_id" in finding and "WP02" in finding for finding in runtime_findings)
