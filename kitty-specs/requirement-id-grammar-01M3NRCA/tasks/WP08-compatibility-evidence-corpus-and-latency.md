---
work_package_id: WP08
title: 'Compatibility evidence: corpus scan and latency micro-benchmark'
dependencies:
- WP06
- WP07
requirement_refs:
- NFR-001
- NFR-003
- C-007
- C-008
planning_base_branch: issue-2991-requirement-id-grammar
merge_target_branch: issue-2991-requirement-id-grammar
branch_strategy: Planning artifacts for this mission were generated on issue-2991-requirement-id-grammar. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-2991-requirement-id-grammar unless the human explicitly redirects the landing branch.
subtasks:
- T035
- T036
- T037
phase: Phase 4 - Compatibility evidence
history:
- at: '2026-09-29T06:22:20Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: researcher-robbie
authoritative_surface: kitty-specs/requirement-id-grammar-01M3NRCA/research/
create_intent:
- kitty-specs/requirement-id-grammar-01M3NRCA/research/corpus_scan.py
- kitty-specs/requirement-id-grammar-01M3NRCA/research/corpus-scan.md
- kitty-specs/requirement-id-grammar-01M3NRCA/research/latency_bench.py
- kitty-specs/requirement-id-grammar-01M3NRCA/research/latency.md
execution_mode: planning_artifact
model: claude-sonnet-5
owned_files:
- kitty-specs/requirement-id-grammar-01M3NRCA/research/**
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP08 – Compatibility evidence: corpus scan and latency micro-benchmark

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `researcher-robbie`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

Also run `.venv/bin/spec-kitty profiles show researcher-robbie` and `.venv/bin/spec-kitty charter context --action implement`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `.venv/bin/spec-kitty agent tasks status` or the Activity Log below).
- **You must address all feedback** before your work is complete. Feedback items are your implementation TODO list.
- **Report progress**: As you address each feedback item, update the Activity Log explaining what you changed.

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the Activity Log below or in the status event log.]*

---

## ⛔ HARD RULE: no heavy suites

Never run any of these:
- the whole `tests/architectural/` directory;
- e2e or full-integration suites;
- performance, stress or timing suites (the micro-benchmark in T037 is a standalone script, not a pytest suite; never set `SPEC_KITTY_RUN_PERFORMANCE=1`);
- `make test-full`;
- whole-repo `pytest`.

Run ONLY what `## Validation surface` lists: the two research scripts, and the one named architectural gate file. Always invoke tests as `PWHEADLESS=1 .venv/bin/python -m pytest -q <files>`. This is C-007, one of this WP's own `requirement_refs`.

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`,````bash`

---

## 🧭 Orchestrator overrides (take precedence over anything below)

- **Do NOT edit or commit anything under `kitty-specs/requirement-id-grammar-01M3NRCA/traces/`**, and do not commit any other mission-directory bookkeeping on the primary checkout. A dirty mission-dir file on the primary checkout blocks every WP's `move-task`. Put your tracer notes (tooling friction, approach changes, design decisions, each 1–3 dated sentences) in a `## Tracer notes` section of your final hand-off report. The orchestrator appends and commits them.
- **CLI:** always `.venv/bin/spec-kitty`, run from the repo-root checkout. In a lane worktree, run tests with `PYTHONPATH=$(pwd)/src <repo-root>/.venv/bin/python -m pytest …`, and confirm once that `specify_cli.__file__` resolves inside the lane. Never a bare `uv run`.
- **Commit** the `base_commit` that `implement` stamps into this WP's frontmatter before any state move.
- **HARD RULE: no heavy suites** (restated): run only the files and named gates in this prompt's Validation surface.

## Objectives & Success Criteria

This WP produces the committed compatibility evidence that NFR-001 and NFR-003 require. It changes no product code, no test and no other mission's files. It measures the mission's final behaviour (WP01–WP05) against the pre-mission code on the same inputs, and says honestly what changed.

1. **T035** – `research/corpus_scan.py`: a standalone, deterministic, read-only scan that runs the merge-base `src` and the head `src` over ONE shared file list, each in its own subprocess, and emits JSON plus a markdown summary covering NFR-001 (a)–(d).
2. **T036** – `research/corpus-scan.md`: the committed report. It records the commands, both SHAs, the counts and lists, and classifies every changed item as an **intended fix** or a **regression**. It also records the SC-005 positive control (the egress spec is still flagged, or why not).
3. **T037** – `research/latency_bench.py` + `research/latency.md`: an in-process micro-benchmark (not a performance suite) on a generated 30-WP fixture, with the median of 20 interleaved runs per side, and a verdict against NFR-003: head − base ≤ 50 ms, and the head total < 2 s.

**Done means:**
- both scripts run clean end to end, and the scan is byte-identical when run twice at the same SHAs;
- the four report files, plus their JSON outputs, are committed under `research/`;
- `test_bare_prose_corpus_ratchet.py` is green at the head;
- the throwaway merge-base worktree is removed, and `git worktree list` proves it;
- any regression or failed threshold is named in the hand-off, never hidden.

## Context & Constraints

Read these first:
- the charter: `.kittify/charter/charter.md`;
- in `kitty-specs/requirement-id-grammar-01M3NRCA/`:
  - `spec.md`: NFR-001, NFR-003, SC-005, C-007, C-008, C-009, the Edge Cases, and Assumptions (bullet 1: newly failing coverage in existing missions is the intended fix);
  - `research.md`: R1 (the erasure evidence), R4 (digit width, placeholders such as `FR-00N`), R5 (qualifier syntax), and the adversarial row "4 corpus specs would be refused";
  - `data-model.md` and `contracts/grammar.md`: the grammar API and the verdict table you classify against;
  - `plan.md`: IC-06 (this WP's concern);
  - `tasks/WP01-*.md`, `WP02-*.md`, `WP03-*.md`, `WP04-*.md` and `WP05-*.md`: the real API names the head exposes. WP05 owns `lint_spec_requirement_ids` in `src/specify_cli/requirement_mapping/lint.py`.
- `tests/architectural/test_bare_prose_corpus_ratchet.py` and `tests/fixtures/bare_prose_corpus_baseline.json`: the existing corpus scan. Copy its `_live_flagged_ids` flattening (it iterates the returned candidates, then `candidate.ids`, deduplicating in order), so that your count (a) means exactly what the gate means. The fixture records one flagged spec, `kitty-specs/egress-refusal-consolidation-3110-01KYW895/spec.md`, with `C-1` and `C-3`.

**Facts at prompt time (re-verify, do not trust):**
- `git merge-base HEAD upstream/main` = `ffe8d39152` today. The spec's NFR-001 names "the merge-base with `upstream/main` recorded at scan time"; the planning-time base was `aedb30cddd`, and the branch was rebased onto `ffe8d39152` afterwards. Use the ACTUAL merge-base you compute, record it with `git log -1 --format='%H %cs %s'`, and state its deviation from the planning-time `aedb30cddd` in the report.
- The corpus holds 519 `kitty-specs/*/spec.md` files (518 + this mission's own) and about 3014 `kitty-specs/*/tasks/WP*.md` files. Record your real counts.
- On the pre-mission code, `_REF_FIND_PATTERN` is `\b(?:FR|NFR|C)-\d+\b`. It does not match `FR-006a` at all (there is no word boundary before `a`), nor any `SC-*`. `normalize_requirement_refs_value` therefore **drops** these refs and uppercases the rest. That is the "before" classification.
- Grep candidates for (b), not a verdict: `C-EXCL-2167` and `C-EXCL-FALLBACK` (`coord-read-residuals-merge-lanes-and-identity-routing-01KW2M8V`), and `C-S1` and `SC-S2` (`mission-type-drg-edges-01KXKY2N`). The authoritative list is what `lint_spec_requirement_ids` refuses at the head.

**Scope guards (C-008):**
- Read-only over the corpus. Never edit another mission's `spec.md` or WP file, never re-finalize a corpus mission, and never re-seed an acceptance matrix.
- Never edit `tests/fixtures/bare_prose_corpus_baseline.json` or any test. If (a) grows, that is a regression to escalate, not a baseline to bump.
- The scripts contain **no requirement-ID regex of their own**. Every parse, lint and classification goes through the API of the tree under test; otherwise the evidence measures the script, not the product. A regex for file names (`WP\d+`) is fine.

## Branch Strategy

- **Strategy**: Planning artifacts were generated on `issue-2991-requirement-id-grammar`; completed changes must merge back into `issue-2991-requirement-id-grammar`.
- **Planning base branch**: `issue-2991-requirement-id-grammar`
- **Merge target branch**: `issue-2991-requirement-id-grammar`
- **Workspace**: run `.venv/bin/spec-kitty agent action implement WP08 --agent claude`. A `planning_artifact` WP goes to `lane-planning`, which resolves to the repository-root checkout, not a `.worktrees/` lane.

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

**Commit path (record which one applies).** Read the `implement` output. If it prints a planning-artifact commit instruction, commit the `research/` files through `.venv/bin/spec-kitty spec-commit --mission requirement-id-grammar-01M3NRCA -m "<msg>" <files>`. If the lane owns the files, use the lane's normal commit flow. Never spec-commit (or otherwise commit) anything under `traces/`. Record the path you used, and why, in the hand-off's `## Tracer notes` and the Activity Log. Never force-add around a refusal without recording it.

**Head source (orchestrator ruling).** Head `src` = the repo-root checkout after implement's self-heal merge. Claiming this planning-lane WP runs `reenter_lane_self_heal` (`src/specify_cli/lanes/implement_support.py:565-583`; merge at `:361-384`), which merges the approved dependency lane tips into the repo-root checkout. It refuses when the root is dirty (`:369`), so start from a clean root. Record its SHA (`git rev-parse HEAD` in the repo root, after `implement`). Confirm `grammar.py`/`lint.py` and the ancestry of all lane tips (preflight below). Never hand-merge lanes.

**Scratch-first outputs.** Both scripts write every output to a scratch directory outside the repository (for example under the system temp dir) and the results are copied into `research/` only at the end, after both runs and the determinism diff pass. A half-written `research/` file in the repo-root checkout would dirty the root that the self-heal and every WP's `move-task` depend on.

**Head-source preflight (STOP condition).** Before any measurement, prove the head tree holds the whole mission:
1. `src/specify_cli/requirement_mapping/grammar.py` exists and exposes `classify` and `canonical`;
2. `src/specify_cli/requirement_mapping/lint.py` exposes `lint_spec_requirement_ids`;
3. every lane tip recorded in `lanes.json` / the status log for WP01–WP07 is an ancestor of the head SHA (`git merge-base --is-ancestor <tip> <head>`).

If any check fails, **STOP**. Record it in the hand-off's `## Tracer notes` and escalate to the orchestrator. Never hand-merge lanes, and never measure a partial head and call it the head.

## Subtasks & Detailed Guidance

### Subtask T035 – `research/corpus_scan.py`

- **Shape**: one file, two modes.
  - **Driver** (default): `.venv/bin/python kitty-specs/requirement-id-grammar-01M3NRCA/research/corpus_scan.py --corpus-root <head-tree> --base-src <base-worktree>/src --head-src <head-tree>/src --out-dir <scratch>/research`, where `<scratch>` is outside the repository; copy the results into `kitty-specs/requirement-id-grammar-01M3NRCA/research/` only at the end (see "Scratch-first outputs").
  - **Worker** (`--worker --side base|head --file-list <json>`): run by the driver in a subprocess; it prints one JSON object to stdout.
- **Merge-base tree**: the driver (or a documented shell step in the report) runs `git worktree add --detach <tmp>/rig-base <merge-base-sha>` under the system temp dir, NOT under `.worktrees/`, so no lane tool mistakes it for a lane. Remove it in a `finally` with `git worktree remove --force`, then `git worktree prune`. Record `git worktree list` output after removal.
- **One file list, built once**: the driver globs `kitty-specs/*/spec.md` and `kitty-specs/*/tasks/WP*.md` under `--corpus-root` (the head tree), sorts them as repo-relative POSIX paths, and writes them to a temp JSON file that BOTH workers receive. Both workers read file CONTENT from the head tree too; only the `src` differs. Record the counts and a sha256 of the sorted list in the output, so the reviewer can see the lists were identical.
- **Import isolation**: each worker runs as `subprocess.run([sys.executable, __file__, "--worker", …], env={…, "PYTHONPATH": <side-src>, "HOME": <tmp-home>}, cwd=<tmpdir>)`. Never import both trees in one process. The venv's editable install also puts a `src` on `sys.path`, and `PYTHONPATH` must win: at start-up each worker asserts that `specify_cli.__file__` (and `runtime`, `charter`, `kernel`, if imported) resolves under its side's `src`, and fails loudly otherwise. Record the resolved paths in the JSON.
- **What each worker computes** (per file, deterministic, sorted):
  - **(a) bare prose**: for every spec, the flattened ids from `find_bare_prose_requirement_ids(content)`, using the ratchet's flattening. Output: `{spec_path: [ids]}` for flagged specs only, plus the count.
  - **(b) planning-hand-off refusals**, head only: `lint_spec_requirement_ids(content)`. Record `errors` as `{spec_path: [{token, line, rule}]}`. Record the `warnings` count per spec too, as information (FR-014 is non-blocking). On the base side, record `"not_available"` explicitly; never an empty list, which would read as "zero refused".
  - **(c) declared-ID growth**: `parse_requirement_ids_from_spec_md(content)["all"]` per spec. The driver computes `head − base` per spec (and `base − head`; a shrink is a finding too).
  - **(d) WP ref classification**, per WP file and per raw token:
    - raw tokens: `read_all_wp_raw_requirement_refs(tasks_dir)` exists on both trees. If the head renamed it, read the frontmatter value and split it with the head's `grammar.tokenize_refs`, and record which reader each side used. The declared set is that mission's own `spec.md`, read with the same side's `parse_requirement_ids_from_spec_md`; a missing spec gives an empty set, recorded as `spec_missing`.
    - **before** (base): `normalize_requirement_refs_value([token])`. An empty result is `dropped`. A result equal to the token is `kept`. Any other result is `kept_respelled:<value>`. Also record whether the kept value is in the base declared set (`known` or `unknown`), because the base finalize gate used that.
    - **after** (head): `grammar.classify(token, declared)`. Record `accepted` or `rejected:<reason>`, with the reason in {`malformed`, `unknown_spec_id`, `foreign_qualified`}. Use the head's real signature; `data-model.md` names it `classify(raw, declared)`.
- **Driver output**:
  - `<out-dir>/corpus-scan.json` (committed as `research/corpus-scan.json`): `json.dumps(…, sort_keys=True, indent=2)`, repo-relative paths, both SHAs, the file-list hash and counts, per-side results, and the derived diffs. Put NO timestamps or absolute temp paths in it; the file must be byte-identical across re-runs at the same SHAs.
  - A markdown summary printed to stdout (or `research/corpus-scan.summary.md`) that T036 pastes and interprets.
  - For (d), a before→after transition matrix with counts (for example `dropped → accepted`, `kept/known → accepted`, `kept/known → rejected:unknown_spec_id`), plus the full item list for every transition except `kept/known → accepted`, which is the unchanged case.
- **Hygiene**: no network, no writes outside `--out-dir` except the temp dirs, which are removed. Exit non-zero on any worker failure; never emit a partial report. Keep every function at complexity ≤ 15, with type hints, and clean under `ruff check`, `ruff format --check` and `mypy --strict`. `ruff format --check .` runs over `kitty-specs/` in CI too.

### Subtask T036 – `research/corpus-scan.md` (the report)

Run the scan and commit the report. Sections, in this order:
1. **Method**: the exact commands, the merge-base SHA with its deviation from `aedb30cddd`, the head SHA and how the head preflight passed, the file counts and list hash, the Python version, and the worktree-removal proof.
2. **(a) Bare prose / SC-005**: base count and list, head count and list, and the verdict `head ≤ base`. **Positive control**: the egress spec must still be flagged at the head with `C-1`/`C-3` (C-009 keeps unqualified, unsuffixed FR/NFR/C candidates). If it is no longer flagged, explain exactly why (for example, its citations were rewritten in qualified form by some commit, named by SHA). A silent disappearance is a detector regression.
3. **(b) Newly refused specs**: every `{spec, token, line, rule}`. Expected: 4 specs. For each, say whether it is an **intended fix** (a kind-prefixed token in a declared position that the grammar cannot parse, such as `C-EXCL-2167`, `C-S1` or `SC-S2`) or a **regression** (a false refusal: a token inside an HTML comment or code fence, a non-first table cell, a legitimate ID, a prose compound such as `FR-008-mandated` outside a declared position). If the count is not 4, explain every difference.
4. **(c) Declared-set growth**: per spec, the added IDs. Classify: `SC-###` and lowercase-suffixed IDs in declared shapes are intended (FR-003). Anything else is a suspect regression: a placeholder (`FR-00N`), a qualified citation, an ID taken from a description cell (the "first ID on a line" rule), or an uppercase-suffix declaration. List any shrink separately; a shrink is a regression unless explained. One shrink class is expected: WP01 makes `_declared_ids` scan `blank_html_comments(text)`, so an ID declared only inside an HTML comment is no longer declared. Report every such change, and classify it as intended only when the removed ID sits inside a comment in that spec (quote the line).
5. **(d) WP ref transitions**: the matrix, then every changed item, grouped by transition and classified:
   - `dropped → accepted`: intended (#2991: the authored ref is now kept and counted);
   - `dropped → rejected:*` and `kept/unknown → rejected:unknown_spec_id`: intended per the FR-019 verdict table and the spec's Assumptions bullet 1. List the missions whose next re-finalize will newly fail;
   - `kept/known → rejected:*`: a probable regression. Investigate each one (for example, a digit-width or case mismatch) and escalate if it is not explained;
   - `kept_respelled → accepted`: record it; this is the uppercase-suffix tolerance.
6. **Interpretation and escalations**: one short paragraph, then a bullet list of every item classified as a regression, repeated verbatim in the hand-off.

### Subtask T037 – `research/latency_bench.py` + `research/latency.md` (NFR-003)

- **Not a performance suite (C-007)**: a standalone script, run once, with no pytest and no markers.
- **Fixture**: generated at run time in a `tempfile.TemporaryDirectory()` and removed afterwards, identical for both sides. Model it on `_build_mission` in `tests/specify_cli/cli/commands/test_finalize_tasks_validate_only_readonly.py`: a git repo, `meta.json`, `spec.md`, `tasks.md` and WP files, committed. Content:
  - `spec.md` declares `FR-001`..`FR-030` in a table, 5 NFRs, 3 Cs, and 4 SCs as `- **SC-00N**: …` bullets;
  - 30 WPs (`WP01`..`WP30`), each with `requirement_refs: [FR-0NN, NFR-00x]`, so that every FR is mapped.
  - Before timing, run each side once and assert that finalize exits 0 and that both sides reach the same pass verdict. If the base rejects something (for example, SC refs, if you add any), reduce the fixture to what both accept, and record that in `latency.md`. A benchmark in which one side takes a failure path is invalid.
- **Entry point**: in-process typer `CliRunner` on `specify_cli.cli.commands.agent.mission.app` with `["finalize-tasks", "--mission", <slug>, "--json", "--validate-only"]`. Patch `specify_cli.cli.commands.agent.mission.locate_project_root` and `run_git_preflight` exactly as `_run_finalize` in that test does, and stub `specify_cli.status.emit._saas_fan_out` if that tree has it (no network). After each run, assert that `git status --porcelain` in the fixture is empty (the read-only contract); if it is not, the sample is invalid.
- **Two metrics per sample**, both in-process with `time.perf_counter_ns`:
  - **phase**: the requirement-mapping phase. Wrap `mission_finalize._validate_requirement_mapping` and `mission_finalize._read_spec_requirement_ids` (both exist at the merge-base) with an accumulating timer through `unittest.mock.patch.object(…, wraps=…)`. If WP02 renamed or split them at the head, wrap the head's equivalents and record the mapping in `latency.md`. Ref reading in the bootstrap loop is not inside these functions; the total metric covers it.
  - **total**: the whole `runner.invoke(...)` call.
- **Isolation and interleaving**: 20 rounds. Each round spawns one base worker and one head worker as separate subprocesses (same `PYTHONPATH` + `__file__` assertion + temp `HOME` as T035), alternating the order (ABBA). Each worker does one untimed warm-up invocation, then one timed invocation, and prints `{phase_ns, total_ns}`. Record the load average before and after.
- **Verdict**: `median(phase_head) − median(phase_base) ≤ 50 ms` is the NFR-003 threshold, AND `median(total_head) < 2000 ms` is the charter budget. Also report `median(total_head) − median(total_base)`. If the total delta exceeds 50 ms while the phase delta passes, flag it in the hand-off; do not hide it behind the phase metric.
- **`latency.md`** records:
  - the machine: `platform.platform()`, the CPU model from `/proc/cpuinfo` where available, `os.cpu_count()`, the Python version, and the load averages;
  - both SHAs and the command;
  - the fixture shape;
  - all 20 samples per side, with the median, min and max;
  - the verdict line, e.g. `NFR-003: PASS (phase Δ = +3.1 ms ≤ 50 ms; total head = 812 ms < 2000 ms)`.
- Also write `latency.json` (sorted keys; the samples themselves are expected to vary between runs). Like every output, `latency.json` and `latency.md` go to the scratch out-dir first and are copied into `research/` at the end.

## Validation surface

Running the scripts IS the validation. Run only these.

**Scripts** (from the repo root):
- `.venv/bin/python kitty-specs/requirement-id-grammar-01M3NRCA/research/corpus_scan.py …`, twice, then `diff` the two `corpus-scan.json` outputs: they must be identical (the determinism check);
- `.venv/bin/python kitty-specs/requirement-id-grammar-01M3NRCA/research/latency_bench.py …`, once.

**Named architectural gate** (by file name only, at the head tree):
- `PWHEADLESS=1 .venv/bin/python -m pytest -q tests/architectural/test_bare_prose_corpus_ratchet.py`

**Static checks** (zero findings):
- `.venv/bin/ruff check kitty-specs/requirement-id-grammar-01M3NRCA/research/corpus_scan.py kitty-specs/requirement-id-grammar-01M3NRCA/research/latency_bench.py`
- `.venv/bin/ruff format --check kitty-specs/requirement-id-grammar-01M3NRCA/research/corpus_scan.py kitty-specs/requirement-id-grammar-01M3NRCA/research/latency_bench.py`
- `.venv/bin/ruff check --select C901` on both scripts (complexity ≤ 15).
- `.venv/bin/mypy --strict kitty-specs/requirement-id-grammar-01M3NRCA/research/corpus_scan.py kitty-specs/requirement-id-grammar-01M3NRCA/research/latency_bench.py` (zero findings; the scripts carry full type hints, and no `# type: ignore`).

No other suites. Record each command with its result (and the pytest passed/failed counts) in the Activity Log and the hand-off.

**Baseline-red gotcha:** if the ratchet gate is red, first run it against the merge-base tree (`PYTHONPATH=<base-worktree>/src`). A failure that is also red there is not yours: report it and do not fix it. A failure that is red only at the head is a mission regression, to escalate with the (a) evidence.

## Test Strategy

This is an evidence WP, so there is no red-first repro: it fixes no defect. Its non-vacuity comes from the measurements themselves:
- **(a) has a floor**: the egress spec must be flagged on BOTH sides. A base-side count of 0 means the scan is broken (for example, wrong flattening or import leakage), not that the corpus is clean. Assert this in the driver.
- **(b) has a floor**: at least one refusal is expected at the head. Zero refusals means the lint was not really invoked; investigate before reporting "0".
- **(d) has a floor**: at least one `dropped → accepted` transition is expected. A prompt-time grep found about 74 corpus WP files with `SC-*` list items and 3 with letter-suffixed ones; the base drops all of these. Zero means the head classification did not run.
- **Isolation is proven, not assumed**: each worker's JSON carries the resolved `specify_cli.__file__`, and the driver asserts that base and head resolve to different trees.
- **The benchmark is valid only if both sides passed and stayed read-only** on every sample.

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| The head tree lacks some lane's code (the self-heal did not merge every approved lane) | Head-source preflight over all WP01–WP07 lane tips; STOP and escalate. Never hand-merge lanes, and never measure a partial head. |
| A dirty repo-root checkout blocks implement's self-heal (`implement_support.py:369`) | Start from a clean root; scripts write to a scratch dir and copy into `research/` only at the end. |
| Import-path leakage between the two `src` trees (the editable install's `.pth`) | One subprocess per side, `PYTHONPATH` set, and a `__file__` assertion per package; the resolved paths are recorded in the JSON. |
| The merge-base worktree is left behind | Remove it in `finally` plus `git worktree prune`; paste `git worktree list` into the report. |
| The base and head read different corpus content | One file list built once from the head tree; both workers read head content; the list hash is recorded. |
| Machine noise | Median of 20, ABBA interleaving, a warm-up per worker, and the load average recorded. |
| A regression gets reclassified as "intended" to pass | Every changed item is classified with a one-line reason. `kept/known → rejected` and any (a) growth default to regression until explained. |
| The scan embeds its own ID regex and so measures itself | Forbidden; all classification goes through the tree's API. |
| The spec names `aedb30cddd` but the real merge-base differs | Use the real one; state the deviation in both reports and the hand-off. |
| Cross-gate malformed/foreign parity | Not WP08's: WP04's parity test (finalize vs runtime) and WP06 T038 (finalize, map-requirements, runtime) cover it. |

## Review Guidance

- The SAME file list feeds both runs: one list hash, and both workers read head content.
- Both SHAs are recorded, and the deviation from `aedb30cddd` is stated.
- Isolation holds: separate subprocesses, the recorded `specify_cli.__file__` differs per side, and the merge-base worktree is gone.
- (a) passes `head ≤ base`, and the SC-005 positive control is addressed. (b) lists every refused spec with token, line and rule, and explains any count other than 4. (c) and (d) classify every changed item as an intended fix or a regression, with a reason.
- Every regression is escalated in the hand-off.
- `corpus-scan.json` is deterministic (the two-run diff is empty) and carries no timestamps or temp paths.
- The benchmark: subprocess isolation, ABBA interleaving, the median of 20, both sides passing and read-only, the machine info, and a verdict line against both thresholds.
- The scripts contain no requirement-ID regex, pass ruff lint and format, and keep complexity ≤ 15.
- No file outside `research/` changed, and nothing under `traces/` was committed.

## Tracer notes

Add 1–3 dated sentences at decision points to the `## Tracer notes` section of your hand-off (never to `traces/`):
- approach: the head SHA and how the preflight passed; the merge-base SHA;
- design decisions: the phase functions wrapped at each side; any fixture reduction;
- tooling friction: the commit path used; any import-leakage, self-heal or worktree surprise.

## Activity Log

> **CRITICAL**: Activity log entries MUST be in chronological order (oldest first, newest last).

### How to Add Activity Log Entries

**When adding an entry**:

1. Scroll to the bottom of this Activity Log section
2. **APPEND the new entry at the END** (do NOT prepend or insert in middle)
3. Use exact format: `- YYYY-MM-DDTHH:MM:SSZ – agent_id – <action>`
4. Timestamp MUST be current time in UTC (check with `date -u "+%Y-%m-%dT%H:%M:%SZ"`)
5. Agent ID should identify who made the change (claude-sonnet-4-5, codex, etc.)

**Format**:

```
- YYYY-MM-DDTHH:MM:SSZ – <agent_id> – <brief action description>
```

**Initial entry**:

- 2026-09-29T06:22:20Z – system – Prompt created.

---

### Updating Status

Status is managed via `status.events.jsonl`. Use `.venv/bin/spec-kitty agent tasks move-task WP08 --to <status>` to change WP status.
