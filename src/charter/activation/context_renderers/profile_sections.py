"""Profile-channel render sections (WP12).

A loaded agent profile is a first-class governance entry vector: the implement
loop loads it on every work package. Before WP12 only ``_render_profile_directives``
/ ``_render_profile_tactics`` existed in :mod:`charter.activation.context`, so a profile that
resolved a procedure, styleguide, or toolguide reached its agent with none of them.

This module houses the shared selector-section renderer and the render paths for
the kinds a profile *attests*:

* **styleguide / toolguide** — schema-attested inline reference kinds
  (``styleguide-references`` / ``toolguide-references``). These render
  **pointer-only** (a header line + ``--include`` fetch stanza, ``body_fn=None``)
  BY DESIGN, not as a silent no-op: it is a deliberate NFR-001 token-budget
  choice. Their bodies are large and shaped unlike the other kinds', so they are
  pulled on demand rather than inlined into every profile load — keeping the
  profile block within budget. See :func:`render_profile_styleguides` /
  :func:`render_profile_toolguides`.
* **procedure** — reached through the profile *channel*: WP08's
  ``walk_edges({requires, specializes_from})`` traversal
  (:meth:`AgentProfileRepository.profile_channel_procedure_ids`), **not** a
  ``resolve_context`` seed set (profiles carry no outbound ``scope`` edge, so a
  ``resolve_context`` seed would measure zero at any depth — R-3). This is the
  mechanism that carries the PR #3007 exemplar
  ``procedure:onboard-external-agent-to-pack`` — reached from
  ``agent_profile:doctrine-daphne`` by a ``requires`` edge — to the agent.

Unattested kinds (asset / anti-pattern / paradigm) are **not** invented into a
profile section; deciding a profile delivers them is a doctrine question the schema
does not answer, so they are deferred under C-007.

The renderer lives here rather than in :mod:`charter.activation.context` so the shared,
WP-contended ``context.py`` does not grow: ``context.py`` imports these functions
and keeps only its directive/tactic paths. The catalog-miss + fetch-stanza +
budget primitives previously lived in ``charter.activation.context`` and were re-used here
via a function-local import to avoid a module-load cycle (``context`` imports
this module at top level). WP04 (#2532) dissolved that cycle by relocating the
three cycle symbols to their own leaf homes (none of which import ``context``),
so they are now imported at top level like every other dependency.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import TYPE_CHECKING, Protocol

from charter.activation._catalog_miss import (
    emit_catalog_miss_warning,
    format_catalog_miss_stanza,
)
from charter.activation.context_renderers.artifact_bodies import (
    _format_inline_directive_body,
    _format_profile_directive_code,
)
from charter.activation.context_renderers.catalog_diagnosis import _diagnose_catalog_miss
from charter.activation.context_renderers.fetch_stanza import (
    render_fetch_stanza as _render_fetch_stanza,
)
from charter.activation.context_renderers.token_budget import (
    _PROFILE_INLINE_BODY_LIMIT_CHARS,
    _budget_estimate,
)
from charter.activation.progressive_disclosure import (
    STATED_DEFAULT_WHEN,
    profile_channel_references,
)
from charter.offering.drg.models import NodeKind

if TYPE_CHECKING:
    from charter.offering.agent_profiles import AgentProfile

# ``_render_profile_directives`` / ``_render_profile_tactics`` de-exported after
# the context.py re-export shim retirement (doctrine-built-in-seam-consolidation
# WP06): no external ``src/`` importer remains. Both stay module-internal,
# called by ``_render_profile_sections`` below.
__all__ = [
    "_render_profile_sections",
]


# Styleguide and toolguide profile sections are pointer-only by design: their
# bodies are fetched on demand rather than inlined on every profile load.
_STYLEGUIDE_TOOLGUIDE_POINTER_ONLY_REASON: str = (
    "styleguide/toolguide profile sections are pointer-only by design "
    "(NFR-001 token budget): their bodies are pulled on demand via the "
    "--include fetch stanza, never inlined on every profile load"
)


_PROFILE_DIRECTIVES_HEADER_TPL = "Profile-Cited Directives ({profile_id}):"
_PROFILE_TACTICS_HEADER_TPL = "Profile-Cited Tactics ({profile_id}):"
_PROFILE_STYLEGUIDES_HEADER_TPL = "Profile-Cited Styleguides ({profile_id}):"
_PROFILE_TOOLGUIDES_HEADER_TPL = "Profile-Cited Toolguides ({profile_id}):"
# Procedures arrive through the profile *channel* (a ``requires`` DRG edge), not an
# inline citation list, so the header reads "Resolved" rather than "Cited".
_PROFILE_PROCEDURES_HEADER_TPL = "Profile-Resolved Procedures ({profile_id}):"
_PROFILE_CODE_CHANGE_WHEN = "are about to apply a code change"
_STYLEGUIDE_TOOLGUIDE_POINTER_ONLY_REASON = (
    "Styleguide and toolguide bodies vary in shape and are fetched on demand "
    "under the NFR-001 token budget."
)

# WP01 (deliver-loaded-doctrine, FR-005): the stated reason styleguide/toolguide
# profile sections render pointer-only (``body_fn=None``). This is a DELIBERATE
# NFR-001 token-budget decision -- their bodies are large and pulled on demand --
# not a silent no-op. This constant is a documented, human-readable stated
# reason surfaced in the render-policy docstrings below (the FR-005
# discoverability requirement); it is not imported or asserted by any test.
# Named here (rather than left as an incidental "bodies vary" aside) so the
# choice is discoverable at the point of decision.
_STYLEGUIDE_TOOLGUIDE_POINTER_ONLY_REASON: str = (
    "styleguide/toolguide profile sections are pointer-only by design "
    "(NFR-001 token budget): their bodies are pulled on demand via the "
    "--include fetch stanza, never inlined on every profile load"
)

# --- WP01: suggests-delivery render policy (C4) -----------------------------
# The NodeKind values the profile channel delivers when it reaches an artefact
# via a ``suggests`` edge. Deliberately EXCLUDES ``asset`` / ``anti_pattern``
# (non-activatable kinds, C-004 — keeping anti_pattern topology validation-tier
# only, never accidentally delivered) and ``agent_profile`` (a lineage
# pass-through hop, never delivered as doctrine to itself).
_PROFILE_SUGGESTS_DELIVERED_KINDS: frozenset[str] = frozenset(
    {
        NodeKind.PARADIGM.value,
        NodeKind.DIRECTIVE.value,
        NodeKind.TACTIC.value,
        NodeKind.STYLEGUIDE.value,
        NodeKind.TOOLGUIDE.value,
        NodeKind.PROCEDURE.value,
    }
)

# Deterministic render order and, per kind, the ``ActiveCharterService`` catalog-repo
# attribute plus the human section title.
_SUGGESTS_KIND_RENDER: tuple[tuple[str, str, str], ...] = (
    (NodeKind.PARADIGM.value, "paradigms", "Paradigms"),
    (NodeKind.DIRECTIVE.value, "directives", "Directives"),
    (NodeKind.TACTIC.value, "tactics", "Tactics"),
    (NodeKind.STYLEGUIDE.value, "styleguides", "Styleguides"),
    (NodeKind.TOOLGUIDE.value, "toolguides", "Toolguides"),
    (NodeKind.PROCEDURE.value, "procedures", "Procedures"),
)

_PROFILE_SUGGESTED_HEADER_TPL = "Profile-Suggested {title} ({profile_id}):"
_URN_SEP = ":"


class _CatalogRepoLike(Protocol):
    """Minimal catalog-repository shape the profile renderers look up against."""

    def get(self, item_id: str) -> object | None: ...


def format_inline_named_body(artifact: object) -> list[str]:
    """Render an artifact's ``Name`` / ``Purpose`` / ``Steps`` inline body.

    Shared by the tactic and procedure renderers — both carry a
    ``name`` / ``purpose`` / ``steps`` shape. Each step renders its ``title`` as
    the header line; WP01 (FR-004) then renders a non-empty ``description`` as an
    indented sub-line beneath it. When a step carries a ``description`` but no
    ``title`` the description remains the header line (no sub-line), so the
    output is byte-identical to the pre-WP01 fall-through for that shape.
    """
    body: list[str] = []
    name = getattr(artifact, "name", None)
    if isinstance(name, str) and name:
        body.append(f"    Name: {name}")
    purpose = getattr(artifact, "purpose", None)
    if isinstance(purpose, str) and purpose.strip():
        body.append(f"    Purpose: {purpose.strip()}")
    steps = getattr(artifact, "steps", None)
    if isinstance(steps, list) and steps:
        body.append("    Steps:")
        for step in steps:
            title = getattr(step, "title", None)
            description = getattr(step, "description", None)
            header = title or description or str(step)
            body.append(f"      - {header}")
            # Only a sub-line when the title is the header AND a distinct,
            # non-empty description exists — never duplicate a description that
            # already stands in as the header (the title-less fall-through).
            if (
                isinstance(title, str)
                and title.strip()
                and isinstance(description, str)
                and description.strip()
            ):
                body.append(f"        {description.strip()}")
    return body


def _resolve_catalog_artifact(
    repo: _CatalogRepoLike | None,
    artifact_id: str,
) -> object | None:
    """Best-effort catalog lookup; ``None`` on a missing repo or a lookup failure."""
    if repo is None:
        return None
    try:
        return repo.get(artifact_id)
    except Exception:  # noqa: BLE001 — best-effort catalog lookup
        return None


def _catalog_miss_lines(
    *,
    selector_kind: str,
    artifact_id: str,
    repo: _CatalogRepoLike | None,
    profile_id: str,
) -> list[str]:
    """Return the structured catalog-miss stanza and emit the diagnostic warning.

    Shared by every profile-section renderer: a missing catalog artifact
    degrades to the structured miss stanza + warning (FR-013) instead of
    crashing the resolver.
    """
    diagnosis = _diagnose_catalog_miss(artifact_id, repo)
    lines: list[str] = format_catalog_miss_stanza(
        selector_kind=selector_kind,
        artifact_id=artifact_id,
        diagnosis=diagnosis,
        indent="    ",
    )
    emit_catalog_miss_warning(
        selector_kind=selector_kind,
        artifact_id=artifact_id,
        diagnosis=diagnosis,
        context=f"profile:{profile_id}",
    )
    return lines


def _render_selector_entry(
    *,
    raw_id: str,
    rationale: str,
    repo: _CatalogRepoLike | None,
    selector_kind: str,
    profile_id: str,
    when_clause: str,
    body_fn: Callable[[object], list[str]] | None,
) -> list[str]:
    """Render one selector-ref entry: header line + inline body or fetch stanza.

    Mirrors :func:`render_profile_selector_refs`'s per-entry contract: the
    inline body (when ``body_fn`` yields one under the per-entry budget) wins
    over the fetch stanza; a catalog miss degrades to the structured miss
    stanza instead.
    """
    artifact_id = str(raw_id).strip()
    header_line = f"  - {artifact_id}"
    if rationale:
        header_line = f"{header_line}: {rationale}"
    lines = [header_line]

    artifact = _resolve_catalog_artifact(repo, artifact_id)
    if artifact is None:
        lines.extend(
            _catalog_miss_lines(
                selector_kind=selector_kind,
                artifact_id=artifact_id,
                repo=repo,
                profile_id=profile_id,
            )
        )
        return lines

    body_lines = body_fn(artifact) if body_fn is not None else []
    if body_lines and _budget_estimate(body_lines) <= _PROFILE_INLINE_BODY_LIMIT_CHARS:
        lines.extend(body_lines)
    else:
        lines.extend(
            _render_fetch_stanza(
                selector=f"{selector_kind}:{artifact_id}",
                when_clause=when_clause,
            )
        )
    return lines


def render_profile_selector_refs(
    *,
    header: str,
    entries: list[tuple[str, str]],
    repo: _CatalogRepoLike | None,
    selector_kind: str,
    profile_id: str,
    when_clause: str,
    body_fn: Callable[[object], list[str]] | None,
    when_by_id: dict[str, str | None] | None = None,
) -> list[str]:
    """Render one profile section (header + per-entry bodies).

    Each entry emits a ``  - <id>`` header line (optionally ``: <rationale>``),
    then either the inline body (when ``body_fn`` yields one under the per-entry
    budget) or the canonical fetch stanza. A catalog miss degrades to the
    structured miss stanza + warning rather than crashing the resolver (FR-013).
    ``body_fn=None`` always emits the fetch stanza — used for styleguide/toolguide
    as a deliberate NFR-001 token-budget choice (pointer-only by design, not a
    silent no-op): their bodies are pulled on demand rather than inlined on every
    profile load. See :data:`_STYLEGUIDE_TOOLGUIDE_POINTER_ONLY_REASON`.

    ``when_by_id`` supplies a *per-entry* when-clause override (WP01): the
    suggests-delivery renderer carries each artefact's own edge ``when`` rather
    than a single static clause for the whole section. When an id is absent from
    the mapping (or maps to a falsy value) the section-wide ``when_clause`` is the
    fallback — so the existing static-clause callers (styleguide/toolguide/
    procedure) are unaffected when they pass no mapping.
    """
    per_entry_when = when_by_id or {}

    lines: list[str] = [header]
    for raw_id, rationale in entries:
        artifact_id = str(raw_id).strip()
        lines.extend(
            _render_selector_entry(
                raw_id=raw_id,
                rationale=rationale,
                repo=repo,
                selector_kind=selector_kind,
                profile_id=profile_id,
                when_clause=per_entry_when.get(artifact_id) or when_clause,
                body_fn=body_fn,
            )
        )

    return lines


def _ref_entries(refs: Iterable[object]) -> list[tuple[str, str]]:
    """Map a profile reference list to ``(id, rationale)`` entry tuples."""
    return [
        (getattr(ref, "id", ""), getattr(ref, "rationale", "") or "")
        for ref in refs
    ]


def render_profile_styleguides(profile: AgentProfile, service: object) -> list[str]:
    """Render the ``Profile-Cited Styleguides (<profile-id>):`` section (T067).

    Styleguides are a schema-attested profile reference kind. Each entry renders
    as a header line plus the ``--include styleguide:<id>`` fetch stanza and
    NEVER an inlined body (``body_fn=None``): that is a deliberate NFR-001
    token-budget choice, not a silent no-op -- their bodies are pulled on demand.
    See :data:`_STYLEGUIDE_TOOLGUIDE_POINTER_ONLY_REASON`. Empty when none cited.
    """
    refs = list(profile.styleguide_references)
    if not refs:
        return []
    return render_profile_selector_refs(
        header=_PROFILE_STYLEGUIDES_HEADER_TPL.format(profile_id=profile.profile_id),
        entries=_ref_entries(refs),
        repo=getattr(service, "styleguides", None),
        selector_kind="styleguide",
        profile_id=profile.profile_id,
        when_clause=_PROFILE_CODE_CHANGE_WHEN,
        body_fn=None,
    )


def render_profile_toolguides(profile: AgentProfile, service: object) -> list[str]:
    """Render the ``Profile-Cited Toolguides (<profile-id>):`` section (T067).

    Toolguides are a schema-attested profile reference kind, rendered as a header
    line plus the ``--include toolguide:<id>`` fetch stanza and never an inlined
    body (``body_fn=None``): a deliberate NFR-001 token-budget choice, not a
    silent no-op -- bodies are pulled on demand. See
    :data:`_STYLEGUIDE_TOOLGUIDE_POINTER_ONLY_REASON`. Empty when none.
    """
    refs = list(profile.toolguide_references)
    if not refs:
        return []
    return render_profile_selector_refs(
        header=_PROFILE_TOOLGUIDES_HEADER_TPL.format(profile_id=profile.profile_id),
        entries=_ref_entries(refs),
        repo=getattr(service, "toolguides", None),
        selector_kind="toolguide",
        profile_id=profile.profile_id,
        when_clause=_PROFILE_CODE_CHANGE_WHEN,
        body_fn=None,
    )


def render_profile_procedures(profile: AgentProfile, service: object) -> list[str]:
    """Render the ``Profile-Resolved Procedures (<profile-id>):`` section (T068).

    Procedures reach a profile through the profile *channel* — the
    ``walk_edges({requires, specializes_from})`` traversal surfaced by
    :meth:`AgentProfileRepository.profile_channel_procedure_ids` — not through an
    inline citation list. Empty when the profile requires no procedures (a
    fail-closed channel: an absent/unknown profile reaches nothing rather than
    falling open to the whole graph — T069).
    """
    repo = getattr(service, "agent_profiles", None)
    if repo is None:
        return []
    try:
        procedure_ids = repo.profile_channel_procedure_ids(profile.profile_id)
    except Exception:  # noqa: BLE001 — best-effort channel lookup
        procedure_ids = []
    if not procedure_ids:
        return []
    return render_profile_selector_refs(
        header=_PROFILE_PROCEDURES_HEADER_TPL.format(profile_id=profile.profile_id),
        entries=[(pid, "") for pid in procedure_ids],
        repo=getattr(service, "procedures", None),
        selector_kind="procedure",
        profile_id=profile.profile_id,
        when_clause="are about to run this procedure",
        body_fn=format_inline_named_body,
    )


def _bare_id(urn: str) -> str:
    """The artefact id from a DRG URN (``tactic:refactoring-move-method`` -> id)."""
    return urn.split(_URN_SEP, 1)[1] if _URN_SEP in urn else urn


def _kind_of(urn: str) -> str:
    """The kind prefix of a DRG URN (``tactic:foo`` -> ``tactic``)."""
    return urn.split(_URN_SEP, 1)[0] if _URN_SEP in urn else ""


def _consolidate_kind_entries(
    references: list[dict[str, str | None]],
    delivered_ids: set[str],
) -> tuple[list[tuple[str, str]], dict[str, str | None]]:
    """Collapse a kind's reference rows to ``(entries, when_by_id)`` for rendering.

    :func:`~charter.activation.progressive_disclosure.link_references` may emit more than one
    row for the same target id (one per ``(id, relation)`` — e.g. an artefact
    reached both by a ``requires`` and a ``suggests`` edge). For a link section we
    render each id once, preferring the first non-empty ``when`` so an authored
    ``suggests`` applicability wins over a ``requires`` row's absent one. Ordering
    is the deterministic order :func:`link_references` already produced.
    """
    entries: list[tuple[str, str]] = []
    when_by_id: dict[str, str | None] = {}
    seen: set[str] = set()
    for ref in references:
        artifact_id = ref["id"] or ""
        if artifact_id not in delivered_ids:
            continue
        if artifact_id not in seen:
            seen.add(artifact_id)
            entries.append((artifact_id, ref["reason"] or ""))
        if not when_by_id.get(artifact_id):
            when_by_id[artifact_id] = ref["when"]
    return entries, when_by_id


def render_profile_suggested_doctrine(
    profile: AgentProfile, service: object
) -> list[str]:
    """Render the profile channel's ``suggests``-delivered doctrine (WP01, C2–C5).

    The profile channel now follows ``suggests`` edges
    (``PROFILE_CHANNEL_RELATIONS``), so a loaded profile reaches the #3063 A–E
    families (Family A: ``paradigm:domain-driven-design``; Family B: the
    ``refactoring-*`` tactics; …). This renderer surfaces each reached-by-suggests
    artefact as a ``when``-labelled **link** (the canonical fetch stanza), never an
    inlined body (NFR-003) — the ``when`` is the reaching edge's own clause
    (``STATED_DEFAULT_WHEN`` when the edge is ``when``-less), projected by
    :func:`~charter.activation.progressive_disclosure.profile_channel_references`.

    Requires-precedence (C3/A4) is handled inside that projection: an artefact in
    the seed's ``requires``-closure delivers eager and is excluded here, so a
    diamond never double-delivers.

    Fail-closed (like :func:`render_profile_procedures`): an absent/empty channel
    contributes no section rather than falling open to the whole graph.
    """
    repo = getattr(service, "agent_profiles", None)
    if repo is None:
        return []
    try:
        reached = repo.profile_channel_reached(profile.profile_id)
    except Exception:  # noqa: BLE001 — best-effort channel lookup
        return []
    delivered = {u for u in reached if _kind_of(u) in _PROFILE_SUGGESTS_DELIVERED_KINDS}
    if not delivered:
        return []

    seeds = {f"{NodeKind.AGENT_PROFILE.value}{_URN_SEP}{profile.profile_id}"}
    references = profile_channel_references(repo.drg, seeds, reached, delivered)

    lines: list[str] = []
    for kind, repo_attr, title in _SUGGESTS_KIND_RENDER:
        delivered_ids = {_bare_id(u) for u in delivered if _kind_of(u) == kind}
        if not delivered_ids:
            continue
        entries, when_by_id = _consolidate_kind_entries(references, delivered_ids)
        if not entries:
            continue
        lines.extend(
            render_profile_selector_refs(
                header=_PROFILE_SUGGESTED_HEADER_TPL.format(
                    title=title, profile_id=profile.profile_id
                ),
                entries=entries,
                repo=getattr(service, repo_attr, None),
                selector_kind=kind,
                profile_id=profile.profile_id,
                when_clause=STATED_DEFAULT_WHEN,
                body_fn=None,
                when_by_id=when_by_id,
            )
        )
    return lines


# ---------------------------------------------------------------------------
# Directive / tactic profile sections + the whole-profile assembler (WP06
# T029 campsite, #2532). Relocated verbatim from ``charter.activation.context`` — the
# data-model.md seam→home map already named this the "render half" of the
# profile-cited-render consolidation; no WP in the mission's task breakdown
# claimed the move explicitly, so it stayed behind after WP04/WP05 until
# WP06's residual-LOC ceiling required completing it. ``charter.activation.context``
# keeps a ``# FR-009 preserved surface`` re-export (leading-underscore
# aliases, matching every other symbol re-exported from this module) for the
# existing test imports.
# ---------------------------------------------------------------------------


def _render_directive_entry(
    ref: object,
    repo: _CatalogRepoLike | None,
    profile_id: str,
) -> list[str]:
    """Render one directive-reference entry: header line + inline body or fetch stanza.

    RISK-3 (Mission B post-merge): a missing directive degrades to the
    structured catalog-miss stanza + warning instead of the generic
    placeholder. FR-013: ``_diagnose_catalog_miss`` checks
    ``scope_filtered_ids`` first so a scope-filtered directive surfaces
    SCOPE_FILTERED rather than MISSING_ARTIFACT.
    """
    code = _format_profile_directive_code(getattr(ref, "code", ""))
    title = getattr(ref, "name", "") or ""
    rationale = getattr(ref, "rationale", "") or ""
    header_line = f"  - {code}: {title}"
    if rationale:
        header_line = f"{header_line} — {rationale}"
    lines = [header_line]

    directive = _resolve_catalog_artifact(repo, code)
    if directive is None:
        lines.extend(
            _catalog_miss_lines(
                selector_kind="directive",
                artifact_id=code,
                repo=repo,
                profile_id=profile_id,
            )
        )
        return lines

    body_lines = _format_inline_directive_body(directive)
    if body_lines and _budget_estimate(body_lines) <= _PROFILE_INLINE_BODY_LIMIT_CHARS:
        lines.extend(body_lines)
    else:
        lines.extend(
            _render_fetch_stanza(
                selector=f"directive:{code}",
                when_clause=_PROFILE_CODE_CHANGE_WHEN,
            )
        )
    return lines


def _render_profile_directives(
    profile: AgentProfile,
    service: object,
) -> list[str]:
    """Render the ``Profile-Cited Directives (<profile-id>):`` section as a list of lines.

    Returns an empty list when the profile has no ``directive_references``
    so the caller can filter out the header. Each entry is either the
    verbatim body (when under the per-entry budget) OR the
    fetch + when-doing stanza pinned by the ATDD contract.
    """
    refs = list(profile.directive_references)
    if not refs:
        return []

    header = _PROFILE_DIRECTIVES_HEADER_TPL.format(profile_id=profile.profile_id)
    lines: list[str] = [header]
    repo = getattr(service, "directives", None)

    for ref in refs:
        lines.extend(_render_directive_entry(ref, repo, profile.profile_id))

    return lines


def _render_profile_tactics(
    profile: AgentProfile,
    service: object,
) -> list[str]:
    """Render the ``Profile-Cited Tactics (<profile-id>):`` section as a list of lines.

    Returns an empty list when the profile has no ``tactic_references``.
    The fetch stanza uses ``--include tactic:<id>``. Tactics do not carry
    a ``when:`` field today; the conditional falls back to "apply a code
    change" so the prompt remains actionable.
    """
    refs = list(profile.tactic_references)
    if not refs:
        return []
    # WP12/T067: shares the profile-section renderer with the styleguide /
    # toolguide / procedure paths. Byte-identical to the prior inline body.
    return render_profile_selector_refs(
        header=_PROFILE_TACTICS_HEADER_TPL.format(profile_id=profile.profile_id),
        entries=[
            (getattr(ref, "id", ""), getattr(ref, "rationale", "") or "")
            for ref in refs
        ],
        repo=getattr(service, "tactics", None),
        selector_kind="tactic",
        profile_id=profile.profile_id,
        when_clause=_PROFILE_CODE_CHANGE_WHEN,
        body_fn=format_inline_named_body,
    )


# The composed set of profile-channel section renderers ``_render_profile_sections``
# calls, in deterministic render order. Named at module scope (rather than kept
# function-local) so the FR-008 anti-divergence test
# (``tests/charter/test_emit_delivery_bind.py::_REAL_PROJECTED_CHANNELS``) can
# bind its roster to this exact tuple instead of hand-copying/re-deriving it —
# a future 7th renderer added here without a matching roster entry now fails
# that test instead of silently diverging.
_PROFILE_SECTION_RENDERERS: tuple[Callable[[AgentProfile, object], list[str]], ...] = (
    _render_profile_directives,
    _render_profile_tactics,
    render_profile_styleguides,
    render_profile_toolguides,
    render_profile_procedures,
    # WP01 (doctrine-delivery-activation-01KYQVQK): the channel-resolved
    # ``suggests``-delivery section — the profile channel now follows
    # ``suggests``, delivering the #3063 A–E families (paradigm/tactic/…) as
    # ``when``-labelled links. Distinct from the C-007 deferral of
    # schema-attested INLINE citation of asset/anti-pattern/paradigm kinds:
    # this delivers what the CHANNEL reaches, as ``render_profile_procedures``
    # already does.
    render_profile_suggested_doctrine,
)


def _render_profile_sections(
    profile: AgentProfile | None,
    service: object,
) -> str:
    """Render every profile-channel section the profile attests.

    Returns an empty string when *profile* is ``None`` (T069 — an absent
    profile renders nothing, never a fail-open whole-graph fallback) or when
    no section has entries. WP12/T067 widens this beyond directives/tactics to
    the schema-attested styleguide/toolguide kinds and the channel-resolved
    procedure kind (T068). Unattested kinds (asset/anti-pattern/paradigm) are
    C-007 deferrals and contribute no section.
    """
    if profile is None:
        return ""
    blocks = [
        "\n".join(lines)
        for renderer in _PROFILE_SECTION_RENDERERS
        if (lines := renderer(profile, service))
    ]
    return "\n\n".join(blocks)
