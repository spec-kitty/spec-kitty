---
work_package_id: WP01
title: Exclude synthesis-owned directives from synthesis input
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- FR-008
- NFR-001
- NFR-002
- NFR-003
- C-001
- C-002
- C-003
- C-004
- C-005
- SC-001
- SC-002
- SC-004
planning_base_branch: issue-6510-resynthesis-after-activation
merge_target_branch: issue-6510-resynthesis-after-activation
branch_strategy: Planning artifacts for this mission were generated on issue-6510-resynthesis-after-activation. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6510-resynthesis-after-activation unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-resynthesis-after-activation-01M5ZD62
base_commit: 7ff1f4525cbfa704d4f85542fb3fe8367dbb6130
created_at: '2026-10-27T19:37:36.497254+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
phase: Phase 1 - Core fix
history:
- at: '2026-10-27T19:45:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/charter/
create_intent:
- tests/specify_cli/cli/commands/charter/test_resynthesis_after_activation_6510.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/cli/commands/charter/_synthesis.py
- src/charter/activation/synthesizer/manifest.py
- tests/charter/synthesizer/test_manifest.py
- tests/specify_cli/cli/commands/charter/test_resynthesis_after_activation_6510.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Exclude synthesis-owned directives from synthesis input

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

- **Has review feedback?** Check the `review_ref` field in the event log (`spec-kitty agent tasks status --mission resynthesis-after-activation-01M5ZD62`).
- Address every feedback item before declaring the work complete, and record each with `spec-kitty agent tasks add-history WP01 --note "..."`.

---

## Objective

After an operator activates any directive, `activated_directives` becomes an explicit list that also
contains the project directive synthesis promoted itself (stem `001-project-intent-directive`, id
`PROJECT_001`). `_build_synthesis_request` (`src/specify_cli/cli/commands/charter/_synthesis.py`)
turns every activated directive into a node of the request's graph snapshot (lines ~104–149). The
additive-only check in `src/charter/activation/synthesizer/project_drg.py:334-346` then refuses the
synthesis target `directive:PROJECT_001` because "it already exists". Synthesis collides with its own
output (#6510, #4226).

**Fix (operator ruling, see `research.md` D-1..D-3):** leave every directive that synthesis owns out of
both `interview_snapshot["selected_directives"]` and `drg_snapshot["nodes"]`. Ownership comes from the
existing record: the synthesis manifest plus each entry's provenance sidecar `artifact_urn`. Activation
is never touched, so delivery through `charter context` is unchanged.

Requirements: FR-001, FR-002, FR-003, FR-004, FR-005, FR-008, NFR-001, NFR-002, C-001..C-005; SC-001, SC-002, SC-004.

## Context

- Spec: `kitty-specs/resynthesis-after-activation-01M5ZD62/spec.md`
- Plan + alignment: `kitty-specs/resynthesis-after-activation-01M5ZD62/plan.md`
- Research (live reproduction recipe, decisions): `kitty-specs/resynthesis-after-activation-01M5ZD62/research.md`
- Data model: `kitty-specs/resynthesis-after-activation-01M5ZD62/data-model.md`
- Live reproduction scratch project (reference only, never commit from it): `/tmp/claude-0/-home-user-spec-kitty/d67a888b-959e-5297-84ce-eb8416451854/scratchpad/repro`

## Branch Strategy

- Planning base branch: `issue-6510-resynthesis-after-activation`
- Final merge target: `issue-6510-resynthesis-after-activation` (the operator opens/merges the PR to `main`; never push or merge `main`)
- The execution worktree is allocated per computed lane from `lanes.json`; use the workspace path that `spec-kitty agent action implement WP01 --agent claude --mission resynthesis-after-activation-01M5ZD62` prints. Do not construct worktree paths yourself.

## Constraints you must honour

- **C-002**: no code path you add may write `.kittify/charter/activation.yaml` or any `activated_*`/`deactivated_*` key.
- **C-003**: do NOT touch `project_drg.py`'s additive-only check. The exclusion happens where the request is built.
- **C-004**: do NOT edit `src/charter/activation/synthesizer/reach_only.py` or `reconcile.py` (mission M2 owns them).
- **C-005**: ATDD/red-first. The acceptance tests are committed failing (a separate commit) BEFORE the fix commit.
- Quality: zero new ruff / `ruff format` / mypy findings on touched files; no new `# noqa` / `# type: ignore`; complexity ≤ 15 per function; ≥ 90 % diff coverage.
- Terminology: "Mission", never "feature", in any new text.

---

## Subtask T001 — Characterization test + tidy-first extraction

**Purpose:** make the "activated directive ids → (`selected_directives`, snapshot nodes)" derivation a
pure function before you change it (Standing Order #2, tidy-first), so the later fix is a one-line,
unit-testable change.

**Steps:**
1. In `_synthesis.py`, find the block in `_build_synthesis_request` that sets `directives_for_synthesis`
   and builds `drg_nodes` (currently `for directive_id in directives_for_synthesis: drg_nodes.append({"urn": f"directive:{directive_id}", "kind": "directive"})`).
2. Extract a module-private pure helper, for example:
   ```python
   def _directive_synthesis_inputs(directive_ids: Sequence[str]) -> tuple[list[str], list[dict[str, str]]]:
       """Return (selected_directives, drg snapshot nodes) for the activated directive ids."""
   ```
   The caller assigns `selected_directives` and `nodes` from it. Keep the existing explanatory
   comments next to the helper. The two outputs must stay derived from the SAME list (that comment
   already exists and explains why).
3. Add focused unit tests for the helper in
   `tests/specify_cli/cli/commands/charter/test_resynthesis_after_activation_6510.py` (this WP's new
   test file): empty input gives `([], [])`; order is preserved; each node has exactly the keys `urn` and `kind`.
4. Commit this alone, e.g. `refactor(charter): extract directive synthesis-input derivation (#6510)`.
   Existing tests must pass unchanged. The extraction is behaviour-preserving.

**Validation:** `uv run pytest tests/charter/synthesizer tests/specify_cli/cli/commands/charter -q -k "synthes"` is green before and after.

---

## Subtask T002 — Red-first CLI acceptance tests

**Purpose:** pin the user-visible contract through the REAL entry points: the `charter synthesize`
and `charter resynthesize` typer commands, with NO patching of `_build_synthesis_request`. Existing
tests such as `tests/charter/synthesizer/test_synthesize_activation_append.py` patch the request
builder, which is exactly where the bug lives, so they cannot witness it.

**Fixture (build once, module-scoped if practical; keep it fast):**
- A `tmp_path` git repository (`git init`, an initial commit). Use the `charter_cwd_isolation` fixture
  pattern from `tests/charter/synthesizer/conftest.py` / `test_synthesize_activation_append.py` for the CWD and HOME isolation.
- Reach a real "synthesized once" state. Prefer driving the real commands (`charter interview
  --defaults`, `charter generate`, then authoring `.kittify/charter/generated/...` and `charter
  synthesize`) through `CliRunner` on `charter_app`. If `init` is too heavy, seed the minimum files
  those commands need and document why in the fixture docstring.
- Generated artifacts: the `generated` adapter reads `.kittify/charter/generated/{directives,tactics,styleguides}/`.
  The project directive file is `directives/001-project-intent-directive.directive.yaml` with
  `id: PROJECT_001` (copy the body of
  `tests/charter/fixtures/synthesizer/directive/project-intent-directive/26d34812f1be.directive.yaml`).
  Every other target the run names (e.g. `review-policy-tactic`, `testing-philosophy-tactic`,
  `quality-gates-style-guide`, `testing-style-guide`, and one `how-we-apply-<id>` tactic per activated
  built-in directive) needs a minimal valid YAML. A synthesize failure message names the missing file
  and its expected `id`. The scratch helper `fill.sh` next to the scratchpad repro shows the
  minimal shapes. Keep the activated list SMALL: write the explicit `activated_directives` list into
  `.kittify/charter/activation.yaml` yourself (e.g. `[001-project-intent-directive,
  003-decision-documentation-requirement]`) instead of running `charter activate`, which expands to
  ~39 directives. Also add one test that does go through `charter activate directive ...` if it
  stays under a few seconds; otherwise note why it is omitted.

**Tests (all must FAIL on the planning base for the stated reason, except the controls):**
1. `test_resynthesize_after_activation_succeeds` (FR-001, SC-001): the second `charter synthesize` exits 0; assert no `colliding_urn` in output.
2. `test_resynthesize_topic_project_directive_succeeds` (FR-002): `charter resynthesize --topic directive:PROJECT_001` exits 0.
3. `test_owned_directive_still_delivered` (FR-004, SC-002): after test 1's run, the rendered `charter context --action implement` (CLI or the context API the CLI uses) contains a distinctive phrase from the PROJECT_001 body. This is a ratchet and passes on base before step 4, but it must run on the SAME fixture right after a successful synthesis, so it cannot pass vacuously.
4. `test_activation_files_untouched` (FR-005, SC-004): the bytes of `.kittify/charter/activation.yaml` are identical before and after the synthesize/resynthesize runs.
5. `test_no_companion_tactic_for_own_directive` (spec US1 scenario 4): the synthesize run does not require `how-we-apply-project-001` (do not author it; the run must still exit 0).
6. `test_hand_authored_directive_kept_in_snapshot` (FR-008): an activated project-layer directive that synthesis does NOT own (no manifest/provenance record, and an id synthesis does not generate, e.g. `TEAM_001` with stem `050-team-directive`) still appears in the request's `selected_directives` and snapshot nodes, so its companion `how-we-apply-team-001` is still demanded. A unit-level assertion on `_build_synthesis_request(...)`'s returned request is acceptable here.
7. `test_ownership_read_only_when_list_explicit` (NFR-002 / D-3): with the activation key absent, a corrupt `synthesis-manifest.yaml` does not make the request build raise.

Commit the failing tests alone: `test(charter): red-first acceptance for re-synthesis after activation (#6510)`. Record the RED evidence (command + failing assertion lines) with `spec-kitty agent tasks add-history WP01 --note "..."`.

---

## Subtask T003 — Ownership reader `synthesized_urns`

**Purpose:** one public, strict read of "which URNs of a kind did synthesis create", from the existing
record (C-001). The layer rule puts config/record reads in `charter`; `specify_cli` orchestrates.

**Steps:**
1. In `src/charter/activation/synthesizer/manifest.py` add:
   ```python
   def synthesized_urns(repo_root: Path, kind: str) -> frozenset[str]:
       """URNs of the *kind* artifacts synthesis created, from the manifest and provenance sidecars.

       Absent manifest: empty set (nothing synthesized). Unreadable or invalid manifest, or a
       missing/unreadable/URN-less sidecar for an entry of *kind*: raise (fail closed, never empty).
       """
   ```
   - Manifest path: `repo_root / MANIFEST_PATH`. Load with the module's `load_yaml`.
   - For each `entry` with `entry.kind == kind`, load `repo_root / entry.provenance_path` with
     `charter.activation.synthesizer.provenance.load_yaml` (no import cycle: `provenance` does not
     import `manifest`; import it lazily inside the function if mypy or import order complains) and
     collect `artifact_urn`.
   - Raise a clear exception type. Reuse `ManifestIntegrityError` from `.errors` if its semantics fit
     (read it first). Otherwise use the closest existing `SynthesisError` subclass. Do not invent a new
     error hierarchy. The message names the path that could not be read.
   - Add `"synthesized_urns"` to `__all__` (charter `__all__` convention; the dead-symbol gate needs
     the `src/` caller that T004 adds).
2. Unit tests in `tests/charter/synthesizer/test_manifest.py`: absent manifest gives `frozenset()`; two
   directives and one tactic give only the directive URNs for `kind="directive"`; a corrupt manifest
   raises; a missing sidecar raises; a sidecar without `artifact_urn` raises. Build real files under
   `tmp_path` with the module's own dump helpers where possible.
3. Note in the docstring that the lenient display reader `_synthesis._extract_artifact_id_from_provenance`
   (never raises, used for the JSON envelope) is a different contract and stays as it is.

---

## Subtask T004 — Exclude synthesis-owned directives at the request seam

**Steps:**
1. Extend the T001 helper with an `owned` parameter:
   `_directive_synthesis_inputs(directive_ids, owned_ids: frozenset[str] = frozenset())`. It drops
   every id in `owned_ids` from BOTH outputs and keeps order.
2. In `_build_synthesis_request`, only when `directives_for_synthesis` is non-empty (D-3), compute
   `owned_ids = {urn.split(":", 1)[1] for urn in synthesized_urns(repo_root, "directive")}` and pass
   it in. When the list is empty, do not read the manifest at all (test 7).
3. Update the nearby comment block. Explain in two or three sentences that synthesis-owned directives
   are synthesis output, not input (#6510/#4226), and stay activated for delivery.
4. Verify `resynthesize` goes through the same builder (`resynthesize.py:129` calls
   `_charter_pkg._build_synthesis_request`). The `resynthesize_pipeline` may also read
   `request.drg_snapshot` (`resynthesize_pipeline.py:501-540`, falling back to the snapshot when no
   project graph exists). Confirm test 2 is green, and if the pipeline reads the persisted project
   graph instead, write down in the WP history why that path does not collide.
5. Run T002's tests: all GREEN. Commit: `fix(charter): leave synthesis-owned directives out of synthesis input (#6510, #4226)`.

**Edge cases to check explicitly:** the activation key is absent (unchanged, empty); the project
directive was deactivated (not in the list, nothing to exclude); several owned directives
(`PROJECT_001`, `PROJECT_002`); an owned directive that is no longer a target (excluded anyway,
reconcile/prune untouched).

---

## Subtask T005 — Blast radius, quality gates, live check

Run and record the commands and pass/fail counts in the WP history:
```bash
uv run pytest tests/charter/synthesizer -q
uv run pytest tests/charter -q -x --ignore=tests/charter/synthesizer   # owning subsystem
uv run pytest tests/charter_offering -q
uv run pytest tests/specify_cli/cli/commands/charter -q
uv run pytest tests/architectural/test_no_dead_symbols.py tests/architectural/test_layer_rules.py -q
make test-fast
uv run --frozen ruff check <touched files>
uv run --frozen ruff format --check --force-exclude <touched files>
uv run --frozen mypy <touched src files>
uv run --frozen ruff check --select C901 <touched src files>
```
Do NOT run `make test-full` or the whole `tests/architectural/` directory. Then repeat the quickstart
(`kitty-specs/.../quickstart.md`) in a fresh scratch directory (never inside the repository) and record
exit codes. For any red you did not cause, classify it with CLAUDE.md's baseline-red gotcha. Each
`tests/charter*` red must be shown red on the planning base too before you call it pre-existing.

## Definition of Done

- T001's refactor commit, T002's red test commit and T004's fix commit are separate, in that order.
- All seven acceptance tests are green; the T003 unit tests are green.
- No change to `reach_only.py`, `reconcile.py`, `project_drg.py` or activation-writing code.
- Gates in T005 are clean and recorded.
- `spec-kitty agent tasks mark-status T001 T002 T003 T004 T005 --status done --mission resynthesis-after-activation-01M5ZD62`.

## Risks

- Fixture weight: a real synthesis needs every target authored. Keep the activated list to two
  directives and reuse one module-scoped synthesized repository (copy it per test) if runtime grows.
- `targets.py` checks companion-tactic source URNs against the snapshot. Removing a node without
  removing its `selected_directives` entry would raise a different refusal. The single helper prevents
  that; test it.

## Reviewer guidance

- Verify RED→GREEN: check out the T002 commit and confirm tests 1, 2 and 5 fail with
  `colliding_urn='directive:PROJECT_001'` or the missing companion tactic, then confirm green at the
  WP tip.
- Confirm ownership is read only from the manifest/provenance (no `PROJECT_` prefix heuristic, no new record).
- Confirm activation bytes are untouched and that no test patches `_build_synthesis_request` for the acceptance cases.

## Implementation command

```bash
spec-kitty agent action implement WP01 --agent claude --mission resynthesis-after-activation-01M5ZD62
```
