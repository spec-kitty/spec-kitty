"""Always-on freshness gate: README.md's Governance layer section stays accurate.

Lifted from ``tests/specify_cli/docs/test_readme_governance.py`` (WP03 /
FR-005), a ``tests/specify_cli/docs`` tree recorded ``out_of_matrix`` in
``.github/ci-module-registry.yml`` — no per-PR lane selects it (#4374
disposition ledger, disposition 2 — lift-invariant).
"""

from __future__ import annotations

import pytest

# The tests live once, in the shared home this gate and its source import
# (#5015); importing them is what makes pytest collect them in this module.
from tests.architectural._lifted_specify_cli_docs_readme_governance import test_readme_has_governance_layer_section as test_readme_has_governance_layer_section
from tests.architectural._lifted_specify_cli_docs_readme_governance import (
    test_governance_section_links_to_trail_model as test_governance_section_links_to_trail_model,
)
from tests.architectural._lifted_specify_cli_docs_readme_governance import (
    test_governance_section_links_to_host_surface_parity as test_governance_section_links_to_host_surface_parity,
)
from tests.architectural._lifted_specify_cli_docs_readme_governance import (
    test_governance_section_mentions_dispatch_only as test_governance_section_mentions_dispatch_only,
)
from tests.architectural._lifted_specify_cli_docs_readme_governance import test_runtime_next_skill_references_resolve as test_runtime_next_skill_references_resolve

pytestmark = [pytest.mark.architectural]
