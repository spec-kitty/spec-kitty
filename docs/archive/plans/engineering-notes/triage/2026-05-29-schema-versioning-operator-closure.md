---
title: Schema-Versioning Launch Cluster Operator Closure
description: 'Operator closure (2026-05-29) of the schema-versioning launch cluster: the issues resolved and the closure decision recorded.'
doc_status: deprecated
updated: '2026-05-29'
---
# Schema-Versioning Launch Cluster Operator Closure

Date: 2026-05-29

Issues:

- Priivacy-ai/spec-kitty#1198
- Priivacy-ai/spec-kitty#1200
- Priivacy-ai/spec-kitty#1203
- Priivacy-ai/spec-kitty#1281

## Decision

The schema-versioning launch cluster has launch evidence posted, operator
closure accepted, and all four tracked `spec-kitty` issues closed. No additional
implementation delta is required in `spec-kitty`.

## Evidence Reviewed

- Parent evidence comment:
  <https://github.com/Priivacy-ai/spec-kitty/issues/1198#issuecomment-4525778364>
- Child issue closure-evidence comments:
  - <https://github.com/Priivacy-ai/spec-kitty/issues/1200#issuecomment-4525778553>
  - <https://github.com/Priivacy-ai/spec-kitty/issues/1203#issuecomment-4525778603>
  - <https://github.com/Priivacy-ai/spec-kitty/issues/1281#issuecomment-4525778646>

The evidence records merged cross-repo PRs for canonical producer contracts,
CLI producer refactor, SaaS legacy normalization, SaaS materializer follow-up,
and end-to-end canary coverage.

## Local Verification

From a fresh `spec-kitty` workspace:

```bash
SPEC_KITTY_ENABLE_SAAS_SYNC=1 uv run --extra test python -m pytest tests/status/test_producer_conformance.py
SPEC_KITTY_ENABLE_SAAS_SYNC=1 uv run --extra test python -m pytest tests/sync/test_event_emission.py tests/sync/test_events.py
python scripts/lint_canonical_producers.py --paths src scripts tests --baseline scripts/canonical_producer_lint_baseline.txt
```

Results:

- `tests/status/test_producer_conformance.py`: 22 passed.
- `tests/sync/test_event_emission.py tests/sync/test_events.py`: 127 passed.
- `canonical-producer-lint`: passed.

## Follow-Up

The only repo delta found during this closure pass was a stale
`canonical-producer-lint` baseline entry for
`src/specify_cli/next/_internal_runtime/engine.py::CP001`. This PR removes that
entry while preserving the baseline rationale.
