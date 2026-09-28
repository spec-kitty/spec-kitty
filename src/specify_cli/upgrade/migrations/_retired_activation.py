"""Shared machinery for migrations that retire an activatable doctrine id.

Extracted from ``m_3_2_6_retire_rtk_search_tooling`` (T002, behaviour
preserved -- ``tests/specify_cli/upgrade/migrations/
test_m_3_2_6_retire_rtk_search_tooling.py`` still passes unmodified against
the rebuilt migration). That migration hand-rolled the removal logic for a
single retired toolguide; ``m_4_0_0rc5_retire_single_owner_doctrine_ids``
needs the same mechanics for eight retirements across four project surfaces,
so the generic parts move here as a shared, data-driven engine rather than a
second near-copy (DIRECTIVE_044 / boy-scout precedent already established by
``_merge_driver_seeding.py``, which this module mirrors: migrations
parametrize a shared engine with their own data instead of cloning the body).

The leading underscore keeps ``auto_discover_migrations()`` (which only
imports ``m_*.py`` and ``base.py``) from ever importing this module as a
migration in its own right -- the same ``_merge_driver_seeding.py``
precedent T002 cites.

Retirement model
-----------------
A :class:`Retirement` names one activatable doctrine id being removed,
renamed, moved or re-kinded: the exact ``activated_<kind>`` key it lives
under (``kind_key``), its bare config-id stem, the catalog/reference id
prefix (e.g. ``"TACTIC"``), and an optional tuple of successor
``(activated_<kind>, stem)`` pairs to activate in its place.

Surfaces
--------
Five project files/blocks, each optional and each left untouched if the
retired stem is not present in it:

* ``.kittify/config.yaml``             -- ``kind_key`` list member.
* ``.kittify/charter/charter.yaml``    -- ``kind_key`` list member, plus a
  ``catalog`` reference block matched by id. Production ``charter.yaml``
  nests catalog blocks under ``catalog.references``; the rtk migration's own
  test fixtures use a flat top-level ``catalog:`` list. :func:`_block_list`
  resolves both shapes so this one engine serves both.
* ``.kittify/charter/charter.yaml``'s ``governance.charter.selected_<kind>``
  block -- a SEPARATE, nested surface inside the same file as the previous
  bullet (WP10-discovered gap, spec.md FR-009 amendment). This is the
  hand-authored, pre-``consolidate-charter-bundle`` activation snapshot
  ``charter.activation.sync.load_governance_config(...).charter`` reads;
  ``charter context``'s selection-block renderer
  (``charter.activation.context_renderers.selection_block``) still sources
  from it, so a migration that leaves it untouched keeps feeding retired
  ids into every agent prompt after ``charter generate`` regenerates the
  top-level surface from it. ``_selected_key`` derives the nested member
  key from ``kind_key`` (the same derivation the answers surface below
  uses); ``_Surface.successor_key_prefix`` derives each successor's nested
  key the same way, so a successor is activated under
  ``governance.charter.selected_<kind>``, never under the top-level
  ``activated_<kind>`` used by the other charter.yaml surface.
* ``.kittify/charter/references.yaml`` -- a ``references`` block matched by
  id (already a flat list in both the real and the rtk-fixture shape).
* ``.kittify/charter/interview/answers.yaml`` -- the interview's
  ``selected_<kind>`` list member (derived from ``kind_key`` by swapping the
  ``activated_`` prefix for ``selected_``), so a later ``charter generate``
  cannot reintroduce the id from a stale answer. Callers that do not carry
  this surface (the rtk migration never touched it) opt out via
  ``include_answers_surface=False``.

A successor is activated in the SAME file the retired stem was removed
from, and only in the two surfaces that carry an ``activated_<kind>`` list
(config.yaml, charter.yaml) -- never invented in ``answers.yaml`` or a
``catalog``/``references`` block (the next ``charter generate`` compiles
those). It is appended to its own ``activated_<kind>`` list only when that
list already EXISTS in that file and does not already contain the successor
stem; an absent key means "not narrowed" (see
``m_3_2_x_normalize_activation_absence``) and is never created here.

Org-pack-resolvable skip
-------------------------
An id moved to an org pack (e.g. ``packs/internal``) still resolves for a
project that loads that pack via ``.kittify/config.yaml``'s
``charter_packs.org.packs`` (or its legacy ``doctrine.org.packs`` /
``organisation_packs`` synonyms -- see
``charter.offering.drg.org_pack_config``). :func:`_still_resolves_via_org_pack`
is the cheap check: does any configured, existing org-pack root carry
``<kind_prefix>s/<stem>.<kind_prefix>.yaml``? When it does, every surface
for that retirement is left alone -- the project's activation genuinely
still resolves, so there is nothing to migrate away from.

Nothing is ever created by this module: a project missing a surface file
(or missing the key/entry within it) is left untouched, and a malformed
(unparseable, or non-mapping) YAML file is skipped rather than treated as
fatal. Every write is a round-trip (comment/quote preserving) parse-mutate-
dump, exactly as the rtk migration did before extraction.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from charter.bundle import CHARTER_YAML
from ruamel.yaml import YAML

from .base import MigrationResult

__all__ = [
    "Retirement",
    "apply_retirements",
    "detect_retirements",
]


@dataclass(frozen=True)
class Retirement:
    """One activatable doctrine id being retired from consumer projects.

    ``kind_key`` is the literal ``activated_<kind>`` key the stem lives
    under (e.g. ``"activated_tactics"``) -- match-by-kind-key (not by bare
    stem alone) is what keeps a directive of the same slug
    (``activated_directives``) untouched while the tactic of that slug is
    removed. ``reference_prefix`` is the catalog/reference id prefix (e.g.
    ``"TACTIC"``); ``reference_id`` composes the two into the full
    ``PREFIX:stem`` form used by ``catalog``/``references`` blocks.
    ``successors`` is a tuple of ``(activated_<kind>, stem)`` pairs to
    activate in the retired id's place; empty when there is no successor.
    """

    kind_key: str
    stem: str
    reference_prefix: str
    successors: tuple[tuple[str, str], ...] = ()

    @property
    def reference_id(self) -> str:
        return f"{self.reference_prefix}:{self.stem}"


@dataclass(frozen=True)
class _Surface:
    """One project file this engine may touch for a given retirement.

    ``member_key`` names a list-of-strings key to check the stem's
    membership in (``None`` when this surface carries no such list, e.g.
    ``references.yaml``). It may be a dotted path (e.g.
    ``"governance.charter.selected_tactics"``) to reach a list nested inside
    the file, resolved by :func:`_resolve_member_list`; a plain undotted key
    behaves exactly as before. ``block_key`` names a list-of-block-mappings
    key matched by ``id`` (``None`` when this surface carries no block
    list). ``successor_eligible`` gates whether a successful member removal
    on this surface also attempts successor activation on the same file.
    ``successor_key_prefix`` is ``None`` for a surface whose successor list
    lives under the retirement's own ``kind_key`` vocabulary (the top-level
    ``activated_<kind>`` surfaces); when set, a successor's
    ``(activated_<kind>, stem)`` pair is instead activated under
    ``f"{successor_key_prefix}{_selected_key(activated_<kind>)}"`` -- the
    nested ``governance.charter.selected_<kind>`` block uses
    ``"governance.charter."``, mirroring the ``selected_<kind>`` naming the
    answers surface already uses.
    """

    relative_path: Path
    member_key: str | None
    block_key: str | None
    successor_eligible: bool
    successor_key_prefix: str | None = None


_CONFIG_RELATIVE_PATH = Path(".kittify") / "config.yaml"
_REFERENCES_RELATIVE_PATH = Path(".kittify") / "charter" / "references.yaml"
_ANSWERS_RELATIVE_PATH = Path(".kittify") / "charter" / "interview" / "answers.yaml"

_ANSWERS_KEY_PREFIX = "activated_"
_ANSWERS_KEY_REPLACEMENT = "selected_"
_GOVERNANCE_CHARTER_PATH_PREFIX = "governance.charter."


def _selected_key(kind_key: str) -> str:
    """Derive the ``selected_<kind>`` key from an ``activated_<kind>`` key."""
    return _ANSWERS_KEY_REPLACEMENT + kind_key.removeprefix(_ANSWERS_KEY_PREFIX)


def _surfaces_for(retirement: Retirement, *, include_answers_surface: bool) -> tuple[_Surface, ...]:
    governance_member_key = f"{_GOVERNANCE_CHARTER_PATH_PREFIX}{_selected_key(retirement.kind_key)}"
    surfaces: tuple[_Surface, ...] = (
        _Surface(_CONFIG_RELATIVE_PATH, retirement.kind_key, None, True),
        _Surface(CHARTER_YAML, retirement.kind_key, "catalog", True),
        _Surface(CHARTER_YAML, governance_member_key, None, True, successor_key_prefix=_GOVERNANCE_CHARTER_PATH_PREFIX),
        _Surface(_REFERENCES_RELATIVE_PATH, None, "references", False),
    )
    if include_answers_surface:
        surfaces += (_Surface(_ANSWERS_RELATIVE_PATH, _selected_key(retirement.kind_key), None, False),)
    return surfaces


# --------------------------------------------------------------------------- #
# YAML I/O (round-trip, comment/quote preserving)
# --------------------------------------------------------------------------- #


def _round_trip_yaml() -> YAML:
    yaml = YAML()
    yaml.preserve_quotes = True
    return yaml


def _load_mapping(path: Path) -> dict[str, Any] | None:
    """Round-trip load *path* as a mapping; ``None`` when absent/unreadable/not a mapping."""
    if not path.exists():
        return None
    try:
        data = _round_trip_yaml().load(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 -- a malformed project file is skipped, never fatal
        return None
    return data if isinstance(data, dict) else None


def _write(path: Path, data: dict[str, Any]) -> None:
    """Write *data* back to *path* in round-trip form (the file already exists)."""
    with path.open("w", encoding="utf-8") as handle:
        _round_trip_yaml().dump(data, handle)


# --------------------------------------------------------------------------- #
# Shape primitives: plain member lists and id-keyed block lists
# --------------------------------------------------------------------------- #


def _resolve_member_list(data: dict[str, Any], key: str) -> list[Any] | None:
    """Resolve *key* (plain, or a dotted path) to the list it names, if any.

    A plain key (no ``.``) behaves exactly as ``data.get(key)`` always did.
    A dotted key (``"governance.charter.selected_tactics"``) walks the
    intermediate mappings, returning ``None`` -- never creating anything --
    the moment any segment is missing or not itself a mapping.
    """
    node: Any = data
    for part in key.split("."):
        if not isinstance(node, dict):
            return None
        node = node.get(part)
    return node if isinstance(node, list) else None


def _member_present(data: dict[str, Any], key: str, stem: str) -> bool:
    values = _resolve_member_list(data, key)
    return values is not None and stem in values


def _remove_member(data: dict[str, Any], key: str, stem: str) -> bool:
    """Remove every occurrence of *stem* from the list named by *key*; True when changed."""
    values = _resolve_member_list(data, key)
    if values is None:
        return False
    removed = False
    while stem in values:
        values.remove(stem)
        removed = True
    return removed


def _block_list(data: dict[str, Any], key: str) -> list[Any] | None:
    """Resolve *key* to the block list it names, in either shape it may take.

    ``data[key]`` is either already the flat block list (the rtk migration's
    own fixtures, and ``references.yaml`` in production), or a mapping whose
    ``references`` entry is the block list (production ``charter.yaml``'s
    ``catalog: {mission, template_set, languages, references: [...]}``).
    ``None`` when neither shape matches.
    """
    value = data.get(key)
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        nested = value.get("references")
        if isinstance(nested, list):
            return nested
    return None


def _block_present(data: dict[str, Any], key: str, block_id: str) -> bool:
    blocks = _block_list(data, key)
    if blocks is None:
        return False
    return any(isinstance(block, dict) and block.get("id") == block_id for block in blocks)


def _remove_block(data: dict[str, Any], key: str, block_id: str) -> bool:
    blocks = _block_list(data, key)
    if blocks is None:
        return False
    stale_indexes = [index for index, block in enumerate(blocks) if isinstance(block, dict) and block.get("id") == block_id]
    for index in reversed(stale_indexes):
        del blocks[index]
    return bool(stale_indexes)


def _append_successor_stems(
    data: dict[str, Any],
    successors: tuple[tuple[str, str], ...],
    *,
    key_prefix: str | None,
) -> list[tuple[str, str]]:
    """Append each successor stem to its own list when present and lacking it.

    *key_prefix* is ``None`` for the top-level ``activated_<kind>`` surfaces
    (the successor's own ``target_key`` names the list directly); when set
    (the nested ``governance.charter.selected_<kind>`` surface), the
    successor's ``activated_<kind>`` key is remapped to
    ``f"{key_prefix}{_selected_key(target_key)}"`` first, so the successor
    is activated in the SAME nested vocabulary the retired stem was removed
    from, never in the top-level one.
    """
    added: list[tuple[str, str]] = []
    for target_key, target_stem in successors:
        resolved_key = f"{key_prefix}{_selected_key(target_key)}" if key_prefix else target_key
        values = _resolve_member_list(data, resolved_key)
        if values is not None and target_stem not in values:
            values.append(target_stem)
            added.append((resolved_key, target_stem))
    return added


# --------------------------------------------------------------------------- #
# Org-pack-resolvable skip
# --------------------------------------------------------------------------- #


def _still_resolves_via_org_pack(project_path: Path, retirement: Retirement) -> bool:
    """True when a configured, existing org-pack root still carries this id.

    Cheap existence check, not a full DRG resolution: an id moved to
    ``packs/internal`` (or any other configured org pack) still resolves for
    a project that loads that pack, so nothing here should be removed.
    """
    from charter.drg import resolve_existing_org_roots  # noqa: PLC0415 -- public door (doctrine census); lazy so migration-registry discovery does not import charter.offering (C-002)

    kind_dir = f"{retirement.reference_prefix.lower()}s"
    filename = f"{retirement.stem}.{retirement.reference_prefix.lower()}.yaml"
    return any((root / kind_dir / filename).is_file() for root in resolve_existing_org_roots(project_path))


# --------------------------------------------------------------------------- #
# Per-surface processing
# --------------------------------------------------------------------------- #


def _surface_needs_change(data: dict[str, Any], retirement: Retirement, surface: _Surface) -> bool:
    if surface.member_key is not None and _member_present(data, surface.member_key, retirement.stem):
        return True
    return surface.block_key is not None and _block_present(data, surface.block_key, retirement.reference_id)


def _process_surface(data: dict[str, Any], retirement: Retirement, surface: _Surface) -> tuple[list[str], list[tuple[str, str]]]:
    """Mutate *data* in place per *surface*; return (touched keys, successors added)."""
    touched: list[str] = []
    member_removed = False
    if surface.member_key is not None and _remove_member(data, surface.member_key, retirement.stem):
        touched.append(surface.member_key)
        member_removed = True
    if surface.block_key is not None and _remove_block(data, surface.block_key, retirement.reference_id):
        touched.append(surface.block_key)
    successors_added: list[tuple[str, str]] = []
    if member_removed and surface.successor_eligible:
        successors_added = _append_successor_stems(data, retirement.successors, key_prefix=surface.successor_key_prefix)
    return touched, successors_added


def _describe(stem: str, rel_path: str, keys: list[str], verb: str) -> list[str]:
    return [f"{verb} {stem} from {rel_path} ({key})" for key in keys]


def _describe_successors(rel_path: str, successors: list[tuple[str, str]], verb: str) -> list[str]:
    return [f"{verb} successor {stem} in {rel_path} ({key})" for key, stem in successors]


def _apply_one_retirement(
    project_path: Path,
    retirement: Retirement,
    *,
    include_answers_surface: bool,
    dry_run: bool,
    errors: list[str],
) -> list[str]:
    changes: list[str] = []
    for surface in _surfaces_for(retirement, include_answers_surface=include_answers_surface):
        path = project_path / surface.relative_path
        data = _load_mapping(path)
        if data is None:
            continue
        touched, successors_added = _process_surface(data, retirement, surface)
        if not touched and not successors_added:
            continue
        rel_path = surface.relative_path.as_posix()
        if dry_run:
            changes.extend(_describe(retirement.stem, rel_path, touched, "Would remove"))
            changes.extend(_describe_successors(rel_path, successors_added, "Would activate"))
            continue
        try:
            _write(path, data)
        except OSError as exc:
            errors.append(f"Failed writing {rel_path}: {exc}")
            continue
        changes.extend(_describe(retirement.stem, rel_path, touched, "Removed"))
        changes.extend(_describe_successors(rel_path, successors_added, "Activated"))
    return changes


# --------------------------------------------------------------------------- #
# Public engine
# --------------------------------------------------------------------------- #


def detect_retirements(
    project_path: Path,
    retirements: tuple[Retirement, ...],
    *,
    include_answers_surface: bool,
) -> bool:
    """True when at least one retirement has a removable presence in *project_path*.

    Skips a retirement entirely (across every surface) when it still
    resolves via a configured org pack -- see module docstring.
    """
    for retirement in retirements:
        if _still_resolves_via_org_pack(project_path, retirement):
            continue
        for surface in _surfaces_for(retirement, include_answers_surface=include_answers_surface):
            data = _load_mapping(project_path / surface.relative_path)
            if data is not None and _surface_needs_change(data, retirement, surface):
                return True
    return False


def apply_retirements(
    project_path: Path,
    retirements: tuple[Retirement, ...],
    *,
    include_answers_surface: bool,
    dry_run: bool = False,
) -> MigrationResult:
    """Remove every retired id's presence from *project_path*'s surfaces.

    A retirement that still resolves via a configured org pack is skipped
    entirely (no surface is touched for it). ``changes_made`` is empty (not
    a synthesized "nothing to do" message) when nothing changed -- each
    calling migration composes its own no-op message from that, preserving
    its own existing wording (e.g. the rtk migration's
    ``"{stem} already absent; nothing to remove"``).
    """
    changes: list[str] = []
    errors: list[str] = []
    for retirement in retirements:
        if _still_resolves_via_org_pack(project_path, retirement):
            continue
        changes.extend(
            _apply_one_retirement(
                project_path,
                retirement,
                include_answers_surface=include_answers_surface,
                dry_run=dry_run,
                errors=errors,
            )
        )
    return MigrationResult(success=not errors, changes_made=changes, errors=errors)
