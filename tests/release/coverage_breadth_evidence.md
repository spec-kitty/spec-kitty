# Coverage-breadth evidence — WP01


> **Slice-count footnote (#4334, added at consolidation).** Every figure in this document was
> measured against the **34** matrix leaves that existed in lane-b. The shipped registry has **36**:
> WP02 (lane-a) added `unit` and `specify_cli_runtime`, and the two lanes never shared a tree until
> consolidation. The table is deliberately **not** recomputed. Naively re-applying the flat
> +16.21 s/slice average at 36 would understate the margin, because those two slices run 4.7 s and
> 14.2 s respectively — their actual breadth overhead is ≈2.2 s, not 32.4 s. The conclusion is
> unchanged; only the denominator moved.

**Mission** `sonar-per-pr-coverage-reuse-01M2FR32` · **WP01** · FR-013 / FR-016 / NFR-002 / NFR-009
· measured 2026-09-14 at `576801bc0249171bb037e4ccdc5ccbe66c186ba7`
(branch `kitty/mission-sonar-per-pr-coverage-reuse-01M2FR32-lane-a`).

Machine-readable companion: [`coverage_breadth_baseline.json`](coverage_breadth_baseline.json).
Every number below cites either a run id, or a command you can re-run.

---

## BLUF

| | |
|---|---|
| Breadth fix works | one slice recovers **+30,226** covered statements that the narrow `--cov` was dropping (target: ≥2,808) |
| Per-file regressions from breadth | **zero** — measured, and true by construction (below) |
| Aggregate runner-minute cost | **+9.2 min** at the locally measured rate; **+19.1 min** projected at CI speed |
| Aggregate saving | **22.5 min** median (population 12.8–23.3 min, n=12) |
| Net | **positive in the central case** (+3.4 min at the CI projection, +13.3 min at the local rate) — but the margin is thin and the pessimistic corner is net-negative. See the **finding** below. |
| Artefact bytes | 29.8 MB → **166 MB** (×5.6) |
| Downstream parse | ~1.0 s → **6.5 s** (measured; negligible against minutes) |

---

## 1. Red-first evidence (T001 → T002)

T001 was written and run **before** the workflow changed. Both assertions failed on the unchanged
tree, naming the per-module derivation as the reason:

```
$ .venv/bin/python -m pytest tests/architectural/test_coverage_breadth.py -q \
    -k "full_top_level or vary_per_matrix"
FF                                                                       [100%]
___________ test_every_shard_measures_the_full_top_level_package_set ___________
E   AssertionError: .github/workflows/module-tests.yml's 'pytest-run' step does not derive its
    coverage targets from the source tree (no <<'COV_PY' program found).
E     It still builds one --cov flag per entry of the per-module `inputs.cov_target`, so each
      slice measures ONLY its own module's package and every line it executes outside that
      package is DROPPED from the report (coverage.py does not record it as zero — it records
      nothing at all).
E     See mission sonar-per-pr-coverage-reuse-01M2FR32 WP01 / FR-013.
______________ test_coverage_targets_cannot_vary_per_matrix_input ______________
E   AssertionError: (same)
2 failed, 3 deselected in 0.41s
```

After T002 (`module-tests.yml` only): `3 passed, 2 deselected`.

**Integration check — the flags the runner actually emits, not merely the ones it defines.** The
`pytest-run` step's `run:` block was extracted from the YAML, its `${{ }}` expressions substituted
with real values, the pytest call replaced by an `echo`, and the block executed under `bash`:

```
module-tests: measuring --cov=charter --cov=doctrine --cov=glossary --cov=kernel \
  --cov=mission_runtime --cov=runtime --cov=specify_cli
PYTEST_ARGV: ... --cov=charter ... --cov-report=xml:out/reports/coverage/coverage-standard-lanes-shard1-of-1.xml
```

Seven flags, identical for every matrix row, derived from `src/` at run time.

**Why `doctrine` is in the set.** `src/doctrine.py` is a top-level single-file module (the
`charter.offering` compatibility shim), not a package. The step this mission retires measures it
(`--cov=doctrine` in `ci-quality.yml`'s `sonarcloud` job). Deriving only directories-with-`__init__.py`
would have silently dropped that file's coverage — a regression the breadth fix is supposed to
prevent — so the derivation covers packages **and** public top-level modules.

---

## 2. Per-slice cost (T003)

One slice, one identical test selection (`tests/lanes -m "not performance"`, 400 passed / 1 skipped),
run twice:

| | narrow (`--cov=specify_cli.lanes`) | broadened (7 targets) | Δ |
|---|---|---|---|
| wall clock (pytest-reported) | 140.85 s | 157.06 s | **+16.21 s (+11.5 %)** |
| wall clock (process) | 142.28 s | 158.88 s | +16.60 s |
| coverage XML | 79,718 B | 4,881,542 B | ×61.2 |
| files in report | 15 | 1,258 | +1,243 |
| covered statements | 1,711 | 31,937 | **+30,226** |

Reproduce:

```bash
.venv/bin/python -m pytest tests/lanes -m "not performance" \
  --cov=specify_cli.lanes --cov-report=xml:narrow.xml -p no:cacheprovider -q
.venv/bin/python -m pytest tests/lanes -m "not performance" \
  --cov=charter --cov=doctrine --cov=glossary --cov=kernel --cov=mission_runtime \
  --cov=runtime --cov=specify_cli --cov-report=xml:broad.xml -p no:cacheprovider -q
```

**Against the prior measurement** (narrow 144.38 s / 79,718 B / 1,711 covered → broad 158.70 s /
4,881,542 B / 31,911 covered): both XML byte counts and the narrow covered count reproduce
**exactly**; the broad covered count differs by +26 statements (0.08 %) and the delta is +11.5 %
here against +9.9 % there. Same shape, confirmed rather than trusted.

## 3. Aggregate cost (T003) — the number that actually decides this

NFR-002 is an **aggregate** budget. A per-slice budget cannot protect it: 34 slices each absorbing
one minute is +34 min against ~22 saved.

**Slice count** — 34, summed from `.github/ci-module-registry.yml`'s `shard_count` column
(`merge 1, missions 1, post_merge 1, release 1, status 1, review 1, next 2, lanes 1, dashboard 1,
upgrade 4, cli 2, charter 5, agent 3, kernel 1, glossary 1, execution_context 3, core_misc 5`).

**Local→CI scaling factor, derived rather than assumed.** The retiring step ran locally in
**651.47 s** (below, §4). Its CI population median is **1,352 s**. Ratio **2.08×** — which
independently corroborates the ≈2.2× single-point figure recorded in `quickstart.md` §6.

| | per slice | × 34 slices |
|---|---|---|
| measured locally | +16.21 s | **+9.19 min** |
| projected at CI speed (×2.08) | +33.7 s | **+19.08 min** |

**Saving** — the retiring `sonarcloud` job, population n=12 pull-request runs: median **22 m 32 s**
(22.53 min), range 12 m 50 s – 23 m 15 s. Do not quote a single run; the population is wide.

| scenario | added | saved | net |
|---|---|---|---|
| local rate vs median saving | 9.19 | 22.53 | **+13.34 min saved** |
| CI-projected vs median saving | 19.08 | 22.53 | **+3.45 min saved** |
| CI-projected vs low-end saving | 19.08 | 12.83 | **−6.25 min (net negative)** |

> ### ⚠️ FINDING — surfaced, not absorbed (T003 stopping condition)
>
> The trade is **net positive in the central case and thin**. At the CI-projected overhead the
> whole saving is +3.4 min out of 22.5 — and if a given PR's retiring-step run lands at the low end
> of its own observed range, the change is **net negative for that run**.
>
> This does **not** meet "aggregate cost exceeds the saving" on the central estimate, so WP01 does
> not stop here. But two things follow, and neither is mine to decide:
>
> 1. **The mission's NFR-002 claim must be made against a measured aggregate, not this projection.**
>    The ×2.08 scaling is a first-order projection of a CPU-bound tracer overhead onto a
>    whole-suite wall-clock ratio. Only the branch's own CI run settles it (§6).
> 2. **If the operator's acceptance bar is "clearly faster" rather than "not slower", this is a
>    decision point, not a pass.** The mission's own framing is a runtime-for-accuracy trade; the
>    accuracy gain is large and certain (§5), the runtime saving is small and uncertain.
>
> Per-slice sensitivity: the overhead is not uniform. `lanes` is a mid-sized slice; a slice that
> imports less of the tree absorbs less, one that imports more absorbs more. 34 × one slice's delta
> is an estimate, not a sum of measurements.

**Artefact bytes and downstream parse.**

| | before | after | source |
|---|---|---|---|
| reconciled artefact total | 29.8 MB | **166.0 MB** (×5.57) | 34 × 4,881,542 B measured |
| downstream load (`validate_diff_coverage.py`'s `XmlCoverageReporter([parse(r) for r in reports])` + `measured_lines`) | ~1.03 s | **6.48 s** | measured on 34 reports; 25.6 MB/s broad, 29.0 MB/s narrow |

The parse cost is negligible against runner-minutes. The **upload/download** of 166 MB across 34
artefacts is not measurable locally and is listed in §6.

---

## 4. Per-file baseline (T004)

**Retiring step, measured locally** — 1,796 passed / 5 skipped in **651.47 s**:

```bash
.venv/bin/python -m pytest tests/unit tests/status tests/cli tests/specify_cli/runtime \
    tests/architectural/test_no_retired_subsystems.py \
  -m "(fast or unit) and not slow and not e2e and not integration and not regression \
      and not distribution and not live_adapter and not stress and not windows_ci \
      and not platform_darwin" \
  -n auto --dist loadfile \
  --cov=charter --cov=doctrine --cov=glossary --cov=kernel --cov=mission_runtime \
  --cov=runtime --cov=specify_cli --cov-report=xml:retiring-step.xml -p no:cacheprovider -q
```

| | this run | planning figure |
|---|---|---|
| covered statements | **42,942** | 42,933 |
| statement union | **128,878** | 128,878 |
| percentage | **33.32 %** | 33.31 % |
| files in report / with any coverage | 1,258 / 998 | — |

Per-file counts are committed in `coverage_breadth_baseline.json` under
`per_file_covered.retiring_step.files` as `path -> [covered, statements]`.

**The post-change matrix union is recorded as `pending-ci`, not invented.** It is the reconciliation
of all 34 shard reports from a real `ci-modules.yml` run; reproducing it locally means running the
whole suite, which `CLAUDE.md`'s test policy assigns to the CI agent. The baseline carries the
retrieval command and a `null` run id to be filled by the first run of this branch:

```bash
gh run download <ci-aggregate run id> -n ci-aggregate-reconciled-coverage -D recon/
```

---

## 5. Marker-mismatch exception set (T005) and the no-regression verdict (T006)

### The exception set — derived, not transcribed

Committed derivation:
`tests/architectural/test_coverage_breadth.py::derive_marker_mismatch_exception_set`, re-run by
`test_marker_mismatch_exception_set_is_reproducible` in the blocking architectural gate. It takes
the set difference between the retiring step's selection and the slices' selection **over the same
directories**, reading both marker expressions from their own authorities (the `Makefile`'s
`FAST_TIER_MARKERS`; `module-tests.yml`'s `-m "not performance"`) — no literal is transcribed.

Current output — **5 tests, all in `tests/status`**, confirming the planning count:

```
tests/status/test_emit_durability.py::TestT015Responsiveness::test_verdict_recording_completes_under_two_seconds
tests/status/test_locking_key.py::test_contended_bounded_take_stays_under_five_seconds
tests/status/test_saas_fanout_timeout.py::test_hanging_lifecycle_handler_does_not_block
tests/status/test_saas_fanout_timeout.py::test_hanging_saas_handler_returns_within_three_seconds
tests/status/test_tail_reader.py::test_tail_events_zero_real_sleep_stays_under_budget
```

All five carry the `performance` marker, which the retiring step's expression does not exclude and
every slice does.

### T006 verdict: zero unexplained per-file regressions

**Measured.** The one slice run both ways (§2) is the direct test of WP01's own effect, because the
test selection is identical on both sides:

* files whose covered count **decreased** narrow → broad: **0**
* files present in the narrow report and **absent** from the broad report: **0**
* files gained: +1,243 · statements recovered: **+30,226** (target ≥2,808 — exceeded by 10×)

**And true by construction.** Broadening `--cov` changes only the *recording scope*, never which
tests run or which lines execute. A file's covered-line set can therefore only grow. The only
remaining way a file can lose coverage is a **selection** change — which is exactly what the T005
exception set enumerates, and WP01 changes no selection (the `-m`, the shard bin-packing and the
`test_dirs` resolution are untouched).

### Residual selection gap — pre-existing, and NOT closed by WP01

Of the five paths the retiring step selects, **three are in no matrix slice's test directories**
(union computed from the registry's `test_dirs`, with the workflow's `tests/{module}` + `tests/doctrine`
fallback):

| retiring-step path | covered by a slice? |
|---|---|
| `tests/status` | yes |
| `tests/cli` | yes |
| `tests/unit` | **no** |
| `tests/specify_cli/runtime` | **no** |
| `tests/architectural/test_no_retired_subsystems.py` | **no** |

This is the gap the mission's "adding the two rows" step closes, and it belongs to **WP02** (WP01 is
forbidden from touching `.github/ci-module-registry.yml` / `tests/release/ci_retirement_scrub.json`,
which a verbatim gate pins). Flagging it here so WP02 sizes it correctly: it is **three** inputs, not
two — `tests/architectural/` has no registry row at all, so the whole directory is currently outside
the matrix.

The separate dormant group (52 tests in one file, excluded by markers from every selection including
the scheduled sweep) is **#4351** — pre-existing, not absorbed here.

---

## 6. What could not be measured here (honesty boundary)

This branch has not been pushed, so no run id exists for it yet. Each of these is a
**post-integration observation**, not a pre-merge claim:

| claim | why not measurable locally | how to close it |
|---|---|---|
| aggregate matrix job-duration sum, before vs after | needs the branch's own `ci-modules.yml` run | sum `.jobs[].started_at/completed_at` for the 34 `module-tests` jobs on the first run of this branch, both against the merge base and after |
| real per-slice overhead on CI | local→CI ratio ×2.08 is a projection of one whole-suite ratio onto a tracer overhead | compare the same 34 job durations |
| reconciled artefact total after | needs a real reconciliation | `gh run download <id> -n ci-aggregate-reconciled-coverage` and sum the bytes |
| matrix-union per-file coverage after | requires the whole suite; assigned to the CI agent by `CLAUDE.md` | same artefact; write it into `per_file_covered.matrix_union_after` |
| diff-cover gate behaviour change | WP01 moves files from `absent` to present-but-uncovered in `scripts/ci/validate_diff_coverage.py:57`, which puts them in the `--fail-under=90` denominator | first PR run on this branch |

The last row is the one to watch: **this work package is not behaviour-preserving for the
merge-blocking change-coverage gate.** Files that used to be scored as `absent` now enter the
denominator, so a PR that previously slipped through on missing measurement can now fail at 90 %.
That is the intended correction, and it is the reason WP01 is the riskiest package in the mission.

---

# Coverage-breadth evidence — WP02 (test-inventory rows)

WP01 established this file; WP02 co-owns it. This half records what declaring `tests/unit` and
`tests/specify_cli/runtime` in the registry costs, and settles the third input WP01's "Residual
selection gap" section flagged.

## 7. The two new rows — measured timings, and their per-slice cost (T008 / T012)

Both rows were measured, not estimated. The producer is now committed
(`scripts/ci/capture_shard_timings.py`, T007) so this is reproducible rather than archaeological —
the original `.github/ci-shard-timings.json` came from an ad-hoc plugin that was never in the tree.

Producing run: `run_id = wp02-durations-20260914T153812Z` (local; this branch has not been pushed, so
no CI run id exists — same honesty boundary as §6). Recorded per module under the new
`module_capture_provenance` key in `.github/ci-shard-timings.json`, alongside the exact command.

| registry row | `test_dirs` | tests measured | Σ per-test seconds | wall clock | `shard_count` | added slices |
|---|---|---|---|---|---|---|
| `unit` | `tests/unit` | 454 | 4.742 s | 6.26 s | 1 | 1 |
| `specify_cli_runtime` | `tests/specify_cli/runtime` | 77 | 14.219 s | 14.47 s | 1 | 1 |

**Per-slice runtime the two rows add to the mission's aggregate budget:** 2 new matrix slices,
~6.3 s + ~14.5 s = **~20.8 s of local test wall clock**, before the fixed per-slice overhead every
`module-tests.yml` job pays (checkout, warmup, `uv sync`, coverage start-up). Against §3's local→CI
ratio of ×2.08 that projects to roughly **43 s of added CI test time**, plus two job set-ups. That is
noise beside §3's 22.53 min median saving and beside WP01's own +9.19 min local breadth cost; the
inventory rows are not what decides this mission's budget.

`shard_count: 1` for both is the honest answer at these durations — a second shard would spend more
on job set-up than it could save. Note the consequence for the skew guard
(`test_inter_shard_skew_within_twenty_percent`): at `shard_count == 1` it is **trivially satisfied**
and proves nothing about these rows. What actually protects them is the length match below.

### Why the measurement is load-bearing (the silent-fallback trap)

`module-tests.yml` cannot join durations to node ids (the committed file drops node ids), so it pairs
them **positionally** and falls back to uniform weights **for the whole module** when
`len(durations) != len(collected)`. Nothing reports that fallback, and the skew guard re-reads the
same committed list — so a fabricated list of the right length passes every gate while silently
degrading balancing to a test-count split.

Length match, verified against the consumer's own selection
(`pytest <test_dirs> -m "not performance" --collect-only -q`):

| row | collected | durations recorded | matches |
|---|---|---|---|
| `unit` | 454 | 454 | yes |
| `specify_cli_runtime` | 77 | 77 | yes |

Both directories collect **> 0** tests (T012 step 1) — the floor `module-tests.yml` enforces with
`exit 64`.

One methodology note for whoever regenerates the older rows: the committed `module_duration_seconds`
badly understates wall clock for fixture-heavy modules (the `merge` row reads 1.1 s against a ~138 s
serial run) because the original capture recorded the **call phase only**. `DurationRecorder` sums
`setup + call + teardown`, which is why the two rows above land at 76 % (`unit`) and 98 %
(`specify_cli_runtime`) of measured wall clock instead of under 1 %. Do not build a cost model on the
pre-WP02 values in that field.

## 8. The third input: `tests/architectural/test_no_retired_subsystems.py` — quantified, accepted

WP01 §5 correctly flagged that the retiring step runs **three** things absent from the matrix, not
two. The third is the architectural gate file, and it is real: `ci-router.yml`'s `architectural-heavy`
job **runs** it but emits no coverage artefact (no `--cov`, no upload), and no registry row names
`tests/architectural`, so its *coverage contribution* — not its execution — is what retirement would
drop.

**Decision (operator ruling, WP02): do not add a `tests/architectural` row.** Putting the ~2,400-test
architectural battery into the per-PR matrix under coverage is exactly the heavy work that belongs to
CI, and it would dwarf this mission's saving. The reduction is instead quantified and declared here.

**Measured marginal contribution: 0 statements.**

Two runs, identical `--cov` set (the full top-level package set derived from `src/`, per WP01) and
identical marker expression (the retiring step's own fast-tier expression), compared at **line**
granularity:

| run | selection | covered statements |
|---|---|---|
| A | `tests/unit tests/status tests/cli tests/specify_cli/runtime` | 42,942 |
| B | `tests/architectural/test_no_retired_subsystems.py` | 26,845 |
| A ∪ B | the retiring step's five paths | **42,942** |
| **B \ A** | **covered ONLY by the third input** | **0** |

Files carrying at least one line covered by B and by no test in A: **0 of 1,258**.

Every one of B's 26,845 lines is import-time coverage — module-level `import`/`class`/`def`
statements the gate materializes by walking the tree — and all of it is already executed by the four
test directories the matrix now owns. Retiring the step therefore loses **no measured statement** on
account of the third input.

The A-run total independently reproduces WP01's recorded retiring-step figure of 42,942 / 128,878
(`tests/release/coverage_breadth_baseline.json` → `per_file_covered.retiring_step.totals`) **from the
four directories alone**, which is the same conclusion from the other side: the third input was never
contributing a statement of its own.

Reproduce (≈11 min for run A, ≈30 s for run B):

```bash
M='(fast or unit) and not slow and not e2e and not integration and not regression and not distribution and not live_adapter and not stress and not windows_ci and not platform_darwin'
COV='--cov=charter --cov=doctrine --cov=glossary --cov=kernel --cov=mission_runtime --cov=runtime --cov=specify_cli'
.venv/bin/python -m pytest tests/unit tests/status tests/cli tests/specify_cli/runtime -m "$M" -n auto --dist loadfile $COV --cov-report=json:a.json -q
.venv/bin/python -m pytest tests/architectural/test_no_retired_subsystems.py -m "$M" -n auto --dist loadfile $COV --cov-report=json:b.json -q
# then: per file, |executed_lines(b) - executed_lines(a)|  ==  0
```

This closes WP01 §5's "three inputs, not two" flag: two are declared, the third is measured at zero
and accepted. The 52 marker-excluded tests remain **#4351** — still not absorbed.

## 9. `roots` for a row that owns no source (T009 step 3)

Both new rows are *test-inventory* rows: they exist to give a live test directory a declared home, and
they own no `src/**` surface of their own. `roots` could not simply be omitted — two gates forbid it
(`test_every_row_has_required_fields` refuses an empty list; `gate_selection.Router.src_backed_groups`
only counts a group with a `src/` glob, and `test_router_src_filters_derive_from_scrub_verbatim`
requires the src-backed set to equal the scrub group set exactly).

The chosen expression: **each root is a verbatim copy of a glob another kept group already owns**,
restricted to the surfaces that directory's tests actually import. Consequence: no path's group-match
set changes, so the `unmatched` fail-closed union keeps its exact previous semantics. Verified by
routing representative paths through `scripts/ci/gate_selection.select_gates` before and after — the
selected job set is identical for `src/kernel/clock.py`, `src/specify_cli/merge/executor.py`,
`src/specify_cli/intake/scanner.py` (still `unmatched_src=True` → run-all) and `docs/x.md`.

The rejected alternative and its rationale are recorded in
`kitty-specs/sonar-per-pr-coverage-reuse-01M2FR32/traces/design-decisions.md`. In short: claiming the
six `src/specify_cli/{intake,git,mission_loader,migration,contracts,workspace}/**` packages that
`tests/unit` exercises and that **no** group currently owns would have closed a real routing gap, but
it would also have demoted those paths from the FR-004 run-all catch-all to a single shard. That is a
routing-policy change, not test-inventory bookkeeping, and it is not this WP's to make.
