"""Canonical work-package subtask row patterns + the snapshot-backed guard resolver.

A WP's subtasks are historically the checkbox rows of the form
``- [ ] T001 <desc>`` / ``- [x] T001 <desc>`` in ``tasks.md`` and the WP prompt
body. Since #2816 IC-10 (FR-016 / SC-010) the lane-transition guard no longer
blocks on those checkbox rows: subtask completion is **solely** event-sourced.
The guard's blocking source is now the pair defined here — ``authored_subtask_roster``
(the authored ``subtasks:`` frontmatter list = static design intent) and
``unchecked_subtask_ids_from_snapshot`` (completion from the reduced event-log
``subtasks`` slot, fail-closed). The row patterns below survive for the callers
that still legitimately parse checkboxes: the **migration backfill** (seeds the
snapshot from legacy checkboxes, C-010), the ``move-task --to planned``
**rollback** writer, and the **acceptance gate**. Do not re-derive any of these
locally (canonical-sources rule).

Semantics (mirrors the guard, ``_check_unchecked_subtasks``):

* A ``T`` id of at least three digits is mandatory (``\\d{3,}`` so ids past
  T999 still match).
* Only implementation rows count: validation/procedure command rows
  (``- [ ] swift test``), prose checkboxes, and anything inside fenced code
  blocks are not work-package subtasks.
* Section semantics (#2346 / #2324): a heading (``##``–``####``) belongs to
  the WP named by its FIRST ``WPxx`` token, NOT any mention — so
  ``### WP03 … (depends: WP01)`` does not re-enter WP01's section.
* Section semantics (NFR-005): once a *different* WP's heading is seen, the
  section is closed for the rest of the document — a later re-appearing
  ``## WPxx`` heading for the same WP does not reopen it. This is a
  deliberate correction of the writer's pre-unification behavior, which used
  to re-enter such a heading; the guard/read side always had this right.

All three callers (lane-transition guard, dashboard progress, rollback
writer) are driven by the single private ``_walk_wp_section`` generator
below — it is the only place the heading rule, fence skipping, and
section-exit semantics are encoded.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping
from pathlib import Path
from typing import Any

from kernel._safe_re import re

#: WP-file name matcher tail: ``WP04.md`` / ``WP04-slug.md`` / ``WP04_slug.md``
#: but NOT ``WP04b.md`` — the same word-boundary rule the emit / wp_view locators
#: use (mirrors ``status.wp_view._WP_FILE_SEP``). Kept in lockstep by convention;
#: consolidating the four private WP-file locators is out of scope for this WP.
_WP_FILE_SEP = r"(?:[-_.]|\.md$)"

#: Unchecked canonical subtask row: ``- [ ] T001 ...`` (blocks lane transitions).
UNCHECKED_SUBTASK_ROW = re.compile(r"^-\s*\[\s*\]\s*(T\d{3,})\b")

#: Checked canonical subtask row: ``- [x] T001 ...``.
CHECKED_SUBTASK_ROW = re.compile(r"^-\s*\[[xX]\]\s*(T\d{3,})\b")


def count_subtask_rows(text: str) -> tuple[int, int]:
    """Return ``(done, total)`` canonical subtask rows in *text*.

    Rows inside fenced code blocks (``` or ~~~) are ignored — task-like
    example lines in implementation notes are not real subtasks, matching the
    guard's fence handling.

    This counts across the whole document, not a single WP's section, so it
    does not consume ``_walk_wp_section`` (which is WP-scoped) — it keeps its
    own minimal fence-aware loop but shares the two row-pattern constants.
    """
    done = 0
    total = 0
    in_code_fence = False
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped.startswith(("```", "~~~")):
            in_code_fence = not in_code_fence
            continue
        if in_code_fence:
            continue
        if CHECKED_SUBTASK_ROW.match(stripped):
            done += 1
            total += 1
        elif UNCHECKED_SUBTASK_ROW.match(stripped):
            total += 1
    return done, total


def iter_unchecked_subtask_rows(text: str) -> Iterator[str]:
    """Yield the raw (stripped) unchecked canonical subtask rows in *text*.

    Whole-file, fence-aware, ``T###``-scoped — the canonical substitute for a
    bespoke ``re.match(r"^\\s*-\\s*\\[ \\]")`` whole-file scan (#2567). Unlike
    that stray regex, prose ``- [ ]`` checkboxes without a ``T###`` id, and
    any row inside a fenced code block, are not real implementation subtasks
    and are not yielded — this is an intentional narrowing of what counts as
    "unchecked" (FR-009), ratified by a characterization test rather than
    folded in silently.

    Mirrors ``count_subtask_rows``'s fence loop exactly, sharing the same
    ``UNCHECKED_SUBTASK_ROW`` constant, but yields the offending line string
    instead of a count — callers that need to *report* unchecked rows (e.g.
    the acceptance gate) need the strings; ``count_subtask_rows`` only needs
    the totals.
    """
    in_code_fence = False
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped.startswith(("```", "~~~")):
            in_code_fence = not in_code_fence
            continue
        if in_code_fence:
            continue
        if UNCHECKED_SUBTASK_ROW.match(stripped):
            yield stripped


def _heading_wp_token(line: str) -> str | None:
    """Return the FIRST ``WPxx`` token in *line* if it is a ``##``-``####`` heading."""
    if not re.match(r"^#{2,4}[^#]", line):
        return None
    wp_tokens = re.findall(r"\bWP\d{2,}\b", line)
    return wp_tokens[0] if wp_tokens else None


def _walk_wp_section(lines: list[str], wp_id: str) -> Iterator[tuple[int, str, bool]]:
    """Yield ``(index, raw_line, checked)`` for canonical rows in *wp_id*'s section.

    The single, canonical definition of "what counts as a WP subtask row",
    consumed identically by the lane-transition guard, the dashboard, and the
    rollback writer. Encodes, once:

    * **First-``WPxx``-token heading rule** (#2346/#2324): a heading
      (``##``-``####``) belongs to the WP named by the *first* ``WPxx`` token
      found in it, not any mention — ``### WP03 … (depends: WP01)`` belongs
      to WP03, not WP01.
    * **Fenced-code skipping**: lines between a matching ``` `/`~~~` pair are
      never yielded as rows, even if they look like subtask rows.
    * **Break-on-section-exit**: once a *different* WP's heading is seen
      after the target section opened, the section is closed for the rest of
      the document — a later re-appearing ``## wp_id`` heading does not
      reopen it.

    Only rows matching ``CHECKED_SUBTASK_ROW``/``UNCHECKED_SUBTASK_ROW`` are
    yielded; the *index* is the position in *lines* so a caller can either
    read-count (ignore the index) or mutate in place (index back into
    *lines*) without a second parallel walk.
    """
    in_wp_section = False
    in_code_fence = False
    for index, line in enumerate(lines):
        stripped = line.strip()

        if stripped.startswith(("```", "~~~")):
            in_code_fence = not in_code_fence
            continue
        if in_code_fence:
            continue

        heading_wp = _heading_wp_token(line)
        if heading_wp == wp_id:
            in_wp_section = True
            continue
        if in_wp_section and heading_wp is not None and heading_wp != wp_id:
            break  # entered a different WP's section — closed for the rest of the doc

        if not in_wp_section:
            continue

        checked_match = CHECKED_SUBTASK_ROW.match(stripped)
        if checked_match:
            yield index, line, True
            continue
        unchecked_match = UNCHECKED_SUBTASK_ROW.match(stripped)
        if unchecked_match:
            yield index, line, False


def iter_wp_section_subtask_rows(tasks_md_text: str, wp_id: str) -> Iterator[tuple[str, bool]]:
    """Yield ``(task_id, checked)`` for canonical rows in *wp_id*'s tasks.md section.

    The standard convention keeps the checkable ``- [ ] T### …`` rows in
    ``tasks.md``, grouped under per-WP headings — the source the
    lane-transition guard blocks on. Section semantics are driven by
    ``_walk_wp_section`` (see its docstring for the exact rules).
    """
    lines = tasks_md_text.split("\n")
    for _index, line, checked in _walk_wp_section(lines, wp_id):
        stripped = line.strip()
        pattern = CHECKED_SUBTASK_ROW if checked else UNCHECKED_SUBTASK_ROW
        match = pattern.match(stripped)
        if match:
            yield match.group(1), checked


def count_wp_section_subtask_rows(tasks_md_text: str, wp_id: str) -> tuple[int, int]:
    """Return ``(done, total)`` canonical rows in *wp_id*'s tasks.md section."""
    done = 0
    total = 0
    for _task_id, checked in iter_wp_section_subtask_rows(tasks_md_text, wp_id):
        total += 1
        if checked:
            done += 1
    return done, total


def uncheck_wp_section_subtask_rows(tasks_md_text: str, wp_id: str) -> str:
    """Return *tasks_md_text* with all checked T### rows in *wp_id*'s section unchecked.

    Applies the same section and fence semantics as the lane-transition guard
    and the dashboard counter, via ``_walk_wp_section`` — including the
    break-on-section-exit rule: a re-appearing ``## wp_id`` heading later in
    the document is NOT re-entered, so only the *first* section's checked
    rows are ever flipped (NFR-005 correction — the writer previously
    re-entered such a heading; the guard/dashboard never did).

    Returns the original text unchanged when the section has no checked rows
    (no allocation, no write). Used by ``move-task --to planned`` to reset
    subtask state on WP rollback (#2513): a rolled-back WP must be
    re-implemented, so leaving its subtasks checked would be a lie.
    """
    lines = tasks_md_text.split("\n")
    flip_indices = {index for index, _line, checked in _walk_wp_section(lines, wp_id) if checked}
    if not flip_indices:
        return tasks_md_text

    changed = False
    result: list[str] = []
    for index, line in enumerate(lines):
        if index not in flip_indices:
            result.append(line)
            continue
        new_line = re.sub(r"\[[xX]\]", "[ ]", line, count=1)
        if new_line != line:
            changed = True
        result.append(new_line)
    return "\n".join(result) if changed else tasks_md_text


# ---------------------------------------------------------------------------
# Snapshot-backed guard resolver (#2816 IC-10 / FR-016 / SC-010)
# ---------------------------------------------------------------------------
# The lane-transition guard's blocking source: the authored roster (frontmatter
# static design intent) + event-sourced completion (the reduced ``subtasks``
# slot). This retires the ``tasks.md`` checkbox as the subtask-completion proxy
# (the D-13 incoherence: a raw checkbox edit without ``mark-status`` showed
# frozen progress). ``mark-status`` -> ``emit_inner_state_changed`` -> snapshot
# is now the SOLE completion authority.


class SubtaskRosterResolutionError(RuntimeError):
    """The authored subtask roster could not be resolved safely."""


def _locate_wp_file(feature_dir: Path, wp_id: str) -> Path:
    """Locate the single canonical WP markdown file for *wp_id* under ``tasks/``.

    Mirrors the word-boundary rule the emit / wp_view locators use
    (``WP04.md`` / ``WP04-slug.md`` but not ``WP04b.md``). Missing or ambiguous
    sources are errors: collapsing them to an empty roster would make the review
    gate fail open and conflate corruption with an explicitly authored ``[]``.
    """
    tasks_dir = feature_dir / "tasks"
    if not tasks_dir.exists():
        raise SubtaskRosterResolutionError(
            f"Cannot resolve subtask roster for {wp_id}: tasks directory is missing"
        )
    pattern = re.compile(rf"^{re.escape(wp_id)}{_WP_FILE_SEP}", re.IGNORECASE)
    matches = [
        path
        for path in tasks_dir.glob("*.md")
        if path.name.lower() != "readme.md" and pattern.match(path.name)
    ]
    if not matches:
        raise SubtaskRosterResolutionError(
            f"Cannot resolve subtask roster for {wp_id}: work-package file is missing"
        )
    if len(matches) > 1:
        paths = ", ".join(path.name for path in sorted(matches))
        raise SubtaskRosterResolutionError(
            f"Cannot resolve subtask roster for {wp_id}: ambiguous files ({paths})"
        )
    return matches[0]


def authored_subtask_roster(feature_dir: Path, wp_id: str) -> list[str]:
    """Return the authored subtask-id roster for *wp_id* from its WP frontmatter.

    The roster (which task ids belong to *wp_id*) is static design intent,
    authored in the WP file's ``subtasks:`` frontmatter list — NOT the
    ``tasks.md`` checkbox rows. Since #2816 IC-10 (FR-016) retired the markdown
    checkbox as the subtask-completion proxy, the guard sources its roster here
    (frontmatter) and its completion from the reduced snapshot slot
    (:func:`unchecked_subtask_ids_from_snapshot`). Sourcing the roster from the
    frontmatter — not by re-parsing ``tasks.md`` — is what makes checkbox
    removal safe: an emptied ``tasks.md`` can no longer silently empty the
    roster and disable the guard.

    Returns the task ids in authored order, de-duplicated and coerced to
    ``str``. Only an explicitly readable empty ``subtasks`` list yields ``[]``
    ("nothing to block on"). Missing, ambiguous, or malformed WP metadata raises
    :class:`SubtaskRosterResolutionError` so transition callers fail closed.
    """
    wp_file = _locate_wp_file(feature_dir, wp_id)
    # Lazy imports: ``core`` must not import ``status`` at module scope
    # (``status.emit`` imports THIS module — a top-level edge would cycle).
    from specify_cli.frontmatter import FrontmatterManager
    from specify_cli.status import WPMetadata

    try:
        frontmatter, _body = FrontmatterManager().read(wp_file)
        if "subtasks" not in frontmatter:
            raise SubtaskRosterResolutionError(
                f"Cannot resolve subtask roster for {wp_id}: subtasks key is missing"
            )
        metadata = WPMetadata.model_validate(frontmatter, strict=False)
    except SubtaskRosterResolutionError:
        raise
    except Exception as exc:
        raise SubtaskRosterResolutionError(
            f"Cannot resolve subtask roster for {wp_id}: {wp_file.name} is unreadable"
        ) from exc
    return normalize_authored_subtask_roster(metadata.subtasks)


def normalize_authored_subtask_roster(raw_values: Iterable[object]) -> list[str]:
    """Normalize authored subtask IDs in order, trimming and de-duplicating."""
    seen: set[str] = set()
    roster: list[str] = []
    for raw in raw_values:
        task_id = str(raw).strip()
        if task_id and task_id not in seen:
            seen.add(task_id)
            roster.append(task_id)
    return roster


def unchecked_subtask_ids_from_snapshot(
    feature_dir: Path, wp_id: str, roster: Iterable[str]
) -> list[str]:
    """Return the *roster* ids whose reduced-snapshot ``subtasks`` status is not DONE.

    The single, fail-closed completion resolver the lane-transition guard blocks
    on since #2816 IC-10 (FR-016 / SC-010). Completion is read ONLY from the
    event-sourced reduced snapshot's ``subtasks`` slot (written by
    ``mark-status``'s ``emit_inner_state_changed`` call) — never from ``tasks.md``
    checkbox bytes, which the cutover retired as an incoherent proxy (D-13).

    Fail-closed (mirrors ``emit._infer_subtasks_complete``): a WP with an
    authored roster but an absent/silent snapshot slot has EVERY roster id
    reported incomplete — an unprovable completeness state must block, never
    fall open. An empty roster yields ``[]`` ("nothing to block on").
    """
    roster_ids = [str(task_id) for task_id in roster]
    if not roster_ids:
        return []
    # Lazy import: see ``authored_subtask_roster`` — avoids the core->status cycle.
    from specify_cli.status import is_subtask_terminal, wp_snapshot_state

    wp_state = wp_snapshot_state(feature_dir, wp_id)
    subtasks: Mapping[str, Any] = {}
    if wp_state is not None:
        raw = wp_state.get("subtasks")
        if isinstance(raw, Mapping):
            subtasks = raw
    return [task_id for task_id in roster_ids if not is_subtask_terminal(subtasks.get(task_id, ""))]


def unchecked_subtask_ids_from_event_stream(
    event_stream: Any,
    wp_id: str,
    roster: Iterable[str],
) -> list[str]:
    """Return incomplete roster ids from an already-resolved event stream.

    Transactional callers use this form when canonical status lives on a
    coordination branch that has no materialized worktree.  The completion
    semantics are identical to :func:`unchecked_subtask_ids_from_snapshot`.
    """
    from specify_cli.status import is_subtask_terminal, reduce

    roster_ids = [str(task_id) for task_id in roster]
    if not roster_ids:
        return []
    state = reduce(
        event_stream.transitions,
        event_stream.annotations,
    ).work_packages.get(wp_id)
    raw_subtasks = state.get("subtasks") if state is not None else None
    subtasks: Mapping[str, Any] = raw_subtasks if isinstance(raw_subtasks, Mapping) else {}
    return [task_id for task_id in roster_ids if not is_subtask_terminal(subtasks.get(task_id, ""))]
