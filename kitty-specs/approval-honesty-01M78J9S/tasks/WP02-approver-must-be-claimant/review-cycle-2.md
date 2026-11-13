---
affected_files: []
cycle_number: 2
mission_slug: approval-honesty-01M78J9S
reproduction_command:
reviewed_at: '2026-11-13T02:59:19Z'
reviewer_agent: claude::reviewer-renata
wp_id: WP02
---

# WP02 review feedback (cycle 2) — reviewer-renata

**Verdict: changes requested.** The cycle-1 defect is fixed. One narrow regression that this cycle introduced remains: on an unforced approval, a caller-supplied `--reviewer` can now be recorded as a reconstruction seed (#6754).

## Defect: `--reviewer migration:<x> --profile <p>` records a seed-shaped approval actor

Probed through the real `move-task` on the #4670 fixture. The approval is unforced and direct (`for_review -> approved`, so there is no claimant). The same applies out of `in_review` when there is no claimant. There is no `--agent`.

```
move-task WP01 --to approved --reviewer migration:x --profile python-pedro --note ok
```

| commit | exit | recorded `actor` | review fields |
|---|---|---|---|
| `1693d554` (base) | 0 | `{tool: "migration", model: "x", profile: "python-pedro"}`, parsed strictly, not a seed | `migration:x` |
| `9fe2f097` (cycle 1) | 0 | the same (strict) | `migration:x` |
| `eff12bb4` (cycle 2) | 0 | `{tool: "migration:x:python-pedro", profile: "python-pedro"}`: `is_migration_actor` is True and `reduces_as_reconstruction_seed` is True | `migration:x:python-pedro` |

**Cause.** `tasks_move_task_hops.py::_mt_structured_actor` uses the strict builder for `--reviewer` only when `tool_identity == st.reviewer.strip()`. Cycle 2 now hands it the bound identity (`asserted_review_identity`, which is `migration:x:python-pedro`). That no longer equals the raw flag (`migration:x`), so the value falls through to `actor_from_option(..., recorded=True)`. That builder keeps a `migration:` value whole as a *recorded* seed. A caller flag is therefore replayed as if it had been read out of the log. This is exactly what #6754 forbids: "a caller-supplied value shaped like a seed is refused rather than recorded". The result is an unforced approval that the reducer and `approved_bound` treat as history restated by a migration.

Without `--profile`, or with `--agent migration:x`, the actor is still strict at `eff12bb4`. Only the `--reviewer`-without-`--agent` path under a binding regressed.

**Required (small):**
- In `_mt_structured_actor`, treat `--reviewer` as asserted when `tool_identity` is the identity it records, i.e. compare against `asserted_review_identity(st.reviewer, st.resolved_binding)`, not the raw flag. The simpler alternative is `st.agent or st.reviewer` whenever the hop records the reviewer of record. Either way an asserted flag must always go through `build_status_actor`. This is WP01's file; record it as a leeway edit as you did for `tasks_move_task.py`.
- Add a regression test (in `test_move_task_structured_actor_6400.py`, beside `test_recorded_migration_identity_stays_a_reconstruction_seed`). An unforced approval with `--reviewer migration:x --profile python-pedro` and no `--agent` must record a non-seed actor (`not reduces_as_reconstruction_seed(actor)`), and its review fields must name the same identity as the actor.
- Optional, and better if cheap: refuse a seed-shaped `--agent`/`--reviewer` upfront on `move-task` (`refuse_seed_shaped_identity`). The base already accepts `--agent migration:x` as tool `migration`, so treat this as a follow-up and not a requirement.

## Everything else checked and fine

- **Cycle-1 defect fixed.** I ran a 260-combination matrix through the real CLI: claimants (`claude:sonnet:reviewer-renata`, `claude::reviewer-renata`, `claude::python-pedro`, bare `claude`, and none/direct) × `--agent` × `--reviewer` × `--profile`. Results:
  - 77 runs were accepted, all unforced. In every one, `actor`, `evidence.review.reviewer`, `review_result.reviewer` and `policy_metadata.tool` name the claimant, or for a direct approval one identity.
  - Every refusal exited 1 with a byte-identical log and no git change.
  - Probe 1 is refused `APPROVER_NOT_CLAIMANT`. Probe 2 records `codex::reviewer-renata` in every field.
- **One identity.** The guard, the combiner (`_mt_reviewer_of_record`) and `claimant_as_recorded` all use `asserted_review_identity`. The only raw-flag consumers left are the cycle writer (the WP03 xfail) and the hop actor described above.
- **Binding-override refusal.** It is correct (see the report for the scope note). A binding that only fills an empty segment passes, and a conflicting profile refuses. The canonical flows (`--agent claude::reviewer-renata`, `--agent claude --profile reviewer-renata`, a bare `--profile` matching the claim) still pass.
- **Red-first.** `265badf3` gives 9 failed / 43 passed. `e7b9d56d` gives 11 failed / 31 passed / 1 xfailed. `eff12bb4` gives 56 passed / 1 xfailed.
- **Strict xfail.** It is the right hand-off: WP03 T-list line 201 already requires `reviewer_agent` from the reviewer of record, and the xfail flips red when that lands.
- **Checks.** ruff, format (`--force-exclude`), C901 and mypy are clean. `_do_move_task` is unchanged. No forbidden files are touched, and the trailers are correct.
