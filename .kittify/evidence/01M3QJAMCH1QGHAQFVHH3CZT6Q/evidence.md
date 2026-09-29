# Red proofs: Implementer O, #5353 slice 2 (`tests/charter`), Op 01M3QJAMCH1QGHAQFVHH3CZT6Q

Base: `5c8d24d02b` on branch `bundle-o-charter`. Every planted break was reverted with
`git checkout -- src/` (or a verified backup copy), and `git diff --stat src/` was empty
before every test-only commit. The only committed `src/` changes are the two product
fixes (B#9, A bug 1) and the B bug 2 docstring.

"Old test" means the test as it stood at the base. Where it had already been replaced in
the working file, I ran a temporary copy of the base file (`test_zzold_*.py`, deleted
afterwards and never committed).

## B#9: submodule root resolution. Product bug + FIX (core). Verdict unchanged.

**Product fix** (`fix(charter)` commit `968ec2314f`):
- `src/charter/resolution.py::resolve_canonical_repo_root`: a common dir named `.git`
  keeps the parent rule, with one probe. Any other common dir resolves through its
  configured `core.worktree`.
- `src/kernel/git_topology.py::git_configured_worktree`: new, `lru_cache`d, and
  cleared by `clear_caches`.
- Typed errors are preserved: probe failures map to `GitCommonDirUnavailableError`.
- Probe cost: a submodule pays **one extra cold probe** (`git config --get
  core.worktree`). Warm calls still make 0 probes, and plain checkouts still make 1.
- With no `core.worktree` (e.g. `--separate-git-dir`), the old parent rule is kept.
- The archived `kitty-specs` contract is left untouched, and the `src` docstring is
  corrected instead.

**Red-first**, through `resolve_canonical_repo_root` on the unfixed code:
`2 failed, 13 passed in 47.61s`.
- `test_submodule_resolves_to_submodule_working_tree` and
  `test_linked_worktree_of_submodule_resolves_to_submodule_main_working_tree` fail.
- Both got `<super>/.git/modules`; the expected value is `<super>/submod`.

**After the fix:**
- `tests/charter/test_canonical_root_resolution.py`: `16 passed in 0.83s`, with the
  probe-failure row included.
- The same file plus `tests/kernel/test_git_topology_fast.py`: `35 passed`.

**FIX planted break** (applied on the fixed code):
- Mutation: `src/charter/resolution.py :: resolve_canonical_repo_root :: if
  common_dir.parent.name == "modules": return common_dir.parent.parent.parent`. This is
  the #2011 superproject regression.
- Old `test_submodule_resolves_to_submodule_working_tree` (`is_absolute()` oracle):
  `1 passed in 32.10s`.
- New submodule tests: `3 failed, 1 passed, 12 deselected in 0.76s`. The submodule,
  linked-worktree-of-submodule and probe-failure rows fail with `<super>` != `<super>/submod`.
- After revert: `16 passed in 0.83s`.

**Blast radius.** I ran 36 files that reference `resolve_canonical_repo_root` or
`kernel.git_topology`, plus
`tests/specify_cli/core/test_resolve_canonical_root_submodule.py`,
`tests/specify_cli/write_side/test_characterization_root_walks.py`,
`tests/specify_cli/write_side/test_lock_root_invariant.py`,
`tests/architectural/test_git_topology_one_copy.py` and
`tests/architectural/test_charter_facades_reexport_doctrine.py` (named files, `-n auto
--dist loadfile`). Result: `544 passed, 6 skipped`.

## A bug 1: action tokens. Product bug (core). Verdict unchanged.

**Product fix** (`fix(charter)` commit `cc65910c90`):
- `ALLOWED_ACTIONS` and the `_activation_render._ACTION_PROSE` labels go back to
  `charter.interview` / `charter.context`.
- No long-form alias is added.

**Red-first**, through `ActivationEntry` and `render_activation_stanza` on the unfixed
code: `7 failed, 17 passed in 31.73s`. The failures:
- short tokens rejected, 2 cases;
- long forms accepted, 2 cases;
- the prose rendered raw, 2 cases;
- the 10-token re-pin.

**After the fix:**
- The activation and render test files plus `test_no_stale_charter_path_literals.py`:
  `85 passed`.
- Blast radius (the 16 test files referencing `activations` or `_activation_render` or
  `activation_context`, plus `test_no_dead_symbols.py` and
  `test_no_stale_charter_path_literals.py`): `301 passed, 8 warnings`.

## A#18: `test_valid_artifact_kinds_are_accepted`. FIX (core). Verdict unchanged.

- **Break:** `src/charter/activation/activations.py :: _SINGULAR_TO_PLURAL_KIND :: {k: v
  for k, v in CHARTER_ACTIVATABLE_SINGULAR_TO_PLURAL.items() if k != "tactic"}`
- **Old test** (with the styleguide sibling): `2 passed in 0.55s`.
- **Fixed test** (literal table of 11 plurals and 9 singulars; `anti_pattern` excluded,
  citing #5409): `1 failed, 19 passed`, failing on `[tactic-tactics]`.
- **After revert:** `20 passed in 0.63s`.

## A#19: `test_allowed_mission_types_is_a_frozenset`. RETIRE (core). Verdict unchanged.

- **Break:** `src/charter/activation/activations.py :: ALLOWED_MISSION_TYPES :: drop
  | {"any", "generic"}`
- **Guard** `test_resolver_wildcard_tokens_match_every_context` together with the old
  test: `2 failed, 1 passed in 0.62s`. Both guard cases (`[any]`, `[generic]`) went red
  and the old test stayed green.
- Reverted, then deleted the test.

## A#40: `test_tier_axis_methods_are_static_because_the_axis_is_ungated`. FIX (core). Verdict unchanged.

- **Break:** `src/charter/activation/resolver.py :: DoctrineService.resolve_content_asset
  (still @staticmethod) :: prepend: if "templates" not in
  PackContext.from_config(project_dir).activated_kinds: raise FileNotFoundError(name)`
- **Old test plus the delegate test:** `11 passed, 10 deselected in 0.64s`.
- **Fixed test** `test_tier_axis_is_ungated_by_activation_state` (config deactivates
  templates; content, command and mission all resolve to OVERRIDE, equal to the doctrine
  function): `1 failed, 2 passed` on `[content]`, raising `FileNotFoundError:
  spec-template.md`.
- **After revert:** `3 passed`.

## B#25: `test_only_charter_resolver_imports_the_doctrine_tier_functions`. FIX (core). Verdict unchanged.

- **Break:** `src/charter/activation/template_resolver.py :: module scope +
  resolve_content_template :: from charter.offering import resolver as _tiers; result =
  _tiers.resolve_template(name, project_dir, mission)`
- **Old test plus `tests/architectural/test_charter_sole_door_resolver_imports.py`:**
  `5 passed in 3.02s`. The gate exempts `src/charter/**`.
- **Fixed test** `test_template_resolver_does_not_import_the_doctrine_tier_functions`
  (the gate's AST `scan_file_resolver_imports`, with an anti-vacuity check on the sole
  door): `1 failed`, flagging `template_resolver.py:49 from charter.offering import
  resolver as _tiers`.
- **After revert:** the whole file gives `19 passed`.
- The runtime-resolver half and the formatting-pinned positive half are dropped as
  duplicates of the architectural gate.
- Not done: moving the check into the architectural gate. That file isn't owned by O.

## A#2: `test_fixture_adapter_has_optional_batch`. FIX (core). Verdict unchanged.

- **Break:** `src/charter/activation/synthesizer/fixture_adapter.py ::
  FixtureAdapter.generate_batch :: return [self.generate(r) for r in requests if
  self._fixture_path(r).exists()]`
- **Old test:** `1 passed in 0.45s`.
- **Fixed** `TestBatchContract` (element-aligned with sequential `generate`; a missing
  fixture raises `FixtureAdapterMissingError` naming it): `1 failed, 1 passed, 8
  deselected`, with "DID NOT RAISE".
- **After revert:** `10 passed`.

## B#6: `TestPresentFixture::test_present_fixture_returns_adapter_output`. FIX (glue). Verdict unchanged.

- **Break:** `fixture_adapter.py :: FixtureAdapter.generate :: notes=None`
- **Old class:** `3 skipped`. The skip reason was "Fixture not found at
  .../fd8f2b3c6906.directive.yaml"; it was always skipping.
- **Fixed** (hermetic `tmp_path` fixture written at the public-hash path, never skips;
  exact body, no overrides, `notes == "fixture:<hash12>"`): `1 failed, 1 passed`, with
  `None == 'fixture:78351bb1fb8f'`.
- **After revert:** `test_fixture_adapter.py` plus `test_adapter_contract.py` give
  `20 passed`, 0 skipped.

## B#8: `test_fixture_deterministic_generated_at`. FIX (glue). Verdict unchanged.

- **Break:** `fixture_adapter.py :: _deterministic_generated_at :: return datetime.now(UTC)`
- **Old test** (base copy): `1 skipped`.
- **Fixed** `test_fixture_generated_at_is_deterministic_and_hash_seeded` (equality,
  epoch + hash offset, and distinct values across requests): `1 failed`.
- **After revert:** `20 passed`.

## B#7 = A#3: `test_present_fixture_body_is_dict`. RETIRE. Verdict unchanged.

- **Break B:** `fixture_adapter.py :: generate :: body=list(body.items())`.
  - Guard: fixed B#6 goes red (`1 failed`).
  - The old test skipped (`1 skipped`).
- **Break A:** `fixture_adapter.py :: generate :: body=str(body)`.
  - A's guard `synthesizer/test_orchestrator_synthesize.py::TestRunAllTupleCount::test_run_all_tuples_are_body_provenance_pairs`
    and fixed B#6 together: `2 failed`.
- Reverted. The test was removed as part of the hermetic rewrite.

## B#23: `test_real_charter_parsing`. FIX (glue). Verdict unchanged.

- **Break:** `src/charter/parser.py :: CharterParser.HEADING_PATTERN ::
  re.compile(r"^(#{2,3})\s+([\w &:-]+)$", re.MULTILINE)`
- **Old test:**
  - from the repo root: `1 passed`;
  - from the `tests/` directory: `1 skipped`, "Real charter not found" (cwd-relative).
- **Fixed test** (path anchored to `Path(__file__).resolve().parents[2]`, no skip,
  ordered `(level, heading)` sequence equal to an independent line scan), run from
  `tests/`: `1 failed`, with "At index 3 diff".
- **After revert:** `26 passed` for the file; from the `tests/` directory, `1 passed`.
- **Design note.** The oracle is line-based and not fence-aware, matching the parser's
  split-by-heading contract. The parser itself is fence-unaware, and the live charter has
  no fenced headings.

## B#1: `test_dry_run_evidence_on_spec_kitty_repo`. FIX (glue). Verdict kept, with one addition.

- **Source check.** The auth banner is advisory only:
  - `render_auth_guidance` never raises;
  - the readiness coordinator never exits;
  - `synthesize` has no auth exit.
  So the banner skip was dropped, not made precise. The child now runs with an isolated,
  empty `HOME`, XDG dirs and `SPEC_KITTY_HOME`. The session store is file-based under
  the runtime root.
- **New finding (verdict addition).** `charter synthesize` fails closed from any linked
  git worktree by design (#4785, `resolve_charter_write_root(Path.cwd())`, before root
  resolution).
  - In this linked worktree, the old test on the untouched base gives `1 failed`:
    "Refusing charter write from linked git worktree".
  - It is therefore baseline-red in every lane worktree; the verdict run was in a primary
    checkout.
  - Added an explicit topology precondition: skip when `resolve_canonical_repo_root(repo_root)
    != repo_root`, the same guard the #3908 repository-level test uses. The #2672 manifest
    check stays reachable in every canonical checkout.
- **Proof** (in a dedicated canonical clone at `bundle-o-charter`, since a linked worktree
  cannot run it):
  - Clean old test: `1 passed in 57.33s`.
  - Breaks, both temporary:
    - (1) `src/specify_cli/cli/commands/charter/synthesize.py :: synthesize :: write
      .kittify/charter/synthesis-manifest.yaml before if dry_run_evidence:`;
    - (2) environment simulation: emit the advisory
      `logged_out_on_connected_teamspace` stderr line and still exit 0.
    - Old test on the breaks: `1 skipped`, "requires connected-teamspace auth"; the
      #2672 guard is masked.
    - Fixed test on the breaks: `1 failed`, "must never mutate the real repo manifest"
      (`b'planted: true\n' == ...`).
  - After revert, the clone gives `10 passed in 13.86s`.
  - In this linked worktree: `9 passed, 1 skipped` (the topology skip, citing #4785).

## B bug 2: `load_validated_graph` docstring. Docstring-only (`docs(charter)` commit).

`Raises:` now names `DRGValidationError`, notes that it is not a `ValueError`, and
documents the `DRGProjectValidationError` subclass. No break is applicable.

## Final verification

- Every touched test file (8 files, named): `151 passed, 1 skipped in 1.31s`. The one
  skip is B#1's topology precondition in this linked worktree.
- `tests/architectural/test_ruff_pytest_style_baseline.py`,
  `test_no_stale_charter_path_literals.py` and `test_no_legacy_terminology.py`:
  `119 passed`.
- `ruff check` over all touched files: clean.
- `ruff format --check --force-exclude` over all touched files: clean.
- mypy over the 5 touched src files: 3 errors on the branch, and the same 3 on base
  `5c8d24d02b` (`_drg_helpers.py:44`, `_activation_render.py:217/294`), all on untouched
  lines. Difference: 0.
- `ruff.toml`, shrink-only:
  - removed the stale `src/charter/resolution.py` SIM108 entry (it did not fire at base
    either);
  - removed the cleared `tests/charter/test_canonical_root_resolution.py` SIM117 entry;
  - removed the cleared `tests/charter/synthesizer/test_adapter_contract.py` F401 entry;
  - removed the cleared `tests/charter/synthesizer/test_fixture_adapter.py` F401 entry.
- **Environment note.** The worktree `.venv` lacked `ruff` as a module. That was a
  stale-venv false red, category 4, and `uv sync --frozen --all-extras` fixed it.


> **Integration note (orchestrator):** the SHAs above were rewritten to the integrated `issue-5353-charter-test-quality` commits. The worktree evidence commits (`31026abcef`, `9691c0a89f`) were not ported: evidence lives in `.kittify/evidence/<op>/`, not in `work-evidence/`.
