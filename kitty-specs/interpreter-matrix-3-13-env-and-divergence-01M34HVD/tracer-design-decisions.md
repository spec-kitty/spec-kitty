# Tracer: Design Decisions

Seeded at spec authoring (2026-09-22). Scan-fast format — decision, one-line
rationale. Full narrative reasoning is in `tracer-approach.md`.

## Operator-mandated scope decisions

| Decision | Chosen | Rationale (one line) |
|---|---|---|
| Q1 — mission scope once the leg runs on 3.13 | **B**: fix flags + fix the 4 confirmed kernel `dir_fd` failures, same mission | Operator overrode the readiness probe's narrower recommendation (A) — small, well-diagnosed fix; avoids handing over a newly-red leg with a known cheap fix left undone. |
| Q2 — shared-venv mid-run corruption finding | **B**: in-scope for #4866, root-cause (or timeboxed fallback) here | Operator overrode the probe's recommendation to file it separately (A) — it's plausibly a real CI hazard (shared `.venv`), not just a sandbox artifact, and directly contaminates this mission's own measurement. |

## The four tensions

| Tension | Resolution | Rationale (one line) |
|---|---|---|
| (a) Q2-B is an unbounded investigation | Bounded spike: `-k`-scoped reproduction against named suspect subsystems, one sized WP at plan time (not this spec); fallback = interim `UV_PROJECT_ENVIRONMENT` pinning mitigation + follow-up issue with evidence if timebox exhausted | Commits to a contract (bounded, evidenced, non-silent) without inventing an arbitrary wall-clock number that belongs to plan/tasks sizing. |
| (b) Venv-corruption fix changes the 429 count | Mission re-measures `fast or unit` on 3.13 AFTER the venv fix/fallback lands (FR-004/SC-004); 429 is explicitly retired as a planning baseline | 429 is contaminated by a second, independent defect (per readiness report); scoping decisions must use clean data. Charter's full-suite-run reservation is scoped to `pytest tests/`, not the `fast or unit` selector this re-measurement uses — exemption applies narrowly, stated explicitly. |
| (c) Residual red after all 3 fixes, from other genuine 3.13 divergence | File the residue against #3189; accept an honestly red leg if residue exists — do NOT claim/imply "nightly turns green" | #3189 already exists as the workflow's own declared home for above-3.12 divergence beyond this job's claimed scope (its own inline comment says so); an honest red is correct charter doctrine (§9), a false green would not be. |
| (d) No CI safety net for the workflow-file diff | Every acceptance scenario names its exact local-repro command or manual `workflow_dispatch` step; spec states plainly no PR check will validate this change | Verified directly: `ci-nightly.yml` triggers on `schedule`/`workflow_dispatch` only. Silently assuming CI coverage that doesn't exist would itself be a silent-success failure. |

## Requirement-shape decisions worth flagging for later reviewers

- **FR-005 (pre-existing failure reporting) resolved to option (a)**: open a
  fresh issue for the 21 pre-existing 3.11 failures. #3284 is CLOSED and
  cannot serve as the open report the charter rule requires; #4866 itself
  reports the environment defect, not these 21 failures as their own
  tracked item. Chosen over silently treating #3284+#4866 as sufficient,
  which the mission brief flagged as NOT obviously sufficient and required
  a real decision on.
- **ATDD test shape for the workflow-YAML fix (C-004) named concretely**: a
  test that parses `ci-nightly.yml`'s YAML and asserts the
  `interpreter-matrix` job's `uv run` step carries `--python`/`--all-extras`
  (or `--no-sync`), shown RED on the current file and GREEN after the fix —
  per the mission brief's explicit instruction not to hand-wave this
  charter C-011 obligation for a "just a workflow flag" change.
- **Standing Order 4 classification made explicit**: the `dir_fd` test
  doubles are classified as a **stale test double** (3.13's `shutil.rmtree`
  legitimately changed; the shim didn't model the new kwarg) — not
  git-blame'd, not assumed, reached on the cited `TypeError: ... got an
  unexpected keyword argument 'dir_fd'` evidence per Standing Order 4's own
  "judge the test, not git-blame" instruction.
- **NFR-002 exists specifically to close the reflexive silent-success loop**:
  named explicitly in spec.md's Reflexivity section — the bug this mission
  fixes IS a silent-success instance (uv silently rebuilt the environment);
  the fix must not introduce a new one.

## Plan-authoring decisions worth flagging for later reviewers

| Decision | Chosen | Rationale (one line) |
|---|---|---|
| Plan template shape | Author against the canonical `packs/built-in/missions/software-dev/templates/plan-template.md` (Charter Check, Implementation Concern Map), not the `spec-kitty plan --json` scaffold it actually produced | The scaffold was stale (wrong doc-note path, "Constitution Check", "Parallel Work Organization") — flagged as a live spec-kitty tooling defect rather than silently followed. |
| Venv-corruption spike timebox | 3 hours wall-clock OR 5 `-n auto` reproduction attempts, whichever first | ~411s/attempt × 5 ≈ 34 min of repro time, leaving headroom within 3h for grep/cross-reference/`-k`-narrowing steps; a concrete number was owed at plan time per Edge Case (a). |
| FR-003(b) fallback regression check's home | `tests/upgrade/test_migration_robustness.py` (beside `test_concurrent_upgrade_handled`), not a step alongside the `ci-nightly.yml` fallback change | The check is inherently dynamic (before/after a real `-n auto` run); belongs beside the test that first surfaced the hazard, exercised by the same selector, not only asserted as a static CI-YAML fact. |
| "Coverage-floored shards (kernel ≥90%, mission-loader ≥90%)" gate framing | Reframed to the actual mechanism: `ci-aggregate.yml`'s single diff-cover ≥90% critical-path gate | No per-module named floor or `mission-loader` module exists in `.github/ci-module-registry.yml` — verified live rather than assumed from the dispatch brief's phrasing. |
| Bandit/pip-audit/commitlint/markdownlint gate status | Stated as NOT enforced (blocking) in live CI, contra `docs/configuration/linting-cutoff-policy.md`'s claim for Bandit/pip-audit | Live workflow files verified directly; the doc disagrees with the code — a doc defect per the charter's docs doctrine, flagged not silently trusted. |
| #3283 (pytest shared test-venv lock) framing | Stated as CLOSED/COMPLETED (2026-09-08), not an active capacity ceiling | Verified live via `gh issue view 3283`; the dispatch brief's framing predates the fix. |

## Correction to the "Plan template shape" row above (post-plan adversarial review)

- The row above calls the scaffold mismatch a "live spec-kitty tooling
  defect." Adversarial review of plan.md (finding PLAN-ARCH-001, round 1;
  reconfirmed as PLAN-FRESH-002 when this file itself was found still
  carrying the misdiagnosis) traced the actual cause live: this checkout
  carries a git-tracked project-tier override at
  `.kittify/overrides/missions/software-dev/templates/plan-template.md`
  (last touched 2026-04-17) that still has the exact stale shape the row
  above describes, and OVERRIDE is the documented highest-priority
  template-resolution tier (`src/charter/activation/template_resolver.py`,
  `src/charter/offering/resolver.py`,
  `docs/architecture/mission-system.md`), ahead of the canonical
  `packs/built-in/` template (updated 2026-08-15). The `plan` command
  resolved exactly as designed; the defect is a stale, never-re-synced
  project-tier override, not a live `plan`-command defect. Left as-is
  above rather than edited, per this tracer file's append-only discipline —
  this entry is the correction. plan.md's "Tooling drift flagged" section
  and its Standing Order 6 bullet, and tracer-tooling-friction.md's own
  appended correction note, carry the same corrected diagnosis.

## WP02 — dir_fd shim widening: forward the kwarg, don't try to resolve through it

Both fixed shims (`_WindowsMandatoryLockSimulator.wrap_open`'s inner `_open`
in `tests/kernel/test_lock_parity.py`, and `plant_symlink` duplicated in
`tests/kernel/test_no_follow.py` / `tests/specify_cli/core/test_no_follow.py`)
now take `dir_fd: int | None = None` (keyword-only, matching stdlib
`os.open`'s own signature) and forward it verbatim to the wrapped/real
`open` call. Deliberately did **not** attempt to make
`_WindowsMandatoryLockSimulator`'s locked-path bookkeeping `dir_fd`-aware:
`resolved = str(Path(path).resolve())` still resolves `path` against the
process cwd, which is technically wrong when `path` is relative and
`dir_fd` is set (the correct resolution would be relative to the fd's
directory). This is safe in practice because the only caller that ever
passes `dir_fd` here is `shutil.rmtree`'s fd-relative directory walk during
`tmp_path` teardown, by which point every test's locks are already
released and `self._locked_paths` is empty — so the mis-resolved string
never collides with a real entry. If a future test starts exercising
`dir_fd` opens *while a lock is actually held* (not just at teardown), this
resolution gap would need fixing properly (thread `dir_fd` through
`os.path.join`-style resolution, or track by `(dir_fd, name)` pairs
instead of an absolute string). Not needed for this WP's scope (FR-002 /
NFR-003), which is teardown-only; flagging for whoever touches this shim
next.

## WP03 — asserting flag position, not just presence

The ATDD test (`tests/ci/test_interpreter_matrix_env_pinning.py`) does not
just check that `--python` and `--all-extras` appear somewhere in the
`uv run` step's `run:` string — it isolates the substring BEFORE the
`pytest` command word (`re.search(r"\bpytest\b", run_str)`) and asserts the
flags are inside that prefix specifically. This was deliberate, not
incidental: `uv run`'s CLI grammar passes every token after the `pytest`
command word straight through to pytest, so a broken variant with the
flags appended AFTER `pytest -m "fast or unit" ...` would still contain
both substrings anywhere-in-string while being functionally identical to
the original defect. Verified live (not just reasoned about): edited the
already-fixed workflow file in place to move `--python "${{
matrix.python-version }}" --all-extras` to AFTER the existing pytest
arguments (keeping both flags present in the file, just in the wrong
position), re-ran the test, and confirmed the same load-bearing assertion
failed for the same reason (`--python` not found in the prefix before
`pytest`) as it did against the original unfixed file — then restored the
correct fix and reconfirmed GREEN. This is the concrete evidence behind
the "assertion avoids passing on the broken form" requirement, not an
assumption.

## WP03 — T005 local repro used --collect-only, not a full `fast or unit` run

T005 (per its own written validation criterion) only needs to prove the
FIXED environment collects on real 3.13 with the `test` extra present —
"pass/fail counts are informative but not this WP's concern... this
subtask only needs to confirm the *environment* is now correct, i.e. no
`ModuleNotFoundError` collection errors." The mission dispatch's SK-99
section separately and explicitly says there is "no reason to run `fast or
unit`" (cites an 84-minute figure) and to report before any full-suite run.
Reconciled by running the exact fixed command pair with `--collect-only -q`
appended instead of a full execution: `uv sync --frozen --all-extras
--python 3.13` then `uv run --frozen --python 3.13 --all-extras pytest -m
"fast or unit" --collect-only -q`, both under `UV_PROJECT_ENVIRONMENT`
pointed at the pre-built `.venv313` (never touching the checkout's pinned
3.11 `.venv`). Result: 34831/45053 tests collected (10222 deselected by the
marker filter) in 17.65s, zero `ModuleNotFoundError`, zero collection
errors, `.venv313/lib64/python3.13/site-packages` confirmed in the
traceback/warning paths shown. This satisfies T005's actual acceptance
criterion without the ~411s+ full execution the dispatch asked to be
reported first — flagged as a discrepancy in the WP03 report rather than
silently picked.

## WP04 — chose containment over silently claiming closure for the venv-corruption fallback

The dispatch's Branch B framing ("Pin `UV_PROJECT_ENVIRONMENT`... so the
leg's environment cannot be rebuilt out from under it regardless of which
test misbehaves") reads as a claim of full closure. Direct reproduction
(three separate `-n auto`/bare-`uv` attempts, all with the pin exported the
entire time) disproved that reading: the pin changes *which* path a nested
unpinned `uv run --frozen` rebuilds, not *whether* it rebuilds. Rather than
landing the literal instruction and letting the completion report imply the
hazard is closed, chose to: (a) land the pin anyway, since it is genuinely
useful containment (protects the primary dev `.venv` and any other
concurrent consumer of the default path) and is plan.md's binding fallback;
(b) document the gap prominently in the landed code comment, the regression
test's class docstring, this tracer, and the follow-up issue, rather than
only in one place a future reader might miss; (c) design the regression
test around what is actually true (a well-pinned invocation is stable) plus
a static presence check, instead of a dynamic "run the real hazard and
expect green" test that would either misleadingly always pass (by excluding
the known culprits) or legitimately never pass (by including them, since
fixing them is out of this WP's scope). This is the same "falsified
hypothesis" discipline Debugger Debbie's profile calls for: the venv-pin
hypothesis as a *complete* fix is falsified with direct evidence, not
assumed correct because it matches the dispatch's prose.

## WP04 — Branch A vs Branch B boundary extended by analogy, not by new authority

The WP prompt only writes out one out-of-scope exception explicitly (a
named call site under `src/`). It says nothing about a named call site
under `tests/` but outside this WP's own `owned_files`
(`tests/upgrade/**`, `tests/specify_cli/upgrade/**`,
`tests/specify_cli/skills/**`) — which is exactly what both confirmed
culprits turned out to be (`tests/charter/**`, `tests/docs/**`). Rather than
treating the absence of an explicit rule as license to fix them directly
(small, well-understood, one-line-flag changes), applied the same
underlying rationale the `src/` exception encodes — this WP's authority to
land a fix is scoped to its declared `owned_files`, and a fix outside that
scope risks colliding with another lane's ownership or silently widening
this WP's footprint — and treated it as the same class of exception.
Flagged this reasoning explicitly rather than silently picking either
branch, per the dispatch's instruction to report discrepancies with the WP
prompt.

## WP04 scope extension (operator-authorized, was #4922) — chose `--no-sync` over `--python`/`--all-extras`, verified empirically on uv 0.11.28

The operator lifted the out-of-scope boundary WP04 drew (see the two entries
above) and authorized fixing the two named call sites
(`tests/charter/test_interview_mapping_mission_alias.py:107`,
`tests/docs/test_docs_index.py:197`) inside this mission. Rather than reason
from uv's documentation about which flag closes the hazard, reproduced all
three candidates directly against a scratch `UV_PROJECT_ENVIRONMENT`
(`.venv-fix`, under this checkout's own `/home`-backed root — never `/tmp`,
never the checkout's `.venv`/`.venv313`/`.venv312`) pinned to Python 3.12,
deliberately mismatched against the repo's `.python-version` (3.11.15):

1. **Bare `uv run --frozen python -c ...`** (the pre-fix shape): confirmed
   the hazard live — `pyvenv.cfg` flips from 3.12 to 3.11.15, "Removed
   virtual environment" / "Creating virtual environment" printed, extras
   dropped (64 packages vs. the full `--all-extras` sync). This reproduces
   WP04's finding directly against these two call sites' actual shape rather
   than a synthetic stand-in.
2. **`uv run --frozen --no-sync python -c ...`**: `pyvenv.cfg` byte-identical
   before/after. uv prints a stderr warning ("Using incompatible environment
   ... due to `--no-sync`") but still runs successfully against the
   mismatched env — it does not sync, full stop, regardless of interpreter
   mismatch. Also verified `--no-sync` composes cleanly with
   `test_docs_index.py`'s custom `env=` (`PYTHONHASHSEED` override): a
   direct subprocess run with `PYTHONHASHSEED=4242` and `--no-sync` printed
   `SEED=4242` back, confirming the flag does not touch the environment
   mapping, only skips uv's own sync step.
3. **`uv run --frozen --python 3.12 --all-extras python -c ...`**: also left
   `pyvenv.cfg` untouched (matches WP04's already-landed positive control),
   but requires the call site to hardcode/discover the "correct" interpreter
   version, and still nominally permits a sync if uv decided the env were
   stale — it constrains sync, `--no-sync` forbids it outright.

Chose `--no-sync` for both call sites: neither test wants ANY resync — both
just want to invoke `python` inside the project environment the outer
pytest process is already running in. `--no-sync` is the literal expression
of that intent and needs no version constant to keep in sync with
`.python-version` bumps. Verified with a nonexistent target env too:
`--no-sync` still creates a bare (dependency-free) venv if none exists
rather than erroring — a non-issue here since both call sites always run
nested inside an already-synced outer process, but recorded for completeness.

Landed as its own commit after a RED-first hazard test
(`tests/upgrade/test_migration_robustness.py::TestVenvCorruptionHazardFR003b::test_named_call_site_argv_does_not_rebuild_a_mismatched_dedicated_venv`)
that extracts each call site's real `uv run` argv via AST (not a hand-copied
duplicate) and runs it against a scratch mismatched-version venv — RED
before the fix (both parametrizations), GREEN after, confirmed red again on
a `git stash`/`stash pop` revert-check that restored the working tree
byte-for-byte (`git status --porcelain` clean throughout).

## WP05 — `-n auto` chosen deliberately for the re-measurement, with the comparability caveat stated, not hidden

Chose `-n auto` over serial for the FR-004 re-measurement, matching WP05's
own prompt and `plan.md`'s IC-05 command. This was a deliberate choice, not
just prompt-compliance: this WP doubles as Deliverable 2, the first
full-scale exercise of WP04's venv-corruption fix, and that fix's entire
purpose is protecting interpreter identity specifically under `-n auto`
parallel execution — the exact condition under which the corruption
originally manifested (spec.md User Story 3). A serial run would answer
"does the leg still have the same failures" but would never stress the
hazard WP04 fixed at all, defeating half of this WP's purpose. The
trade-off: WP01's 3.11 control baseline was run serial (by its own prompt's
instruction, for its own separate good reason — isolating that baseline
measurement from the then-unfixed corruption hazard). This WP05 run and
WP01's baseline therefore differ in parallelism as well as interpreter
version. Judged this acceptable because the actual comparison this WP
produces is a **node-ID set diff**, not a wall-clock or ordering
comparison — a test either failed by name or it didn't, and parallelism
differences don't change which specific tests a deterministic assertion
fails on (no such drift was in fact observed: the 20/20 baseline-failure
match was exact). Recorded the caveat explicitly in
`evidence-remeasurement-3.13.md` rather than silently comparing across
settings as if they were equivalent.

## WP06 — Filed a comment on existing #3189 rather than opening a new issue

WP06's dispatch and prompt both allow either "comment on #3189" or "open a
new issue cross-linked to #3189, if #3189's own scope doesn't cleanly
absorb the findings." Read #3189 live before deciding (not assumed from the
plan/spec's snapshot): its title/body is "no CI job runs pytest above Python
3.12, so interpreter-divergence defects are invisible to the gate" —
exactly the class of the 3 residual findings (interpreter-only divergence
found by running `fast or unit` on 3.13, a version no pre-#4866 CI job
exercised). Judged #3189's scope absorbs these findings cleanly; no new
issue was opened. Comment posted:
<https://github.com/spec-kitty/spec-kitty/issues/3189#issuecomment-5782934410>.

## WP06 — Included an isolation-sensitivity finding for one of the 3 residual IDs, not just the full-run failure

`test_human_output_shows_valid` failed in WP05's full `-n auto` `fast or
unit` run (the canonical re-measurement) but passed 3/3 times when re-run
standalone against `.venv313` during WP06's cheap targeted verification.
Decision: report both facts in the #3189 comment and the evidence file,
rather than only the full-run failure (which would be incomplete) or
discounting the finding because it didn't reproduce in isolation (which
would understate it — the real `ci-nightly.yml` job runs the full parallel
selector, not an isolated subset, so the full-run failure is what the leg
will actually observe). No cause is asserted for the isolation-sensitivity
itself; recorded as an observed fact only, per WP06's mandate not to
speculate about root cause beyond what the failure output supports.

## Post-merge pre-merge-squad fix (pr-merged-004) — recorded the venv-absent gap rather than adding a live-subprocess test for it

The pre-merge adversarial squad (finding `pr-merged-004`, confirmed by an
independent refuter) noted that `uv run --frozen --no-sync` silently
creates an EMPTY ad hoc venv when `UV_PROJECT_ENVIRONMENT` points at a path
that does not exist yet — reproduced by the refuter: exit 0, no warning,
`ModuleNotFoundError` for every project dependency inside it.
`TestVenvCorruptionHazardFR003b` covers present+correct
(`test_a_well_pinned_nested_uv_run_leaves_a_dedicated_venv_untouched`) and
present+wrong-version
(`test_named_call_site_argv_does_not_rebuild_a_mismatched_dedicated_venv`),
never the absent-target branch.

Decision: record the gap here and in the test module's docstring rather
than add a fourth live-subprocess characterization test for it, for two
reasons. First, the behavior under test is `uv`'s own (a third-party tool),
not any spec-kitty `src/` code this mission may touch (zero `src/` lines is
this WP-fix dispatch's explicit boundary) — a passing test would pin uv's
current behavior, not verify anything spec-kitty controls, and would need
re-verification against every future uv upgrade regardless. Second, this
mission's own operating constraints explicitly forbid triggering a network
interpreter download; while the absent-venv-creation branch itself should
not need one (uv falls back to the already-resolved `.python-version`
pin), a fresh `UV_PROJECT_ENVIRONMENT` path is exactly the kind of
first-touch operation most likely to trigger metadata/interpreter
resolution over the network on an unfamiliar host (e.g. a GitHub runner),
which is a materially different risk profile than the two existing hazard
tests (both of which build against interpreters already known-resolvable
locally). Weighed against `pr-merged-004`'s own severity (2, non-blocking,
"either cover or record"), recording was judged the safer default. The gap
is not a live regression risk for THIS mission's fix: neither of the two
call sites this WP's `--no-sync` fix touches
(`tests/charter/test_interview_mapping_mission_alias.py`,
`tests/docs/test_docs_index.py`) sets `UV_PROJECT_ENVIRONMENT` itself —
both inherit it unchanged from the ambient process environment (via
`env=dict(os.environ)` or no `env=` override at all), so at runtime they
always target whatever venv is ALREADY populated: the interpreter-matrix
job's own per-interpreter dedicated venv (created by that job's earlier
`uv sync --frozen --all-extras --python ...` step, before either nested
call ever runs) in CI, or this checkout's own default `.venv` locally.
Neither call site can encounter an absent target in practice — so the
absent-branch gap is real in `uv`'s general behavior but does not undermine
the containment this WP already verifies for its own two call sites.
