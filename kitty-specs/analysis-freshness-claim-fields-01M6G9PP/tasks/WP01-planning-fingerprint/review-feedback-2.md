# WP01 review — cycle 2: changes requested

Re-review of `601244d88c` (cycle 1's repair). F1's architectural failure is
resolved (singleton gate 10/10, gate file unchanged) and F2/F3's original
concerns check out. Three follow-on findings stand.

## Blocking

**G1 (MEDIUM) — the repair silenced an unexpected backend value and deleted its
positive control.** `_meta_fingerprint` now drops *every* `vcs` value, so
`{"vcs": "hg"}` or `{"vcs": null}` no longer changes the fingerprint, contrary to
FR-003/SC-002, and `601244d88c` removed
`test_unexpected_vcs_backend_still_changes_the_meta_hash`. The lock must be
*normalised*, not silenced: absent and the backend a claim writes (`git`) are the
same state; any other value is preserved and still stales the report. Restore the
positive control (parametrised over `"hg"`, `null`, `""`).

**G2 (MEDIUM) — `_meta_mapping` is an independent meta decoder.** It hand-rolls
`json.loads` over `meta.json` instead of routing through the canonical reader
(`mission_metadata.parse_meta_file` / `kernel.meta_decode.decode_meta`), which is
what `tests/architectural/test_inline_meta_read_gate.py` (FR-010) enforces — and
its scanner misses the helper precisely because it takes a generic `path`, so a
green enumeration does not prove compliance. Route it through
`mission_metadata.parse_meta_file` and keep the `MaterialInputError` translation
(and the missing-file sentinel, which is decided before the read).

## Non-blocking

**G3 (LOW) — the comparator probing is quadratic and not total.** Probing
membership with `is_vcs_lock_only_change(mapping minus key, mapping)` costs
O(n²) and defeats itself on a `NaN`-valued non-lock key (`NaN != NaN`), which
would reintroduce false staleness. Removing the probe (per G1/G2, by putting the
normalisation in the kernel that owns the field set) removes the problem
entirely.

## Accepted

- The `tasks/` flat-surface rule and the provenance triple are unchanged and
  correct; nested `tasks/<subdir>/` fixtures are legacy migration/repair shapes,
  not current planning content.
- `_include` recursion, refusal behaviour and `dict(zip(..., strict=True))` are
  preserved.
