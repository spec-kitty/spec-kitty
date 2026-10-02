---
work_package_id: WP12
title: Close-out evidence record, measurements and tracer assessment (IC-10, part b)
dependencies:
- WP11
requirement_refs:
- C-001
- C-002
- C-003
- C-004
- C-005
- C-006
- NFR-001
- NFR-007
- SC-002
- SC-003
- SC-007
- SC-008
- SC-009
- SC-010
planning_base_branch: issue-5558-mission-status-contract-v1
merge_target_branch: issue-5558-mission-status-contract-v1
branch_strategy: Planning artifacts for this mission were generated on issue-5558-mission-status-contract-v1. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5558-mission-status-contract-v1 unless the human explicitly redirects the landing branch.
subtasks:
- T074
- T075
- T076
- T077
- T078
- T079
history: []
agent_profile: curator-carla
authoritative_surface: kitty-specs/mission-status-contract-v1-01M3WC5X/
create_intent:
- kitty-specs/mission-status-contract-v1-01M3WC5X/close-out.md
execution_mode: planning_artifact
model: sonnet
owned_files:
- kitty-specs/mission-status-contract-v1-01M3WC5X/research.md
- kitty-specs/mission-status-contract-v1-01M3WC5X/close-out.md
- kitty-specs/mission-status-contract-v1-01M3WC5X/tracer-approach.md
- kitty-specs/mission-status-contract-v1-01M3WC5X/tracer-design-decisions.md
- kitty-specs/mission-status-contract-v1-01M3WC5X/tracer-tooling-friction.md
role: curator
tags: []
tracker_refs: []
---

# WP12 - Close-out evidence record, measurements and tracer assessment (IC-10, part b)

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `curator-carla`
- **Role**: `curator`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## Objective

Write the Mission close-out record (`close-out.md`) that backs the PR body, verify and finish the evidence the orchestrator wrote into `research.md` during the Mission, record the preview tag names, and complete the tracer files' "assess at close" sections.

## Context

- Second half of plan concern **IC-10**; no new behaviour. **The only planning WP, and deliberately last.** `finalize-tasks` places every planning WP in one planning lane and rejects a lane graph in which that lane is both upstream and downstream of a code lane (`LANE_DEPENDENCY_CYCLE`, observed with `--validate-only`); planning records that the plan wanted between code WPs (baseline, IC-07a spike table, IC-07b supply-chain table) are therefore written by the **orchestrator** at the record steps named in WP01, WP02 and WP08, and verified and completed here.
- All inputs are artefacts of earlier WPs and CI runs relayed by the orchestrator; where an input is missing, record the gap and stop, never infer.
- **Six stacked seam PRs, all drafts until a maintainer acknowledges the design on #5528 (C-001, SC-010; operator ruling of 2026-10-02, DD-21, which supersedes the earlier single-PR wording).** The orchestrator opened PR 1 at the WP02 pre-step (before the CI-only spike) and opens PRs 2 to 6 at their seam end (PR 4 earlier, at WP08's first push); never an agent. This WP only finalises the PR bodies (it opens nothing, pushes nothing, marks nothing ready); every PR stays a draft until the acknowledgement is linked, and the operator or a maintainer merges bottom-up. This WP is the last of PR 6.
- **Orchestrator pre-PR step: tracer F-3 (not an agent action).** The scaffold commit subject uses legacy wording (`tracer-tooling-friction.md` F-3). The orchestrator rewords it during the compact-history step; this WP verifies read-only with `git log --format=%s origin/main..HEAD` that no subject still reads `scaffold for feature`, and records the result (or the gap) in `close-out.md` and `tracer-tooling-friction.md`.
- **PR shape and reviewability (binding, DD-21).** About 10,000 or more added lines across five kinds of artefact (about 25 `contracts/tools/` scripts and libraries with fixtures, about 22 unit-test modules, two workflow files, about 40 contract YAML files, a reality-check helper and pinned fixture, and docs) are not readable in a sitting as one diff, so the Mission is delivered as six stacked seam PRs: (1) WP01 and WP02 (baseline, libraries, routing, shared pieces, workflow skeleton and spike; base `main`); (2) WP03 to WP05 (the contract content, the UI early-start unit, ending at p0); (3) WP06 and WP07 (Python checks and hygiene); (4) WP08 and WP09 (JVM and Go tooling, workflows, release; the highest-risk review); (5) WP10 (reality check); (6) WP11 and WP12 (docs and records). PR n (n = 2 to 6) targets the head branch of seam n-1. Reason: each group has a different reviewer skill set (OpenAPI authoring, Python tooling, GitHub Actions and supply chain, status-domain readers, documentation) and the workflow group can only be exercised on CI. Record the realised shape (PR numbers, seam heads, bases) in `close-out.md`. **Stack maintenance (orchestrator, not an agent action):** seam branches are cut at the WP02, WP05, WP07, WP09, WP10 and WP12 heads; a re-sync or compact-history step runs lowest seam first, then `rebase --onto` for the upper seams, `--force-with-lease` only, and every rewrite re-publishes (`compact history`) any published preview tag whose commit lies in the rewritten seam or above it. **Planning records and PRs (A9):** the records the orchestrator wrote into `research.md` and the tracer files (R-8, R-3, R-9, ...) were committed in the seam where they were written (PR 1 for R-8, R-3 and the IC-07a rows of R-9; PR 4 for the IC-07b rows); this WP, in PR 6, only verifies and finalises them.
- **Chokepoint summary the record must state**: the resolver (`contract_resolver.py`, written by WP01 and extended only under resolver change control in WP03 to WP05 and, conditionally, WP09); the router glob (one line) and the corpus-registry file (append-only rows, owned by each WP that adds a corpus-marked module, which is why all code WPs share one lane); `contracts.yml` single-writer order WP02, then WP08, then WP09; the pinning inventory (regenerated by script in WP01 and WP02; no scanned file edited later); the contract root map and `_index.yaml` files (WP03, WP04, WP05 sequential, plus WP09's conditional brace re-sweep). No WP touches the migration chain, a runtime-state schema or the event-contract implementation; shared CI gates touched are the router glob (WP01), the fleet-verdict inventory (WP02) and the new workflow files (WP02, WP08, WP09).
- Public repository: no absolute host path, e-mail address, credential or private-discussion reference in any owned file (C-006); upstream issue and PR numbers may be cited.
- Terminology: Mission, never feature; status lane, code lane and repo-root lane kept apart.

### Test surface and gates

No code. Run, record and cite read-only: `.venv/bin/python contracts/tools/leak_scan.py --root contracts` and `.venv/bin/python contracts/tools/no_pytest_scan.py`; `.venv/bin/spec-kitty cutover-guard --base-ref origin/main` (second record for PR prep, to compare with WP01's); `.venv/bin/spec-kitty regen --check` as the plan's no-diff confirmation only if `--help` shows it is read-only (otherwise do not run it and record that). `PWHEADLESS=1 .venv/bin/python -m pytest -q tests/architectural/test_no_legacy_terminology.py` and `uv lock --check` (both read-only; record results in `close-out.md`). Only the five owned files may change.

## Subtasks

### Subtask T074: Verify the orchestrator-written records

**Purpose**: the records were written outside any WP; check them against their sources.
**Steps**: read `research.md` and confirm: R-8 "Baseline record" (from WP01: base hash, command lines and counts, binned reds with tracker issue numbers, floors, CI durations, `cutover-guard`); R-3 (WP02: normalisation table within the cap of eight, brace spelling, smoke counts, generator-failure plant, E-1/E-4 outcome, the "IC-07a complete" sentence, or the time-box fallback sentence "IC-07a pending, default spelling provisional"; when only the fallback sentence is present, require the later "IC-07a complete" record, the WP09 brace re-sweep outcome and any re-publication tags caused by a spelling change, and record the absence of any of them as a gap for the orchestrator) and the IC-07a rows of R-9; R-2 versions and dates and the R-9 rows for vacuum and oasdiff plus the pushed planted inputs (WP08). Compare versions and dates with `contracts/tools/pins.json`. Fix transcription errors; record any missing record as a gap for the orchestrator.
**Files**: `kitty-specs/mission-status-contract-v1-01M3WC5X/research.md` (transcription fixes only).
**Validation**: each record has an artefact behind it (file, run id, test name).

### Subtask T075: Write `close-out.md`: evidence ledger for the PR body

**Purpose**: SC-001 to SC-010 evidence in one place.
**Steps**: sections: (1) base commit and baseline of known-red tests; (2) class A evidence: a link or run id per check in FR-021 (negative-tests runs, planted violations), relayed by the orchestrator; (3) class B evidence: test ids of the in-test planted cases (reality-check controls; `tests/ci/test_contracts_workflows.py` cases) from collect-only output; (4) the `x-derived` property list with each rule and inputs, citations used by more than five properties, and the printed `citation_check` counts (`properties`, `x_source`, `x_derived`, `inputs_resolved`); (5) the reality-check floors as measured and pinned, the disagreement list length and its ceiling, and the ratchet issue number, owner and `drain_by` (from the fixture header); (6) the data files the reality check reads that the router does not select (`meta.json`, `status.events.jsonl`, `tasks.md`, `.kittify/config.yaml`) and the uncovered reader paths (`src/specify_cli/status/**`, `src/specify_cli/mission_metadata.py`, `src/mission_runtime/**`, `src/specify_cli/core/dependency_graph.py`, `tests/contract/**`); (7) DEV-1, DEV-2 and the D-P13 plan-level additions as confirmation requests (E-2); (8) the statement that review is advisory (no branch protection; CODEOWNERS routes only), carried in the body of PR 3 (WP07); (9) the fleet-verdict observability limit (`workflow_run` runs the default-branch copy; confirmed only post-merge); (10) the realised six-seam PR shape (PR numbers, seam heads and bases; binding, repeated from WP01's PR shape paragraph, where the orchestrator sees it first); (11) the open-PR overlap results from each WP (PRs, files; WP11's changelog and index overlap with #5540 and #5326) and the note that #5557 is closed, not merged; (12) the lane-model note (all code WPs in one lane) and the tags-and-CLI limitations listed in the hand-off (IC-07a and IC-07b cited as IC-07 in `wps.yaml` because the manifest accepts only `IC-##`); (13) the **per-PR evidence table**, one row per PR, each row confirmed against that PR's body. Every PR: five-section body and the known-red baseline. PR 1 (WP01+WP02): DEV-1 and DEV-2 confirmation requests (also asked on #5528), spike record pointers, SC-008 assertions against `origin/main`. PR 2 (WP03-WP05): example-test counts, p0 tag name (the PR 2 head). PR 3 (WP06+WP07): the CODEOWNERS advisory statement (SC-010), class A and class B evidence of the checks. PR 4 (WP08+WP09): the release-dry-run artifact (SC-006: bundle, `openapi.yaml.sha256`, `sha256sum -c`, run id), p1 tag name with PR 4's run id, supply-chain record, fleet-verdict observability limit. PR 5 (WP10): NFR-001 timing and the SC-002 reality check, the NFR-007 coverage paste, p2 tag name (the PR 5 head), ratchet issue. PR 6 (WP11+WP12): the ledger, the post-merge list, the acknowledgement link. For PRs 1 to 6 also record the SC-008 diff assertions taken against that PR's own base (`origin/main` for PR 1, the previous seam head for PRs 2 to 6) and the stray/missing check of T079 run per PR (see T079); the stack-level run against `origin/main` is the sixth, cumulative record.
**Files**: `kitty-specs/mission-status-contract-v1-01M3WC5X/close-out.md` (new, ~300 lines).
**Validation**: every claim cites an artefact or is marked "not available" with the reason.

### Subtask T076: NFR-001 measurements

**Purpose**: performance numbers from CI logs.
**Steps**: from relayed run logs, record the reality-check module duration (at most 120 s), the slowest case (at most 60 s), the whole `tests-corpus` job duration against its 10 minute timeout (headroom at least 50 percent), and the `built-in-corpus-suite` duration against its 20 minute timeout from a full-mode `packs.yml` dispatch on the branch after the first draft-PR run (the orchestrator dispatches; agents do not). Compare with WP01's baseline readings. Put the numbers in `research.md` R-8 and `close-out.md`.
**Files**: `kitty-specs/mission-status-contract-v1-01M3WC5X/research.md` (R-8 numbers), `kitty-specs/mission-status-contract-v1-01M3WC5X/close-out.md`.
**Validation**: each number has a run identifier.

### Subtask T077: Preview points and post-merge close-out list

**Purpose**: record the early-start deliverables and the maintainer steps.
**Steps**: record in `tracer-approach.md` (section "UI early-start point") the tag **names** (not hashes) the orchestrator published and their dates: `preview/mission-status/p0` (WP05, cut at the PR 2 head; cites PR 2), `p1` (WP09, inside PR 4; cites PR 4 and its run id), `p2` (WP10, cut at the PR 5 head; cites PR 5), each with its re-publication counter history (`-r2`, `-r3`, ... and the cause of each: `compact history` or `brace re-sweep`), or "not yet published". In `close-out.md` list the post-merge steps (maintainer-run, SC-009): push `contract-mission-status-v1.0.0`; verify the release was created with `--latest=false`, that the repository's Latest release is still the CLI's, that it holds exactly the bundle and its sha256, that the downloaded checksum verifies and equals a locally rebuilt bundle; open or inspect the first pull request touching `contracts/` and confirm the fleet-verdict comment lists the contracts workflow; read the push-to-`main` `built-in-corpus-suite` run and apply the first-red triage rule if red; run `spec-kitty regen --check` once as a no-diff confirmation. These are the close-out record, not follow-up issues.
**Files**: `kitty-specs/mission-status-contract-v1-01M3WC5X/tracer-approach.md` ("UI early-start point"), `kitty-specs/mission-status-contract-v1-01M3WC5X/close-out.md` (post-merge list).
**Validation**: the three tags are accounted for.

### Subtask T078: Campsite, decision and friction entries

**Purpose**: complete the tracer trail.
**Steps**: record in `tracer-approach.md` whether the WP01 campsite commit landed or "no domain-matched debt found"; append dated entries to `tracer-design-decisions.md` for decisions taken during implementation (resolver extensions, ruleset location `contracts/lint/`, negative-case driver, brace spelling outcome, the single-lane model); add observed friction (CI-only loop, hidden inventory gate, `IC-##`-only manifest pattern, lane-cycle rejection) to `tracer-tooling-friction.md`.
**Files**: `kitty-specs/mission-status-contract-v1-01M3WC5X/tracer-approach.md`, `kitty-specs/mission-status-contract-v1-01M3WC5X/tracer-design-decisions.md`, `kitty-specs/mission-status-contract-v1-01M3WC5X/tracer-tooling-friction.md`.
**Validation**: each tracer file has at least one dated entry from implementation.

### Subtask T079: "Assess at close" and final leak check

**Purpose**: charter standing order 3.
**Steps**: complete the "Assess at close" sections of the three tracer files; run `leak_scan` and `no_pytest_scan` as above; `git diff --stat` confirms only the five owned files changed (this WP's own diff). **Mission-wide diff constraints (SC-008, C-002, C-003, C-004, C-005), read-only over the cumulative diff of the stack (`origin/main...HEAD`) and, with the base replaced by the previous seam head and `HEAD` by the seam head, over each PR's own diff (PR 1 against `origin/main`; the router glob line is in PR 1 only, so the added-line count there is exactly one and zero for PRs 2 to 6), not only this WP's files**: record that `git diff --stat origin/main...HEAD -- src contracts/fixtures tests/contract/test_handoff_fixtures.py pytest.ini .github/ci-module-registry.yml scripts/ci/fleet_main.py` is empty (`contracts/fixtures` and `tests/contract/test_handoff_fixtures.py` are the C-004 paths; `scripts/ci/fleet_main.py` is the SC-008 untouched file); that `git diff -U0 origin/main...HEAD -- .github/workflows/ci-router.yml` shows exactly one added line and no removed line; that the C-003 shared-CI path set is exactly what the Mission's WPs own there, computed rather than hand-listed: the allowed set is the union of `owned_files` entries (from `wps.yaml`) that fall under `.github/workflows`, `scripts/ci` or `tests/ci`, matched as globs, and the actual set is `git diff --name-only origin/main...HEAD -- .github/workflows scripts/ci tests/ci`. Run this and record its output:

  ```
  .venv/bin/python - <<'PY'
  import fnmatch, subprocess, sys, yaml
  # usage: <base> [<head> [<WP ids, comma separated>]]; no argument = whole stack against origin/main
  base = sys.argv[1] if len(sys.argv) > 1 else 'origin/main'
  head = sys.argv[2] if len(sys.argv) > 2 else 'HEAD'
  seam = set(sys.argv[3].split(',')) if len(sys.argv) > 3 else None
  m = 'kitty-specs/mission-status-contract-v1-01M3WC5X'
  roots = ('.github/workflows/', 'scripts/ci/', 'tests/ci/')
  wps = [wp for wp in yaml.safe_load(open(f'{m}/wps.yaml'))['work_packages'] if seam is None or wp['id'] in seam]
  owned = {f for wp in wps for f in wp['owned_files'] if f.startswith(roots)}
  out = subprocess.run(['git', 'diff', '--name-only', f'{base}...{head}', '--', '.github/workflows', 'scripts/ci', 'tests/ci'], capture_output=True, text=True, check=True).stdout.split()
  stray = [f for f in out if not any(fnmatch.fnmatch(f, g) for g in owned)]
  must_by_wp = {'WP01': {'.github/workflows/ci-router.yml', 'tests/ci/test_contracts_routing.py'}, 'WP02': {'.github/workflows/contracts.yml'}, 'WP09': {'.github/workflows/contracts-release.yml', 'tests/ci/test_contracts_workflows.py'}}
  must = set().union(*(v for k, v in must_by_wp.items() if seam is None or k in seam))
  print('owned', len(owned), 'changed', len(out), 'stray', stray, 'missing', sorted(must - set(out)))
  PY
  ```

  Run it once per PR (the arguments are the base, the seam head and the seam's WP ids: PR 1 `origin/main <seam 1 head> WP01,WP02`; PR 2 `<seam 1 head> <seam 2 head> WP03,WP04,WP05`; PR 3 `<seam 2 head> <seam 3 head> WP06,WP07`; PR 4 `<seam 3 head> <seam 4 head> WP08,WP09`; PR 5 `<seam 4 head> <seam 5 head> WP10`; PR 6 `<seam 5 head> HEAD WP11,WP12`) and once with no argument for the whole stack against `origin/main`; record all seven outputs. `stray` must be empty and `missing` must be empty (a non-empty diff that omits a file the Mission must have changed is as wrong as a stray one). `tests/ci/test_fleet_main.py` is owned only conditionally: if it appears in `out`, confirm WP02 recorded that it turned red, otherwise treat it as stray. **Wording gap to record in `close-out.md` and state in the body of PR 1**: spec C-003 and SC-008 name only the four fleet-verdict files as other shared-CI edits; `tests/ci/test_contracts_routing.py` is a new routing test WP01 adds (a new file, not an edit of an existing shared file) and is covered by the computed set above, not by the spec wording; `plan.md` and `spec.md` are not edited in this phase and the deviation is stated here on purpose; that `git diff -U0 origin/main...HEAD -- tests/architectural/test_ci_corpus_trigger_completeness.py` has no removed line (`^-[^-]`) and only added registry rows, with `_CORPUS_GLOBS` and `_CORPUS_DATA_ROOTS` untouched (C-003); and that the Node ban (C-005, scoped to contracts tooling, workflows and tests; `kitty-specs/`, `docs/` and all `*.md` prose are excluded by construction) holds, in three parts, each of which can return its stated result on a correct tree. Part 1, tooling tokens over added lines of contracts, workflows and tests (no `*.md`): `git diff -U0 origin/main...HEAD -- contracts .github/workflows tests ':!*.md' | grep -E '^\+[^+]' | grep -E -w 'npm|npx|yarn|pnpm|setup-node|node-version'`. The only file permitted to hit is `tests/ci/test_contracts_workflows.py` (its planted violating workflow texts); record hits per file; hits elsewhere must be zero and that file must show at least one hit. Part 2, `node` as a command in workflow YAML only (Python identifiers named `node`, such as an `ast.walk` loop variable, are ordinary vocabulary and never in scope because Python files are not scanned here): `git diff -U0 origin/main...HEAD -- .github/workflows | grep -E '^\+[^+]' | grep -E '^\+\s*(-\s+)?(run:\s*[|>-]?\s*)?node\s|[;&|]\s*node\s|(run|uses):.*\bnode\b'`. This must return empty with no allow-list (the planted texts live in a Python file, outside this scan). Part 3, non-vacuity of Part 2 (the same patterns must be shown able to hit): run the Part 2 grep on `git diff -U0 origin/main...HEAD -- tests/ci/test_contracts_workflows.py`; it must hit at least once, which requires WP09's guard test to plant a bare `run: node` workflow line (WP09 owns that plant) in addition to the `setup-node` plant. A zero here means the guard test does not plant the violation and the check fails. Any other hit is a defect to fix or escalate, never to wave through. Re-run these after any rebase or compact-history step. Also re-run the terminology guard and `uv lock --check` (see Test surface) and verify the F-3 subject (see Context).
**Files**: the three tracer files ("Assess at close" sections) and `kitty-specs/mission-status-contract-v1-01M3WC5X/close-out.md` (leak, diff-constraint and gate results).
**Validation**: records leak-clean; all five constraints recorded with the command output summary.

## Definition of Done

- `close-out.md` has all twelve sections with artefact citations; NFR-001 numbers recorded; preview tag names recorded; post-merge steps listed; the per-PR evidence table (six rows) present and each row confirmed against its PR body; realised six-seam shape recorded.
- Orchestrator-written records verified against their sources; gaps listed.
- Mission-wide diff constraints (SC-008, C-002, C-003, C-004, C-005) recorded over the cumulative diff; terminology guard and `uv lock --check` results recorded; the F-3 commit subject verified.
- Tracer files assessed; only the five owned files changed; public-repository hygiene holds.
- Per-subtask completion recorded with `spec-kitty agent tasks mark-status <Txxx> --status done`.

## Risks

- Filling the ledger from the plan's promises instead of results: every line needs an artefact.
- Recording a tag as a commit hash (hashes do not survive history rewrites): names only.

## Reviewer Guidance

Spot-check five ledger lines (and the Mission-wide diff-constraint results) against the cited run or file; confirm no host path or address; confirm tag names, not hashes; confirm the draft-until-acknowledged statement on all six PRs and the advisory-review statement in PR 3.

Implementation command: `spec-kitty agent action implement WP12 --agent claude`
