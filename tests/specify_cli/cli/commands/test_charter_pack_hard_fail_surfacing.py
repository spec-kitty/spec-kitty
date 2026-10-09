"""A pack the merge REFUSED must not be reported healthy (the WP08 join).

WP08 minted five hard-fail conflict classes (``unresolved_edge_endpoint``,
``ambiguous_edge_endpoint``, ``malformed_urn``, ``kind_mismatch``,
``layer_rule_violation``) and made :func:`charter.offering.drg.merge_three_layers`
*raise* :class:`OrgDRGConflictError` for them. Every CLI collector caught that
raise and wrote it to ``collision_warnings`` — an advisory channel no verdict
reads. ``CharterPackHealthReport.healthy`` reads ``org_drg["errors"]`` only. So a
graph the merge layer refused to assemble came back::

    RC=0, profile_health.healthy=True, org_drg.errors=[]
    org_drg.collision_warnings=[{... "resolution": "hard_fail"}]

Two tests existed on either side of the seam and neither owned it: WP08 pinned
the merge-layer refusal (``tests/charter_offering/test_drg_merge.py``) and a later WP
pinned the collector's *non-raising* dangling-endpoint path
(``test_doctor_charter_packs_org_layer.py``). Nothing exercised a collector against
a merge that actually raised. That untested join is the root cause, so these
tests live at the CLI surface the operator reads.

**Monotonicity is the acceptance criterion.** Before this fold, adding a second
defect made the report *greener*, because the hard-fail raise aborted the
``try`` before ``validate_dangling_references`` could run::

    ONLY dangling qualified URN   → RC=1  healthy=False
    ONLY bare unresolved endpoint → RC=0  healthy=True     <- refused, reported clean
    BOTH                          → RC=0  healthy=True     <- more breakage, greener

A health verdict that improves when you break more is worse than no verdict:
it actively misleads. Each defect alone, and both together, must be unhealthy.
"""

from __future__ import annotations

import json
import shutil
from io import StringIO
from pathlib import Path
from textwrap import dedent
from unittest.mock import patch

import pytest
from rich.console import Console
from typer.testing import CliRunner

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_REPO_ROOT: Path = Path(__file__).resolve().parents[4]
_FIXTURE_ORG_PACK: Path = _REPO_ROOT / "tests" / "architectural" / "_fixtures" / "org_packs" / "example_org"

runner = CliRunner()

#: A fully-qualified endpoint whose ``<kind>:`` prefix is a real ``NodeKind``
#: but whose id binds to no node. ``merge_three_layers`` keeps the edge and only
#: WARNs (a sibling pack could supply the node), so the merge RETURNS; the
#: finding is raised by the post-merge ``validate_dangling_references`` pass.
_DANGLING_TOKEN = "styleguide:plain-languagee"

#: A BARE endpoint id the fragment does not declare and no layer supplies.
#: The bridge cannot guess a kind for it, so this is an ``unresolved_edge_endpoint``
#: hard failure and ``merge_three_layers`` RAISES — there is no merged graph.
_UNRESOLVED_TOKEN = "no-such-bare-node"

_UNRESOLVED_EDGE = f"  - source: sox-controls\n    target: {_UNRESOLVED_TOKEN}\n    relation: refines\n"


def _write_repo(root: Path, *, dangling: bool = False, unresolved: bool = False) -> Path:
    """Materialise a repo with the example org pack, optionally sabotaged.

    The two sabotages are deliberately independent: ``dangling`` survives the
    merge, ``unresolved`` aborts it. Composing them is the whole point.
    """
    pack_dest = root / "example_org"
    shutil.copytree(_FIXTURE_ORG_PACK, pack_dest)
    kittify = root / ".kittify"
    kittify.mkdir(exist_ok=True)
    (kittify / "config.yaml").write_text(
        dedent(
            f"""\
            charter_packs:
              org:
                packs:
                  - name: example-org
                    local_path: {pack_dest}
            """
        ),
        encoding="utf-8",
    )

    fragment = pack_dest / "drg" / "fragment.yaml"
    text = fragment.read_text(encoding="utf-8")
    if dangling:
        text = text.replace("styleguide:plain-language", _DANGLING_TOKEN)
    if unresolved:
        text = text + _UNRESOLVED_EDGE
    fragment.write_text(text, encoding="utf-8")
    return root


#: ``(case_id, dangling, unresolved, expect_healthy)`` — the monotonicity table.
#: The clean row is the discriminator: a gate that flags everything is worthless,
#: so the fix must keep an unmodified pack green.
_MONOTONICITY_TABLE = [
    pytest.param(False, False, True, id="clean"),
    pytest.param(True, False, False, id="only-dangling-qualified-urn"),
    pytest.param(False, True, False, id="only-bare-unresolved-endpoint"),
    pytest.param(True, True, False, id="both"),
]


def _doctor_charter_packs_json(repo_root: Path) -> tuple[int, dict[str, object]]:
    """Invoke ``doctor charter-packs --json`` and return ``(exit_code, payload)``.

    ``merge_three_layers`` emits operator WARNINGs on stderr, which ``CliRunner``
    interleaves with stdout, so the payload is sliced from the first ``{``
    rather than parsed from the raw output.
    """
    from specify_cli.cli.commands.doctor import app as doctor_app

    with patch(
        "specify_cli.cli.commands.doctor.locate_project_root",
        return_value=repo_root,
    ):
        result = runner.invoke(doctor_app, ["charter-packs", "--json"])

    brace = result.output.find("{")
    assert brace != -1, f"no JSON payload in output: {result.output!r}"
    payload = json.loads(result.output[brace:])
    assert isinstance(payload, dict)
    return result.exit_code, payload


@pytest.mark.parametrize(("dangling", "unresolved", "expect_healthy"), _MONOTONICITY_TABLE)
def test_doctor_charter_packs_is_monotonic_in_org_pack_defects(
    tmp_path: Path,
    dangling: bool,
    unresolved: bool,
    expect_healthy: bool,
) -> None:
    """More breakage must never read greener.

    RED before this fold on the ``only-bare-unresolved-endpoint`` and ``both``
    rows: both returned RC=0 with ``healthy=True`` for a graph
    ``merge_three_layers`` had refused to assemble.
    """
    repo_root = _write_repo(tmp_path, dangling=dangling, unresolved=unresolved)

    exit_code, payload = _doctor_charter_packs_json(repo_root)

    profile_health = payload["profile_health"]
    assert isinstance(profile_health, dict)
    assert profile_health["healthy"] is expect_healthy, (
        f"healthy={profile_health['healthy']} for dangling={dangling} unresolved={unresolved}; org_drg={payload['org_drg']}"
    )
    assert exit_code == (0 if expect_healthy else 1), (
        f"exit code must track the verdict; got RC={exit_code} for healthy={expect_healthy}. Output payload: {payload['org_drg']}"
    )


def test_hard_fail_conflict_reaches_the_channel_the_verdict_reads(
    tmp_path: Path,
) -> None:
    """``org_drg['errors']`` must name the refused conflict class and its token.

    ``collision_warnings`` is not a substitute: no verdict, exit code, or
    renderer treats it as fatal. The operator needs the *kind* (which of the
    five refusal classes fired) and the *token* (which endpoint) to act.
    """
    from specify_cli.cli.commands.doctor import _collect_org_layer_data

    repo_root = _write_repo(tmp_path, unresolved=True)

    result = _collect_org_layer_data(repo_root)

    errors = result["errors"]
    assert isinstance(errors, list)
    assert any("unresolved_edge_endpoint" in e for e in errors), f"the refusal class must be named in errors; got {errors}"
    assert any(_UNRESOLVED_TOKEN in e for e in errors), f"the offending token must be named in errors; got {errors}"


def test_hard_fail_conflict_keeps_its_structured_collision_record(
    tmp_path: Path,
) -> None:
    """Routing to ``errors`` must ADD a verdict, not delete the detail.

    ``errors`` is a flat list of strings — enough to fail the report, too lossy
    to drive tooling. The typed record (kind / target_id / conflicting_layers /
    resolution) stays available so a consumer can still discriminate.
    """
    from specify_cli.cli.commands.doctor import _collect_org_layer_data

    repo_root = _write_repo(tmp_path, unresolved=True)

    result = _collect_org_layer_data(repo_root)

    warnings = result["collision_warnings"]
    assert isinstance(warnings, list)
    hard = [w for w in warnings if isinstance(w, dict) and w.get("resolution") == "hard_fail"]
    assert hard, f"the typed hard-fail record must survive; got {warnings}"
    assert hard[0]["kind"] == "unresolved_edge_endpoint"
    assert hard[0]["target_id"] == _UNRESOLVED_TOKEN


def test_charter_status_reports_a_hard_fail_in_its_errors_array(
    tmp_path: Path,
) -> None:
    """``charter status``'s collector shares the defect and must share the fix.

    Its docstring already claims ``errors`` is the channel for "any org edge
    endpoint that binds to nothing" — a bare unresolved endpoint binds to
    nothing in the strongest possible sense: the merge refused it outright.
    """
    from specify_cli.cli.commands.charter import _collect_org_layer_status

    repo_root = _write_repo(tmp_path, unresolved=True)

    result = _collect_org_layer_status(repo_root)

    errors = result["errors"]
    assert isinstance(errors, list)
    assert any(_UNRESOLVED_TOKEN in e for e in errors), f"charter status must report the refusal as an error; got {errors}"


def test_human_section_does_not_print_a_clean_dangling_verdict_after_a_refusal(
    tmp_path: Path,
) -> None:
    """ "Not checked" and "checked, found nothing" are different answers.

    When the merge raises there is no merged graph, so the completeness check
    genuinely cannot run. Printing ``dangling endpoints: none`` would assert a
    result the command never computed — the same false-clean this mission is
    about, one line further down.
    """
    from specify_cli.cli.commands.doctor import _render_org_layer_section

    repo_root = _write_repo(tmp_path, unresolved=True)

    buf = StringIO()
    _render_org_layer_section(repo_root, Console(file=buf, highlight=False, markup=False, width=200))
    output = buf.getvalue()

    assert "dangling endpoints: none" not in output, (
        f"the merge refused this graph, so the dangling check never ran; claiming 'none' invents a verdict. Got:\n{output}"
    )
    assert _UNRESOLVED_TOKEN in output, f"the human section must name the refused endpoint; got:\n{output}"


def test_dangling_endpoints_key_is_always_present(tmp_path: Path) -> None:
    """A conditional key cannot distinguish "clean" from "never ran".

    ``dangling_endpoints`` was only written when non-empty, so its absence
    conflated "the check ran and found nothing" with "the check did not run" —
    the exact ambiguity :func:`_collect_org_layer_data` names ~80 lines below
    as the reason its broad handler is no longer a bare ``pass``.
    """
    from specify_cli.cli.commands.doctor import _collect_org_layer_data

    clean = _collect_org_layer_data(_write_repo(tmp_path / "clean"))
    assert clean["dangling_endpoints"] == []

    broken = _collect_org_layer_data(_write_repo(tmp_path / "broken", dangling=True))
    dangling = broken["dangling_endpoints"]
    assert isinstance(dangling, list)
    assert any(_DANGLING_TOKEN in e for e in dangling), dangling


def test_org_drg_conflict_error_partitions_fatal_from_advisory() -> None:
    """The ``resolution_applied`` Literal needs a reader, or it is decoration.

    ``merge_three_layers`` accumulates advisory conflicts (``org_override`` and
    friends) alongside fatal ones and raises with the *whole* list, so the
    exception type genuinely carries both. Consumers were left to re-derive the
    distinction from a string field and every one of them skipped it. Expose the
    partition on the type that owns the invariant.
    """
    from charter.offering.drg.merge import OrgDRGConflict, OrgDRGConflictError

    advisory = OrgDRGConflict(
        kind="node_override",
        conflicting_layers=["org:example-org"],
        target_id="directive:sox-controls",
        built_in_value=None,
        org_value={},
        project_value=None,
        resolution_applied="org_override",
    )
    fatal = OrgDRGConflict(
        kind="unresolved_edge_endpoint",
        conflicting_layers=["org:example-org"],
        target_id=_UNRESOLVED_TOKEN,
        built_in_value=None,
        org_value={},
        project_value=None,
        resolution_applied="hard_fail",
    )

    error = OrgDRGConflictError([advisory, fatal])

    assert error.hard_failures == [fatal]
    assert error.advisory_conflicts == [advisory]
    assert error.conflicts == [advisory, fatal], "the full list stays the primary payload — the properties are a view, not a replacement"
