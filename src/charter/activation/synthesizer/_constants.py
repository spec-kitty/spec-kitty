"""Leaf constants for the charter synthesizer package.

Single source of truth for literals shared across synthesizer modules. This
module MUST stay a leaf — it carries ZERO imports — so any synthesizer module
(``project_drg``, ``write_pipeline``) and downstream consumers (e.g.
``specify_cli.charter_runtime.freshness.computer``) can import it without
risking an import cycle.
"""

from __future__ import annotations

#: Canonical filename of the project-layer DRG overlay written under
#: ``.kittify/charter-packs/`` and staged under ``<staging>/charter-packs/``.
GRAPH_FILENAME = "graph.yaml"

__all__ = ["GRAPH_FILENAME"]
