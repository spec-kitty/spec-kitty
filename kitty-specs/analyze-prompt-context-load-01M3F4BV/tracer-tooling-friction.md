# Tracer: tooling friction — analyze-prompt-context-load-01M3F4BV

## Scaffold — known transient global-cache race (documented, expected)

`.venv/bin/spec-kitty agent mission create ...` failed twice in a row with:

```
RuntimeError: Global asset input changed: /home/<user>/.kittify/cache/agent-commands-freshness.lock
```
```
RuntimeError: Global asset input changed: /home/<user>/.agent/workflows/spec-kitty.analyze.md
```

This matches the known transient race on this shared host (another mission elsewhere touching
the same global agent-commands cache concurrently), per the mission brief. Retried per
instructions.

## Self-inflicted duplication (operator error, not a tool defect)

On retry, instead of retrying once and checking the result, a `for i in 1 2 3; do ...; done`
loop was run without checking after the first iteration succeeded. All three loop iterations
succeeded (the transient race had cleared), producing **three** mission scaffolds
(`analyze-prompt-context-load-01M3F4BV`, `-01M3F4CB`, `-01M3F4CX`) and three auto-commits on
`fix/analyze-prompt-context-load-5005`, violating the "scaffold exactly once" instruction.

Recovered by inspecting `git log --oneline` (three sequential "Add scaffold for feature ..."
commits on top of the mission's base), then:

```bash
git reset --hard a15e136ef   # the first (01M3F4BV) auto-commit
rm -rf kitty-specs/analyze-prompt-context-load-01M3F4CB kitty-specs/analyze-prompt-context-load-01M3F4CX
```

This is a self-correction of an operator (agent) scripting mistake on a branch nobody else had
touched — not a `spec-kitty` tool defect, and not a workaround of a refusal. Recorded here for
honesty and so a later reader does not mistake the surviving single scaffold
(`analyze-prompt-context-load-01M3F4BV`) for anything other than the first, clean,
correctly-created mission.

## Live-render measurement

No friction: `.venv/bin/python` (synced venv) successfully imported
`runtime.next.prompt_builder.build_prompt` and `specify_cli.runtime.resolver.resolve_command`
directly and rendered all 8 measured actions without error. Two non-fatal
`CharterCatalogMissWarning`s were emitted during rendering (`java-conventions` styleguide and
`maven-review-checks`/`typescript-mutation-tools` toolguides scope-filtered for the active
Python language set) — pre-existing charter-catalog noise unrelated to this mission's diagnosis,
not investigated further here.

## Plan phase (2026-09-26)

**Stale `.venv` — `pytestarch` missing (AGENTS.md category 4, stale-venv false red).** Before
running any baseline tests, `.venv/bin/python -m pytest tests/architectural/...` failed at
collection with `ModuleNotFoundError: No module named 'pytestarch'` — the synced venv in this
checkout was stale relative to `pyproject.toml`/`uv.lock`. Fixed with
`uv sync --frozen --all-extras` per AGENTS.md's own documented remedy; re-run then collected
and ran cleanly. Recorded as friction because it would otherwise have been misclassified as a
pre-existing failure in the merge-base baseline run that followed.

**Baseline-worktree test run — stale global `spec-kitty` shadowed the venv's own console
script (AGENTS.md category 3, stale-install false red).** Running
`tests/architectural/test_doctrine_regenerate_graph_roundtrip.py` in the separate
merge-base worktree (`git worktree add ... da6d0af97eb1291cb08d4d0a6772cdfc43df4496`)
initially failed: `shutil.which("spec-kitty")` resolved a global `~/.local/bin/spec-kitty`
install (unrelated to either the mission checkout's or the baseline worktree's own `.venv`),
which then shelled out with `ModuleNotFoundError: No module named 'spec_kitty_events.diary'`.
Stripping that one `~/.local/bin` entry from `PATH` before the run let the test's own
documented fallback (`python -m specify_cli`) take over, and the suite passed cleanly
(72/72). Recorded because a future baseline run on this same shared host will hit the same
false red unless it also excludes the stale global install from `PATH`.

**`spec-kitty agent tracer-append`'s canonical target path does not match this mission's
existing tracer-file convention.** Checked via `--help` and by reading
`src/specify_cli/retrospective/tracer_writer.py` before use (per the mission brief's
instruction to check whether it fits). It targets `kitty-specs/<mission>/traces/<category>.md`
(a `traces/` subdirectory) and is hardcoded to route through the COORD partition
(`_DESTINATION_SURFACE = "coord"`), but this mission's `meta.json` declares
`"topology": "single_branch"` — a topology CLAUDE.md's own Execution Workspace Strategy
section says "route[s] everything to primary" (no coordination branch/worktree exists to
route to). Using the CLI here would likely have raised
`CoordinationWorktreeUnmaterialized` and, even if it had succeeded, would have created a
second, differently-named tracer surface (`traces/tooling-friction.md` alongside the existing
`tracer-tooling-friction.md`) inside the same mission. Not used for this reason; the tracer
files were edited directly instead. Worth a gap report for a future pass (not filed here —
out of this plan-phase agent's scope).

## Plan-revision pass (2026-09-26, Operator Decision 7)

**Stale `.venv` again — same category-4 (AGENTS.md) stale-venv false red as the prior
round.** `.venv/bin/python -m pytest tests/architectural/...` failed at collection with
`ModuleNotFoundError: No module named 'pytestarch'` before any test could run. The venv had
drifted again since the prior plan round (mission commits since then included the merge of
`origin/main`, which can shift `uv.lock`-adjacent state even without touching `pyproject.toml`
directly in this mission's own diff). Fixed the same way: `uv sync --frozen --all-extras`.
Re-run then collected and ran cleanly. Recorded again because this is now the second time
this exact false red has been hit in this mission, and a future pass on this same shared host
should expect to hit it a third time unless the sync step becomes a standing pre-check.

**Stale global `spec-kitty` shadowing the venv's own console script — same false red as the
prior round, hit again in the fresh `34b53d78e` baseline worktree.** Not re-investigated in
depth since the prior round's entry already documents the exact mechanism
(`shutil.which("spec-kitty")` resolving `~/.local/bin/spec-kitty` instead of falling back to
`python -m specify_cli`); the same remedy (stripping `~/.local/bin` from `PATH` before
invoking pytest, and before invoking `.venv/bin/spec-kitty` directly) was applied again this
pass, including for the direct `spec-kitty doctrine validate` / `regenerate-graph --check`
invocations run for the "Contracts touched" / "Generated artifacts" re-verification. Every
CLI invocation this pass used the checkout's own `.venv/bin/spec-kitty` or `.venv/bin/python`
with that one `PATH` entry stripped, per the mission brief's own hard rule never to fall back
to `~/.local/bin/spec-kitty` or bare `uv run`.

**`spec-kitty doctrine` subcommand now prints a deprecation warning (`use spec-kitty charter
instead`), non-blocking.** Both `spec-kitty doctrine validate` and
`spec-kitty doctrine regenerate-graph --check` still work exactly as spec.md/plan.md's
binding text requires (the companion-step instruction names `regenerate-graph` specifically,
not `charter`), but now emit a `DeprecationWarning` line to stderr/stdout ahead of their
normal output. Not acted on this pass — the binding text names the `doctrine` subcommand
explicitly and it is not yet removed, only deprecated — but worth flagging for whichever pass
implements FR-002, since the warning could be mistaken for an error by an agent not expecting
it.

**Baseline re-run (`34b53d78e` worktree) took noticeably longer than the prior round's
baseline (91s vs 15s for a smaller file count).** `tests/doctrine/test_directive_consistency.py`
carries a real, non-mocked directory scan and cross-reference check across every shipped
agent profile and directive
(`test_all_referenced_directives_have_matching_files_and_titles`, ~45s setup on this run) —
this is expected behavior for a corpus-wide consistency test, not a regression, and is noted
here only so a future baseline re-run on this same file set is not mistaken for a hang.

## Tasks phase (2026-09-26)

**`finalize-tasks --validate-only` false-positive on `FR-005` requirement mapping.** First
run failed with `{"error": "Requirement mapping validation failed", ...,
"unmapped_functional_requirements": ["FR-005"]}` even though this mission's spec.md has no
Functional-Requirements-table row for FR-005 at all (only FR-001..FR-004 are real rows).
Root cause traced to `src/specify_cli/requirement_mapping.py::_declared_ids`'s bold-bullet-
lead heuristic (`_BOLD_PARAGRAPH_LEAD_ID_PATTERN` / `_BULLET_LEAD_ID_PATTERN`), which treats
any line starting `- **FR-NNN` as a declaration of a requirement needing WP coverage —
regardless of whether the surrounding prose says the requirement is *out of scope*. spec.md's
"Remaining scope after Operator Decision 7" section has exactly one such line: `- **FR-005/006/007
(governance-context budget fix) stay out of scope per Decision 6, unchanged by Decision
7.**` — a line explicitly declaring FR-005/006/007 as dropped, not as build items, but the
parser's syntax-only heuristic has no concept of "in scope" vs "out of scope" and flags the
first id on that line as a real, uncovered functional requirement. Worked around (not routed
around dishonestly) by adding `FR-005` to WP01's `requirement_refs` with an explicit,
documented "this WP does NOT implement FR-005; listed only to satisfy the parser" note in the
WP prompt file — see `tracer-design-decisions.md` for the full reasoning. This is a genuine
tooling gap worth an upstream fix (the requirement-mapping parser could recognize an
explicit "out of scope" / "dropped" / "superseded" qualifier on the same declaring line and
exclude it from the unmapped-FR check), not something this mission's own scope covers —
noted here per this repo's tracer-file convention rather than silently worked around.

## Analyze phase (2026-09-27)

**This mission is itself live evidence for issue #5005 (agents routing around
`/spec-kitty.analyze` on an unverified size assumption).** This entry reports what actually
happened when the analyze phase was run for real, through the canonical override-tier
prompt, rather than an improvised substitute.

**Byte sizes, measured firsthand (`wc -c`), not assumed:**

- `.kittify/overrides/missions/software-dev/command-templates/analyze.md` (the file THIS
  checkout's 6-tier resolver actually resolves for `/spec-kitty.analyze`, OVERRIDE tier
  winning): **11,555 bytes**, confirmed via `wc -c` run directly by this agent, not copied
  from the mission brief's stated figure.
- Diffed against canonical `packs/built-in/missions/mission-steps/software-dev/analyze/prompt.md`
  with `diff` (not merely `cmp -s`): **zero output — byte-identical.** Canonical is also
  11,555 bytes (`wc -c` confirmed independently). This matches spec.md's own re-verified
  claim (post-#5133-merge) that all 10 software-dev command-template overrides are
  byte-identical to their canonical counterparts.
- `.kittify/charter/charter.md` (loaded per the analyze prompt's own §2 "Load Artifacts"
  instruction, "From charter: Load `.kittify/charter/charter.md` for principle validation"):
  **38,540 bytes**, 635 lines, `wc -c` confirmed.

**Total context actually held for this analyze pass, and whether it was a problem — reported
honestly, not hedged:**

- Analyze prompt: 11,555 B
- Charter: 38,540 B
- spec.md: 86,273 B (767 lines — the largest single file, heavily inflated by this mission's
  own seven-operator-decision supersession history, not by the analyze template)
- plan.md: 46,507 B (665 lines)
- tasks.md: 678 B
- WP01 prompt file: 25,222 B (387 lines)
- **Running total for the artifacts the analyze prompt's own contract requires: ~208,775
  bytes (~204 KB) across six files.**

**This was NOT a problem for this agent.** Every file was read in full (no truncation, no
"summarize instead of reading" shortcut), including the unusually large 86 KB spec.md (which
required two sequential Read calls purely because of this harness's own single-call line
cap, not because the content was too large to hold or reason about). Nothing was dropped,
nothing degraded, and the full ~204 KB combined did not approach any context ceiling this
agent hit. If anything, this mission's own spec.md is a better test case for "is a large
document actually a problem" than `analyze/prompt.md` ever was — at 86 KB it is nearly 8x
the analyze template's size, and it was still no obstacle. This is exactly the live
evidence #5005 asks for: the canonical prompt (11,555 B) is trivially loadable, the
governance context it pulls in (charter.md, 38,540 B) is not oversized either, and even the
mission's own outsized spec.md did not cause any real friction. The reported root cause in
spec.md — an agent that never attempted to load or measure the prompt before deciding it
was "too large" — is corroborated once again by this direct, first-hand experience of
loading everything the contract asked for without incident.

**`record-analysis`/verdict friction actually hit: less than expected, one notable
discrepancy from the ledger.**

- **No SK-06/SK-141/SK-185 carrier-shape friction.** The carrier was written with a literal
  `---` as line 1 character 1 and a literal `schema: analysis-findings/v1` key (not a legacy
  `schema_version`/`artifact_type` shape). `record-analysis` computed `verdict: ready` from
  the carrier's single LOW finding, exactly as expected — no silent `unknown`.
- **No SK-114/SK-22/SK-249 `DIRTY_WORKTREE` friction.** This was the mission's first
  `record-analysis` call this session; the worktree was clean before the call.
  `record-analysis` also self-verified clean afterward — no stash, no manual
  `analysis-report.md` pre-commit was needed.
- **No SK-32 absolute-path injection.** `input_artifacts[*].path` in the persisted report
  uses repo-relative paths (`kitty-specs/analyze-prompt-context-load-01M3F4BV/spec.md`,
  etc., plus `.kittify/charter/charter.yaml` for the charter entry) — confirmed by reading
  the persisted file back directly and by `grep -rn "/home/" analysis-report.md`, which
  found nothing. This known defect class did not manifest this run.
- **Discrepancy against SK-43 ("`record-analysis` does NOT commit its own output"):** on
  this run, `record-analysis` DID auto-commit its output — `git status --short` was clean
  immediately after the call, and `git log` showed a new commit
  (`docs(record-analysis): record analysis report for mission
  analyze-prompt-context-load-01M3F4BV`) already present, authored by the same identity
  prior commits on this branch use. No manual `safe-commit` was run or needed for this
  step, and none was performed (to avoid double-committing empty content). This is recorded
  as a live, first-hand observation that contradicts the ledger's SK-43 description as
  currently worded on this checkout/version (`spec-kitty` 4.0.0rc5) — either SK-43 has since
  been fixed, or it is narrower/conditional than the ledger entry states. Flagged here for
  the ledger sweep, not silently assumed away.

**Verdict, read back from the actual persisted file, not trusted from JSON alone:**
`grep -n "verdict" kitty-specs/analyze-prompt-context-load-01M3F4BV/analysis-report.md` →
`verdict: ready` (line 22). One LOW-severity finding (C1: WP01's `requirement_refs` cites
FR-005, which has no Functional-Requirements-table row in spec.md — already documented
extensively in WP01's own Context section and Definition-of-Done table, tracked upstream as
issue #5065). No MEDIUM/HIGH/CRITICAL findings. `ready` is the correct, non-forced verdict
for zero-high/critical findings, consistent with Step 4's binding rule for this mission.

## Analyze phase, round 2 (2026-09-27)

Fresh re-derivation (no memory of round 1) against the current tree, HEAD = `dfa2ae7ab`
(the fix commit for round 1's single LOW finding, C1), before this round's own commits.

- **C1 independently confirmed closed.** Round 1 found WP01's `requirement_refs`
  (`kitty-specs/analyze-prompt-context-load-01M3F4BV/tasks/WP01-unverified-size-assumption-doctrine.md`
  frontmatter) cites FR-005 with no corresponding row in spec.md's Functional Requirements
  table. `git show --stat dfa2ae7ab` confirms a surgical, +3-line-only diff to `spec.md`
  adding FR-005/006/007 rows (lines 724-726), each with exactly 6 `|` characters — a
  well-formed 5-column row matching the table's existing shape — each `Status: **Dropped**
  (Operator Decision 6 — out of scope, never executed)`, mirroring the pre-existing
  FR-001 `**Superseded**` convention and cross-referencing the "Known residual (out of
  scope): governance-context budget gap" section rather than re-narrating it. No other
  file was touched by the fix commit. Independent judgment: the three new rows read as
  coherent, correctly-shaped table rows; they introduce no new malformed row, no broken
  cross-reference, and no new duplication/ambiguity. WP01's FR-005 citation now resolves.
  **C1 is closed by this fix, confirmed independently, not merely trusted from the fix
  commit's own message.**
- **Full independent re-derivation, not a rubber-stamp.** Re-read `analyze.md` (the
  OVERRIDE-tier command template, `.kittify/overrides/missions/software-dev/command-templates/analyze.md`,
  11,555 bytes per `wc -c`, matching canonical byte-for-byte per this mission's own
  research), `.kittify/charter/charter.md` in full, and the current `spec.md`, `plan.md`,
  `tasks.md`, and WP01 file on disk. Ran the six detection passes (Duplication, Ambiguity,
  Underspecification, Charter Alignment, Coverage Gaps, Inconsistency) fresh. Cross-checked
  every DIRECTIVE_044/DIRECTIVE_052/C-011/`canonical-source-unification` citation against
  the live charter and the actual doctrine-source YAML files (confirmed: tactic's
  `failure_modes` has exactly 6 entries, directive's `procedures` has exactly 3, matching
  the spec/plan/WP01's "six/three today" claims — no drift, no charter conflict). Found
  zero new findings.
- **No new tooling friction hit this round distinct from round 1's already-recorded items.**
  `record-analysis` again auto-committed its own output on this mission
  (`abfd887ad docs(record-analysis): record analysis report ...`) — reconfirms round 1's
  first-hand discrepancy note against the ledger's SK-43 description ("record-analysis does
  NOT commit its own output"): on this checkout/version (`spec-kitty` 4.0.0rc5), it does.
  `git status --short` was clean immediately after the call; no manual `safe-commit` was
  needed or performed for the report itself. No `DIRTY_WORKTREE` refusal hit (SK-114/
  SK-22/SK-249 class). Carrier used the correct `analysis-findings/v1` schema (literal
  `---` at line 1, `findings: []`, `counts` all-zero) — no legacy-shape silent-`unknown`
  risk (SK-06/SK-141/SK-185 class) was hit, since the carrier was authored fresh this round
  rather than fed back from the previously-persisted (legacy-shaped) `analysis-report.md`.
  No SK-32 absolute-path injection this round either: `grep -rn "/home/"
  analysis-report.md` found nothing; `input_artifacts[*].path` values are repo-relative
  (`kitty-specs/.../spec.md`, `.kittify/charter/charter.yaml`).
- **Final persisted verdict, read back from disk, not trusted from the JSON response
  alone:** `grep -n "^verdict:" kitty-specs/analyze-prompt-context-load-01M3F4BV/analysis-report.md`
  → `verdict: ready` (line 22). `findings: []`, `issue_counts` all zero. This round is
  findings-free, meeting the round's own bar.

## WP01 implementation round (2026-09-27)

- **`spec-kitty doctrine regenerate-graph` (and `built_in_root()` generally) ignores the
  lane worktree's cwd and silently resolves against the editable install's own module
  location instead.** Running `spec-kitty doctrine regenerate-graph[--check]` from inside
  `.worktrees/analyze-prompt-context-load-01M3F4BV-lane-a` printed
  `<workspace>/packs/built-in` (the MAIN checkout root, not the
  worktree) and reported "fresh"/wrote there — confirmed by `stat`/`md5sum`: the main
  checkout's `tactic.graph.yaml` mtime advanced while the worktree's own copy stayed
  untouched, and `git rev-parse --show-toplevel` from the worktree correctly returns the
  worktree path (so it isn't a naive cwd bug — `charter.offering.pack_paths.built_in_root()`
  intentionally routes through an installed-module ancestor-walk per
  `doctrine-built-in-seam-consolidation-01KYW3TX` WP03, "an INTENTIONAL, called-out NFR-001
  behaviour delta, not a regression" per its own docstring). **Workaround found and used**:
  export `SPEC_KITTY_PACKS_ROOT=<worktree>/packs` before every `regenerate-graph`
  invocation — the kernel-floor `get_built_in_pack_root()` honors this override ahead of the
  ancestor walk. Without it, a lane-worktree WP that runs `regenerate-graph` believes it
  regenerated its own graph fragments when it actually mutated the primary checkout's copy
  (byte-identically in this WP's case, since `failure_modes`/`procedures` text isn't
  structural graph content, but a WP whose doctrine edit DID change a node's
  urn/kind/label/edges would silently commit a stale worktree graph while leaving a spurious
  untracked mtime bump on the main checkout). This is a real hazard for any future
  lane-worktree WP that touches DRG-source doctrine files and is not documented anywhere in
  CLAUDE.md/AGENTS.md/the charter.
- **`tests/architectural/test_doctrine_regenerate_graph_roundtrip.py::test_regenerate_graph_check_is_byte_identical`
  resolves `spec-kitty` via `shutil.which`, which finds a stale global
  `~/.local/bin/spec-kitty` (v3.2.7) ahead of the checkout's dev `.venv/bin/spec-kitty`
  (v4.0.0rc5) on `$PATH`.** Combined with the `SPEC_KITTY_PACKS_ROOT` workaround above, this
  produced a spurious RED (`DRG graph is stale`) that had nothing to do with this WP's
  doctrine edit — the stale v3.2.7 binary's extractor/calibrator logic disagrees with this
  checkout's dev code about what the regenerated graph should contain. Without
  `SPEC_KITTY_PACKS_ROOT` set, the same stale binary instead silently falls through to ITS
  OWN vendored `packs/built-in` (self-consistent, always "fresh") — meaning this
  architectural gate is **vacuous** for anyone whose `$PATH` puts a stale global
  `spec-kitty` ahead of the dev venv, in either direction (false green with no env override,
  false red with the worktree-scoping override). **Workaround used**: prepend
  `<checkout>/.venv/bin` to `$PATH` before invoking pytest for this test file. This matches
  CLAUDE.md's documented "stale-install false reds" category (#3) but that section only
  warns about commands the CLI shells out to (`merge-driver-*`); this is the same failure
  mode surfacing through a *test's* internal subprocess call, worth naming explicitly since
  the fix (`pip install -e .` per CLAUDE.md) doesn't apply — reinstalling wouldn't fix a
  `$PATH` ordering issue, only prepending the dev venv would.
- **`make lint` invokes `uv run --frozen ruff check src/`, and `make format-check` invokes
  `uv run --frozen ruff format --check .`; both silently created a brand-new, broken
  `.venv/` inside the lane worktree** (a `uv sync`-style resolve + build, landing without
  `ruff` installed at all — `error: Failed to spawn: ruff`) the first time either target was
  run from inside `.worktrees/analyze-prompt-context-load-01M3F4BV-lane-a`, rather than
  reusing the checkout's hand-built `.venv`. This directly reproduces the dispatch's own
  documented hazard ("NEVER a bare `uv run`, which destroys the hand-built .venv") one level
  removed — the *Makefile targets named as this WP's own required gates* are themselves thin
  `uv run` wrappers. **Workaround used**: ran the equivalent commands directly against the
  checkout's `.venv/bin/ruff` (`ruff check src/`, `ruff format --check .`) instead of `make
  lint`/`make format-check`, and deleted the stray worktree-local `.venv/` (gitignored,
  untracked, safe to remove) it had already created before switching. CLAUDE.md should
  either document this substitution for lane-worktree WPs or fix the Makefile targets to use
  the checkout's `.venv` instead of `uv run`.
- **A single-file `ruff format --check <path>` invocation bypasses `pyproject.toml`'s
  `[tool.ruff.format].exclude` list**, which is a documented shrink-only formatter-debt
  ratchet (issue #473) that currently still lists `tests/doctrine/test_directive_consistency.py`
  itself. Checking that one file directly reported `Would reformat` (a false alarm relative
  to the real gate), while the actual gate — whole-repo `ruff format --check .` — correctly
  skips the file per the ratchet and reports `2368 files already formatted` (exit 0). No
  format fix was needed or applied to this file; confirmed by running the same check against
  the pre-T001 committed version of the file (`git show 6fd106041:...`), which independently
  reproduces the identical "Would reformat" result — the debt predates this WP and is
  unrelated to the added test function.
- **`spec-kitty agent tasks move-task WP01 --to for_review` refused once** with
  `ACTIVE_WP_SCOPE_VIOLATION`-adjacent guard output: it detected that this WP's tracer-file
  updates (see above) had been committed on the LANE branch
  (`kitty/mission-analyze-prompt-context-load-01M3F4BV-lane-a`) instead of the planning
  branch (`fix/analyze-prompt-context-load-5005`), and refused with "kitty-specs/ changes
  are not allowed on lane branches." It suggested `git restore --source
  fix/analyze-prompt-context-load-5005 --staged --worktree -- kitty-specs/` — a command this
  WP's own operating rules forbid (`git restore` is on the never-run list). Resolved without
  running the forbidden command: read back each of the three tracer files' pre-commit
  content via `git show <planning-base-sha>:<path>`, wrote it back verbatim with the
  Write/cp tools (not git), and committed that as a new `chore:` commit on the lane branch —
  net effect identical to a revert, achieved with only sanctioned tools. The tracer content
  itself was then re-applied here, directly on the planning branch
  (`fix/analyze-prompt-context-load-5005`, this file), which is where `move-task`'s own error
  message says planning artifacts belong. `move-task` then succeeded cleanly on retry.

## WP01 rework round (2026-09-27, pr-contract-001/pr-tests-001 fix)

- **Re-confirmed the single-file `ruff format --check <path>` false alarm from the prior
  round (issue #473 exclude ratchet) against this round's OWN edits to the same file.**
  `ruff format --check tests/doctrine/test_directive_consistency.py` reported "Would
  reformat" both before and after this round's edits — but a first single-file `ruff format`
  run (before recognizing the ratchet) also silently rewrote seven UNRELATED pre-existing
  hunks elsewhere in the file (collapsing several multi-line asserts). Caught via
  `git diff --stat` showing 118 changed lines against an intended ~25-line addition, and via
  re-running `ruff format --check` against the pre-edit `HEAD` copy of the same file (also
  "Would reformat," confirming the drift predates this change). Manually reverted every hunk
  outside the new/changed test functions back to its committed form with Edit (not
  `git restore`, which is on this WP's forbidden list), keeping only the genuinely new lines.
  The correct signal is the whole-repo `ruff format --check .` (2368 files already formatted,
  exit 0) per the prior round's own tracer entry — a single-file invocation of this specific
  file is not a trustworthy gate and should not be used for it going forward.
- **`safe-commit` on the doctrine-content commit succeeded but emitted two
  `ACTIVE_WP_SCOPE_VIOLATION` warnings (non-blocking)** for
  `packs/built-in/agent_profiles/implementer-ivan.agent.yaml` and
  `packs/built-in/pack-manifest.yaml`, since WP01's original `owned_files` (set when the WP
  was first authored, before this rework) only lists the tactic/directive/graph files and the
  one test file. This is an EXPECTED, operator-authorized scope widening for this specific
  fix — the dispatch explicitly directed finding and editing whatever real, automatically-
  rendered surface exists, which turned out to be a different file than WP01's original scope
  anticipated — not a self-authorized exception. Recorded here per the "phase agents
  self-authorize exceptions" caution, and reflected in spec.md's corrected FR-002/SC-002 text
  (which now names `implementer-ivan.agent.yaml` as an additional companion-step target) so
  the widening is auditable rather than silent.

## Round-2 rework (2026-09-27, WP01 cycle-2 rejection): `--to planned` requires an
`/spec-kitty.analyze` re-run before `implement` will reopen

`spec-kitty agent action implement WP01 --agent claude --mission ...` refused with
`analysis_report_required: /spec-kitty.analyze must be run inside your coding agent ... stale
inputs: spec.md`, because `analysis-report.md`'s recorded content hash pre-dated the WP01
cycle-2 rejection's spec.md edits (commit `4f0e4fb4f`). The order chosen: fix spec.md's
internal contradiction first (WP01-C2-001/pr-FRESH-001 remediation, Decision 8), THEN run
`/spec-kitty.analyze` against the corrected spec (verdict `ready`, zero findings), THEN
`implement WP01` — rather than analyzing the still-contradictory spec first. This matches the
gate's own intent (don't let implementation resume against a spec analyze hasn't seen) and
avoided a wasted analyze pass that would have had to be re-run anyway.

`spec-kitty doctrine regenerate-graph` (write mode) failed twice more with the same
`Global asset input changed: <cache-file>` transient race documented above (a third, different
cache file each time: `agent-commands-freshness.lock`, then `agent-commands.lock`, then
`spec-kitty.analyze.md`), then succeeded on the third retry with no further changes made. Same
known, expected, self-clearing race as the scaffold-phase entry above — not investigated
further, per that entry's own disposition.

## `python-pedro` inherits DIRECTIVE_044 via `specializes_from`, not its own file — discovered
empirically, not assumed

Before editing `python-pedro.agent.yaml`'s own DIRECTIVE_044 rationale, the parametrized
reachability test was run standalone (test committed, profile edits not yet applied) to get a
genuine red-first baseline for all three then-unedited profiles (`architect-alphonso`,
`doctrine-daphne`, `python-pedro`). Only two failed. `python-pedro` already passed — not
because its own file's rationale mentioned the failure mode (it did not; confirmed by reading
the file), but because `packs/built-in/agent_profile.graph.yaml` declares
`agent_profile:python-pedro --specializes_from--> agent_profile:implementer-ivan`, and
`AgentProfileRepository.resolve_profile("python-pedro")`'s lineage union-merge resolves the
DIRECTIVE_044 citation to **implementer-ivan's** (already-fixed) rationale text, not
python-pedro's own — confirmed directly by printing `resolve_profile("python-pedro")
.directive_references` in an isolated `python -c` process (no prior resolution of any other
profile in that process) and finding implementer-ivan's exact rationale string attached to
code `044`, while codes unique to python-pedro (024, 025, 030, 034, 041) kept python-pedro's
own text. The same `specializes_from --> implementer-ivan` edge exists for `drupal-dries`,
`frontend-freddy`, `java-jenny`, and `node-norris` (none of which are in DIRECTIVE_044's
`directive-references` list directly, so this mission does not touch them), confirming this is
a real, by-design profile-lineage mechanism (documented in this repo's CLAUDE.md under
"`specializes_from` DRG Lineage"), not a test-ordering cache bug. python-pedro's own file was
still edited with the identical clause for source-of-truth correctness — SC-002/Decision 8
name it as one of "the four" — even though the rendered-reachability test was already green
for it via inheritance before that edit landed; this is recorded here so a future reader does
not mistake "test was already green" for "no edit was needed."

## Independent fresh `/spec-kitty.analyze` re-run (2026-09-27) — canonical prompt followed byte-for-byte, one genuine new finding

Dispatched as an independent ANALYZE agent (no prior authorship of this mission's artifacts) to
re-run `/spec-kitty.analyze` from scratch, because the previously-persisted `analysis-report.md`
(commit `afe2ae304`) was flagged defective by an independent fresh review pass (`reviews/pr-fresh-2.yaml`,
finding `pr-FRESH2-002`, sev 3: its own Metrics line inverted the dropped/superseded-vs-live FR
count and silently narrowed the Coverage Summary Table without reconciling "Total Requirements: 7").

Loaded `.kittify/overrides/missions/software-dev/command-templates/analyze.md` (confirmed
byte-identical via `diff` against canonical `packs/built-in/missions/mission-steps/software-dev/analyze/prompt.md`
before starting — both resolve to the same 9-step contract) and followed its contract exactly:
ran `spec-kitty agent mission check-prerequisites --json --include-tasks --mission
analyze-prompt-context-load-01M3F4BV` (valid, no errors/warnings); read spec.md (860 lines),
plan.md (664 lines), tasks.md, `tasks/WP01-unverified-size-assumption-doctrine.md`, `wps.yaml`,
the three WP01 review-cycle files, and `reviews/pr-fresh-2.yaml` for context on what the prior
squad already caught; the mission's `checklists/` directory is empty (no consistency checklist
artifact exists for this mission — not a defect, `/analyze`'s own contract does not mandate one).
Did **not** feed the previously-persisted report back as input (the known silent-`unknown`
trap this mission's own dispatch warned about) — authored the findings carrier fresh from a
first-principles re-read of spec.md/plan.md/tasks.md.

**New finding (F1, severity high, not previously flagged by any prior review round):** `plan.md`
was last revised 2026-09-26 for Operator Decision 7 (`git log`: commit `4b0492916`) and has never
been touched since. Operator Decision 8 (2026-09-27) and the WP01 round-2 rework it retroactively
authorizes widened FR-002's real scope to four agent-profile files plus `pack-manifest.yaml`'s
regenerated hashes plus a new test file (`tests/doctrine/test_directive_consistency.py`, two
parametrized tests) — all already shipped. `plan.md`'s "Seam"/"Contracts touched"/"Red-first
tests"/"Scale-Scope" sections still describe only the pre-Decision-8 two-doctrine-file scope and
design an entirely different (simpler, since-abandoned) test,
`test_size_assumption_bypass_failure_mode_documented`, with no acknowledgment anywhere that this
is now historical. Unlike WP01's `owned_files` frontmatter (which spec.md itself explicitly
documents as a deliberate, authorized non-edit), plan.md's drift carries no such acknowledgment —
genuinely unflagged, not a documented exception. Checked `reviews/*.yaml` for `plan.md` +
"Decision 8"/"stale"/"scope widen" hits: only round-2 plan reviews (dated before Decision 8)
matched, confirming this drift postdates every review round plan.md has been through.

Persisted via `spec-kitty agent mission record-analysis --mission
analyze-prompt-context-load-01M3F4BV --input-file <scratchpad-path> --agent claude --json` (input
file staged outside this repository checkout, per the prompt's own instruction). Recorded
`analyzer_agent: claude` (not `unknown` — passing `--agent` on this spec-kitty build,
4.0.0rc5, avoided the silent-`unknown` trap the dispatch warned about) and `verdict: blocked`
(the honest, arithmetic verdict for one HIGH finding — not suppressed to force `ready`). No
friction encountered: prerequisite check, artifact loads, and `record-analysis` all worked
against a clean worktree on the first attempt; the auto-commit landed as
`9c6c6ea23 docs(record-analysis): record analysis report for mission
analyze-prompt-context-load-01M3F4BV`.

## Second independent fresh `/spec-kitty.analyze` re-run (2026-09-27) — F1 (plan.md) confirmed fixed, one new finding in tasks/WP01

Dispatched as a second, independent ANALYZE agent to re-check whether the prior HIGH finding
(plan.md stale vs. spec.md's Operator Decision 8) was genuinely fixed by the intervening
`docs(plan)` sync commit, rather than assuming the fix landed cleanly. Confirmed
`.kittify/overrides/missions/software-dev/command-templates/analyze.md` byte-identical (`diff`)
to canonical before starting. Re-read spec.md, plan.md, tasks.md, and the WP01 prompt file fresh.

**Original F1 confirmed FIXED.** plan.md's Summary/Scale-Scope/Seam/Contracts-touched/
Generated-artifacts/Red-first-tests/PR-overlap/Project-Structure sections now fully name the
four `packs/built-in/agent_profiles/*.agent.yaml` files, the `pack-manifest.yaml` regeneration,
and the three shipped test functions — matching spec.md. Cross-checked against the actual
shipped code on the WP's own lane worktree (read-only `grep`, no writes there): the failure-mode
needle is present in all four agent-profile files' DIRECTIVE_044 `rationale` (two of the four
split the phrase across a YAML fold-line, which a naive single-line `grep -c` on this checkout's
own copy under `packs/built-in/agent_profiles/` would miss — verified by re-checking the
multi-line context, not by trusting the first grep), and the test file there defines all three
named test functions. plan.md's post-fix claims are accurate against the real, shipped diff.

**New finding (F1 this round, HIGH, category inconsistency):**
`tasks/WP01-unverified-size-assumption-doctrine.md` — the WP's own prompt file — was never
revised for Operator Decision 8 (`git log` on this one file shows no commit after the WP01
"Start WP01 implementation" commit that predates the round-2 rework). Its Objective, Context,
Subtasks T001-T004, Definition of Done, and Reviewer Guidance sections still describe only the
pre-Decision-8 single-doctrine-file, single-test design and never mention the four-profile
widening, the profile-citation render-path seam, `pack-manifest.yaml`'s regeneration, or the two
additional shipped test functions. This is the same defect class as the original F1 (an artifact
left behind when spec.md/plan.md were revised), just a different instance — and unlike WP01's
`owned_files` frontmatter (which spec.md explicitly documents as a deliberate, authorized
non-edit), this staleness in the WP prompt's body text carries no such acknowledgment anywhere.

**Tooling friction actually hit this round (worth recording — not self-inflicted):**

- **`record-analysis --report-only` crashes deterministically on a pre-existing, unrelated
  absolute-path leak in `.kittify/charter/charter.yaml`.** One `source_path` field (for the
  `TEMPLATE_SET:software-dev-default` DRG node, committed 2026-09-19 by a different contributor,
  predating this mission) is a raw contributor-machine-local absolute path
  (`/home/<other-contributor>/.../packs/built-in/missions/software-dev/mission.yaml`) rather than
  a repo-relative path, a `${SPEC_KITTY_PACKS_ROOT}/`-prefixed value, or a `://` URL —
  the three shapes `specify_cli/analysis_inputs.py::_source_paths`/`_safe_path` expect. Because
  `_source_paths` walks the whole charter dict for any `source_path` key and does `root / value`
  (which returns `value` unchanged when `value` is already absolute), `_safe_path`'s
  `path.relative_to(root)` then raises, and `collect_material_inputs` surfaces this as
  `MaterialInputError("External mutable analysis authority is unsupported")` — a message that
  reads like an intentional policy refusal, not what it actually is (a single stale path
  string). Reproduced directly in-process (`collect_material_inputs(feature_dir, repo_root)`)
  to get the real traceback rather than trusting the CLI's opaque error text. This is
  repo-wide and deterministic, independent of this mission's own diff or worktree cleanliness —
  it will break `--report-only` for any mission's `record-analysis` call on this checkout until
  either that one `source_path` value is corrected or the collector is made tolerant of a stale
  absolute path (e.g. treat it as `info`-only provenance rather than a material input, or skip
  non-repo-relative `source_path` values with a warning instead of a hard fail). Not fixed here —
  out of this mission's scope and not this agent's call to make (a different contributor's
  charter-bundle content, unrelated to analyze-prompt-context-load-01M3F4BV).
- **Concurrent read-only reviewers left two untracked review files in the primary checkout's
  `kitty-specs/.../reviews/` directory, uncommitted, for several minutes with no further
  activity** (`pr-verify-3.yaml`, `wp-WP01-cycle4.yaml`) — a live instance of the
  "subagents strand on own background work" pattern. This blocked plain (non-`--report-only`)
  `record-analysis` with `DIRTY_WORKTREE`, and `--report-only` (the tool's own designed escape
  hatch for exactly this "preserve concurrent work" scenario) was unusable due to the unrelated
  bug above. Waited (two bounded polls, ~5 minutes combined) rather than committing another
  agent's in-flight files unasked; the orchestrator ultimately committed those two files
  directly, unblocking this run. Recorded so a future analyze pass on a busy shared checkout
  expects this combination (stranded parallel output + a broken report-only escape hatch) rather
  than treating either symptom as this mission's own defect.

**Final persisted verdict, read back from disk, not trusted from the JSON response alone:**
`grep -n "^verdict:" kitty-specs/analyze-prompt-context-load-01M3F4BV/analysis-report.md` →
`verdict: blocked` (one HIGH finding, tasks/WP01 staleness above). `analyzer_agent: claude`
(not `unknown`). Auto-committed as
`a83b96fcf docs(record-analysis): record analysis report for mission
analyze-prompt-context-load-01M3F4BV`.

## Third independent fresh analyze re-run (post-fix verification, no findings)

Ran with a clean worktree, no concurrent reviewer left anything untracked this time. Re-checked
the F1 fix (commit `59c80d1b9`, `docs(tasks): sync WP01 prompt body to Operator Decision 8 and
the shipped implementation`) against spec.md/plan.md rather than trusting the commit message: WP01
body's Objective/Context/T001-T004/Definition of Done/Reviewer Guidance now name the widened
four-profile scope and three test functions, matching both spec.md (synced at `bb7a9defb`) and
plan.md (synced at `6c2024d3c`). Also re-verified the claimed "as shipped" content directly
against the actual bytes on the mission's lane branch
(`kitty/mission-analyze-prompt-context-load-01M3F4BV-lane-a`, not this planning checkout) rather
than trusting the prose — this planning checkout's own tracked files never carry the
`unverified size assumption` needle (implementation lives on the lane branch until merge, per
spec-kitty's coord/primary-vs-execution-workspace split; this is expected, not a defect, but
worth noting for a future analyze pass that a naive `grep` against the planning checkout alone
would produce a false "the shipped work doesn't exist" alarm).

Plain (non-`--report-only`) `record-analysis` was used per the mission brief, since
`--report-only` still trips the unrelated repo-wide `MaterialInputError` bug documented above.
Findings this pass: none. Persisted verdict, read back from disk:
`grep -n "^verdict:" kitty-specs/analyze-prompt-context-load-01M3F4BV/analysis-report.md` →
`verdict: ready`. `analyzer_agent: claude` (not `unknown`). Auto-committed as
`052aad609 docs(record-analysis): record analysis report for mission
analyze-prompt-context-load-01M3F4BV`.
