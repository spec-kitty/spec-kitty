---
affected_files: []
cycle_number: 1
mission_slug: mixed-lane-authorship-soundness-01M3M7Y0
reproduction_command:
reviewed_at: '2026-09-28T16:24:50Z'
reviewer_agent: claude
wp_id: WP03
---

# WP03 review feedback (reviewer-renata) — cycle 1

Overall: the design is sound and close to approvable. Pipeline purity holds (no git/subprocess in
`transition_pipeline.py`; `lane_head_probe=None` = no stamp; byte-identity test green), all four call
sites inject `probe_lane_head`, the probe is correct (live-probed against this very mission: WP01/WP03/WP07
resolve to their lane tips, WP99 -> None, mid8 handle and a lane-worktree repo_root both resolve), and
claim keys are preserved. 433 targeted tests + 9 architectural gates pass. Rejecting for the items below
(two are policy-blocking, all are small).

**Issue 1 (MEDIUM, blocking — spec deviation in the pin, T013):** `test_every_prepare_transition_call_site_passes_probe_lane_head`
only parses `status/emit.py` and `coordination/status_transition.py`. T013 requires "every
`prepare_transition(...)` call in `src/specify_cli/`". A fifth caller added in any other module
(or a call through an attribute, e.g. `_pipeline.prepare_transition(...)`, which `_prepare_transition_calls`
ignores because it only matches `ast.Name`) would escape the pin entirely, and the `== 4` floor would
still pass. Fix: walk every `*.py` under `src/specify_cli/` (skip `transition_pipeline.py`'s own `def`),
match both `ast.Name` and `ast.Attribute` with attr `prepare_transition`, and keep the floor at 4 over
that whole-tree count. Add a self-mutation case for the attribute-call form.

**Issue 2 (MEDIUM, blocking per CLAUDE.md "new code MUST pass mypy with zero issues"):** new code
`src/specify_cli/status/emit.py:721` (`_repo_root_for_lane_head`, `return resolve_canonical_root(feature_dir)`)
raises `no-any-return` under `mypy src/specify_cli/status/emit.py` (not present at base; the 3
`status_transition.py` errors are pre-existing). Fix exactly as the sibling
`coordination/status_transition.py::_repo_root_for_feature` does: `canonical: Path = resolve_canonical_root(feature_dir)`
then `return canonical`. Add `emit.py` to your mypy check list.

**Issue 3 (LOW — T015 incompleteness):** `test_transactional_shell_stamps_lane_head` asserts only on the
returned event. T015 asks for the *persisted* event read back with `read_events` for the transactional
shell too, and for claim `policy_metadata` preservation alongside the stamp. Read the coord-branch log back
(e.g. via a coord worktree / `git show <coord>:kitty-specs/<dir>/status.events.jsonl` parsed through the store,
or the store reader on the coord worktree) and pass `policy_metadata=build_claim_policy_metadata(...)` there as well.

**Issue 4 (LOW — avoidable cast):** the `typing.cast` in `_stamped_policy_metadata` is justified in its
comment but not necessary: an annotated local (`request_policy_metadata: dict[str, Any] | None = request.policy_metadata`)
satisfies mypy without a cast (same idiom as Issue 2), drops the `cast` import, and lets the 12-line
rationale comment shrink to nothing. Prefer it.

**Issue 5 (LOW — cutover campsite accuracy):** (a) the rewritten docstring still says "the only transitions
that carry those keys are real `planned -> claimed` claims" — false: `tasks_move_task._mt_approval_policy_metadata`
puts `shell_pid` on APPROVED/DONE hops. Correct the sentence. (b) Note in the docstring/PR that the re-key also
(intentionally?) stops counting `pre_review_gate`-only, approval `tool/profile/model`-only and
`migration_original_actor`-only metadata as runtime evidence — a deliberate narrowing beyond `lane_head`; state it
or switch to "any key other than `lane_head`" if the broader narrowing is not intended. `test_dogfood_corpus_backfilled.py`
and `test_accept_birth_cutover.py` stay green either way. (c) The new `return any(...)` line is not
`ruff format`-clean; the file was already unformatted at base — campsite it with `ruff format` on the file.

Coordination note: WP04/WP06 depend on WP03 (`LANE_HEAD_KEY` facade export is correct and should not change).
