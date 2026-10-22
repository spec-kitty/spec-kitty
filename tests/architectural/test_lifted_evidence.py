"""Always-on gate: the project-sync consent evidence manifest is immutable.

Lifted from ``tests/evidence/test_project_sync_consent_manifest.py`` (WP11
T049/T054), a ``tests/evidence`` tree recorded ``out_of_matrix`` in
``.github/ci-module-registry.yml`` — no per-PR lane selects it (#4374
disposition ledger, disposition 2 — lift-invariant).

The source suite exercises ``scripts/evidence/build_project_sync_consent_manifest.py``
through its real subprocess CLI across many fail-closed refusal branches
(floating refs, dirty checkouts, digest drift, duplicate ownership, expired
retention...). Those refusal branches are broad, enumerable-but-numerous
coverage and stay make-test-full-only; what is lifted here is the tree's
single headline claim from its own module docstring — the manifest builder
"fails closed and emits an immutable, deterministic bundle" — i.e. a valid
input set produces a schema-complete manifest, and once written that
manifest is never silently overwritten by a second run.
"""

from __future__ import annotations

import pytest

# The tests live once, in the shared home this gate and its source import
# (#5015); importing them is what makes pytest collect them in this module.
from tests.architectural._lifted_evidence import inputs as inputs
from tests.architectural._lifted_evidence import test_valid_inputs_produce_schema_complete_manifest as test_valid_inputs_produce_schema_complete_manifest
from tests.architectural._lifted_evidence import test_existing_manifest_is_never_overwritten as test_existing_manifest_is_never_overwritten

pytestmark = [pytest.mark.architectural]
