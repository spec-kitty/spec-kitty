# WP16 review feedback (cycle 1): changes requested — one MEDIUM finding, everything else verified green

Reviewer: claude:claude-sonnet-5-5:reviewer-renata. Lane commits reviewed: 09c8f576d8 (red), f641f5599f (fix), base efde6109dd.

## What I verified (all pass)

- Red-first is real. In a detached worktree at 09c8f576d8, `test_history_read_error_refuses_the_claim_and_moves_nothing` fails with
  `AssertionError: 'a git probe failed while building the approved-WP claim' not in "<consolidate output>"` (1 failed, 2 passed; both
  genuine-deletion controls pass). It fails for the stated reason, not a fixture error. The temporary worktree was removed.
- Pin (d) `test_history_read_error_refuses_instead_of_deleting` is no longer xfail and passes: exit 1, probe message, the path in the
  output, `ref_shas` unchanged, reflogs unchanged, no `pre_mutation_refs`. All other WP05 pins still XFAIL: `7 passed, 10 xfailed`, no XPASS.
- `changed_cells('efde6109dd') == ['fresh|single_lane|stamp=present|window=recorded|history_read_error']` (fail/unattributable_blobs -> refuse).
  The golden diff is exactly that one cell, made through `regenerate_cells`.
- The fix is fail-closed. The only `try/except` in `_final_authored_walk` re-raises `GitProbeError` (path and commit named, `from exc`); nothing else is
  caught. Every caller propagates it. Claim, forecast and `_verify_declared_ref` (-> `_REFUSE_DEPENDENCY_PROBE`) use their existing
  probe-error channels. No new refusal code or wording, no new handler, one read per path, one spine walk.
- Out-of-map edit (1), `characterization_support._fault_history_read_error`: I traced `GitProbeError("injected …")` over the cell.
  It fires exactly once, from `_failing` inside `_final_authored_walk` (stack: build_claim > build_approved_wp_set > _collect_authored >
  _final_authored_walk > _failing). It fires only for `(authored_sha, WP01_PATH)` and never in a gate read. Accepted.
- WP03 refusal matrix unchanged and green. The refusal is raised at the same claim-time probe point, so no precedence row is affected.
- Targeted runs: test_reconciliation_characterization, test_reconciliation, test_presence_lane_base, test_dependency_ref_claim,
  test_approved_content_presence, test_git_probes_seam, surface_pin, family_guard, refusal_precedence_matrix, single_rollback_authority:
  394 passed, 1 xfailed (the pre-existing strict #5051 3-way-merge xfail). Seeded mutations: 23 passed, twice.
- ruff check / ruff format --check --force-exclude / C901 are clean on all five touched files. No `noqa` or `type: ignore` added.
- The two mypy errors (reconciliation_authorship.py:132 `no-any-return`, test_reconciliation_intended_verdicts.py:136 `WP_WINDOW_KEY`
  not exported) are PRE-EXISTING: identical output at efde6109dd in a detached worktree, and neither line is in this diff. Not WP16's.
- Tracer: design-decisions.md carries the red evidence, the fix, the key, and the Before/After sentence for WP21's fragment.

## Finding (MEDIUM) — removing the (d) witness leaves the new refusal with no seeded-mutation guard

`tests/consolidation/test_reconciliation_seeded_mutations.py`: the (d) cell is dropped from the `kernel-bookkeeping` row. That is correct for that row,
because the cell now refuses at claim time before any content judgement, so it cannot flip under `_is_bookkeeping`. But it leaves the WP06
harness (NFR-008, SC-005: every behaviour the corpus pins must turn a cell red when weakened) with no row that reverts the read-error refusal.
The existing `authorship` row cannot reach it, because it wraps the real walk and only strips blobs from its result. The implementer's tracer note
says "a regression is caught by the pin and the unit test, not by a seeded mutation". That is true but is exactly the coverage gap the
harness exists to close. Not genuinely unnecessary.

Required: add one extra row (a non-PHASE3 row like `-strict` / `-exemption`; `PHASE3_CHECKS` and `len == 16` stay untouched), e.g. check id
`authorship-read-error`, target `_final_authored_walk`, mutation "an unreadable history path is recorded as a deletion again (the pre-WP16 behaviour)",
expected red cell `fresh|single_lane|stamp=present|window=recorded|history_read_error` (`cs.NAMED_KEYS["d_history_read_error"]`; the
`_HISTORY_READ_ERROR` constant you removed). Keep the module docstring's two tables (check/target/mutation, and the expected-red-cells block) in
agreement with the new row, because `test_docstring_table_matches_mutations` parses both.

Ordering trap: the corpus fault installs its own `path_state_at` fake via `setattr_reconciliation_family` AFTER the row's `apply()` ran, and that
overwrites any plain `path_state_at` patch. So the mutation must act at call time. I prototyped this and checked it (scratch script, nothing committed):

```python
import specify_cli.consolidation.reconciliation_authorship as _authorship   # or via family_modules_binding

def _mutate_authorship_read_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """An unreadable history path is a deletion again: the pre-WP16 behaviour (#5048(b))."""
    real_walk = _real("_final_authored_walk")

    def _walk_that_reads_errors_as_deletions(*args: Any, **kwargs: Any) -> Any:
        installed = _authorship.path_state_at  # whatever is bound NOW (the corpus fault's fake)

        def _swallow(repo_root: Path, ref: str, path: str) -> str | None:
            try:
                return installed(repo_root, ref, path)
            except GitProbeError:
                return None

        with pytest.MonkeyPatch.context() as inner:
            inner.setattr(_authorship, "path_state_at", _swallow)
            return real_walk(*args, **kwargs)

    _patch_function(monkeypatch, "_final_authored_walk", _walk_that_reads_errors_as_deletions)
```

Result with this mutation: the (d) cell recomputes to `{'status': 'fail', 'exit_code': 1, 'divergence_fields': ['unattributable_blobs']}`, which differs from
the golden `refuse`. Without it the cell equals golden. (Add `from specify_cli.consolidation.git_probes import GitProbeError` and the module import;
use `_ROW_WORKERS` forking as the other rows do — the patch is inherited.) Then confirm `test_every_row_has_a_real_target_and_cells`,
`test_docstring_table_matches_mutations`, `test_unmutated_cells_match_golden` and the new row pass, and run the file twice.

## Low notes (non-blocking, no action required for approval)

- [LOW] closed-world declared-ref path: a read error in `_verify_declared_ref`'s walk now surfaces as `DEPENDENCY_REF_UNVERIFIABLE` (previously a silent
  deletion). That is the intended fail-closed behaviour but no test pins it. A one-line follow-up test would close it; WP21/PR notes can mention it.
- [LOW] forecast mode: the same refusal shows through the forecast's "closed-world window could not be read" text; unpinned for this cause.
- [INFO] The mypy errors above should be a campsite item for the mission owner, not for this WP.

Scope note: edits to `characterization_support.py` and `test_reconciliation_seeded_mutations.py` are outside `owned_files` but forced by the (d) flip,
and are accepted as sanctioned (like WP12's). The new row belongs in the same out-of-map file; record it in the tracer.
