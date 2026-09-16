"""Shared seams for the charter activate/deactivate cascade render paths.

Neutral home (issue #3772) for the two seams ``activate.py`` and
``deactivate.py`` previously duplicated or cross-imported:

* :data:`KIND_FILTERED_LABEL` + :func:`render_kind_filtered_line` -- the one
  kind-filtered-node render definition, previously defined in (and imported
  back out of) ``activate.py`` as the underscore-private
  ``_render_kind_filtered_line``, a private name consumed by a sibling module.
* :func:`drg_urn_to_config_id` -- the one URN-accepting DRG-URN ->
  config-stem-ID resolution with orphan fallback, previously
  ``activate.py``'s ``(kind, id)``-shaped ``_drg_id_to_config_id`` plus two
  inline copies of the same try/except in ``deactivate.py``'s
  ``_render_cascade_deactivation``.

Both CLI command modules import from here; neither imports the other for
these seams anymore.
"""

from __future__ import annotations

from pathlib import Path

from charter.activation.kind_vocabulary import UnknownArtifactIdError, resolve_config_id
from specify_cli.cli.console import console

__all__ = ["drg_urn_to_config_id", "render_kind_filtered_line"]

#: FR-009 -- the ONE shared definition of the kind-filtered-node label,
#: consumed by :func:`render_kind_filtered_line` below and, through it, by
#: ``activate.py``'s cascade-activation and no-cascade-warning render paths
#: and ``deactivate.py``'s ``_render_cascade_deactivation`` -- never re-coined
#: at any of those call sites (Sonar S1192). Styled ``[dim]`` like the
#: existing ``Skipped (out of scope)`` line, but with distinct literal text so
#: the two remain grep-distinguishable (FR-008): a structurally
#: non-activatable kind (``template``/``asset``, C-001) must never be
#: mistaken for a scope-excluded one. Never phrased as a warning/error/
#: failure (FR-003) -- issue #3705 is a silent-drop bug, not a failure.
KIND_FILTERED_LABEL = "[dim]Not cascaded[/dim]: {kind_token}/{config_id} (kind not charter-activatable)"


def render_kind_filtered_line(kind_token: str, config_id: str) -> None:
    """Render one line for a kind-filtered (structurally non-activatable) node.

    FR-009: the single shared rendering helper -- ``activate.py``'s
    ``_render_cascade_activation``/``_render_no_cascade_warning`` and
    ``deactivate.py``'s ``_render_cascade_deactivation`` all call this same
    helper rather than each re-coining the wording (Sonar S1192). Relocated
    here from ``activate.py`` (issue #3772) so no sibling module imports an
    underscore-private name cross-module.
    """
    console.print(KIND_FILTERED_LABEL.format(kind_token=kind_token, config_id=config_id))


def drg_urn_to_config_id(
    urn: str,
    doctrine_root: Path,
    layer_roots: dict[str, Path] | None,
    org_roots: list[Path] | None = None,
) -> str:
    """Map a cascade-reported DRG URN back to its config-stem ID.

    The cascade engine works in DRG URN space (e.g. ``DIRECTIVE_001``) while
    activation lists use config-stem IDs (e.g.
    ``001-architectural-integrity-standard``). Falls back to the URN's bare ID
    when no config stem resolves (so rendering never crashes on an orphan
    node) -- the same ``resolve_config_id(...)`` call with the same
    ``(UnknownArtifactIdError, ValueError)`` fallback every cascade render
    loop previously made inline (issue #3772 consolidating the three call
    sites: ``activate.py``'s cascade loops and ``deactivate.py``'s
    ``plan.deactivate`` / kind-filtered loops).

    ``org_roots`` (T008/T009): the full declaration-ordered org-pack chain —
    see :func:`specify_cli.cli.commands.charter._layer_roots.resolve_org_root_chain`
    for why this is threaded as a separate parameter rather than widened into
    ``layer_roots``. Without it, a cascade-reported ID that only resolves
    through org pack 2..N fell back to the raw DRG ID here (pack 1 was the
    only pack ``layer_roots["org"]`` could ever carry).
    """
    try:
        resolved: str = resolve_config_id(
            urn,
            doctrine_root=doctrine_root,
            org_roots=org_roots,
            layer_roots=layer_roots,
        )
        return resolved
    except (UnknownArtifactIdError, ValueError):
        return urn.partition(":")[2]
