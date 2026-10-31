# WP02 review feedback 2 — aggregate review finding (post-approval)

The aggregate review of the integrated diff raised one defect that touches WP02's
surfaces, so the lane moved after its approval stamp and needs a fresh approval.

**Finding (LOW, real).** `consolidation/forecast.py` compared the resolved `--target`
against `lanes.json`'s `target_branch`, while the real run compares it against
`meta.json` via `resolve_merge_target_branch(..., None)`. Both are written from the
same resolution, so they normally agree, but if they ever drift the preview could
refuse a run the real command allows (or the reverse) — the exact disagreement this
mission exists to remove.

**Fix.** `_forecast_recorded_target` resolves `meta.json` the way the real run does
and falls back to the manifest value only when `meta.json` cannot be read (a preview
must not own that failure). Commit f1a0583.

**Re-verified.** `tests/terminus/test_protected_target_preflight.py`,
`tests/agent/cli/commands/test_merge_target_resolution.py` and
`tests/lanes/test_merge_policy.py`: 24 passed.
