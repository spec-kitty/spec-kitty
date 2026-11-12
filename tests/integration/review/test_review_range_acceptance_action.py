"""Acceptance: ``agent action review`` (render sites 2 and 3) prints the WP review range (#7578, WP07).

ATDD-first (C-010): committed red before any production change. Site 2 (the review prompt) and
site 3 (its stdout finalize summary) are driven through the production entry point, the workflow
Typer app's ``review`` command; site 1 (``spec-kitty next``'s ``build_prompt("review", ...)``) is
rendered on the same fixture copy for comparison. Per review-ready fixture:

* exact provenance: ``[recorded]``, ``base: <base12> (window open)``, ``tip:  <tip12> (for_review submission)``;
* SC-003: the site-2 block is byte-identical to the site-1 block, and site 3 prints that block's
  header line and ``git log`` command line verbatim, and names no other ``..`` range;
* FR-012: ``ReviewPromptMetadata.base_ref`` is the full range base SHA;
* the commit list and ``CHANGED FILES`` lines are exact, and the printed commands run as written
  through ``bash -c`` (FR-008), the ``git log`` output listing exactly the listed commits;
* C-001: no patch text and no diff file; NFR-005: byte-identical under two hash seeds.

FR-013 / NFR-004: an unavailable range is a notice on sites 2 and 3, exit 0, never a refusal.
Operator rulings Q7 and Q9: ``OWNED_REVIEW_BASE_UNAVAILABLE`` keeps its code and message prefix and fires
only for an owned single_branch checkout whose scoped range is unavailable (its reason in words, not the raw
gap value) or whose work package declares no ``owned_files``.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from mission_runtime import OwnedRefusalCode
from runtime.next.prompt_builder import build_prompt
from specify_cli.cli.commands import next_cmd
from specify_cli.cli.commands.agent import workflow as workflow_module
from specify_cli.review.prompt_metadata import read_review_prompt_metadata
from tests.integration.conftest import OwnedCheckouts
from tests.integration.review.review_range_fixtures import (
    HARNESS_VARIABLES,
    REVIEW_READY,
    REVIEWED_WP,
    ReviewFixture,
    ReviewTemplates,
    assert_no_patch_text,
    make_owned_range_unavailable,
    review_block,
    run_printed_command,
    snapshot_tree,
)
from tests.integration.test_owned_lifecycle_acceptance_review import _commit_all, _owned_next, _owned_review_ready
from tests.runtime._next_mission_scaffold import analysis_is_current
from tests.terminus.canceled_dependency_support import ACTOR
from tests.terminus.mixed_lane_support import transition

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_MISSION_TYPE = "software-dev"
_AGENT = "claude"
_UNAVAILABLE_COMMAND = "  (no deterministic range; inspect `spec-kitty agent tasks status` and the WP's commits)"
_PROMPT_LINE = re.compile(r"^\s*cat (\S+\.md)\s*$", re.MULTILINE)
_RANGE_TOKEN = re.compile(r"[0-9A-Za-z_/.~^-]*[0-9A-Za-z_~^]\.\.[0-9A-Za-z_~^][0-9A-Za-z_/.~^-]*")

runner = CliRunner()


@dataclass(frozen=True)
class _Review:
    """One ``agent action review`` run (sites 2 and 3) and the site-1 prompt rendered on the same copy just before it."""

    fixture: ReviewFixture
    site1: str
    exit_code: int
    stdout: str
    prompt_file: Path | None
    prompt: str
    metadata: dict[str, str]


@pytest.fixture(scope="module")
def templates(tmp_path_factory: pytest.TempPathFactory) -> ReviewTemplates:
    return ReviewTemplates(tmp_path_factory.mktemp("review-range-action"))


def _site1(fx: ReviewFixture) -> str:
    with fx.environment():
        text, _prompt = build_prompt("review", fx.feature_dir, fx.mission_slug, REVIEWED_WP, _AGENT, fx.repo, _MISSION_TYPE)
    return text


def _review_args(fx: ReviewFixture) -> list[str]:
    """The ``review`` arguments, after readying a lane fixture for a review claim.

    The lane fixtures keep their Mission on protected ``main``, so the review claim's bookkeeping is
    refused there; their copy lifts the protection in ``.kittify/config.yaml`` (committed; a
    bookkeeping path, so the range is unchanged). On ``lanes`` (and its stamp-stripped copy) the claim's follow-up commit then
    finds an empty changeset (a defect of the claim path, not of the range, reported with WP07),
    so that copy records the ``in_review`` claim up front and the review resumes it without
    ``--agent``. Neither step touches WP02's ``for_review`` submission or its window.
    """
    args = ["review", REVIEWED_WP, "--mission", fx.mission_slug]
    if fx.lane_mission is None:
        return [*args, "--agent", _AGENT]
    config = fx.repo / ".kittify" / "config.yaml"
    config.parent.mkdir(parents=True, exist_ok=True)
    existing = config.read_text(encoding="utf-8") if config.exists() else ""
    if "protected_branches" not in existing:
        config.write_text(existing + "\nprotection:\n  protected_branches: []\n", encoding="utf-8")
        subprocess.run(["git", "add", "-f", str(config)], cwd=fx.repo, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-qm", "test: lift main's protection"], cwd=fx.repo, check=True, capture_output=True)
    if fx.name == "lanes_with_coord":
        return [*args, "--agent", _AGENT]
    with fx.environment():
        transition(fx.lane_mission, REVIEWED_WP, "in_review", actor=ACTOR)
    return args


def _site2(fx: ReviewFixture, args: list[str]) -> tuple[int, str, Path | None]:
    with fx.environment():
        result = runner.invoke(workflow_module.app, args)
    match = _PROMPT_LINE.search(result.output)
    return result.exit_code, result.output, Path(match.group(1)) if match else None


def _run(fx: ReviewFixture) -> _Review:
    args = _review_args(fx)
    site1 = _site1(fx)
    exit_code, stdout, prompt_file = _site2(fx, args)
    prompt = prompt_file.read_text(encoding="utf-8") if prompt_file and prompt_file.is_file() else ""
    metadata = read_review_prompt_metadata(prompt_file) if prompt else {}
    return _Review(fx, site1, exit_code, stdout, prompt_file, prompt, metadata)


class _Reviews:
    """Each review-ready fixture copied and reviewed once per module, for the read-only assertions."""

    def __init__(self, templates: ReviewTemplates, root: Path) -> None:
        self._templates = templates
        self._root = root
        self._done: dict[str, _Review] = {}

    def get(self, name: str) -> _Review:
        if name not in self._done:
            self._done[name] = _run(self._templates.checkout(name, self._root))
        return self._done[name]


@pytest.fixture(scope="module")
def reviews(templates: ReviewTemplates, tmp_path_factory: pytest.TempPathFactory) -> _Reviews:
    return _Reviews(templates, tmp_path_factory.mktemp("reviewed"))


def _section(block: str, heading: str) -> list[str]:
    lines = block.splitlines()
    start = next((index for index, line in enumerate(lines) if line.startswith(heading)), None)
    assert start is not None, f"no {heading!r} section in:\n{block}"
    items: list[str] = []
    for line in lines[start + 1 :]:
        if not line.startswith("  "):
            break
        items.append(line)
    return items


def _command(block: str, prefix: str) -> str:
    matches = [line for line in block.splitlines() if line.startswith(prefix)]
    assert len(matches) == 1, f"expected one {prefix!r} line in:\n{block}"
    return matches[0]


#: The one ``..HEAD`` the review prompt may carry: the anti-pattern checklist's frozen-surface recipe
#: (``review/antipattern_checklist.py`` item 5), a ``<base>`` placeholder the reviewer fills, not a range
#: the prompt computed. The worktree topology's ``diff_command`` was the other source until Q13 (#7590).
_CHECKLIST_HEAD_RECIPE = "`git log --oneline <base>..HEAD -- <frozen-file>` must be empty."


def _head_ranges(prompt: str) -> list[str]:
    """Every prompt line naming a ``..HEAD`` range, the anti-pattern checklist's placeholder recipe excepted."""
    return [line for line in prompt.splitlines() if "..HEAD" in line and line.strip() != _CHECKLIST_HEAD_RECIPE]


def _site2_block(review: _Review) -> str:
    assert review.exit_code == 0, review.stdout
    block = review_block(review.prompt)
    assert block, f"site 2 printed no REVIEW RANGE block:\n{review.prompt}"
    return block


# --------------------------------------------------------------------------- site 2: the prompt


@pytest.mark.parametrize("name", REVIEW_READY)
def test_site2_header_carries_exact_recorded_provenance(reviews: _Reviews, name: str) -> None:
    review = reviews.get(name)
    fx = review.fixture
    block = _site2_block(review)
    assert fx.expected_base and fx.expected_tip
    base12, tip12 = fx.expected_base[:12], fx.expected_tip[:12]

    lines = block.splitlines()
    assert lines[0] == f"REVIEW RANGE ({REVIEWED_WP}): {base12}..{tip12}  [recorded]", block
    assert f"  base: {base12} ({fx.base_label})" in lines
    assert f"  tip:  {tip12} ({fx.tip_label})" in lines
    assert not _head_ranges(review.prompt), review.prompt


@pytest.mark.parametrize("name", REVIEW_READY)
def test_site2_block_equals_site1_block(reviews: _Reviews, name: str) -> None:
    """SC-003: one range, one renderer: the two review entry points print the same block, byte for byte."""
    review = reviews.get(name)
    site1 = review_block(review.site1)

    assert site1, "precondition: site 1 renders the block"
    assert _site2_block(review) == site1


@pytest.mark.parametrize("name", REVIEW_READY)
def test_metadata_base_ref_is_the_range_base(reviews: _Reviews, name: str) -> None:
    """FR-012: the recorded ``ReviewPromptMetadata.base_ref`` is the full base SHA the ``git log`` command carries."""
    review = reviews.get(name)
    log_line = _command(_site2_block(review), "  git log ")

    assert review.metadata["base_ref"] == review.fixture.expected_base
    assert f" {review.metadata['base_ref']}..{review.fixture.expected_tip}" in log_line


@pytest.mark.parametrize("name", REVIEW_READY)
def test_site2_commits_and_changed_files_are_exact(reviews: _Reviews, name: str) -> None:
    review = reviews.get(name)
    fx = review.fixture
    block = _site2_block(review)

    listed = [line.split()[0] for line in _section(block, "IMPLEMENTATION COMMITS")]
    assert listed == [sha[:12] for sha in fx.implementation_shas]
    files = [line for line in _section(block, "CHANGED FILES (owned files, +added -removed):") if not line.startswith("  OUTSIDE OWNED FILES")]
    assert files == [f"  {line}" for line in fx.changed_files]
    for path in fx.excluded_paths:
        assert path not in block


@pytest.mark.parametrize("name", REVIEW_READY)
def test_site2_printed_commands_run_as_written(reviews: _Reviews, name: str) -> None:
    """FR-008: the commands run through ``bash -c``; ``git log`` lists exactly the listed commits."""
    review = reviews.get(name)
    fx = review.fixture
    block = _site2_block(review)

    log_out = run_printed_command(fx.repo, _command(block, "  git log "))
    diff_out = run_printed_command(fx.repo, _command(block, "  git diff "))
    assert log_out.strip() and diff_out.strip()
    logged = [line.split()[0] for line in reversed(log_out.splitlines())]
    listed = [line.split()[0] for line in _section(block, "IMPLEMENTATION COMMITS")]
    assert len(logged) == len(listed) and all(full.startswith(short) or short.startswith(full) for short, full in zip(listed, logged, strict=True))
    for excluded in fx.excluded_shas:
        assert excluded[:7] not in log_out
    for path in fx.excluded_paths:
        assert path not in log_out and path not in diff_out


# --------------------------------------------------------------------------- site 3: the stdout summary


@pytest.mark.parametrize("name", REVIEW_READY)
def test_site3_prints_the_blocks_header_and_git_log_line_verbatim(reviews: _Reviews, name: str) -> None:
    review = reviews.get(name)
    block = _site2_block(review)
    header = block.splitlines()[0]
    log_line = _command(block, "  git log ")
    stdout_lines = review.stdout.splitlines()

    assert header in stdout_lines, review.stdout
    assert log_line in stdout_lines, review.stdout
    assert run_printed_command(review.fixture.repo, log_line).strip()
    allowed = {header.split()[3], log_line.split()[3]}
    ranges = set(_RANGE_TOKEN.findall(review.stdout))
    assert ranges <= allowed, f"site 3 names another range: {sorted(ranges - allowed)}"
    assert "..HEAD" not in review.stdout


# --------------------------------------------------------------------------- C-001 and NFR-005


def _prompts_root() -> Path:
    return Path(tempfile.gettempdir()) / "spec-kitty-review-prompts"


def test_no_patch_text_and_no_diff_file(templates: ReviewTemplates, tmp_path: Path) -> None:
    fx = templates.checkout("single_branch_minted", tmp_path)
    prompts_root = _prompts_root()
    prompts_before = snapshot_tree(prompts_root) if prompts_root.is_dir() else {}
    tree_before = snapshot_tree(fx.root)

    exit_code, stdout, prompt_file = _site2(fx, _review_args(fx))

    assert exit_code == 0, stdout
    assert prompt_file is not None and prompt_file.is_file(), stdout
    prompt = prompt_file.read_text(encoding="utf-8")
    assert review_block(prompt)
    assert_no_patch_text(prompt)
    assert_no_patch_text(stdout)
    prompts_after = snapshot_tree(prompts_root)
    new_prompts = sorted(set(prompts_after) - set(prompts_before))
    assert new_prompts == [str(prompt_file.relative_to(prompts_root))], new_prompts
    tree_after = snapshot_tree(fx.root)
    for path in sorted(set(tree_after) - set(tree_before)):
        assert not path.endswith((".diff", ".patch")), path
        assert_no_patch_text(tree_after[path].decode("utf-8", "replace"))


_REVIEW_SCRIPT = """
import sys
from typer.testing import CliRunner
from specify_cli.cli.commands.agent import workflow
from tests.integration.review.review_range_fixtures import review_block
import re
from pathlib import Path
result = CliRunner().invoke(workflow.app, sys.argv[1:])
match = re.search(r"^\\s*cat (\\S+\\.md)\\s*$", result.output, re.MULTILINE)
assert result.exit_code == 0 and match, result.output
sys.stdout.write(review_block(Path(match.group(1)).read_text(encoding="utf-8")))
"""


def _review_in_fresh_interpreter(fx: ReviewFixture, seed: str) -> str:
    args = _review_args(fx)
    env = {key: value for key, value in os.environ.items() if key not in HARNESS_VARIABLES}
    env.pop("SPEC_KITTY_ORIGIN_CHECK", None)
    env.update(fx.environment_variables())
    env["PYTHONHASHSEED"] = seed
    env["PYTHONPATH"] = os.pathsep.join(filter(None, (str(_PROJECT_ROOT), env.get("PYTHONPATH"))))
    proc = subprocess.run(
        [sys.executable, "-c", _REVIEW_SCRIPT, *args],
        cwd=fx.repo,
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    return proc.stdout


@pytest.mark.parametrize("name", REVIEW_READY)
def test_site2_block_is_byte_identical_across_hash_seeds(templates: ReviewTemplates, tmp_path: Path, name: str) -> None:
    first = _review_in_fresh_interpreter(templates.checkout(name, tmp_path / "seed0"), "0")
    second = _review_in_fresh_interpreter(templates.checkout(name, tmp_path / "seed1"), "1")

    assert first.startswith(f"REVIEW RANGE ({REVIEWED_WP}): "), first
    assert first == second


# --------------------------------------------------------------------------- FR-013 / NFR-004: unavailable is a notice


def test_unavailable_range_is_a_notice_on_sites_2_and_3(templates: ReviewTemplates, tmp_path: Path) -> None:
    review = _run(templates.checkout("lanes_stamp_stripped", tmp_path))
    reason_suffix = f"({review.fixture.unavailable_reason})"

    assert review.exit_code == 0, review.stdout
    assert "Traceback" not in review.stdout
    lines = review_block(review.prompt).splitlines()
    assert lines, f"site 2 printed no REVIEW RANGE notice:\n{review.prompt}"
    assert lines[0].startswith(f"REVIEW RANGE ({REVIEWED_WP}): unavailable — ") and lines[0].endswith(reason_suffix), review.prompt
    assert lines[1:3] == ["REVIEW COMMANDS:", _UNAVAILABLE_COMMAND]
    assert not _head_ranges(review.prompt), review.prompt
    reason = lines[0].split("unavailable — ", 1)[1]
    # Q13 (#7590): the topology payload names the same gap and points at the notice, never a ``<base>..HEAD`` diff.
    assert _topology_diff_command(review.prompt) == f"unavailable: {reason}; see REVIEW RANGE"
    assert review.metadata["base_ref"] == "unknown"
    assert f"Review range unavailable — {reason}" in review.stdout.splitlines(), review.stdout
    assert not _RANGE_TOKEN.findall(review.stdout), review.stdout


# --------------------------------------------------------------------------- operator ruling Q7: owned checkouts


def _blocked_reason(payload: dict[str, Any]) -> str:
    summary = {key: payload.get(key) for key in ("kind", "action", "reason", "error_code")}
    assert payload["kind"] == "blocked", summary
    assert payload.get("error_code") == OwnedRefusalCode.OWNED_REVIEW_BASE_UNAVAILABLE, summary
    reason = str(payload.get("reason") or "")
    assert "cannot build a scoped review diff for WP01 in the owned checkout: " in reason, summary
    return reason


@pytest.mark.parametrize("ambiguous", [False, True], ids=["unresolvable", "ambiguous"])
def test_owned_unavailable_scoped_range_is_blocked_with_its_reason_in_words(
    owned_checkouts: OwnedCheckouts, monkeypatch: pytest.MonkeyPatch, ambiguous: bool
) -> None:
    monkeypatch.setattr(next_cmd, "analysis_currency_for", lambda *_a, **_k: analysis_is_current)
    _owned_review_ready(owned_checkouts, monkeypatch)
    make_owned_range_unavailable(owned_checkouts.owned_root, owned_checkouts.mission_dir, owned_checkouts.mission_slug, "WP01", ambiguous=ambiguous)

    reason = _blocked_reason(_owned_next(owned_checkouts, monkeypatch))

    detail = reason.split("the review range is unavailable: ", 1)
    assert len(detail) == 2, reason
    # The renderer's readable gap description, then the raw gap value in parentheses, never the bare gap value.
    assert re.fullmatch(r"[a-z][^()]* \([a-z_]+\)\.?", detail[1].strip()), reason


def test_owned_wp_without_owned_files_is_blocked(owned_checkouts: OwnedCheckouts, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(next_cmd, "analysis_currency_for", lambda *_a, **_k: analysis_is_current)
    _owned_review_ready(owned_checkouts, monkeypatch)
    wp_file = owned_checkouts.mission_dir / "tasks" / "WP01-owned.md"
    wp_file.write_text(wp_file.read_text(encoding="utf-8").replace("owned_files:\n- wp01.py", "owned_files: []"), encoding="utf-8")
    _commit_all(owned_checkouts.owned_root, "drop owned_files")

    assert _blocked_reason(_owned_next(owned_checkouts, monkeypatch)).endswith("the work package declares no owned_files")


def test_owned_available_range_is_never_blocked(owned_checkouts: OwnedCheckouts, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(next_cmd, "analysis_currency_for", lambda *_a, **_k: analysis_is_current)
    _owned_review_ready(owned_checkouts, monkeypatch)

    payload = _owned_next(owned_checkouts, monkeypatch)

    assert payload["kind"] == "step" and payload.get("error_code") is None, json.dumps(payload)[:2000]


# --------------------------------------------------------------------------- operator ruling Q13 (#7590): one review range in the prompt

_TOPOLOGY_START = "<!-- WORKTREE_TOPOLOGY -->"
_TOPOLOGY_END = "<!-- /WORKTREE_TOPOLOGY -->"


def _topology_diff_command(prompt: str) -> str | None:
    """The ``diff_command`` of the prompt's WORKTREE_TOPOLOGY payload (``None`` when the prompt carries no topology)."""
    if _TOPOLOGY_START not in prompt:
        return None
    payload = prompt.split(_TOPOLOGY_START, 1)[1].split(_TOPOLOGY_END, 1)[0]
    return str(json.loads(payload)["diff_command"])


@pytest.mark.parametrize("name", REVIEW_READY)
def test_site2_topology_diff_command_is_the_review_range_diff(reviews: _Reviews, name: str) -> None:
    """Q13: the topology payload's ``diff_command`` is the block's own ``git diff`` line, never a ``<base>..HEAD`` diff."""
    review = reviews.get(name)
    diff_line = _command(_site2_block(review), "  git diff ")
    diff_command = _topology_diff_command(review.prompt)

    assert diff_command is not None, f"precondition: {name}'s review prompt carries the worktree topology"
    assert diff_command == diff_line.strip()
    assert "..HEAD" not in diff_command
