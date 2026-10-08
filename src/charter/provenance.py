"""Charter facade for the portable provenance path normalizer.

This module is the charter-layer proxy for runtime callers that normalize a
committed provenance ``source_path`` (contracts/provenance-and-channel.md
C-PRV-1..3/6). The runtime -> charter -> charter.offering boundary (ADR 2026-03-27-1,
re-affirmed by mission ``doctrine-public-api-surface-01KZPDSR``) requires
runtime modules under ``src/specify_cli/`` to reach charter offering artifacts only
through charter facades.

``charter.offering.provenance`` is consumed from charter exactly like
``charter.offering.pack_paths`` (see :mod:`charter.pack_paths`) -- both normalizer
functions are re-exported here (from ``charter.offering.provenance``, not a wrapper).

This file is a **pure re-export** module -- no behaviour, no wrappers, no type
aliases. Object identity is preserved (``charter.provenance.to_portable_source_path
is charter.offering.provenance.to_portable_source_path``).
"""

from charter.offering.provenance import is_built_in_pack_path, to_portable_source_path

__all__ = [
    "is_built_in_pack_path",
    "to_portable_source_path",
]
