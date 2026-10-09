"""Conditional renderer hook for SPDD/REASONS prompt fragments.

Command templates may contain at most one ``spdd:reasons-block`` per file,
delimited by HTML-comment marker lines:

    <!-- spdd:reasons-block:start -->
    ... markdown content (action-scoped REASONS guidance) ...
    <!-- spdd:reasons-block:end -->

This module exposes :func:`process_spdd_blocks`, which is invoked by the
template materialization seam (``specify_cli.template.asset_generator`` and
``specify_cli.skills.command_renderer``) just after a template file has been
read from disk and before any further processing. The hook keeps content with
markers stripped when the project has the SPDD/REASONS Charter Pack active,
and removes the entire block (including delimiter comment lines and the single
blank line that author convention places around the markers) when inactive.

NFR-001 demands byte-identical output for inactive projects. To meet that, the
inactive branch absorbs the leading blank line that precedes the start marker
in the canonical template layout. Templates are expected to follow the layout

    ...preceding line...
    <BLANK>
    <!-- spdd:reasons-block:start -->
    <BLANK>
    ### REASONS Guidance — ...
    ...
    <BLANK>
    <!-- spdd:reasons-block:end -->
    <BLANK>
    ...following line...

When inactive, the entire span from the blank line preceding the start marker
through the end marker is removed in one cut. That gives back the template
text that existed before WP04 added the markers — bytes for bytes.

Activation is decided by the caller (single source of truth, C-002). The hook
takes ``active`` as a keyword-only parameter; it does not call
``is_spdd_reasons_active`` itself. See ``contracts/prompt-fragment.md``.
"""

from __future__ import annotations

from pathlib import Path

REASONS_BLOCK_START = "<!-- spdd:reasons-block:start -->"
REASONS_BLOCK_END = "<!-- spdd:reasons-block:end -->"


class UnmatchedReasonsBlockError(ValueError):
    """Raised when a SPDD reasons-block start/end marker pair is malformed."""


def process_spdd_blocks(template_text: str, *, active: bool) -> str:
    """Render any SPDD reasons-blocks in ``template_text``.

    Parameters
    ----------
    template_text:
        Raw template text. May contain zero or more (currently expected: zero
        or one) ``spdd:reasons-block`` regions.
    active:
        ``True`` when the SPDD/REASONS Charter Pack is active for the calling
        project (caller passes ``is_spdd_reasons_active(repo_root)``).

        - ``True``: keep block content; strip only the marker comment lines.
        - ``False``: remove the entire block including delimiters AND the blank
          line preceding the start marker, so the result is byte-identical to
          a template that never carried the markers.

    Returns
    -------
    str
        The rewritten template text.

    Raises
    ------
    UnmatchedReasonsBlockError
        If a start marker appears without a matching end (or vice versa), or
        if markers nest.
    """
    if REASONS_BLOCK_START not in template_text and REASONS_BLOCK_END not in template_text:
        return template_text

    # Validate marker balance up-front so a malformed file fails loudly with a
    # clear error rather than silently mangling output.
    _validate_markers(template_text)

    if active:
        return _strip_marker_lines(template_text)
    return _remove_blocks(template_text)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _validate_markers(text: str) -> None:
    """Validate that every start marker has a matching end marker, no nesting."""
    depth = 0
    for line in text.splitlines():
        stripped = line.strip()
        if stripped == REASONS_BLOCK_START:
            if depth != 0:
                raise UnmatchedReasonsBlockError("Nested spdd:reasons-block start marker; flat blocks only.")
            depth += 1
        elif stripped == REASONS_BLOCK_END:
            if depth == 0:
                raise UnmatchedReasonsBlockError("spdd:reasons-block end marker has no matching start.")
            depth -= 1
    if depth != 0:
        raise UnmatchedReasonsBlockError("spdd:reasons-block start marker has no matching end.")


def _strip_marker_lines(text: str) -> str:
    """Active rendering: drop the marker comment lines, keep block content.

    Splits/joins on ``\n`` to preserve whatever trailing newline (or absence
    thereof) the original file carried.
    """
    # Preserve trailing newline structure: splitlines drops a trailing newline,
    # so we track it explicitly.
    has_trailing_newline = text.endswith("\n")
    out_lines: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped in (REASONS_BLOCK_START, REASONS_BLOCK_END):
            continue
        out_lines.append(line)
    rendered = "\n".join(out_lines)
    if has_trailing_newline:
        rendered += "\n"
    return rendered


def _remove_blocks(text: str) -> str:
    """Inactive rendering: remove block + delimiters, including preceding blank.

    Each block region is the closed span:

        [optional preceding blank line] + start_marker_line + ... + end_marker_line

    Plus the line terminator after the end marker. Removing this entire span
    yields the pre-feature template byte-for-byte, since author convention
    surrounds the markers with one blank line on each side.
    """
    has_trailing_newline = text.endswith("\n")
    lines = text.splitlines()

    out_lines: list[str] = []
    i = 0
    n = len(lines)
    while i < n:
        if lines[i].strip() == REASONS_BLOCK_START:
            # Drop the immediately preceding blank line if we already emitted
            # one (this is the blank line author convention places before the
            # start marker to separate it from surrounding prose).
            if out_lines and out_lines[-1] == "":
                out_lines.pop()
            # Skip lines until we consume the end marker.
            i += 1
            while i < n and lines[i].strip() != REASONS_BLOCK_END:
                i += 1
            # Also consume the end marker itself, if present (validation
            # already guarantees it is).
            if i < n:
                i += 1
            continue
        out_lines.append(lines[i])
        i += 1

    rendered = "\n".join(out_lines)
    if has_trailing_newline:
        rendered += "\n"
    return rendered


def apply_spdd_blocks_for_project(template_text: str, repo_root: Path | None) -> str:
    """Convenience wrapper: gate ``process_spdd_blocks`` on charter activation.

    Resolves activation by calling
    :func:`charter.offering.spdd_reasons.activation.is_spdd_reasons_active` against
    ``repo_root``. When ``repo_root`` is ``None`` the helper assumes the pack
    is inactive (the safer default — block content is removed entirely so
    inactive projects render byte-identical templates).

    This is the single seam that template materialization should call so all
    template paths share one activation gate (no drift across renderers).
    """
    if REASONS_BLOCK_START not in template_text and REASONS_BLOCK_END not in template_text:
        # Fast path: no marker, no work, no activation read.
        return template_text

    if repo_root is None:
        return process_spdd_blocks(template_text, active=False)

    # Local import to avoid a hard module-load dependency cycle when the
    # activation module imports tooling that touches templates.
    from charter.offering.spdd_reasons.activation import is_spdd_reasons_active

    return process_spdd_blocks(template_text, active=is_spdd_reasons_active(repo_root))


__all__ = [
    "REASONS_BLOCK_END",
    "REASONS_BLOCK_START",
    "UnmatchedReasonsBlockError",
    "apply_spdd_blocks_for_project",
    "process_spdd_blocks",
]
