---
affected_files: []
cycle_number: 2
mission_slug: untrusted-audit-relocation-pairing-01M66F6X
reproduction_command:
reviewed_at: '2026-10-30T14:44:06Z'
reviewer_agent: user
wp_id: WP01
---

# WP01 Review Round 1 — REJECT (reviewer-renata, independent delegate)

Commit under review: 12546928b4 on kitty/mission-untrusted-audit-relocation-pairing-01M66F6X-lane-a.

## Verified empirically (all pass)

- Module: 30/30 passed; 12 pre-existing assertions byte-unchanged.
- FR-001/FR-002: one `sink moved:` finding naming both locators, ghost+undercount suppressed, exit 1; two independent relocations fixed in one pass.
- FR-003 fail-closed on all three paths (unrelated error; buggy rewrite; relocation emptying a KNOWN_CANDIDATE_FILE → re-audit refuses).
- Teeth through main(): removal → overcount only; new sink → undercount only; truncation guard blocks pairing.
- NFR-001: green-tree output byte-identical to origin/main. NFR-002: 3.6s vs 3.9s baseline.
- Inventory edits surgical: exactly 6 source-cell re-pins, 0 disposition/sink_op changes, 12 rationale edits.

## BLOCKER

B-1. The two new audit guards (_check_source_canonicality, _check_no_line_shift_chains) have no red-direction tests — they are unpinned against silent removal. SC-004's letter requires a test asserting the chain regex on every sink-table rationale cell; T006/T009 say "Add its test". Removing either check (or weakening the regex) keeps every existing test green. Fix: add red-direction tests for checks 5 and 6 through the real seams (e.g. main() on a tmp inventory copy).

## MAJOR

M-1. Red-first proof and NFR-002 runtime are not recorded in the WP01 history block (T001/T008 contracted deliverables; C-004 and the DoD depend on them). baseline-tests.json recorded total: 0 (empty capture). Fix: record the red run (command + output summary) and before/after runtimes in the WP01 history.

M-2. The commit's "mypy --strict clean" claim is false for tests/architectural/test_untrusted_path_containment.py: 14 errors, all in the new code (bare generics, untyped params, no-any-return, attr-defined on the private composite_key_from_file re-export). Fix: annotate the new test code and reference composite_key_from_file via its owning module.

## MINOR

m-1. SinkRow._key_cache participates in __eq__/__hash__/__repr__ (frozen dataclass default) — latent trap; use field(compare=False, repr=False).
m-2. Over-trim of substantive #2091 provenance on coordination/surface_resolver.py:552 and :504 (the fail-closed reasoning about CoordinationWorkspace.worktree_path requiring a non-empty mid8) — restore the behavior-relevant note without the line arithmetic.
m-3. Near-miss note names an arbitrary first token-match and is O(ghosts x missing) — name all matching candidates.

## NOTE (no action required)

n-1. Inherent false-pairing hazard of the (token, source)+uniqueness key is spec-accepted and confirmed reproducible; still exits red pre-fix.
n-2. pair_relocations signature deviates from T002's prescribed form (rich Mapping in / RelocationPair out) — defensible (exact-source comparison needs it); document the deviation in the WP history.
n-3. _apply_relocation_fixes re-serializes matched rows with normalized " | " spacing; no current row affected.
