# Exemption mechanism -- `_OPAQUE_SUFFIXES`

<!-- Machine-readable exemption-registry row (R-014). Parsed by
     tests/architectural/test_exemption_registry_ratchet.py. ONE mechanism per
     file. Registered as a landing fold for PR #6569 (bulk-edit review gate:
     file creation is not a protected-content change). `status:
     justified-survivor` -- see "Why this cannot route onto the owner" below. -->


- mechanism: `_OPAQUE_SUFFIXES`
- module: `src/specify_cli/bulk_edit/diff_check.py`
- literals: `_OPAQUE_SUFFIXES`
- symbol: `_OPAQUE_SUFFIXES`
- retirement-wp: `n/a — new bulk-edit non-occurrence mechanism, landing-pass registration (PR #6569)`
- retirement-ref: `n/a`
- owner-route: `n/a — genuine survivor, outside is_toolchain_generated_churn's scope`
- status: `justified-survivor`

## Why this cannot route onto the owner

`_OPAQUE_SUFFIXES` lists opaque binary media and compiled output (webfonts, raster images, audio/video, compiled objects) by file SUFFIX. It belongs to the bulk-edit gate's "non-occurrence" class: files that cannot carry a textual occurrence of a renamed term. Every match is surfaced as a warning, never silently skipped.

A file with one of these suffixes is a byte stream that cannot carry a textual occurrence of a renamed term, so the bulk-edit review gate does not demand a category for it in the occurrence map (it would otherwise block as FR-008 unclassified and force a reviewer to label it with an action that is untrue of it). `.svg` and `.pdf` are deliberately absent: they are text-bearing and still need a category. Opaque data files (`.dat`, `.bin`, `.db`, `.sqlite`, `.pkl`, archives) are also absent: they can carry serialized keys.

`is_toolchain_generated_churn` answers a different question: whether spec-kitty's OWN runtime bookkeeping (status logs, Op records, coordination residue) should be ignored by a dirty-state gate. These files are ordinary user-repository content, not spec-kitty toolchain output, so routing them through the owner would either misclassify them as spec-kitty churn (silently widening every dirty-state gate that consults the owner) or require the owner to learn user-repository file types. The classification is by what a file CAN CONTAIN, which is a bulk-edit review concern, so the list stays local to `diff_check.py` and is enumerated here so it is never a silent module-level collection.
