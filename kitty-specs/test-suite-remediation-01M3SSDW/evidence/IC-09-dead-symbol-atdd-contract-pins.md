# IC-09 — Dead-symbol ATDD pins + parity snapshot (WP10)

Materialized at closeout from WP10's reported evidence (scratchpad `WP10-evidence.md`, which
was already written in data-model §4 record form) and the reviewer's full approval note
(`status.events.jsonl`, `review_ref: auto-approval:WP10:20260930`). Lane commit `5528599b9e`
(lane-j). `git diff --stat src/` was empty at commit.

```yaml
id: EV-IC09-01
item: FR-009 ATDD contract (contracts/dead-symbol-allowlist.md §3 M1, M7, M8, M11)
kind: FIX
planted_break:
  target: "tests/architectural/test_dead_symbol_allowlist_contract.py (seam absent today; plus scratch stubs of tests/architectural/_dead_symbol_allowlist.py, never committed)"
  description: >
    The ATDD red is the missing seam itself. Every test is xfail(strict=True, raises=(ImportError, AttributeError)).
    Harness non-vacuity plants on an untracked scratch file tests/architectural/_dead_symbol_allowlist.py:
    (i) an empty stub module, which simulates WP11 landing without WP12;
    (ii) a stub that raises ValueError at import (a wrong-reason failure).
    Both were removed (rm) and are absent from git status.
  reverted: true
command: >
  uv run --frozen pytest tests/architectural/test_dead_symbol_allowlist_contract.py --collect-only -q ;
  uv run --frozen pytest tests/architectural/test_dead_symbol_allowlist_contract.py -n0 -q -rxX ;
  uv run --frozen pytest tests/architectural/test_dead_symbol_allowlist_contract.py -n0 -q --runxfail
results:
  collect_only: "4 tests collected, 0 errors"
  strict_xfail_run: "4 xfailed (M1, M7, M8, M11 each XFAIL - pending the dead-symbol re-key (WP12, #5346))"
  runxfail_today: >
    4 failed, each with: E   ModuleNotFoundError: No module named 'tests.architectural._dead_symbol_allowlist'
    (test_m1_body_edit_of_allowlisted_dead_symbol_stays_green, test_m7_rename_reports_gone_and_new_offender,
    test_m8_move_reports_gone_with_moved_hint_and_new_offender, test_m11_gate_reads_the_allowlist_file_it_is_given)
  stub_i_empty_loader: "-rxX: 4 xfailed; --runxfail: 4 failed, each with E   AttributeError: _evaluate_allowlist (the WP11->WP12 red stage)"
  stub_ii_wrong_reason_ValueError: "-rxX: 4 FAILED (E   ValueError: wrong-reason plant), not XFAIL, so raises= discriminates"
  old_form_under_break: "n/a (new file)"
  new_form_under_break: "fail (under --runxfail, on the missing seam)"
  clean_tree: "xfail (strict), 4/4 at HEAD 5528599b9e"
counts: {executed_before: null, executed_after: null}
reviewer_rerun: true
notes: >
  Reviewer re-run (approval note, auto-approval:WP10:20260930): "-rxX 4 xfailed; --runxfail 4
  failed ModuleNotFoundError" — exactly this record's strict-xfail and --runxfail progression,
  reproduced independently. "M1 same-fixture positive control; M11(a) >=2-entry category; seam
  API exact" confirm the positive-controls claim below. Tallied in evidence/README.md.
  Positive controls: M1 (same fixture vs allowlist [(pkg.m, Other)] -> offenders ==
  ['pkg.m::Baz'] for each of 4 bodies); M11 (real load_allowlist() over real inputs ->
  offenders == [] and stale == [] before arms a/b). Fixture sanity: the synthetic corpus fed
  through today's production _compute_offenders resolves the synthetic modules correctly.
  Quality: ruff check / ruff format --check / mypy (strict) all clean, 0 new noqa/type:ignore.
  The seam is loaded via importlib inside _seam(), so there is no module-scope import of the
  absent modules (collection-clean, mypy-clean). No SymbolKey, body hash or tier appears in
  the file.
```

```yaml
id: EV-IC09-02
item: "SC-003 real-tree red observation (a body edit of an allowlisted dead symbol reds today's gate)"
kind: FIX
planted_break:
  target: "src/specify_cli/status/lifecycle_events.py::append_lifecycle_event::rename local `envelope` -> `persisted_envelope` (lines 631, 643, 644 x2, 645; 4 code-token sites, docstring untouched)"
  description: "a behaviour-neutral code-token body edit (it changes the content-tier hash; not a docstring/comment edit)"
  reverted: true   # git checkout -- src/specify_cli/status/lifecycle_events.py ; git diff --stat src/ -> empty
command: "uv run --frozen pytest tests/architectural/test_no_dead_symbols.py -n0 -q -k test_no_public_symbol_in_all_is_unimported"
results:
  old_form_under_break: >
    fail: 1 failed, 34 deselected in 37.68s.
    tests/architectural/test_no_dead_symbols.py:3917 AssertionError: Symbol-level dead-code gate FAILED (#470 ...)
    - specify_cli.status.lifecycle_events::append_lifecycle_event
  new_form_under_break: "pending: WP12 re-runs the same plant against the (module, name) gate and must show GREEN"
  clean_tree: "pass: 1 passed, 34 deselected in 36.60s (after revert)"
  full_gate_file_clean: "uv run --frozen pytest tests/architectural/test_no_dead_symbols.py -n0 -q -> 35 passed in 114.42s"
counts: {executed_before: null, executed_after: null}
reviewer_rerun: true
notes: >
  Reviewer re-run (approval note): "SC-003 plant (envelope->persisted_envelope in
  append_lifecycle_event) RED with exactly that offender -> revert GREEN, src clean" — exactly
  this record's planted break, reproduced independently and reverted clean. append_lifecycle_event
  is allowlisted: before.json row [specify_cli.status.lifecycle_events, append_lifecycle_event,
  category_a_slice_f_deferred]. The 'new_form_under_break: pending' line is resolved by WP12's
  EV-IC10b-02, which reruns this exact plant against the re-keyed gate and records
  new_form_under_break: pass. Tallied in evidence/README.md.
```

```yaml
id: EV-IC09-03
item: "dead-symbol parity snapshot before.json (contract §4 step 1; data-model §1.7)"
kind: KEEP
command: "PYTHONPATH=. uv run --frozen python <scratchpad>/parity_before.py > <scratchpad>/before.json   (from lane-j worktree root)"
base_sha: "68f7418bb4c55888d06b05b7785aaf62a0a1d9dc"   # lane-j HEAD at snapshot (merge of the mission branch into lane-j); src/ identical at 5528599b9e
counts: {allowlist: 293, widened_470: 91}
offenders: []
stale: []   # stale + dangling + widened_stale, all empty
parity_digest_sha256: "c86703f3d8904b128cfb823e043915971298eb892995ad708bb2ea35707607a1"
before_json_file_sha256: "30e9c0491f295bb468fbf8b5e612f038651cdf50ad63a6d9ac9178b1deccf139"   # 1842 lines, sort_keys=True, indent=2
script_file_sha256: "fecc8cbeba5f922c2f5d473d88976047489bdbe318de31858685e31f095f6baf"
reviewer_rerun: true
notes: >
  Reviewer re-run (approval note): "parity 293/91 digest c86703f3...07a1 reproduced
  independently" — the digest and counts reproduced a second time by the reviewer, matching
  this record's values exactly. (`kind: KEEP` — not counted toward the SC-005 FIX/RETIRE
  tally, but the independent reproduction is recorded for completeness.) Committed at closeout
  as evidence/dead-symbol-parity/before.json (see that directory's README.md).
```

## Tests run (lane tip `5528599b9e`)

- `uv run --frozen pytest tests/architectural/test_dead_symbol_allowlist_loader.py tests/architectural/test_ratchet_positional_anchor_ban.py tests/architectural/test_no_dead_symbols.py -n0 -q` -> 197 passed
- `uv run --frozen pytest tests/architectural/test_dead_symbol_allowlist_contract.py -n0 -q` -> 4 xfailed (strict; --runxfail: 4 x AttributeError: _evaluate_allowlist)
- `ruff check` / `ruff format --check` / `mypy` on the 2 owned files -> 0 findings (C901 clean)
- `make test-fast` -> 2169 passed, 5 skipped
- `git diff --stat src/` empty before every commit
