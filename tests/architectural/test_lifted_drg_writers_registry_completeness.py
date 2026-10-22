"""Always-on gate: every DRG mapping writer emits every declared field.

Lifted from ``tests/specify_cli/drg_writers/test_registry_completeness.py``
(mission ``doctrine-delivery-reachability``), a
``tests/specify_cli/drg_writers`` tree recorded ``out_of_matrix`` in
``.github/ci-module-registry.yml`` — no per-PR lane selects it (#4374
disposition ledger, disposition 2 — lift-invariant).

The DRG writer registry (``specify_cli.drg_writers.registry``) enumerates
every site that persists ``DRGNode``/``DRGEdge`` state, so a field added to a
model later cannot be silently dropped by a writer nobody remembered to
update. This pins the registry-completeness contract (W-1/W-1a): a
fully-populated node's declared fields, AND a genuinely novel field a writer
has never seen before, must both survive every registered mapping writer.
"""

from __future__ import annotations

import pytest

# The tests live once, in the shared home this gate and its source import
# (#5015); importing them is what makes pytest collect them in this module.
from tests.architectural._lifted_drg_writers_registry_completeness import (
    test_every_mapping_writer_emits_every_declared_node_field as test_every_mapping_writer_emits_every_declared_node_field,
)
from tests.architectural._lifted_drg_writers_registry_completeness import (
    test_every_mapping_writer_preserves_a_novel_node_field as test_every_mapping_writer_preserves_a_novel_node_field,
)

pytestmark = [pytest.mark.architectural]
