# Exemption mechanism -- `_PLACEHOLDER_BASENAMES`

<!-- Machine-readable exemption-registry row (R-014). Parsed by
     tests/architectural/test_exemption_registry_ratchet.py. ONE mechanism per
     file. Registered as a landing fold for PR #6569 (bulk-edit review gate:
     file creation is not a protected-content change). `status:
     justified-survivor` -- see "Why this cannot route onto the owner" below. -->


- mechanism: `_PLACEHOLDER_BASENAMES`
- module: `src/specify_cli/bulk_edit/diff_check.py`
- literals: `_PLACEHOLDER_BASENAMES`
- symbol: `_PLACEHOLDER_BASENAMES`
- retirement-wp: `n/a — new bulk-edit non-occurrence mechanism, landing-pass registration (PR #6569)`
- retirement-ref: `n/a`
- owner-route: `n/a — genuine survivor, outside is_toolchain_generated_churn's scope`
- status: `justified-survivor`

## Why this cannot route onto the owner

`_PLACEHOLDER_BASENAMES` lists zero-byte empty-directory markers (`.keep`, `.gitkeep`) by exact BASENAME. It belongs to the bulk-edit gate's "non-occurrence" class: files that cannot carry a textual occurrence of a renamed term. Every match is surfaced as a warning, never silently skipped.

These files are zero bytes by construction and so cannot contain any occurrence of a renamed term.

`is_toolchain_generated_churn` answers a different question: whether spec-kitty's OWN runtime bookkeeping (status logs, Op records, coordination residue) should be ignored by a dirty-state gate. These files are ordinary user-repository content, not spec-kitty toolchain output, so routing them through the owner would either misclassify them as spec-kitty churn (silently widening every dirty-state gate that consults the owner) or require the owner to learn user-repository file types. The classification is by what a file CAN CONTAIN, which is a bulk-edit review concern, so the list stays local to `diff_check.py` and is enumerated here so it is never a silent module-level collection.
