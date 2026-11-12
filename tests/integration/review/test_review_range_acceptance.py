"""Acceptance: the ``spec-kitty next`` review step (render site 1) prints the WP review range (#7578, WP05).

ATDD-first (C-010): committed red before any production change. Site 1 is driven through its
production entry point, ``runtime.next.prompt_builder.build_prompt("review", ...)``, over four
review-ready topology fixtures (``review_range_fixtures``), and asserts, per fixture:

* exact provenance: ``[recorded]``, ``base: <base12> (window open)``, ``tip:  <tip12> (for_review submission)``;
* the commit list is exactly WP02's implementation commits, oldest first (SC-001), never the
  lane-mate commit on WP02's own owned path (only the base can exclude it);
* the exact ``CHANGED FILES`` lines (FR-006) and the ``OUTSIDE OWNED FILES`` line;
* the printed ``git log`` / ``git diff`` commands run as written through ``bash -c`` (FR-008);
* cited requirement texts (SC-002), the moved-past note (FR-009), no patch text and no diff file
  (C-001), the 4,096-byte budget (NFR-001) and byte-identical output under two hash seeds (NFR-005).

The unavailable notice (FR-013, NFR-004) is driven through ``spec-kitty next`` itself on the
stamp-stripped ``lanes`` fixture: exit 0, a ``step`` decision, and the unavailable block.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
import typer
from typer.testing import CliRunner

from runtime.next.prompt_builder import build_prompt
from specify_cli.cli.commands import next_cmd
from specify_cli.review.wp_range import RangeStatus, resolve_wp_review_range
from tests.integration.review.review_range_fixtures import (
    CITED_REFS,
    DECLARED_TEXTS,
    HARNESS_VARIABLES,
    REVIEW_READY,
    REVIEWED_WP,
    ReviewFixture,
    ReviewTemplates,
    assert_no_patch_text,
    review_block,
    run_printed_command,
    snapshot_tree,
)
from tests.runtime._next_mission_scaffold import advance_to_step, analysis_is_current

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_MISSION_TYPE = "software-dev"
_AGENT = "claude"
_BUDGET = 4096
_REQUIREMENTS_HEADING = "CITED REQUIREMENTS:"
_UNAVAILABLE_COMMAND = "  (no deterministic range; inspect `spec-kitty agent tasks status` and the WP's commits)"

next_app = typer.Typer()
next_app.command(name="next")(next_cmd.next_step)


@pytest.fixture(scope="module")
def templates(tmp_path_factory: pytest.TempPathFactory) -> ReviewTemplates:
    return ReviewTemplates(tmp_path_factory.mktemp("review-range-acceptance"))


class _Rendered:
    """Each review-ready fixture copied and rendered once per module, for the read-only assertions."""

    def __init__(self, templates: ReviewTemplates, root: Path) -> None:
        self._templates = templates
        self._root = root
        self._done: dict[str, tuple[ReviewFixture, str]] = {}

    def get(self, name: str) -> tuple[ReviewFixture, str]:
        if name not in self._done:
            fx = self._templates.checkout(name, self._root)
            self._done[name] = (fx, _render(fx)[0])
        return self._done[name]


@pytest.fixture(scope="module")
def rendered(templates: ReviewTemplates, tmp_path_factory: pytest.TempPathFactory) -> _Rendered:
    return _Rendered(templates, tmp_path_factory.mktemp("rendered"))


@pytest.fixture(params=REVIEW_READY)
def fixture(request: pytest.FixtureRequest, templates: ReviewTemplates, tmp_path: Path) -> ReviewFixture:
    """A private copy, for the cells that render again (snapshot, determinism)."""
    return templates.checkout(str(request.param), tmp_path)


def _render(fx: ReviewFixture) -> tuple[str, Path]:
    with fx.environment():
        return build_prompt("review", fx.feature_dir, fx.mission_slug, REVIEWED_WP, _AGENT, fx.repo, _MISSION_TYPE)


def _section(block: str, heading: str) -> list[str]:
    """The indented item lines under the first line starting with *heading*, up to the next unindented line."""
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


def _owned_pathspec(fx: ReviewFixture) -> str:
    return "'src/m2/**'" if fx.name.startswith("single_branch") else "'src/pkg/wp02/**'"


# --------------------------------------------------------------------------- the review range block


@pytest.mark.parametrize("name", REVIEW_READY)
def test_header_carries_exact_recorded_provenance(rendered: _Rendered, name: str) -> None:
    fixture, text = rendered.get(name)
    block = review_block(text)
    assert fixture.expected_base and fixture.expected_tip
    base12, tip12 = fixture.expected_base[:12], fixture.expected_tip[:12]

    lines = block.splitlines()
    assert lines[:1] == [f"REVIEW RANGE ({REVIEWED_WP}): {base12}..{tip12}  [recorded]"], block
    assert f"  base: {base12} ({fixture.base_label})" in lines
    assert f"  tip:  {tip12} ({fixture.tip_label})" in lines
    assert not [line for line in lines if "recorded window not used" in line]


@pytest.mark.parametrize("name", REVIEW_READY)
def test_commit_list_is_exactly_the_implementation_commits_oldest_first(rendered: _Rendered, name: str) -> None:
    fixture, text = rendered.get(name)
    block = review_block(text)

    heading = f"IMPLEMENTATION COMMITS ({len(fixture.implementation_shas)}; = output of the git log command below):"
    assert heading in block.splitlines(), block
    listed = [line.split()[0] for line in _section(block, "IMPLEMENTATION COMMITS")]
    assert listed == [sha[:12] for sha in fixture.implementation_shas]
    for excluded in fixture.excluded_shas:
        assert excluded[:12] not in listed, f"lane-mate / later commit {excluded[:12]} leaked into the commit list"
        # On a lane the lane-mate commit can BE the window open: the exclusive base is what keeps it out.
        if excluded != fixture.expected_base:
            assert excluded[:12] not in block, f"lane-mate / later commit {excluded[:12]} named in the review range"


@pytest.mark.parametrize("name", REVIEW_READY)
def test_changed_files_lines_are_exact(rendered: _Rendered, name: str) -> None:
    fixture, text = rendered.get(name)
    block = review_block(text)

    files = [line for line in _section(block, "CHANGED FILES (owned files, +added -removed):") if not line.startswith("  OUTSIDE OWNED FILES")]
    assert files == [f"  {line}" for line in fixture.changed_files]
    outside = (
        f"  OUTSIDE OWNED FILES ({len(fixture.out_of_map_paths)} path(s) in {fixture.out_of_map_only_commits} commit(s) "
        f"touching only those paths; review rationale required): {', '.join(fixture.out_of_map_paths)}"
    )
    assert outside in block.splitlines(), block
    for path in fixture.excluded_paths:
        assert path not in block


@pytest.mark.parametrize("name", REVIEW_READY)
def test_printed_commands_run_as_written(rendered: _Rendered, name: str) -> None:
    fixture, text = rendered.get(name)
    block = review_block(text)
    assert fixture.expected_base and fixture.expected_tip
    rev_range = f"{fixture.expected_base}..{fixture.expected_tip}"
    pathspec = _owned_pathspec(fixture)

    log_line = _command(block, "  git log ")
    diff_line = _command(block, "  git diff ")
    assert log_line == f"  git log --oneline {rev_range} -- {pathspec}"
    assert diff_line == f"  git diff {rev_range} -- {pathspec}"

    log_out = run_printed_command(fixture.repo, log_line)
    diff_out = run_printed_command(fixture.repo, diff_line)
    assert log_out.strip() and diff_out.strip()
    logged = [line.split()[0] for line in log_out.splitlines()]
    assert len(logged) == len(fixture.implementation_shas)
    assert all(full.startswith(short) for short, full in zip(reversed(logged), fixture.implementation_shas, strict=True))
    for excluded in fixture.excluded_shas:
        assert excluded[:7] not in log_out
    for path in fixture.excluded_paths:
        assert path not in log_out and path not in diff_out


@pytest.mark.parametrize("name", REVIEW_READY)
def test_cited_requirements_render_with_their_resolution(rendered: _Rendered, name: str) -> None:
    fixture, text = rendered.get(name)
    block = review_block(text)

    assert _section(block, _REQUIREMENTS_HEADING) == [
        f"  FR-001 — {DECLARED_TEXTS['FR-001']}",
        f"  NFR-001 — {DECLARED_TEXTS['NFR-001']}",
        "  C-009 — not declared in this Mission's spec",
        "  other-mission#FR-002 — cites another Mission (not resolved here)",
    ]
    assert len(CITED_REFS) == 4


@pytest.mark.parametrize("name", REVIEW_READY)
def test_moved_past_note_only_when_the_branch_moved(rendered: _Rendered, name: str) -> None:
    fixture, text = rendered.get(name)
    block = review_block(text)

    moved = [line for line in block.splitlines() if "has moved" in line]
    if fixture.moved_past:
        assert len(moved) == 1 and moved[0].startswith("  note: ") and moved[0].endswith(f"has moved {fixture.moved_past} commit(s) past the submitted tip")
    else:
        assert moved == [], block


@pytest.mark.parametrize("name", REVIEW_READY)
def test_block_stays_within_the_byte_budget(rendered: _Rendered, name: str) -> None:
    fixture, text = rendered.get(name)
    block = review_block(text)

    assert block and _REQUIREMENTS_HEADING in block
    assert len(block.split(_REQUIREMENTS_HEADING)[0].encode("utf-8")) <= _BUDGET


# --------------------------------------------------------------------------- C-001: no patch text, no diff file


def test_detector_sees_a_real_patch(templates: ReviewTemplates, tmp_path: Path) -> None:
    """Positive control: the C-001 detector fails on the real output of ``git diff`` over a fixture range."""
    fx = templates.checkout("single_branch_minted", tmp_path)
    assert fx.expected_base and fx.expected_tip
    patch = subprocess.run(["git", "diff", f"{fx.expected_base}..{fx.expected_tip}"], cwd=fx.repo, check=True, capture_output=True, text=True).stdout

    with pytest.raises(AssertionError, match="C-001"):
        assert_no_patch_text(patch)


def test_prompt_carries_no_patch_text_and_writes_no_diff_file(fixture: ReviewFixture) -> None:
    before = snapshot_tree(fixture.root)

    text, prompt_file = _render(fixture)

    assert review_block(text), "no review range block"
    assert_no_patch_text(text)
    after = snapshot_tree(fixture.root)
    prompt_rel = str(prompt_file.relative_to(fixture.root)) if prompt_file.is_relative_to(fixture.root) else None
    new = sorted(set(after) - set(before) - {prompt_rel})
    changed = sorted(path for path in set(after) & set(before) if after[path] != before[path])
    for path in [*new, *changed]:
        assert_no_patch_text(after[path].decode("utf-8", "replace"))
    assert not [path for path in new if path.endswith((".diff", ".patch"))], new


# --------------------------------------------------------------------------- NFR-005: determinism


_RENDER_SCRIPT = """
import sys
from pathlib import Path
from runtime.next.prompt_builder import build_prompt
from tests.integration.review.review_range_fixtures import review_block
text, _ = build_prompt("review", Path(sys.argv[1]), sys.argv[2], sys.argv[3], "claude", Path(sys.argv[4]), "software-dev")
sys.stdout.write(review_block(text))
"""


def _render_in_fresh_interpreter(fx: ReviewFixture, seed: str) -> str:
    env = {key: value for key, value in os.environ.items() if key not in HARNESS_VARIABLES}
    env.update(fx.environment_variables())
    env["PYTHONHASHSEED"] = seed
    env["PYTHONPATH"] = os.pathsep.join(filter(None, (str(_PROJECT_ROOT), env.get("PYTHONPATH"))))
    proc = subprocess.run(
        [sys.executable, "-c", _RENDER_SCRIPT, str(fx.feature_dir), fx.mission_slug, REVIEWED_WP, str(fx.repo)],
        cwd=fx.repo,
        env=env,
        check=True,
        capture_output=True,
        text=True,
        timeout=300,
    )
    return proc.stdout


def test_block_is_byte_identical_across_hash_seeds(fixture: ReviewFixture) -> None:
    first = _render_in_fresh_interpreter(fixture, "0")
    second = _render_in_fresh_interpreter(fixture, "1")

    assert first, "no review range block"
    assert first == second


# --------------------------------------------------------------------------- FR-013 / NFR-004: unavailable, through `next`


def _payload(output: str) -> dict[str, Any]:
    data, _end = json.JSONDecoder().raw_decode(output[output.index("{") :])
    assert isinstance(data, dict), output
    return data


def test_unavailable_range_is_a_notice_through_next_never_a_refusal(templates: ReviewTemplates, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fx = templates.checkout("lanes_stamp_stripped", tmp_path)
    monkeypatch.setattr(next_cmd, "analysis_currency_for", lambda *_a, **_k: analysis_is_current)
    with fx.environment():
        found = resolve_wp_review_range(fx.repo, fx.mission_slug, REVIEWED_WP, owned_files=["src/pkg/wp02/**"])
        assert found.status is RangeStatus.UNAVAILABLE, "precondition: the stripped range is genuinely unavailable"
        assert found.gap == fx.unavailable_reason
        advance_to_step(fx.repo, fx.mission_slug, _MISSION_TYPE, "analyze")

        result = CliRunner().invoke(next_app, ["--agent", _AGENT, "--mission", fx.mission_slug, "--result", "success", "--json"])

    assert result.exit_code == 0, result.output
    payload = _payload(result.output)
    assert payload["kind"] == "step" and payload["action"] == "review" and payload["wp_id"] == REVIEWED_WP, payload
    prompt = Path(payload["prompt_file"]).read_text(encoding="utf-8")
    block = review_block(prompt)
    lines = block.splitlines()
    assert lines[0].startswith(f"REVIEW RANGE ({REVIEWED_WP}): unavailable — "), block
    assert lines[0].endswith(f"({fx.unavailable_reason})"), block
    assert lines[1:3] == ["REVIEW COMMANDS:", _UNAVAILABLE_COMMAND], block
    assert "..HEAD" not in block
    assert _section(block, _REQUIREMENTS_HEADING)[2] == "  C-009 — not declared in this Mission's spec"
