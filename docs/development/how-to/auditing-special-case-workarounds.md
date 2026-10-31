---
title: 'Auditing special-case workarounds'
description: 'How to find, classify and remove the branches that tolerate a wrong input, a private seam or a test double instead of fixing the cause, with the dispositions from issue #6745.'
doc_status: active
updated: '2026-10-31'
audience: docs/context/audience/internal/maintainer.md
type: how-to
related:
- docs/development/how-to/review-gates.md
- docs/development/how-to/pr-landing.md
- docs/development/reference/quality-and-tech-debt-standing-orders.md
- docs/adr/4.x/2026-09-30-1-allowlist-ratchets-are-priced-debt.md
- docs/changelog/index.md
---
# Auditing special-case workarounds

**Audience**: maintainers and implementers who are about to add a branch that
makes a wrong input, a missing seam or a test double "just work".

A special-case workaround is a branch that tolerates something the code should
have fixed or refused. It buys a green test and costs a second authority: the
tolerated case behaves differently from the canonical path, the two drift, and
the next change has to keep both working. Issue
[#6745](https://github.com/spec-kitty/spec-kitty/issues/6745) is the standing
ticket for finding them; this page is the method it uses and the ledger it
produced, so the next audit starts from a table instead of a keyword grep.

## Is it a workaround? Ask the input question first

Before adding a branch, ask: **is the input wrong, or is the code wrong?**

| If… | Then the answer is | Not |
| --- | --- | --- |
| the value cannot legitimately occur | refuse it where it enters, with a structured error | a warning plus "keep as given" |
| the caller cannot reach a private helper | publish the seam | a duplicated copy of the helper |
| only a test double needs the tolerance | fix the double | `getattr(..., default)` in production |
| the cause was fixed in a later mission | delete the compensation | keep it "just in case" |
| two modules must agree on one decision | call the one authority | a hand-synced second copy |

A tolerance that survives this table needs a comment naming the cause it
tolerates **and** the issue that removes it.

## The method

Six greppable heuristics, then classification. Time-box one pass per subsystem
you are already touching (roughly twenty minutes each); this is a sweep, not a
line-by-line review.

1. **Names and comments**: `compensat`, `tolerat`, `workaround`, `fallback`,
   `legacy`, "for now", "best-effort", "kept as written", "defensive",
   "belt and braces", "does not depend on a private".
2. **Broad `except` that yields an empty value or a default** instead of
   surfacing (in this repo: `except Exception  # noqa: BLE001`).
3. **A second construction** of an object another module already builds — a copy
   kept alive because the original builder is private.
4. **Production code shaped by a test double**: `getattr(..., default)`,
   duck-typed `len`/`in`, `try/except TypeError` around a read.
5. **Shrink-only allowlists and baselines** still carrying entries whose cause is
   gone (see [ADR 2026-09-30-1](../../adr/4.x/2026-09-30-1-allowlist-ratchets-are-priced-debt.md)).
6. **Docstrings describing "residuals", "carve-outs" or a validator "elsewhere"**
   that does not exist.

Then classify each finding — exactly one of:

| Classification | The fix | The tell |
| --- | --- | --- |
| **genuine constraint** | keep it, and say in the comment what it protects | removing it breaks a documented contract or a real user's data |
| **workaround for bad data** | refuse or report the input where it enters | the tolerated value has no legitimate producer |
| **workaround for a missing seam** | add the seam, delete the branch or copy | the comment says the original is private |
| **dead compensation** | delete it | the cause it compensates for was removed in a merged mission |

## The ledger from #6745 (2026-10-31)

`S<n>` ids are stable for follow-ups. Evidence paths are `path:line` at
`origin/main` `dfe9efb0e8`; the full write-up is the mission's `research.md`
§4.

| Id | Site | Classification | Disposition |
| --- | --- | --- | --- |
| S1 | `src/charter/activation/resolver.py:216-224` (`_gated`) | workaround for bad data | **Left.** An unknown activation token is logged and kept best-effort, then silently dropped by the filter. Refusing it is reachable from real org-pack content, so it needs an operator decision: [#6527](https://github.com/spec-kitty/spec-kitty/issues/6527) (open, claimed). |
| S2 | `src/charter/activation/org_charter.py:333-341` (`_best_effort_offering_root`) | genuine constraint (weak) | **Left.** `resolve_offering_root()` owns its own fallback chain and returns a `Path`; the wrapper's swallow is the documented best-effort contract of three writers. Tightening it is a refusal change, tracked with S1. |
| S3 | `src/specify_cli/lanes/worktree_allocator.py:1135-1142` | genuine constraint (stale comment) | **Left.** Legacy missions without `coordination_branch` still exist in user repositories and need the `mission_branch` fallback; only the "WP08 will harden it" comment is stale. |
| S4 | `src/charter/offering/drg/org_pack_config.py:649-651` (`ensure_pack_identity`) | workaround for missing data | **Left.** The planned pack_id backfill owns it; the docstring at `:196-206` says loading without a `pack_id` raises only once the pack_id-keyed readers land. |
| S5 | `src/specify_cli/lanes/implement_support.py:602` (`reenter_lane_self_heal`) | workaround for a missing seam | **Left here** (needs an allocator refactor, not a P0-audit PR): [#6898](https://github.com/spec-kitty/spec-kitty/issues/6898). |
| S6 | 327 `except Exception  # noqa: BLE001` in `src/` | mixed — **sampled, not reviewed** | **Sampled.** The nine in `src/charter/activation/context_renderers/` are genuine constraints: doctrine rendering degrades to a diagnostic instead of crashing a prompt build. The rest of the 327 are **unreviewed** and this audit does not claim them. |
| S7 | `src/specify_cli/mission_loader/command.py:206-235` | workaround for a missing seam | **Removed in this PR.** The loader kept a byte-identical copy of the runtime's `DiscoveryContext` builder because it was private (its own docstring said so), and mission `up-org-template-fsm-01M06F9K` then had to wire the org tier into both copies. One public builder now: `runtime.next.runtime_bridge_io.build_discovery_context`; a patch-point test proves `mission run` observes it. |
| S8 | `src/runtime/next/runtime_bridge_composition.py:615-645` | production shaped by a test double | **Removed in this PR.** `getattr(result, "invocation_ids", ())`, a `len()` `except TypeError` and `getattr(result, "steps", ())` existed "so test mocks (MagicMock) and real instances both flow through cleanly"; the executor's result type always carries both. The read is direct, the tolerance-pinning test became a contract test, and a non-sized value now raises instead of logging `emitted 0 invocation(s)`. |
| S9 | `src/specify_cli/ownership/validation.py:150` | workaround for bad data (phantom authority) | **Left.** `continue  # defensive: ignore cycles (validated elsewhere)` names a validator that does not exist; the guard bounds the recursion, so the clean fix is to refuse a cyclic `depends-on` graph where it enters: [#6899](https://github.com/spec-kitty/spec-kitty/issues/6899). |
| S10 | `src/specify_cli/upgrade/autocommit.py:221-245` | not a second authority | **Left.** `should_auto_commit_for_worktree` is a documented twin (D-10) of `should_auto_commit`; both are two-line wrappers over one `get_auto_commit_default` decision. Collapsing them is taste, not debt. |

The issue's worked example (the activation "keep the id as given, with a
warning" family, mission `activate-output-and-identity-01M5ZA9X`) is **not** in
the table because it already landed: PR #6748 made
`IdentityIndex.stored_spelling` the one spelling authority and removed the
hand-rolled variants. Do not re-litigate it.

## What this audit did not cover

- **The 318 unsampled `BLE001` sites.** S6 is a sample of one subsystem. A
  second pass should take one package per session and record a row per hit.
- **Refusal changes.** S1, S2 and S9 all convert a silent tolerance into a
  refusal, which is a behaviour change for existing pack and mission content.
  They are child issues, not this PR.
- **The process guard.** The proposal — a reviewer checklist line, a "workaround"
  lens for the adversarial squad, and a naming rule for tolerated paths — is
  [#6900](https://github.com/spec-kitty/spec-kitty/issues/6900), filed for the
  operator to accept or reject. It is deliberately **not** in `packs/built-in/`:
  that pack ships to every consumer, and this is in-house review practice.

## Related

- Issue: [#6745](https://github.com/spec-kitty/spec-kitty/issues/6745)
- Child issues: [#6527](https://github.com/spec-kitty/spec-kitty/issues/6527),
  [#6898](https://github.com/spec-kitty/spec-kitty/issues/6898),
  [#6899](https://github.com/spec-kitty/spec-kitty/issues/6899),
  [#6900](https://github.com/spec-kitty/spec-kitty/issues/6900)
- [Review gates: pre-PR / pre-review checklist](review-gates.md)
- [Quality & Tech-Debt Standing Orders](../reference/quality-and-tech-debt-standing-orders.md)
