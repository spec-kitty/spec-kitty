"""WP08 — docs/architecture/trail-model.md subsection presence regression tests."""

from __future__ import annotations

import pytest

# The tests live once, in ``tests/architectural/_lifted_specify_cli_docs_trail_model.py``, which this suite's
# always-on lift also imports (#5015); importing them is what makes pytest collect them here.
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

pytestmark = [pytest.mark.unit, pytest.mark.fast]
