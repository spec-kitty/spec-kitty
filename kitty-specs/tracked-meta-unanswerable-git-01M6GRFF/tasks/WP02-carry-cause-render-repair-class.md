---
work_package_id: WP02
title: Carry the cause, render the repair class
dependencies:
- WP01
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-006
- FR-007
- NFR-001
- NFR-002
- NFR-003
- NFR-004
- C-001
- C-002
- C-003
- C-004
- SC-001
- SC-002
- SC-003
- SC-004
planning_base_branch: issue-7131-tracked-meta-unanswerable-git
merge_target_branch: issue-7131-tracked-meta-unanswerable-git
branch_strategy: Planning artifacts for this mission were generated on issue-7131-tracked-meta-unanswerable-git. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-7131-tracked-meta-unanswerable-git unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-tracked-meta-unanswerable-git-01M6GRFF
base_commit: 0ea008dbeeb9d490a1ed89526fd625e82293df95
created_at: '2026-11-03T13:29:01.735563+00:00'
subtasks:
- T005
- T006
- T007
- T008
phase: Phase 2 - User Story 1 and 2
history:
- at: '2026-11-03T13:15:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/upgrade/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/mission_metadata.py
- src/specify_cli/upgrade/tracked_meta_notice.py
- tests/specify_cli/upgrade/test_read_tracked_meta_6673.py
- docs/changelog/unreleased/*.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Carry the cause, render the repair class

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `pi`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`,````bash`

---

## Objectives & Success Criteria

- `read_tracked_meta` carries *why* git could not answer, as data on `TrackedMeta`.
- The one shared notice renders the matching repair class, and for these causes never offers
  `git checkout -- <path>` (a command that fails for the same reason classification did).
- Nothing about the refusal changes: `refuse is True`, code `TRACKED_META_UNAVAILABLE`, no identity,
  seed or metadata write, and the healthy restore-or-rebuild path is untouched.

Success criteria (SC-001..SC-004): three cause tests assert refusal-preserved plus no `git checkout --`
in the notice; the existing healthy-path and cutover tests pass unmodified; no stderr text appears in
any notice; the touched files pass ruff/format/mypy.

## Context & Constraints

- Read `kitty-specs/tracked-meta-unanswerable-git-01M6GRFF/spec.md` (US1, US2, FR-001..FR-007),
  `plan.md` (IC-01, IC-03), and the two modules you own.
- **The refusal is the safety net** (#6673). This mission changes diagnosis only (C-001). If a change
  would let a seam write a `meta.json` on one of these paths, stop: that is out of scope and wrong.
- **One notice authority** (C-002): the text lives in `tracked_meta_notice`. Its four consumers
  (`runtime_state_cutover`, `normalize_mission_lifecycle`, `backfill_identity`,
  `m_2_0_6_residue_safe_consistency_sweep`) must not grow wording of their own.
- **Red-first** (charter, ATDD-First Discipline / DIRECTIVE_034): write the failing tests through the
  pre-existing entry points before the production change, and record the failure output.
- **No stderr echo** (NFR-001): the notice prints a curated cause phrase and the project-relative
  path only. Never git's raw stderr, never a URL or a credential.
- **Ownership trust is not ours to grant** (C-003): name the trust decision, scope it to one checkout
  (`safe.directory` for that path), never a wildcard, and never a config write.

## Branch Strategy

- **Strategy**: coordination-branch mission; execution worktrees are allocated per computed lane from
  `lanes.json` by `spec-kitty agent action implement WP02 --agent pi --mission tracked-meta-unanswerable-git-01M6GRFF`.
- **Planning base branch**: `main`
- **Merge target branch**: `main`

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

## Subtasks & Detailed Guidance

### Subtask T005 – Red-first coverage for the three unreadable causes

- **Purpose**: witness the defect before fixing it, on the same fixtures the module already uses.
- **Steps** (in `tests/specify_cli/upgrade/test_read_tracked_meta_6673.py`):
  1. **Strengthen** `test_a_git_that_refuses_to_answer_is_not_read_as_nothing_tracked` (its fixture
     already replaces `.git` with an unresolvable pointer): assert the result carries the
     repository cause, and that `classify_missing_tracked_meta(...)` returns `refuse is True`, ends
     with `[TRACKED_META_UNAVAILABLE]`, does **not** contain `git checkout --`, and does not claim the
     file "is missing from the working tree".
  2. **Add** an ownership test: build a real repo, delete the working-tree `meta.json`, and patch the
     git seam so the prefix probe answers returncode 128 with git's real refusal line
     `fatal: detected dubious ownership in repository at '<somewhere>'` plus a distinctive marker token
     in the same stderr. Assert the ownership cause, that the notice names ownership and an explicit
     operator trust decision scoped to this checkout, that it contains no `git checkout --`, no
     `safe.directory *`, and that the distinctive stderr token is absent from the notice (NFR-001).
  3. **Add** a committed-blob test: commit `meta.json`, delete the working-tree copy, make the
     committed object unreadable (corrupt one loose object under `.git/objects/`), and assert the
     committed-content cause and a `git fsck` repair class with no `git checkout --`.
  4. Run the module and record the three failures (one strengthened, two new) as the red proof.
- **Files**: `tests/specify_cli/upgrade/test_read_tracked_meta_6673.py`
- **Validation**: `uv run --frozen pytest -q -p no:randomly tests/specify_cli/upgrade/test_read_tracked_meta_6673.py`
  fails only on the new assertions.

### Subtask T006 – `TrackedMeta.unreadable_reason`

- **Purpose**: the classifier already knows the cause; stop throwing it away.
- **Steps** (in `src/specify_cli/mission_metadata.py`):
  1. Declare a small module-level literal type, e.g.
     `UnreadableReason = Literal["repository", "ownership", "objects"]`.
  2. Add `unreadable_reason: UnreadableReason | None = None` as the last field of `TrackedMeta`, and
     extend its docstring: set **only** together with `unavailable=True`, and it shapes only the
     operator message (like the three flags beside it).
  3. Give `_GitRefuses` a `stderr` attribute (it already receives the text; keep `str(exc)` behaviour).
  4. Add one classifier helper, e.g.
     `def _unreadable_reason(stderr: str, *, repository_identified: bool) -> UnreadableReason:` —
     ownership first (shared `refuses_ownership` from `kernel.git`), otherwise `"objects"` when the
     repository was identified, else `"repository"`.
  5. Set it at the two branches: the `except _GitRefuses` return (`repository_identified=False`) and
     the non-timeout `GitCommandError` from `_committed_meta_bytes` (`repository_identified=True`).
     A timeout still re-raises; `not_run` still means "nothing is tracked here".
- **Files**: `src/specify_cli/mission_metadata.py`
- **Validation**: `uv run --frozen mypy src/specify_cli/mission_metadata.py`

### Subtask T007 – Render one repair-class tail per cause

- **Purpose**: the operator gets the actual repair class, and no dead remedy.
- **Steps** (in `src/specify_cli/upgrade/tracked_meta_notice.py`):
  1. Add a per-cause tail map as a module constant (`dict[UnreadableReason, str]`) — the text is data,
     not a nested conditional (keeps the function inside the complexity ceiling, NFR-004). Each tail
     must: name the cause, say that *whether the path is tracked is unknown*, say no identity was
     minted, name the repair class, and state that a file restore cannot succeed until git answers.
     - `repository`: unreadable/garbled `.git` marker, or `GIT_DIR`/`GIT_WORK_TREE` naming elsewhere;
       repair the repository layout or environment; `git status` in the checkout reports the cause.
     - `ownership`: the checkout belongs to another user; trusting the repository is an explicit
       operator decision scoped to this checkout only (`safe.directory` names that one path, never a
       wildcard); no file restore can succeed until git answers.
     - `objects`: damaged or incomplete object store; `git fsck` names the damage.
  2. Branch on `tracked.unreadable_reason` **first** in `_refusal_notice`, using the subject
     `meta.json` (not `tracked meta.json`) — git never established that the path is tracked — and keep
     the caller's lead sentence ("is missing from the working tree" / "has lost its mission_id").
  3. Leave every other branch byte-identical: `staged_differs`, `index_only`, `corrupt`, the generic
     fallback, `_restore_notice`, `refuse`, and the codes.
  4. Green the suite from T005; confirm `tracked_meta_refusal`'s lead reads correctly in front of each
     tail (it is the present-file case).
- **Files**: `src/specify_cli/upgrade/tracked_meta_notice.py`
- **Validation**: the T005 suite passes; `uv run --frozen mypy src/specify_cli/upgrade/tracked_meta_notice.py`

### Subtask T008 – Verification sweep, changelog fragment, tracer

- **Purpose**: evidence for the PR and the record for the next mission.
- **Steps**:
  1. Run, and record exact commands and counts:
     - `tests/specify_cli/upgrade/test_read_tracked_meta_6673.py`
     - `tests/specify_cli/migration/test_runtime_state_cutover_placement.py`
     - `tests/specify_cli/migration/test_backfill_identity_tracked_absent_6673.py`
     - `tests/integration/migration/test_upgrade_tracked_meta_identity_6673.py`
     - `tests/git_ops/test_git_preflight.py` (WP01's suite, as regression evidence)
     - `uv run --frozen ruff check` + `ruff format --check --force-exclude` + `mypy` on the touched files
     - `uv run --frozen python -m scripts.docs.check_changelog_style`
  2. Add the **per-PR changelog fragment** `docs/changelog/unreleased/<pr>.fixed.md` (the PR number once
     it exists; `7131.fixed.md` before that) in the shape `docs/changelog/unreleased/README.md`
     requires: a bold impact-first lead with the `(#7131)` reference, `**Before:**` / `**After:**`, and
     under 1,200 characters. Never edit `docs/changelog/CHANGELOG.md`.
  3. Append to the tracer files: the design decision (cause as data, not stderr re-parsing) and any
     tooling friction met.
- **Files**: `docs/changelog/unreleased/<pr>.fixed.md`
- **Validation**: `check_changelog_style` and `check_spelling --pass unreleased` clean.

## Definition of Done

- [ ] The three causes each have a test asserting refusal-preserved (flag, code, nothing written).
- [ ] No notice for these causes contains `git checkout --` or raw stderr.
- [ ] The ownership notice names an explicit operator decision scoped to one checkout; no wildcard.
- [ ] Healthy paths (usable tracked copy, pre-identity Mission, inside a real repo) behave as before.
- [ ] `TrackedMeta`'s existing fields and the notice's other branches are untouched.
- [ ] ruff/format/mypy clean; changelog fragment present; tracer updated.

## Risks & Mitigations

- **Corrupting a loose object** may be git-version sensitive: if `git cat-file` still succeeds, remove
  the object file instead so the read genuinely fails; if neither is stable, patch the git seam for
  that test and say why in its docstring. Do not weaken the assertion.
- **Wording length**: the notice is one operator-facing line. Keep each tail under ~220 characters and
  the whole notice under ~700; if it grows past that, cut clauses rather than the repair class.
- **Second wording authority**: if a consumer seems to need a different sentence, stop and report it —
  the fix belongs in the shared notice.

## Reviewer Guidance

- Check that the refusal surface is unchanged: `grep -n "refuse=\|CODE_" src/specify_cli/upgrade/tracked_meta_notice.py`.
- Check the diff for a write path on any of these branches (`write_meta`, `restore_tracked_meta`, config
  mutation): there must be none.
- Check the ownership notice does not read as an instruction to run a global `safe.directory` add.
- Re-run the red-first tests against `origin/main` to confirm they fail there.
