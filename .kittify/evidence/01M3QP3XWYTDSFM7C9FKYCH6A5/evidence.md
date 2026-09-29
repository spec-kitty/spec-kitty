# Review: #5353 slice 2 (`tests/charter`), Op 01M3QP3XWYTDSFM7C9FKYCH6A5

Reviewer: reviewer-renata (independent, read-only; planted breaks only, all reverted).
Range: `5c8d24d02b..237ee132d1` (12 commits, bundle O = Opus, bundle M = Sonnet).

## Verdict: APPROVE-WITH-NITS

Both product fixes are correct for every realistic topology I built. Every planted break I
re-ran turns the new test RED while the old test stays GREEN. Every retired test has a live,
non-vacuous guard. History, trailers, lint, mypy and the named gates are clean.

One finding (F1) is a small correctness gap in the new kernel probe. It is cheap to fix, and I
recommend folding it before merge. The rest are nits or deferred follow-ups.

## Environment

- Worktree detached at `237ee132d1`.
- `uv sync --frozen --all-extras` run once, because the venv was absent.
- All 23 touched test files, named (`-n 8 --dist loadfile`): **534 passed, 1 skipped**. The
  skip is B#1's topology precondition: this is a linked worktree.

## Planted breaks re-run (FIX items)

Every break was in `src/`, and each was reverted with `git checkout -- src/`; `git diff --stat src/` was empty afterwards.

| Item | Break (file :: symbol :: mutation) | New test | Old test (base copy) | Reverted |
|---|---|---|---|---|
| B#9 (core) | `charter/resolution.py :: resolve_canonical_repo_root ::` `if common_dir.parent.name == "modules": return common_dir.parent.parent.parent` (#2011 superproject) | RED, 3 failed / 1 passed (submodule, linked-wt-of-submodule, probe-failure) | GREEN, 1 passed (`is_absolute()`) | yes, 16 passed |
| B#9 (core), 2nd | same :: `return common_dir.parent` (the base rule, `<super>/.git/modules`) | RED, 3 failed | n/a (this is the base behaviour) | yes |
| B#9 one-probe contract | same :: drop the `.git` short-circuit, so plain checkouts pay the `core.worktree` probe | RED: `test_warm_call_uses_cache_no_git_invocation` (1 -> 2) and `test_cache_clear_resets_invocation_count` (2 -> 4) | n/a | yes |
| A#18 (core) | `activations.py :: _SINGULAR_TO_PLURAL_KIND :: {**..., "styleguide": "toolguides"}` | RED, `[styleguide-styleguides]` | old `test_valid_artifact_kinds_are_accepted` GREEN (its old styleguide sibling does catch this token; the new table covers all 9 singulars) | yes, 42 passed |
| A#40 (core) | `activation/resolver.py :: DoctrineService.resolve_command_asset ::` raise `FileNotFoundError` unless `"templates"` is activated (still `@staticmethod`) | RED, `[command]` | GREEN, 21 passed | yes |
| B#25 (core) | `template_resolver.py` + `specify_cli/runtime/resolver.py :: module scope :: from charter.offering import resolver as _tiers` | RED (charter test); the architectural gate also RED for the runtime half, which proves the dropped half is still covered | GREEN, 1 passed (the line-substring census misses the `from X import resolver` spelling) | yes |
| B#20/22 (core) | `mission_type_repository.py:430 ::` malformed-YAML branch raises `RuntimeError` instead of `ValueError` | RED, 2 failed / 1 passed | GREEN, 3 passed | yes, 62 passed |
| B#3 (of B#2–5) | `synthesizer/evidence.py :: CorpusEntry :: @dataclass(unsafe_hash=True)` + a hand-rolled `__setattr__` raising `AttributeError` | RED, `test_corpus_entry_is_frozen` | GREEN, 27 passed | yes |
| B#6 + B#8 | `fixture_adapter.py :: generate :: notes=f"fixture:{h[:8]}"` and `_deterministic_generated_at :: return _EPOCH` | RED, 2 failed (both `TestPresentFixture` tests) | 3 **skipped** (a permanent masked green: the fixture `fd8f2b3c6906` is absent) | yes, 20 passed |
| B#23 | `parser.py :: HEADING_PATTERN :: #{2,3} -> #{2}` | RED, 1 failed | GREEN from the repo root; **SKIPPED** from the `tests/` cwd | yes; the new test passes from the `tests/` cwd too |

Extra probe (for F3): I planted a hash drift in `request.py :: compute_inputs_hash`
(`sha256(b"drift" + raw)`). `test_fixture_adapter.py` stayed fully GREEN; only the golden
hashes in `test_request.py` caught it (3 failed).

## Covering guards re-run (RETIRE items)

| Item | Break | Guard | Result |
|---|---|---|---|
| A#20 | `mission_type_profile_repository.py:88 :: built_in_dir or (self._default_built_in_dir() / "nope")` | `test_mission_type_profile_override.py::TestShippedProfilesHonourInvariant::test_all_shipped_profiles_have_id_equal_to_mission_type` | RED: "shipped profile for 'documentation' did not load". **Not vacuous**: it iterates `['documentation', 'plan', 'research', 'software-dev']`, sourced from the separate `MissionTypeRepository`. |
| A#31 | `pack_context.py:266 :: pack_roots = [builtin_root, *org_pack_roots]` | `test_pack_context.py::test_pack_context_is_hashable` | RED (`unhashable type: 'list'`). Ordering is additionally pinned by `pack_roots[0]` / `[1]` index asserts. |
| A#32/33 | `pack_context.py:615 :: _read_list_key` returns a `set(...)` | same guard | RED (`unhashable type: 'set'`) |

**Coverage census.** 24 test functions were removed: 17 RETIRE plus 7 replaced FIX tests. Every
named guard is collected at HEAD, 19 node ids in all:
- `test_section_labels_are_nonempty_strings`
- `test_run_all_expected_count` and `test_run_all_tuples_are_body_provenance_pairs`
- `test_synthesize_result_has_target_kind` and `test_synthesize_result_has_inputs_hash`
- `test_software_dev_returns_builtin_sequence`
- `test_resolver_wildcard_tokens_match_every_context[any|generic]`
- `test_all_shipped_profiles_have_id_equal_to_mission_type`
- `test_action_normalized` and `test_mode_is_bootstrap_on_first_load`
- `test_explicit_operational_context_round_trip`
- `test_custom_type_accepted_without_validation_error`
- `test_pack_context_is_hashable`
- `test_valid_path_keys_matches_historical_specify_cli_value`
- `test_each_valid_key_accepted_individually[data]`
- `TestMissionTypePathConventionsField::test_all_valid_keys_accepted_together`
- `test_round_trip_without_references`
- `TestUnknownSelectors::test_unknown_kind_fails_closed`

The two `resolve_package_default_*` methods lost their `@staticmethod` pin (A#40). They take no
`project_dir`, so they cannot read activation state. No coverage is lost.

## Product fix 1: submodule root (B#9)

I checked the resolver on real topologies (scratch probe; cold/warm counts are git subprocess calls):

| Topology | Resolver | `--show-toplevel` | Cold / warm probes |
|---|---|---|---|
| plain checkout (dir, file) | `<super>` | `<super>` | 1 / 0 |
| linked worktree of plain | `<super>` (main) | `<superwt>` | 1 / 0 |
| submodule | `<super>/submod` | same | 2 / 0 |
| linked worktree of submodule | `<super>/submod` (submodule main) | `<subwt>` | 2 / 0 |
| nested submodule | `<super>/submod/nested` | same | 2 / 0 |
| `--separate-git-dir=<R>/sep.git` | `<R>` (wrong, pre-existing, unchanged) | `<R>/sepwork` | 2 / 0 |
| `--separate-git-dir=<R>/sep2/.git` | `<R>/sep2` (wrong, pre-existing) | `<R>/sep2work` | 1 / 0 |

- **Correctness.** The fix is correct for submodules, a linked worktree of a submodule, and
  nested submodules.
- **Probe contract.** The one-probe/cache contract holds for plain checkouts, and it is pinned
  (the planted break above goes red).
- **Typed errors.** They are preserved.
- **`--separate-git-dir`.** It stays wrong, exactly as before. Git writes no `core.worktree`
  there, and nothing in the common dir points back to the work tree. This is honest residual
  behaviour, not a regression (see F5).

## Product fix 2: action tokens (A bug 1)

- **Readers.** Only `_activation_render.py` (lines 61, 268–272) reads `ALLOWED_ACTIONS` /
  `_ACTION_PROSE`, and it is consistent after the fix.
- **No emitters.** No code in `src/` or `packs/` emits `charter.interview` / `charter.context`,
  or their long forms, as an action value (no `action=`, and no doctrine YAML `action:`).
- **Other hits.** Every other `charter.activation.interview|context` hit in `src/` is a
  module-path reference, which is legitimate.
- **Canonical source.** `kitty-specs/charter-mediated-doctrine-selection-01KRTZCA/data-model.md:203`
  is the §7 source, and it uses the short tokens.
- **Origin.** `git show e72f8b8a0b` confirms that commit introduced the long forms.

## Blast radius, lint and gates

- **Blast radius.** The 39 test files that reference `resolve_canonical_repo_root` or
  `git_topology` (excluding conftests), plus `tests/specify_cli/core/test_resolve_canonical_root_submodule.py`,
  run as named files: **447 passed, 7 skipped**. All skips carry a documented reason: 5 are
  `SPEC_KITTY_RUN_PERFORMANCE`, 1 is B#1, and 1 is the #3908 canonical-checkout skip.
- **`ruff check`** on all 28 touched `.py` files: clean.
- **`ruff format --check --force-exclude`**: clean. Only 6 files were in scope; the rest are
  format-excluded by repo config.
- **C901** on the 5 touched src files: clean.
- **mypy** on the 5 touched src files: 3 errors at HEAD and the same 3 at base
  (`_drg_helpers.py:44`, `_activation_render.py:217/294`, all on untouched lines). **Delta 0.**
- **Named gates**, 7 files, **238 passed**:
  - `test_ruff_pytest_style_baseline.py`, which is green after the venv sync; M's "pre-existing
    red" was the stale-venv category 4;
  - `test_no_stale_charter_path_literals.py`, `test_no_legacy_terminology.py`,
    `test_no_dead_symbols.py`;
  - `test_layer_rules.py`, `test_git_topology_one_copy.py`,
    `test_charter_sole_door_resolver_imports.py`.
- **History.**
  - The history is linear, with 0 merges.
  - Commits are sliced by concern (fix, then test, then docs); the M "retire" and "strengthen"
    commits mix a retire into a strengthen commit only within the same file.
  - The trailers are correct: 8 Opus 5.5 commits and 4 Sonnet 5 commits.
  - `git diff base..HEAD -- src/` shows only the two fixes and the docstring.
  - No `work-evidence/` or scratch files are committed.
  - The `ruff.toml` edits are shrink-only.

## Findings (ranked)

### F1 (Medium, FOLD, code). `core.worktree` probe reads global/system config
- **Where.** `src/kernel/git_topology.py:197`, `git_configured_worktree`.
- **Problem.** `git config --get core.worktree` also reads the global and system config. Git
  itself honours only the repository-local `core.worktree` (`read_repository_format` reads
  `$GIT_DIR/config` only).
- **Reproduced.** In a `--separate-git-dir` repo with
  `GIT_CONFIG_GLOBAL` holding `core.worktree = <B>/bogus`, `resolve_canonical_repo_root(<B>/work)`
  returns `<B>/bogus`, while `git rev-parse --show-toplevel` returns `<B>/work`. At base the
  result was `<B>` (wrong, but not a phantom path). The same leak affects bare repos and any
  other common dir not named `.git`.
- **Fix.** Use `["git", "--git-dir", str(resolved), "config", "--local", "--get", "core.worktree"]`.
  Verified: with `--local` the probe returns `rc=1` and empty output, so the result is `None`.
  - Add a kernel test asserting `--local` is in the argv, or a real-git test that sets
    `GIT_CONFIG_GLOBAL` through `monkeypatch.setenv`.
  - Optional: drop `cwd=str(resolved)`. It is redundant with `--git-dir`, and if the directory
    were missing it would make a `FileNotFoundError` surface as "git binary not found on PATH".

### F2 (Low, FOLD, code). The resolver docstring still points at a superseded contract row
- **Where.** `src/charter/resolution.py:82`.
- **Problem.** The docstring sends readers to `contracts/canonical-root-resolver.contract.md`
  "for the full behavioral matrix". That contract's submodule row (line 96, `<repo>/.git/modules`)
  and its note (line 100) are now contradicted by the code, and they stay untouched by ruling.
- **Fix.** Add one clause: "its submodule row and note are superseded by #5353, see below".

### F3 (Low, FOLD, code). The `TestPresentFixture` docstring overclaims hash-regression detection
- **Where.** `tests/charter/synthesizer/test_fixture_adapter.py:262`.
- **Problem.** The docstring says "a hashing or path regression fails instead of skipping". The
  fixture path is derived through `compute_inputs_hash` itself, which is hash-agnostic by
  design (verdict B#6). So a hash drift stays GREEN here, as the probe above shows; only the
  golden hashes in `test_request.py` catch it.
- **Fix.** Reword to "a path-layout or provenance regression fails instead of skipping; hash
  stability is pinned by the golden hashes in `test_request.py`".

### F4 (Low, FOLD, code). The test name no longer matches the oracle
- **Where.** `tests/charter/synthesizer/test_interview_mapping.py:445`, `test_context_is_dict`.
- **Problem.** The test now asserts the exact answer-context shape (`answer`, `kinds`,
  `source_section`, `answer_source`).
- **Fix.** Rename it to e.g. `test_answer_context_carries_answer_kinds_and_provenance`.

### F5 (Low, ADVISORY/DEFERRED). The two root authorities disagree inside a submodule
- **Where.** `src/specify_cli/cli/commands/charter/_charter_write_root.py:88`, compared with
  `src/charter/resolution.py`.
- **Problem.** `resolve_charter_write_root` still decides "linked worktree" with
  `common_dir.parent != toplevel`.
  - Reproduced: in a submodule's MAIN working tree it raises `LinkedWorktreeCharterWriteError`,
    while `resolve_canonical_repo_root` now returns that same working tree.
  - It is a pre-existing false refusal, identical at base, but it is now visibly inconsistent
    with the fixed resolver.
- **Fix (follow-up issue).** Decide linked-worktree status as
  `resolve_canonical_repo_root(start) != git_toplevel(start)`, so there is one authority for
  the root. Also file the pre-existing `--separate-git-dir` residual (table above) in the same
  issue.

### F6 (Low, ADVISORY). B#1's skip predicate is a proxy for the product predicate
- **Where.** `tests/charter/evidence/test_orchestrator.py:200`.
- **Assessment.** The skip is justified. The old test is baseline-red in every linked worktree
  by design (#4785), and it still runs in canonical clones and CI.
- **Problem.** The predicate uses `resolve_canonical_repo_root`, but the refusal comes from
  `resolve_charter_write_root`. Per F5 these disagree for a submodule checkout: a spec-kitty
  checkout vendored as a submodule would not skip and would go red.
- **Fix (optional).** Key the skip on the real predicate:
  `try: resolve_charter_write_root(repo_root) except CharterWriteRootError: pytest.skip(...)`.

### F7 (Low, ADVISORY). HOME isolation also hides the global git config
- **Where.** `tests/charter/evidence/test_orchestrator.py:210`.
- **Problem.** The isolated `HOME` / `XDG_CONFIG_HOME` also hides the global git config. In a
  container CI job, where `actions/checkout` records `safe.directory` globally, the child's git
  probes could hit "dubious ownership".
- **Status.** Not observed; flagged only as a risk.
- **Mitigation if it bites.** Keep `GIT_CONFIG_GLOBAL` pointing at the parent's global config.

### F8 (Low, ADVISORY). The Windows skip was extended to three new tests without evidence
- **Where.** `tests/charter/test_canonical_root_resolution.py:199,232`.
- **Problem.** The pre-existing reason ("submodule edge cases differ on Windows; documented in
  resolver contract") is now applied to 3 new tests. The contract documents no Windows
  difference, and `ci-windows.yml` is live, so the new product path has no Windows coverage.
- **Fix.** Either verify on Windows CI and drop the skip, or cite a tracking issue in the reason.

### F9 (Nit, ADVISORY). Duplicated `_record_fixture` helpers
- **Where.** `test_adapter_contract.py:58` and `test_fixture_adapter.py:236`.
- **Problem.** The two helpers are near-duplicates.
- **Fix (optional).** Hoist one helper into `tests/charter/synthesizer/conftest.py`.

### F10 (Nit, ADVISORY, pre-existing). Comments reference a non-existent test module
- **Where.** `src/charter/activation/activations.py:14,18,106,131`.
- **Problem.** The comments reference `tests.architectural.test_trigger_registry_coverage`, which
  does not exist. The "byte-identical" cross-check they promise is actually
  `test_allowed_actions_is_the_canonical_10_token_set`.
- **Fix.** Campsite-clean the comments to point at that test.

### Process notes (advisory, no code)
- **Stale SHAs.** `red-proofs-O.md` cites fix SHAs `bec8a33fae` / `94374e189e`; after the bundle
  merge the history carries `968ec2314f` / `cc65910c90`. Update the evidence file so the PR's
  audit trail resolves.
- **Shared stash.** `red-proofs-M.md` (baseline note) says `git stash` was used. The stash stack
  is shared across worktrees and sessions; use a WIP commit or a tagged stash with an apply-by-SHA
  step.

## Scope of what I did not verify

- B#1's positive run needs a canonical, non-linked checkout, and this review ran in a linked
  worktree, where the test skips as designed. I relied on O's dedicated-clone proof for that.
- I did not run anything on Windows.

---

## Disposition (orchestrator, fold commit `04dbc5223d`)

| Finding | Disposition |
|---|---|
| F1 | **Folded.** `git config --local --get core.worktree`; the new real-git test `test_worktree_probe_ignores_a_global_core_worktree` went RED without `--local` (it returned `<base>/bogus`) and GREEN with it. The redundant `cwd=` was dropped. |
| F2 | **Folded.** The docstring says #5353 supersedes the contract's submodule row. |
| F3 | **Folded.** The `TestPresentFixture` docstring now points to `test_request.py`'s golden hashes for hash stability. |
| F4 | **Folded.** Renamed to `test_answer_context_carries_answer_kinds_and_provenance`. |
| F5 | **Deferred** to #5411, together with the `--separate-git-dir` residual. |
| F6 | **Folded.** The skip is keyed on `resolve_charter_write_root` raising `CharterWriteRootError`. The test runs (not skips) in the primary checkout: 162 passed. |
| F7 | **Advisory, not folded.** No container failure has been observed. |
| F8 | **Deferred** to #5411 (verify on Windows, or cite the difference). |
| F9 | **Declined.** The `test_fixture_adapter.py` helper deliberately hardcodes the documented `directive/project-decision-doc-directive/<hash>.directive.yaml` layout. Sharing the contract helper, which derives the path from `request.target`, would make that oracle copy the product's path derivation. |
| F10 | **Folded.** The comments name `tests/charter/test_activations.py`'s real pins. |
| Process: stale SHAs | **Fixed.** Both red-proof files now carry the integrated SHAs. |
