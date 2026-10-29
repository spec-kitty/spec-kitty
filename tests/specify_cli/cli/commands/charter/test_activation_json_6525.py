"""``charter activate`` / ``charter deactivate`` ``--json`` (issue #6525, local slice; FR-004..FR-008).

Positional activate/deactivate emit exactly one JSON document on stdout: the
ActivationChangeReport on success, the canonical ``{"ok": false, "error":
{"code", "message"}}`` envelope on refusal (exit code equal to the same
invocation without ``--json``, nothing under ``.kittify/`` changed). The codes
are local UPPER_SNAKE (contracts/cli-json.md), never the spec-kitty-charter
contract codes. Fixtures are shared with ``test_activation_text_golden.py``.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest
from click.testing import Result

from specify_cli.cli.commands.charter import charter_app
from specify_cli.cli.commands.charter._charter_write_root import LinkedWorktreeCharterWriteError
from tests.specify_cli.cli.commands.charter.test_activation_text_golden import (
    RUNNER,
    WIDE_ENV,
    build_activation_project,
    build_deactivation_project,
)

pytestmark = [pytest.mark.fast]

_P = {"kind": "directive", "id": "p-dir", "urn": "directive:DIRECTIVE_P"}
_C = {"kind": "tactic", "id": "c-tac", "urn": "tactic:TACTIC_C"}
_G = {"kind": "procedure", "id": "g-proc", "urn": "procedure:PROCEDURE_G"}
_S = {"kind": "styleguide", "id": "s-style", "urn": "styleguide:STYLEGUIDE_S"}
_A = {"kind": "asset", "id": "a-asset", "urn": "asset:ASSET_A"}
_EMPTY_OUTCOMES = {
    "cascaded": [],
    "reinstated": [],
    "failed": [],
    "skipped_out_of_scope": [],
    "skipped_deactivated": [],
    "unreached_behind_deactivated": [],
    "skipped_kind_filtered": [],
    "skipped_shared": [],
    "skipped_required": [],
    "still_active_unrestricted": [],
}


_NO_COMPILE_NOTICE = (
    "Catalog not recompiled (--no-compile): catalog.references may go stale until the next `charter generate` or `charter activate --resynthesize`."
)


def _run(root: Path, command: str, *args: str, json_output: bool = True) -> Result:
    flags = ["--json"] if json_output else []
    return RUNNER.invoke(charter_app, [command, "--repo-root", str(root), "--no-compile", *args, *flags], env=WIDE_ENV)


def _payload(result: Result) -> Any:
    """The whole stdout must be one JSON document (NFR-001)."""
    return json.loads(result.stdout)


def _kittify(root: Path) -> dict[str, bytes]:
    base = root / ".kittify"
    return {str(path.relative_to(base)): path.read_bytes() for path in sorted(base.rglob("*")) if path.is_file()}


def _cascade(**outcomes: list[dict[str, Any]]) -> dict[str, Any]:
    return {**_EMPTY_OUTCOMES, **outcomes}


# --------------------------------------------------------------------------- #
# Success payloads
# --------------------------------------------------------------------------- #


def test_direct_activation_reports_what_the_no_cascade_warning_names(tmp_path: Path) -> None:
    root = build_activation_project(tmp_path)

    result = _run(root, "activate", "directive", "p-dir")

    assert result.exit_code == 0, result.output
    payload = _payload(result)
    assert payload == {
        "schema_version": "1.0.0",
        "command": "activate",
        "kind": "directive",
        "id": "p-dir",
        "changed": ["p-dir"],
        "now_listed": [],
        "no_longer_in_force": [],
        "warnings": [],
        "notices": [_NO_COMPILE_NOTICE],
        "referenced_not_cascaded": [_G, _S, _C],
        "referenced_kind_filtered": [_A],
        "cascade": None,
    }


def test_direct_activation_lists_a_deactivated_reference_too(tmp_path: Path) -> None:
    root = build_activation_project(tmp_path, deactivated_tactics=["c-tac"])

    payload = _payload(_run(root, "activate", "directive", "p-dir"))

    assert payload["referenced_not_cascaded"] == [_G, _S, _C]


def test_cascade_activation_reports_every_touched_artifact(tmp_path: Path) -> None:
    root = build_activation_project(tmp_path)

    result = _run(root, "activate", "--cascade", "all", "directive", "p-dir")

    assert result.exit_code == 0, result.output
    payload = _payload(result)
    assert payload["referenced_not_cascaded"] == []
    # With --cascade the kind-filtered references are cascade.skipped_kind_filtered.
    assert payload["referenced_kind_filtered"] == []
    assert payload["cascade"] == {
        "source_urn": _P["urn"],
        "scope": "all",
        **_cascade(cascaded=[_G, _S, _C], skipped_kind_filtered=[_A]),
    }


def test_a_narrowed_scope_reports_the_out_of_scope_artifacts(tmp_path: Path) -> None:
    root = build_activation_project(tmp_path)

    payload = _payload(_run(root, "activate", "--cascade", "tactic", "directive", "p-dir"))

    assert payload["cascade"]["scope"] == ["tactic"]
    assert payload["cascade"]["cascaded"] == [_C]
    assert payload["cascade"]["skipped_out_of_scope"] == [{**_G, "deactivated": False}, {**_S, "deactivated": False}]


def test_an_out_of_scope_deactivated_node_is_marked_as_the_blocker(tmp_path: Path) -> None:
    root = build_activation_project(tmp_path, deactivated_tactics=["c-tac"])

    payload = _payload(_run(root, "activate", "--cascade", "directive,procedure", "directive", "p-dir"))

    assert payload["cascade"]["skipped_out_of_scope"] == [{**_S, "deactivated": False}, {**_C, "deactivated": True}]
    assert payload["cascade"]["unreached_behind_deactivated"] == [_G]


def test_a_deactivated_child_is_skipped_with_its_requiring_parent(tmp_path: Path) -> None:
    root = build_activation_project(tmp_path, deactivated_tactics=["c-tac"])

    payload = _payload(_run(root, "activate", "--cascade", "all", "directive", "p-dir"))

    assert payload["cascade"] == {
        "source_urn": _P["urn"],
        "scope": "all",
        **_cascade(
            cascaded=[_S],
            skipped_deactivated=[{**_C, "required_by": ["directive:DIRECTIVE_P"]}],
            unreached_behind_deactivated=[_G],
            skipped_kind_filtered=[_A],
        ),
    }


def test_include_deactivated_reports_the_reinstated_child(tmp_path: Path) -> None:
    root = build_activation_project(tmp_path, deactivated_tactics=["c-tac"])

    payload = _payload(_run(root, "activate", "--cascade", "all", "--include-deactivated", "directive", "p-dir"))

    assert payload["cascade"]["cascaded"] == [_G, _S, _C]
    assert payload["cascade"]["reinstated"] == [_C]
    assert payload["cascade"]["skipped_deactivated"] == []


def test_only_reports_what_stopped_being_in_force(tmp_path: Path) -> None:
    root = build_activation_project(tmp_path, activated_tactics=["adversarial-qa-handoff"])

    payload = _payload(_run(root, "activate", "--only", "tactic", "c-tac"))

    assert payload["changed"] == ["c-tac"]
    assert payload["no_longer_in_force"] == ["adversarial-qa-handoff"]
    assert payload["now_listed"] == ["c-tac"]


def test_only_on_an_unresolved_effective_set_reports_no_longer_in_force_as_unknown(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``null``, not ``[]``: the text footer reads "unknown" here (a8dd1812, Decision ``only_unknown_footer``)."""
    import dataclasses
    from collections.abc import Iterable

    from charter.activation import effective_set
    from charter.activation.activation_engine import EffectiveSet

    real = effective_set.resolve_effective_sets

    def resolve(repo_root: Path, yaml_keys: Iterable[str]) -> dict[str, EffectiveSet]:
        sets = real(repo_root, yaml_keys)
        entry = sets.get("activated_tactics")
        if entry is not None:
            sets["activated_tactics"] = dataclasses.replace(
                entry, ids=frozenset(), resolved=False, reason="the test made it unresolvable", fallback_ids=entry.ids | entry.fallback_ids
            )
        return sets

    monkeypatch.setattr(effective_set, "resolve_effective_sets", resolve)
    # Two projects: the first run writes the list, after which nothing is unresolved any more.
    root = build_activation_project(tmp_path / "json")
    text_root = build_activation_project(tmp_path / "text")

    result = _run(root, "activate", "--only", "tactic", "c-tac")
    text = _run(text_root, "activate", "--only", "tactic", "c-tac", json_output=False)

    assert result.exit_code == 0, result.output
    payload = _payload(result)
    assert payload["now_listed"] == ["c-tac"]
    assert payload["no_longer_in_force"] is None
    assert any("could not be resolved because the test made it unresolvable" in warning for warning in payload["warnings"]), payload["warnings"]
    assert "No longer in force: unknown (see the warning above)" in text.stdout


def test_cascade_deactivation_reports_shared_required_and_unrestricted_children(tmp_path: Path) -> None:
    root = build_deactivation_project(tmp_path)

    result = _run(root, "deactivate", "--cascade", "all", "directive", "p1-dir")

    assert result.exit_code == 0, result.output
    payload = _payload(result)
    assert payload["command"] == "deactivate"
    assert payload["changed"] == ["p1-dir"]
    assert payload["no_longer_in_force"] == []
    assert payload["cascade"] == {
        "source_urn": "directive:DIRECTIVE_P1",
        "scope": "all",
        **_cascade(
            cascaded=[{"kind": "tactic", "id": "x-tac", "urn": "tactic:TACTIC_X"}],
            skipped_kind_filtered=[_A],
            skipped_shared=[{"kind": "tactic", "id": "t-tac", "urn": "tactic:TACTIC_T", "referenced_by": "directive:DIRECTIVE_P2"}],
            skipped_required=[{"kind": "tactic", "id": "r-tac", "urn": "tactic:TACTIC_R", "packs": ["acme"]}],
            still_active_unrestricted=[_S],
        ),
    }


def test_direct_deactivation_has_no_cascade(tmp_path: Path) -> None:
    root = build_deactivation_project(tmp_path)

    payload = _payload(_run(root, "deactivate", "directive", "p2-dir"))

    assert payload["changed"] == ["p2-dir"]
    assert payload["cascade"] is None
    assert payload["referenced_not_cascaded"] == []


# --------------------------------------------------------------------------- #
# Refusals: canonical envelope, same exit code, nothing written (NFR-003)
# --------------------------------------------------------------------------- #


def _break_activation_store(root: Path) -> None:
    """An unparseable activation ledger: the activation store cannot be read (FR-013)."""
    (root / ".kittify" / "charter" / "activation.yaml").write_text("activated_directives: [unclosed\n", encoding="utf-8")


def _assert_refusal(root: Path, command: str, args: tuple[str, ...], code: str) -> dict[str, Any]:
    before = _kittify(root)

    result = _run(root, command, *args)
    text = _run(root, command, *args, json_output=False)

    assert result.exit_code == 1, result.output
    assert text.exit_code == result.exit_code, text.output
    payload = _payload(result)
    assert payload["ok"] is False
    assert payload["error"]["code"] == code
    assert isinstance(payload["error"]["message"], str) and payload["error"]["message"]
    assert f"Error ({code}):" in text.stdout
    assert _kittify(root) == before
    error: dict[str, Any] = payload["error"]
    return error


@pytest.mark.parametrize("command", ["activate", "deactivate"])
def test_an_unknown_kind_is_refused(tmp_path: Path, command: str) -> None:
    root = build_activation_project(tmp_path)

    _assert_refusal(root, command, ("nonsense", "x"), "ACTIVATION_KIND_UNKNOWN")


@pytest.mark.parametrize("command", ["activate", "deactivate"])
def test_a_bad_cascade_scope_is_refused(tmp_path: Path, command: str) -> None:
    root = build_activation_project(tmp_path)

    _assert_refusal(root, command, ("--cascade", "bogus-kind", "directive", "p-dir"), "CASCADE_SCOPE_INVALID")


@pytest.mark.parametrize("command", ["activate", "deactivate"])
def test_an_unreadable_activation_store_is_refused(tmp_path: Path, command: str) -> None:
    root = build_activation_project(tmp_path)
    _break_activation_store(root)

    _assert_refusal(root, command, ("directive", "p-dir"), "ACTIVE_CHARTER_CONFIG_INVALID")


@pytest.mark.parametrize(
    ("command", "code"),
    [
        # activate reads the org registry through charter's require_declared_org_roots,
        # which raises a plain ValueError (an activation-engine failure here).
        ("activate", "ACTIVATION_FAILED"),
        # deactivate reads it through the strict required-floor read (ActiveCharterConfigError).
        ("deactivate", "ACTIVE_CHARTER_CONFIG_INVALID"),
    ],
)
def test_a_malformed_charter_packs_config_is_refused(tmp_path: Path, command: str, code: str) -> None:
    root = build_activation_project(tmp_path)
    (root / ".kittify" / "config.yaml").write_text("charter_packs: [1, 2]\n", encoding="utf-8")

    error = _assert_refusal(root, command, ("directive", "001-architectural-integrity-standard"), code)

    assert "org pack registry" in error["message"]


def test_an_org_required_id_is_refused_naming_the_packs(tmp_path: Path) -> None:
    root = build_deactivation_project(tmp_path)

    error = _assert_refusal(root, "deactivate", ("tactic", "r-tac"), "DEACTIVATION_REFUSED_REQUIRED")

    assert error["requiring_packs"] == ["acme"]


@pytest.mark.parametrize("command", ["activate", "deactivate"])
def test_a_linked_worktree_write_root_is_refused(tmp_path: Path, command: str, monkeypatch: pytest.MonkeyPatch) -> None:
    root = build_activation_project(tmp_path)

    def refuse(start: Path) -> Path:
        raise LinkedWorktreeCharterWriteError(start)

    # The write-root probe itself is covered by test_charter_write_root_4785.py
    # against a real linked worktree; here only its refusal rendering is under test.
    monkeypatch.setattr("specify_cli.cli.commands.charter.activate.resolve_charter_write_root", refuse)

    _assert_refusal(root, command, ("directive", "p-dir"), "CHARTER_WRITE_ROOT_INVALID")


@pytest.mark.parametrize("command", ["activate", "deactivate"])
def test_an_unknown_artifact_id_is_refused(tmp_path: Path, command: str) -> None:
    root = build_activation_project(tmp_path)

    error = _assert_refusal(root, command, ("directive", "no-such-directive"), "ACTIVATION_FAILED")

    assert "no-such-directive" in error["message"]


def test_the_text_refusal_carries_the_code(tmp_path: Path) -> None:
    root = build_activation_project(tmp_path)

    result = _run(root, "activate", "nonsense", "x", json_output=False)

    assert result.exit_code == 1
    assert result.stdout.startswith("Error (ACTIVATION_KIND_UNKNOWN): Unknown kind 'nonsense'. Valid kinds: ")


def test_a_preset_json_refusal_is_unchanged(tmp_path: Path) -> None:
    root = build_activation_project(tmp_path)

    result = RUNNER.invoke(charter_app, ["activate", "--repo-root", str(root), "--preset", "missing", "--json"], env=WIDE_ENV)

    assert result.exit_code == 1
    payload = _payload(result)
    assert payload["ok"] is False
    assert payload["error"]["code"]


def test_include_deactivated_without_cascade_stays_a_usage_error(tmp_path: Path) -> None:
    root = build_activation_project(tmp_path)

    result = _run(root, "activate", "--include-deactivated", "directive", "p-dir")

    assert result.exit_code == 2


# --------------------------------------------------------------------------- #
# The post-change tail in --json mode
# --------------------------------------------------------------------------- #


def test_a_failed_catalog_refresh_is_a_coded_error_carrying_the_report(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import typer

    root = build_activation_project(tmp_path)

    def fail(_root: Path, **_kwargs: object) -> None:
        raise typer.Exit(3)

    monkeypatch.setattr("specify_cli.cli.commands.charter.activate.recompile_or_notify", fail)

    result = _run(root, "activate", "directive", "p-dir")

    assert result.exit_code == 1
    error = _payload(result)["error"]
    assert error["code"] == "RESYNTHESIS_FAILED"
    assert "(exit 3)" in error["message"]
    assert error["changed"] == ["p-dir"]


def test_a_failed_skill_projection_is_a_coded_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import typer

    root = build_deactivation_project(tmp_path)

    def fail(_root: Path, _kind: str) -> None:
        raise typer.Exit(1)

    monkeypatch.setattr("specify_cli.cli.commands.charter.activate.reproject_pack_skills", fail)

    result = _run(root, "deactivate", "directive", "p2-dir")

    assert result.exit_code == 1
    error = _payload(result)["error"]
    assert error["code"] == "ACTIVATION_FAILED"
    assert error["command"] == "deactivate"


def test_the_failed_step_output_is_the_error_detail(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import typer

    from specify_cli.cli.console import console

    root = build_activation_project(tmp_path)

    def fail(_root: Path, **_kwargs: object) -> None:
        console.print("[red]Error[/red]: the bundle could not be synthesized.")
        raise typer.Exit(3)

    monkeypatch.setattr("specify_cli.cli.commands.charter.activate.recompile_or_notify", fail)

    result = _run(root, "activate", "directive", "p-dir")

    assert result.exit_code == 1
    error = _payload(result)["error"]
    assert error["code"] == "RESYNTHESIS_FAILED"
    assert error["detail"] == "Error: the bundle could not be synthesized."


def test_the_no_compile_notice_is_a_json_notice(tmp_path: Path) -> None:
    root = build_deactivation_project(tmp_path)

    payload = _payload(_run(root, "deactivate", "directive", "p2-dir"))

    assert payload["notices"] == [_NO_COMPILE_NOTICE]


def test_a_degraded_catalog_recompile_reaches_the_json_notices(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Default compile, nothing patched: an unresolvable activated directive degrades the recompile to a notice."""
    import subprocess

    root = build_activation_project(tmp_path)
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    monkeypatch.chdir(root)
    generated = RUNNER.invoke(charter_app, ["generate", "--no-from-interview"], env=WIDE_ENV)
    assert generated.exit_code == 0, generated.output
    assert (root / ".kittify" / "charter" / "charter.yaml").is_file()

    result = RUNNER.invoke(charter_app, ["activate", "--repo-root", str(root), "directive", "p-dir", "--json"], env=WIDE_ENV)

    assert result.exit_code == 0, result.output
    payload = _payload(result)
    degraded = [notice for notice in payload["notices"] if notice.startswith("Catalog not recompiled: ")]
    assert len(degraded) == 1, payload["notices"]
    assert "every activated 'directive' reference is unresolvable (DIRECTIVE_P)" in degraded[0]
    assert degraded[0].endswith("or `charter activate --resynthesize`.")


def test_a_mission_type_activation_reports_its_kind_filtered_references(tmp_path: Path) -> None:
    root = build_activation_project(tmp_path)

    payload = _payload(_run(root, "activate", "mission-type", "software-dev"))
    text = _run(root, "activate", "mission-type", "software-dev", json_output=False)

    filtered = payload["referenced_kind_filtered"]
    assert filtered, "software-dev references templates, which are not charter-activatable"
    assert {ref["kind"] for ref in filtered} == {"template"}
    rendered = [line for line in text.stdout.splitlines() if line.startswith("Not cascaded: ")]
    assert rendered == [f"Not cascaded: {ref['kind']}/{ref['id']} (kind not charter-activatable)" for ref in filtered]


def test_a_clean_exit_of_the_tail_passes_through() -> None:
    import typer

    from specify_cli.cli.commands.charter.activate import _captured_tail

    def done() -> None:
        raise typer.Exit(0)

    with pytest.raises(typer.Exit) as raised:
        _captured_tail(done, "UNUSED", "unused", {})
    assert raised.value.exit_code == 0


# --------------------------------------------------------------------------- #
# Focused report / helper tests
# --------------------------------------------------------------------------- #


def test_a_failed_cascade_target_is_reported_and_rendered(capsys: pytest.CaptureFixture[str]) -> None:
    from specify_cli.cli.commands.charter._activation_report import ArtifactRef, CascadeEntry, CascadeOutcome, CascadeReport
    from specify_cli.cli.commands.charter.activate import render_cascade_activation

    failed = CascadeEntry(CascadeOutcome.FAILED, ArtifactRef("tactic", "t1", "tactic:T1"), message="boom")
    report = CascadeReport("directive:D", ("tactic",), (failed,), zero_activatable=False)

    render_cascade_activation(report)

    assert "could not cascade-activate tactic/t1: boom" in " ".join(capsys.readouterr().out.split())
    assert report.to_json()["failed"] == [{"kind": "tactic", "id": "t1", "urn": "tactic:T1", "message": "boom"}]
    assert report.to_json()["scope"] == ["tactic"]


def test_the_zero_activatable_summary_closes_the_rendered_report(capsys: pytest.CaptureFixture[str]) -> None:
    from specify_cli.cli.commands.charter._activation_report import CascadeReport
    from specify_cli.cli.commands.charter.activate import render_cascade_activation

    render_cascade_activation(CascadeReport("directive:D", "all", (), zero_activatable=True))

    assert "Cascade resolved zero activatable targets" in capsys.readouterr().out


def test_a_cascaded_profile_warning_joins_the_json_warnings() -> None:
    from specify_cli.cli.commands.charter._activation_report import (
        ActivationChangeReport,
        ArtifactRef,
        CascadeEntry,
        CascadeOutcome,
        CascadeReport,
    )

    cascaded = CascadeEntry(CascadeOutcome.CASCADED, ArtifactRef("agent-profile", "p", "agent_profile:p"), message="p is a mission default")
    report = ActivationChangeReport(
        command="deactivate",
        kind="directive",
        id="d",
        warnings=("direct",),
        tension_warnings=("tension",),
        cascade=CascadeReport("directive:D", "all", (cascaded,)),
    )

    payload = report.to_json()

    assert payload["warnings"] == ["direct", "tension", "p is a mission default"]
    cascade = payload["cascade"]
    assert isinstance(cascade, dict)
    assert cascade["cascaded"] == [{"kind": "agent-profile", "id": "p", "urn": "agent_profile:p"}]


def test_a_non_required_deactivation_refusal_is_activation_failed() -> None:
    from charter.activation.pack_manager import DeactivationRefused
    from specify_cli.cli.commands.charter import deactivate as deactivate_module

    class _Locked(DeactivationRefused):
        """A future, non-``required`` policy reason."""

        def __init__(self) -> None:
            super().__init__("directive", "d", "locked", "locked by policy")

    refusal = deactivate_module._deactivation_refusal(_Locked())

    assert (refusal.code, refusal.message, refusal.payload) == ("ACTIVATION_FAILED", "locked by policy", None)


# --------------------------------------------------------------------------- #
# Canonical payload snapshots (T006). Regenerate with UPDATE_SNAPSHOT=1 and
# review the diff: a change here is a change of the local JSON contract.
# --------------------------------------------------------------------------- #

_SNAPSHOT_DIR = Path(__file__).parent / "snapshots" / "activation_json"
_SNAPSHOT_CASES: dict[str, tuple[str, str, tuple[str, ...]]] = {
    "activate_direct": ("activation", "activate", ("directive", "p-dir")),
    "activate_cascade": ("activation", "activate", ("--cascade", "all", "directive", "p-dir")),
    "deactivate_cascade": ("deactivation", "deactivate", ("--cascade", "all", "directive", "p1-dir")),
}


@pytest.mark.parametrize("name", sorted(_SNAPSHOT_CASES))
def test_payload_matches_its_snapshot(tmp_path: Path, name: str) -> None:
    fixture, command, args = _SNAPSHOT_CASES[name]
    root = build_activation_project(tmp_path) if fixture == "activation" else build_deactivation_project(tmp_path)

    result = _run(root, command, *args)

    assert result.exit_code == 0, result.output
    actual = json.dumps(_payload(result), indent=2, ensure_ascii=False).replace(str(root), "<ROOT>") + "\n"
    snapshot = _SNAPSHOT_DIR / f"{name}.json"
    if os.environ.get("UPDATE_SNAPSHOT") == "1":
        snapshot.parent.mkdir(parents=True, exist_ok=True)
        snapshot.write_text(actual, encoding="utf-8")
    assert actual == snapshot.read_text(encoding="utf-8")


# --------------------------------------------------------------------------- #
# Step-removal warnings of a mission-type activation reach the payload (FR-005)
# --------------------------------------------------------------------------- #


def _patch_step_removal(monkeypatch: pytest.MonkeyPatch) -> None:
    """A mission-type activation that drops ``review`` while WP02 of ``live-mission`` is in ``for_review``."""
    from types import SimpleNamespace

    from specify_cli.charter_activate import AffectedMission, StepRemovalWarning

    monkeypatch.setattr(
        "charter.activation.mission_type_profiles.resolve_mission_type_context",
        lambda *_args, **_kwargs: SimpleNamespace(action_sequence=["specify", "plan", "review"]),
    )
    monkeypatch.setattr(
        "specify_cli.cli.commands.charter.mission_type.resolve_layered_roster",
        lambda _root: {"software-dev": SimpleNamespace(action_sequence=["specify", "plan"])},
    )
    monkeypatch.setattr(
        "specify_cli.charter_activate.scan_inflight_missions",
        lambda removed, _specs: [StepRemovalWarning(step, [AffectedMission("live-mission", "WP02", "for_review")]) for step in removed],
    )


_STEP_REMOVAL_WARNING = "Step 'review' removed by mission-type override. Affected missions: live-mission (WP02, currently in lane 'for_review')"


def test_a_step_removal_warning_reaches_the_json_warnings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = build_activation_project(tmp_path)
    _patch_step_removal(monkeypatch)

    result = _run(root, "activate", "mission-type", "software-dev")

    assert result.exit_code == 0, result.output
    assert _payload(result)["warnings"][0] == _STEP_REMOVAL_WARNING


def test_the_step_removal_warning_text_is_unchanged(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = build_activation_project(tmp_path)
    _patch_step_removal(monkeypatch)

    result = _run(root, "activate", "mission-type", "software-dev", json_output=False)

    assert result.exit_code == 0, result.output
    assert result.stdout.startswith(
        "⚠ Step 'review' removed by mission-type override.\n  Affected missions:\n  - live-mission (WP02, currently in lane 'for_review')\n"
    )
