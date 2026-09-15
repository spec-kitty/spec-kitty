"""Compact charter view (FR-034, WP07/T041).

Bootstrap mode renders the whole charter governance bundle: paradigms,
directives, tactics, tools, plus the long-form prose body of each
section. Compact mode is what we hand to agents on subsequent action
loads to keep the context window cheap, but until WP07 it dropped the
*identifiers* — directive IDs, tactic IDs, and section anchors — which
agents key on. Issue #790 traced bad agent behaviour to that loss.

The contract this module enforces (and the contract test asserts): for
any charter, the set of directive IDs, tactic IDs, and section anchors
emitted by ``render_compact_view`` is exactly the set emitted by the
bootstrap view. Only long-form prose may be elided in compact mode.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

from charter.activation._doctrine_paths import resolve_project_root
from charter.bundle import CHARTER_MD
from charter.activation.language_scope import infer_repo_languages
from charter.activation.resolver import GovernanceResolutionError, resolve_project_governance


__all__ = [
    "CompactView",
    "extract_section_anchors",
    "render_compact_view",
]

NONE_LABEL = "(none)"


@dataclass(frozen=True)
class CompactView:
    """Structured payload for the compact charter view.

    Tests treat the ID/anchor sets as the contract surface. ``text`` is the
    rendered string suitable for direct inclusion in agent context, and
    ``token_estimate`` is a coarse character-based proxy used by smoke checks
    to verify compact stays meaningfully smaller than bootstrap.

    WP11 (T061, FR-010) widens the steady-state rail: the compact view is the
    render an agent receives on *every load after the first*, so it must carry
    **every** delivered kind — not just directives and tactics — or the
    styleguides, toolguides, procedures and assets that FR-009/FR-011 deliver
    on the bootstrap load evaporate on the next one.
    """

    text: str
    directive_ids: tuple[str, ...] = field(default_factory=tuple)
    tactic_ids: tuple[str, ...] = field(default_factory=tuple)
    styleguide_ids: tuple[str, ...] = field(default_factory=tuple)
    toolguide_ids: tuple[str, ...] = field(default_factory=tuple)
    procedure_ids: tuple[str, ...] = field(default_factory=tuple)
    asset_ids: tuple[str, ...] = field(default_factory=tuple)
    section_anchors: tuple[str, ...] = field(default_factory=tuple)

    @property
    def token_estimate(self) -> int:
        """Rough proxy for token count (4 chars/token heuristic)."""
        return max(1, len(self.text) // 4)


def extract_section_anchors(charter_text: str) -> list[str]:
    """Return ordered, de-duplicated section anchor strings.

    A "section anchor" is the heading text from any ``#``-style
    Markdown heading. We preserve insertion order so anchors line up
    with the bootstrap reading order, and deduplicate so repeated
    headings (rare, but possible) only contribute once to the contract.
    """
    seen: set[str] = set()
    anchors: list[str] = []
    for line in charter_text.splitlines():
        anchor = _extract_markdown_heading(line)
        if not anchor:
            continue
        if anchor in seen:
            continue
        seen.add(anchor)
        anchors.append(anchor)
    return anchors


def _extract_markdown_heading(line: str) -> str | None:
    """Return heading text from an ATX Markdown heading line."""
    stripped = line.strip()
    if not stripped.startswith("#"):
        return None

    level = 0
    while level < len(stripped) and stripped[level] == "#":
        level += 1
    if level == 0 or level > 6:
        return None
    if level == len(stripped) or stripped[level] != " ":
        return None

    anchor = stripped[level + 1 :].strip()
    return anchor or None


def render_compact_view(
    repo_root: Path,
    *,
    directive_ids: Iterable[str] = (),
    tactic_ids: Iterable[str] = (),
    styleguide_ids: Iterable[str] = (),
    toolguide_ids: Iterable[str] = (),
    procedure_ids: Iterable[str] = (),
    asset_ids: Iterable[str] = (),
    section_anchors: Iterable[str] | None = None,
    charter_text: str | None = None,
    suppress_project_resolver: bool = False,
) -> CompactView:
    """Render the compact governance block with IDs + anchors preserved.

    Args:
        repo_root: The mission repo root used to resolve governance.
        directive_ids: Directive IDs the bootstrap view would surface.
            Each ID is emitted verbatim in the compact output.
        tactic_ids: Tactic IDs the bootstrap view would surface.
        styleguide_ids: Styleguide IDs the bootstrap view would surface
            (WP11/T061 — carried on the steady-state rail so they persist
            past the first load).
        toolguide_ids: Toolguide IDs, per ``styleguide_ids``.
        procedure_ids: Procedure IDs (FR-009 delivery), per ``styleguide_ids``.
        asset_ids: Asset IDs (D4 delivery), per ``styleguide_ids``.
        section_anchors: Optional pre-computed anchor list. When omitted
            the helper extracts anchors from ``charter_text`` (or, if
            both are omitted, from ``<repo_root>/.kittify/charter/charter.md``
            when present).
        charter_text: Optional charter body text used for anchor
            extraction; convenient for tests.
        suppress_project_resolver: WP03/#3064 -- when ``True``, the
            ``resolver_directives`` computed by
            :func:`~charter.activation.resolver.resolve_project_governance` (via
            :func:`_resolve_governance_summary`) are NOT merged into the
            ``Directive IDs:`` block; only the caller-supplied
            ``directive_ids`` are emitted. Under a wholly-empty charter,
            ``_resolve_directives_selection`` catalog-falls-back to the
            FULL built-in directive canon (research.md Decision 4) --
            this flag exists so the empty-charter/generic-agent dispatch
            path can suppress that specific merge without changing
            ``_resolve_directives_selection`` (or this function's default
            behaviour) for any other caller. Defaults to ``False`` so every
            existing consumer is unaffected.

    Returns:
        :class:`CompactView` carrying the rendered text and the per-kind
        ID/anchor tuples that form the contract surface.
    """
    directive_tuple = tuple(dict.fromkeys(directive_ids))
    tactic_tuple = tuple(dict.fromkeys(tactic_ids))
    styleguide_tuple = tuple(dict.fromkeys(styleguide_ids))
    toolguide_tuple = tuple(dict.fromkeys(toolguide_ids))
    procedure_tuple = tuple(dict.fromkeys(procedure_ids))
    asset_tuple = tuple(dict.fromkeys(asset_ids))

    if section_anchors is not None:
        anchor_tuple = tuple(dict.fromkeys(section_anchors))
    else:
        if charter_text is None:
            # WP05 (IC-05) — the companion `charter.md` is DISPLAY-only and
            # optional (governance authority lives in `charter.yaml`); a
            # missing/unreadable file degrades to an empty anchor set rather
            # than raising. Consumes the shared `charter.bundle.CHARTER_MD`
            # constant instead of re-declaring the filename locally.
            charter_path = repo_root / CHARTER_MD
            charter_text = ""
            if charter_path.exists():
                try:
                    charter_text = charter_path.read_text(encoding="utf-8")
                except OSError:
                    charter_text = ""
        anchor_tuple = tuple(extract_section_anchors(charter_text))

    text = _render_text(
        repo_root,
        directive_tuple,
        tactic_tuple,
        styleguide_tuple,
        toolguide_tuple,
        procedure_tuple,
        asset_tuple,
        anchor_tuple,
        suppress_project_resolver=suppress_project_resolver,
    )

    return CompactView(
        text=text,
        directive_ids=directive_tuple,
        tactic_ids=tactic_tuple,
        styleguide_ids=styleguide_tuple,
        toolguide_ids=toolguide_tuple,
        procedure_ids=procedure_tuple,
        asset_ids=asset_tuple,
        section_anchors=anchor_tuple,
    )


def _render_text(
    repo_root: Path,
    directive_ids: tuple[str, ...],
    tactic_ids: tuple[str, ...],
    styleguide_ids: tuple[str, ...],
    toolguide_ids: tuple[str, ...],
    procedure_ids: tuple[str, ...],
    asset_ids: tuple[str, ...],
    section_anchors: tuple[str, ...],
    *,
    suppress_project_resolver: bool = False,
) -> str:
    """Render the human-readable compact governance block.

    The format is intentionally line-oriented and stable so downstream
    diffs in agent context stay reviewable. Long-form prose is replaced
    by ID lists and an anchor index. When governance cannot be resolved
    (e.g., the repo lacks ``.kittify`` config) the renderer still emits
    every supplied directive ID, tactic ID, and section anchor — the
    FR-034 contract is "no IDs are silently dropped", so a degraded
    governance block must not erase the IDs the caller already knows.

    ``suppress_project_resolver`` (WP03/#3064) drops the resolver's
    catalog-fallback directives from the merge -- see
    :func:`render_compact_view` for the full rationale. Only the merge is
    affected; ``template_set``/``paradigms``/``tools``/``diagnostics`` still
    come from :func:`_resolve_governance_summary` unconditionally since
    those are not the leaking surface (research.md Decision 4 / the
    contract scope both name the ``Directive IDs:`` block specifically).
    """
    (
        template_set,
        paradigms,
        tools,
        diagnostics,
        resolver_directives,
    ) = _resolve_governance_summary(repo_root)

    effective_resolver_directives: list[str] = (
        [] if suppress_project_resolver else resolver_directives
    )
    merged_directive_ids = tuple(
        dict.fromkeys(list(directive_ids) + effective_resolver_directives)
    )

    lines: list[str] = [
        "Governance:",
        f"  - Template set: {template_set}",
        f"  - Paradigms: {paradigms}",
        f"  - Tools: {tools}",
    ]

    _append_section(lines, "Directive IDs:", merged_directive_ids)
    _append_section(lines, "Tactic IDs:", tactic_ids)
    # WP11 (T061) — the widened rail carries every delivered kind so the
    # steady-state render is not one strictly narrower than the bootstrap one.
    # These four kinds are emitted only when the bundle delivers them: an empty
    # kind adds no heading, keeping the rail compact when nothing is delivered
    # (the FR-034 contract is ID *parity*, not a fixed heading list).
    _append_section_if_present(lines, "Styleguide IDs:", styleguide_ids)
    _append_section_if_present(lines, "Toolguide IDs:", toolguide_ids)
    _append_section_if_present(lines, "Procedure IDs:", procedure_ids)
    _append_section_if_present(lines, "Asset IDs:", asset_ids)
    _append_section(lines, "Section Anchors:", section_anchors)

    if diagnostics:
        lines.append(f"  - Diagnostics: {' | '.join(diagnostics)}")

    # Reference repo languages / project root only as a footnote so the
    # compact view stays one-screen even on big charters.
    try:
        languages = infer_repo_languages(repo_root)
        if languages:
            lines.append(f"  - Languages: {', '.join(sorted(languages))}")
    except Exception:  # pragma: no cover - defensive
        pass

    try:
        project_root = resolve_project_root(repo_root)
        if project_root is not None and project_root != repo_root:
            lines.append(f"  - Doctrine layer root: {project_root}")
    except Exception:  # pragma: no cover - defensive
        pass

    return "\n".join(lines)


def _resolve_governance_summary(
    repo_root: Path,
) -> tuple[str, str, str, list[str], list[str]]:
    template_set = NONE_LABEL
    paradigms = NONE_LABEL
    tools = NONE_LABEL
    diagnostics: list[str] = []
    resolver_directives: list[str] = []

    try:
        resolution = resolve_project_governance(repo_root)
    except GovernanceResolutionError as exc:
        diagnostics.append(f"governance unresolved ({exc})")
        return template_set, paradigms, tools, diagnostics, resolver_directives
    except Exception as exc:  # pragma: no cover - defensive degrade
        diagnostics.append(f"governance unavailable ({exc})")
        return template_set, paradigms, tools, diagnostics, resolver_directives

    if resolution.paradigms:
        paradigms = ", ".join(resolution.paradigms)
    if resolution.tools:
        tools = ", ".join(resolution.tools)
    diagnostics.extend(list(resolution.diagnostics))
    resolver_directives = list(resolution.directives)
    return resolution.template_set, paradigms, tools, diagnostics, resolver_directives


def _append_section(lines: list[str], title: str, values: Iterable[str]) -> None:
    lines.append(title)
    entries = list(values)
    if not entries:
        lines.append(f"  - {NONE_LABEL}")
        return
    for entry in entries:
        lines.append(f"  - {entry}")


def _append_section_if_present(lines: list[str], title: str, values: Iterable[str]) -> None:
    """Emit a section only when it carries at least one id (WP11/T061).

    Used for the widened-rail kinds so a load that delivers nothing of a kind
    adds no heading — the rail stays compact when a kind is absent while still
    carrying every id when the bundle delivers it.
    """
    entries = list(values)
    if entries:
        _append_section(lines, title, entries)
