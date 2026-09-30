---
title: 'Verification evidence — egress-refusal-consolidation-3110-01KYW895'
description: 'Closeout evidence for mission 01KYW895: the 3.11 portability run, isolated single-file runs, per-clause criterion reporting, and the conditionality ledger.'
doc_status: closeout
type: explanation
updated: '2026-08-04'
related:
- docs/adr/3.x/2026-08-04-1-egress-consent-boundary.md
- docs/context/identity.md
- docs/development/testing/testing-flakiness.md
---
## Verification evidence — `egress-refusal-consolidation-3110-01KYW895`

This page is the mission's verification record: what was measured, on what tree, with what
command, and — the part that makes it usable — **what was measured wrongly and re-taken**, and
**which greens are conditional on work that has not landed**.

### How to read it

Three reading rules, each of which this mission learned the hard way.

1. **A number without its subject is not a measurement.** Every count below names the tree
   (`HEAD`), the interpreter, and the command. Where a number came from someone else's run rather
   than the run recorded here, it is attributed.
2. **A green without its limit is a claim, not evidence.** The [conditionality
   ledger](#conditionality-ledger--what-a-successor-must-re-take) says which greens a successor
   must re-take and which were never conditional.
3. **Per clause, never as one verdict.** Four criteria in this mission are satisfiable by the
   work not having been done. They are reported clause by clause in [Per-clause criterion
   reporting](#per-clause-criterion-reporting-nfr-004--r13), and each says which clause
   discriminates.

---

## The tree everything was measured on

Asserted in process before each measurement, not assumed — the mission's own method note records
three invalid verifications whose common shape was *an exit status or a path that was not the one
the measurer believed*.

| | |
|---|---|
| Repository root | `/home/jeroennouws/dev/sk-missions/3110` |
| Branch | `pr/egress-refusal-consolidation-3110` |
| `HEAD` | `673a718f0c155310838eb2aaa0ebcf768b40c3ee` |
| Consolidation baseline (`HEAD` of the pre-mission tree) | `985ae6484b20f2c935fdad858bc1f868c73835e1` |
| `specify_cli` resolved to | `/home/jeroennouws/dev/sk-missions/3110/src/specify_cli/__init__.py` |

`import specify_cli` was asserted to resolve inside **this** clone before every run. A bare
`python3 -c "import specify_cli"` on this machine resolves to a different, concurrently-edited
checkout; every non-`pytest` invocation below sets
`PYTHONPATH=/home/jeroennouws/dev/sk-missions/3110/src` explicitly.

**Ancestry is not the test of whether a lane landed.** Lane branches were squash-merged, so no
lane commit is an ancestor of `HEAD` and `git merge-base` reports nothing useful. Consolidation
was verified **by content**: `src/specify_cli/egress.py` and
`src/specify_cli/decisions/ownership.py` are present, and both `*/egress_consent.py` modules are
gone — confirmed by import, not by `git log`:

```
saas_client/egress_consent.py importable: False
tracker/egress_consent.py     importable: False
```

---

## T037 — NFR-006 / SC-014 `[one-off]`: the Python 3.11 run

**Why it is required in executed form.** Only 3.14 is installed on this machine; CI runs
3.11/3.12. `ownership.py`'s unreadable-ledger branch sits on a real `Path.exists()`/`is_dir()`
EACCES divergence between those interpreters, so a judgement about version-divergent branches
made on 3.14 is not verification of anything.

**Environment, built for this measurement:**

```
uv venv --python 3.11 <scratch>/venv311
uv pip install --python <scratch>/venv311/bin/python -e ".[test]"
```

| | 3.11 venv | system interpreter |
|---|---|---|
| Python | `3.11.15` | `3.14.4` |
| `pytest` | `9.0.3` (venv `site-packages`) | `9.1.1` (**user site**, `~/.local/lib/python3.14/`) |

The 3.11 venv is the **more faithful** of the two in a second respect nobody asked for:
`pyproject.toml` pins `pytest>=9.0.3,<9.1` and says why (the 9.1.x `reorder_items`
`INTERNALERROR`, #2884). The venv resolved to `9.0.3`, matching CI; the system interpreter's
user-site `pytest` is `9.1.1`, outside the pin.

**What was run:** this mission's nine touched test files — which include **both** attribution
guards (`tests/specify_cli/saas_client/test_client_consent_gate_3030.py` and
`tests/sync/tracker/test_saas_client_consent_gate_3030.py`, the two modules that hold
`_saas_site_attribution` / `_tracker_site_attribution`) — each as its own single-file `pytest`
process from the clone root. Output written to a file per run and read from the file; no run was
piped, and the `N passed` line is the evidence rather than the exit code.

**The `N passed` lines, verbatim, on `3.11.15` / `pytest 9.0.3`:**

```
tests/specify_cli/saas_client/test_client_consent_gate_3030.py
    ============================= 21 passed in 55.37s ==============================
tests/sync/tracker/test_saas_client_consent_gate_3030.py
    ============================= 27 passed in 50.64s ==============================
tests/architectural/test_gate_coverage.py
    ======================== 37 passed in 490.14s (0:08:10) ========================
tests/architectural/test_integration_boundary.py
    ========================= 4 passed in 62.45s (0:01:02) =========================
tests/specify_cli/test_egress_consolidation_3110.py
    ============================= 13 passed in 52.76s ==============================
tests/specify_cli/decisions/test_ownership_3111.py
    ======================== 33 passed in 63.31s (0:01:03) =========================
tests/specify_cli/saas_client/test_decision_widen_ownership_3111.py
    ======================== 11 passed in 68.01s (0:01:08) =========================
tests/specify_cli/cli/commands/test_decision_widen_subcommand.py
    ======================== 28 passed in 64.97s (0:01:04) =========================
tests/invocation/test_adapters.py
    ======================== 18 passed in 63.38s (0:01:03) =========================
```

**Input count stated alongside the greens, because "all passed" without it is unfalsifiable:**
**9 files, 192 collected items, 0 failures, 0 errors, 0 skips** on 3.11. Per-file collected counts
are 21 / 27 / 37 / 4 / 13 / 33 / 11 / 28 / 18.

**Provenance of the first two rows.** The first attempt at this sweep was **killed** at exactly
10m00s — the harness timeout, not a test timeout — part-way through `test_gate_coverage.py`. The
two rows above were produced by pytest processes that had already exited `rc=0` with a complete
summary line before the kill; the interrupted file was **re-run narrowed**, not explained, and its
partial output (35 of 37 items, all dots) is quoted nowhere as evidence. Same tree, same venv,
both halves.

### T030's test is named, because a green run over files that never touch the branch is a true statement about nothing

The test carrying NFR-006 is:

```
tests/specify_cli/decisions/test_ownership_3111.py::test_unreadable_decisions_directory_yields_not_established_with_the_flag
```

It is the **directory** shape — `chmod 0o000` on the containing `decisions/` directory, file left
readable — and that shape is the requirement, not a stylistic preference. `stat(2)` needs *search*
permission on the parent, not read permission on the file, so the `file=0o000` shape returns an
**identical** result on 3.11 and 3.14; the honest reading of an identical result is *"no
divergence, NFR-006 discharged"*, which would be a false negative in this mission's only
portability gate.

What it asserts is `resolve_decision_ownership`'s **outcome** — `owned is False`,
`has_unreadable_ledger is True`, `unreadable_ledgers == ("mission-locked",)`, and a refusal that
names the ledger — not `Path.exists()`'s return value. A `Path.exists()` characterization test
passes identically whether or not `ownership.py` carries its `except OSError`, i.e. it is green on
precisely the regression the branch exists to catch.

Its `file=0o000` companion, `test_unreadable_index_file_is_also_handled`, is labelled in its own
docstring as covering `read_text` → `PermissionError` at `store.py:66` and is **explicitly not
offered as NFR-006 evidence**.

**It did not skip.** The test guards itself with `mode_bits_enforced(index_file)` and skips with a
stated reason if the process can read through a `0o000` directory. Had it skipped, that would not
be a discharge of NFR-006 and this page would say so instead of quoting a `N passed` line. It ran.
The process euid was `1000`, so mode bits are enforced here.

---

## The divergence the 3.11 run actually found — and it points the other way

**Do not read this as NFR-006 failing.** NFR-006 asks that behaviour hold on the interpreters CI
runs, and it does: `test_ownership_3111.py` is `33 passed` on 3.11. The run found something
NFR-006's text does not cover, in the **opposite** direction — a branch that works on 3.11/3.12
and silently does nothing on 3.13+.

Measured on the same tree, in two venvs with the **same** `pytest 9.0.3`, so the interpreter is
the only variable:

| File | 3.11.15 | 3.14.4 |
|---|---|---|
| `tests/specify_cli/decisions/test_ownership_3111.py` | `33 passed in 63.31s` | `2 failed, 31 passed in 55.31s` |

The two failures:

```
FAILED test_unstattable_mission_candidate_is_flagged_not_reported_as_no_missions
FAILED test_unstattable_mission_candidate_does_not_veto_a_hit_elsewhere
  assert () == ('m-link',)
```

### Mechanism, probed directly with a control before anything was attributed

```
                              3.11.15                   3.14.4
CONTROL readable vault        is_dir() -> True          is_dir() -> True
vault = 0o000                 is_dir() RAISES           is_dir() RETURNS False
                              PermissionError           (EACCES swallowed)
```

`ownership.py:387` reads `if not resolved.is_dir() or not resolved.is_relative_to(specs_root):
continue`, and the LOW-8 recording — `unreadable.append(candidate.name)` — hangs off the
`except OSError` on the following line. On 3.11/3.12 `is_dir()` raises, the handler runs, and the
dropped candidate is recorded. **On 3.13+ `is_dir()` returns `False`, control takes the bare
`continue` at `:388`, and the drop is never recorded.**

This is the module's own documented lesson, unapplied at the one place the recording depends on
it. Its docstring removes `Path.exists()` three times *because* it is EACCES-divergent
(`:50-56`, `:120`, `:322-323`, `:434`) and `:374-380` states the `is_dir()` divergence explicitly
— then reads 3.14's non-raise as *"a clean refusal on 3.14"*. It is not a clean refusal. It is
LOW-8's original defect, verbatim.

### The operator-visible consequence, measured on both interpreters

```
3.11 : … (no mission under <root>/kitty-specs could be searched at all). 1 mission ledger(s) or
       mission directory(ies) could not be read or parsed and so could not answer: m-link.
       To fix: this is not a missing checkout — `git pull` will not fix it. Inspect the named
       path … restore read+execute access (e.g. `chmod u+rx`) …

3.14 : … (no missions were found under <root>/kitty-specs to search).
       To fix: run `git pull` (or otherwise restore kitty-specs/) and retry …
```

On 3.13+ the operator is told *"no missions were found … run `git pull`"* for a permission
problem — the exact sentence, and the exact wrong remedy, that
`test_unstattable_mission_candidate_is_flagged_not_reported_as_no_missions` was written to make
impossible.

### Severity, scope, and disposition

**Fail-closed on both interpreters.** `owned is False` and `missions_searched == ()` on 3.11 and
3.14 alike; nothing is transmitted and no consent is laundered. This is a **diagnosis** defect —
the same wrong-operator-action class as FU-J, LOW-6, LOW-7 and LOW-1 — not a consent leak.

It is nonetheless in scope for the repo: `pyproject.toml` declares
`requires-python = ">=3.11"`, so 3.13 and 3.14 are supported interpreters, and 3.14 is the only
one installed on this machine.

**This work package did not fix it and did not absorb it.** WP07 writes no source and no tests;
a red it repaired, worked around, or quietly dropped from T038's file list would be exactly the
"unstated set" R-22 names, landing in the one artifact whose whole purpose is to be trusted. The
owning package is **WP04**, which is `approved`, so the route is **escalation to the operator**
rather than a unilateral reopen. Evidence refs:

- `tests/specify_cli/decisions/test_ownership_3111.py` — the two named failures, `assert () == ('m-link',)`
- `src/specify_cli/decisions/ownership.py:387-403` — the site
- the `is_dir()` probe table and the two refusal strings above, both reproducible on this tree

A candidate fix (**not applied here**): catch the containment/`is_dir()` drop and the `OSError`
drop as two recorded outcomes rather than one raise-dependent one — i.e. probe readability
explicitly, the way the module already does one level down for the ledger, instead of leaning on
whether `is_dir()` happens to raise on the running interpreter.

---

## T038 — NFR-005 / SC-009: isolated single-file runs

**File count: 9.** Confirmed against the actual diff rather than transcribed from the WP prompt —
`git diff --name-status 985ae6484 HEAD -- tests/` returns exactly these nine paths and no others.
"All isolated runs passed" over an unstated set is vacuous; an empty set satisfies the bare claim.

Each run is one `pytest` process, one file, invoked from this clone's root, output written to a
file and read from the file. No run below was piped.

**The set, stated with its count — 9 files, and every one of them listed.** Both interpreters were
run so the isolated greens are not silently interpreter-bound; both used `pytest 9.0.3` from a
venv, so the interpreter is the only variable between the columns.

| # | File | From | Items | 3.11.15 | 3.14.4 |
|---|---|---|---|---|---|
| 1 | `tests/specify_cli/saas_client/test_client_consent_gate_3030.py` | WP01, WP03 | 21 | `21 passed in 55.37s` | `21 passed in 61.97s` |
| 2 | `tests/sync/tracker/test_saas_client_consent_gate_3030.py` | WP01, WP03 | 27 | `27 passed in 50.64s` | `27 passed in 67.74s` |
| 3 | `tests/architectural/test_gate_coverage.py` | WP02 | 37 | `37 passed in 490.14s` | `37 passed in 582.40s` |
| 4 | `tests/architectural/test_integration_boundary.py` | WP03 | 4 | `4 passed in 62.45s` | `4 passed in 62.59s` |
| 5 | `tests/specify_cli/test_egress_consolidation_3110.py` | WP03 | 13 | `13 passed in 52.76s` | `13 passed in 66.04s` |
| 6 | `tests/specify_cli/decisions/test_ownership_3111.py` | WP04 | 33 | `33 passed in 63.31s` | **`2 failed, 31 passed in 55.31s`** |
| 7 | `tests/specify_cli/saas_client/test_decision_widen_ownership_3111.py` | WP04 | 11 | `11 passed in 68.01s` | `11 passed in 59.87s` |
| 8 | `tests/specify_cli/cli/commands/test_decision_widen_subcommand.py` | **WP04 (T027 b) — pre-existing, CHANGED** | 28 | `28 passed in 64.97s` | `28 passed in 49.31s` |
| 9 | `tests/invocation/test_adapters.py` | WP05 | 18 | `18 passed in 63.38s` | `18 passed in 48.08s` |

**Totals. 9 files, 192 collected items on each interpreter.** On **3.11**: 192 passed, 0 failed,
0 errors. On **3.14**: 190 passed, 2 failed, 0 errors — the two failures in one file. **0 skips
and 0 xfails on both**, checked file by file rather than inferred from the totals, because a
silently-skipping `0o000` test is the vacuous case this mission's own criteria name and it would
be invisible in a `passed` count.

**Row 6 is the only divergence, and it is not a flake.** It is a defect in `ownership.py` that
appears only on 3.13+, with the tests correct on both sides. It is analysed, attributed and
escalated in [its own section](#the-divergence-the-311-run-actually-found--and-it-points-the-other-way),
and it is **not** absorbed into this work package, not fixed here, and not dropped from this list.
Recording nine files and quoting eight would be exactly the unstated set NFR-005 exists to
prevent.

**Row 3's earlier reds were an invalid measurement, not a red.** Under the *system* interpreter
this file produced 1 failure and 8 setup errors; under a venv it is `37 passed` on **both**
interpreters. The cause and its control are in [measurements that were
wrong](#measurements-that-were-wrong-and-were-re-taken). No red was green-washed: the environment
was wrong, and the same file run correctly is green.

`tests/specify_cli/cli/commands/test_decision_widen_subcommand.py` is on the list and is the row
most likely to be dropped, so it is called out: it is a **pre-existing green module that WP04
changed**, not a new one. Its `DECISION_ID` fixture was 22 characters and contained an `I`, so it
failed the FR-005 ULID check, and its nine `patch(… SaasClient.from_env …)` live-path tests ran
against a `tmp_path` owning no ledger, so they hit the new ownership refusal. *"Every test added
**or changed**"* includes changed ones, and a file that appears in the diff only as fixture
corrections is exactly the file an isolated-run list forgets.

**Why isolation is the compensation and not belt-and-braces.** `#3115` (shard-parallel test
isolation) is OPEN and its sync half is deferred to `#3136` (FU-G), so a full-suite red on this
surface is not attributable. The isolated single-file runs are the only trustworthy greens this
mission can produce — which also means **no full-suite green is claimed anywhere on this page.**

**Pre-existing reds were not folded in.** In particular,
`tests/specify_cli/invocation/test_propagator_consent_gate_3030.py` run *before*
`tests/specify_cli/saas_client/test_client_consent_gate_3030.py` in one process fails with *"no
hosted-sync consent resolver is registered"* — a fixture-teardown ordering artefact, deterministic
in alphabetical order. On a consent mission that text reads exactly like the defect under repair.
It was neither chased nor green-washed, and it is not in this mission's scope.

---

## Per-clause criterion reporting (NFR-004 / R13)

Four criteria here are compatible with the work not having been done. Reporting them as one
verdict would hide that.

### SC-004 — three clauses, one of which discriminates

| Clause | Label | Result | What it proves, and does not |
|---|---|---|---|
| 1 — the non-fragment portion of both rendered `DENIED` strings is byte-identical | `[ratchet]` | holds | Already true at `bb2020fea`; the two strings differed in exactly one word before consolidation. **It does not distinguish a correct consolidation from an incorrect one** — it must merely stay true. |
| 2 — each transport's fragment names exactly its own enumerated identifier set, and no foreign kind | `[ratchet]` | holds | True of the **unconsolidated** state by construction: under the operator's Q2 decision both current `DENIED` strings survive verbatim, so the mission produced no wording. The only way it can red is if the Key-Entities check fails on the *existing* text — which would have red at `bb2020fea` too. |
| 3 — binding identity: both deciding modules' `project_egress_refusal` **is** `specify_cli.egress.project_egress_refusal` | `[standing]` | **holds — and this is the clause that discriminates** | It reds on the state nothing else in the spec detects: a partial consolidation where `tracker/egress_consent.py` or its SaaS twin survives as a **re-export**, so the deciding module's by-value binding still points at the old object. A surviving re-export renders the *identical correct string*, so text cannot separate the two cases. |

*"SC-004 passes"* is therefore not evidence the consolidation happened. Clause 3 is. Measured here
independently, in process, from two separately imported names — never two imports of one path,
because comparing an object to itself proves nothing:

```
specify_cli.saas_client.client.project_egress_refusal  is specify_cli.egress.project_egress_refusal  -> True
specify_cli.tracker.saas_client.project_egress_refusal is specify_cli.egress.project_egress_refusal  -> True
CONTROL, a different callable, must be False                                                         -> False
```

The control is there because an identity assertion that cannot return `False` is one of the five
proofs-that-could-not-fail this mission produced. It returned `False`.

### SC-005 / #3030 — the guards are non-vacuous, and this is WP01's measurement, not mine

Recorded here **attributed**, because this work package did not take it. WP01 measured the
per-class non-vacuity floors as named integers — `SAAS_CONSTRUCTION_SITE_FLOOR = 4`,
`TRACKER_CONSTRUCTION_SITE_FLOOR = 3` — over **1197** files under `src/`, identical to the count
under the older `src/specify_cli` root (936 files), which is why widening the scan moved no count.
WP01 reports MUT-4/5/6 killed and, for the SC-005 demonstration, that removing one site of each
class reds with `assert 3 >= 4` and `assert 2 >= 3`.

What this buys: the `assert scanned` the floors replace reds only when **every** site of a class
disappears. A named integer makes losing **one** site red. What it does not buy: coverage. #3030
itself was closed upstream by the parent mission (`journal-project-consent-3030-01KYKWQS`, PR #3098,
merged 2026-07-31); the verdict is `verified-already-fixed`, and what this mission
established is that the guard keeping it closed is real rather than decorative.

I re-ran both modules on both interpreters and they are green (see T037 and T038). I did **not**
re-take the mutation runs or the site-removal demonstration.

### SC-010 — the four `could not be determined` assertions

`[ratchet]`. **Input count measured, not transcribed: four**, at
`test_client_consent_gate_3030.py:297` and `:631` and
`test_saas_client_consent_gate_3030.py:382` and `:657` — two per transport. All four were
**already passing at `bb2020fea`**. A green SC-010 is not evidence of this mission's work; the
requirement is that they keep passing, and they do.

### SC-021 — the two tracker behavioural tests

`[ratchet]`. Both were **already passing** before this mission. The requirement is that they keep
passing. They are collected by `fast-tests-sync` alone, which is why WP02 routed
`src/specify_cli/tracker/**` into the `sync` change-group — see [CI routing](#sc-006-and-fr-017--ci-routing-is-a-parser-reading-not-an-observed-run).

### NFR-004 — five per-branch pins, and all five already hold at `bb2020fea`

NFR-004 is a `[ratchet]`. The build work was **pinning** the branches; **the pins do not
discriminate a correct implementation from an incorrect one.** Reported per pin, measured in
process against `src/specify_cli/egress.py` at `HEAD`:

| # | Branch | Pin | Result |
|---|---|---|---|
| 1 | `DENIED` | contains `sync opt-in` (a concrete next action, not a bare "denied") | holds |
| 2 | import failure | carries the exception text (`{exc}` in `_IMPORT_FAILURE_TEMPLATE`) | holds |
| 3 | `NO_RESOLVER` | names the resolver | holds |
| 4 / 5 | `UNDETERMINED` vs `UNANSWERABLE` | both contain `could not be determined` and remain **distinguishable from each other** (correction C-1) | holds |

Pins 4/5 are the pair a weak assertion would wave through, so the distinguishability check was
controlled: comparing `UNDETERMINED_PROJECT_REFUSAL` to itself returns `False`, so the check can
fail. The two rendered strings:

```
UNDETERMINED : the project that owns this data could not be determined, so its consent to
               hosted sync could not be resolved; refusing to transmit (an undetermined
               project is never a consenting one)
UNANSWERABLE : consent for the project at {project_root} could not be determined (the consent
               chain raised or answered with a non-bool); refusing to transmit, because
               inability to determine consent is not consent
```

### SC-019 / SC-020 — grep gates: presence measured, content read separately

Both are presence checks, and the spec's own honesty notes say so: *a file containing only the
three search terms passes*. The presence result is reported as a presence result.

```
SC-019  grep -rn "resolve_egress_consent\|ConsentedBatch\|project_egress_refusal" docs/adr/3.x/ docs/context/
        -> 5 hits, in docs/adr/3.x/2026-08-04-1-egress-consent-boundary.md
        CONTROL, a nonsense term over the same paths, must be 0 -> 0

SC-020  grep -ril engagement docs/context/
        -> docs/context/identity.md
        CONTROL, a nonsense term over the same path, must be empty -> empty
```

**Content is a PR-review item, and it was read rather than inferred from the green.** The ADR
carries all three things SC-019 names, as named sections: the boundary as one presentation
(`### 1. The boundary is one presentation: src/specify_cli/egress.py`), the provenance invariant
(`### 2. The provenance invariant …`), and that the attribution guard is syntactic
(`### 3. The attribution guard is SYNTACTIC — it is not an ownership proof`). It also carries its
own *"what this ADR does not prove"* section. `docs/context/identity.md`'s new `engagement` entry
defines the term and quotes the operator-facing refusal string verbatim.

That reading is recorded here as a reading. **It is not what the gate measured**, and a reviewer
should not treat this paragraph as a substitute for their own.

### SC-006 and FR-017 — CI routing is a parser reading, not an observed run

Every claim that WP03's discriminating module and WP02's routing edges *select the right jobs*
rests on `tests/architectural/_gate_coverage.py`'s parse of `.github/workflows/ci-quality.yml`
plus a reading of each job's `if:` expression. The model uses pytest's own expression evaluator
and the two agree — but **no CI run has been observed** (FU-I). See [what this mission did not
prove](#what-this-mission-did-not-prove).

---

## Docs lockfile reconciliation

This WP is the reconciler and it is last for exactly that reason: two shared 1:1 lockfiles over
`docs/**/*.md` cannot be owned by two lanes at once. WP06 added the ADR and edited
`docs/context/identity.md` and deliberately landed lockfile-dirty; this page is the second added
document. Both rows are reconciled here.

**There are two lockfiles, not one.** `docs/development/3-2-docs-retrieval-index.yaml` was in no
work package's `owned_files` and in no lane's `write_scope` (FU-N). Its drift is `severity=error`
via `DOCS-INDEX-DRIFT` and reds `docs-freshness` exactly as the page inventory does, and
`freshen_adr_inventory.py` contains **zero** references to it — verified by grep, not assumed. It
needs its own command.

### Baseline, re-measured rather than transcribed

The WP prompts state a 685/685 baseline. Measured in a clean detached worktree at
`985ae6484` — the tree immediately before the mission's squash merge:

```
docs/**/*.md                                689
3-2-page-inventory.yaml committed rows      689
3-2-docs-retrieval-index.yaml committed rows 689
check_docs_freshness: exit=0 findings=0 errors=0 warnings=0
docs_structural_lint: checked 689 page(s); 0 violation(s).
freshen_adr_inventory --check --all: STALE (missing_rows=1 inventory_stale=False)
```

**689, not 685**, in both rulers. The number moved upstream between design and implementation
(FU-O); it is not pre-existing drift. Note the last line: **one ADR was already missing its era
README row at baseline** — see [what was deliberately not
fixed](#one-pre-existing-gap-left-alone-on-purpose).

### Before

Asserted in process at `HEAD 673a718f0`, immediately before writing:

```
docs/**/*.md                                 691   (baseline 689 + WP06's ADR + this page)
3-2-page-inventory.yaml committed rows       689
3-2-docs-retrieval-index.yaml committed rows 689
docs/adr/3.x/README.md index-table rows       94   (the ADR absent: 0 matches)
```

**Five error rows, not the three the WP prompt implies:**

```
ERROR LEAK-MISSING-INVENTORY     docs/adr/3.x/2026-08-04-1-egress-consent-boundary.md
ERROR INVENTORY-INCOMPLETE       docs/adr/3.x/2026-08-04-1-egress-consent-boundary.md
ERROR INVENTORY-LOCKFILE-DRIFT   docs/adr/3.x/2026-08-04-1-egress-consent-boundary.md
ERROR DOCS-INDEX-DRIFT added     docs/adr/3.x/2026-08-04-1-egress-consent-boundary.md
ERROR DOCS-INDEX-DRIFT changed   docs/context/identity.md
check_docs_freshness: exit=1 findings=5 errors=5 warnings=0
```

The first three are three separate rules reporting the same missing page-inventory row, so the
remediation is unchanged. **This page's own row does not appear** in the before-state because the
page did not exist when that measurement was taken; it was added by the same regeneration.

The `changed` row on `docs/context/identity.md` is the `engagement` anchor FR-023 requires. WP06
measured that the `updated`/`related` frontmatter bump contributes nothing to that row;
**independently confirmed here at the lockfile level** — the regenerated retrieval index's diff for
that page is exactly one added line and no deletions:

```
+    - {slug: "engagement", text: "engagement", level: 3}
```

Across the whole retrieval-index diff: **67 insertions, 0 deletions.** The index schema carries
`title` / `divio_type` / `abstract` / `anchors` and not `updated` or `related`, which is why the
frontmatter bump is invisible to it and the anchor is the entire cause.

### The two commands

`freshen_adr_inventory.py` reconciles the page inventory **and** the era README table.
`docs_index.py` reconciles the retrieval index, which `freshen_adr_inventory.py` **does not touch
at all** — grep over that script returns zero references to `docs_index` or the retrieval index.
Both need `PYTHONPATH=.`.

```
$ PYTHONPATH=. python scripts/docs/freshen_adr_inventory.py \
      docs/adr/3.x/2026-08-04-1-egress-consent-boundary.md
README-ROW-ADDED 2026-08-04-1-egress-consent-boundary.md
freshen_adr_inventory: rows_added=1 inventory=regenerated

$ PYTHONPATH=. python scripts/docs/docs_index.py --write
docs_index: exit=0 generated=691 committed=691 drift=False (added=0 removed=0 changed=0)
```

The ADR's exact filename was taken from the tree, not guessed — `git diff --name-status`
against the baseline shows exactly one added file under `docs/adr/`. The explicit path was used
rather than `--all` deliberately: `--all` would also have written the pre-existing missing row.

### After — `drift=False` is the evidence, with its counts

*Taken at `b07d7896b`* (originally measured on a dirty tree over `673a718f0`, which is not a
reachable object; re-taken at the commit so a successor can reproduce it).

```
inventory_lockfile: exit=0 generated=691 committed=691 drift=False (added=0 removed=0 changed=0)
docs_index:         exit=0 generated=691 committed=691 drift=False (added=0 removed=0 changed=0)

docs/**/*.md                                 691
3-2-page-inventory.yaml committed rows       691
3-2-docs-retrieval-index.yaml committed rows 691
docs/adr/3.x/README.md index-table rows       95   (the ADR present: 1 match)
this page present in the page inventory       1
this page present in the retrieval index      1
```

`691 = 689 + 2`, and the two are WP06's ADR and this page. No other page landed.

**The gates:**

```
check_docs_freshness: exit=0 findings=0 errors=0 warnings=0
docs_structural_lint: checked 691 page(s); 0 violation(s).
description_length_check: checked 542 page(s); 0 violation(s).
related_validator: checked 942 edge(s); 0 dangling.
```

**Input counts alongside the greens** — `inventory_rows_count = 691` from the report JSON, 691
pages walked by the structural lint, 691 markdown files under `docs/`. A caution on that JSON: its
`visible_paths_count` and `reference_entries_count` fields read like input counts and are not —
`:460` computes the first as *the number of `REF-*` findings* and `:421` the second as *the number
of findings in the CLI-reference payload*. Both are `0` here because there are **no findings**, not
because nothing was checked. **Do not quote either as an input count**; `inventory_rows_count` is
the only genuine one in the payload.

### One pre-existing gap, left alone on purpose

`freshen_adr_inventory.py --check --all` reports a second missing era-README row:

```
ADR-README-ROW-MISSING 2026-07-29-1-lane-base-recorded-planning-commit.md
```

**It is pre-existing**, measured at `985ae6484` where it is the *only* missing row and the
inventory is otherwise clean. `ADR-README-ROW-MISSING` is **not** one of
`check_docs_freshness`'s rules, so it does not red `docs-freshness` and did not red the 689/689
baseline. It was **not fixed here** — it is another mission's row, and running `--all` to sweep it
up would have made this work package's diff quietly larger than its scope. Recorded instead of
silently absorbed or silently ignored.

**Nothing was weakened, skipped, or allowlisted to get there.** A lockfile made green by exempting
its rows is the vacuous case, and it would have been indistinguishable in the output from this
one.

---

## Measurements that were wrong, and were re-taken

The greens above are the less instructive half of this record. These are the failures of
measurement — recorded because in the output they are indistinguishable from real results.

### Taken during this work package, and mine

| What happened | How it was caught | Disposition |
|---|---|---|
| **Nine reds in `tests/architectural/test_gate_coverage.py`** under the system interpreter — 1 failure and 8 setup errors, every one reporting `/usr/bin/python: No module named pytest` from a subprocess. It looks exactly like a broken guard. | Controlled against a known answer. `_gate_coverage.py:1146` sets `env["HOME"] = tempfile.mkdtemp(...)` for isolation; the system interpreter's `pytest` lives in `~/.local/lib/python3.14/site-packages`, i.e. the **user site**, which a replaced `HOME` makes unresolvable. Verified directly: `HOME=$(mktemp -d) python -c "find_spec('pytest')"` → `False`; the same probe in the 3.11 venv → `True`. | **Not a defect. An invalid measurement** — the same shape as the mission's method note: *a path that was not the one the measurer believed*. Re-measured in venvs where `pytest` is `HOME`-independent: **`37 passed` on 3.11 and `37 passed` on 3.14** — the second of those on the **same interpreter version** as the failing run, `3.14.4`, differing only in where `pytest` lives. That is the controlled attribution: one variable changed, nine reds gone. |
| **`-p no:randomly` would have produced `EXIT=4`** — a pytest usage error, not a test result — because `pytest-randomly` is not installed here. | Checked plugin presence **before** running, not after seeing a red. | Flag removed before any measurement was taken. This is the exact shape of the mission's *"pytest reds that were `EXIT=4` usage errors from a syntax-broken plant"*. |
| **A killed run.** The 3.11 sweep was killed at exactly 10m00s — the harness timeout, not a test timeout — part-way through `test_gate_coverage.py`, with only progress dots and no `F` or `E` on the line. | Elapsed time was compared against the timeout **before** attributing anything, because `exit 143` is ambiguous between a timeout, a signal and a pipeline artefact. `pytest.ini` carries `addopts = --tb=short` and **no `--timeout`** (FU-6, re-measured OPEN), so a slow run consumes a run rather than failing it. | **A killed run is neither a pass nor a fail.** Re-run narrowed to the seven remaining files, in the background, with no harness timeout. The partial output is quoted nowhere as evidence — and note that the re-run **overwrote** it, so the exact dot count is no longer verifiable and is deliberately not stated. What matters is that it was **re-run, not explained**. |
| The summary extractor that reads `N passed` out of each output file. | Controlled on a purpose-built file with one passing and one failing test **before** being pointed at real runs. It reported `1 failed, 1 passed` and `rc=1`. | A green-only extractor would have silently converted every red below into a pass. It does not. |
| **`freshen_adr_inventory.py --check` reports `missing_rows=0`** with no paths and no `--all` — a green over an **empty target set**. | Controlled by re-running the same command with `--all`, which returned `missing_rows=2`. | **A sixth proof that could not fail, in the tooling rather than in a test.** `--check` alone is not a verification of the ADR index; `--check --all` or `--check <path>` is. Recorded because the bare form is the one a reader reaches for. |
| The `is_dir()` EACCES probe used to attribute the 3.14 ownership failures. | Its **CONTROL row is a readable directory**, asserted to return `True` on both interpreters before the `0o000` row was read; euid checked as non-zero so the branch is reachable at all. | Without the control, "3.14 returned `False`" is indistinguishable from a probe that returns `False` unconditionally. |
| **A control that did not fire, and was not waved away.** Because this page is itself an indexed doc, every edit to it can re-dirty the retrieval index — so each editing round was followed by a drift check *expected to be dirty* before regenerating. One round came back `drift=False` **before** regeneration, which is what a broken detector looks like. | Explained from the schema rather than assumed benign: the index carries `title` / `divio_type` / `abstract` / `anchors` only. The round that drifted had added new `###` **headings** (new anchors); the round that did not had added only body prose under existing headings. And the detector was already **proven able to fire** earlier the same session — it reported `DOCS-INDEX-DRIFT changed` for this page, then `drift=False` after `--write`. | The correct reading of a silent control is *"find out why"*, not *"good"*. Here the silence was correct. **The order matters and is easy to get backwards**: regenerate the lockfiles **last**, after the page content is final, or the page you just edited drifts the index you just wrote. |

### Corrections to the WP prompt's own stated numbers and paths, re-measured here

| Prompt says | Measured | Where |
|---|---|---|
| `docs_structural_lint` baseline **685 pages, 0 violations**; `inventory_lockfile` **685/685** | **689 pages, 0 violations** and **689/689**, `check_docs_freshness: exit=0 findings=0` | At `985ae6484`, in a clean detached worktree. The number moved upstream between design and implementation (FU-O). |
| "Two pages are added by this mission and both rows are yours" ⇒ three error rows | **Five error rows.** `LEAK-MISSING-INVENTORY`, `INVENTORY-INCOMPLETE` and `INVENTORY-LOCKFILE-DRIFT` all name the ADR; `DOCS-INDEX-DRIFT added` names the ADR and `DOCS-INDEX-DRIFT changed` names `docs/context/identity.md`. | The first three are separate rules cleared by the same page-inventory regeneration, so the remediation is unchanged. Five where three were expected is **not** a new defect. |
| Styleguide at `src/doctrine/styleguides/built-in/common-docs.styleguide.yaml` | That path **does not exist**. The live file is `packs/built-in/styleguides/common-docs.styleguide.yaml`, and it is the path `.github/workflows/docs-freshness.yml` passes to `--styleguide`. | The cited line numbers still resolve correctly in the real file. |
| WP06 "edits two `docs/context/` pages" | **One.** `git diff --name-status` shows only `docs/context/identity.md` under `docs/context/`. | Consistent with there being exactly one `DOCS-INDEX-DRIFT changed` row. |
| `python scripts/docs/inventory_lockfile.py --write docs/development/3-2-page-inventory.yaml` | Runs, but **contradicts the module's own stated contract**: `inventory_lockfile.py:24-25` says *"This module never writes to `docs/` or to the inventory"*, and `--write`'s help reads *"(never docs/)"*. Nothing enforces it — `:416-419` writes wherever it is pointed. | The sanctioned writer of that lockfile is `freshen_adr_inventory.py`, which regenerates it *and* the era README table. That is what was used. |
| `python scripts/docs/…` with no `PYTHONPATH` | Both `inventory_lockfile.py` and `docs_index.py` die on import with `ModuleNotFoundError: No module named 'scripts'` unless `PYTHONPATH=.` is set. The workflow sets it; the prompt's commands omit it. | — |
| `docs-freshness.yml` is "the **one** workflow with no base-branch filter" | It is **one of three**: `canonical-producer-lint.yml`, `docs-freshness.yml`, `plugin-validate.yml`. Partition over all 17 workflow files: **8 base-branch-filtered + 3 PR-triggered-unfiltered + 6 not PR-triggered**. | The substantive point still holds — `docs-freshness` **would** have red on a per-lane PR, and no lane opened one. But it is **not** escape-proof: its job carries `if: !contains(labels, 'pr:deferred') && !contains(labels, 'pr:skip-ci')`, so a label does skip it. No lane reached for one. |
| — *(my own probe, not the prompt's)* | My first pass at that partition reported `docs-freshness.yml` as **not PR-triggered**, because `on: pull_request:` with an **empty body** parses to `None` and my condition tested `pr is not None`. | Caught by making the partition **exhaustive** — `8 + 3 + 6 = 17` — instead of printing only the matches. A filter that silently drops a case looks identical to a case that is not there. |

### Taken earlier in the mission — attributed, not mine

These come from the mission's own method note in `follow-ups.md` and from the operator's WP07
dispatch. They are recorded because they are the mission's most transferable output, and
attributed because this page did not measure them.

- **Five invalid verifications shared one shape: an exit status or a path that was not the one
  the measurer believed.** (i) `EXIT=$?` placed *after* a `$(...)` reported the command
  substitution's status, not the command's. (ii) pytest "reds" that were `EXIT=4` usage errors
  raised by a syntax-broken plant, never a test result. (iii) A reviewer whose shell `cwd`
  defaulted to a different lane than the one under review — for a full round.
  (iv) `HOME` replacement relocating `pytest` to the user site, producing **nine** spurious reds in
  `test_gate_coverage.py` — same interpreter in a venv gives `37 passed`. (v) Backticks inside a
  double-quoted shell string executing as command substitution.
- **THIS PAGE'S OWN EVENT RECORD IS A CASUALTY OF (v), AND THAT MATTERS FOR FU-Q.** WP07's
  `for_review` note in the append-only `status.events.jsonl` had its mechanism phrase deleted:
  it now reads *"hangs off  under resolved.is_dir()"*. The event log cannot be rewritten, so
  **this page and `follow-ups.md` are authoritative for FU-Q**, not the event note. The claim
  survived; only the mechanism was lost, which bounds the damage but does not remove it.
- **A sixth instance, and it is in the tooling rather than a measurer:**
  `freshen_adr_inventory.py --check` **without `--all`** reports `missing_rows=0` over an
  **empty target set** — a gate that passes because it inspected nothing. `--check --all`
  reports `missing_rows=1`, rc=1.
- **The method that caught all of them: assert the environment *in process*, before measuring.**
  `assert LANE_C in ownership.__file__`; `git rev-parse HEAD` compared against the expected
  commit; an anti-vacuity assertion placed **before** the value being reported. Every measurement
  on this page follows it, which is why each one names its tree and interpreter.
- **A red attributed to the wrong assertion, and reported as proof that a fix worked.** The run
  really was red; the assertion that produced the red was not the one the fix touched.
- **Five instances of *a proof that could not fail*** — including **two anti-vacuity controls that
  were themselves vacuous**. This is the mission's signature defect, and it is why every check on
  this page that could be vacuous carries an explicit control whose result is quoted alongside it.

---

## Conditionality ledger — what a successor must re-take

| Evidence | Conditional on | What that means |
|---|---|---|
| Any full-suite green on this surface | **`#3115`** — OPEN, sync half deferred to `#3136` (FU-G) | Not attributable. **Only the T038 isolated single-file runs count**, and no full-suite green is claimed on this page. |
| Any green from `test_egress_consent_boundary.py` on a **moved sink** (WP03) | **`#3113`** | `_transmits_a_body` derives `kwargs` solely from `node.keywords`, so a fully positional `poster(url, data, headers)` is not classified as a sink. **`#3113` is CLOSED by non-adoption, not deferral** (FU-D): the matcher tightening was *declined* at a measured cost, and two positional shapes are pinned `xfail(strict=True)`. The blind spot survives by decision. |
| **The attribution guards** (`test_client_consent_gate_3030.py`, `test_saas_client_consent_gate_3030.py`) | **Nothing — explicitly not `#3113`** (R-12 / D-10) | They match by class name and count every match regardless of call form. **Do not re-take these**, and do not credit any coverage claim here to `#3113`. Their real bound is the **literal class-name match**: an aliased import, a factory, or an injected transport is invisible to them, and both modules say so in the constant next to the floor. |
| SC-006's `[one-off]` CI observation (WP02/T015) | **Necessarily post-merge** | `ci-quality.yml` is itself the first entry of the `core_misc` glob list, so any PR editing it selects `fast-tests-core-misc` *for that reason*. A `core_misc`-green run on the mission PR is a **tautology that looks exactly like proof**. See [post-merge carriers](#post-merge-carriers). |
| Observing the `specify-cli-rest` shard execute | **Necessarily post-merge** (FU-I) | See [post-merge carriers](#post-merge-carriers). |
| A killed or timed-out run | **FU-6** — re-measured OPEN | `pytest.ini` has no global `--timeout`, so a hang consumes a run rather than failing it. One killed run occurred here and was re-run narrowed. |
| **`test_ownership_3111.py`'s green** | **The interpreter** — it is a **3.11/3.12 green only**, and note the sharper form: **no CI job runs the test suite on 3.13+.** CI *does* provision 3.13 in two jobs — `build-wheel` (`ci-quality.yml:3848`) and `clean-install-verification` (`:3898`) — and **neither runs pytest** (verified by parsing both job bodies; census across 17 workflows is 3×`3.11`, 58×`3.12`, 2×`3.13`). An earlier draft said "CI runs only 3.11/3.12", which was false **and understated the exposure**: `clean-install-verification` imports `specify_cli` and runs `spec-kitty next` on 3.13, so 3.13 is a supported surface that no suite covers | `33 passed` on 3.11; `2 failed, 31 passed` on 3.14, same `pytest 9.0.3`. The two failing tests are correct and the module under test is wrong on 3.13+. **Do not re-take this as a flake and do not widen the tests to accept `()`** — see [the divergence the 3.11 run actually found](#the-divergence-the-311-run-actually-found--and-it-points-the-other-way). Open, escalated, and **filed as [#3177](https://github.com/Priivacy-ai/spec-kitty/issues/3177)** so it has an owner past this dossier. |
| WP04's containment checks against a bind mount | **Nothing will fix this at this level** (FU-E) | `mount --bind` is transparent to `realpath`, needs root to arrange, and is indistinguishable from a copy at the VFS layer, so there is no second path to compare against. **Reasoned, not measured.** An inherent limit of path-based containment, not a defect. |
| `_repo_relative` / `_saas_site_attribution` / `_tracker_site_attribution` pins | **A helper-bypass bound** (FU-M) | Each helper is single-source by construction, which is what lets its pin fail. A future edit that *re-implements* rather than *calls* one of them is outside what any runtime assertion can observe. **No action implied** — recorded so the pins are not mistaken for coverage of that case, and not "strengthened" in a way that cannot work. |

---

## What this mission did not prove

Stated positively, because a limit recorded as an absence is a limit nobody finds.

1. **No CI run was observed.** The entire CI-routing model — SC-006, FR-017, WP02's two change-group
   edges, the `cli` disjunct on `fast-tests-core-misc` — is a **parser reading of workflow YAML**
   plus a reading of each job's `if:`. The parse and the reading agree. Neither is a run.
2. **The `specify-cli-rest` shard was never watched executing** (FU-I). Every claim that WP03's
   discriminating module *runs* rests on the model above.
3. **No full-suite green exists for this mission**, by design (`#3115`). Every green here is an
   isolated single-file run.
4. **Bind-mount invisibility is reasoned, not measured** (FU-E).
5. **`#3113`'s all-positional blind spot is open by decision** (FU-D). Non-adoption is the
   resolution, not a deferral — a successor should not read it as pending work.
6. **The grep gates (SC-019, SC-020) prove presence, not content.** Content is a PR-review item.
7. **The `[ratchet]` criteria prove continuity, not construction.** SC-004 clauses 1–2, SC-010,
   SC-021 and all five NFR-004 pins already held at `bb2020fea`. Only SC-004 clause 3
   discriminates.
8. **`acceptance-matrix.json` is an unpopulated stub** at `HEAD` — every criterion reads
   `pending` with `"notes": "TODO: replace with a real acceptance criterion"`. It is not this work
   package's file and was not edited; noted so nobody reads it as a verdict.
9. **This mission halts at design for `#3113` and `#3115`.** Neither is fixed here. This page is
   where Bundle A's cost is written down.
10. **Nothing was measured on 3.12.** CI runs 3.11 **and** 3.12; only 3.11 was built and run here,
    which is what NFR-006 asks for in executed form. 3.12 shares 3.11's `is_dir()` EACCES
    behaviour according to `ownership.py`'s own docstring table — **that is a reading of someone
    else's measurement, not one taken here.**
11. **The 3.13+ ownership defect is reported, not fixed.** WP07 writes no source and no tests. Its
    remedy is escalation, and it is open at the time this page was written.

---

## Post-merge carriers

**Three** obligations survive the merge. Two have homes; the third does not yet, and is named
here precisely so its homelessness is on the record rather than discovered later.

### 0. `tracer-tooling-friction.md` — NO HOME YET

Charter standing order 3 asks for a friction tracer. The dossier has
`tracer-evidence-base.md` and `tracer-squad-findings.md` and **not** this one. WP07's contract
assigns creating it to the orchestrator **after this WP merges**, and `finalize-tasks` rejects
the `owned_files` entry that would let WP07 write it — so it could not be created here even
deliberately. Recorded as a third surviving obligation rather than left to be noticed.

The raw material already exists: the five invalid-measurement instances above, plus the
empty-target-set gate, are exactly what a friction tracer is for.

### 1. SC-006's `[one-off]` half — folded into the repo

The carrier is the **docstring of
`test_ci_quality_workflow_file_is_itself_a_core_misc_glob`**, which reds if the confound ever
disappears. It states what is owed, why the mission PR cannot supply it, why the stacked-PR
substitute is inoperative, the procedure
(`packs/built-in/procedures/post-merge-arch-gate-adjudication.procedure.yaml`) and an
accept/reject condition checkable by a stranger.

It is **necessarily** post-merge: `.github/workflows/ci-quality.yml` is itself the first entry of
the `core_misc` glob list, so any PR editing it selects `fast-tests-core-misc` **for that reason**
— a tautology that looks exactly like proof. This is not a deferral for convenience; the
in-mission observation is structurally unobtainable.

### 2. Observing the `specify-cli-rest` shard actually execute (FU-I)

Owed, unowned by any pre-merge step, and the last inch of WP03's routing claim. Watching that
shard run is what converts the parser reading into an observation.

---

## Friction tracer

Consolidated from `follow-ups.md` (the implementation-phase record) plus this work package's own
measurements. Full text and falsifiers live in
`kitty-specs/egress-refusal-consolidation-3110-01KYW895/follow-ups.md`; this is the index a
successor reads first.

### Filed upstream — not this mission's code

- **FU-A** — `active_job_keys` does not gate on `on.pull_request.branches`. Pre-existing, and it
  errs toward **over-approximating** selection, the direction that makes a positive assertion
  easier to pass. Harmless for every assertion this mission makes; noted so it is not
  rediscovered as a WP02 defect.
- **FU-B** — the dead qualname comparison in both `invocation/adapters.py` registrars: both arms
  assign `fn`, so the comparison changes only the path taken to an identical assignment. WP05
  corrected the docstring that misdescribed it and left the code, because this seam was scoped to
  be **kept and pinned**, not refactored.
- **FU-C** — the upstream ownership-validator defect: the documented "planning-artifact WP that
  legitimately owns nothing" has a docstring and a regression test but **no path to a green run**
  — the manifest builder drops any WP with an empty ownership list and the lane computer then
  treats the missing manifest as a hard error.
- **FU-P** — a profile-wrapper contradiction: `curator-carla`'s generated wrapper carries a
  read-only "Hard boundary" clause contradicting WP06's own `role: implementer` /
  `execution_mode: code_change`. Reported rather than silently resolved. Looks like a
  reviewer-slot default leaking into an implementer dispatch; file against the profile generator.

### Carried residuals — recorded, not fixed

**FU-D** (`#3113` non-adoption) · **FU-E** (bind mounts) · **FU-F** (SC-015's scan scope diverged
from the spec and was reconciled *toward* the spec; **the spec and the WP contract still disagree
in text**) · **FU-G** (`#3115`'s sync half open, deferred to `#3136`) · **FU-M** (the
helper-bypass bound). Each is in the [conditionality
ledger](#conditionality-ledger--what-a-successor-must-re-take) with what it does and does not
bound.

### Residual remediation, frozen under an explicit operator decision

All four were found by review, graded LOW, and are fail-closed. None is a fix-round item.

- **FU-J** — *a regression introduced by a fix, stated plainly.* LOW-4 re-keyed the remedy onto
  `unreadable_ledgers` alone, which correctly fixed the likelier EACCES-mixed row — but that
  tuple **conflates malformed with unreadable** (the module's own docstring says so at
  `ownership.py:87-89`), so a corrupt-ledger operator is now told to `chmod u+rx`, where no mode
  bit is wrong. Measured on both the corrupt-JSON and schema-invalid rows. Same
  wrong-operator-action class as LOW-6/7/1, **moved rather than removed**. Net still a win, and
  the point of recording it is that *"I fixed the diagnosis"* was the claim and it was only
  two-thirds true.
- **FU-K** — the AST guard's try-context rule ignores the handler type: `try: p.stat()` /
  `except ValueError:` satisfies it while `OSError` still escapes. No live defect (all three real
  handlers catch `OSError`), and the docstring states what is implemented rather than
  overclaiming.
- **FU-L** — `unreadable_ledgers` is a published field with mixed-kind contents: it now carries
  mission-*directory* names as well as ledger names and is exposed under that key in the
  `--dry-run` payload. LOW-2 corrected the prose; the field name and JSON key were not touched, so
  a machine consumer parsing it as ledger paths still gets a wrong answer.
- **FU-N / FU-O** — the second lockfile and the stale baseline. Both discharged by this work
  package; see [Docs lockfile reconciliation](#docs-lockfile-reconciliation).

### Found by this work package — open, and escalated rather than absorbed

- **The 3.13+ `is_dir()` regression in `ownership.py:387-403`.** LOW-8's recording of a dropped
  mission candidate hangs off `except OSError`, and on 3.13+ `Path.is_dir()` swallows EACCES
  instead of raising, so the drop is never recorded and the operator is told *"no missions were
  found … run `git pull`"* for a permission problem — LOW-8's original defect, verbatim. Green on
  CI's interpreters, wrong on the only locally installed one. Fail-closed either way; a diagnosis
  defect, not a consent leak. **Owner WP04, which is `approved`, so the route is escalation.**
  Full analysis, mechanism probe and candidate fix: [the divergence the 3.11 run actually
  found](#the-divergence-the-311-run-actually-found--and-it-points-the-other-way).
- **A pre-existing missing ADR era-README row** (`2026-07-29-1-lane-base-recorded-planning-commit.md`),
  measured at baseline, outside `check_docs_freshness`'s rule set, deliberately not swept up. See
  [one pre-existing gap](#one-pre-existing-gap-left-alone-on-purpose).
- **`freshen_adr_inventory.py --check` is vacuous without `--all` or a path** — it reports
  `missing_rows=0` over an empty target set. Tooling, not test code, and the same shape as the
  mission's five proofs-that-could-not-fail.

### Tooling friction met while producing this page

- `pytest` collection costs roughly **50–60 s per invocation** on this tree before a single test
  body runs, so nine isolated single-file runs cost about nine minutes in fixed overhead alone.
  `tests/architectural/test_gate_coverage.py` is far worse: it spawns a `--collect-only` subprocess
  **per CI gate** over the whole test tree.
- With no global `pytest` timeout (FU-6), that cost is what turns a harness timeout into a
  **consumed run** rather than a failure — the mechanism behind the one killed run recorded above.
- `scripts/docs/inventory_lockfile.py` and `scripts/docs/docs_index.py` are not runnable as bare
  scripts; both need `PYTHONPATH=.`.
- `check_docs_freshness.py` fails closed with `ENV-SAAS-SYNC-OFF` (exit 3) unless
  `SPEC_KITTY_ENABLE_SAAS_SYNC=1` is set **at import time**. A run missing it is not a clean run;
  it is no run.
