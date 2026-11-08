---
title: Review test execution budget
description: Configure a bounded per-run budget for complete baseline and candidate review tests.
doc_status: active
kind: Reference
updated: '2026-10-28T00:00:00Z'
related:
- configuration
---
# Review test execution budget

A project whose complete declared review command needs more than five minutes can
set its per-run budget in `.kittify/config.yaml`:

```yaml
review:
  test_command: zig build test
  test_output_format: text
  test_timeout_seconds: 1200
```

`test_timeout_seconds` accepts an integer from 1 through 86400 seconds. The
defaults depend on the **scope shape** the pre-review gate chose:

| Scope shape | Default budget |
|---|---|
| whole declared command | 1,200 s (`WHOLE_COMMAND_TEST_TIMEOUT_SECONDS`) |
| bounded target list | 300 s (`DEFAULT_TEST_TIMEOUT_SECONDS`) |

A repository whose declared command runs in full is not running a scoped check,
so the scoped default under-bounds it; the whole-command default is sized for a
whole-suite run (this repository's `make test-fast` was measured at 215 s of
pytest, and its CI bounds a whole per-PR lane at 20 minutes). A pinned per-WP
`pre_review_test_scope` narrows *what* runs, not the bound. A declared
`test_timeout_seconds` always wins, whatever the shape.

Booleans, fractions, strings, null, zero, negative values and larger values
are errors; an invalid declaration refuses the transition before a test runs,
and the shape default never masks it. The ceiling is one day per run, bounding
oversized declarations and platform waits. The setting changes execution time,
leaving the command, selected scope, failure comparison, oversized-scope policy
and timeout refusal policy intact.

The baseline and candidate use the same configuration authority as the declared
command. A lane's execution checkout and its detached baseline do not substitute
their own settings for the planning root's configuration. A validated owned
checkout supplies its own command, budget and receipt write authority; the
repository primary remains its Git identity. Explicit Python API
budget arguments take precedence for callers that already supply them.

Baseline receipts record `test_timeout_seconds`. Older receipts were captured with
the release's hardcoded 300-second budget and are interpreted as 300. A changed
budget triggers recapture on the next applicable review transition. If recapture
fails, a stale receipt remains historical evidence and cannot qualify the new
budget. A valid cached receipt at the same budget remains reusable under the
existing baseline policy.

Budget the outer invocation for **both** test runs, process cleanup and other gate
work. For example, two 1200-second legs can require more than 2400 seconds overall.
The candidate's machine lock still has its independent short acquisition budget;
baseline capture still bypasses that lock. On timeout, a
declared command (`review.test_command` resolved through the scope source, the
normal path) terminates and joins its whole process group before the temporary
workspace is released. The legacy config-driven capture path, used only when no
scope source is supplied, bounds the run with the same budget but stops only the
direct shell child.

This source change requires a release containing it. Installing an older published
CLI does not adopt this setting. A passing local fixture does not establish a
passing project aggregate, fleet deployment or production adoption.
