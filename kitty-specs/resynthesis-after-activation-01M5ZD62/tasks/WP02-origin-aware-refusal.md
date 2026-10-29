---
work_package_id: WP02
title: Origin-aware collision refusal
dependencies:
- WP01
requirement_refs:
- FR-006
- FR-007
- NFR-003
- C-003
- C-004
- C-005
- SC-003
planning_base_branch: issue-6510-resynthesis-after-activation
merge_target_branch: issue-6510-resynthesis-after-activation
branch_strategy: Planning artifacts for this mission were generated on issue-6510-resynthesis-after-activation. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6510-resynthesis-after-activation unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-resynthesis-after-activation-01M5ZD62
base_commit: a64d2762db10233caa46347775fbbaa21b11f9ac
created_at: '2026-10-27T21:03:30.454124+00:00'
subtasks:
- T006
- T007
- T008
- T009
- T010
phase: Phase 2 - Refusal quality
history:
- at: '2026-10-27T19:45:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/charter/
create_intent:
- src/specify_cli/cli/commands/charter/_collision_remedy.py
- tests/specify_cli/cli/commands/charter/test_collision_refusal_6510.py
execution_mode: code_change
model: ''
owned_files:
- src/charter/activation/synthesizer/errors.py
- src/charter/activation/synthesizer/project_drg.py
- src/specify_cli/cli/commands/charter/_collision_remedy.py
- src/specify_cli/cli/commands/charter/synthesize.py
- src/specify_cli/cli/commands/charter/resynthesize.py
- tests/charter/synthesizer/test_project_drg.py
- tests/specify_cli/cli/commands/charter/test_collision_refusal_6510.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Origin-aware collision refusal

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

- **Has review feedback?** Check the `review_ref` field in the event log (`spec-kitty agent tasks status --mission resynthesis-after-activation-01M5ZD62`).
- Address every feedback item before declaring the work complete, and record each with `spec-kitty agent tasks add-history WP02 --note "..."`.

---

## Objective

After WP01, synthesis no longer collides with its own directives. A collision that remains is a real
clash, and today's text misleads: "URN 'directive:PROJECT_001' already exists in the built-in DRG
layer. Synthesized artifacts must carry new URNs disjoint from built-in nodes." That node is often not
built-in at all, and #4226 shows operators renaming the tool's own identifiers because of it. Make
the refusal:

1. carry a structured `colliding_urn` on `ProjectDRGValidationError` (additive, default `None`);
2. use origin-neutral core wording ("already present in the synthesis input graph") instead of "built-in";
3. at the CLI, name the origin and the recovery:
   - **unowned project directive**: activated, its stem resolves from the project pack root
     (`.kittify/charter-packs/directive/`), and it is not in `synthesized_urns(repo_root, "directive")`.
     Remedy: "If synthesis created it, restore `.kittify/charter/synthesis-manifest.yaml` and its
     provenance sidecar from version control and re-run. If you authored it by hand, give it an id
     synthesis does not generate. Do not deactivate it to get past this refusal; that stops agents
     receiving it."
   - **upstream (built-in or org) node**: say so, and say synthesis never overwrites built-in or org doctrine.

The additive-only CHECK is unchanged (FR-006, C-003). Requirements: FR-006, FR-007, SC-003.

## Context

- Spec, plan, research (D-4), data model under `kitty-specs/resynthesis-after-activation-01M5ZD62/`.
- WP01 adds `charter.activation.synthesizer.manifest.synthesized_urns(repo_root, kind)`; use it for classification.
- Raise sites: `src/charter/activation/synthesizer/project_drg.py` `emit_project_layer` (~line 334,
  the target collision) and `_append_project_profile_nodes` (~line 184, the agent_profile collision).
  Give BOTH the structured field. Reword only the target-collision text to be origin-neutral; the
  profile site's text is about a hand-authored profile and may keep its meaning (drop "built-in"
  only if it is inaccurate there too; read the snapshot construction first).
- CLI handlers: `synthesize.py` `except SynthesisError` (~line 626) and `resynthesize.py` `except SynthesisError` (~line 260).
- `rg "built-in DRG layer" tests/` finds no test that asserts the old wording (checked 2026-10-27). Re-check on your base.

## Branch Strategy

- Planning base branch: `issue-6510-resynthesis-after-activation`; final merge target: the same branch.
- Workspace: the lane worktree that `spec-kitty agent action implement WP02 --agent claude --mission resynthesis-after-activation-01M5ZD62` prints (lanes.json). WP02 depends on WP01 and cannot be claimed until WP01 is approved.

## Constraints

- Do not loosen or bypass the additive-only check (C-003). Only wording and an additive field change in `charter`.
- Do not edit `_synthesis.py` (WP01 owns it). The remedy helper lives in the NEW module `_collision_remedy.py`.
- Do not edit `reach_only.py` / `reconcile.py` (C-004).
- The `synthesize` command function is long. Keep every touched function at complexity ≤ 15 by putting the logic in the helper (`ruff check --select C901`).
- No new `noqa` / `type: ignore`. "Mission", never "feature".

---

## Subtask T006 — Red-first tests

1. `tests/charter/synthesizer/test_project_drg.py`: a target whose URN is in `built_in_drg` raises
   `ProjectDRGValidationError` with `e.colliding_urn == "directive:PROJECT_00X"`, and `str(e)` no
   longer contains "built-in DRG layer" for the target collision. Keep (or add) an assertion that the
   refusal still happens (FR-006 ratchet).
2. `tests/specify_cli/cli/commands/charter/test_collision_refusal_6510.py`:
   - Unit-test the classifier directly: given a `tmp_path` project with an activated, unowned
     project-layer directive `PROJECT_001` (file in `.kittify/charter-packs/directive/`, no manifest),
     `collision_remedy(repo_root, err)` returns text naming `PROJECT_001`, saying synthesis did not
     create it, naming `.kittify/charter/synthesis-manifest.yaml`, and NOT containing "new URNs".
   - Given a colliding URN that is not a project-layer directive, the text says built-in or org.
   - Given an error with `colliding_urn=None`, it returns `None`.
   - One CLI-level case: `charter synthesize --json` on such a project exits 1, and the JSON
     `warnings` contain the remedy line. The human-mode output contains it as well. Reuse WP01's
     fixture approach (real files, no patching of the request builder). If you import a helper from
     WP01's test module, move the shared fixture into the nearest `conftest.py` only if you own it;
     otherwise duplicate the small seed function.
3. Commit the failing tests alone: `test(charter): red-first origin-aware collision refusal (#6510)`.

## Subtask T007 — Structured field + neutral wording

1. `errors.py`: add `colliding_urn: str | None = None` to the frozen `ProjectDRGValidationError` dataclass (after the existing fields, so existing constructors keep working). Keep `__str__` unchanged in shape.
2. `project_drg.py`: pass `colliding_urn=urn` at both raise sites. Target collision text:
   `"Additive-only violation (FR-020 / EC-6): URN '{urn}' is already present in the synthesis input graph. Synthesis never overwrites an artifact it did not create."`
   Keep `merged_graph_summary` (other tooling may read `colliding_urn=` from it); rename
   `built_in_nodes=` only if no test or caller parses it (`rg "built_in_nodes=" src tests`).
3. Run `tests/charter/synthesizer/test_project_drg.py` and confirm it is green.

## Subtask T008 — Remedy helper module

Create `src/specify_cli/cli/commands/charter/_collision_remedy.py` with `__all__` and one public function:
```python
def collision_remedy(repo_root: Path, error: SynthesisError) -> str | None:
    """Operator remedy for a synthesis URN collision, naming the colliding node's origin (FR-007)."""
```
- Returns `None` unless `error` is a `ProjectDRGValidationError` with a `colliding_urn`.
- Classify a `directive:<id>` URN: it is a project-layer directive when a file under
  `project_pack_root(repo_root) / "directive"` (`kernel.charter_pack_paths`) declares `id: <id>`.
  Look for an existing reader first: `project_drg._registered_project_artifacts`, the
  `charter.offering` project-layer resolvers, `resolve_artifact_urn` with `layer_roots`. Reuse one
  instead of hand-parsing YAML if it fits. It is unowned when its URN is not in
  `synthesized_urns(repo_root, "directive")`. If that read raises, say the ownership record is
  unreadable and point at the manifest; never guess.
- Anything else gives the upstream (built-in or org) text.
- Keep it pure apart from these file reads. No console I/O here.

## Subtask T009 — Wire into both commands

- `synthesize.py` `except SynthesisError` branch: compute `remedy = collision_remedy(repo_root, e)`
  once. Human mode prints it as `[yellow]Hint:[/yellow] ...` after the error panel. In JSON mode,
  append it to `warnings`. Do not disturb the `GeneratedArtifactMissingError` branch.
- `resynthesize.py` `except SynthesisError` branch: the same behaviour. Its JSON goes through
  `_emit_error(console, json_output=True, message=str(e))`; append the remedy to the message (or a
  field the existing envelope supports — read `_emit_error` first).
- `repo_root` must be in scope in both handlers. Check that it is defined before the `try`.

## Subtask T010 — Blast radius and gates

```bash
uv run pytest tests/charter/synthesizer -q
uv run pytest tests/charter -q --ignore=tests/charter/synthesizer
uv run pytest tests/charter_offering -q
uv run pytest tests/specify_cli/cli/commands/charter -q
uv run pytest tests/architectural/test_no_dead_symbols.py tests/architectural/test_layer_rules.py tests/architectural/test_no_legacy_terminology.py -q
make test-fast
uv run --frozen ruff check <touched files>; uv run --frozen ruff format --check --force-exclude <touched files>
uv run --frozen mypy <touched src files>; uv run --frozen ruff check --select C901 <touched src files>
```
Record the commands and counts with `add-history`. No full heavy suites.

## Definition of Done

- The red test commit precedes the implementation commit(s); all new tests are green at the tip.
- Both raise sites carry `colliding_urn`; the target-collision text no longer says "built-in" or "must carry new URNs".
- Both commands print the remedy in human and JSON mode; exit codes are unchanged (1).
- Gates clean; `spec-kitty agent tasks mark-status T006 T007 T008 T009 T010 --status done --mission resynthesis-after-activation-01M5ZD62`.

## Reviewer guidance

- Confirm the additive-only condition (`if urn in built_in_node_urns`) is byte-identical apart from the raise arguments.
- Confirm the remedy never advises deactivation or renaming a synthesis-owned id.
- Check complexity of `synthesize`'s command function before and after.

## Implementation command

```bash
spec-kitty agent action implement WP02 --agent claude --mission resynthesis-after-activation-01M5ZD62
```
