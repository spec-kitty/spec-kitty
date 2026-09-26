"""MissionStepRepository — compound-key layered resolution (FR-012).

Resolution algorithm (highest precedence wins):
    1. Project layer: ``.kittify/overrides/mission-steps/{mission_type_id}/{step_id}/step.yaml``
    2. Org layer:     for each pack root in ``pack_context.pack_roots``,
                      check ``{root}/mission-steps/{mission_type_id}/{step_id}/step.yaml``
    3. Built-in layer: ``{builtin_steps_root}/{mission_type_id}/{step_id}/step.yaml``

Compound-key isolation guarantee
---------------------------------
The shadowing key is the **full compound key** ``(mission_type_id, step_id)``.
A shadow for ``("software-dev", "review")`` only overrides the *review* step of
the *software-dev* mission type.  It has **no effect** on
``("documentation", "review")`` because those two compound keys are distinct.

The :class:`StepKey` frozen dataclass enforces this at the cache layer: Python
``==`` and ``hash()`` compare *both* fields, so two ``StepKey`` instances with
the same ``step_id`` but different ``mission_type_id`` values are always
treated as separate entries.

Layer precedence in full
------------------------
project > org (earliest pack_root wins) > built-in

If ``pack_context`` is ``None``, only the built-in layer is queried.
If ``pack_context.repo_root`` is available, the project layer is also queried.
"""

from __future__ import annotations

import functools
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from ruamel.yaml import YAML

from .models import MissionStep


class _PackContextLike(Protocol):
    """Narrow structural protocol for the pack-context object.

    Replaces the ``TYPE_CHECKING`` import of ``charter.activation.pack_context.PackContext``
    (C-004: doctrine must not import from charter).  Only the two attributes
    accessed by this module are declared; the protocol is intentionally
    minimal so that any conforming object — including test fakes — satisfies
    it without needing to depend on the charter package.

    ``__hash__`` is declared explicitly (NFR-003, mission-step-creatability-01KXQA6R
    WP01) so this protocol is a structural subtype of ``collections.abc.Hashable``
    for ``mypy --strict`` -- ``resolve_all_for_mission_type``'s shared cache
    keys on ``pack_context`` directly. The real ``charter.activation.pack_context.PackContext``
    (and every test double used against this module) is a frozen
    ``@dataclass``, which synthesizes ``__hash__`` automatically.
    """

    pack_roots: tuple[Path, ...]
    repo_root: Path

    def __hash__(self) -> int: ...

__all__ = [
    "StepKey",
    "MissionStepRepository",
]

# ---------------------------------------------------------------------------
# YAML loader (thread-local accessor -- WP01, mission
# concurrent-template-config-race-4589-01M35M6B)
#
# A single module-level YAML(typ="safe") instance is NOT thread-safe: its
# .load() mutates cross-call reader/scanner/parser/composer state
# (self.reader.stream, self.tags, ...) with no synchronization. Two threads
# racing a cache miss on `_resolve_all_for_mission_type_cached` (below) could
# corrupt each other's in-flight parse on the shared instance -- confirmed by
# this mission's research.md and the red-first regression tests this fix
# turns green (tests/core/test_mission_creation_identity.py, OBL-1).
#
# Fix: hand each THREAD its own private YAML(typ="safe") instance, built
# once per thread and reused by that thread only. This removes the shared
# mutable object entirely -- there is nothing left to race on, so no lock is
# needed for this half of the fix at all.
# ---------------------------------------------------------------------------

class _YamlLocal(threading.local):
    """Thread-local holder for this thread's own ``YAML(typ="safe")`` instance.

    A genuine ``threading.local`` subclass (mirrors ``kernel.locks._ReentrancyState``,
    src/kernel/locks.py:647) rather than a bare ``threading.local()`` instance, so
    the ``instance`` attribute has a declared type and ``mypy --strict`` does not
    infer ``Any`` on every access (PR-CONTRACT-001). ``threading.local`` calls
    ``__init__`` once per thread on that thread's first attribute access, so this
    keeps the exact same "build once per thread, lazily on first use" behavior as
    the previous ``try/except AttributeError`` construction.
    """

    def __init__(self) -> None:
        self.instance = YAML(typ="safe")


_yaml_local = _YamlLocal()


def _get_yaml() -> YAML:
    """Return this thread's own ``YAML(typ="safe")`` instance, building it once."""
    return _yaml_local.instance


# ---------------------------------------------------------------------------
# Single-flight per-key lock (6b) -- closes the redundant-population /
# cache-poisoning window that 6a alone does not address: functools.cache's
# cache-miss path never serializes concurrent execution of the wrapped body,
# so two threads racing the SAME key could each independently run the full
# filesystem walk. Owned here (the primary fix site); the second fix site
# (mission_type_repository.py) imports this same helper so both sites share
# ONE lock-key-space implementation, never two.
# ---------------------------------------------------------------------------


class MissionCacheLockError(ValueError):
    """Raised by lock/cache-population code in this package on an unrecoverable
    population failure.

    Neither fix site's lock/cache-population code ever converts a failure into
    a degraded (``None``/empty/partial) result -- CL-006's raise-never-degrade
    contract. This mission's design (plan.md Section 6c) adds no lock-timeout,
    corrupted-cache, or retry-exhaustion path, so nothing in THIS mission's own
    diff raises it yet; it exists so a future bounded-wait/retry addition at
    either fix site has one shared, typed failure to raise instead of
    improvising a second exception class.
    """


_locks_guard = threading.Lock()
_locks: dict[tuple[Any, ...], threading.Lock] = {}


def _lock_for(key: tuple[Any, ...]) -> threading.Lock:
    """Return the single-flight lock for *key*, creating it on first use.

    The returned lock is never torn down or removed by :meth:`MissionStepRepository.cache_clear`
    (or the sibling :meth:`MissionTypeRepository.cache_clear`) -- a leftover
    ``threading.Lock`` for a key no longer in the data cache is harmless, and
    reusing the same ``Lock`` object across a ``cache_clear()`` boundary is
    safe (an unheld ``Lock`` has no memory of what it used to guard).
    """
    with _locks_guard:
        lock = _locks.get(key)
        if lock is None:
            lock = threading.Lock()
            _locks[key] = lock
        return lock


_STEP_FILENAME = "step.yaml"

# ---------------------------------------------------------------------------
# Public value objects
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StepKey:
    """Cache key for a compound ``(mission_type_id, step_id)`` pair.

    Both fields participate in equality and hashing.  This guarantees that
    ``StepKey("software-dev", "review") != StepKey("documentation", "review")``,
    which is the foundation of the compound-key isolation guarantee.
    """

    mission_type_id: str
    step_id: str


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _load_step_yaml(step_file: Path) -> MissionStep | None:
    """Parse *step_file* into a :class:`~charter.offering.missions.models.MissionStep`.

    Returns ``None`` when the file does not exist, is empty, or cannot be
    parsed.  Any extra keys in the YAML (e.g. ``display_name``, ``step_type``,
    ``guidance``, ``delegates_to``) are passed through as-is; ``MissionStep``
    is configured with ``extra="forbid"`` so we strip unknown keys before
    validation.

    The mapping between step.yaml field names and MissionStep field names:

    step.yaml field         → MissionStep field
    ─────────────────────────────────────────────
    id                      → id
    display_name            → display_name  (human-readable label; also accessible as .title)
    step_type               → step_type     (executor discriminant)
    prompt_template         → prompt_template
    agent_profile           → agent-profile (alias)
    depends_on              → depends_on
    sequence_index          → sequence_index          (S-B, WP01)
    in_action_sequence      → in_action_sequence       (S-B, WP01)
    recommended_model_tier  → recommended_model_tier   (S-B, WP01; advisory offer, WP08 consumer)
    template                → template                 (S-B, WP01; MissionStepTemplateRef)
    (guidance)              → stripped (not in MissionStep)
    (delegates_to)          → stripped (not in MissionStep)

    ``MissionStep`` is ``extra="forbid"`` — any field absent from this
    mapping is **silently stripped** before validation rather than raising.
    Every new ``MissionStep`` field MUST be added here or it vanishes on
    load with no error (see :mod:`tests.doctrine.missions.test_step_schema`
    for the round-trip regression guard).
    """
    if not step_file.exists():
        return None
    try:
        raw: Any = _get_yaml().load(step_file.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None
    if not isinstance(raw, dict):
        return None

    # Map step.yaml fields → MissionStep fields and strip unknown keys.
    _STEP_YAML_TO_MODEL: dict[str, str] = {
        "id": "id",
        "display_name": "display_name",
        "step_type": "step_type",
        "prompt_template": "prompt_template",
        "agent_profile": "agent-profile",  # alias
        "depends_on": "depends_on",
        "sequence_index": "sequence_index",
        "in_action_sequence": "in_action_sequence",
        "recommended_model_tier": "recommended_model_tier",
        "template": "template",
    }
    mapped: dict[str, Any] = {}
    for src_key, dst_key in _STEP_YAML_TO_MODEL.items():
        if src_key in raw:
            mapped[dst_key] = raw[src_key]

    try:
        return MissionStep.model_validate(mapped)
    except Exception:  # noqa: BLE001
        return None


def _add_step_ids_from_dir(step_ids: set[str], mission_type_dir: Path) -> None:
    """Add step ids from ``mission_type_dir`` when ``step.yaml`` exists."""
    if not mission_type_dir.is_dir():
        return
    for entry in mission_type_dir.iterdir():
        if entry.is_dir() and (entry / _STEP_FILENAME).exists():
            step_ids.add(entry.name)


def _project_mission_type_dir(
    pack_context: _PackContextLike, mission_type_id: str,
) -> Path:
    """Return the project override directory for a mission type."""
    return (
        pack_context.repo_root
        / ".kittify"
        / "overrides"
        / "mission-steps"
        / mission_type_id
    )


# ---------------------------------------------------------------------------
# Repository
# ---------------------------------------------------------------------------


class MissionStepRepository:
    """Resolves MissionStep definitions via built-in → org → project layering.

    Shadowing key: compound ``(mission_type_id, step_id)``.

    A ``software-dev/review`` shadow does **NOT** affect
    ``documentation/review``.  See module docstring for the full resolution
    algorithm and compound-key isolation guarantee.

    Parameters
    ----------
    builtin_steps_root:
        Directory that contains the built-in step definitions, laid out as
        ``{mission_type_id}/{step_id}/step.yaml`` sub-paths.

        Defaults to the ``mission-steps/`` directory co-located with this
        module when constructed via :meth:`default`.
    """

    def __init__(self, builtin_steps_root: Path) -> None:
        self._builtin_root: Path = builtin_steps_root

    # ------------------------------------------------------------------
    # Class-level constructor helpers
    # ------------------------------------------------------------------

    @classmethod
    def default(cls) -> MissionStepRepository:
        """Return a repository loaded from the doctrine-bundled mission-steps directory.

        Mission ``doctrine-consumer-surface-missions-extraction-01KZ6G6H``
        (FR-005) relocated ``mission-steps/`` from
        ``src/charter/offering/missions/mission-steps`` to
        ``packs/built-in/missions/mission-steps``. Delegates to the one
        promoted missions-root authority
        (:meth:`~charter.offering.missions.repository.MissionTemplateRepository.default_missions_root`,
        FR-004) instead of the retired ``Path(__file__).parent``-relative
        literal, which would resolve to a directory that no longer exists at
        all post-relocation.
        """
        from .repository import MissionTemplateRepository  # noqa: PLC0415

        return cls(MissionTemplateRepository.default_missions_root() / "mission-steps")

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def resolve(
        self,
        mission_type_id: str,
        step_id: str,
        pack_context: _PackContextLike | None = None,
    ) -> MissionStep | None:
        """Return the highest-precedence MissionStep for the given compound key.

        Layer order (highest wins): project → org → built-in.

        Parameters
        ----------
        mission_type_id:
            The mission type identifier (e.g. ``"software-dev"``).
        step_id:
            The step identifier (e.g. ``"review"``).
        pack_context:
            Optional :class:`~charter.activation.pack_context.PackContext` providing org
            pack roots and the repository root for project-layer overrides.
            When ``None``, only the built-in layer is consulted.

        Returns
        -------
        MissionStep | None
            The resolved step, or ``None`` if not found in any layer.
        """
        # ── Layer 1: project ──────────────────────────────────────────────
        if pack_context is not None:
            project_step = self._resolve_project_layer(
                mission_type_id, step_id, pack_context
            )
            if project_step is not None:
                return project_step

        # ── Layer 2: org ──────────────────────────────────────────────────
        if pack_context is not None:
            org_step = self._resolve_org_layer(mission_type_id, step_id, pack_context)
            if org_step is not None:
                return org_step

        # ── Layer 3: built-in ─────────────────────────────────────────────
        return self._resolve_builtin_layer(mission_type_id, step_id)

    def resolve_all_for_mission_type(
        self,
        mission_type_id: str,
        pack_context: _PackContextLike | None = None,
    ) -> dict[str, MissionStep]:
        """Return all steps for a mission type, with shadowing applied.

        Scans the built-in layer for available ``step_id`` values, then
        applies org and project shadows via :meth:`resolve`.

        **Shared cache (NFR-003):** the underlying filesystem walk is
        memoised in a **module-level** cache keyed by
        ``(builtin_steps_root, mission_type_id, pack_context)`` -- shared
        across every :class:`MissionStepRepository` instance and call site,
        not scoped to ``self`` or to a single consumer. This is deliberate:
        after the S-C cutover (mission-step-creatability-01KXQA6R WP01)
        both the retained ``action_sequence`` overlay
        (``mission_type_repository._inject_projected_fields``) and the
        projected ``template_set`` slot
        (``charter.activation.mission_type_profiles._resolve_template_set_slot``)
        resolve steps for the same ``(mission_type, pack_context)`` per
        resolution; without a shared cache that would be two filesystem
        walks instead of one. Cleared via :meth:`cache_clear` (test seam).

        Parameters
        ----------
        mission_type_id:
            The mission type identifier (e.g. ``"software-dev"``).
        pack_context:
            Optional pack context for org/project layer resolution.

        Returns
        -------
        dict[str, MissionStep]
            Mapping of ``step_id → MissionStep`` with shadowing applied.
            Only step IDs that exist in the built-in layer (or in org/project
            overrides for the same mission type) are returned.

        **Single-flight lock (6b, WP01):** the entire cached call is made
        under this key's :func:`_lock_for` lock -- not just the cache-miss
        body -- so a losing thread's call becomes a ``functools.cache`` HIT
        (the winner's result, read from the now-populated cache dict) rather
        than a second, independent, redundant walk. See :func:`_lock_for`'s
        own docstring for why ``cache_clear()`` needs no new awareness of
        this lock.
        """
        key = (self._builtin_root, mission_type_id, pack_context)
        with _lock_for(key):
            return _resolve_all_for_mission_type_cached(
                self._builtin_root, mission_type_id, pack_context
            )

    @staticmethod
    def cache_clear() -> None:
        """Test seam (NFR-003): clear the shared ``resolve_all_for_mission_type`` cache.

        Production never mutates the bundled ``mission-steps/`` tree
        mid-process, so the cache is safe there; tests that write into a
        synthetic tree and expect a subsequent call to observe the change
        must call this first (mirrors the ``MissionTypeRepository.default``
        cache-vs-test-seam contract, C-010).
        """
        _resolve_all_for_mission_type_cached.cache_clear()

    def _resolve_all_for_mission_type_uncached(
        self,
        mission_type_id: str,
        pack_context: _PackContextLike | None,
    ) -> dict[str, MissionStep]:
        """Perform the actual layered filesystem walk (the cache-miss path)."""
        result: dict[str, MissionStep] = {}

        # Collect step_ids from all layers.
        step_ids: set[str] = set()

        # Built-in layer
        _add_step_ids_from_dir(step_ids, self._builtin_root / mission_type_id)

        # Org layer (collect any extra step_ids present in org packs)
        if pack_context is not None:
            step_ids.update(self._collect_org_step_ids(mission_type_id, pack_context))

        # Project layer (collect any extra step_ids present in project overrides)
        if pack_context is not None:
            _add_step_ids_from_dir(
                step_ids, _project_mission_type_dir(pack_context, mission_type_id),
            )

        # Resolve each step_id through the full layer stack.
        for step_id in step_ids:
            step = self.resolve(mission_type_id, step_id, pack_context)
            if step is not None:
                result[step_id] = step

        return result

    # ------------------------------------------------------------------
    # Private layer helpers
    # ------------------------------------------------------------------

    def _collect_org_step_ids(
        self, mission_type_id: str, pack_context: _PackContextLike
    ) -> set[str]:
        """Collect step_ids discoverable in org packs for *mission_type_id*.

        Iterates over ``pack_context.pack_roots``, skipping the built-in root
        (``self._builtin_root.parent``) which is handled by the built-in layer.
        """
        step_ids: set[str] = set()
        builtin_pack_root = self._builtin_root.parent
        for pack_root in pack_context.pack_roots:
            if pack_root == builtin_pack_root:
                continue
            org_mt_dir = pack_root / "mission-steps" / mission_type_id
            _add_step_ids_from_dir(step_ids, org_mt_dir)
        return step_ids

    def _resolve_builtin_layer(
        self, mission_type_id: str, step_id: str
    ) -> MissionStep | None:
        """Attempt to load ``{builtin_steps_root}/{mission_type_id}/{step_id}/step.yaml``."""
        step_file = self._builtin_root / mission_type_id / step_id / _STEP_FILENAME
        return _load_step_yaml(step_file)

    def _resolve_org_layer(
        self,
        mission_type_id: str,
        step_id: str,
        pack_context: _PackContextLike,
    ) -> MissionStep | None:
        """Iterate over ``pack_context.pack_roots`` in order.

        The first org-layer file found (earliest in ``pack_roots`` order)
        wins over the built-in layer.

        The built-in root (``self._builtin_root.parent``) is skipped when it
        appears in ``pack_roots`` — it is already handled by
        :meth:`_resolve_builtin_layer` and must not be re-scanned here.

        Org pack layout convention:
            ``{pack_root}/mission-steps/{mission_type_id}/{step_id}/step.yaml``
        """
        builtin_pack_root = self._builtin_root.parent
        for pack_root in pack_context.pack_roots:
            if pack_root == builtin_pack_root:
                continue
            step_file = (
                pack_root / "mission-steps" / mission_type_id / step_id / _STEP_FILENAME
            )
            step = _load_step_yaml(step_file)
            if step is not None:
                return step
        return None

    def _resolve_project_layer(
        self,
        mission_type_id: str,
        step_id: str,
        pack_context: _PackContextLike,
    ) -> MissionStep | None:
        """Check ``.kittify/overrides/mission-steps/{mission_type_id}/{step_id}/step.yaml``.

        Project-layer shadow wins over both org and built-in layers.
        """
        step_file = _project_mission_type_dir(
            pack_context, mission_type_id,
        ) / step_id / _STEP_FILENAME
        return _load_step_yaml(step_file)


# ---------------------------------------------------------------------------
# Shared cache (NFR-003, mission-step-creatability-01KXQA6R WP01)
# ---------------------------------------------------------------------------


@functools.cache
def _resolve_all_for_mission_type_cached(
    builtin_root: Path,
    mission_type_id: str,
    pack_context: _PackContextLike | None,
) -> dict[str, MissionStep]:
    """Module-level, cross-instance cache for ``resolve_all_for_mission_type``.

    Keyed by ``(builtin_root, mission_type_id, pack_context)`` -- **not**
    keyed on any :class:`MissionStepRepository` instance, so it stays
    shared even though ``MissionStepRepository.default()`` itself is not
    memoised (only ``MissionTypeRepository.default()`` singletons the
    *repository object*; this cache is what actually avoids re-walking
    ``mission-steps/`` on repeat resolutions, per NFR-003). ``pack_context``
    is either ``None`` or a hashable frozen dataclass (real
    ``charter.activation.pack_context.PackContext``, or a test double satisfying the
    same shape), so it is safe to use directly as part of the cache key.

    Cleared via :meth:`MissionStepRepository.cache_clear` (test seam) --
    never call ``.cache_clear()`` on this private function directly from
    outside this module.
    """
    return MissionStepRepository(
        builtin_root
    )._resolve_all_for_mission_type_uncached(mission_type_id, pack_context)
