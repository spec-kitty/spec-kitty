# WP01 review — cycle 1: changes requested

Independent review of `kitty/mission-analysis-freshness-claim-fields-01M6G9PP-lane-a`
(`375963f1a0`, plus `9f0907cb12`). The fix's behaviour is right, but two blocking
findings stand.

## Blocking

**F1 (HIGH) — the architectural singleton gate fails.**
`tests/architectural/test_meta_decoder_comparator_singletons.py::test_single_vcs_lock_comparator`
now finds two "VCS-lock comparator definitions":

```
src/kernel/vcs_lock.py:32 is_vcs_lock_only_change
src/specify_cli/analysis_inputs.py:141 _meta_fingerprint
```

`_meta_fingerprint` reads `VCS_LOCK_META_FIELDS`, and the gate treats any function
that inspects the field set as a forked comparator (NFR-002). Do **not** fix this by
renaming or relocating the reference to evade the detector, and do **not** refine a
gate for this mission's convenience: route the decision through the canonical API the
gate's own message prescribes (`kernel.vcs_lock.is_vcs_lock_only_change`) so the
field-set knowledge stays in its single home.

**F2 (MEDIUM) — malformed metadata can stay freshness-equivalent.**
`_meta_fingerprint` loads `meta.json` through `_mapping`, i.e. the safe YAML loader,
which accepts arbitrary YAML mappings and maps an empty/null document to `{}`. A
`meta.json` rewritten as an equivalent YAML mapping therefore fingerprints identically
even though the canonical metadata reader rejects it; before this change the whole-file
hash made that corruption visible. Parse `meta.json` as strict JSON and translate a
failure into `MaterialInputError` (fail closed, preserving the missing-file sentinel),
with tests for an equivalent YAML document, an empty document, `null`, and malformed
JSON.

## Non-blocking

**F3 (LOW) — the rework regression is under-asserted.** The first-claim test asserts
the claim really happened (lane state, stamp, untouched report bytes); the rework test
only asserts exit status and the absence of `analysis_report_required`. Add: WP01 is
`planned` right after the rejection, `in_progress` after the re-claim, and the recorded
report's bytes are unchanged.

## Notes

- Everything else checked out: the closure keeps config/charter/spec/plan/tasks index,
  flat `tasks/` entries (`.gitkeep`, README, prompts), `.kittify` declarative trees,
  packs, declared authorities, templates and package digests; `_include` preserves the
  escape/symlink/non-regular refusals; `dict(zip(..., strict=True))` preserves the
  writer's three keys and order; 71 relevant tests pass.
- Accepted, and recorded in the mission's `research.md`: an unexpected `vcs` value is
  no longer freshness-relevant once the lock is normalised away. Name it in the PR body
  so a maintainer can decide whether the audit signal is worth restoring.
