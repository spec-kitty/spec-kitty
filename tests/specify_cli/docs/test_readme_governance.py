"""WP03 — README Governance layer subsection regression tests."""

from __future__ import annotations

import pytest

# The tests live once, in ``tests/architectural/_lifted_specify_cli_docs_readme_governance.py``, which this suite's
# always-on lift also imports (#5015); importing them is what makes pytest collect them here.
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
from tests.architectural._lifted_specify_cli_docs_readme_governance import (
    test_runtime_next_skill_documents_omitted_result_as_query_mode as test_runtime_next_skill_documents_omitted_result_as_query_mode,
)

pytestmark = [pytest.mark.unit, pytest.mark.fast]
