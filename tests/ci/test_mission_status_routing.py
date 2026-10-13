"""Pin the CI routing of the Mission Status API conformance goldens (mission mission-status-read-api-overview, FR-008, AC-8e, AC-8f).

The goldens tree joins the ``contract_tools`` router group, so a golden-only diff selects ``tests (contract tools)``, the one home of
the golden-honesty test, and no other Python gate. The Packs advisory corpus lane deselects the new module, so it runs exactly once.
Each revert row edits a temporary copy of the workflow and requires the pin to turn red.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from scripts.ci.fleet_verdict import applicable_workflows
from scripts.ci.gate_selection import load_router, select_gates, select_modules
from tests.architectural import _gate_coverage as gc

pytestmark = pytest.mark.fast

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github" / "workflows"
ROUTER_PATH = WORKFLOWS / "ci-router.yml"
PACKS_PATH = WORKFLOWS / "packs.yml"
GOLDENS_GLOB = "services/mission-status-api/src/test/resources/conformance/**"
GOLDEN_ONLY_PATH = "services/mission-status-api/src/test/resources/conformance/manifest.json"
OTHER_SERVICE_PATH = "services/mission-status-api/src/main/java/Example.java"
NEW_MODULE = "tests/contract/test_mission_status_conformance.py"
PACKS_CORPUS_JOB = "built-in-corpus-suite"
GROUP = "contract_tools"
# The 35 contract modules the advisory corpus command deselected before this module, plus the new one.
DESELECTED_CONTRACT_MODULES_FLOOR = 36


def _contract_tools_jobs() -> frozenset[str]:
    return frozenset(job for job, groups in load_router().job_gates.items() if GROUP in groups)


def _packs_gate(path: Path = PACKS_PATH) -> gc.Gate:
    gates = [gate for gate in gc.parse_workflow(path) if gate.job == PACKS_CORPUS_JOB]
    assert len(gates) == 1, "the Packs corpus job runs exactly one pytest command"
    return gates[0]


def _deselected_contract_modules(path: Path = PACKS_PATH) -> list[str]:
    return [entry for entry in _packs_gate(path).ignores if entry.startswith("tests/contract/")]


def test_the_goldens_glob_is_in_the_contract_tools_group_exactly_once_and_in_no_other_group() -> None:
    filters = load_router().filters

    assert filters[GROUP].count(GOLDENS_GLOB) == 1
    assert [group for group, globs in filters.items() if GOLDENS_GLOB in globs] == [GROUP]


def test_a_contract_tools_gated_job_exists_to_receive_the_selection() -> None:
    assert _contract_tools_jobs()


def test_a_golden_only_diff_selects_contract_tools_and_nothing_else_in_python() -> None:
    router = load_router()

    selection = select_gates([GOLDEN_ONLY_PATH], router=router)

    assert selection.matched_groups == {GROUP}
    assert selection.selected_jobs == router.always_on_jobs | _contract_tools_jobs()
    assert selection.selected_code_shards == frozenset()
    assert not selection.unmatched_src
    assert select_modules([GOLDEN_ONLY_PATH], router=router) == frozenset()


def test_a_services_diff_outside_the_conformance_tree_selects_no_code_shard_gate() -> None:
    router = load_router()

    selection = select_gates([OTHER_SERVICE_PATH], router=router)

    assert GROUP not in selection.matched_groups
    assert selection.selected_code_shards == frozenset()
    assert select_modules([OTHER_SERVICE_PATH], router=router) == frozenset()


def test_a_python_src_change_selects_the_status_group_but_not_the_mission_status_api_workflow() -> None:
    paths = ["src/specify_cli/status/reducer.py"]
    selection = select_gates(paths, router=load_router())

    assert GOLDENS_GLOB not in load_router().filters["status"]
    assert "status" in selection.matched_groups
    # The native matrix lives in the separate workflow; the path filter, read the way the fleet verdict reads it, never picks it up.
    assert "mission-status-api.yml" not in applicable_workflows(ROOT, {"base": {"ref": "main"}}, paths)
    assert "mission-status-api.yml" in applicable_workflows(ROOT, {"base": {"ref": "main"}}, [OTHER_SERVICE_PATH])


def test_the_packs_advisory_corpus_command_deselects_the_new_module_exactly_once() -> None:
    deselected = _deselected_contract_modules()

    assert deselected.count(NEW_MODULE) == 1
    assert (ROOT / NEW_MODULE).is_file()
    assert all((ROOT / entry).is_file() for entry in deselected), "every deselected contract module exists"


def test_the_discovered_deselect_count_sees_the_floor() -> None:
    deselected = _deselected_contract_modules()

    assert len(deselected) >= DESELECTED_CONTRACT_MODULES_FLOOR, f"the Packs command deselects {len(deselected)} contract modules"
    assert len(set(deselected)) == len(deselected), "no duplicate deselect entry"


def test_removing_the_goldens_glob_from_a_router_copy_turns_the_routing_red(tmp_path: Path) -> None:
    broken = tmp_path / "ci-router.yml"
    text = ROUTER_PATH.read_text(encoding="utf-8")
    needle = f"              - '{GOLDENS_GLOB}'\n"
    assert text.count(needle) == 1, "control: the router names the glob once"
    broken.write_text(text.replace(needle, ""), encoding="utf-8")

    selection = select_gates([GOLDEN_ONLY_PATH], router=load_router(broken))

    assert selection.matched_groups != {GROUP}, "a router without the glob must select nothing for a golden-only diff"


def test_removing_the_deselect_token_from_a_packs_copy_turns_the_pin_red(tmp_path: Path) -> None:
    broken = tmp_path / "packs.yml"
    text = PACKS_PATH.read_text(encoding="utf-8")
    token = f" --deselect {NEW_MODULE}"
    assert text.count(token) == 1, "control: the Packs command names the token once"
    broken.write_text(text.replace(token, ""), encoding="utf-8")

    assert NEW_MODULE not in _deselected_contract_modules(broken)
    assert len(_deselected_contract_modules(broken)) < DESELECTED_CONTRACT_MODULES_FLOOR


GITATTRIBUTES_LINE = f"{GOLDENS_GLOB} -text"
CRLF_FIXTURE = f"{GOLDENS_GLOB[:-2]}crlf-and-listing/crlf-and-lf-twin/kitty-specs/crlf-mission/status.events.jsonl"


def test_gitattributes_scopes_one_text_off_line_to_the_conformance_tree() -> None:
    lines = (ROOT / ".gitattributes").read_text(encoding="utf-8").splitlines()

    assert lines.count(GITATTRIBUTES_LINE) == 1
    assert not [line for line in lines if line.strip() and not line.startswith("#") and line.split()[0] in {"*", "**", "*.jsonl", "*.json"} and "-text" in line], (
        "never a global -text rule"
    )


def test_git_reads_the_crlf_fixture_as_unset_text_so_checkout_keeps_its_bytes() -> None:
    out = subprocess.run(["git", "-C", str(ROOT), "check-attr", "text", "--", CRLF_FIXTURE], check=True, capture_output=True, text=True).stdout

    assert out.strip().endswith("text: unset"), out
    assert b"\r\n" in (ROOT / CRLF_FIXTURE).read_bytes()
