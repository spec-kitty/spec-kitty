# Tracer: approach

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-11-02 · pi · Surveyed the entry points before coding: ScenarioLifecycle (the guard), FileSnapshots (its sibling snapshot helper), src/runtime/next/_tmp_namespace.py (owner of spec-kitty-prompts) and src/spec_cli/review/pre_review_gate.py (owner of gate-locks). The exclusion is keyed on the first path component below the fingerprinted root, so a new prompt or lock filename cannot silently escape the list.
