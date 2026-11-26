---
work_package_id: WP01
title: Merge probes fail closed on effective merge attributes
dependencies: []
requirement_refs:
- FR-010
- NFR-001
- NFR-002
planning_base_branch: fix/approved-lane-resolution-route
merge_target_branch: fix/approved-lane-resolution-route
branch_strategy: Planning artifacts for this mission were generated on fix/approved-lane-resolution-route. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/approved-lane-resolution-route unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
phase: Phase 1 - Foundations
history:
- at: '2026-11-20T17:20:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/consolidation/
create_intent:
- src/specify_cli/consolidation/merge_attribute_guard.py
- tests/consolidation/test_merge_attribute_guard.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/consolidation/git_probes.py
- src/specify_cli/consolidation/merge_attribute_guard.py
- tests/consolidation/test_merge_attribute_guard.py
- src/specify_cli/git/merge_tree_probe.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 - Merge probes fail closed on effective merge attributes

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (`spec-kitty agent tasks status --mission approved-lane-resolution-route-01M7WW0Z`).
- **You must address all feedback** before your work is complete. Feedback items are your implementation TODO list.
- **Report progress**: as you address each item, record it with `spec-kitty agent tasks add-history WP01 --note "..."`.

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`, ````bash`

---

## Objectives & Success Criteria

Two merge probes decide what a merge "carries":

- the clean-fold recognizer `git_probes.n_way_merge_blob` (`src/specify_cli/consolidation/git_probes.py:924-952`), the last-chance attribution in the squash content axis;
- the own-content probe `git_probes.merge_own_changed_paths` (`git_probes.py:740-766`), used by the merge-strategy closed world today (`reconciliation_verifier.py:661`) and by FR-004 later (WP05).

Both re-run git's merge logic, and git honours clone-local and unreviewed merge settings while it does so. The squads reproduced, on git 2.43, that each of these makes arbitrary bytes look like a clean merge or makes a hand resolution look like "no own content":

- `merge=union` from `$GIT_COMMON_DIR/info/attributes`, from an uncommitted working-tree `.gitattributes`, or from `core.attributesFile`;
- a custom `merge.<x>.driver` in any config scope;
- `merge.default` (it re-routes every path whose attribute is `unspecified`; `git check-attr` still prints `unspecified`);
- a user-defined `merge.text.driver` or `merge.binary.driver`: git looks up user drivers BEFORE its built-ins, so `merge=text` / `merge=binary` can be redirected (verified while writing this prompt: `merge=binary` plus `merge.binary.driver='printf EVIL > %A; true'` makes `git merge-tree --write-tree` exit 0 with `EVIL` as the result);
- a registered spec-kitty driver name whose `merge.<name>.driver` command was redefined.

This WP adds ONE guard in the probe layer and wires it into both probes, so that each refuses (raises `GitProbeError`) whenever the effective merge behaviour of a probed path is anything other than git's built-in merge or spec-kitty's own registered driver, with its registered command, on its registered pattern.

Done when:

- red attack tests for every route above fail on HEAD and pass after the change, against BOTH probes;
- the positive control (only spec-kitty's own drivers, on their own patterns, including another Mission's `kitty-specs/**` file) is byte-for-byte unchanged;
- the guard costs one batched `git check-attr` per probed merge (or per recognizer call) plus one config read cached for the run (NFR-001);
- the git version check (`src/specify_cli/git/merge_tree_probe.py::_git_at_least`) runs `git --version` at most once per run scope, pinned by a subprocess-count test (NFR-001, T004 step 5);
- every probe failure inside the guard raises `GitProbeError` (NFR-002);
- ruff, `ruff format --check --force-exclude` and mypy are clean on every changed file; every function has complexity <= 15; no suppressions.

## Context & Constraints

- Read first: `kitty-specs/approved-lane-resolution-route-01M7WW0Z/spec.md` (US7, FR-010, NFR-001, NFR-002), `plan.md` (IC-01), `research.md` (R-06), `contracts/refusal-codes.md` ("FR-010 probe refusal"), and `squads/01-pre-spec-and-post-specify.md` (squad 2, FR-010 rows).
- Charter: read `.kittify/charter/charter.md`; load action doctrine with `spec-kitty charter context --action implement`.
- Integrity invariants that bind this WP:
  - **C-001**: no conflict resolution is ever attributed without a review approval. This guard only removes false "clean" verdicts; it never attributes more.
  - **C-002**: no new attestation, flag or override lifts a verdict. Do not add an opt-out for the guard.
  - **C-003**: the post-approval merge rule (#7307) is unchanged.
  - **C-006**: single authority. The guard lives in the probe layer (`consolidation/`), shared by both probes. The registry of spec-kitty drivers stays `lanes/consolidation._MERGE_DRIVERS`; do not copy it.
  - **Fail closed** (NFR-002): any `git check-attr` / `git config` failure, a count mismatch in the output, a path that cannot be passed to `--stdin`, or an unsupported registry pattern shape raises `GitProbeError`. Nothing ever reads a probe failure as "no attribute".
- **Recorded leeway (tasks.md)**: you add ONE read-only public accessor, `registered_merge_driver_specs()`, to `src/specify_cli/lanes/consolidation.py` (owned by WP07), next to `merge_driver_attribute_lines()` (`lanes/consolidation.py:533-535`). No other edit to that file. Record the leeway with `spec-kitty agent tasks add-history WP01 --note "recorded leeway: registered_merge_driver_specs() added to lanes/consolidation.py"`.
- **Import cycle**: `lanes/consolidation.py` imports `consolidation.git_probes` at module top (`lanes/consolidation.py:40`). The guard must import `registered_merge_driver_specs` **function-locally**, exactly like `git_probes._resolve_registered_driver_callable` already does (`git_probes.py:1048-1066`). A module-top import creates a cycle.
- **Path listing ownership**: `tests/architectural/test_git_path_listing_owner.py` forbids splitting git output on NUL or `" -> "` outside `src/kernel/git/`. Use `git check-attr --stdin` WITHOUT `-z` and match the output to the input by line order (see T003). Do not add a `-z` parser in `consolidation/`. If you conclude a kernel helper is required, stop and ask the orchestrator: `src/kernel/git/` is not in this WP's owned files.
- **Operator ruling (2026-11-20): committed merge attributes, option (a).** Build (a). Red tests are required for the committed-allowed case and for each override bypass, including `merge=binary` plus a custom `merge.binary.driver`.
  - **Default (a)**: a built-in `union` (or `set`) value that comes from the COMMITTED tree is honoured, and only when ALL hold: (1) git >= 2.40 (`git check-attr --source` exists from 2.40; on an older git the value refuses); (2) `git check-attr --source <pre-run target tip> merge` prints the same value as the effective (checkout) read; (3) no clone-local source sets a merge attribute for the path; (4) no `merge.<name>.driver` is configured for that name (`merge.union.driver` would redirect it). Clone-local sources (`$GIT_COMMON_DIR/info/attributes`, `core.attributesFile`, the system attributes file, an uncommitted working-tree `.gitattributes`) still refuse.
  - **Verified while writing this prompt (git 2.43)**: `git check-attr --source <tree-ish>` still applies `info/attributes` and `core.attributesFile` (`p.py merge=union` in `.git/info/attributes` prints `union` with `--source HEAD` too). So check (2) alone does NOT exclude clone-local sources. Check (3) reads them with `git check-attr --source <empty tree> merge` (the empty tree is `git hash-object -t tree /dev/null`; it has no `.gitattributes`, so any non-`unspecified` value there comes from a clone-local or system source) and refuses unless that prints `unspecified`. The two `--source` reads are batched with `--stdin` like the effective read (three `check-attr` processes per probed merge at most; record it against NFR-001).
  - **Where the pre-run target tip comes from**: add a keyword `attributes_source: str | None = None` to the guard and to both probes. `None` means "honour no committed value" (strict: `union` refuses from any source). WP01's tests call the probes directly with and without it. The callers pass the claim's pre-run target tip (`ApprovedWpCommitSet.excluded_window_base`): WP05 at its claim-time call, WP06 at the two verifier call sites (`reconciliation_verifier.py:661` and `:984`).
  - **Consequence of (a)**: this repository's own `.gitattributes:41` (`kitty-ops/lifecycle.jsonl merge=union`) is then honoured when it is committed in the pre-run target tip and nothing clone-local overrides it (T005 pins this).
  - Alternative (b) was NOT chosen; do not build it.
- Terminology: Mission (never "feature"); lane consolidation; never "sync".

## Branch Strategy

- **Strategy**: populated by `finalize-tasks`
- **Planning base branch**: `fix/approved-lane-resolution-route`
- **Merge target branch**: `fix/approved-lane-resolution-route`

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

Implement command:
`spec-kitty agent action implement WP01 --agent claude --mission approved-lane-resolution-route-01M7WW0Z`

## Subtasks & Detailed Guidance

### Subtask T001 - Red attack tests against both probes

- **Purpose**: prove each route bypasses the probes at HEAD before any production change (Standing Order 4, NFR-004). Every test is written against the post-fix expectation and must be red on HEAD.
- **File**: `tests/consolidation/test_merge_attribute_guard.py` (new). Mark it `pytestmark = pytest.mark.git_repo`.
- **Fixture** (real git, in `tmp_path`; copy the shape of `tests/consolidation/test_merge_derivation_7626.py:23-48`, do not import from it):
  - `main` with `p.py` = `a\nb\nc\n`; branch `one` edits line 1 to `ONE`; branch `two` edits line 1 to `TWO`. `git merge-tree --write-tree one two` exits 1 (assert it as a fixture precondition, so the test cannot pass on a non-conflicting fixture).
  - A hand merge commit `M` on `one` merging `two` whose committed `p.py` is the union bytes (`ONE\nTWO\nb\nc\n`). Without any attribute, `merge_own_changed_paths(repo, M) == ["p.py"]` (assert it as a precondition).
- **Attack parametrisation** (one `pytest.param` per route; each sets the route up, then calls the probe):
  1. `info_attributes`: write `p.py merge=union` to `.git/info/attributes`.
  2. `worktree_gitattributes`: write an UNCOMMITTED `.gitattributes` with `p.py merge=union` in the checkout the probe runs from.
  3. `core_attributes_file`: write the line to a file outside the repo and `git config core.attributesFile <file>`.
  4. `custom_driver`: `p.py merge=evil` in info attributes and `git config merge.evil.driver "printf EVIL > %A; true"`.
  5. `merge_default`: no attribute, `git config merge.default union`.
  6. `builtin_name_redefined`: `p.py merge=binary` in info attributes and `git config merge.binary.driver "printf EVIL > %A; true"` (and a second param for `text`).
  7. `registered_driver_redefined`: `p.py merge=spec-kitty-meta` and `merge.spec-kitty-meta.driver "printf EVIL > %A; true"`. Note this also needs the path to match the registered pattern for the "redefined command" leg to be what refuses; add a second variant on `kitty-specs/m/meta.json` with the redefined command, and a third variant on `p.py` with the SHIPPED command (wrong pattern).
- **Assertions per route**:
  - `n_way_merge_blob(repo, [one, two], "p.py")` raises `GitProbeError` (today it returns a blob for the union/driver routes);
  - `merge_own_changed_paths(repo, M)` raises `GitProbeError` (today it returns `[]` for the union/driver routes, which reads as "no own content");
  - the error text names the path and the attribute value or the config key (the contract text in `contracts/refusal-codes.md`).
- **Also red-first at the verifier seam** (one test each, same fixture shapes, using the real verifier, no mocks): a squash claim whose last-chance recognizer would attribute the union blob is REFUSED (`VerifyStatus.REFUSE`), and the merge-strategy closed world (`MergeOutcomeVerifier._unattributable_patch_id` via `verify`) REFUSES instead of skipping `M`. Building a full claim is heavy; a minimal hand-built `ApprovedWpCommitSet` with `enforce_closed_world=True`, `path_contributions` and `excluded_window_base` is acceptable (see `tests/consolidation/test_reconciliation.py` for hand-built claims). Keep these two tests few and focused.
- **Why they are red today**: `n_way_merge_blob`'s own docstring says a custom driver "is not detected" (`git_probes.py:938-941`), and `merge_own_changed_paths` calls `kernel.git.remerge_paths` with no attribute check (`git_probes.py:757-766`).
- **Record**: after running them red, `spec-kitty agent tasks add-history WP01 --note "T001 red: <n> attack tests fail on HEAD (<list>)"`.
- **Edge cases to cover in the parametrisation**:
  - the attribute is set on a DIFFERENT path than the probed one: the probe must not refuse (control: guard is per path, not global);
  - the attribute is set but the merge does not touch the path at all: `merge_own_changed_paths` does not refuse for an untouched path;
  - `merge=union` on a path where the two sides do not conflict: still refuses (over-refusal is the accepted fail-closed direction; pin it so nobody "optimises" it into a pass).
- **Validation**:
  - each attack param fails on HEAD with the specific symptom (blob returned / `[]` returned), not with an unrelated error: assert the HEAD symptom in a comment-free precondition helper you delete once green, or record the red output in WP history;
  - `pytest -q tests/consolidation/test_merge_attribute_guard.py` lists one failure per route and probe.
- **Files**: `tests/consolidation/test_merge_attribute_guard.py`.
- **Parallel?**: no; it defines the contract the rest of the WP satisfies.

### Subtask T002 - `registered_merge_driver_specs()` accessor (recorded leeway)

- **Purpose**: the guard needs the registry's `(config_key, command, pattern)` triples; `_MERGE_DRIVERS` is private and its file belongs to WP07.
- **Steps**:
  1. In `src/specify_cli/lanes/consolidation.py`, directly after `merge_driver_attribute_lines()` (`:533-535`), add:
     ```python
     def registered_merge_driver_specs() -> tuple[tuple[str, str, str], ...]:
         """``(config_key, command, pattern)`` of every registered driver, in registry order (FR-010)."""
         return tuple((spec.config_key, spec.command, spec.pattern) for spec in _MERGE_DRIVERS)
     ```
     Plain string triples, so no private class (`_MergeDriverSpec`, `:45-64`) leaks out. Two registry rows share `spec-kitty-event-log` with two patterns (`:72-94`); keep both rows (a key may have several patterns).
  2. No subprocess, no env (the AC-F1 ratchet in `tests/architectural/test_merge_pipeline_ratchets.py:168-211` scans this file).
- **Test**: one unit test in `test_merge_attribute_guard.py` that every triple's `pattern` is a `kitty-specs/**` pattern and that the de-duplicated rendered lines agree: `tuple(dict.fromkeys(f"{pattern} merge={key}" for key, _cmd, pattern in registered_merge_driver_specs())) == merge_driver_attribute_lines()`. `merge_driver_attribute_lines()` de-duplicates with `dict.fromkeys` (`lanes/consolidation.py:535`), so compare de-duplicated lines, never the raw triple count. The two views of the registry then cannot drift.
- **Notes**: this is the only out-of-map edit. Do not touch `_MERGE_DRIVERS`, `install_merge_driver_config` or anything else in that file.
- **Steps**:
  1. Add the function with a one-line docstring naming FR-010 and the reason it exists (the guard's allowance).
  2. Add it to the module's `__all__` if the module declares one (check before editing).
  3. Add the drift test (below) in WP01's own test file, not in a WP07-owned test.
- **Why not reuse `merge_driver_attribute_lines()`**: it renders `"<pattern> merge=<key>"` strings and drops the command, and the guard must compare the configured command with the registered one (a redefined `merge.spec-kitty-meta.driver` is an attack route). Parsing the rendered lines back would be a second, lossy view of the registry.
- **Edge cases**:
  - a registry key with several patterns (`spec-kitty-event-log`) yields several triples; the guard treats a path as matching if ANY pattern of its key matches;
  - `superseded_names` (`lanes/consolidation.py:58-60`) are display names, not commands; they play no role in the guard.
- **Validation**:
  - `uv run --frozen mypy src/specify_cli/lanes/consolidation.py` clean;
  - `tests/architectural/test_merge_pipeline_ratchets.py` still green (AC-F1 env routing; you add no subprocess call);
  - WP07 owns this file: mention the accessor in your history note so WP07's implementer does not remove it while reworking `consolidate_lane_into_mission`.
- **Files**: `src/specify_cli/lanes/consolidation.py` (leeway), `tests/consolidation/test_merge_attribute_guard.py`.
- **Parallel?**: yes with T001 (different file), but T003 needs it.

### Subtask T003 - `merge_attribute_guard.py`: one batched check, fail closed

- **Purpose**: one function that decides, for a set of paths in one checkout, whether git's merge of those paths could run anything other than its built-in merge or a registered spec-kitty driver.
- **File**: `src/specify_cli/consolidation/merge_attribute_guard.py` (new). Public entry point, for example:
  ```python
  def assert_registered_merge_behaviour(repo_root: Path, paths: Sequence[str]) -> None:
      """Raise GitProbeError when an effective merge attribute or driver for any of *paths* is unregistered (FR-010)."""
  ```
  Import direction (keep it acyclic): the guard imports `GitProbeError` from `git_probes` at module top; `git_probes` imports the guard **function-locally** inside the two probes (the same lazy pattern as `git_probes.py:1065`); the guard imports `registered_merge_driver_specs` from `lanes.consolidation` function-locally. Optionally define `class MergeAttributeRefused(GitProbeError)` in the guard so tests can assert the specific refusal; callers keep catching `GitProbeError`. Pin the import order with a fresh-interpreter test (`subprocess.run([sys.executable, "-c", "import specify_cli.consolidation.merge_attribute_guard"])`, and the same for `git_probes` and `lanes.consolidation` imported first).
- **Rule** (R-06, extended by the probe in this prompt). For each path, read the effective `merge` attribute with ONE call: `git check-attr --stdin merge` run in `repo_root`, stdin = one path per line. It reports every attribute source git itself uses: `info/attributes`, the checkout's `.gitattributes` (committed or not), `core.attributesFile`, `GIT_ATTR_SOURCE` / `attr.tree`. Then read the effective merge config ONCE: `git config --get-regexp ^merge\.` (no `--local`: global and system scopes count). The path is allowed only when one of these holds:
  - value `unspecified` AND `merge.default` is not configured;
  - value `set` or `unset` (`merge` set is git's built-in text merge with no user lookup; `-merge` keeps ours and conflicts: neither can forge bytes);
  - value `text` or `binary` AND `merge.<value>.driver` is not configured;
  - value is a registered `config_key` AND the path matches one of that key's registered patterns AND `merge.<key>.driver` is either not configured (git then falls back to its built-in merge) or equals the registered command exactly.
  Everything else refuses: `union`, any other name, a registered name on a non-matching path, a registered name with a different command. Also refuse when any `merge.<name>.recursive` is configured for a name in play (a recursive driver runs on the virtual merge base).
- **Output parsing** (no `-z`, see Context): `check-attr` prints exactly one line per input path, in input order, `<quoted path>: merge: <value>`. Take the value with `line.rpartition(": ")` (the existing `_resolve_merge_driver_config_key` does the same, `git_probes.py:1038-1044`); never parse the path text. Refuse (raise) when:
  - a path contains `\n` (it cannot be fed to `--stdin` without `-z`);
  - the line count differs from the path count;
  - git exits non-zero or cannot be started.
- **Pattern matching**: implement a small `_matches_registered_pattern(pattern, path)` that translates gitattributes wildmatch for exactly the tokens the registry uses: a leading anchored `kitty-specs/`, `**/` (zero or more directories), `*` (no `/`), literal text. Raise (refuse) for any other wildmatch token (`[`, `?`, `\`, a trailing `/**`). A unit test runs every registry pattern through it with positive paths (`kitty-specs/a/status.events.jsonl`, `kitty-specs/a/b/tasks/WP01/review-cycle-1.md`) and negative paths (`src/kitty-specs/a/meta.json`, `kitty-specs/a/meta.json.bak`, `kitty-specs/a/traces/x/y.md`).
- **Error text** (`contracts/refusal-codes.md`): `merge attribute '<value>' from the effective git attributes applies to <path>; refusing to classify a merge whose resolution git would compute with an unregistered driver` and, for a config route, name the key (`merge.default`, `merge.binary.driver`, `merge.spec-kitty-meta.driver`). The contract's `<source>` cannot be named precisely: `check-attr` does not report which file set the value. Use the fixed phrase above and record this in `traces/design-decisions` via add-history.
- **Complexity**: split into `_effective_attributes`, `_merge_config`, `_path_refusal` (pure: value + config + path -> reason or None) and the entry point. `_path_refusal` is pure and gets direct parametrised unit tests for every branch (no git), which keeps coverage cheap.
- **Edge cases**:
  - empty `paths`: return without spawning git;
  - an operator who customised a spec-kitty driver (`install_merge_driver_config` keeps customised values, `lanes/consolidation.py:680-708`) now refuses on any probed path that driver maps. That is FR-010 working as specified; the message must name the key and the shipped command so the operator can restore it;
  - a path that matches TWO lines with different values: `check-attr` already resolves precedence and prints the winner, so the guard judges only the printed value (do not re-implement precedence);
  - `GIT_ATTR_SOURCE` set in the environment: honoured by `check-attr` the same way the probe's own git call honours it, because both run with the same environment. Do not pass a custom `env=` to one and not the other.
- **Reference implementation note**: the existing `_resolve_merge_driver_config_key` (`git_probes.py:1002-1045`) uses `check-attr --source <ref>` to read a COMMITTED tree. The guard must NOT pass `--source`: the probes (`merge-tree`, `show --remerge-diff`) read the checkout's attributes, and so must the guard.
- **Validation**:
  - unit tests for `_path_refusal` cover each allowed branch and each refusing branch (union, custom name, `merge.default`, `text`/`binary` with driver, registered key on wrong path, registered key with wrong command, `recursive` configured);
  - a git-backed test with three paths in one call proves one `check-attr` process (count calls with a thin wrapper or `monkeypatch` on the runner; do not mock git's answer);
  - a git failure (non-repo directory) raises `GitProbeError`.
- **Files**: `src/specify_cli/consolidation/merge_attribute_guard.py`, `tests/consolidation/test_merge_attribute_guard.py`.
- **Parallel?**: no; T004 consumes it.

### Subtask T004 - Wire the guard into both probes; cache per run

- **Purpose**: both probes, and therefore every caller (squash recognizer, merge-strategy closed world, FR-004 later), fail closed through one guard.
- **Steps**:
  1. `n_way_merge_blob` (`git_probes.py:924-952`): when `len(commits) >= 2`, call the guard for `[path]` before `_n_way_merge_fold`. A single commit is not a merge; no guard. The fold cache stays as it is (`MergeFoldCache`, `:883`); a refusal raises and is never cached (matches the fold's own rule, `:891-893`).
  2. `merge_own_changed_paths` (`git_probes.py:740-766`): after the octopus and git-version checks, collect every path the merge changed relative to EACH parent: `kernel.git.changed_paths(repo_root, parent, sha)` for both parents (the same helper `first_parent_changed_paths` uses, `:850-863`). A union-forged path differs from at least one parent, so it is always in this set, even though remerge-diff no longer lists it. Call the guard once with the union of both lists, THEN run `remerge_paths`. A `GitCommandError` from the listing raises `GitProbeError`.
  3. Update both docstrings: remove "this probe does not detect one" from `n_way_merge_blob` (`:938-941`) and state the FR-010 rule. Do NOT edit `reconciliation_verifier.is_legitimate_merge_resolution`'s docstring (`reconciliation_verifier.py:957-962`, "this recognizer does not detect it"): that file is owned by WP06, and WP06 fixes that sentence (its T030; WP06 depends on WP01).
  4. **Caching (NFR-001)**: the config read is a function of the repository config, so route it through `kernel.git.read_cache.cached_git_read(repo_root, ("merge-config",), compute, depends=Depends(config=True))` (pattern: `lanes/consolidation._git_config_get`, `:479-501`). Outside a run scope it is a plain read. Do NOT cache `check-attr`: it reads the working tree, and `read_cache.py`'s rule is that working-tree reads are never cached (`kernel/git/read_cache.py:33-35`).
  5. **Git version once per run (NFR-001)**: at HEAD `merge_tree_probe._git_at_least` (`src/specify_cli/git/merge_tree_probe.py:57-65`) spawns `git --version` through `subprocess.run` on EVERY call, and `merge_own_changed_paths` calls `remerge_diff_available` once per probed merge (WP10 adds another caller). Route the version read through the existing cached read helper: `kernel.git.read_cache.cached_git_read(repo_root, ("git-version",), _read_git_version, depends=Depends(), store_if=lambda v: v is not None)` (`kernel/git/read_cache.py:158`, `Depends` at `:97`), where `_read_git_version(repo_root) -> tuple[int, int] | None` runs `git --version` once and parses it; `_git_at_least` compares the cached tuple. An empty `Depends()` makes the answer reused for the whole scope; an unreadable version (`None`) is not stored, so it is re-read and still fails closed. Outside a scope it is a plain read, exactly as today. Keep the module free of `specify_cli` imports (its docstring: a neutral, dependency-free module); `kernel.git.read_cache` is a kernel import, which the layering allows. The public functions and `__all__` are unchanged.
     - **Test** (`test_merge_attribute_guard.py`): `test_git_version_is_read_once_per_run_scope`: inside `git_read_cache_scope()`, call `merge_own_changed_paths` on THREE different merges (or `remerge_diff_available` + `merge_tree_write_tree_available` several times) with `subprocess.run` wrapped by a counting spy that delegates; assert exactly one call whose argv is `["git", "--version"]`. Control in the same test: outside a scope, two calls spawn two. Red at HEAD (HEAD spawns one per call).
- **Callers already fail closed**: the squash axis catches `GitProbeError` and REFUSES (`reconciliation_verifier.py:746-749`, `:776-779`); the merge axis does too (`:411-420`). You do not need to touch them. Assert it in T001's verifier-level tests.
- **Process budget**: `merge_own_changed_paths` gains two diff listings, one `check-attr` and one cached config read. That is within NFR-001 as restated ("one attribute query per probed merge"); note it in the PR.
- **Ordering inside `merge_own_changed_paths`**: keep the existing early refusals first (octopus `:757-758`, git version `:759-760`) so their messages are unchanged; then the parents' diff listing; then the guard; then `remerge_paths`. The return value for an allowed merge is byte-identical to today.
- **"The kernel remerge path they share"** (tasks.md wording): both probes reach git's merge machinery through `kernel.git.merge_tree` (`kernel/git/listing.py:460-472`) and `kernel.git.remerge_paths` (`:491-498`). Guard at the `git_probes` level, not inside the kernel helpers: other kernel callers (`lane_cleanup._absorbed_but_for_status_log`, `lane_tip._merge_tree_no_op`) are not attribution probes and must not change. Note this scoping decision in history.
- **Edge cases**:
  - a merge whose parent cannot be read: `changed_paths` raises `GitCommandError` -> `GitProbeError` (fail closed, same as `commit_parents`);
  - a merge that changed no path relative to either parent (an empty merge): guard called with `[]`, no process, then `remerge_paths` as today;
  - the fold cache: a refused path must not populate the cache for OTHER paths of the same fold. Because the guard runs before `_n_way_merge_fold`, a refusal never reaches the cache.
- **Red tests owned by this subtask** (add them before the wiring, beside T001's):
  1. `test_merge_own_changed_paths_guards_paths_changed_against_either_parent`: union attribute on a path changed only relative to the SECOND parent (the first parent already had the final bytes) still refuses. This catches a lazy fix that lists only first-parent changes (`first_parent_changed_paths`).
  2. `test_n_way_merge_blob_single_commit_is_not_guarded`: with `merge=union` on the path, a one-commit fold returns `path_state_at` exactly as today (no refusal: nothing is merged).
  3. `test_config_read_is_cached_inside_a_run_scope`: inside `git_read_cache_scope()`, two guard calls on the same repo spawn `git config` once (use the scope's stats object: `hits >= 1`).
  4. `test_check_attr_is_not_cached`: inside a scope, write an uncommitted `.gitattributes` between two calls; the second call refuses. This is the working-tree read the cache must never serve.
- **Steps, in order**:
  1. add the function-local import of the guard entry point inside both probes;
  2. add the parents' changed-path collection helper (private, `_paths_changed_against_parents(repo_root, sha, parents)`), reusing `commit_parents` already called for the octopus check so the parents are read once;
  3. call the guard; then the existing body;
  4. update docstrings;
  5. run T001 + the four tests above; then the blast radius below.
- **Validation**: T001 goes green; `tests/consolidation/test_merge_derivation_7626.py` and `tests/consolidation/test_dependency_merge_attribution_7307.py` (both exercise these probes on unattributed fixtures) stay green unchanged.
- **Files**: `src/specify_cli/consolidation/git_probes.py`, `tests/consolidation/test_merge_attribute_guard.py`.
- **Parallel?**: no.

### Subtask T005 - Positive control: spec-kitty's own drivers are unchanged [P]

- **Purpose**: the tool installs its own drivers locally (`_ensure_merge_driver_git_config`, `lanes/consolidation.py:598-624`; info attributes seeded by `_ephemeral_merge_driver_activation`, `:728-767`) and this repository commits the same mappings (`.gitattributes:13-20`). Those must keep working.
- **Tests** (in `test_merge_attribute_guard.py`):
  1. Install the drivers with the real `install_merge_driver_config(repo)` and seed info attributes with `merge_driver_attribute_lines()`. A merge whose own content is on `kitty-specs/<this>/status.events.jsonl` and `kitty-specs/<other-mission>/meta.json` (another Mission's file, which `_is_bookkeeping` does NOT exempt, `reconciliation_kernel.py:43-90`) passes the guard, and `merge_own_changed_paths` returns exactly what it returns today without the guard (compare against a run with the guard monkeypatched to a no-op, as a differential, NOT as the main assertion).
  2. A path with no attribute and no `merge.default` passes.
  3. A committed `.gitattributes` mapping a registered driver to its registered pattern, with the driver config ABSENT, passes (git falls back to its built-in merge).
  4. `merge=set` (attribute `merge` without value) passes.
- **Committed attributes (the pending operator question, Context)**: this repository's own `.gitattributes:41` sets `kitty-ops/lifecycle.jsonl merge=union`.
  - Under default (a), write: `test_committed_union_is_honoured_with_the_pre_run_tip_as_source` (a committed `.gitattributes` with `merge=union`, `attributes_source=<that commit>`, no clone-local source, no `merge.union.driver`: the guard passes); `test_committed_union_refuses_without_a_source` (`attributes_source=None`: refuses); `test_committed_union_refuses_when_info_attributes_also_sets_it` (the same committed line plus the same line in `.git/info/attributes`: refuses, the clone-local leg); `test_committed_union_refuses_when_the_checkout_differs` (an uncommitted edit of `.gitattributes` changes the value: refuses); `test_committed_union_refuses_with_a_union_driver_configured` (`merge.union.driver` set: refuses); `test_committed_union_refuses_on_git_older_than_2_40` (monkeypatch the cached version read to `(2, 39)`: refuses).
  - Also required by the ruling: `test_committed_binary_refuses_with_a_binary_driver_configured` (committed `merge=binary` plus `merge.binary.driver` forging bytes: refuses). The repo's own `kitty-ops/lifecycle.jsonl merge=union` line is honoured under (a).
  - Either way, no exemption by path name (C-002).
- **Steps**:
  1. Build a small repo with a Mission-shaped tree: `kitty-specs/this-mission/status.events.jsonl`, `kitty-specs/other-mission/meta.json`, `src/app.py`.
  2. Run the real `install_merge_driver_config(repo)` (`lanes/consolidation.py:680`) and append `merge_driver_attribute_lines()` to `.git/info/attributes` (the same lines `_ensure_info_attributes` writes, `:538-563`).
  3. Make two branches that both append to the event log and both edit `other-mission/meta.json`; merge them by hand with a resolution on `src/app.py` only.
  4. Assert: `merge_own_changed_paths(repo, M) == ["src/app.py"]` (the event log and meta merges resolve through the registered drivers, which needs `spec-kitty` on PATH in the test environment: if the driver binary is not resolvable in the test env, use a fixture where those files change on ONE side only, so no driver runs, and assert the guard still passes them).
  5. Assert `n_way_merge_blob` on `kitty-specs/other-mission/meta.json` returns a blob (no refusal).
- **Why the differential**: the main assertion must be on the observable result (paths returned, blob returned). The differential only proves "unchanged"; on its own it would pass if both runs were broken in the same way.
- **Edge cases**:
  - the auto-rebase path defines driver config but does NOT seed info attributes (`lanes/consolidation.py:598-624` docstring, the #2709/#2711 split); with a repository that commits no `.gitattributes`, the registered patterns are then `unspecified` and pass trivially. Include one such fixture so a regression that starts requiring the driver to be active is caught;
  - `kitty-specs/**/tasks/*/review-cycle-*.md` (a registered pattern with a `*` mid-path) must match `kitty-specs/m/tasks/WP01/review-cycle-2.md` and must not match `kitty-specs/m/tasks/WP01/sub/review-cycle-2.md`.
- **Validation**: all four positive tests green; `tests/consolidation/test_merge_drivers.py`, `test_gate_artifact_merge_drivers_2804.py` and `test_ephemeral_driver_activation_2709.py` unchanged and green.
- **Files**: `tests/consolidation/test_merge_attribute_guard.py`.
- **Parallel?**: [P] yes, once T003's entry point exists; it does not depend on T004 for the guard-level controls.

## Test Strategy

Write T001 first and watch it fail. Commands (targeted files only):

```bash
uv run --frozen pytest -q tests/consolidation/test_merge_attribute_guard.py
uv run --frozen pytest -q tests/consolidation/test_merge_derivation_7626.py tests/consolidation/test_dependency_merge_attribution_7307.py \
  tests/consolidation/test_git_probes_seam.py tests/consolidation/test_git_probes_git_paths.py tests/consolidation/test_reconciliation.py \
  tests/consolidation/test_merge_drivers.py tests/consolidation/test_ephemeral_driver_activation_2709.py tests/consolidation/test_reconciliation_module_imports.py
uv run --frozen pytest -q tests/specify_cli/git/test_merge_tree_probe.py tests/lanes/test_lane_tip.py   # the version probe's own tests fake subprocess.run outside a scope: they must stay green unchanged
uv run --frozen pytest -q tests/architectural/test_git_path_listing_owner.py tests/architectural/test_merge_pipeline_ratchets.py tests/architectural/test_layer_rules.py
make test-fast
```

No full heavy suites and no bare `tests/architectural/` (NO_FULL_HEAVY_SUITES_IN_MISSION).

Quality gates on every changed file:

```bash
uv run --frozen ruff check src/specify_cli/consolidation/git_probes.py src/specify_cli/consolidation/merge_attribute_guard.py src/specify_cli/git/merge_tree_probe.py src/specify_cli/lanes/consolidation.py tests/consolidation/test_merge_attribute_guard.py
uv run --frozen ruff format --check --force-exclude src/specify_cli/consolidation/git_probes.py src/specify_cli/consolidation/merge_attribute_guard.py src/specify_cli/git/merge_tree_probe.py src/specify_cli/lanes/consolidation.py tests/consolidation/test_merge_attribute_guard.py
uv run --frozen mypy src/specify_cli/consolidation/git_probes.py src/specify_cli/consolidation/merge_attribute_guard.py src/specify_cli/git/merge_tree_probe.py src/specify_cli/lanes/consolidation.py
```

Complexity <= 15 for every function (ruff C901 is configured). No `# noqa`, no `# type: ignore`.

Record the exact commands and pass/fail counts in WP history (`spec-kitty agent tasks add-history WP01 --note "tests: ..."`).

**Tracer notes**: this code WP cannot own `kitty-specs/` paths. Record friction, approach and design notes with `spec-kitty agent tasks add-history WP01 --note "trace(<tooling-friction|approach|design-decisions>): ..."`, so the Mission's `traces/{tooling-friction,approach,design-decisions}.md` can be filled from history. Expected design-decision entries: the allowed-value table (including `set`, and the `text`/`binary` driver-override finding), the fixed `<source>` phrase, the cycle-avoidance choice, the committed-attribute ruling (option (a), operator 2026-11-20) and its `kitty-ops/lifecycle.jsonl` consequence, and the git-version cache.

## Risks & Mitigations

- **Over-refusal on real repositories.** A repository that commits `merge=union` on a content path, or an operator with a customised spec-kitty driver, now gets refusals where it did not. This is the specified fail-closed behaviour; the message names the path and value or key. Mitigation: T005 pins the registered-driver path unchanged, and the `kitty-ops/lifecycle.jsonl` consequence is reported to the orchestrator rather than silently exempted.
- **Import cycle** (`lanes/consolidation.py:40` imports `git_probes`). Mitigation: function-local import; a fresh-interpreter import test.
- **Output order assumption** in `check-attr --stdin`. Mitigation: count check, newline-path refusal; never parse the path text.
- **Path listing gate.** A `-z` split in `consolidation/` fails `test_git_path_listing_owner.py`. Mitigation: no `-z`; run that gate.
- **Cost.** One extra `check-attr` per probed merge (three under default (a) when `attributes_source` is passed) plus two diff listings. Mitigation: config read and git version cached via `cached_git_read`; guard skipped for single-commit folds and empty path sets.
- **Global config in tests.** Tests that set `core.attributesFile` or a driver must use repo-local config or an isolated HOME (the root test fixture isolates HOME per worker); never write the developer's real `~/.gitconfig`.

## Review Guidance

Anti-fake checks (from `squad2/reviewer-renata.md`, FR-010 findings):

- The attack set covers the working-tree `.gitattributes` and `core.attributesFile` routes, not only `info/attributes` and a local driver. A fix that reads only `$GIT_COMMON_DIR/info/attributes` and `git config --local merge.*.driver` must fail at least two tests.
- The remerge leg (`merge_own_changed_paths`) is guarded and tested, not only the fold. Confirm the verifier-level merge-strategy test REFUSES.
- Spec-kitty's drivers are allowed by the (key, command, pattern) triple, never by driver name alone: the "registered name, redefined command" test refuses.
- The `text`/`binary` override and `merge.default` routes are tested; `merge.default` is invisible to `check-attr`.
- Every guard failure path raises `GitProbeError` (or its subclass); grep the new module for any `except` that returns instead of raising.
- The leeway edit in `lanes/consolidation.py` is exactly one accessor; nothing else changed there.
- `merge_tree_probe.py` reads the git version through `cached_git_read`, and the subprocess-count test proves one `git --version` per run scope across several probed merges.
- Under default (a): a committed `union` is honoured only with `attributes_source` passed, git >= 2.40, an equal effective value, an `unspecified` empty-tree (clone-local) read and no `merge.union.driver`; `info/attributes` plus a committed line still refuses.
- Confirm the implementer ran mypy as well as pytest, and that compiler diagnostics passed.

## Progress & Status

Progress, history, and status all live in the status event log (`status.events.jsonl`), never in this prompt file. Do **not** hand-edit a history section here.

- **Record a progress note**: `spec-kitty agent tasks add-history WP01 --note "<what you did>"`
- **Change WP status**: `spec-kitty agent tasks move-task WP01 --to <status>`
- **View history and status**: `spec-kitty agent tasks status`
