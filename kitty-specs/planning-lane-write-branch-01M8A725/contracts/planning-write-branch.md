# Contract: operator-visible outputs of the planning lane write branch

These are CLI outputs, not an HTTP API. Tests assert the bracketed values; the surrounding wording may change.

## C1 — `implement` workspace for a planning work package

| Shape | Workspace | Branch named in the message |
|---|---|---|
| default, not landed, Mission branch held by the coordination worktree | `<repo>/.worktrees/<slug>-coord` | `[mission_branch]`, described as "the Mission branch (the coordination branch)" |
| explicit topology, or landed | repository root checkout | `[target_branch]` (unchanged) |
| default, not landed, no checkout holds the Mission branch | refusal: no workspace | the named remedy (restore the coordination worktree) |

`--json` payloads that carry the workspace path report the same path.

## C2 — `IMPLEMENTATION_MISSING` for a planning work package of a default, not-landed Mission

- Window: `[claim_event_commit]..[mission_branch] (lane-planning)`.
- Remedy: commit the owned change on the Mission branch, in the coordination worktree.
- In-flight addendum, present only when owned changes exist on the target only:
  - "found on the target branch only: `[sha…]`";
  - remedy 1: cherry-pick them onto the Mission branch;
  - remedy 2: `--attest-no-implementation <WP> --attest-reason "..."` where the work package owes no implementation.
- The addendum never appears for a hollow work package.

## C3 — Error codes

No new codes. The existing codes are used: `IMPLEMENTATION_MISSING`, `IMPLEMENTATION_UNREADABLE`, `EVIDENCE_WINDOW_UNCOMPUTABLE`, `OWNERSHIP_UNRESOLVED`, `REVIEW_NOT_INDEPENDENT`.
