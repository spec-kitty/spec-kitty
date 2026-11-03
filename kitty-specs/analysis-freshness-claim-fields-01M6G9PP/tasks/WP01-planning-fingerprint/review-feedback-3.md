# WP01 review — cycle 3: one blocking finding

Re-review of `f219762caf`. G1–G3 are functionally resolved: selective backend
normalisation, non-mutating projection, canonical meta decoding with
`MaterialInputError` translation, unchanged missing-file sentinel, fail-closed
callers, linear projection, both architectural gates green without edits, and the
three end-to-end cases genuinely exercise sequential claims, the planning-edit
refusal and the rework re-claim.

## Blocking

**H1 (MEDIUM) — `src/kernel/vcs_lock.py:19–21`: two exported symbols with no
external production caller.** `VCS_LOCK_BACKEND_FIELD` and
`VCS_LOCK_TIMESTAMP_FIELD` were added to `__all__`, and
`tests/architectural/test_no_dead_symbols.py::test_no_public_symbol_in_all_is_unimported`
(#470) reds naming exactly them. Do not allow-list them: drop the two internal
constants from `__all__` (they stay in the module that owns the lock's names) and
leave the gate and its allow-list untouched — `project_metadata_without_vcs_lock`
is the public way to use them.

## Follow-through (not a code finding)

- The per-PR changelog fragment is deferred to T007/`docs/changelog/unreleased/README.md`;
  it must exist with the PR number before hand-off.
