"""Pure requirement-mapping decision core for ``agent tasks map-requirements`` (WP04).

This module lifts ``map_requirements``' FR↔WP **mapping + new-ref validation +
coverage** decision out of the interleaved command body into ONE pure function,
:func:`plan_mapping`. Originally a behaviour-preserving (pure-parity) extraction
(FR-005 / FR-002 / NFR-001); mission ``requirement-id-grammar-01M3NRCA`` / WP03
changes the behaviour deliberately: the merge is now append-only (existing
items are kept byte-identical, in place, never re-sorted -- FR-005) and the
per-ref verdict routes through the single grammar authority
(:mod:`specify_cli.requirement_mapping.grammar`, C-001) via ``grammar.classify``
instead of the retired ``validate_ref_format``/``validate_refs`` pair, so a
declared Success-Criterion or letter-suffixed id is accepted (FR-006) and a
foreign-qualified citation (``<mission-slug>#<ID>``) is appended like any
other accepted ref, never blocking (FR-010/FR-019).

Design (functional core / imperative shell):

* The orchestrator (``map_requirements``) performs all filesystem / git reads
  (spec.md parse, per-WP frontmatter, tasks.md fallback) and freezes the results
  in a :class:`MappingRequest`.
* :func:`plan_mapping` is **PURE** (INV-4) — no filesystem, git, status-emission,
  rendering, or clock access — and returns a :class:`MappingPlan`:
  - ``to_write`` — the per-WP merged ``requirement_refs`` the shell writes to
    frontmatter (empty in ``tracker_only`` mode — that mode touches only
    ``tracker_refs``, a shell concern).
  - ``offenders`` — the PRE-write new-ref validation buckets (``malformed`` from
    the format check, ``unknown_spec_id`` from the spec-membership check). The
    shell gates on these BEFORE the write loop, so a bad new ref refuses with NO
    write, exactly as the un-refactored command did.
  - ``unmapped_fr`` — the functional FRs left uncovered after the projected
    write, i.e. ``compute_coverage``'s ``unmapped_functional`` over
    ``{**existing_all_refs, **to_write}``.

**Write-timing note (parity-critical, FR-002 / NFR-001).** The core deliberately
does NOT reproduce the command's *post-write* stale-refs gate (the hard-fail that
re-reads EVERY WP's raw frontmatter AFTER the write loop). That gate stays in the
imperative shell at its ORIGINAL sequence position — AFTER the frontmatter write —
so a pre-existing stale ref on an untouched WP still refuses (exit 1) with the OLD
partial write already on disk. The core owns only the PRE-write decision; the
shell owns the write side effect and the post-write gate, preserving the exact
partial-write-on-refusal behaviour.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from specify_cli.requirement_mapping import compute_coverage, grammar

# Operator-facing mode token (data-model §MappingRequest) whose merge arm writes
# no ``requirement_refs`` — only ``tracker_refs`` (persisted by the shell).
TRACKER_ONLY_MODE = "tracker_only"


@dataclass(frozen=True)
class MappingRequest:
    """Every fact :func:`plan_mapping` needs — all resolved by the shell.

    The shell (``map_requirements``) performs the I/O (spec.md parse, per-WP
    frontmatter reads, tasks.md fallback parse) and freezes the results here so
    the decision is pure.
    """

    # Parsed spec requirement ids (``parse_requirement_ids_from_spec_md``):
    spec_all_ids: frozenset[str]
    spec_functional_ids: frozenset[str]
    # New mappings the operator supplied, per WP, already canonicalised by the
    # shell (malformed tokens verbatim) -- mode-specific building (batch JSON
    # parse / individual comma-split) stays in the shell because its error
    # arms raise ``typer.Exit`` (WP03 T016: ``_canonical_input_refs`` replaces
    # the old blind ``.upper()``).
    new_mappings: dict[str, list[str]]
    # Existing normalized ``requirement_refs`` for ALL WPs (pre-write), the single
    # read that feeds BOTH the union-merge base AND the coverage projection.
    existing_all_refs: dict[str, list[str]]
    # tasks.md-parsed refs per WP — the union-merge fallback when frontmatter empty.
    tasks_md_refs: dict[str, list[str]]
    mode: str
    replace: bool
    # WP06 (#3396) T032a: bare-prose requirement ids already computed by the
    # shell (``find_bare_prose_requirement_ids`` over spec.md's raw text) --
    # ``plan_mapping`` never touches raw spec text itself (INV-4 pure/no-I/O).
    bare_prose_requirement_ids: frozenset[str] = frozenset()
    mission_type: str = "software-dev"


@dataclass(frozen=True)
class MappingOffenders:
    """PRE-write new-ref verdict buckets (undeduped, input order — shell renders them).

    Each new ref is classified by the single grammar authority
    (:func:`grammar.classify`, C-001) against the declared spec-id set:
    ``malformed`` does not parse under the grammar and is reported AS TYPED
    (never uppercased, FR-010); ``unknown_spec_id`` is well-formed but not
    declared in ``spec.md`` and is reported canonical. A ``foreign_qualified``
    ref (``<mission-slug>#<ID>``) lands in NEITHER bucket — it never blocks
    (FR-019) and is appended like any other accepted ref. Every offending ref
    lands in exactly one bucket (FR-010): the old double-listing of a
    malformed ref in the unknown bucket is retired.
    """

    malformed: tuple[str, ...]
    unknown_spec_id: tuple[str, ...]


@dataclass(frozen=True)
class MappingPlan:
    """The pure mapping decision the shell applies (write) + reports."""

    to_write: dict[str, list[str]]
    offenders: MappingOffenders
    unmapped_fr: list[str]
    # WP06 (#3396) T032: surfaced verbatim from the request under the SAME
    # field name ``finalize-tasks`` uses -- a distinct, separately-labeled
    # signal, never merged into ``unmapped_fr`` (Story 1 / FR-001 / FR-004).
    bare_prose_requirement_ids: list[str] = field(default_factory=list)
    # WP03 (requirement-id-grammar-01M3NRCA) FR-005: per-WP raw items dropped
    # by an explicit ``--replace`` overwrite (original on-disk order, raw
    # spelling) -- empty for every WP when ``req.replace`` is False. The shell
    # surfaces this ONLY on the ``--replace`` leg (``replaced_refs_removed``),
    # so the default-mode ``map_requirements_success`` byte contract never
    # moves (NFR-002).
    replaced_refs_removed: dict[str, list[str]] = field(default_factory=dict)


def _dedup_key(item: str) -> str:
    """The canonical-form dedup key for *item* (C-001); a malformed item keys itself.

    ``FR-006A`` and ``FR-006a`` share a key (both canonicalise to ``FR-006a``);
    a token the grammar cannot parse (e.g. a stray ``FR_009``) keys on its own
    raw text, so it still dedupes against an identical repeat without being
    silently folded onto an unrelated well-formed ref.
    """
    return grammar.canonical(item) or item


def _merge_refs(
    *,
    new_refs: list[str],
    existing: list[str],
    tasks_md_fallback: list[str],
    replace: bool,
) -> list[str]:
    """The per-WP merge (FR-005, append-only -- operator ruling DM 01M3NSKHE8T6TBKNFPSJ6BRD2G).

    Default (union) mode: existing items are kept, byte-identical, in their
    original order (including any pre-existing duplicate -- "never erase"
    covers an author's own duplicate too); each new ref (arriving canonical,
    T016) is appended only when its canonical form is not already present.
    The tasks.md fallback seeds the base, in its parsed order, ONLY when the
    frontmatter list is empty.

    ``--replace`` is the operator's explicit, documented recovery: it
    overwrites with just the new refs, deduplicated by canonical form, BUT
    when a new ref's canonical form matches a stored item, the STORED
    item's spelling is written (a stored ``FR-006A`` stays ``FR-006A``) --
    see :func:`_replace_preserving_spelling`. Replace never respells; it can
    only drop what the operator did not re-supply (see
    :func:`_replaced_items_removed`).

    **The one defined exception to "byte-identical."** A legacy SCALAR
    ``requirement_refs`` value (``"FR-001, FR-002"``) or a single list item
    holding a comma-joined pair (``["FR-001, FR-002"]``) is tokenised into
    separate single-ID items by the raw reader (``grammar.tokenize_refs``)
    BEFORE this function ever sees ``existing`` -- a list of single-ID
    strings is the only item form that can reach disk, so no ID is lost and
    order is preserved, but the two comma-joined tokens are no longer one
    on-disk item. Pinned by ``test_legacy_scalar_string_splits_into_single_id_items``
    / ``test_legacy_compound_list_item_splits_into_single_id_items``.
    """
    if replace:
        return _replace_preserving_spelling(existing, new_refs)
    base = list(existing) or list(tasks_md_fallback)
    merged = list(base)
    seen = {_dedup_key(item) for item in base}
    for ref in new_refs:
        key = _dedup_key(ref)
        if key not in seen:
            seen.add(key)
            merged.append(ref)
    return merged


def _replace_preserving_spelling(existing: list[str], new_refs: list[str]) -> list[str]:
    """``--replace``'s overwrite set: deduped by canonical form, stored spelling wins.

    The FIRST occurrence of each canonical key in *new_refs* decides the
    written spelling, UNLESS *existing* already carries that key -- in which
    case the stored item's own spelling is written instead (analysis B7: a
    stored ``FR-006A`` stays ``FR-006A`` even when the operator retypes it
    ``fr-006a``). The result is sorted, exactly as the pre-WP03 ``sorted(set(...))``
    replace shape.
    """
    existing_by_key: dict[str, str] = {}
    for item in existing:
        existing_by_key.setdefault(_dedup_key(item), item)
    written_by_key: dict[str, str] = {}
    for ref in new_refs:
        key = _dedup_key(ref)
        written_by_key.setdefault(key, existing_by_key.get(key, ref))
    return sorted(written_by_key.values())


def _replaced_items_removed(existing: list[str], written: list[str]) -> list[str]:
    """The raw *existing* items an explicit ``--replace`` dropped (FR-005).

    Compared by canonical form (:func:`_dedup_key`) so a written item that is
    merely the SAME ref under its stored spelling is never reported as
    "removed". Order is the original on-disk order.
    """
    written_keys = {_dedup_key(item) for item in written}
    return [item for item in existing if _dedup_key(item) not in written_keys]


def _classify_new_ref_offenders(all_new_refs: list[str], declared: frozenset[str], mission_type: str = "software-dev") -> MappingOffenders:
    """The PRE-write offender buckets, one grammar verdict per new ref (FR-010/FR-019).

    Routes every new ref through the single grammar authority
    (:func:`grammar.classify`, C-001) instead of the retired
    ``validate_ref_format``/``validate_refs`` pair: ``malformed`` keeps the
    raw, as-typed spelling (T016: refs already arrive canonicalised, so what
    reaches here unparsed is genuinely malformed); ``unknown_spec_id`` is
    reported canonical. A ``foreign_qualified`` verdict lands in neither
    bucket -- it never blocks.
    """
    malformed: list[str] = []
    unknown: list[str] = []
    for ref in all_new_refs:
        verdict = grammar.classify(ref, declared, mission_type=mission_type)
        if isinstance(verdict, grammar.Rejected):
            if verdict.reason == grammar.MALFORMED:
                malformed.append(verdict.raw)
            elif verdict.reason == grammar.UNKNOWN_SPEC_ID:
                unknown.append(verdict.raw)
    return MappingOffenders(malformed=tuple(malformed), unknown_spec_id=tuple(unknown))


def plan_mapping(req: MappingRequest) -> MappingPlan:
    """Decide the requirement mapping purely (FR-005 / FR-006 / FR-010 / FR-019).

    Computes the PRE-write offender buckets over the supplied new refs, the
    per-WP append-only merged ``to_write`` (skipped entirely in
    ``tracker_only`` mode), the ``--replace``-only ``replaced_refs_removed``,
    and the projected ``unmapped_fr`` coverage — with NO side effects (INV-4).
    The shell applies the write and runs the post-write stale gate at their
    original positions.
    """
    all_new_refs = [ref for refs in req.new_mappings.values() for ref in refs]
    offenders = _classify_new_ref_offenders(all_new_refs, req.spec_all_ids, req.mission_type)

    to_write: dict[str, list[str]] = {}
    replaced_refs_removed: dict[str, list[str]] = {}
    if req.mode != TRACKER_ONLY_MODE:
        for wp_id, new_refs in req.new_mappings.items():
            existing = req.existing_all_refs.get(wp_id, [])
            written = _merge_refs(
                new_refs=new_refs,
                existing=existing,
                tasks_md_fallback=req.tasks_md_refs.get(wp_id, []),
                replace=req.replace,
            )
            to_write[wp_id] = written
            if req.replace:
                replaced_refs_removed[wp_id] = _replaced_items_removed(existing, written)

    projected: dict[str, list[str]] = {**req.existing_all_refs, **to_write}
    coverage = compute_coverage(projected, set(req.spec_functional_ids))
    return MappingPlan(
        to_write=to_write,
        offenders=offenders,
        unmapped_fr=list(coverage["unmapped_functional"]),
        bare_prose_requirement_ids=sorted(req.bare_prose_requirement_ids),
        replaced_refs_removed=replaced_refs_removed,
    )
