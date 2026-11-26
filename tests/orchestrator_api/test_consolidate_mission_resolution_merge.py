"""``orchestrator-api consolidate-mission`` carries this Mission's two behaviours through its existing doors (WP09).

* FR-004 / C-007: a merge on an approved code lane that carries its own content and that no review
  approval of the lane reaches (``RESOLUTION_MERGE_UNREVIEWED``) is refused before the first lane
  is consolidated, with the ``PREFLIGHT_FAILED`` envelope and the code in
  ``data.preflight_error_code`` / ``data.preflight_error_codes``. This path has no rollback door,
  so no branch may move. The contract version is bumped and the code is documented.
* FR-001 / C-006: a stale approved lane reports the one approved-lane route the shared renderer
  prints (reopen, re-enter, ``--incorporate <sibling>``, resolve, ``for_review``, independent
  approval, re-run), through ``consolidate_lane_into_mission``; this module adds no wording.

Driven through the REAL ``spec-kitty orchestrator-api`` CLI over real git, except the probe-error
cell, which patches the probe and therefore runs the CLI in process.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from tests.terminus.conftest import CoordMission, blob_present_at, git_rev, run_terminus
from tests.terminus.post_approval_support import (
    LATE_CONTENT,
    LATE_PATH,
    WP01_PATH,
    add_post_approval_commit,
    build_post_approval_coord_mission,
    build_post_approval_lanes_mission,
    lane_worktree,
)
from tests.terminus.rollback_harness import flat, ref_shas

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_CODE = "RESOLUTION_MERGE_UNREVIEWED"
_LATE_CODE = "LANE_MOVED_AFTER_APPROVAL"
_TARGET = "develop"
#: The contract version that introduced ``RESOLUTION_MERGE_UNREVIEWED`` (a historical fact, not the current version).
_VERSION = "1.31.0"
_DOC = Path(__file__).resolve().parents[2] / "docs" / "api" / "orchestrator-api.md"
_SKILL_REFERENCE = _DOC.parents[2] / "src/charter/offering/skills/spec-kitty-orchestrator-api-operator/references/orchestrator-api-contract.md"


def _consolidate_mission(mission: CoordMission) -> subprocess.CompletedProcess[str]:
    return run_terminus(mission, ["orchestrator-api", "consolidate-mission", "--mission", mission.slug, "--strategy", "squash"])


def _envelope_from(stdout: str) -> dict[str, object]:
    """The JSON envelope: the last non-empty stdout line (the success path's branch cleanup prints first)."""
    lines = [line for line in stdout.splitlines() if line.strip()]
    assert lines, f"expected a JSON envelope on stdout. stdout={stdout!r}"
    envelope = json.loads(lines[-1])
    assert isinstance(envelope, dict)
    return envelope


def _data(envelope: dict[str, object]) -> dict[str, object]:
    data = envelope["data"]
    assert isinstance(data, dict), envelope
    return data


def _build(tmp_path: Path, topology: str) -> CoordMission:
    if topology == "coord":
        return build_post_approval_coord_mission(tmp_path, target_branch=_TARGET)
    return build_post_approval_lanes_mission(tmp_path, target_branch=_TARGET)


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True).stdout.strip()


def _add_merge(mission: CoordMission, *, own_content: bool) -> str:
    """Make lane-a's tip a hand merge of its approved tip and the Mission branch tip; return the merge SHA.

    The shape of WP05's ``_add_evil_merge`` (``tests/consolidation/test_approved_bound_residuals.py``),
    copied rather than imported (it is private to that module). The second parent is an ancestor of the
    lane, so with *own_content* the merge's only own change is ``LATE_PATH``; without it the merge's tree
    is the lane tip's tree and the merge carries nothing of its own.
    """
    worktree = lane_worktree(mission, "lane-a")
    anchor = git_rev(mission.repo, mission.coord_branch)
    if own_content:
        late_file = worktree / LATE_PATH
        late_file.parent.mkdir(parents=True, exist_ok=True)
        late_file.write_text(LATE_CONTENT, encoding="utf-8")
        _git(worktree, "add", LATE_PATH)
    tree = _git(worktree, "write-tree")
    merge = _git(worktree, "commit-tree", tree, "-p", "HEAD", "-p", anchor, "-m", "merge: hand merge of the Mission branch")
    _git(worktree, "reset", "--hard", merge)
    return merge


# --- FR-004: the unreviewed resolution merge is refused before any lane merges ------------------------------------


@pytest.mark.parametrize("topology", ["lanes", "coord"])
def test_unreviewed_resolution_merge_is_refused_before_any_lane_merges(tmp_path: Path, topology: str) -> None:
    mission = _build(tmp_path, topology)
    merge = _add_merge(mission, own_content=True)
    before = ref_shas(mission)

    result = _consolidate_mission(mission)

    output = flat(result)
    assert result.returncode != 0, f"an unreviewed resolution merge must be refused. output={output}"
    envelope = _envelope_from(result.stdout)
    assert envelope["success"] is False, envelope
    assert envelope["error_code"] == "PREFLIGHT_FAILED", envelope
    data = _data(envelope)
    assert data["preflight_error_code"] == _CODE, envelope
    assert data["preflight_error_codes"] == [_CODE], envelope
    assert merge[:7] in str(data["errors"]), "the merge is named by its short SHA"
    assert "no attestation flag" not in str(data["errors"]), "the text names no attestation, so no CLI-only note"
    assert ref_shas(mission) == before, f"no branch tip may move (this path has no rollback). output={output}"
    assert not blob_present_at(mission.repo, _TARGET, LATE_PATH), "the merge's own content must not reach the target"
    assert not blob_present_at(mission.repo, mission.coord_branch, LATE_PATH), "nor the Mission branch"


def test_two_codes_keep_first_code_first(tmp_path: Path) -> None:
    """A late commit on lane-b and an unreviewed merge on lane-a: both codes, in the order the text names them."""
    from specify_cli.consolidation.approved_bound import refusal_codes

    mission = _build(tmp_path, "lanes")
    _add_merge(mission, own_content=True)
    late = add_post_approval_commit(mission, "lane-b", path="src/beta/late.py")
    before = ref_shas(mission)

    result = _consolidate_mission(mission)

    data = _data(_envelope_from(result.stdout))
    assert result.returncode != 0, flat(result)
    errors = data["errors"]
    assert isinstance(errors, list) and errors
    text = "\n".join(str(error) for error in errors)
    codes = list(refusal_codes(text))
    assert data["preflight_error_codes"] == codes, data
    assert codes == [_LATE_CODE, _CODE], data  # WP05 renders the resolution-merge block last
    assert data["preflight_error_code"] == _LATE_CODE, data
    assert late[:7] in text, text
    assert ref_shas(mission) == before, flat(result)


def test_control_clean_merge_consolidates(tmp_path: Path) -> None:
    """A hand merge with no content of its own is not refused by the new code; the Mission lands."""
    mission = _build(tmp_path, "lanes")
    _add_merge(mission, own_content=False)

    result = _consolidate_mission(mission)

    output = flat(result)
    envelope = _envelope_from(result.stdout)
    assert _CODE not in output, output
    assert result.returncode == 0, output
    assert envelope["success"] is True, output
    assert blob_present_at(mission.repo, _TARGET, WP01_PATH), output


def test_probe_error_does_not_merge(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """NFR-002: a git probe error in the resolution-merge check fails closed before any lane merges.

    The probe is patched, so the CLI runs in process (a subprocess cannot be patched). ``GitProbeError``
    is a ``RuntimeError``, which ``consolidate-mission`` envelopes as ``PREFLIGHT_FAILED`` with no code.
    """
    from specify_cli import app as cli_app
    from specify_cli.consolidation.git_probes import GitProbeError

    mission = _build(tmp_path, "lanes")
    _add_merge(mission, own_content=True)
    before = ref_shas(mission)

    def _probe_fails(*_args: object, **_kwargs: object) -> list[str]:
        raise GitProbeError("git show --remerge-diff is unavailable")

    monkeypatch.setattr("specify_cli.consolidation.approved_bound.merge_own_changed_paths", _probe_fails)
    monkeypatch.chdir(mission.repo)
    monkeypatch.setenv("HOME", str(mission.home))
    monkeypatch.setenv("SPEC_KITTY_NO_UPGRADE_CHECK", "1")
    monkeypatch.delenv("SPEC_KITTY_ORIGIN_CHECK", raising=False)

    result = CliRunner().invoke(cli_app, ["orchestrator-api", "consolidate-mission", "--mission", mission.slug, "--strategy", "squash"])

    assert result.exit_code != 0, result.output
    envelope = _envelope_from(result.stdout)
    assert envelope["success"] is False and envelope["error_code"] == "PREFLIGHT_FAILED", envelope
    data = _data(envelope)
    assert "remerge-diff is unavailable" in str(data["errors"]), envelope
    assert "preflight_error_code" not in data, "a probe error is not a refusal code"
    assert ref_shas(mission) == before, "no lane may merge on a probe error"
    assert not blob_present_at(mission.repo, mission.coord_branch, LATE_PATH)


# --- FR-001 / C-006: the stale approved lane prints the approved-lane route through this path ---------------------


def test_stale_approved_lane_prints_the_approved_lane_route(tmp_path: Path) -> None:
    """Both lanes approved, adjacent hunks of one file: lane-a lands on the Mission branch, lane-b is stale.

    The envelope's ``data.errors`` carries the shared renderer's route: reopen (the send-back), re-entry and
    ``--incorporate lane-a`` with ``--agent``, ``for_review``, the independent re-approval, then the re-run.
    No ``git merge``, no ``cd .worktrees``, no bare re-entry for the approved work package without the reopen.
    """
    from tests.consolidation.stale_sibling_lane_support import POPUP, build_stale_sibling_mission

    scenario = build_stale_sibling_mission(tmp_path)
    mission = scenario.mission
    target_before = git_rev(mission.repo, mission.target_branch)

    result = run_terminus(mission, ["orchestrator-api", "consolidate-mission", "--mission", mission.slug, "--strategy", "squash"])

    envelope = _envelope_from(result.stdout)
    assert result.returncode != 0, flat(result)
    assert envelope["error_code"] == "PREFLIGHT_FAILED", envelope
    data = _data(envelope)
    errors = data["errors"]
    assert isinstance(errors, list) and errors, data
    text = "\n".join(str(error) for error in errors)
    assert "Lane lane-b is stale" in text and POPUP in text, text
    slug = mission.slug
    reopen = f"spec-kitty agent tasks move-task WP02 --to planned --review-feedback-file <file> --mission {slug}"
    route = [
        f"spec-kitty agent action implement WP02 --mission {slug} --agent <agent>",
        f"spec-kitty agent action implement WP02 --mission {slug} --incorporate lane-a --agent <agent>",
        f"spec-kitty agent tasks move-task WP02 --to for_review --mission {slug}",
        f"spec-kitty consolidate --mission {slug}",
    ]
    assert reopen in " ".join(text.split()), text
    commands = [line.strip() for line in text.splitlines() if line.strip().startswith("spec-kitty ")]
    assert commands == route, text
    assert "An independent reviewer reviews WP02 and approves it again" in text, text
    assert scenario.lane_a_branch in text, "the sibling lane is named with its branch"
    assert not re.search(r"git merge(?! --abort)", text), text
    assert "cd .worktrees" not in text, text
    assert "allowed_error_codes" not in data and "preflight_error_code" not in data, data
    assert git_rev(mission.repo, mission.target_branch) == target_before, "the target never moves on a stale lane"


# --- C-007: the contract version and its documentation ------------------------------------------------------------


def test_contract_version_carries_the_1_31_0_bump() -> None:
    """The refusal code arrived with 1.31.0 (C-007); the CLI reports ``CONTRACT_VERSION`` and a supported provider still passes.

    The exact current version is pinned only in ``tests/specify_cli/orchestrator_api/test_contract_version.py``,
    so a later bump does not turn this cell red.
    """
    from packaging.version import Version

    from specify_cli.orchestrator_api import envelope as envelope_module
    from specify_cli.orchestrator_api.commands import app

    assert Version(envelope_module.CONTRACT_VERSION) >= Version(_VERSION)
    assert envelope_module.MIN_PROVIDER_VERSION == "0.1.0"
    result = CliRunner().invoke(app, ["contract-version", "--provider-version", "0.1.0"])
    assert result.exit_code == 0, result.output
    envelope = _envelope_from(result.stdout)
    assert envelope["contract_version"] == envelope_module.CONTRACT_VERSION
    assert _data(envelope)["api_version"] == envelope_module.CONTRACT_VERSION


def test_doc_contract_version_matches_envelope() -> None:
    from specify_cli.orchestrator_api.envelope import CONTRACT_VERSION

    page = _DOC.read_text(encoding="utf-8")
    section = page.split("## Contract Version", 1)[1]
    match = re.search(r"^- `CONTRACT_VERSION`: `([0-9.]+)`", section, re.MULTILINE)
    assert match is not None, "the Contract Version section names CONTRACT_VERSION"
    assert match.group(1) == CONTRACT_VERSION
    entry = re.search(rf"^- `{re.escape(_VERSION)}` — [^\n]*(?:\n  [^\n]*)*", page, re.MULTILINE)
    assert entry is not None and _CODE in entry.group(0), "a 1.31.0 history entry naming the code"
    assert re.search(rf"^\| `{_CODE}` \| \({re.escape(_VERSION)}", page, re.MULTILINE), "a preflight code row"
    reference = _SKILL_REFERENCE.read_text(encoding="utf-8")
    assert re.search(rf"^\| `{_CODE}` \| .*{re.escape(_VERSION)}", reference, re.MULTILINE), "the operator-skill reference row"
