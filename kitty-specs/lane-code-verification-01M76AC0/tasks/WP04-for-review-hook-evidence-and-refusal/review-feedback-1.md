# WP04 review feedback (cycle 1) — reviewer-renata (claude-reviewer)

Verdict: **changes requested** (one blocking finding).

## BLOCKING 1 — an undeclared gate is now refused on a foreign lane (FR-011 / C-003 / FR-008)

`src/specify_cli/cli/commands/agent/tasks_move_task_gates.py:1267-1270` checks
`inputs.probe_is_foreign` as the very first statement of
`_mt_collect_transition_gate_verdicts`, ahead of the override tier, the empty-diff arm,
the binding resolution and the `_mt_pre_review_gate_declared` check (#3821). A repository
that never declared `review.test_command` (today: one quiet `skipped` verdict, the move
applies) whose lane `.venv` points elsewhere is now REFUSED with exit 1 /
`EVIDENCE_TREE_MISMATCH`. The same happens with an empty changed-file set (today:
`no_coverage` warn, proceed) and with no active binding.

Reproduced with the WP's own `_Fixture`, foreign `.pth`, **no** `write_review_config()`:
both `changed=True` and `changed=False` raise `typer.Exit(1)` with
`error_code: EVIDENCE_TREE_MISMATCH`, no status event.

Why it is wrong: the refusal's premise (FR-008) is "the run loaded code from outside the
lane"; when the gate would run nothing there is no evidence to be foreign. FR-011 requires
existing outcomes to stay as they are, C-003 forbids reshaping the gate, and the contract
scopes evidence to "whenever the gate built an invocation" for a run.

Required fix:
- Apply the foreign short-circuit only on the paths that would actually run tests: inside
  the override tier (before `_mt_pre_review_gate_with_override_scope`), and after the
  `_mt_pre_review_gate_declared` check (just before dispatch). The empty-diff, no-binding
  and undeclared arms must return exactly what they return today.
- Make it consistent for the recorded evidence: build/probe the invocation (and record
  `evidence_tree`) only when a run tier is reached, i.e. no probe subprocess and no
  `evidence_tree` key on the `skipped` / `no_coverage` arms. This also keeps the probe cost
  (NFR-001) off every undeclared repository's `for_review` move. (If you prefer to keep
  recording evidence on those arms, say so in the WP and make sure it can never refuse —
  but "no evidence where no run" is what the contract wording supports.)
- Add tests on the same `_Fixture` with a foreign `.pth`: (a) no `review.test_command` →
  move applies, outcome `skipped`, no `EVIDENCE_TREE_MISMATCH`; (b) declared command but no
  changed files → `no_coverage`, applies. Keep the existing declared-foreign refusal as the
  positive control beside them.

## Non-blocking notes

- `evidence_tree.path` is relative (contract-conformant). `probe.origins` and
  `probe.interpreter` carry absolute machine paths into the tracked status log
  (WP01-owned; already queued as a close-out fold — no action in WP04).
- The out-of-map edit in `tasks_move_task.py` (`pre_review_lane_id` state field + two
  re-exports) is justified: the field avoids a second workspace resolution and the
  re-exports follow the module's existing re-export block. Fine.
- Positive control drift: `test_verified_tree_records_evidence_and_applies` builds the
  fixture with `changed=False`, the foreign refusal with `changed=True`. Use the same
  `changed=True` declared fixture for both (only the `.pth` target differing), so the
  verified case also reaches the dispatch tier the refusal now sits in front of.
- `# noqa: BLE001` on the fail-open `except` carries a rationale and mirrors the module's
  existing fail-open idiom; acceptable.
- What is already correct and must stay: refusal → exit 1, `transition_applied: false`, no
  status event, test command not run; `--force` → proceeds with `force_bypassed: true`
  (block on or off) and `bypassed_refusal`; `unverified` never refuses; skip flag/env var
  never probe; fail-open on invocation errors; same-fixture verified positive control.
