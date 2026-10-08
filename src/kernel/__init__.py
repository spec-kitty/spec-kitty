"""Kernel — zero-dependency shared utilities and primitive types.

This package contains primitives shared by ``specify_cli`` and ``charter``
(including the ``charter.offering`` package).  It has **no imports from any
of those packages**, keeping the dependency direction clean:

    kernel  <-  charter
    kernel  <-  specify_cli

Modules
-------
atomic
    Atomic file-write utility (write-to-temp-then-rename).
clock
    The single door to wall-clock time: the injectable ``Clock`` protocol
    (``SystemClock``/``FrozenClock``/``DEFAULT_CLOCK``), the producer family
    (``now_utc_iso``, ``now_utc_stamp``, ``now_utc_compact_stamp``,
    ``now_utc_seconds``, ``now_utc``, ``now_epoch``), parse/format helpers
    (``parse_iso``, ``parse_stamp``, ``format_stamp``, ``from_epoch``), and
    minimal datetime type re-exports. Distinct from any Lamport logical
    clock. See ``kitty-specs/kernel-clock-single-door``.
glossary_types
    Glossary primitive value types: ``Strictness``, ``ExtractedTerm``,
    ``SemanticConflict``, ``ScopeRef``, ``GlossaryScope``, and related
    supporting types. Canonical definitions; consumed as re-exports by
    ``glossary`` and ``charter.offering.shared``.
paths
    Path resolution utilities: ``get_kittify_home()``, the ``PACKS_ROOT``-aware
    built-in-pack-root primitive ``get_built_in_pack_root()``, and the
    single-door ``get_package_asset_root()`` that resolves
    ``<built-in-pack-root>/missions`` through it (FR-005, DR-1). These are the
    canonical implementations; ``specify_cli.runtime.home.get_package_asset_root``
    is a thin delegate to this authority, not a second resolver. The
    ``BUILT_IN_PACK_SIBLING_PATTERN`` / ``MISSION_ASSETS_SIBLING_PATTERN``
    shape constants are exported here so downstream layers (e.g.
    ``charter.offering.pack_paths``) reuse one owned pattern instead of forking it.
glossary_runner
    Plugin registry for the glossary runner. Defines
    ``GlossaryRunnerProtocol``, ``register()``, ``get_runner()``, and
    ``clear_registry()`` (test-only). Nobody registers eagerly: the consumer
    ``charter.offering.missions.glossary_hook`` lazily self-bootstraps the
    registry on first use (``get_runner()`` → ``None`` →
    ``import_module("glossary.attachment")`` →
    ``register(GlossaryAwarePrimitiveRunner)`` → retry) and degrades only when
    ``glossary.attachment`` is unimportable; ``charter.offering`` calls ``get_runner()``
    without importing ``specify_cli``.
"""

from kernel.paths import (
    BUILT_IN_PACK_SIBLING_PATTERN,
    MISSION_ASSETS_SIBLING_PATTERN,
    get_built_in_pack_root,
)

__all__: list[str] = [
    "BUILT_IN_PACK_SIBLING_PATTERN",
    "MISSION_ASSETS_SIBLING_PATTERN",
    "get_built_in_pack_root",
]

