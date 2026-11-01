---
title: 'ADR 2026-04-15-2: Explicit Empty Charter Selections Remain Empty'
description: 'An empty paradigm, directive, or tool selection compiles to empty; the charter compiler may never silently expand an explicit empty list into shipped defaults.'
status: Accepted
date: '2026-04-15'
doc_status: active
kind: ADR
updated: '2026-04-15T00:00:00Z'
---

## Context

`spec-kitty charter generate` compiles a project charter from
`.kittify/charter/interview/answers.yaml`.

That interview schema includes explicit selection lists for:

- `selected_paradigms`
- `selected_directives`
- `available_tools`

During emergency hardening of the charter flow, it became clear that the
compiler treated explicit empty selections as "apply all shipped defaults".
That behavior is wrong.

If the interview or the agent leaves one of these lists empty, that means one of
two things:

1. no shipped doctrine/tooling cleanly fits the user's needs yet, or
2. the user deliberately does not want shipped doctrine/tooling imposed.

Broadening an explicit empty list into the full catalog force-feeds doctrine
that the user did not ask for, misrepresents the interview outcome, and makes
the generated charter less truthful than the source answers.

## Decision

Explicit empty charter selections remain empty.

Specifically:

- `selected_paradigms: []` stays `[]`
- `selected_directives: []` stays `[]`
- `available_tools: []` stays `[]`

The compiler must not silently expand an explicit empty selection into mission
defaults or the full packaged catalog.

Defaults remain valid only when the user explicitly asks for defaults or when a
bootstrap path generates non-empty default interview data before compilation.

## Consequences

### Positive

- The generated charter reflects the interview truthfully.
- Users are not force-fed shipped doctrine they did not ask for.
- Doctrine gaps can be represented honestly as project-specific charter policy.
- `/spec-kitty.charter` can safely say "do not force a near-match" and the
  compiler will honor it.

### Negative

- Some generated charters will be intentionally sparse until doctrine is added
  or the user chooses concrete shipped selections.
- Existing assumptions that "empty means defaults" must not be reintroduced in
  future compiler or CLI refactors.

## Rules Going Forward

1. Treat empty lists as an intentional state, not missing data.
2. If defaults are desired, they must be made explicit before compilation.
3. Any future charter compiler rewrite must preserve this invariant.
4. Reviewers should reject changes that broaden explicit empty selections.

## Implementation Notes

The invariant is enforced in the charter compiler sanitization path and covered
by regression tests asserting that compiled selections and rendered charter
output preserve empty lists exactly.
