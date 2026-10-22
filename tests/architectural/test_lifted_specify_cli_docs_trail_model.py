"""Always-on freshness gate: docs/architecture/trail-model.md subsections stay present.

Lifted from ``tests/specify_cli/docs/test_trail_model_doc.py`` (WP08), a
``tests/specify_cli/docs`` tree recorded ``out_of_matrix`` in
``.github/ci-module-registry.yml`` — no per-PR lane selects it (#4374
disposition ledger, disposition 2 — lift-invariant).
"""

from __future__ import annotations

import pytest

# The tests live once, in the shared home this gate and its source import
# (#5015); importing them is what makes pytest collect them in this module.
from tests.architectural._lifted_specify_cli_docs_trail_model import (
    test_trail_model_has_mode_enforcement_subsection as test_trail_model_has_mode_enforcement_subsection,
)
from tests.architectural._lifted_specify_cli_docs_trail_model import (
    test_trail_model_has_correlation_links_subsection as test_trail_model_has_correlation_links_subsection,
)
from tests.architectural._lifted_specify_cli_docs_trail_model import (
    test_trail_model_has_saas_read_model_policy_section as test_trail_model_has_saas_read_model_policy_section,
)
from tests.architectural._lifted_specify_cli_docs_trail_model import test_trail_model_has_saas_policy_table_header as test_trail_model_has_saas_policy_table_header
from tests.architectural._lifted_specify_cli_docs_trail_model import (
    test_trail_model_has_tier2_deferral_subsection as test_trail_model_has_tier2_deferral_subsection,
)
from tests.architectural._lifted_specify_cli_docs_trail_model import test_trail_model_has_host_surfaces_subsection as test_trail_model_has_host_surfaces_subsection
from tests.architectural._lifted_specify_cli_docs_trail_model import test_trail_model_mode_prose_updated as test_trail_model_mode_prose_updated

pytestmark = [pytest.mark.architectural]
