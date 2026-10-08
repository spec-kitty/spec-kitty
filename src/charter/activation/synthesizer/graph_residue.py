"""Shared helper for removing stale project ``graph.yaml`` residue.

FR-007: two ``built_in_only``-writer paths used to each carry their own bare
``(pack_dir / "graph.yaml").unlink(missing_ok=True)`` expression:

* ``charter.activation.synthesizer.project_drg.apply_post_condition`` (inside its atomic
  ``write_text(tmp) → unlink(graph) → guard.replace(tmp, manifest)`` sequence),
  and
* ``specify_cli.cli.commands.charter._fresh_doctrine`` (a standalone unlink for
  the synthesizer-bypass fresh-seed path).

Both now route through :func:`unlink_stale_project_graph`. The graph filename
is reused from :mod:`charter.activation.synthesizer.project_drg` (``_GRAPH_FILENAME``) — a
third copy of the literal is deliberately avoided (it already lives in
``project_drg`` and ``write_pipeline``).

This module is import-safe as the helper home: it lives inside
``charter.activation.synthesizer`` (same package as ``project_drg``), and the consumer in
``specify_cli`` already performs a deferred ``from charter.activation.synthesizer.* import``.
It MUST NOT live under ``specify_cli`` — ``charter.activation.synthesizer`` already has a
deferred ``import specify_cli``, so a back-import would tighten toward a cycle.
"""

from __future__ import annotations

from pathlib import Path

from charter.activation.synthesizer._constants import GRAPH_FILENAME as _GRAPH_FILENAME

__all__ = ["unlink_stale_project_graph"]


def unlink_stale_project_graph(pack_dir: Path) -> None:
    """Remove a stale project ``graph.yaml`` under ``pack_dir`` if present.

    Idempotent and missing-safe: a missing ``graph.yaml`` is a no-op. This is
    the single sanctioned removal of a project graph that a ``built_in_only``
    writer disowns (FR-007).

    Args:
        pack_dir: The project pack root (``.kittify/charter-packs``)
            that may contain a residual ``graph.yaml``.
    """
    (pack_dir / _GRAPH_FILENAME).unlink(missing_ok=True)
