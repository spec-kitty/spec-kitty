"""MissionTypeRepository — loads and indexes MissionType YAML files."""

from __future__ import annotations

import functools
import threading
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol, cast

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

if TYPE_CHECKING:
    # Typeshed-only names describing functools.cache's forwarded introspection
    # attributes (PR-CONTRACT-001) -- see _LayeredMissionTypesResolver below.
    from functools import _CacheInfo, _CacheParameters

# MissionCacheLockError: imported for completeness/future-proofing
# (plan.md Section 6c) -- both fix sites' lock/cache-error raise paths
# share this ONE exception type, defined at the primary fix site
# (mission_step_repository.py). This design adds no lock-timeout/
# corrupted-cache/retry-exhaustion path (CL-008), so THIS site has no
# local raise call site for it today; unused import is intentional.
from .mission_step_repository import (
    MissionCacheLockError,  # noqa: F401
    MissionStepRepository,
    _lock_for,
    _PackContextLike,
)
from .models import MissionType
from .step_projection import project_action_sequence

__all__ = [
    "MissionTypeRepository",
    "ORG_MISSION_TYPES_SUBDIR",
    "PROJECT_MISSION_TYPES_RELATIVE",
    "PROJECT_MISSION_TYPES_RELATIVE_TO_KITTYFY_ROOT",
    "builtin_mission_type_id_set",
    "builtin_mission_type_ids",
    "resolve_layered_mission_types",
    "scan_mission_types_dir",
]
# `resolve_layered_mission_types` (FR-001, below) was deliberately withheld
# from `__all__` by WP03 (mission up-mission-type-seam-01KZY1JB) until a real
# `src/` caller existed -- see that WP's own commit history and
# `kitty-specs/up-mission-type-seam-01KZY1JB/tracer-tooling-friction.md` for
# why. WP04 (FR-002) now calls it from
# `charter.activation.mission_type_profiles._resolve_action_slot`
# (`from charter.offering.missions.mission_type_repository import
# resolve_layered_mission_types`), so
# `tests/architectural/test_no_dead_symbols.py`'s symbol-level dead-code gate
# has a live caller to find and the entry is restored here. The three
# path-layout constants above are public for the same reason (#3427): both
# charter.activation consumers below import them, so the dead-symbol gate
# finds a live caller for each.


class MissionTypeRepository:
    """Loads and indexes MissionType YAML files from a directory.

    Scans *mission_types_dir* for ``*.yaml`` files, parses each via the
    :class:`~charter.offering.missions.models.MissionType` Pydantic model, validates
    that each file's ``id`` field matches the filename stem, then indexes the
    results for O(1) lookup.

    The repository is eager: all files are loaded at construction time.
    Any parse or validation error raises immediately so callers never receive
    a partially populated repository.

    Parameters
    ----------
    mission_types_dir:
        Path to the directory that contains ``*.yaml`` MissionType files.
    """

    def __init__(self, mission_types_dir: Path) -> None:
        self._dir = mission_types_dir
        self._index: dict[str, MissionType] = self._load(mission_types_dir)

    # ------------------------------------------------------------------
    # Class-level constructor helpers
    # ------------------------------------------------------------------

    @classmethod
    @functools.cache
    def default(cls) -> MissionTypeRepository:
        """Return a repository loaded from the doctrine-bundled mission_types directory.

        Memoized (NFR-007, WP02): loading a mission type now also resolves
        that type's builtin ``step.yaml`` set to compute the
        ``action_sequence``/``template_set`` projection (see
        :func:`_inject_projected_fields`), so an un-memoized ``default()``
        would re-walk and re-parse the entire ``mission-steps/`` tree on
        every hot-path call. Reuses the exact ``@functools.cache`` idiom
        applied to :func:`builtin_mission_type_ids` below.

        Test seam: call ``MissionTypeRepository.default.cache_clear()``
        (auto-provided by ``functools.cache``, reachable through the
        classmethod's bound-method attribute proxy) to force a rebuild --
        e.g. after pointing at a synthetic ``mission_types/`` fixture tree.
        Production never mutates the bundled ``mission_types/``/
        ``mission-steps/`` trees mid-process, so the cache is safe there;
        tests must never write into the real bundled trees to exercise this
        seam (mirrors the ``builtin_mission_type_ids`` cache-vs-test-seam
        contract, C-010).

        Mission ``doctrine-consumer-surface-missions-extraction-01KZ6G6H``
        (FR-005) relocated ``mission_types/`` from
        ``src/charter/offering/missions/mission_types`` to
        ``packs/built-in/missions/mission_types``. This now delegates to the
        one promoted missions-root authority
        (:meth:`~charter.offering.missions.repository.MissionTemplateRepository.default_missions_root`,
        FR-004) instead of its own ``importlib.resources.files("charter.offering")``
        literal -- the retired literal would silently resolve to the now
        data-less ``src/doctrine`` package tree post-relocation, and its bare
        ``Path(__file__).parent / "mission_types"`` fallback would resolve to
        a directory that no longer exists at all.
        """
        from .repository import MissionTemplateRepository  # noqa: PLC0415

        return cls(MissionTemplateRepository.default_missions_root() / "mission_types")

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def load_all(self) -> list[MissionType]:
        """Return all loaded :class:`MissionType` objects, sorted by ``id``.

        Returns
        -------
        list[MissionType]
            Sorted by ``id`` (ascending, lexicographic).
        """
        return sorted(self._index.values(), key=lambda m: m.id)

    def get(self, mission_type_id: str) -> MissionType | None:
        """Look up a MissionType by its id.

        Parameters
        ----------
        mission_type_id:
            The ``id`` field value (e.g. ``"software-dev"``).

        Returns
        -------
        MissionType | None
            The matching :class:`MissionType`, or ``None`` if not found.
        """
        return self._index.get(mission_type_id)

    def ids(self) -> list[str]:
        """Return a sorted list of all registered mission-type IDs.

        Returns
        -------
        list[str]
            Sorted ascending, lexicographic.
        """
        return sorted(self._index.keys())

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _load(directory: Path) -> dict[str, MissionType]:
        """Scan *directory* for ``*.yaml`` files and return an id-keyed dict.

        Raises
        ------
        ValueError
            If a file's parsed ``id`` does not match the filename stem.
        pydantic.ValidationError
            If any YAML file fails :class:`MissionType` validation.
        """
        _yaml = YAML(typ="safe")
        index: dict[str, MissionType] = {}
        if not directory.is_dir():
            return index

        for yaml_file in sorted(directory.glob("*.yaml")):
            raw: Any = _yaml.load(yaml_file.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise ValueError(
                    f"Expected a YAML mapping in {yaml_file}; got {type(raw).__name__}"
                )
            payload = _inject_projected_fields(raw, mission_type_id=yaml_file.stem)
            mission_type = MissionType.model_validate(payload)
            expected_id = yaml_file.stem
            if mission_type.id != expected_id:
                raise ValueError(
                    f"MissionType id {mission_type.id!r} in {yaml_file.name} "
                    f"does not match filename stem {expected_id!r}. "
                    "Rename the file or correct the id field."
                )
            index[mission_type.id] = mission_type

        return index

    # ------------------------------------------------------------------
    # Layered-lookup test seam (FR-001, mission up-mission-type-seam-01KZY1JB WP03)
    # ------------------------------------------------------------------

    @staticmethod
    def cache_clear() -> None:
        """Test seam (NFR-001/FR-001): clear the layered lookup's cache.

        Mirrors :meth:`MissionStepRepository.cache_clear`
        (``mission_step_repository.py``) -- clears **only** the new,
        SEPARATE, module-level :func:`resolve_layered_mission_types` cache
        introduced by mission ``up-mission-type-seam-01KZY1JB`` (WP03).

        Does **NOT** touch :meth:`default`'s own ``functools.cache`` -- that
        is a different, `cls`-keyed cache, cleared separately via
        ``MissionTypeRepository.default.cache_clear()``. The two caches are
        deliberately independent (CL-001, ADR
        ``docs/adr/3.x/2026-08-13-1-mission-type-roster-layering-seam.md``):
        threading a project-dependent value through the `cls`-keyed
        ``default()`` cache would poison it for every later project resolved
        in the same process, so the layered lookup lives in its own,
        separately-cleared cache instead.
        """
        resolve_layered_mission_types.cache_clear()


# ----------------------------------------------------------------------------
# WP02 projection injection (S-B transitional seam)
# ----------------------------------------------------------------------------


def _inject_projected_fields(
    raw: dict[str, Any],
    *,
    mission_type_id: str,
    pack_context: _PackContextLike | None = None,
) -> dict[str, Any]:
    """Overlay the WP02 ``action_sequence`` projection onto *raw* YAML fields.

    Resolves *mission_type_id*'s step set through
    :meth:`MissionStepRepository.resolve_all_for_mission_type`, forwarding
    *pack_context* unchanged, and derives ``action_sequence`` via
    :func:`~charter.offering.missions.step_projection.project_action_sequence`.

    ``pack_context`` (mission ``mission-types-empty-action-sequence-01M0RMCA``
    WP01, #3701): this parameter defaults to ``None``, which resolves the
    **builtin-only** step set -- exactly this function's pre-WP01 behavior,
    still what :meth:`MissionTypeRepository._load`'s zero-argument call site
    (line 165, deliberately untouched, FR-005/C-001) receives. Callers that
    hold a real ``pack_context`` -- :func:`_load_layered_mission_type_file`,
    threaded down from :func:`resolve_layered_mission_types` -- now forward
    it here, so org/project overrides reach this projection instead of being
    silently dropped. Before WP01, this parameter did not exist and the call
    below hardcoded ``pack_context=None`` unconditionally, so every
    org/project mission type relying on step-file projection (no explicit
    ``action_sequence:`` authored in its own ``<type>.yaml``) always
    projected an empty sequence, regardless of what its callers held (issue
    #3701).

    **Transitional fallback (``action_sequence`` only, C-007-retained):**
    ``action_sequence`` is still YAML-authored for every built-in mission
    type. Until a given type's steps carry ``sequence_index`` /
    ``in_action_sequence`` data, the projection over that type's steps is
    legitimately empty. Injecting an empty value in that case would violate
    ``MissionType``'s non-empty invariant. So an **empty projection falls
    back to the raw YAML-authored value** rather than overwriting it; only
    a *non-empty* projection is injected in its place.

    ``template_set`` (S-C cutover, mission-step-creatability-01KXQA6R WP01,
    FR-001): the persisted field and its overlay are retired entirely --
    this function no longer reads or writes a ``template_set`` key at all.
    ``payload = dict(raw)`` below preserves any (incorrect) raw-authored
    ``template_set:`` key verbatim; ``MissionType``'s ``extra="forbid"``
    then rejects it during validation (SC-002 loud-fail), rather than this
    seam silently honoring or dropping it. Consumers now source the
    template mapping from the step authority directly at the consumption
    boundary (:func:`charter.activation.mission_type_profiles._resolve_template_set_slot`),
    not from this repository-load-time injection.
    """
    steps = list(
        MissionStepRepository.default()
        .resolve_all_for_mission_type(mission_type_id, pack_context=pack_context)
        .values()
    )

    projected_sequence = project_action_sequence(steps)

    payload = dict(raw)
    payload["action_sequence"] = projected_sequence or raw.get("action_sequence")
    return payload


# ----------------------------------------------------------------------------
# Module-level canonical accessors (single source of truth, IC-1a / #2669)
# ----------------------------------------------------------------------------


@functools.cache
def builtin_mission_type_ids() -> tuple[str, ...]:
    """The built-in mission-type ids, derived from the doctrine mission_types/*.yaml source.

    Single canonical authority for "which mission types ship". Sorted (lexicographic).
    Cached: one filesystem scan per process (NFR-002). Raises transitively if the
    repository loud-fails on an id/stem mismatch or invalid schema.

    Test seam (C-010): tests inject a synthetic roster by monkeypatching
    :meth:`MissionTypeRepository.default` (or the root it resolves to), then calling
    ``builtin_mission_type_ids.cache_clear()`` (auto-provided by ``functools.cache``)
    before asserting. Production never adds/removes built-in type YAMLs mid-process,
    so the cache is safe there; tests must never write into the real bundled
    ``mission_types/`` directory to exercise this seam.
    """
    return tuple(MissionTypeRepository.default().ids())


def builtin_mission_type_id_set() -> frozenset[str]:
    """Frozenset projection of :func:`builtin_mission_type_ids` for membership/default consumers."""
    return frozenset(builtin_mission_type_ids())


# ----------------------------------------------------------------------------
# Layered lookup (FR-001, mission up-mission-type-seam-01KZY1JB WP03)
# ----------------------------------------------------------------------------
#
# A new, SEPARATE, module-level, pack-aware factory -- sibling to, never a
# replacement for, MissionTypeRepository.default() above (which stays
# built-in-only, `cls`-keyed, untouched). Threading a project-dependent value
# through that `cls`-keyed cache would poison it for every later project
# resolved in the same process -- the rejected Option (a) recorded in
# docs/adr/3.x/2026-08-13-1-mission-type-roster-layering-seam.md. This
# factory is keyed directly on (mission_types_dirs, pack_context) instead,
# mirroring the sibling module's own already-live pattern:
# mission_step_repository._resolve_all_for_mission_type_cached.

# Thread-local accessor (WP01, mission concurrent-template-config-race-4589-
# 01M35M6B) -- mirrors mission_step_repository._get_yaml exactly, for the
# identical reason: a single module-level YAML(typ="safe") instance shared
# across threads is not thread-safe (.load() mutates cross-call parser
# state). A SEPARATE thread-local pair from the sibling module's -- each
# site gets its own, never shared across the two modules.
class _LayeredYamlLocal(threading.local):
    """Thread-local holder for this thread's own ``YAML(typ="safe")`` instance.

    A genuine ``threading.local`` subclass (mirrors ``kernel.locks._ReentrancyState``,
    src/kernel/locks.py:647, and the sibling ``mission_step_repository._YamlLocal``)
    rather than a bare ``threading.local()`` instance, so the ``instance`` attribute
    has a declared type and ``mypy --strict`` does not infer ``Any`` on every access
    (PR-CONTRACT-001). ``threading.local`` calls ``__init__`` once per thread on that
    thread's first attribute access, so this keeps the exact same "build once per
    thread, lazily on first use" behavior as the previous ``try/except
    AttributeError`` construction.
    """

    def __init__(self) -> None:
        self.instance = YAML(typ="safe")


_layered_yaml_local = _LayeredYamlLocal()


def _get_layered_yaml() -> YAML:
    """Return this thread's own ``YAML(typ="safe")`` instance, building it once."""
    return _layered_yaml_local.instance

#: Org-pack layout (CL-005, ADR 2026-08-13-1): flat, non-recursive
#: ``<pack_root>/mission_types/*.yaml`` -- mirrors the sibling
#: ``mission-steps/`` convention at the org/project pack tier.
#:
#: Single path-layout authority for the CL-005 mission-type roster (#3427):
#: ``charter.activation.mission_type_profiles.resolve_action_sequence_layer``
#: and ``charter.activation.pack_manager._resolve_layer_candidate`` import
#: these constants instead of re-spelling the layout inline, so moving a
#: layer directory is a one-place edit. Publicized from their former
#: leading-underscore spellings for exactly that purpose.
ORG_MISSION_TYPES_SUBDIR = "mission_types"

#: Project-layer layout (CL-005): flat, non-recursive
#: ``.kittify/missions/mission_types/*.yaml``, repo-root-relative. Deliberately
#: distinct from MissionStepRepository's own project-override location
#: (``.kittify/overrides/mission-steps/``) -- CL-005 is its own decision
#: record, not an import-by-analogy of the sibling's path.
PROJECT_MISSION_TYPES_RELATIVE: tuple[str, ...] = (".kittify", "missions", "mission_types")

#: Project-layer layout relative to the ``.kittify`` project root -- the tail
#: of :data:`PROJECT_MISSION_TYPES_RELATIVE` past its leading ``.kittify``
#: segment. Derived, never edited independently: consumers whose supplied base
#: is already the ``.kittify`` root (``charter.activation.pack_manager``, whose
#: ``layer_roots["project"]`` value is ``repo_root / ".kittify"`` per
#: ``specify_cli.cli.commands.charter._layer_roots.resolve_layer_roots``) join
#: this instead of slicing the repo-root-relative tuple at their own call
#: site (#3427) -- the base-point reconciliation lives here, beside the
#: authority it derives from.
PROJECT_MISSION_TYPES_RELATIVE_TO_KITTYFY_ROOT: tuple[str, ...] = PROJECT_MISSION_TYPES_RELATIVE[1:]


def _load_layered_mission_type_file(
    yaml_file: Path, *, pack_context: _PackContextLike | None = None
) -> MissionType:
    """Parse and validate one mission-type YAML file for the layered lookup.

    Mirrors :meth:`MissionTypeRepository._load`'s per-file logic (the same
    :func:`_inject_projected_fields` overlay, the same id/filename-stem
    match check) but wraps a ``ruamel.yaml`` parse failure with *yaml_file*'s
    own path named in the raised error's message.

    ``_load``'s own call (``_yaml.load(yaml_file.read_text(...))``) parses a
    bare ``str``, not a named stream, so a ``ruamel.yaml.YAMLError`` raised
    there carries no file identity of its own -- naively reusing that exact
    call shape unmodified for org/project scanning would satisfy "fail
    loudly" but not spec.md's "naming the offending file" half of the Edge
    Cases requirement (CL-006/NFR-002). This wrap is that fix (T005/T006,
    red-first: see the malformed-YAML tests in
    ``tests/doctrine/missions/test_mission_type_repository.py`` and this
    WP's commit history for the pre-fix RED evidence).

    ``pack_context`` (mission ``mission-types-empty-action-sequence-01M0RMCA``
    WP01, #3701): forwarded unchanged to :func:`_inject_projected_fields` so
    its step-file projection sees the same layered ``pack_context`` this
    file's own scan is running under, instead of the previously-hardcoded
    ``pack_context=None``. Threaded down from :func:`scan_mission_types_dir`,
    itself threaded from :func:`resolve_layered_mission_types`.

    Raises
    ------
    ValueError
        Wrapping a ``YAMLError`` with *yaml_file*'s path named (malformed
        YAML), or raised directly for a non-mapping document or an
        id/filename-stem mismatch -- mirroring ``_load``'s own ``ValueError``
        shape for those two cases.
    pydantic.ValidationError
        The parsed document fails :class:`MissionType` validation.
    """
    try:
        raw: Any = _get_layered_yaml().load(yaml_file.read_text(encoding="utf-8"))
    except YAMLError as exc:
        raise ValueError(f"Malformed YAML in mission-type file {yaml_file}: {exc}") from exc
    if not isinstance(raw, dict):
        raise ValueError(f"Expected a YAML mapping in {yaml_file}; got {type(raw).__name__}")
    payload = _inject_projected_fields(
        raw, mission_type_id=yaml_file.stem, pack_context=pack_context
    )
    mission_type = MissionType.model_validate(payload)
    expected_id = yaml_file.stem
    if mission_type.id != expected_id:
        raise ValueError(
            f"MissionType id {mission_type.id!r} in {yaml_file.name} "
            f"does not match filename stem {expected_id!r}. "
            "Rename the file or correct the id field."
        )
    return mission_type


def scan_mission_types_dir(
    directory: Path, *, pack_context: _PackContextLike | None = None
) -> list[MissionType]:
    """Return every :class:`MissionType` in *directory*, scanned flat/non-recursive (FR-005).

    Public (PR-CONTRACT-002, pre-merge squad, mission
    up-mission-type-seam-01KZY1JB): the single-directory scan primitive
    :func:`resolve_layered_mission_types` itself uses, one layer at a time.
    ``charter.activation.pack_manager.CharterPackManager.list_available_detailed``'s
    ``kind is None`` (mission-type) branch also calls this directly (one
    call per ``(layer, scan_dir)`` pair, mirroring its own per-layer entry
    shape) so that the pre-activation availability catalog loud-fails on the
    identical malformed/unreadable input :func:`resolve_layered_mission_types`
    already loud-fails on post-activation, instead of re-deriving a second,
    tolerant copy of this scan (DIRECTIVE_044). That call site (FR-008,
    ``charter/pack_manager.py:865``) is deliberately left untouched -- it
    keeps calling this with no *pack_context*, which remains valid via the
    new keyword default below, and is safe because it only reads
    ``.id``/``.layer``, never ``.action_sequence``.

    ``pack_context`` (mission ``mission-types-empty-action-sequence-01M0RMCA``
    WP01, #3701): forwarded unchanged to :func:`_load_layered_mission_type_file`
    for every YAML file this scan finds, so each file's own
    ``_inject_projected_fields`` step-file projection sees the same layered
    ``pack_context`` :func:`resolve_layered_mission_types` is resolving
    under. Previously this scan never forwarded *any* ``pack_context`` to
    the files it loaded, regardless of the layer being scanned -- the actual
    root cause of #3701, one level deeper than the top-level
    :func:`resolve_layered_mission_types` entry point (which already
    accepted ``pack_context`` correctly).

    Two distinct non-error-shaped outcomes, and one that must raise:

    - *directory* not existing (e.g. no project-layer pack activated, or a
      caller-supplied built-in-equivalent root that has no local override) is
      "no contributions from this layer" -- not an error, not a crash
      (spec.md Edge Cases). Returns ``[]``.
    - *directory* existing **but unreadable** (bad permissions, a
      misconfigured container/NFS mount) is a **failure, not an empty
      result** (NFR-002/CL-006) -- raises :class:`ValueError` naming the
      offending directory. This is deliberately distinguished from "does not
      exist": ``directory.is_dir()`` alone cannot tell the two apart, since
      ``stat`` only needs search permission on the *parent* directories, not
      on *directory* itself, so it succeeds even on a directory with mode
      ``000``. Only actually listing *directory*'s contents requires
      read+execute on *directory* itself, so that listing (not ``is_dir()``)
      is where this case is detected and raised.
    """
    if not directory.is_dir():
        return []
    try:
        # Path.iterdir() raises PermissionError directly on an unreadable
        # directory. Path.glob("*.yaml") does NOT: it silently swallows
        # PermissionError during scandir and returns an empty iterator,
        # which would collapse "exists but unreadable" into the same `[]`
        # as "does not exist" -- exactly the forbidden collapse this WP
        # exists to close. iterdir() is used here instead of glob() for
        # that reason; the "*.yaml" filter below is applied explicitly.
        entries = list(directory.iterdir())
    except OSError as exc:
        raise ValueError(
            f"mission-type directory exists but cannot be read: {directory}: {exc}"
        ) from exc
    yaml_files = sorted(entry for entry in entries if entry.name.endswith(".yaml"))
    return [
        _load_layered_mission_type_file(f, pack_context=pack_context) for f in yaml_files
    ]


def _resolve_layered_mission_types_uncached(
    mission_types_dirs: tuple[Path, ...],
    pack_context: _PackContextLike | None,
) -> dict[str, MissionType]:
    """Perform the actual layered directory walk (the per-key population unit).

    Mirrors :meth:`MissionStepRepository._resolve_all_for_mission_type_uncached`'s
    own uncached/cached split at the primary fix site (WP01). This is the
    unit OBL-2's redundant-population-count obligation counts invocations of
    (``tests/core/test_mission_creation_identity.py``).

    Layer precedence, full per-compound-key replacement (never a field-level
    merge -- ``MissionTypeRepository`` does not inherit
    ``BaseDoctrineRepository``, spec.md Edge Cases): **project > org
    (earliest pack_root wins) > built-in-equivalent** -- matching
    ``MissionStepRepository``'s own documented precedence.

    Parameters
    ----------
    mission_types_dirs:
        Directories scanned as the lowest-precedence ("built-in-equivalent")
        layer, e.g. ``(MissionTemplateRepository.default_missions_root() /
        "mission_types",)``. Caller-supplied (mirrors
        ``_resolve_all_for_mission_type_cached``'s own ``builtin_root``
        parameter) rather than resolved internally, so a test can point this
        at a synthetic scratch directory without touching the real bundled
        tree.
    pack_context:
        Structural ``_PackContextLike`` object (or ``None``) supplying org
        pack roots (``pack_context.pack_roots``, org layer at
        ``<pack_root>/mission_types/*.yaml`` per CL-005) and the project
        root (``pack_context.repo_root``, project layer at
        ``.kittify/missions/mission_types/*.yaml`` per CL-005). ``None``
        resolves only the built-in-equivalent layer -- mirrors
        ``MissionStepRepository.resolve_all_for_mission_type``'s own
        ``pack_context=None`` contract. Any ``pack_context.pack_roots``
        entry whose value equals a *mission_types_dirs* entry's parent is
        skipped in the org-layer scan (it is already handled by the
        built-in-equivalent layer above) -- mirrors
        ``MissionStepRepository``'s own built-in-pack-root skip.

    Returns
    -------
    dict[str, MissionType]
        ``id -> MissionType``, fully layered. Never ``None``, never a
        placeholder -- an empty dict is a legitimate result (no mission
        types found in any layer) and is distinct from a raise (a malformed
        file in a scanned layer always raises, never silently shrinks the
        roster, NFR-002).

    Raises
    ------
    ValueError
        A YAML file in any scanned layer fails the non-mapping or
        id/filename-stem check.
    pydantic.ValidationError
        A YAML file fails :class:`MissionType` schema validation.
    """
    index: dict[str, MissionType] = {}

    for base_dir in mission_types_dirs:
        for mission_type in scan_mission_types_dir(base_dir, pack_context=pack_context):
            index[mission_type.id] = mission_type

    if pack_context is not None:
        protected_pack_roots = {base_dir.parent for base_dir in mission_types_dirs}
        org_index: dict[str, MissionType] = {}
        for pack_root in pack_context.pack_roots:
            if pack_root in protected_pack_roots:
                continue  # already handled by the built-in-equivalent layer above
            org_dir = pack_root / ORG_MISSION_TYPES_SUBDIR
            for mission_type in scan_mission_types_dir(org_dir, pack_context=pack_context):
                org_index.setdefault(mission_type.id, mission_type)  # earliest pack_root wins
        index.update(org_index)

        project_dir = pack_context.repo_root.joinpath(*PROJECT_MISSION_TYPES_RELATIVE)
        for mission_type in scan_mission_types_dir(project_dir, pack_context=pack_context):
            index[mission_type.id] = mission_type  # project always wins

    return index


@functools.cache
def _resolve_layered_mission_types_cached(
    mission_types_dirs: tuple[Path, ...],
    pack_context: _PackContextLike | None,
) -> dict[str, MissionType]:
    """Module-level, cross-instance ``functools.cache`` lookup (the cache-miss path).

    Private: never call ``.cache_clear()``/``.cache_info()`` on this function
    directly from outside this module -- use the public
    :func:`resolve_layered_mission_types` wrapper's forwarded attributes
    (below), which is what every external caller already does by name.

    FR-001: a new, SEPARATE, module-level ``functools.cache`` lookup --
    sibling to, never a replacement for, :meth:`MissionTypeRepository.default`
    (which stays built-in-only, untouched). See the module-level comment
    above this function for the rejected project-dependent-``default()``
    alternative (CL-001, ADR 2026-08-13-1).

    Cache safety boundary (PR-CONTRACT-003, pre-merge squad, mission
    up-mission-type-seam-01KZY1JB) -- READ BEFORE embedding this in a
    long-lived process
    -----------------------------------------------------------------
    Unlike :meth:`MissionTypeRepository.default`'s cache (safe because
    production never mutates the bundled, read-only built-in tree
    mid-process), this cache ALSO indexes org and project mission-type
    directories -- content that IS user-editable on disk during a process's
    lifetime. The cache key is ``(mission_types_dirs, pack_context)``, so it
    correctly avoids cross-PROJECT poisoning (NFR-001) -- but it does
    **not** detect an on-disk edit to an already-cached org/project
    ``mission_types/*.yaml`` file made *after* the first resolution for that
    same key: the second call with the identical key returns the FIRST
    (now-stale) result. ``tests/doctrine/missions/test_mission_type_repository.py``'s
    ``TestLayeredMissionTypesCacheKeyAndClear.test_same_key_is_a_cache_hit``
    pins this staleness directly (it mutates an org-layer YAML file after a
    first resolution and asserts the second resolution still returns the
    stale first result) -- it is a documented, accepted property of this
    cache, not a bug.

    This is safe for the **one-process-per-CLI-invocation** model every
    current ``src/`` caller uses (each ``spec-kitty`` invocation is a fresh
    process; the cache lives and dies with it, so no on-disk edit can ever
    occur "during" a single resolution). It is **not** safe for a longer-
    lived host (a persistent test-fixture process, a future daemon, or an
    ``orchestrator-api`` consumer) that resolves mission types across
    multiple on-disk states without restarting: such a host MUST call
    :meth:`MissionTypeRepository.cache_clear` (which clears this cache
    specifically, without touching :meth:`MissionTypeRepository.default`'s
    separate built-in-only cache) at every point it wants a fresh read --
    e.g. immediately before each resolution, or in response to a detected
    filesystem change. No current ``src/`` call site does this (`grep`
    confirms ``resolve_layered_mission_types.cache_clear()`` /
    ``MissionTypeRepository.cache_clear()`` are invoked only from test code
    today) because none needs to under the one-process-per-invocation
    model; this paragraph is the explicit contract a future long-lived host
    must honor, not an implementation left for later in this mission's
    scope. Freshness-based invalidation (e.g. keying on a directory mtime)
    was considered and rejected for this fix round as exceeding a
    pre-merge-fix's scope -- it would need its own design (what counts as
    "fresh", how deep to stat, cross-platform mtime granularity) and its own
    red-first regression suite, not a documentation-round addendum.
    """
    return _resolve_layered_mission_types_uncached(mission_types_dirs, pack_context)


class _LayeredMissionTypesResolver(Protocol):
    """Structural type for the public ``resolve_layered_mission_types`` name.

    ``functools.cache``'s own ``.cache_clear``/``.cache_info``/``.cache_parameters``
    attributes are forwarded onto the plain ``resolve_layered_mission_types``
    function by dynamic attribute assignment (plan.md Section 6b; see the
    comment above the assignments below for why ``functools.update_wrapper``
    cannot close this gap). A bare function's mypy-inferred type has no such
    attributes, so ``--strict`` rejects both the assignment site and every
    downstream call site (e.g. :meth:`MissionTypeRepository.cache_clear`)
    without this Protocol. This is the smallest typed surface that describes
    the wrapper's actual runtime shape -- its call signature plus the three
    forwarded cache-introspection attributes -- so both sides type-check with
    zero ``# type: ignore`` (PR-CONTRACT-001).
    """

    def __call__(
        self,
        mission_types_dirs: tuple[Path, ...],
        pack_context: _PackContextLike | None,
    ) -> dict[str, MissionType]: ...

    cache_clear: Callable[[], None]
    cache_info: Callable[[], _CacheInfo]
    cache_parameters: Callable[[], _CacheParameters]


def _resolve_layered_mission_types(
    mission_types_dirs: tuple[Path, ...],
    pack_context: _PackContextLike | None,
) -> dict[str, MissionType]:
    """Resolve the layered mission-type roster for (*mission_types_dirs*, *pack_context*).

    **Single-flight lock (6b, WP01):** this public entry point wraps the
    ENTIRE cached call in this key's :func:`_lock_for` lock -- not just the
    cache-miss body -- so a losing thread's call becomes a
    :func:`_resolve_layered_mission_types_cached` HIT (the winner's result)
    rather than a second, independent, redundant walk. Mirrors
    :meth:`MissionStepRepository.resolve_all_for_mission_type`'s own
    identical shape at the primary fix site, sharing the SAME ``_lock_for``
    key-space (imported from that module) so the two sites never diverge on
    lock semantics.

    This function is the public, ``__all__``-exported, stable name every
    caller (including :func:`charter.activation.mission_type_profiles._resolve_action_slot`)
    keeps using unchanged; the actual ``functools.cache``-decorated
    implementation lives at the private
    :func:`_resolve_layered_mission_types_cached` name above (split out so
    the lock can wrap the *whole* cached call, per the round-4 plan design
    -- a lock only *inside* the cached body would let two threads each
    independently run the walk, which does not close the redundant-
    population window at all; see plan.md Section 6b).

    See :func:`_resolve_layered_mission_types_uncached` for the full
    parameter/return/raise contract this wrapper forwards unchanged.
    """
    key = (mission_types_dirs, pack_context)
    with _lock_for(key):
        return _resolve_layered_mission_types_cached(mission_types_dirs, pack_context)


# `functools.cache`'s own `.cache_clear`/`.cache_info`/`.cache_parameters`
# attributes live on the DECORATED callable -- `_resolve_layered_mission_
# types_cached` above, not the public `resolve_layered_mission_types`
# wrapper. 14 existing call sites depend on the public name still carrying
# all three (12 direct `.cache_clear()` calls across three test files,
# `MissionTypeRepository.cache_clear()`'s own body, and one `.cache_info()`
# call inside `tests/charter/test_charter_import_time_io.py`'s in-subprocess
# import-time-I/O spy). `functools.update_wrapper` would NOT close this gap
# -- it copies `__wrapped__`/`__doc__`/`__name__`/`__module__`/`__dict__`,
# never these three cache-specific attributes -- so three explicit
# assignments are used instead.
#
# `resolve_layered_mission_types` is bound here, at module scope, to the
# `_LayeredMissionTypesResolver`-typed `cast()` of `_resolve_layered_mission_
# types` (PR-CONTRACT-001) -- the SAME function object, just typed so the
# three attribute assignments below and every downstream `.cache_clear()`/
# `.cache_info()`/`.cache_parameters()` call site (including
# `MissionTypeRepository.cache_clear()` above) type-check under `--strict`.
# mypy does not allow rebinding a `def`-introduced name to a wider type in
# place, so the implementation keeps its original name
# (`_resolve_layered_mission_types`) and this is the one, single place the
# public name is defined -- call behavior and the docstring above are
# unchanged, but `__name__`/`__qualname__` are NOT: a plain `def`'s
# `__name__`/`__qualname__` reflect the name it was defined under
# (`_resolve_layered_mission_types`), and `cast()` is purely a static-typing
# annotation -- it does not touch either attribute at runtime. The two
# assignments below correct both, on the underlying function object, before
# the cast, restoring the `resolve_layered_mission_types` identity this
# public name had on `main` (PR-FRESH1-001).
_resolve_layered_mission_types.__name__ = "resolve_layered_mission_types"
_resolve_layered_mission_types.__qualname__ = "resolve_layered_mission_types"
resolve_layered_mission_types: _LayeredMissionTypesResolver = cast(
    _LayeredMissionTypesResolver, _resolve_layered_mission_types
)
resolve_layered_mission_types.cache_clear = _resolve_layered_mission_types_cached.cache_clear
resolve_layered_mission_types.cache_info = _resolve_layered_mission_types_cached.cache_info
resolve_layered_mission_types.cache_parameters = _resolve_layered_mission_types_cached.cache_parameters
