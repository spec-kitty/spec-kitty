# S7: initial QA installation-scenario drafts

Audience: QA and core reviewers binding the converted scenarios. This is a migration handoff,
not a promise ledger or a coverage claim. Updated: 2026-10-18.

Refs: [spec-kitty-qa#783](https://github.com/spec-kitty/spec-kitty-qa/issues/783), with the broader
promise-discovery work in [spec-kitty-qa#801](https://github.com/spec-kitty/spec-kitty-qa/issues/801).

## Source and destination

Converted with QA's existing `scripts/scenario_md_to_feature.py` from QA commit
[`dfd99c0e07a7dfd4d06580daf2a41efeaa706b8f`](https://github.com/spec-kitty/spec-kitty-qa/tree/dfd99c0e07a7dfd4d06580daf2a41efeaa706b8f/scenarios/spec-kitty/a-cli).
The source pages and their Python executors remain in QA until the later retirement step. All three drafts retain their
original `@qa` identity and carry `@wip`, owner and date. No promise ID is generated.

| QA page under `scenarios/spec-kitty/a-cli/` | Core draft | Distinct assertion to preserve |
| --- | --- | --- |
| `SC-A-004-unknown-command-clean-error.md` | `cli/sc-a-004-unknown-command-clean-error.feature` | An unknown root command exits 2 without a Python traceback. This is CLI admission, not init, despite QA's installation-area classification. |
| `SC-A-006-init-idempotent.md` | `init/sc-a-006-init-idempotent.feature` | Re-init preserves an **operator-edited parsed config mapping**. Compare with the existing init repair/preservation scenario; deliberate customization is the additional condition. Parsed equality is not byte equality. |
| `SC-A-013-init-invalid-ai-atomic-reject.md` | `init/sc-a-013-init-invalid-ai-atomic-reject.feature` | Invalid assistant input fails without creating `.kittify/`, while a valid-assistant control creates the config in a sibling directory. |

The converted source carries the QA page's preconditions and oracles as maintainer comments.
Preserve the isolated runtime, no-project controls and both sides of SC-A-013 when binding.

## Review before promotion or retirement

1. Reuse existing acceptance steps where they assert the same thing; bind any missing vocabulary
   through the acceptance driver. A textual conversion is not a bound test or a passing run.
2. Compare each draft's assertions and conditions with existing core scenarios. Consolidate
   equivalent behavior only after review; similar titles are not equivalence. In particular,
   SC-A-006 must not be used to claim PP-0001's stronger byte-preservation check.
3. QA and core review the binding and positive controls before removing WIP. Only a person adds
   `@promise` tags after the corresponding promise/claim review.
4. Re-vendor the merged, non-WIP, non-on-demand scenarios into QA. Unbind each old automatic
   executor in a separate reviewed change, then use S7's `retire` operation to write `moved_to`
   and re-point mappings as proposals. Do not retire a QA page to one of these WIP drafts.

No manual QA page, existing core scenario or engineering test is retired here. No absorption-ledger
row is needed because no test is deleted. The manual charter portfolio stays in QA: its
config-only, diagnostic and authoring controls must be compared with the charter consumer-outcome
scenarios, not blindly copied or discarded. The activation suite's promise ratification remains
spec-kitty-qa#801's separate work.
