---
work_package_id: WP10
title: Extract the shared kernel and the claim types
dependencies:
- WP07
- WP08
- WP09
requirement_refs:
- FR-019
- C-005
- C-006
- NFR-001
planning_base_branch: feat/consolidation-window-provenance
merge_target_branch: feat/consolidation-window-provenance
branch_strategy: Planning artifacts for this mission were generated on feat/consolidation-window-provenance. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into feat/consolidation-window-provenance unless the human explicitly redirects the landing branch.
subtasks:
- T054
- T055
- T056
- T057
- T058
phase: Phase 3 - Behaviour-preserving split
history:
- at: '2026-11-08T19:52:39Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/consolidation/
create_intent:
- tests/consolidation/reconciliation_family.py
- src/specify_cli/consolidation/reconciliation_kernel.py
- src/specify_cli/consolidation/reconciliation_claim_types.py
- tests/consolidation/test_reconciliation_module_imports.py
execution_mode: code_change
model: glm-5.3
owned_files:
- src/specify_cli/consolidation/reconciliation.py
- src/specify_cli/consolidation/reconciliation_kernel.py
- src/specify_cli/consolidation/reconciliation_claim_types.py
- tests/consolidation/reconciliation_family.py
- tests/consolidation/test_reconciliation_module_imports.py
- tests/terminus/test_resume_refuses_committed_staged_deletions.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP10 – Extract the shared kernel and the claim types

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `opencode`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status --mission consolidation-window-provenance-01M6Y84D`).
- **You must address all feedback** before your work is complete.
- **Report progress**: `spec-kitty agent tasks add-history WP10 --note "..."`.

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`,````bash`

---

## Objectives & Success Criteria

You **move** code. You change **no behaviour**. `src/specify_cli/consolidation/reconciliation.py` (4,096 lines, 115 top-level symbols) is being split behind a re-exporting facade in six strictly sequential work packages (WP10 to WP15; plan IC-10, IC-11, IC-12). WP10 is the first and smallest move: the symbols every verification check shares, and the claim record types.

| Output | What it holds |
|---|---|
| `src/specify_cli/consolidation/reconciliation_kernel.py` (new, about 335 lines) | 13 shared-kernel symbols: lane branch and dependency resolution, the closed-world anchors, the bookkeeping classifier, the lazily read event log, the planning prefix, the lane walk record |
| `src/specify_cli/consolidation/reconciliation_claim_types.py` (new, about 335 lines) | 8 symbols: `ApprovedWpCommitSet` (whole, field order unchanged), its content records, the presence-gap vocabulary |
| `src/specify_cli/consolidation/reconciliation.py` | shrinks to about 3,526 lines; gains two re-export blocks |
| `tests/consolidation/reconciliation_family.py` | `RECONCILIATION_FAMILY` gains the two new modules |
| `tests/consolidation/test_reconciliation_module_imports.py` (new) | fresh-interpreter, entry-first import test (3 tests) |
| `tests/terminus/test_resume_refuses_committed_staged_deletions.py` | one patch retargeted through the family helper |

**Done means** (each item is checked by a command in "Definition of Done"):

1. `rtool.py check` prints `same` for all 21 moved symbols (13 kernel + 8 claim types): the moved code is the same code (FR-019, C-006).
2. Zero verdict change (NFR-001): the characterization corpus passes with its golden file byte-identical, the refusal-precedence matrix, the surface pin and the family guard pass, the intended-verdict pins are still all `xfailed`, the seeded mutations still turn their cells red, and the Phase 2 parity pins are unchanged.
3. The facade re-exports every moved name (C-005): no `src/` or `tests/` file needs an import edit. The single test edit is the `commits_in_range` retarget in T056.
4. `ruff check`, `ruff format --check --force-exclude` and `mypy` are clean on every file you touched, with **no new** `# noqa`, `# type: ignore`, allowlist row or registry entry (NFR-005, C-014).

**Do not** (each of these has burned a similar refactor):

- Do not edit a moved body: not a typo, not dead code, not a complexity fix, not an import inside a function. Function-local imports move with their function and stay function-local.
- Do not move any symbol that is not in the two lists above. In particular `_refused`, `ExternalDependencyAttribution`, `_final_authored_walk` / `_final_authored_blobs` / `_final_authored_deletions`, `_fully_canceled_lane_commits` / `_fully_canceled_lane_own_commits`, `_collect_approved_shas`, `_collect_excluded`, `_PresenceScope` and `_AuthoredClaim` stay in `reconciliation.py` in WP10. (Plan IC-10's prose lists `_refused` as a kernel symbol. It is not: it builds an `ExternalDependencyAttribution`, which moves in WP11 with the external-dependency cluster, and a kernel that imports from a later module would be a cycle. See T054.)
- Do not regenerate the golden file or the surface pin: never set `SPEC_KITTY_REGEN_VERDICT_CORPUS` or `SPEC_KITTY_REGEN_RECONCILIATION_SURFACE`. Do not edit `tests/consolidation/characterization/verdict_corpus.json`, `tests/consolidation/reconciliation_surface.json` or `tests/consolidation/test_reconciliation_seeded_mutations.py`.
- Do not add a module to `CHURN_SURFACE_MODULES`, a row to `tests/architectural/dead_symbol_allowlist.yaml`, a changelog fragment or a version bump. No `__init__.py` is created or touched (the new modules are flat siblings).
- Do not touch `rollback.py`, `executor.py`, `phase_*.py`, `forecast.py` or any caller (C-009). Do not run `make test-full`.

**If any expected output in this prompt differs from what you see** (a different list of unused imports, a `DIFFERS` line, a red oracle, a golden-file diff): **stop**. Record the command and its output with `spec-kitty agent tasks add-history WP10 --note "..."` and ask the orchestrator. Never edit a test, a pin or the golden file to make it pass.

## Context & Constraints

- `kitty-specs/consolidation-window-provenance-01M6Y84D/plan.md`: IC-10 (kernel and claim types), IC-11 (one module per check), IC-12 (patch retargeting and literal pins). `spec.md`: FR-019, FR-020, C-005, C-006, NFR-001, NFR-003, NFR-005. `research.md`: R-06 (split shape), R-07 (proving a pure move), R-08 (test interception).
- The oracle files come from earlier work packages: `tests/consolidation/test_reconciliation_characterization.py` and `characterization/verdict_corpus.json` (WP02), `test_refusal_precedence_matrix.py` (WP03), `test_reconciliation_surface_pin.py`, `reconciliation_surface.json`, `reconciliation_family.py`, `test_reconciliation_family_guard.py` (WP04), `test_reconciliation_intended_verdicts.py` (WP05), `test_reconciliation_seeded_mutations.py` (WP06), `test_claim_inputs_parity.py` (WP09).
- **Verified before this prompt was written.** The exact steps below were dry-run on a scratch copy of this branch (commit `aa7f5f0794`, before Phases 1 and 2): all 21 symbols came out `same`; `ruff check --select F401` on the facade then flagged exactly five unused imports (`re`, `typing.Literal`, `KITTIFY_DIR`, `KITTY_SPECS_DIR`, `lane_created_branch`); `tests/consolidation/test_reconciliation.py`, `test_canceled_dependency_attribution.py`, `test_presence_lane_base.py` and `test_approved_bound.py` gave `306 passed, 1 xfailed` (compare with your own BEFORE run: later work packages may have added tests to those files). `mypy` was clean on all three modules.
- **Why the order is safe.** The kernel symbols reference only each other and imported names. The claim types reference only each other (`ApprovedWpCommitSet` uses `ApprovedLaneContent`, `CanceledDependencyContent`, `LaneContribution`). So both modules can be created first, and nothing in them needs the facade: no forward reference is needed in WP10.
- **Rules that bind every Phase 3 work package (WP10 to WP15):**
  - **R1 Pure move.** Bodies are verbatim. `rtool.py check` is the proof; a `DIFFERS` line is a defect.
  - **R2 Re-export in alias form.** The facade imports each moved name as `name as name`. That is the repository's explicit re-export form (see `src/specify_cli/core/mission_creation.py`): ruff F401 and mypy accept it without a suppression.
  - **R3 Pinned names stay importable.** Every name in `tests/consolidation/reconciliation_surface.json` must stay importable from the facade, including third-party names that tests patch (`commits_in_range`, `path_state_at`, ...). When you prune an unused facade import and the name is pinned, keep it in alias form instead of deleting it (T056 shows the command).
  - **R4 Patches follow lookups.** A test that patches a name on the facade only intercepts the lookups that still happen in the facade. After a move, a name can be looked up in two modules; patching one of them silently narrows the interception. `rtool.py audit` shows where each patched name is looked up; a name looked up in more than one module must be patched through `setattr_reconciliation_family` (T056 does this for `commits_in_range`).
  - **R5 No new exemptions.** No suppression comment, allowlist row, registry entry or `CHURN_SURFACE_MODULES` entry (NFR-005). Moved code that already carries a justified suppression keeps it (WP10 moves none).
  - **R6 `__all__`.** Every new module declares `__all__` listing the names the facade re-exports from it.

### Helper tool (create it OUTSIDE the repository; never `git add` it)

One small tool does the mechanical work, so no code is retyped. Run this once, in the worktree, on a **clean tree** before your first edit, and keep the shell open (every command below uses `$WORK`):

```bash
WORK="$(mktemp -d)"; echo "$WORK"
git show HEAD:src/specify_cli/consolidation/reconciliation.py > "$WORK/reconciliation.before.py"   # the facade BEFORE you touch it
cat > "$WORK/rtool.py" <<'PY'
"""Helper for the reconciliation split (Mission consolidation-window-provenance-01M6Y84D). Subcommands:

  move SOURCE TARGET NAME...   cut the top-level symbols (decorators + the # comment block above + body) out of SOURCE, append them verbatim to TARGET
  check BEFORE AFTER NAME...   `same` / `DIFFERS` per symbol: AST of BEFORE's definition vs AFTER's (formatting ignored; forward-reference imports ignored)
  exports MODULE_STEM          print the `__all__` and the facade re-export block for src/specify_cli/consolidation/MODULE_STEM.py
  prune                        read `ruff --output-format json` on stdin: which unused facade imports are pinned (KEEP-AS-ALIAS) or deletable
  audit                        for each name tests patch on the facade: which reconciliation modules look it up
"""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

FACADE = "specify_cli.consolidation.reconciliation"
PACKAGE = Path("src/specify_cli/consolidation")
PATCHED = ["commits_in_range", "path_state_at", "merge_tree_write_tree_available", "resolve_canceled_wp", "attestation_stamps",
           "OVERRIDABLE_REASONS", "canceled_spine_content", "_final_authored_walk"]  # fmt: skip


def names_of(node: ast.stmt) -> list[str]:
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return [node.name]
    if isinstance(node, ast.Assign):
        return [t.id for t in node.targets if isinstance(t, ast.Name)]
    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
        return [node.target.id]
    return []


def find(tree: ast.Module, name: str) -> ast.stmt | None:
    hits = [n for n in tree.body if name in names_of(n)]
    return hits[0] if len(hits) == 1 else None


def start(node: ast.stmt, lines: list[str]) -> int:
    first = min([node.lineno, *[d.lineno for d in getattr(node, "decorator_list", [])]]) - 1
    while first > 0 and lines[first - 1].lstrip().startswith("#"):
        first -= 1
    return first


def move(source: str, target: str, wanted: list[str]) -> None:
    lines = Path(source).read_text().split("\n")
    tree = ast.parse("\n".join(lines))
    nodes = {name: find(tree, name) for name in wanted}
    if missing := [name for name, node in nodes.items() if node is None]:
        sys.exit(f"REFUSED, nothing changed (missing or defined twice): {missing}")
    spans = sorted({(start(n, lines), n.end_lineno) for n in nodes.values() if n is not None and n.end_lineno})
    chunks = ["\n".join(lines[a:b]) for a, b in spans]
    out = Path(target)
    out.write_text(out.read_text().rstrip("\n") + "\n\n\n" + "\n\n\n".join(chunks) + "\n")
    drop = {i for a, b in spans for i in range(a, b)}
    Path(source).write_text("\n".join(line for i, line in enumerate(lines) if i not in drop))
    print(f"moved {len(spans)} symbol(s), {sum(len(c.split(chr(10))) for c in chunks)} lines")


class DropForwardRefs(ast.NodeTransformer):
    def generic_visit(self, node: ast.AST) -> ast.AST:
        for field in ("body", "orelse", "finalbody"):
            stmts = getattr(node, field, None)
            if isinstance(stmts, list):
                setattr(node, field, [s for s in stmts if not (isinstance(s, ast.ImportFrom) and s.module == FACADE)])
        return super().generic_visit(node)


def check(before: str, after: str, wanted: list[str]) -> None:
    old_tree, new_tree = ast.parse(Path(before).read_text()), ast.parse(Path(after).read_text())
    bad = 0
    for name in wanted:
        old, new = find(old_tree, name), find(new_tree, name)
        same = old is not None and new is not None and ast.dump(DropForwardRefs().visit(old)) == ast.dump(DropForwardRefs().visit(new))
        print(("same    " if same else "DIFFERS ") + name)
        bad += not same
    sys.exit(1 if bad else 0)


def exports(stem: str) -> None:
    tree = ast.parse((PACKAGE / f"{stem}.py").read_text())
    names = sorted(n for node in tree.body for n in names_of(node) if n != "__all__")
    print(f"# {len(names)} names. Append to the module:\n__all__ = [" + ", ".join(f'"{n}"' for n in names) + "]\n")
    print(f"# Paste into reconciliation.py above `logger = ...`:\nfrom specify_cli.consolidation.{stem} import (")
    print("".join(f"    {n} as {n},\n" for n in names) + ")")


def prune() -> None:
    pinned = set(json.load(open("tests/consolidation/reconciliation_surface.json")))
    for message in json.load(sys.stdin):
        name = message["message"].split("`")[1].split(".")[-1]
        print(("KEEP-AS-ALIAS " if name in pinned else "delete        ") + name)


def audit() -> None:
    trees = {f.stem: ast.parse(f.read_text()) for f in sorted(PACKAGE.glob("reconciliation*.py"))}
    for name in PATCHED:
        homes = [s for s, t in trees.items() if any(isinstance(n, ast.Name) and n.id == name and isinstance(n.ctx, ast.Load) for n in ast.walk(t))]
        print(f"{name:34} looked up in: {', '.join(homes) or '-'}")


if __name__ == "__main__":
    cmd, args = (sys.argv[1] if len(sys.argv) > 1 else ""), sys.argv[2:]
    if cmd == "move" and len(args) >= 3:
        move(args[0], args[1], args[2:])
    elif cmd == "check" and len(args) >= 3:
        check(args[0], args[1], args[2:])
    elif cmd == "exports" and len(args) == 1:
        exports(args[0])
    elif cmd in ("prune", "audit") and not args:
        prune() if cmd == "prune" else audit()
    else:
        sys.exit(__doc__)
PY
```

The tool's docstring lists its five subcommands (`move`, `check`, `exports`, `prune`, `audit`); each is used below. `move` refuses, and changes nothing, if a name is missing or defined twice. `check` ignores formatting and ignores a `from specify_cli.consolidation.reconciliation import ...` line inside a function body (the sanctioned forward references). Resuming after review feedback? Take `reconciliation.before.py` from the parent of your first commit of this work package (`git show <first-commit>^:src/specify_cli/consolidation/reconciliation.py`), not from `HEAD`.

Also set the shorthand used below: `C=src/specify_cli/consolidation`. If you resume after review feedback, take `reconciliation.before.py` from the parent of your first commit of this work package (`git show <first-commit>^:$C/reconciliation.py`), not from `HEAD`.

First, record the BEFORE results of the oracle block (see "Definition of Done"): run it once on the untouched tree and note each pass count. After your change the counts must be identical.

## Branch Strategy

- **Strategy**: Planning artifacts were generated on kitty/mission-consolidation-window-provenance-01M6Y84D; completed changes must merge into feat/consolidation-window-provenance.
- **Planning base branch**: feat/consolidation-window-provenance
- **Merge target branch**: feat/consolidation-window-provenance

> Populated by `finalize-tasks`. Execution worktrees are allocated per computed lane from `lanes.json`.

```bash
spec-kitty agent action implement WP10 --agent <name> --mission consolidation-window-provenance-01M6Y84D
```

## Subtasks & Detailed Guidance

### Subtask T054 – Move the kernel symbols to `reconciliation_kernel.py`

- **Purpose**: Give the eight check modules that follow one shared home for the helpers they all call (IC-10).
- **Steps**:
  1. Create `$C/reconciliation_kernel.py` containing **only** this header (it was validated: ruff `F`/`E9` clean once the symbols are appended):

```python
"""Shared kernel of the terminus reconciliation gate (Mission consolidation-window-provenance-01M6Y84D, WP10).

The symbols every verification check shares: lane branch and dependency resolution, the closed-world
anchors, the mission-owned bookkeeping classifier, the lazily-read status event log, the planning
prefix and the lane walk record. Moved verbatim out of ``reconciliation.py``; that module re-exports
every name, so no caller changes (C-005).
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from specify_cli.consolidation.git_probes import GitProbeError, commits_in_range, first_parent_commits_in_range
from specify_cli.consolidation.wp_attribution import Unattributable, UnattributableReason
from specify_cli.core.constants import KITTIFY_DIR, KITTY_SPECS_DIR
from specify_cli.lanes.compute import is_planning_lane, lane_created_branch, lane_fully_canceled
from specify_cli.lanes.models import ExecutionLane, LanesManifest
```

  2. Move the 13 symbols (this appends them to the header, in their original order, and removes them from the facade):

```bash
python3 "$WORK/rtool.py" move $C/reconciliation.py $C/reconciliation_kernel.py _APPROVED_MEMBERSHIP_LANES _lane_is_approved _dependency_lane_ids _lane_branch_for _closed_world_anchors _lane_tip_commits _lane_first_parent_spine _KITTY_OPS_ROOT_RECORD _is_nested_alias_coordination_file _is_bookkeeping _ClaimEventLog _planning_prefix _LaneWalk
```

     Expect `moved 13 symbol(s), 270 lines`. The tool takes the `#` comment block directly above a symbol, and its decorator, along with it: `_APPROVED_MEMBERSHIP_LANES` and `_KITTY_OPS_ROOT_RECORD` keep their comments and `_LaneWalk` keeps its `@dataclass(frozen=True)`.
  3. Append the module's `__all__` (R6) at the very end of the file. The tool prints it from the module's own top-level names; copy only the `__all__ = [...]` line:

```bash
python3 "$WORK/rtool.py" exports reconciliation_kernel      # prints "# 13 names." then the __all__ line and the facade block
```

  4. Check the module on its own (the facade is broken until T056, so check only this file):

```bash
uv run --frozen ruff check --select F,E9 $C/reconciliation_kernel.py
uv run --frozen ruff format $C/reconciliation_kernel.py
```

     Expect `All checks passed!`. An `F821 Undefined name` means a symbol uses a name your header lacks: add the import from the facade's own import block (do not guess a new module).
- **Files**: `src/specify_cli/consolidation/reconciliation_kernel.py` (new), `reconciliation.py`.
- **Notes**: `_ClaimEventLog.read` imports `StoreError, read_events` from `specify_cli.status` inside the method. That stays inside the method. It is also why `monkeypatch.setattr("specify_cli.status.read_events", ...)` in `test_reconciliation.py` still intercepts after the move: the lookup happens at call time in `specify_cli.status`.

### Subtask T055 – Move `ApprovedWpCommitSet` and the content records to `reconciliation_claim_types.py`

- **Purpose**: One home for the claim record, which stays whole (C-006). Some constructions are positional, so **field order must not change**; moving the text verbatim guarantees it.
- **Steps**:
  1. Create `$C/reconciliation_claim_types.py` containing only this header:

```python
"""Claim record types of the terminus reconciliation gate (Mission consolidation-window-provenance-01M6Y84D, WP10).

``ApprovedWpCommitSet`` (whole, field order unchanged: some constructions are positional) and the
content records it carries. Moved verbatim out of ``reconciliation.py``; that module re-exports every
name, so no caller changes (C-005, C-006).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Literal

from specify_cli.consolidation.wp_attribution import CanceledPathState
```

  2. Move the 8 symbols:

```bash
python3 "$WORK/rtool.py" move $C/reconciliation.py $C/reconciliation_claim_types.py PresenceGap _GAP_ABSENT _GAP_UNCHANGED MissingApprovedContent CanceledDependencyContent ApprovedLaneContent LaneContribution ApprovedWpCommitSet
```

     Expect `moved 8 symbol(s), 292 lines`.
  3. Append `__all__` at the end of the file, the same way (copy only the `__all__ = [...]` line):

```bash
python3 "$WORK/rtool.py" exports reconciliation_claim_types   # prints "# 8 names." then the __all__ line and the facade block
```

  4. `uv run --frozen ruff check --select F,E9 $C/reconciliation_claim_types.py` then `uv run --frozen ruff format $C/reconciliation_claim_types.py`. Expect `All checks passed!`.
- **Files**: `src/specify_cli/consolidation/reconciliation_claim_types.py` (new), `reconciliation.py`.
- **Notes**: `PresenceGap`, `_GAP_ABSENT` and `_GAP_UNCHANGED` move here (not to a rendering module) because `MissingApprovedContent` is typed with `PresenceGap` and the rendering module (WP11) imports `_GAP_ABSENT` from here. `StateAt` (a `Callable` alias used by the presence check) is **not** moved: it moves with the presence slice in WP15.

### Subtask T056 – Facade re-exports, `RECONCILIATION_FAMILY`, patch audit

- **Purpose**: Make the facade behave exactly as before for every caller and every test (C-005), and keep test patches intercepting what they intercepted before (FR-020).
- **Steps**:
  1. In `$C/reconciliation.py`, add the re-export blocks on their own lines **directly above** the line `logger = logging.getLogger(__name__)`, after a comment line `# Re-exports (C-005): every name moved out of this module stays importable from it.`. Print them with the tool (the facade block is the part after `# Paste into reconciliation.py above ...`), once per module:

```bash
python3 "$WORK/rtool.py" exports reconciliation_claim_types   # 8 names
python3 "$WORK/rtool.py" exports reconciliation_kernel        # 13 names
```

     Each block has one line per name in the form `_lane_branch_for as _lane_branch_for,` (R2).
  2. Find the imports the move made unused, and see which of them the surface pin pins:

```bash
uv run --frozen ruff check --select F401,F811 --output-format json $C/reconciliation.py | python3 "$WORK/rtool.py" prune
```

     Expect exactly five lines, all `delete`: `re`, `Literal`, `KITTIFY_DIR`, `KITTY_SPECS_DIR`, `lane_created_branch`. (If a line says `KEEP-AS-ALIAS`, change that import to the alias form `name as name` by hand first, see R3.) Then delete the rest and format:

```bash
uv run --frozen ruff check --select F401,F811 --fix $C/reconciliation.py
uv run --frozen ruff format $C/reconciliation.py $C/reconciliation_kernel.py $C/reconciliation_claim_types.py
uv run --frozen ruff check $C/reconciliation.py $C/reconciliation_kernel.py $C/reconciliation_claim_types.py
```

     The last command must print `All checks passed!` (this includes the complexity check, C901 at 15).
  3. In `tests/consolidation/reconciliation_family.py` (created by WP04), import the two new modules and extend the tuple. The tuple keeps the facade first and appends modules in the order the split creates them:

```python
from specify_cli.consolidation import reconciliation, reconciliation_claim_types, reconciliation_kernel

RECONCILIATION_FAMILY: tuple[ModuleType, ...] = (reconciliation, reconciliation_kernel, reconciliation_claim_types)
```

     Keep WP04's comment and the rest of the file as it is. Adapt the existing `from specify_cli.consolidation import ...` line instead of adding a second one.
  4. **Patch audit (R4).** Run, from the repository root:

```bash
python3 "$WORK/rtool.py" audit
```

     Expect:
```text
commits_in_range                   looked up in: reconciliation, reconciliation_kernel
path_state_at                      looked up in: reconciliation
merge_tree_write_tree_available    looked up in: reconciliation
resolve_canceled_wp                looked up in: reconciliation
attestation_stamps                 looked up in: reconciliation
OVERRIDABLE_REASONS                looked up in: reconciliation
canceled_spine_content             looked up in: reconciliation
_final_authored_walk               looked up in: reconciliation
```

     Only `commits_in_range` is now looked up in two modules (the kernel's `_lane_tip_commits` reads it). The test that patches it must patch both. In `tests/terminus/test_resume_refuses_committed_staged_deletions.py` (the test around line 190), make exactly these two edits:
     - replace the line `from specify_cli.consolidation import reconciliation as rec` with `from tests.consolidation.reconciliation_family import setattr_reconciliation_family`;
     - replace `monkeypatch.setattr(rec, "commits_in_range", _unreadable_mission_range)` with `setattr_reconciliation_family(monkeypatch, "commits_in_range", _unreadable_mission_range)`.

     The wrapper `_unreadable_mission_range` still calls the real `commits_in_range` imported from `specify_cli.consolidation.git_probes`; leave that import. Nothing else in that file uses `rec`.
  5. Run the moved-code proof and the quick oracles:

```bash
python3 "$WORK/rtool.py" check "$WORK/reconciliation.before.py" $C/reconciliation_kernel.py _APPROVED_MEMBERSHIP_LANES _lane_is_approved _dependency_lane_ids _lane_branch_for _closed_world_anchors _lane_tip_commits _lane_first_parent_spine _KITTY_OPS_ROOT_RECORD _is_nested_alias_coordination_file _is_bookkeeping _ClaimEventLog _planning_prefix _LaneWalk
python3 "$WORK/rtool.py" check "$WORK/reconciliation.before.py" $C/reconciliation_claim_types.py PresenceGap _GAP_ABSENT _GAP_UNCHANGED MissingApprovedContent CanceledDependencyContent ApprovedLaneContent LaneContribution ApprovedWpCommitSet
uv run --frozen pytest -q tests/consolidation/test_reconciliation_surface_pin.py tests/consolidation/test_reconciliation_family_guard.py tests/consolidation/test_reconciliation.py
```

     Expect 21 `same` lines and no `DIFFERS`/`MISSING`; the pytest run must pass.
- **Files**: `reconciliation.py`, `tests/consolidation/reconciliation_family.py`, `tests/terminus/test_resume_refuses_committed_staged_deletions.py`.
- **Notes**: Do not delete a facade import that `rtool.py prune` marks `KEEP-AS-ALIAS`. Do not add names to the facade's own `__all__` (it stays the 10 names it has: C-005, and the surface pin lists it).

### Subtask T057 – Fresh-interpreter import test for the new modules

- **Purpose**: A module-level import cycle only shows when the cycle is entered from the right module, and the unit tests always enter through the facade. This test enters each new module first.
- **Steps**: Create `tests/consolidation/test_reconciliation_module_imports.py` with exactly this content (validated: 3 passed in under a second once the package was compiled; the bogus module is the control that proves the harness can fail):

```python
"""Every module split out of ``consolidation/reconciliation.py`` imports cleanly when it is the FIRST of the family to load.

The split modules look names up in each other (and, for the temporary forward references, in the facade). A
module-level import cycle only shows when the cycle is entered from the right module, so a fresh interpreter
loads the package once, then for each module in turn drops every ``reconciliation*`` module from ``sys.modules``,
imports that module first and the facade second. A bogus module name is the control: the harness must report it.
"""

from __future__ import annotations

import functools
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.fast

_REPO_ROOT = Path(__file__).resolve().parents[2]
_PACKAGE = "specify_cli.consolidation"
# One entry per module split out of reconciliation.py; each work package of the split appends its modules here.
SPLIT_MODULES: tuple[str, ...] = (
    "reconciliation_kernel",
    "reconciliation_claim_types",
)
_BOGUS = "reconciliation_this_module_does_not_exist"
_DRIVER = """
import importlib, sys
prefix = "specify_cli.consolidation.reconciliation"
import specify_cli.consolidation
for dotted in sys.argv[1:]:
    for key in [k for k in sys.modules if k == prefix or k.startswith(prefix + "_")]:
        del sys.modules[key]
    try:
        importlib.import_module(dotted)
        importlib.import_module(prefix)
        print("OK", dotted)
    except Exception as exc:
        print("FAIL", dotted, type(exc).__name__, exc)
"""


@functools.cache
def _entry_first_results() -> dict[str, str]:
    modules = [f"{_PACKAGE}.{name}" for name in (*SPLIT_MODULES, _BOGUS)]
    run = subprocess.run([sys.executable, "-c", _DRIVER, *modules], capture_output=True, text=True, check=False, cwd=_REPO_ROOT)
    assert run.returncode == 0, run.stderr[-2000:]
    return {line.split()[1].rsplit(".", 1)[1]: line for line in run.stdout.splitlines() if line.startswith(("OK ", "FAIL "))}


@pytest.mark.parametrize("module", SPLIT_MODULES)
def test_split_module_imports_first_in_a_fresh_interpreter(module: str) -> None:
    assert _entry_first_results()[module].startswith("OK "), _entry_first_results()[module]


def test_entry_first_harness_reports_a_broken_module() -> None:
    assert _entry_first_results()[_BOGUS].startswith("FAIL "), _entry_first_results()[_BOGUS]
```

  Then `uv run --frozen pytest -q tests/consolidation/test_reconciliation_module_imports.py` must report `3 passed`; `uv run --frozen ruff check`, `uv run --frozen ruff format --check --force-exclude` and `uv run --frozen mypy` on the file must be clean.
- **Files**: `tests/consolidation/test_reconciliation_module_imports.py` (new).
- **Notes**: WP11 and WP12 append their modules to `SPLIT_MODULES`; do not add modules you have not created.

### Subtask T058 – `CHURN_SURFACE_MODULES` check and the oracle gates

- **Purpose**: Confirm the move trips no literal-pin gate, and record the proof (IC-10 risk, P-10).
- **Steps**:
  1. `CHURN_SURFACE_MODULES` (`tests/architectural/test_exemption_registry_ratchet.py`) does **not** list `reconciliation.py` today, so the new modules need no entry, and you must not add one: `_KITTY_OPS_ROOT_RECORD` (a filename-like regex, now in the kernel) would be discovered as an exemption collection and force a registry row, which NFR-005 forbids. Prove it is unaffected: `uv run --frozen pytest -q tests/architectural/test_exemption_registry_ratchet.py` passes with the file unchanged.
  2. Run the whole "Definition of Done" block. Compare every oracle count with your BEFORE note.
  3. Append the tracer entries and the history note (see the last checklist item).
- **Files**: none (verification only).

## Test Strategy

This work package adds no behaviour, so the proof is the Phase 1 oracles, not new assertions: the golden corpus (verdict status, refusal code, divergence fields, exit code per cell), the refusal-precedence matrix, the surface pin with object identity, the patch-lookup guard and the seeded mutations. They ran green before you started and must run green, with identical counts and a byte-identical golden file, after. The only new test is the fresh-interpreter import test (T057). The AST comparison (`rtool.py check`) shows the moved text is unchanged.

## Definition of Done

Run these **exactly**, in this order, from the worktree root, and paste each final summary line (for example `12 passed in 3.21s`) into the history note. Do not paraphrase output; the reviewer reruns everything.

```bash
# 1. the moved code is the same code
python3 "$WORK/rtool.py" check "$WORK/reconciliation.before.py" $C/reconciliation_kernel.py _APPROVED_MEMBERSHIP_LANES _lane_is_approved _dependency_lane_ids _lane_branch_for _closed_world_anchors _lane_tip_commits _lane_first_parent_spine _KITTY_OPS_ROOT_RECORD _is_nested_alias_coordination_file _is_bookkeeping _ClaimEventLog _planning_prefix _LaneWalk
python3 "$WORK/rtool.py" check "$WORK/reconciliation.before.py" $C/reconciliation_claim_types.py PresenceGap _GAP_ABSENT _GAP_UNCHANGED MissingApprovedContent CanceledDependencyContent ApprovedLaneContent LaneContribution ApprovedWpCommitSet

# 2. no pinned file changed (run BEFORE every commit; both commands must print nothing)
git diff --exit-code -- tests/consolidation/characterization/ tests/consolidation/reconciliation_surface.json tests/consolidation/test_reconciliation_seeded_mutations.py
git status --short | grep -vE 'reconciliation|test_resume_refuses_committed_staged_deletions' || true

# 3. the new test
uv run --frozen pytest -q tests/consolidation/test_reconciliation_module_imports.py
```

Then the Phase 1/2 oracle block (counts equal to your BEFORE run):

```bash
uv run --frozen pytest -q tests/consolidation/test_reconciliation_characterization.py        # the golden verdict corpus (WP02)
uv run --frozen pytest -q tests/consolidation/test_refusal_precedence_matrix.py              # refusal order and text (WP03)
uv run --frozen pytest -q tests/consolidation/test_reconciliation_surface_pin.py tests/consolidation/test_reconciliation_family_guard.py   # names, identity, patch lookups (WP04)
uv run --frozen pytest -q -rxX tests/consolidation/test_reconciliation_intended_verdicts.py  # must report only xfailed (WP05)
uv run --frozen pytest -q tests/consolidation/test_reconciliation_seeded_mutations.py        # every mutation still turns its cell red (WP06)
uv run --frozen pytest -q -rxX tests/consolidation/test_claim_inputs_parity.py               # Phase 2 parity pins (WP09)
```

Then the blast radius (the files that import or patch the facade, plus their owning subsystem directories):

```bash
uv run --frozen pytest -q -n auto --dist loadfile tests/consolidation/
uv run --frozen pytest -q tests/coordination/test_projection_teardown.py tests/integration/test_merge_resume.py tests/specify_cli/consolidation/test_single_branch_mission_to_target.py
uv run --frozen pytest -q tests/terminus/test_repro_4982.py tests/terminus/test_repro_4985.py tests/terminus/test_repro_4991.py tests/terminus/test_repro_4997.py tests/terminus/test_repro_5021.py tests/terminus/test_resume_refreshes_lagging_coord_worktree.py tests/terminus/test_resume_refuses_committed_staged_deletions.py tests/terminus/test_rollback_door.py tests/terminus/test_rollback_record_rebaseline.py
```

(The `tests/terminus/` files drive the real CLI and take minutes. A red there that looks stale is the stale-install/stale-venv case: run `uv sync --frozen --all-extras` and retry before recording anything.)

Then the implicated architectural gate files (never the bare directory) and the rollback pin:

```bash
uv run --frozen pytest -q tests/architectural/test_no_dead_symbols.py tests/architectural/test_dead_symbol_allowlist_contract.py tests/architectural/test_no_dead_modules.py tests/architectural/test_exemption_registry_ratchet.py
uv run --frozen pytest -q tests/ci/test_reducer_lock_census.py tests/consolidation/test_single_rollback_authority.py
```

Then quality and the fast baseline:

```bash
uv run --frozen ruff check $C/reconciliation.py $C/reconciliation_kernel.py $C/reconciliation_claim_types.py tests/consolidation/reconciliation_family.py tests/consolidation/test_reconciliation_module_imports.py tests/terminus/test_resume_refuses_committed_staged_deletions.py
uv run --frozen ruff format --check --force-exclude $C/reconciliation.py $C/reconciliation_kernel.py $C/reconciliation_claim_types.py tests/consolidation/reconciliation_family.py tests/consolidation/test_reconciliation_module_imports.py tests/terminus/test_resume_refuses_committed_staged_deletions.py
uv run --frozen mypy $C/reconciliation.py $C/reconciliation_kernel.py $C/reconciliation_claim_types.py tests/consolidation/reconciliation_family.py tests/consolidation/test_reconciliation_module_imports.py
make test-fast
```

Checklist:

- [ ] 21 `same` lines, no `DIFFERS` or `MISSING`.
- [ ] The golden file, the surface pin JSON and the mutation-table file are untouched; every oracle count equals the BEFORE count; the intended-verdict file reports only `xfailed`; `test_reconciliation_module_imports.py` reports `3 passed`.
- [ ] `git diff --stat` shows only: `reconciliation.py`, the two new modules, `reconciliation_family.py`, `test_reconciliation_module_imports.py` and `test_resume_refuses_committed_staged_deletions.py` (plus tracer notes). No `# noqa`, `# type: ignore`, allowlist row, registry entry or changelog fragment was added; `pyproject.toml` is untouched.
- [ ] Both new modules declare `__all__`; the facade's own `__all__` still has its 10 names.
- [ ] Rollback authority untouched: `tests/consolidation/test_single_rollback_authority.py` passes (C-009).
- [ ] **Tracer files**: append dated entries to `kitty-specs/consolidation-window-provenance-01M6Y84D/traces/design-decisions.md` (the `_refused`/`ExternalDependencyAttribution` placement decision, the `commits_in_range` retarget and why, the `__all__` rule) and to `traces/tooling-friction.md` (any friction). Format `- **[YYYY-MM-DD][implement WP10] <summary>.** <detail>`. If your checkout has no `kitty-specs/`, record them with `spec-kitty agent tasks add-history WP10 --note "..."`.
- [ ] Never run `make test-full`. Never claim a command passed that you did not run.

## Risks & Mitigations

- **A silent behaviour change hidden in a "pure move"**: the AST comparison and the byte-identical golden file catch it; do not reformat bodies by hand (only `ruff format` touches them).
- **A patch that quietly intercepts less after the move**: R4 and the audit; the only affected name in WP10 is `commits_in_range` (T056).
- **Deleting a pinned facade import**: R3; `rtool.py prune` and `test_every_pinned_name_is_importable` catch it.
- **An import cycle**: none is possible in WP10 (the two modules import nothing from the facade), and the fresh-interpreter test proves it.
- **Function-local imports hoisted by an editor or `ruff --fix`**: the fidelity check would print `DIFFERS`.

## Review Guidance

- Reviewer profile: `reviewer-renata` (Claude reviewer for a cheap-tier implementer).
- **Model tier: cheap** (implementer: TokenFactory glm-5.3; reviewer: Claude). Rerun every Definition-of-Done command yourself; do not trust pasted output.
- Re-run both `rtool.py check` lines against `git show <parent of the first WP10 commit>:src/specify_cli/consolidation/reconciliation.py`.
- **Mutation spot-check on the moved code (seeded-mutation proof).** Back up the kernel, break `_is_bookkeeping` in the new module, run the corpus, and expect it to go red, then restore:
```bash
cp src/specify_cli/consolidation/reconciliation_kernel.py /tmp/kernel.good
python3 - <<'PY'
import pathlib
p = pathlib.Path("src/specify_cli/consolidation/reconciliation_kernel.py")
s = p.read_text()
old = '    normalized = path.rstrip("/")\n    if mission_slug:'
assert s.count(old) == 1
p.write_text(s.replace(old, '    return False\n' + old))
PY
uv run --frozen pytest -q tests/consolidation/test_reconciliation_characterization.py   # must FAIL, naming changed cells
cp /tmp/kernel.good src/specify_cli/consolidation/reconciliation_kernel.py
git diff --exit-code src/specify_cli/consolidation/reconciliation_kernel.py   # clean again
```
  Repeat once for `_closed_world_anchors` (make it `return []`). If a mutation leaves the corpus green, the move broke the interception path: check `RECONCILIATION_FAMILY` and the facade alias lines.
- Check the facade has no stray blank-line debris, that `logger` is still defined above the re-exports' end, and that the new modules contain no `import` of `specify_cli.consolidation.reconciliation`.

## Progress & Status

- **Record a progress note**: `spec-kitty agent tasks add-history WP10 --note "<what you did>"`
- **Change WP status**: `spec-kitty agent tasks move-task WP10 --to <status>`
- **View history and status**: `spec-kitty agent tasks status --mission consolidation-window-provenance-01M6Y84D`
