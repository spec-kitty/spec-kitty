"""The repository's terminology-exempt roots: one list for every terminology scan.

Policy and rationale for each root:
``docs/development/reference/terminology-exemptions.md``. The live-doc guard
(``tests/contract/test_terminology_guards.py``) and the #4836 operator-surface
gates read this list, so a root exempted for one is exempted for all and the
policy document has one list to describe.
"""

from __future__ import annotations

__all__ = ["FORBIDDEN_SCAN_ROOTS"]

FORBIDDEN_SCAN_ROOTS = (
    "kitty-specs/",
    "architecture/",
    ".kittify/",
    "tests/",
    "docs/migrations/",
    # docs/adr/ holds immutable historical decision records (the common-docs move
    # relocated them from the unscanned architecture/ tree). Their bodies are
    # byte-invariant under C-002/C-006 and legitimately reference era-correct
    # wording (--feature, main-centric workflow). Mirrors the narrow docs/adr/
    # exemption in tests/architectural/test_no_legacy_terminology.py.
    "docs/adr/",
    # docs/archive/ holds retired pages relocated out of the live tree by #5428
    # ("archive retired pages and neutralize 3.x-anchored names"). They are
    # immutable historical snapshots that legitimately retain era-correct wording
    # (--feature, main-centric workflow), exactly like docs/adr/ — the Terminology
    # Canon permits legacy wording in explicitly-archived artifacts. #5428 moved
    # the pages but did not exempt docs/archive/ here, so the scan began flagging
    # e.g. docs/archive/plans/initiatives/test_improvement/IMPLEMENTATION_COMPLETE.md
    # ("Merge to main"); this restores the archival exemption. See #5488.
    "docs/archive/",
    # Historical/archival sub-areas relocated under docs/plans/ by the common-docs
    # move (the old, unscanned engineering_notes/initiatives world): completed
    # initiative records, retained 1.x deep-dive notes, and engineering notes.
    # These are archival records of era-correct decisions, not live first-party
    # docs — the active planning pages at docs/plans/*.md stay scanned.
    "docs/plans/engineering-notes/",
    "docs/plans/initiatives/",
    # Dated report snapshots (e.g.
    # docs/reports/tracer-friction-recon/2026-09-26/) are immutable
    # point-in-time records that legitimately quote retired command/flag
    # shapes on purpose -- rewording them would falsify the historical
    # record they exist to preserve. docs/reports/ is already classified
    # as an immutable-historical-snapshot prefix by ARCHIVE_PATH_PREFIXES
    # in tests/architectural/test_no_dead_src_path_literals.py; this
    # mirrors that classification rather than inventing a third, divergent
    # exemption list. Guarded by
    # test_docs_reports_exemption_is_not_published_as_live_docs in
    # tests/contract/test_terminology_guards.py, which fails loudly if
    # docs/docfx.json ever publishes reports/ as live docs.
    # See spec.md R6 / #5187 (nightly-drift-reds-01M3M14S).
    "docs/reports/",
)
