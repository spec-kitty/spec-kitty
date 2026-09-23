"""Regression + unit coverage for #4894 (WP03): traces merge-driver section union.

``merge_driver_traces`` / ``union_trace_texts`` (``src/specify_cli/cli/commands/
merge_driver.py``) used to dedup ``kitty-specs/**/traces/*.md`` conflict inputs at
LINE granularity with one shared ``seen`` set across ``ours``/``theirs`` -- sound
only for documents whose non-empty lines are globally unique, which markdown is
not (fences, ``Example:`` labels, and headings all legitimately recur across
distinct sections). A file with four fenced blocks came out with one fence line,
exit 0, clean-merge recorded, on every ordinary ``git merge``/``rebase``/
``cherry-pick`` touching the file -- not only spec-kitty's own squash.

The rewrite unions at SECTION/BLOCK granularity (:func:`union_trace_texts`) and
adds 3-way base-awareness (:func:`merge_driver_traces` now reads ``%O``) so a
section left unchanged by one side while the other edited it is recognized as
stale rather than resurrected. See the module docstring in ``merge_driver.py``
for the full contract (INV-3: every non-empty line present in either input is
present in the output).

``test_traces_merge_preserves_both_sections_and_fences_4894`` is the RED-FIRST
regression pinned to #4894, following the issue's own QA repro script almost
verbatim (2 pre-existing fenced sections + 1 independently-appended fenced
section per lane => 4 sections / 8 fence lines / 4 ``Example:`` lines). It runs
a REAL ``git merge`` with the custom driver registered, but points the driver
command at THIS worktree's ``merge_driver_traces`` (invoked in a subprocess via
``sys.path`` injection) rather than the installed ``spec-kitty`` entry point --
the installed entry point resolves to the separate main-checkout install and
would silently test main's code, not the fix under review, since the
``.venv`` editable install is not this worktree (see WP03's task brief). This
keeps the test a genuine git-level merge-driver regression while staying
immune to that staleness trap.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from specify_cli.cli.commands.merge_driver import (
    _drop_stale_theirs_trace_blocks,
    _split_trace_blocks,
    _union_acceptance_history,
    merge_driver_traces,
    union_trace_texts,
)

pytestmark = pytest.mark.fast

_WORKTREE_SRC = Path(__file__).resolve().parents[2] / "src"

_BASE_TRACE = "# Design decisions\n\n## D-1 storage\n\nExample:\n\n```\nvalue = 1\n```\n\n## D-2 transport\n\nExample:\n\n```\nvalue = 2\n```\n"
_LANE_A_APPEND = "\n## D-3 from lane A\n\nExample:\n\n```\nvalue = 3\n```\n"
_LANE_B_APPEND = "\n## D-4 from lane B\n\nExample:\n\n```\nvalue = 4\n```\n"


def _write_driver_shim(directory: Path) -> Path:
    """A tiny script invoking THIS worktree's ``merge_driver_traces`` (see module docstring)."""
    script = directory / "trace_merge_driver_shim.py"
    script.write_text(
        "import sys\n"
        f"sys.path.insert(0, {str(_WORKTREE_SRC)!r})\n"
        "from specify_cli.cli.commands.merge_driver import merge_driver_traces\n"
        "merge_driver_traces(sys.argv[1], sys.argv[2], sys.argv[3])\n",
        encoding="utf-8",
    )
    return script


def _git_env() -> dict[str, str]:
    return {
        **os.environ,
        "GIT_AUTHOR_NAME": "QA",
        "GIT_AUTHOR_EMAIL": "qa@example.invalid",
        "GIT_COMMITTER_NAME": "QA",
        "GIT_COMMITTER_EMAIL": "qa@example.invalid",
        "GIT_CONFIG_NOSYSTEM": "1",
    }


def _run_git(repo: Path, env: dict[str, str], *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=repo, env=env, text=True, capture_output=True, check=False)


# ---------------------------------------------------------------------------
# T012 -- RED-FIRST regression, pinned to #4894
# ---------------------------------------------------------------------------


@pytest.mark.regression
def test_traces_merge_preserves_both_sections_and_fences_4894(tmp_path: Path) -> None:
    """Two lanes each append a fenced section to a shared traces/*.md from one base.

    Expected (the issue's own numbers): 4 sections total (D-1, D-2 pre-existing
    + D-3/D-4 appended), 8 fence lines (4 blocks x 2), 4 ``Example:`` lines --
    or a git conflict. RED before the fix: the old line-level global dedup
    collapsed this to 1 fence line / 1 ``Example:`` line (the issue's observed
    evidence), exit 0, no conflict.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    env = _git_env()

    def run(*args: str) -> subprocess.CompletedProcess[str]:
        return _run_git(repo, env, *args)

    assert run("init", "-q", "-b", "main").returncode == 0
    assert run("config", "user.name", "QA").returncode == 0
    assert run("config", "user.email", "qa@example.invalid").returncode == 0
    assert run("config", "commit.gpgsign", "false").returncode == 0

    trace_dir = repo / "kitty-specs" / "demo" / "traces"
    trace_dir.mkdir(parents=True)
    trace_path = trace_dir / "design-decisions.md"
    trace_path.write_text(_BASE_TRACE, encoding="utf-8")

    shim = _write_driver_shim(tmp_path)
    driver_cmd = f"{sys.executable} {shim} %O %A %B"
    assert run("config", "merge.spec-kitty-traces.name", "spec-kitty traces union").returncode == 0
    assert run("config", "merge.spec-kitty-traces.driver", driver_cmd).returncode == 0
    (repo / ".gitattributes").write_text("kitty-specs/**/traces/*.md merge=spec-kitty-traces\n", encoding="utf-8")

    assert run("add", "-A").returncode == 0
    assert run("commit", "-qm", "base").returncode == 0

    assert run("checkout", "-q", "-b", "lane-a").returncode == 0
    with trace_path.open("a", encoding="utf-8") as fh:
        fh.write(_LANE_A_APPEND)
    assert run("commit", "-qam", "lane-a trace").returncode == 0

    assert run("checkout", "-q", "-b", "lane-b", "main").returncode == 0
    with trace_path.open("a", encoding="utf-8") as fh:
        fh.write(_LANE_B_APPEND)
    assert run("commit", "-qam", "lane-b trace").returncode == 0

    assert run("checkout", "-q", "lane-a").returncode == 0
    result = run("merge", "--no-edit", "lane-b")

    merged_text = trace_path.read_text(encoding="utf-8")
    if result.returncode != 0:
        # A conflict is an acceptable outcome per the contract (never a
        # lossy exit-0) -- but it must genuinely mark the file conflicted.
        assert "CONFLICT" in (result.stdout + result.stderr)
        return

    assert merged_text.count("```") == 8
    assert merged_text.count("Example:") == 4
    for marker in ("## D-1 storage", "## D-2 transport", "## D-3 from lane A", "## D-4 from lane B"):
        assert marker in merged_text


# ---------------------------------------------------------------------------
# T013 -- focused unit coverage over union_trace_texts (section granularity)
# ---------------------------------------------------------------------------


def test_union_preserves_repeated_line_within_one_distinct_section() -> None:
    """A repeated line WITHIN one section must survive (not line-deduped away)."""
    ours_text = "## Notes\nsame line\nsame line\n"
    merged = union_trace_texts(ours_text, "")
    assert merged.count("same line") == 2


def test_union_dedupes_two_identical_whole_sections_to_one() -> None:
    """A whole section byte-identical on both sides collapses to one copy."""
    text = "## Notes\nbody line\nbody line\n"
    merged = union_trace_texts(text, text)
    assert merged.count("## Notes") == 1
    assert merged.count("body line") == 2  # internal repeat still preserved


def test_union_appends_distinct_sections_in_stable_order() -> None:
    """Append order: ours' sections first, then theirs' NEW sections."""
    ours_text = "## A\na body\n"
    theirs_text = "## B\nb body\n"
    merged = union_trace_texts(ours_text, theirs_text)
    assert merged.index("## A") < merged.index("## B")


@pytest.mark.parametrize(
    "ours_text, theirs_text",
    [
        ("## A\nline one\nline one\n", "## B\nline two\n"),
        ("# Title\n\n<!-- section:s -->\nbody\n", "# Title\n\n<!-- section:s -->\nbody\n"),
        ("## Same\nrepeat\nrepeat\n", "## Same\nrepeat\nrepeat\n"),
        ("", "## Only theirs\ncontent\n"),
        ("## Only ours\ncontent\n", ""),
        ("## X\n```\nfence one\n```\n", "## Y\n```\nfence two\n```\n"),
    ],
)
def test_union_trace_texts_inv3_no_line_dropped_without_a_duplicate(ours_text: str, theirs_text: str) -> None:
    """INV-3: every non-empty line in either input survives into the union."""
    merged_lines = set(union_trace_texts(ours_text, theirs_text).splitlines())
    for source in (ours_text, theirs_text):
        for line in source.splitlines():
            if line.strip():
                assert line in merged_lines


# ---------------------------------------------------------------------------
# T014 -- 3-way base-awareness in merge_driver_traces
# ---------------------------------------------------------------------------


def test_merge_driver_traces_drops_stale_theirs_copy_of_a_section_ours_edited(
    tmp_path: Path,
) -> None:
    """Base-awareness: theirs' unchanged copy of a section ours edited is stale."""
    base = tmp_path / "O"
    ours = tmp_path / "A"
    theirs = tmp_path / "B"
    base_text = "## Section X\noriginal body\n"
    base.write_text(base_text, encoding="utf-8")
    ours.write_text("## Section X\nedited body\n", encoding="utf-8")  # ours edited it
    theirs.write_text(base_text, encoding="utf-8")  # theirs left it unchanged

    merge_driver_traces(str(base), str(ours), str(theirs))

    merged = ours.read_text(encoding="utf-8")
    assert merged.count("## Section X") == 1
    assert "edited body" in merged
    assert "original body" not in merged


def test_merge_driver_traces_keeps_both_sides_when_both_edited_differently(
    tmp_path: Path,
) -> None:
    """A genuine structural divergence (both sides edited) is never silently picked."""
    base = tmp_path / "O"
    ours = tmp_path / "A"
    theirs = tmp_path / "B"
    base.write_text("## Section X\noriginal body\n", encoding="utf-8")
    ours.write_text("## Section X\nours body\n", encoding="utf-8")
    theirs.write_text("## Section X\ntheirs body\n", encoding="utf-8")

    merge_driver_traces(str(base), str(ours), str(theirs))

    merged = ours.read_text(encoding="utf-8")
    assert "ours body" in merged
    assert "theirs body" in merged


def test_merge_driver_traces_unions_independent_new_sections_from_base(
    tmp_path: Path,
) -> None:
    """Sibling of the regression above, in-process: two sides append distinct
    NEW sections from a shared base -- both survive with fences intact."""
    base = tmp_path / "O"
    ours = tmp_path / "A"
    theirs = tmp_path / "B"
    base.write_text(_BASE_TRACE, encoding="utf-8")
    ours.write_text(_BASE_TRACE + _LANE_A_APPEND, encoding="utf-8")
    theirs.write_text(_BASE_TRACE + _LANE_B_APPEND, encoding="utf-8")

    merge_driver_traces(str(base), str(ours), str(theirs))

    merged = ours.read_text(encoding="utf-8")
    assert merged.count("```") == 8
    assert merged.count("Example:") == 4


# ---------------------------------------------------------------------------
# T015 -- sibling-unchanged: _union_acceptance_history is record-granularity
# dedup by canonical-JSON equality, untouched by this WP.
# ---------------------------------------------------------------------------


def test_union_acceptance_history_still_record_granularity_dedup() -> None:
    """Pin: this WP does not touch ``_union_acceptance_history`` (#4894 scope)."""
    entry_a = {"accepted_at": "T1", "accepted_by": "a"}
    entry_b = {"accepted_at": "T2", "accepted_by": "b"}
    result = _union_acceptance_history([entry_a], [dict(entry_a), entry_b])
    assert result == [entry_a, entry_b]


# ---------------------------------------------------------------------------
# WP03/T011 -- RED-FIRST: tilde fences (AC-C1) + non-colliding block key (AC-C2)
# (#4993)
# ---------------------------------------------------------------------------


def test_split_trace_blocks_does_not_split_on_heading_like_line_inside_tilde_fence() -> None:
    """AC-C1: a ``~~~``-fenced block is not split at a heading-like line inside it.

    Fails against the backtick-only ``_TRACE_FENCE_MARKER`` (``~~~`` never
    toggles ``in_fence``, so ``# not a heading`` is misread as a section
    boundary and the fenced block is split into two); passes once the
    fence-marker regex also recognizes ``~~~``.
    """
    text = "## Real Heading\n~~~\n# not a heading\nstill inside fence\n~~~\nafter fence\n"
    blocks = _split_trace_blocks(text)
    assert len(blocks) == 1
    assert blocks[0] == tuple(text.splitlines())


def test_drop_stale_theirs_trace_blocks_keys_duplicate_headings_distinctly() -> None:
    """AC-C2: two distinct sections sharing an identical heading are keyed
    distinctly through the base-aware stale-drop -- neither collision-dropped
    nor mis-attributed to the wrong section's base/ours comparison.

    Base has two ``## Same`` sections. Ours leaves the FIRST unchanged and
    diverges the SECOND; theirs leaves both unchanged (stale copies). The
    correct result keeps theirs' first section (ours didn't touch it) and
    drops theirs' second section (ours' diverged edit supersedes it).

    Fails against the old ``setdefault(block[0])`` collision: both base/ours
    index only ever retain the FIRST same-heading block under the shared key
    ``"## Same"``, so theirs' second block is compared against the FIRST
    section's base/ours content instead of its own -- it never matches its
    own (different-content) base, so ``theirs_unchanged`` is wrongly False
    and the stale second section is kept instead of dropped.
    """
    base_text = "## Same\nfirst body\n## Same\nsecond body\n"
    ours_text = "## Same\nfirst body\n## Same\nsecond body EDITED\n"
    theirs_text = base_text  # both sections left unchanged by theirs

    result = _drop_stale_theirs_trace_blocks(base_text, ours_text, theirs_text)

    assert "first body" in result  # ours didn't touch it -- theirs' copy survives
    assert "second body" not in result  # ours diverged -- theirs' stale copy is dropped
    assert result.count("## Same") == 1


# ---------------------------------------------------------------------------
# WP03/T013 -- explicit ``<!-- section:ID -->`` id takes priority over the
# occurrence-ordinal fallback (position-independent identity) (#4993)
# ---------------------------------------------------------------------------


def test_drop_stale_theirs_trace_blocks_prefers_explicit_section_id_over_position() -> None:
    """An explicit ``<!-- section:ID -->`` id is a stable key even when the
    same two sections are reordered between documents -- not just a
    same-position occurrence-ordinal match."""
    base_text = "<!-- section:alpha -->\nalpha original\n<!-- section:beta -->\nbeta original\n"
    # ours: reordered (beta first), alpha's body diverged
    ours_text = "<!-- section:beta -->\nbeta original\n<!-- section:alpha -->\nalpha EDITED\n"
    theirs_text = base_text  # both sections left unchanged by theirs, original order

    result = _drop_stale_theirs_trace_blocks(base_text, ours_text, theirs_text)

    assert "alpha original" not in result  # id-matched to ours' diverged edit -- dropped
    assert "beta original" in result  # id-matched to ours' unchanged copy -- kept


# ---------------------------------------------------------------------------
# WP03/T014 -- regression: single-heading stale-drop + union_trace_texts
# whole-block dedup unchanged by the key-collision fix (#4993)
# ---------------------------------------------------------------------------


def test_drop_stale_theirs_single_heading_section_still_stale_drops_after_key_change() -> None:
    """AC-C3: a single (non-duplicated) heading section's 3-way base-aware
    stale-drop is unaffected by the occurrence-indexed key change."""
    base_text = "## Section X\noriginal body\n"
    ours_text = "## Section X\nedited body\n"
    theirs_text = base_text

    result = _drop_stale_theirs_trace_blocks(base_text, ours_text, theirs_text)

    assert result == ""


def test_union_trace_texts_whole_block_dedup_unchanged_after_key_change() -> None:
    """AC-C4: ``union_trace_texts``'s byte-identical whole-block dedup (C-002,
    out of scope for this WP) is unchanged by the base-comparison key fix."""
    text = "## Notes\nbody line\nbody line\n"
    merged = union_trace_texts(text, text)
    assert merged.count("## Notes") == 1
    assert merged.count("body line") == 2
