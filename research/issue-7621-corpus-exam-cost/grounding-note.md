# Grounding note: #7621, the `corpus_exam` fixture time budget

> Op `01M7B17EJ58V9A9G7YEH9QNPJH` (profile `python-pedro`). Date: 2026-11-13.
> Branch: `test/7621-corpus-exam-fingerprint-cost`. Kind: test quality (cut the cost; no retry,
> no budget change, no floor change).

## 1. What the nightly reported

`interpreter-3.13-shard-4` (run 43358577485) failed the eight tests of
`tests/contract/test_mission_status_reality.py` that use the module-scoped `corpus_exam` fixture.
Each failed on setup with `Timeout (>240.0s)`, the suite-wide `pytest-timeout` backstop. The
fixture set up in 171 s on run 97 and went over 240 s on run 98, while the corpus grew by less
than 1 %. The margin was already thin, and a slower shared runner was enough to cross it.

## 2. The triage hypothesis, checked against a measurement

The triage finding said the cost was the two `tree_fingerprint` passes over about 25.8k files.
I measured it; **the hypothesis does not hold**:

| What | Measured (this host, 4 cores) |
|---|---|
| `tree_fingerprint(REPO_ROOT, "kitty-specs")`, cold | 3.45 s (25,994 files, 5,711 directories) |
| the same, warm | 1.01 s |
| `corpus_exam` setup, whole module, Python 3.13, `-n auto --dist loadfile` | **189.03 s** |

The two passes cost 2 to 5 s of 189 s. Cutting them to one would buy about 1 % and would also
weaken the proof: the `before`/`after` pair brackets the exam itself, and that is what
`test_the_new_readers_leave_the_corpus_tree_as_they_found_it` reads.

## 3. Where the time actually goes

`cProfile` of the fixture alone (profiled seconds are about 2.2 times real for Python-heavy
work; `corpus_exam` was 424 s profiled):

| Cost | Profiled | Calls | Why |
|---|---|---|---|
| `read_authored_wp_frontmatter` (ruamel YAML) | 136 s | 8,314 | every `tasks/WP*.md` parsed **twice**: by the detail reader's `index_work_packages` (72 s) and by the v1 control's `read_authored_files` (68 s) |
| `reconstruct_wp_view` → `wp_snapshot_state` | 45.6 s | 8,297 | built **twice** per work package with the same arguments (detail `_assemble` and v1 `build_work_package`); each call re-reads and re-reduces the Mission's whole event log |
| `load_source` | 42.6 s | 840 | includes 42 real `git ls-remote` probes, 0.45 s each |
| listing and content reads, redaction, leak scans | ~115 s | 23,348 entries | the artifact reader under test |
| independent scans (the oracle side) | ~40 s | | must stay independent |

The per-Mission cases earlier in the same module (`_run_case`) already parse every work package
file and build every work package view through the same two names, for every Mission. Under
`--dist loadfile` the module runs in one process in definition order, so by the time
`corpus_exam` runs, each of those answers has already been computed once or twice.

## 4. The fix

One module-scoped autouse fixture, `work_package_reads_are_shared`, beside the existing
`identity_index_is_walked_once`, and on the same ground: both reads are pure functions of the
files, and the read-only fingerprint fixture proves the tree is unchanged for the whole module.

- It patches only the names bound in the two test-side reader modules
  (`_mission_status_detail`, `_mission_status_payloads`). Production modules are untouched, and so
  is the timed resolver run (`execute_corpus_run` reads through `drift` and the `Project`
  builder, not through these names).
- Every file is still parsed, and every view still built, by the production function, once.
- A failed parse is never kept; it raises again on the next call.
- A planted repository (under pytest's base temp directory) is always read fresh, so every
  control and mutation test that edits a planted file still sees the edit.
- A view is reused only for metadata equal to the metadata it was built from.

`MissionSource` (from `load_source`) is a mutable dataclass, so it is **not** shared. The 42
remote probes stay; they are part of what the resolver does.

Nothing the fixture proves is weakened: every exam check, every floor, the pinned anomaly
fixture and both fingerprints run unchanged. No timeout and no floor is changed.

## 5. Similar surfaces

| Surface | Pattern | Risk |
|---|---|---|
| `kitty_specs_is_left_untouched` (module, autouse) | two fingerprints | about 2 to 5 s, no risk |
| `tree_problems` (Ops walk test) | two fingerprints per tree, `kitty-specs` and `kitty-ops` | about 5 s, no risk |
| `test_mission_status_drift.py:1472` | fingerprints of a planted repository | small tree, no risk |
| `corpus_run` (`execute_corpus_run`) | timed resolver run; 74 s setup locally | under budget; it is timed cold on purpose, so it is not memoised |

No other fixture uses the fingerprint at a cost that matters. The cost driver was duplicated
per-work-package parsing, which only this module's exam does at corpus scale.

## 6. Tracked issues, dispositioned

| Issue | Relation | Disposition |
|---|---|---|
| #7621 | this one | closed by this change |
| #5927 (open, P2) | same file, older environment-dependent red: 240 s timeouts, `KeyError 'findings'`, drift read 500 | related, not closed: this change cuts the exam's time but does not touch the drift read or the envelope |
| #7622 (open) | sibling nightly shard (3.13 shard 3) | unrelated: a `decide_next` stub, PR #7635 |
| #7341 (closed) | earlier shard-4 red | unrelated: a `SimpleNamespace` stand-in, fixed by #7364 |
| #7052 (closed) | same class (fixture at the 240 s backstop) | precedent: there the cost was irreducible and the budget was tuned with evidence; here the cost was avoidable, so it is cut instead |

## 7. Measured result

`uv run --python 3.13 pytest tests/contract/test_mission_status_reality.py -n auto --dist loadfile --durations=10`,
same host (4 cores), two interleaved pairs. Pair 2 swapped only this test file between the base
and the branch:

| Pair | `corpus_exam` setup before | after | change |
|---|---|---|---|
| 1 | 189.03 s | 141.27 s | -25 % |
| 2 | 184.73 s | 139.20 s | -25 % |

The setup of the other heavy module fixture (`corpus_run`, the timed resolver run) is unchanged
(71 to 74 s), as intended. Whole-module wall clock is noisy on this shared host (379 s and 427 s
in pair 2) and is not the claim. CI ran the same setup about 10 % faster than this host before
the change (171 s against 189 s), so a typical nightly should set up in about 125 s, against
the 240 s budget.

What remains (module order, profiled): the artifact reader under test and the leak scan of every
envelope (the pinned contract tool's regular expressions are about a third of all time), the
detail reader under test, and the independent scans the exam compares them with. Cutting any
of those would weaken what the fixture proves, so the change stops here.

Environmental note for anyone reproducing locally: running `spec-kitty dispatch` in the checkout
writes a gitignored `kitty-ops/ops-index.jsonl` that names only the new Op, and four
`test_corpus_ops_*` cases then fail (they read the index). They pass with that local file moved
aside, and CI never has it. This is not caused by this change.
