---
affected_files: []
cycle_number: 1
mission_slug: squad-doctrine-single-owner-01M3KBP7
reproduction_command:
reviewed_at: '2026-09-28T10:54:08Z'
reviewer_agent: claude
wp_id: WP02
---

# WP02 review: changes requested (reviewer-renata)

The substance is correct. The merge takes the right half of every R-7 hunk. The loader is repointed. All 17 `actions/*/guidelines.md` files are deleted. Red-first is proven: 21 tests fail at 2eb0ce69 and 56 pass at head. Two items block approval. Both are small.

## Blocking

1. **The new test file fails the repo-wide formatter gate.** `uv run --frozen ruff format --check .` on the lane reports exactly one offender across the whole repository: `tests/doctrine/missions/test_guidelines_single_owner.py` ("1 file would be reformatted, 2595 files already formatted"). The file is new and is not in the `[tool.ruff.format]` exclude ratchet. CI (`ci-quality.yml` / `ci-router.yml`) and `tests/architectural/test_ruff_format_enforcement.py` will therefore go red. The file was wrapped at about 88 columns, but the live `line-length` is 164.
   - Fix: `uv run --frozen ruff format tests/doctrine/missions/test_guidelines_single_owner.py`.
   - Do NOT add the file to the exclude list. That list is shrink-only.
   - Re-run `uv run --frozen ruff format --check .` and confirm 0 files would be reformatted.

2. **`test_review_dependency_rule_states_approved_or_done` is vacuous.** It PASSED at the red commit 2eb0ce69, when the loader still served the stale `actions/review` copy ("has been merged into the mission's target branch..."). The whole-file `"approved" in content and "done" in content` check is satisfied by the unrelated verdict line: "Approve: move WP to `approved` ... Merge later records `done`." So it does not pin the dependency rule that T006(c) asks for.
   - Fix: assert on the `## Dependency Verification` section, or on the specific line. For example, check that the line containing "`dependencies` frontmatter" contains both "`approved`" and "`done`".
   - Keep the existing "merged to main" negative assertion.

## Non-blocking (fix while you are in there)

- `tests/doctrine/missions/test_referential_integrity.py::TestGuidelinesSingleOwner::test_actions_copy_absent_mission_steps_present` duplicates guard (a) of the new test for documentation and research. The prompt asked for one guard. Consider reducing it to the "mission-steps sole owner is present" assertion only.
- `test_plan_has_no_guidelines_to_copy` still has a stale failure message: "a byte-identity copy test should be added for this step". Byte-identity no longer applies. The message should say that guidelines belong only under `mission-steps/plan/<step>/`.

## Verified OK (no action)

- Correct half taken for every hunk. `specify` and the 12 documentation/research pairs were byte-identical at base.
- No "main repository" or "inflating them with a status commit" text is served.
- `DIRECTIVE_051` is mentioned in all 3 supply-chain sections.
- The loader serves `mission-steps` for all 17 (type, action) pairs. `bootstrap_text._append_guidelines_lines` now serves the supply-chain section for implement and review.
- The org-pack overlay layout (`{pack_root}/mission-steps/<type>/<step>/`) is consistent with the new loader.
- No reader of `actions/*/guidelines.md` remains in `src/` or `tests/`.
- The absence guard fails when a copy is re-added.
- The provenance baseline only shrank. `content-manifest.json` is untouched. `regenerate-graph --check` reports the graph is fresh.
- mypy on `repository.py` is identical to base. `ruff check` is clean.
