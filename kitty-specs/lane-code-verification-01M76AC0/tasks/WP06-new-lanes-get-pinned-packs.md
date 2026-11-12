---
work_package_id: "WP06"
subtasks:
  - "T021"
  - "T022"
  - "T023"
title: "New lanes get the pinned packs trees"
task_type: "implement"
phase: "Phase 2 - Surfaces"
execution_mode: "code_change"
owned_files:
  - "src/specify_cli/lanes/lane_packs.py"
  - "src/specify_cli/lanes/lane_checkout.py"
  - "tests/lanes/test_lane_packs.py"
  - "tests/agent/test_implement_lane_packs.py"
authoritative_surface: "src/specify_cli/lanes/lane_packs.py"
create_intent:
  - "src/specify_cli/lanes/lane_packs.py"
  - "tests/lanes/test_lane_packs.py"
  - "tests/agent/test_implement_lane_packs.py"
dependencies: []
agent_profile: "python-pedro"
role: "implementer"
agent: "claude"
model: ""
assignee: ""
shell_pid: ""
history:
  - at: "2026-11-12T06:00:00Z"
    actor: "system"
    action: "Prompt generated via /spec-kitty.tasks (fold of #7577, decision 01M774QJP2HZ0A2A8KQ05MQCRS)"
---

# Work Package Prompt: WP06 – New lanes get the pinned packs trees

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

Then load `spec-kitty charter context --action implement` and read `CLAUDE.md` (sections "Template Source Location" and "Pack Tiers") and `.kittify/charter/charter.md`.

---

## ⚠️ IMPORTANT: Review Feedback

- Check `review_ref` via `spec-kitty agent tasks status --mission lane-code-verification-01M76AC0`.
- Record progress with `spec-kitty agent tasks add-history WP06 --mission lane-code-verification-01M76AC0 --note "..."`.

## Review Feedback

*[Filled from the status event log when this WP returns from review.]*

---

## Objectives & Success Criteria

Fixes #7577 (operator ruling, decision `01M774QJP2HZ0A2A8KQ05MQCRS`): this repository pins
`packs/built-in` and `packs/internal` (`packs/<name>.source.yaml`) and does not commit the
trees, so a fresh lane worktree has none and the lane's own CLI and pack tests fail with
`BuiltInPackMissing`.

When a lane checkout is created and it carries a pin file for a pack whose tree is absent
in the lane, place the **pinned, digest-verified** tree into the lane using the **same
functions `make sync-packs` uses** (`scripts/sync_packs.py::_sync_one`:
`fetch_to_cache(pin, offline=True)` then `place_pack(cached, dest, pin)`), offline only.
On a cold cache (or any `PackSyncError`), leave the lane without the tree and print one
remedy line (`packs/<name> not placed in the lane (<reason>); run \`make sync-packs\` in
<lane>`); never fail `implement`. A repository without pin files (every consumer project)
is untouched: no output, no work.

Requirements: FR-012, SC-006, C-001 (no pack content edited; the tree comes from the
verified cache, never copied from another checkout).

## Context & Constraints

- Lane creation has exactly one seam: `src/specify_cli/lanes/lane_checkout.py::open_lane_checkout`
  ("every lane `git worktree add` goes through here"; an architectural gate fails on any lane
  `git worktree add` outside it). Add the call there, after the worktree exists and after
  the status-file sparse exclusion, best-effort (wrap: an unexpected exception is reported
  as the remedy line, never raised). Read the module fully first; keep the existing tests in
  `tests/lanes/` and `tests/specify_cli/lanes/` for it green.
- Import the pack functions lazily through the `charter.packs` facade (`load_pack_pin`,
  `fetch_to_cache`, `place_pack`, `PackSyncError`; check its `__all__`). That keeps the
  `specify_cli → charter` direction and the facade seam. Use the pin file name from
  `kernel.pack_tiers.pin_filename` (or the facade), not a hand-written literal, if one exists.
- Packs are listed as `built-in` and `internal` in `scripts/sync_packs.py::PACK_NAMES`; do not
  import from `scripts/`. Derive the pack set from the pin files present in the lane
  (`packs/*.source.yaml`) so a consumer-like repo with no pins is a no-op.
- Placed trees are gitignored (`/packs/built-in/`, `/packs/internal/` in `.gitignore`), so the
  lane stays clean and the dirty-tree guards stay quiet; assert that in a test.
- Where the remedy line is printed: `open_lane_checkout` has no console. Return a small result
  from `place_pinned_packs` and surface the remedy through the same channel the lane
  allocation already uses for warnings (find it in `worktree_allocator.py` / the implement
  output); if there is none reachable without touching WP02's `implement.py`, write the line
  to stderr with `print(..., file=sys.stderr)` inside `lane_packs.py`. Do not edit
  `cli/commands/implement.py` (WP02 owns it).
- `make test-fast` does not sync packs; that is unchanged.

## Branch Strategy

- **Planning base branch**: `fix/7547-lane-code-verification` · **Merge target branch**: `fix/7547-lane-code-verification`

```bash
spec-kitty agent action implement WP06 --agent claude --mission lane-code-verification-01M76AC0
```

## Subtasks & Detailed Guidance

### Subtask T021 – Red tests through `spec-kitty implement` (commit first)

- **Unit file** `tests/lanes/test_lane_packs.py`: build a tiny pinned pack the way
  `tests/charter_offering/test_pack_fetch.py` does (reuse its fixtures/helpers: a fake
  open-packs tree, its digest, and a pin file; point the cache with `XDG_CACHE_HOME` at
  `tmp_path`). Cases:
  1. warm cache → `place_pinned_packs(lane)` places `lane/packs/built-in`, and
     `check_pack(pin, dest)` is `OK` (positive control).
  2. cold cache (empty `XDG_CACHE_HOME`) on the same fixture → no tree, result carries the
     remedy, no exception, no network (assert `offline=True` reached `fetch_to_cache`, or
     block the network by monkeypatching its fetcher to raise).
  3. tree already present → untouched (no re-place; mtime unchanged).
  4. no pin files (consumer-like repo) → no-op, empty result, no output.
  5. placed tree is ignored by git (`git status --porcelain` empty in the lane).
- **CLI file** `tests/agent/test_implement_lane_packs.py`: drive `spec-kitty implement` on a
  fixture project that carries a pin file + warm cache (reuse the harness in
  `tests/specify_cli/cli/commands/test_implement_characterization.py` ~L255, importing its
  fixtures or a minimal local copy) → the new lane contains the verified tree; cold cache →
  implement still exits 0 and prints the remedy line naming the lane.
- Commit these red before T022/T023.

### Subtask T022 – `src/specify_cli/lanes/lane_packs.py`

- `@dataclass(frozen=True) class LanePacksResult`: `placed: tuple[str, ...]`,
  `skipped: tuple[tuple[str, str], ...]` (name, reason). `remedy_lines()` returns the lines.
- `def place_pinned_packs(lane: Path) -> LanePacksResult`: for each `lane/packs/<name>.source.yaml`
  whose `lane/packs/<name>/` is absent: `pin = load_pack_pin(pin_path)`;
  `cached = fetch_to_cache(pin, offline=True)`; `place_pack(cached, lane/"packs"/name, pin)`.
  Catch the facade's `PackSyncError` / `PackPinError` (and `OSError`) per pack → skipped with a
  bounded reason. `__all__ = ["LanePacksResult", "place_pinned_packs"]`.
- Keep it a leaf (no `specify_cli.review|status|cli` imports).

### Subtask T023 – Wire into `open_lane_checkout`

- After the worktree is added and its exclusions applied, call `place_pinned_packs(path)` in a
  `try/except Exception` that degrades to a single remedy line; emit remedy lines as decided
  above. No change to `LaneCheckoutRequest` or the function's return type unless unavoidable
  (callers: grep `open_lane_checkout(`).
- Record the friction you hit (e.g. how warnings surface) with `spec-kitty agent tracer-append`.

## Test Strategy

```bash
.venv/bin/python -m pytest tests/lanes/test_lane_packs.py tests/agent/test_implement_lane_packs.py -q
.venv/bin/python -m pytest tests/lanes tests/charter_offering/test_pack_fetch.py -q
.venv/bin/python -m pytest tests/specify_cli/lanes -q          # out-of-matrix: run and record
.venv/bin/python -m pytest tests/architectural/test_no_dead_symbols.py tests/architectural/test_charter_facades_reexport_offering.py tests/cross_cutting/packaging/test_packaging_safety.py -q
.venv/bin/python -m pytest tests/architectural -q -k "worktree_add or lane_checkout"   # the lane-checkout single-seam gate
ruff check / ruff format --check --force-exclude / mypy on changed files
```

(Run from the lane with its own `.venv`, created by `make sync-packs` in the lane — which,
until this WP lands, is also how the lane gets its packs.)

## Risks & Mitigations

- Network: never fetch from `open_lane_checkout`; offline only (ruling).
- Large trees: `place_pack` copies; measure time on a real lane of this repo and record it in
  the handoff note (expect ~seconds).
- Do not regress `packs/` packaging guards: no file under `packs/` is added to git.

## Review Guidance

- Warm/cold cases share one fixture; the cold case proves no tree and the remedy.
- The placed tree verifies against the pin (`check_pack` OK); no pack content edited.
- Consumer repo (no pins) is a silent no-op.

## Activity Log

- 2026-11-12T06:00:00Z – system – Prompt generated (fold of #7577)
