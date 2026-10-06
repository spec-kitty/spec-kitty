# Tracer: design decisions

Decisions and their rationale (Decision Moments are under `decisions/`).

- `plan.design.internal-call-style`: owner-qualified calls everywhere inside `src/runtime/next/`; bridge re-exports serve only outside callers.
- `plan.design.bulk-edit-classification`: not a bulk edit; per-site call-path review.
- `plan.design.acceptance-gate`: permanent static gate, per-seam strict-xfail ratchet.
- Close-out: the bridge now calls seam names that start with an underscore (`_io_seam._existing_run_ref`, `_composition._dispatch_via_composition`). They are a cross-module API in all but name; #2560 adds more such calls, so it may be the place to make them public (noted in the PR, not ticketed).
- Close-out: `_compute_wp_progress` patches stay on `runtime_bridge` because the bridge imports it from `runtime.next.decision` at module scope; the bridge binding is the patch point. Not a compat delegate.
