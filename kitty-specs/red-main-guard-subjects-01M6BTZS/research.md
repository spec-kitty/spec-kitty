# Discovery — #6997 pre-existing red: two `tests/contract` guards

Mission: `red-main-guard-subjects-01M6BTZS`
Base: `origin/main` @ `287a226cfe` (clone `/home/exedev/work/sk-6997`), branch
`issue-6997-red-main-guard-subjects`.

## Reproduction (base commit, before any change)

Command, exactly as the issue invokes it (plus the repo's `uv run` for the venv):

```
uv run python -m pytest \
  "tests/contract/test_terminology_guards.py::test_no_main_branch_workflow_language_in_live_docs_and_skills" \
  "tests/contract/test_orchestrator_api.py::TestAllowedErrorCodes::test_safe_commit_failure_codes_are_contract_allowed" -q
```

Result: `2 failed in 152.97s`.

1. `Failed: docs/development/how-to/unclog-ci.md:95: teaches deprecated main-centric
   workflow wording.`
   The offending text is `Every GitHub PR merge to ` + "`main`" + ` starts a new wave.`
   — a descriptive sentence about where the CI wave comes from, caught by the
   forbidden pattern ``merge to `main` ``.
2. `AssertionError: Extra items in the left set: 'SAFE_COMMIT_DIRECTORY_ARGUMENT'`
   `SafeCommitDirectoryArgument.error_code` is emitted by
   `src/specify_cli/git/commit_helpers.py:403` but absent from
   `orchestrator_api.allowed_error_codes`.

## Decisions

### D-1 — Fix the guard's subject, never the guard

Both reds are the guard doing its job on a piece of state that is wrong. The
forbidden-pattern tuple in `test_no_main_branch_workflow_language_in_live_docs_and_skills`
and the code-walk in `test_safe_commit_failure_codes_are_contract_allowed` stay
byte-identical. No `skip`, `xfail`, `-k`, scope exemption or narrower glob.

### D-2 — Reword the page, keep the fact

The page's claim is true and useful: a PR landing on the trunk causes a new CI wave.
The deprecated phrasing is what must go, because in this repo ``merge to `main` `` is
the imperative form the branch-intent governance retired (charter, "Branch-Intent
Terminology Governance"; the guard arrived in `fd9965fca8`, "Clarify branch intent
across docs and prompts"). Rewrite the sentence so the trunk-merge fact survives
without the instruction-shaped wording, staying inside the page's 100-column wrap so
the diff is a wording change, not a reflow.

Evidence for the pattern's intent: `fd9965fca8` rewrote every live docs occurrence of
the same family (`planning happens in main`, `merge to ` + "`main`" + ``, `run from the
main repository root`) into explicit branch-intent language, and created
`docs/how-to/keep-main-clean.md` to separate "repository root checkout" from "target
branch". The remaining live hits are: `docs/adr/**` (exempt archive roots) and this
one page.

### D-3 — Register `SAFE_COMMIT_DIRECTORY_ARGUMENT` on the four surfaces the last
registration touched

Precedent `46f37835ca` ("register the three new safe-commit error codes in the
orchestrator contract", #5443) added `SAFE_COMMIT_PATH_LOOP`,
`SAFE_COMMIT_INDEX_DELETION_CONFLICT`, `SAFE_COMMIT_INDEX_RESIDUE` to:

- `src/specify_cli/core/upstream_contract.json` (`orchestrator_api.allowed_error_codes`)
- `docs/contracts/upstream-3.0.0-shape.json` (the pinned planning copy)
- `docs/api/orchestrator-api.md` (the running error-code list)
- `src/charter/offering/skills/spec-kitty-orchestrator-api-operator/references/orchestrator-api-contract.md`
  (the operator skill's error-code table)
- plus `docs/changelog/CHANGELOG.md`

This mission does the same for the one missing code, and additionally names it in the
contract test's explicit code list (as #5443 did for its three) so the regression is
readable at the assertion, not only through the descendant walk.

`SAFE_COMMIT_DIRECTORY_ARGUMENT` is a pre-mutation refusal — `preflight_commit`
raises it before HEAD, refs or the index move — so it must NOT be described as a
`SAFE_COMMIT_RECOVERY_FAILED` refinement. Its `data` carries `offending_path`.

### D-4 — Do not touch the byte-frozen archive or repoint the pin

`tests/specify_cli/core/test_contract_gate.py::test_vendored_contract_matches_planning_artifact`
pins `docs/contracts/upstream-3.0.0-shape.json`; the mission-064 copy under
`kitty-specs/` is byte-frozen by `tests/architectural/test_archive_root_byte_identical.py`
(SK-154) and stays untouched.

## Evidence gathered

- `git log -S` finds no commit that adds `SAFE_COMMIT_DIRECTORY_ARGUMENT` to either
  contract copy; the omission came in with the #6750 fix (contract text is in
  `docs/changelog/CHANGELOG.md` under the #6870/#6750 entry, which names the code but
  never registered it).
- A script walk over `src/specify_cli/git/commit_helpers.py` `error_code` literals
  against `allowed_error_codes` yields exactly one missing code:
  `SAFE_COMMIT_DIRECTORY_ARGUMENT` (15 literal codes, 14 registered).
- `docs/api/orchestrator-api.md`'s bullet list already omits the code; the operator
  skill table omits it too. Both are the prose mirrors #5443 maintained.
- `grep` for the forbidden patterns over live docs finds only
  `docs/development/how-to/unclog-ci.md:95` outside the exempt ADR roots.

## Open questions (resolved by scoping out)

- Should the `tests/contract` shard run in `make test-fast`? That is why both reds sat
  unnoticed. Out of scope: a CI-budget decision for the operator → PR `## Deferred`.
- Should the docs/skill error-code enumerations be machine-checked against the
  contract? Today `docs/api/orchestrator-api.md`'s bullet list omits 22 registered
  codes that appear in prose form elsewhere (the `DESIGN_*` family, `RUNTIME_*`), so
  a parity gate is a docs restructuring, not a bug fix → PR `## Deferred`.
