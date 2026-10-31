# Tracer: design-decisions

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-30 · python-pedro · DD-1 detection is a query on IdentityIndex's memoised per-kind tables (no second directory walk). DD-2 validate compares pack-under-validation with the built-in layer only (a bare path must not read repo config). DD-3 doctor runs the query over the configured chain as a _run_*_check leg that appends to org_drg['errors']. DD-4 severity is error in both, with no opt-in: a deliberate override keeps the same id.

2026-10-30 · reviewer-renata · Review of WP01/WP02: the identity leg is complete for validate (all three pack levels label correctly; packs/internal and packs/built-in report zero collisions) but charter pack assemble remains a third door that can write a colliding pack — deferred as #6825 because the approved spec scopes this mission to validate + doctor.

2026-10-30 · comms-cleo · Docs: docs/api/cli-commands.md is generated from --help and the freshness gate reports it in sync, so the new category is documented in docs/api/charter-commands.md (the prose reference) plus the how-to error table; the changelog entry went under [Unreleased] Fixed because the defect is the silence, not a new feature surface.

2026-10-30 · reviewer-renata · Development-assist test verdict at wrap-up: the issue-named file tests/charter/activation/test_file_name_collision_diagnostic_6743.py (3 tests) is FOLDED into tests/charter/activation/test_identity_index.py, the suite that already owns token<->id<->stem identity and the stored_spelling collision tests, and the file is deleted. Keep-as-own-file was rejected because it duplicated the identity fixture and split one contract across two files; nothing is retired, all three tests guard standing invariants (diagnostic/refusal agreement, message content, same-id control). No split was needed.
