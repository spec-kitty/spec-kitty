---
affected_files: []
cycle_number: 1
mission_slug: ci-runtime-stabilisation-01M3TZH6
reproduction_command:
reviewed_at: '2026-10-01T13:39:55Z'
reviewer_agent: claude-reviewer
wp_id: WP09
---

# WP09 review feedback — cycle 1 (reviewer-renata)

Verdict: CHANGES REQUESTED. The work is otherwise sound. Red→green is verified: at c91846ad27 the tests fail with `ModuleNotFoundError: scripts.ci.corpus_select` and on the dead `src/doctrine` cov target, and they pass at the tip. `corpus_select.py` routes through `select_gates` with no glob copy. The `--help` bare run, ruff, mypy --strict, and the pinning inventory check are all green. Job-level continue-on-error is in place, the job is out of `packs-gate.needs`, and `--deselect` drops exactly the 4 pack-manifest nodes. One blocking defect remains: the superset proof is vacuous at its last link.

## Blocking

1. **tests/architectural/test_ci_corpus_trigger_completeness.py:323 — the Packs corpus job `if:` is checked by substring only, so an inverted or narrowed trigger passes.**
   - Problem: `assert "needs.changes.outputs.corpus" in str(jobs[_CORPUS_JOB]["if"])` accepts any expression that mentions the output. I tested three mutations of `.github/workflows/packs.yml:204`, and each one passes the WP09 tests plus the whole of `tests/ci` and the implicated architectural guards (1553 passed):
     - `${{ needs.changes.outputs.built_in != 'true' && needs.changes.outputs.corpus != 'true' }}` (the job never runs on a corpus PR).
     - `${{ needs.changes.outputs.corpus == 'true' }}` (dropping `built_in`; the suite stops running on `tests/doctrine/**`- or `src/charter/offering/{schemas,drg}/**`-only PRs).
   - So FR-009's "superset trigger" is proven up to `steps.corpus.outputs.selected` but not into the job that runs the suite.
   - Required fix: pin the exact canonical expression, `jobs[_CORPUS_JOB]["if"] == "${{ needs.changes.outputs.built_in == 'true' || needs.changes.outputs.corpus == 'true' }}"`, or parse it into its disjuncts and assert both `== 'true'` disjuncts are joined by `||`. Hoist the string into a module constant, because it is reused by item 2.

2. **tests/architectural/test_ci_corpus_trigger_completeness.py:353-354 — the blocking pack-manifest guard's widened `if:` has the same substring weakness.**
   - Problem: `.github/workflows/packs.yml:189` mutated to `${{ needs.changes.outputs.built_in == 'false' && needs.changes.outputs.corpus == 'false' }}` survives. This trigger is the safety argument for deselecting the manifest test from the advisory run (DoD item 5). If it can silently invert, the deselect weakens the blocking guard.
   - Required fix: assert equality of `jobs[_MANIFEST_JOB]["if"]` with the same canonical expression as the corpus job. Equality between the two jobs is the actual invariant: the manifest guard fires on every trigger the corpus lane fires on.

## Non-blocking (consider; do not let them hold the fix)

3. `.github/workflows/packs.yml:132`: changing `"$EVENT_NAME" = "pull_request"` to anything else survives every test. The diff is then never computed and the step always fails closed to `true`. This is safe for the superset property, but it silently makes every PR run the advisory corpus suite. A one-line assertion that the run text gates the diff on `pull_request` would close it.
4. The 40 orphaned corpus tests (WP10's set) have no blocking home between this WP and WP10. This is acceptable only because WP10 (`dependencies: [WP09]`) is next in lane-h and its red-first test asserts that `corpus` leaves `_DELIBERATELY_UNGATED_FILTER_GROUPS`. Do not land WP09 alone.
5. Pre-existing and out of scope: Packs `concurrency` is `packs-${{ github.ref }}` with `cancel-in-progress: true`. A merge burst on `main` can therefore cancel the corpus run for intermediate tips. The router's push concurrency was fixed for this, and Packs is now the sole corpus owner. Worth a WP19 note.
6. Your handoff recorded the stale prose for WP19 (`.github/ci-module-registry.yml:763`, `docs/development/reference/ci-gate-mechanics.md:114`, `tests/architectural/test_same_tier_uniqueness.py` `fast-tests-corpus`). Good. The WP Activity Log itself has no implementer entries yet: no red-run record and no Packs run ID with the `created: 4/4 workers` line.
