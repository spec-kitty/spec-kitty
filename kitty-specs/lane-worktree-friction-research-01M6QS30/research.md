# Research: lane and worktree execution model friction

Mission `lane-worktree-friction-research-01M6QS30`. The report is
`docs/plans/engineering-notes/2026-11-06-lane-worktree-friction-research.md`.

## Decisions

1. **The operator's observation holds only in part.** Lane, worktree and coordination friction is
   the largest single family, and it is over-represented in severe defects. It is a minority of
   all friction, 24-32% (E1-E3). The persistent per-lane checkout alone is under 10% (E1, E2).
   Rationale: two independent sources agree, and each was hand-validated at 85-93% on the
   lane / not-lane split.
2. **Most of that friction comes from the coordination topology and the consolidation
   transaction, not from lane checkouts** (E1, E2, E4, E6).
3. **Lanes can stay branches while their checkouts become short-lived.** The attribution and
   approval gates read refs (E7). The for_review gate still needs the lane checkout
   (`lanes/for_review_gate.py:280`) and must move onto the ref first.
4. **Recommended order:**
   1. (a) tighten: a per-topology read contract and the for_review gate moved onto the lane ref;
   2. (g) lane branches stop carrying `status.events.jsonl`;
   3. (e) the service writes coordination status without a worktree, as a step after migration
      step 4;
   4. (b) short-lived lane checkouts.

   (c), a `single_branch` default, is left to the operator because it reverses #5100. Reject
   (d). The first slice is one status read contract. Rationale: report sections 4 and 5;
   squad dispositions in `research/squad-dispositions.md`.

## Evidence

| ID | Finding | Source | Confidence |
|---|---|---|---|
| E1 | Of 1,169 tracer entries, at most 376 (32%; an upper estimate) are lane-related and 111 (9.5%) are `worktree`-model | `research/tracer-summary.md` | medium |
| E2 | Of 1,365 labelled issues, 328 (24%) are lane-related, 123 of 330 (37%) within catfooding and 94 (6.9%) `worktree`-model | `research/issue-summary.md` | medium-high |
| E3 | Lane-related PRs are 12.7% of merged PRs and 19.9% of `src/` PR churn | `research/pr-churn-summary.md` | medium |
| E4 | Six recurring mechanisms across the named issues | `research/named-examples.md` | high |
| E5 | Doctrine gives no status-surface rule and uses three worktree concepts | `research/doctrine-scan.md` | high |
| E6 | The status read path has one resolver body and at least eight wrappers; Mission worktrees have no owner after a PR landing | `research/mechanisms-and-options.md` | high |
| E7 | The integrity gates read refs, not lane checkouts | `research/mechanisms-and-options.md` section 1(iv) | high |

`research/evidence-log.csv` and `research/source-register.csv` hold the same rows in tabular
form.

### Reproducing the topology counts

```bash
python3 -c "import json,glob,collections;c=collections.Counter();[c.update([m.get('topology') or 'none']) for m in (json.load(open(p)) for p in glob.glob('kitty-specs/*/meta.json')) if m.get('created_at','')>='2026-08-06'];print(c)"
```

Output on 2026-11-06: `single_branch` 176, `lanes` 74, `coord` 53, `lanes_with_coord` 5,
none 132.

## Operator rulings (2026-11-06)

The operator ruled on all seven questions (stijn-dejongh, relayed by the dispatcher session).
See report section 5.4 for the rulings and section 5.5 for the proposed slices, which are not
yet filed.

## Open questions (as put to the operator)

Each question is for the operator; the report lists them in section 5.3.

1. Should the default topology on a protected primary change from `coord` to `single_branch`?
2. Should the coordination branch stay as the lifecycle home (#7266)?
3. Should we write a git-ref adapter ADR under ADR 2026-10-22-1 D-6?
4. Should releasing a lane checkout commit the work or refuse?
5. Who owns cleanup of a Mission's worktrees after a PR landing?
6. Should the #7264 proof-obligation ADR become the authority for destructive git operations?
