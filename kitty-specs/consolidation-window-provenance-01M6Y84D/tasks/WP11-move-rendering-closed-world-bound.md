---
work_package_id: WP11
title: Move the rendering, closed-world and approved-bound checks
dependencies:
- WP10
requirement_refs:
- FR-019
- FR-020
- NFR-001
- NFR-008
planning_base_branch: feat/consolidation-window-provenance
merge_target_branch: feat/consolidation-window-provenance
branch_strategy: Planning artifacts for this mission were generated on feat/consolidation-window-provenance. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into feat/consolidation-window-provenance unless the human explicitly redirects the landing branch.
subtasks:
- T059
- T060
- T061
- T062
- T063
phase: Phase 3 - Behaviour-preserving split
history:
- at: '2026-11-08T19:52:39Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/consolidation/
create_intent:
- tests/consolidation/reconciliation_family.py
- tests/consolidation/test_reconciliation_module_imports.py
- src/specify_cli/consolidation/reconciliation_rendering.py
- src/specify_cli/consolidation/reconciliation_closed_world.py
- src/specify_cli/consolidation/reconciliation_bound.py
execution_mode: code_change
model: glm-5.3
owned_files:
- src/specify_cli/consolidation/reconciliation.py
- src/specify_cli/consolidation/reconciliation_rendering.py
- src/specify_cli/consolidation/reconciliation_closed_world.py
- src/specify_cli/consolidation/reconciliation_bound.py
- tests/consolidation/reconciliation_family.py
- tests/consolidation/test_reconciliation_module_imports.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP11 – Move the rendering, closed-world and approved-bound checks

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
- **Report progress**: `spec-kitty agent tasks add-history WP11 --note "..."`.

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`,````bash`

---

## Objectives & Success Criteria

You **move** code. You change **no behaviour**. This is the second of six sequential moves that split `src/specify_cli/consolidation/reconciliation.py` behind a re-exporting facade (WP10 to WP15; plan IC-11, IC-12). WP10 already created `reconciliation_kernel.py` and `reconciliation_claim_types.py`. WP11 moves three more units:

| New module | Symbols | Lines moved |
|---|---|---|
| `reconciliation_rendering.py` | 11: the recovery tail, the compound-refusal separators, the two content error codes, the `_describe_*` clause helpers, `_attest_tail`, `_join_refusals` | about 100 |
| `reconciliation_closed_world.py` | 21: the excluded-content collection and the declared external dependency refs (#6771), with their 8 refusal texts | about 380 |
| `reconciliation_bound.py` | 13: the approved bound (#5668), its `single_branch` write-branch leg, `approved_bound_refusal` and the lane-tip re-check | about 270 |

Also: the facade gains three re-export blocks (it shrinks to about 2,740 lines), `RECONCILIATION_FAMILY` gains the three modules, and `test_reconciliation_module_imports.py` gains three entries.

**Done means:**

1. `rtool.py check` prints `same` for all 45 moved symbols (11 + 21 + 13) (FR-019, C-006).
2. Zero verdict change (NFR-001): the Phase 1/2 oracles (golden corpus, precedence matrix, surface pin, family guard, intended-verdict pins, seeded mutations, parity pins) give the same counts as before you started, with the golden file byte-identical. The mutation rows for the moved checks (`rendering`, `closed-world`, `external-dependency-refs`, `approved-bound`, `write-branch`, `lane-tip-recheck`) still turn their cells red (NFR-008).
3. The facade still exports every moved name (C-005); no `src/` caller and no test needs an import edit.
4. ruff, `ruff format --check --force-exclude` and mypy are clean on every touched file with no new suppression, allowlist row or registry entry (NFR-005, C-014).

**One forward reference, and only one.** `_verify_declared_ref` (closed world) calls `_final_authored_walk`, which stays in `reconciliation.py` until WP15. A module-level import of the facade from the new module would be a cycle, so T060 adds a single function-local import, marked `# TEMPORARY FORWARD REFERENCE (moves in WP15)`. This is the one Phase 3 convention, used identically by WP11, WP12 and WP14: one function-local import from the facade, under that comment naming the work package that removes it; WP15 removes every such line and adds the durable test `test_split_modules_never_import_the_facade`. `rtool.py check` ignores exactly that kind of line. Add no other import of the facade to any new module.

**Do not:**

- Do not edit a moved body: not a typo, not dead code, not a complexity fix, not a function-local import. Function-local imports move with their function and stay function-local.
- Do not move any symbol that is not in your lists. Do not regenerate the golden file or the surface pin (never set `SPEC_KITTY_REGEN_VERDICT_CORPUS` or `SPEC_KITTY_REGEN_RECONCILIATION_SURFACE`); do not edit `tests/consolidation/characterization/verdict_corpus.json`, `tests/consolidation/reconciliation_surface.json` or `tests/consolidation/test_reconciliation_seeded_mutations.py`.
- Do not add a module to `CHURN_SURFACE_MODULES`, a row to `tests/architectural/dead_symbol_allowlist.yaml`, a `# noqa` / `# type: ignore`, a changelog fragment or a version bump. No `__init__.py` is created or touched.
- Do not touch `rollback.py`, `executor.py`, `phase_*.py`, `forecast.py` or any caller (C-009). Do not run `make test-full`.
- Do not move `_collect_approved_shas`, `_PresenceScope`, `_final_authored_*`, `_fully_canceled_lane_*`, the mixed-lane or canceled-dependency symbols, `build_approved_wp_set`, `claim_integrity_refusal`, `_compound_refusal` or `_missing_branch_refusal_text`: they move in WP13 to WP15.

**If any expected output below differs** (a different unused-import list, a `DIFFERS` line, a red oracle, a golden-file diff): **stop**, record the command and output with `spec-kitty agent tasks add-history WP11 --note "..."`, and ask the orchestrator. Never edit a test, a pin or the golden file to make it pass.

## Context & Constraints

- `kitty-specs/consolidation-window-provenance-01M6Y84D/plan.md`: IC-11, IC-12. `spec.md`: FR-019, FR-020, C-005, C-006, NFR-001, NFR-003, NFR-005, NFR-008. `research.md`: R-06, R-07, R-08.
- The oracle files come from earlier work packages (WP02 corpus and golden file, WP03 precedence matrix, WP04 surface pin / family / guard, WP05 intended verdicts, WP06 seeded mutations, WP09 parity pins).
- **Dependency analysis (done when this prompt was written).** The symbols of each new module reference only: each other, earlier modules (`reconciliation_kernel`, `reconciliation_claim_types`, and for the bound and verifier also `reconciliation_rendering`) and imported names, with exactly one exception, the forward reference above. So: rendering depends on claim types; closed world and bound depend on the kernel. Nothing moved here depends on anything in WP12 to WP15.
- **Why these units.** The rendering module holds only text that several later modules share (the canceled pair in WP13, the claim orchestration in WP14, the verifier in WP12), so it must exist first. `_attest_tail` and `_join_refusals` sit far from the other helpers in the file (near the mixed-lane code) but belong here for the same reason. `_refused` moves with the external-dependency cluster: it builds an `ExternalDependencyAttribution`.
- Complexity (NFR-004) is unchanged because bodies are unchanged; the one added import is not a branch.
- A moved function that has a function-local import keeps it: `_recorded_lane_heads` (`StoreError, read_events`), `approved_bound_refusal` (`materialize_snapshot`), `_bound_write_branch` (`minted_mission_branch`), `_write_branch_verdict` (`from .write_branch_bound import ...`; a relative import that still resolves, the new module is in the same package). `approved_bound_refusal` now makes `reconciliation_bound.py` a second reader of the CLI reducer in the reducer-lock census; `tests/ci/test_reducer_lock_census.py` must stay green and needs no edit.
- **Rules that bind every Phase 3 work package (the same R1-R6 as WP10):** R1 pure move (`rtool.py check` is the proof); R2 the facade re-exports each moved name as `name as name`; R3 every name in `tests/consolidation/reconciliation_surface.json` stays importable from the facade, so a pinned unused import is kept in alias form, not deleted; R4 a test patch must intercept every module that looks the name up (`rtool.py audit`, `setattr_reconciliation_family`); R5 no new exemptions; R6 every new module declares `__all__` (the names the facade re-exports from it).

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

Shorthand: `C=src/specify_cli/consolidation`. WP10 must already be merged into your worktree: confirm `$C/reconciliation_kernel.py` and `tests/consolidation/reconciliation_family.py` exist. First record the BEFORE results of the oracle block (see "Definition of Done") on the untouched tree; after your change the counts must be identical.

## Branch Strategy

- **Strategy**: Planning artifacts were generated on kitty/mission-consolidation-window-provenance-01M6Y84D; completed changes must merge into feat/consolidation-window-provenance.
- **Planning base branch**: feat/consolidation-window-provenance
- **Merge target branch**: feat/consolidation-window-provenance

> Populated by `finalize-tasks`. Execution worktrees are allocated per computed lane from `lanes.json`.

```bash
spec-kitty agent action implement WP11 --agent <name> --mission consolidation-window-provenance-01M6Y84D
```

## Subtasks & Detailed Guidance

### Subtask T059 – Move the rendering helpers to `reconciliation_rendering.py`

- **Steps**:
  1. Create `$C/reconciliation_rendering.py` containing **only** this header:

```python
"""Refusal and clause text shared by the reconciliation checks (Mission consolidation-window-provenance-01M6Y84D, WP11).

The recovery tail, the compound-refusal separators, the two content error codes and the helpers that
render a divergence entry or join refusals. Moved verbatim out of ``reconciliation.py``; that module
re-exports every name, so no caller changes (C-005).
"""

from __future__ import annotations

from collections.abc import Sequence

from specify_cli.consolidation.canceled_attestation import ATTEST_FLAG, ATTEST_REASON_FLAG
from specify_cli.consolidation.reconciliation_claim_types import _GAP_ABSENT, CanceledDependencyContent, MissingApprovedContent
from specify_cli.consolidation.wp_attribution import CanceledPathState
```

  2. Move the 11 symbols, then append `__all__`:

```bash
python3 "$WORK/rtool.py" move $C/reconciliation.py $C/reconciliation_rendering.py _RECOVERY_TAIL _ALSO_HAS _BOTH_NEEDED APPROVED_CONTENT_MISSING CANCELED_REACHABLE_VIA_DEPENDENCY _attest_tail _renamed_note _describe_canceled_content _describe_approved_content_missing _describe_canceled_reachable _join_refusals
python3 "$WORK/rtool.py" exports reconciliation_rendering     # "# 11 names."; copy only the __all__ line to the end of the module
uv run --frozen ruff check --select F,E9 $C/reconciliation_rendering.py
uv run --frozen ruff format $C/reconciliation_rendering.py
```

     Expect `moved 11 symbol(s), 100 lines` (give or take a line of comment) and `All checks passed!`. An `F821` means the header lacks an import a symbol uses: add it from the facade's own import block, never a new module.
- **Notes**: `_attest_tail` uses `ATTEST_FLAG` / `ATTEST_REASON_FLAG` (the header imports them). The facade's remaining code (`_mixed_lane_recovery` and others) keeps calling these helpers through the facade names; T062 adds the re-exports.

### Subtask T060 – Move the closed-world check and the external dependency refs to `reconciliation_closed_world.py`

- **Steps**:
  1. Create `$C/reconciliation_closed_world.py` containing **only** this header:

```python
"""Closed-world inputs of the reconciliation gate (Mission consolidation-window-provenance-01M6Y84D, WP11).

The excluded-content collection and the declared external dependency refs (#6771): resolving a ref,
verifying it, and the pin check at the gate. Moved verbatim out of ``reconciliation.py``; that module
re-exports every name, so no caller changes (C-005).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from specify_cli.consolidation._constants import (
    DEPENDENCY_REF_COVERS_MISSION_WORK,
    DEPENDENCY_REF_MOVED,
    DEPENDENCY_REF_UNREACHABLE,
    DEPENDENCY_REF_UNRESOLVED,
    DEPENDENCY_REF_UNVERIFIABLE,
    error_code_suffix,
)
from specify_cli.consolidation.git_probes import (
    GitProbeError,
    commits_in_range,
    first_parent_commits_in_range,
    patch_id_of,
    resolve_commit,
    sha_reachable_from,
)
from specify_cli.consolidation.reconciliation_kernel import _lane_branch_for, _lane_tip_commits
from specify_cli.consolidation.wp_attribution import stamp_of
from specify_cli.lanes._git import branch_exists
from specify_cli.lanes.lane_tip import LaneTipListingError, read_tip, recorded_tip_branches
from specify_cli.lanes.models import LanesManifest
```

  2. Move the 21 symbols (the 8 `_REFUSE_DEPENDENCY_*` texts keep the 9-line comment block above the first one):

```bash
python3 "$WORK/rtool.py" move $C/reconciliation.py $C/reconciliation_closed_world.py _REFUSE_DEPENDENCY_UNRESOLVED _REFUSE_DEPENDENCY_NOT_MERGED _REFUSE_DEPENDENCY_COVERS_MISSION_WORK _REFUSE_DEPENDENCY_MISSION_NAMESPACE _REFUSE_DEPENDENCY_RECORDED_TIP _REFUSE_DEPENDENCY_NO_WINDOW_BASE _REFUSE_DEPENDENCY_PROBE _REFUSE_DEPENDENCY_MOVED _collect_excluded ExternalDependencyAttribution _mission_spines _mission_work_reaches _recorded_lane_heads _mission_namespaces _mission_tip_shas _namespace_hit _recorded_work_hit _refused resolve_external_dependency_refs _verify_declared_ref dependency_refs_moved_refusal
```

     Expect `moved 21 symbol(s), 383 lines`.
  3. Add the one forward reference. Run this edit exactly (it fails loudly if the docstring line is not there exactly once):

```bash
python3 - <<'PY'
import pathlib
p = pathlib.Path("src/specify_cli/consolidation/reconciliation_closed_world.py")
s = p.read_text()
old = '    """Verify ONE declared ref: the refusal text, or ``(tip, window, blobs, deletions)``."""\n'
assert s.count(old) == 1
new = old + (
    "    # TEMPORARY FORWARD REFERENCE (moves in WP15): `_final_authored_walk` stays in reconciliation.py until the\n"
    "    # authorship slice moves, and a module-level import here would be circular. WP15 replaces this line with a\n"
    "    # top-level import from reconciliation_authorship.\n"
    "    from specify_cli.consolidation.reconciliation import _final_authored_walk\n\n"
)
p.write_text(s.replace(old, new))
PY
```

  4. Append `__all__` (`python3 "$WORK/rtool.py" exports reconciliation_closed_world`, "# 21 names.", copy only the `__all__` line), then:

```bash
uv run --frozen ruff check --select F,E9 $C/reconciliation_closed_world.py
uv run --frozen ruff format $C/reconciliation_closed_world.py
```

     Expect `All checks passed!`. Before step 3 the same check reports exactly one `F821 Undefined name _final_authored_walk`; that is the forward reference, and step 3 fixes it.
- **Notes**: `resolve_external_dependency_refs` and `dependency_refs_moved_refusal` are used by the claim orchestration (WP14) and the gate (via the facade); they stay importable from the facade. Never "improve" the forward reference into a module-level import.

### Subtask T061 – Move the approved bound to `reconciliation_bound.py`

- **Steps**:
  1. Create `$C/reconciliation_bound.py` containing **only** this header:

```python
"""The approved bound of the reconciliation gate (Mission consolidation-window-provenance-01M6Y84D, WP11).

The check that a code lane holds nothing beyond what review approved (#5668): the claim-time verdict,
the ``single_branch`` write-branch leg (S8, #7283), the public ``approved_bound_refusal`` entry point
and the gate-time lane-tip re-check. Moved verbatim out of ``reconciliation.py``; that module
re-exports every name, so no caller changes (C-005).
"""

from __future__ import annotations

import functools
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from specify_cli.consolidation.approved_bound import (
    BoundRefusal,
    BoundRefusalCode,
    approval_stamp,
    check_lane,
    commits_beyond,
    content_commits,
    render_refusals,
    resolves_commit,
)
from specify_cli.consolidation.git_probes import GitProbeError, resolve_commit
from specify_cli.consolidation.reconciliation_kernel import (
    _APPROVED_MEMBERSHIP_LANES,
    _ClaimEventLog,
    _closed_world_anchors,
    _is_bookkeeping,
    _lane_branch_for,
    _planning_prefix,
)
from specify_cli.lanes._git import branch_exists
from specify_cli.lanes.compute import is_planning_lane, lane_fully_canceled
from specify_cli.lanes.models import ExecutionLane, LanesManifest
```

  2. Move the 13 symbols and append `__all__`:

```bash
python3 "$WORK/rtool.py" move $C/reconciliation.py $C/reconciliation_bound.py _BoundVerdict _bound_events_unreadable_text _bound_claim_base_unresolved_text _bound_approved_wp_ids _bound_lanes _bound_claim_base approval_stamp_anchors _approved_bound_verdict _WriteBranchScope _bound_write_branch _write_branch_verdict approved_bound_refusal lane_tips_moved_refusal
python3 "$WORK/rtool.py" exports reconciliation_bound         # "# 13 names."; copy only the __all__ line to the end of the module
uv run --frozen ruff check --select F,E9 $C/reconciliation_bound.py
uv run --frozen ruff format $C/reconciliation_bound.py
```

     Expect `moved 13 symbol(s), 272 lines` and `All checks passed!`.
- **Notes**: `_BoundVerdict` and `_WriteBranchScope` are frozen dataclasses: the tool takes their decorators. The module imports `_ClaimEventLog`, `_closed_world_anchors`, `_is_bookkeeping`, `_lane_branch_for`, `_planning_prefix` and `_APPROVED_MEMBERSHIP_LANES` from the kernel, which is why WP10 had to come first.

### Subtask T062 – Facade re-exports, family tuple, import test, patch audit

- **Steps**:
  1. In `$C/reconciliation.py`, add the three re-export blocks directly above `logger = logging.getLogger(__name__)` (next to WP10's two blocks). Print them (use the part after `# Paste into reconciliation.py above ...`):

```bash
python3 "$WORK/rtool.py" exports reconciliation_rendering      # 11 names
python3 "$WORK/rtool.py" exports reconciliation_closed_world   # 21 names
python3 "$WORK/rtool.py" exports reconciliation_bound          # 13 names
```

  2. Find the imports the move made unused:

```bash
uv run --frozen ruff check --select F401,F811 --output-format json $C/reconciliation.py | python3 "$WORK/rtool.py" prune
```

     Expect 22 lines, all `delete`: `LaneTipListingError`, `read_tip` (twice: once as unused, once as the redefinition by a function-local import), `recorded_tip_branches`, `DEPENDENCY_REF_COVERS_MISSION_WORK`, `DEPENDENCY_REF_MOVED`, `DEPENDENCY_REF_UNREACHABLE`, `DEPENDENCY_REF_UNRESOLVED`, `DEPENDENCY_REF_UNVERIFIABLE`, `error_code_suffix`, `BoundRefusal`, `BoundRefusalCode`, `check_lane`, `commits_beyond`, `content_commits`, `render_refusals`, `resolves_commit`, `first_parent_commits_in_range`, `resolve_commit`, `ATTEST_FLAG`, `ATTEST_REASON_FLAG`, `stamp_of`. For any `KEEP-AS-ALIAS` line, first turn that import into `name as name` by hand (R3). Then:

```bash
uv run --frozen ruff check --select F401,F811 --fix $C/reconciliation.py
uv run --frozen ruff format $C/reconciliation.py $C/reconciliation_rendering.py $C/reconciliation_closed_world.py $C/reconciliation_bound.py
uv run --frozen ruff check $C/reconciliation.py $C/reconciliation_rendering.py $C/reconciliation_closed_world.py $C/reconciliation_bound.py
```

  3. Extend `tests/consolidation/reconciliation_family.py`: import `reconciliation_bound`, `reconciliation_closed_world` and `reconciliation_rendering` with the existing import line and append them to `RECONCILIATION_FAMILY`, after WP10's entries, in this order: `(reconciliation, reconciliation_kernel, reconciliation_claim_types, reconciliation_rendering, reconciliation_closed_world, reconciliation_bound)`.
  4. Extend `SPLIT_MODULES` in `tests/consolidation/test_reconciliation_module_imports.py` with `"reconciliation_rendering"`, `"reconciliation_closed_world"`, `"reconciliation_bound"`. The file must then report `6 passed`.
  5. **Patch audit (R4).** Run `python3 "$WORK/rtool.py" audit` from the repository root. Expect:

```text
commits_in_range                   looked up in: reconciliation, reconciliation_closed_world, reconciliation_kernel
path_state_at                      looked up in: reconciliation
merge_tree_write_tree_available    looked up in: reconciliation
resolve_canceled_wp                looked up in: reconciliation
attestation_stamps                 looked up in: reconciliation
OVERRIDABLE_REASONS                looked up in: reconciliation
canceled_spine_content             looked up in: reconciliation
_final_authored_walk               looked up in: reconciliation, reconciliation_closed_world
```

     No test needs a new retarget in WP11. `commits_in_range` is already patched through the family helper (WP10), so it now also reaches the closed-world module. `_final_authored_walk` shows `reconciliation_closed_world` only because of the function-local forward reference, which reads the facade's attribute at call time: the one test that patches it on the facade (`test_presence_lane_base.py`) behaves exactly as before. Do not change that test. If any other line differs, stop and ask.
  6. Run the moved-code proof (45 `same` lines expected, no `DIFFERS` or `MISSING`):

```bash
python3 "$WORK/rtool.py" check "$WORK/reconciliation.before.py" $C/reconciliation_rendering.py _RECOVERY_TAIL _ALSO_HAS _BOTH_NEEDED APPROVED_CONTENT_MISSING CANCELED_REACHABLE_VIA_DEPENDENCY _attest_tail _renamed_note _describe_canceled_content _describe_approved_content_missing _describe_canceled_reachable _join_refusals
python3 "$WORK/rtool.py" check "$WORK/reconciliation.before.py" $C/reconciliation_closed_world.py _REFUSE_DEPENDENCY_UNRESOLVED _REFUSE_DEPENDENCY_NOT_MERGED _REFUSE_DEPENDENCY_COVERS_MISSION_WORK _REFUSE_DEPENDENCY_MISSION_NAMESPACE _REFUSE_DEPENDENCY_RECORDED_TIP _REFUSE_DEPENDENCY_NO_WINDOW_BASE _REFUSE_DEPENDENCY_PROBE _REFUSE_DEPENDENCY_MOVED _collect_excluded ExternalDependencyAttribution _mission_spines _mission_work_reaches _recorded_lane_heads _mission_namespaces _mission_tip_shas _namespace_hit _recorded_work_hit _refused resolve_external_dependency_refs _verify_declared_ref dependency_refs_moved_refusal
python3 "$WORK/rtool.py" check "$WORK/reconciliation.before.py" $C/reconciliation_bound.py _BoundVerdict _bound_events_unreadable_text _bound_claim_base_unresolved_text _bound_approved_wp_ids _bound_lanes _bound_claim_base approval_stamp_anchors _approved_bound_verdict _WriteBranchScope _bound_write_branch _write_branch_verdict approved_bound_refusal lane_tips_moved_refusal
```

### Subtask T063 – Oracle gates and module sizes

- **Steps**: Run the whole "Definition of Done". Then `wc -l $C/reconciliation*.py` and record the sizes in the history note and the tracer file. Expect roughly: `reconciliation.py` 2,740, rendering 150, closed world 490, bound 355, kernel 335, claim types 335 (all under the 1,200-line ceiling, NFR-003).

## Test Strategy

No new behaviour, so the proof is the Phase 1/2 oracles (golden corpus, precedence matrix, surface pin with identity, patch-lookup guard, seeded mutations, intended-verdict and parity pins) with identical counts and a byte-identical golden file, plus `rtool.py check` (the moved text is unchanged). The import test (extended to 6 modules) proves no module-level cycle exists from any entry point.

## Definition of Done

Run these **exactly**, from the worktree root, and paste each final summary line into the history note. The reviewer reruns everything.

```bash
# 1. moved code is the same code: the three `rtool.py check` commands of T062 step 6 (45 `same`, nothing else)

# 2. no pinned file changed (run before every commit; must print nothing)
git diff --exit-code -- tests/consolidation/characterization/ tests/consolidation/reconciliation_surface.json tests/consolidation/test_reconciliation_seeded_mutations.py

# 3. exactly one forward reference, in the closed-world module, and none in the others
grep -n "consolidation.reconciliation import" $C/reconciliation_rendering.py $C/reconciliation_closed_world.py $C/reconciliation_bound.py $C/reconciliation_kernel.py $C/reconciliation_claim_types.py

# 4. the import test
uv run --frozen pytest -q tests/consolidation/test_reconciliation_module_imports.py
```

Step 3 must print exactly one line, in `reconciliation_closed_world.py`.

Then the Phase 1/2 oracle block (counts equal to your BEFORE run), then the six mutation rows by name:

```bash
uv run --frozen pytest -q tests/consolidation/test_reconciliation_characterization.py        # the golden verdict corpus (WP02)
uv run --frozen pytest -q tests/consolidation/test_refusal_precedence_matrix.py              # refusal order and text (WP03)
uv run --frozen pytest -q tests/consolidation/test_reconciliation_surface_pin.py tests/consolidation/test_reconciliation_family_guard.py   # names, identity, patch lookups (WP04)
uv run --frozen pytest -q -rxX tests/consolidation/test_reconciliation_intended_verdicts.py  # must report only xfailed (WP05)
uv run --frozen pytest -q tests/consolidation/test_reconciliation_seeded_mutations.py        # every mutation still turns its cell red (WP06)
uv run --frozen pytest -q -rxX tests/consolidation/test_claim_inputs_parity.py               # Phase 2 parity pins (WP09)
```

```bash
uv run --frozen pytest -q tests/consolidation/test_reconciliation_seeded_mutations.py -k "rendering or closed-world or external-dependency-refs or approved-bound or write-branch or lane-tip-recheck"
```

Then the blast radius:

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
uv run --frozen ruff check $C/reconciliation.py $C/reconciliation_rendering.py $C/reconciliation_closed_world.py $C/reconciliation_bound.py tests/consolidation/reconciliation_family.py tests/consolidation/test_reconciliation_module_imports.py
uv run --frozen ruff format --check --force-exclude $C/reconciliation.py $C/reconciliation_rendering.py $C/reconciliation_closed_world.py $C/reconciliation_bound.py tests/consolidation/reconciliation_family.py tests/consolidation/test_reconciliation_module_imports.py
uv run --frozen mypy $C/reconciliation.py $C/reconciliation_rendering.py $C/reconciliation_closed_world.py $C/reconciliation_bound.py tests/consolidation/reconciliation_family.py tests/consolidation/test_reconciliation_module_imports.py
make test-fast
```

Checklist:

- [ ] 45 `same` lines; no `DIFFERS` or `MISSING`.
- [ ] Golden file, surface pin JSON and mutation-table file untouched; oracle counts equal the BEFORE counts; the six mutation rows pass; intended-verdict file reports only `xfailed`.
- [ ] Exactly one `consolidation.reconciliation import` line in the new modules (the forward reference).
- [ ] `git diff --stat` shows only the facade, the three new modules, `reconciliation_family.py` and `test_reconciliation_module_imports.py` (plus tracer notes). No suppression, allowlist row, registry entry, changelog fragment or version change.
- [ ] Each new module declares `__all__`; the facade's own `__all__` still has its 10 names.
- [ ] `tests/ci/test_reducer_lock_census.py` and `tests/consolidation/test_single_rollback_authority.py` pass (C-009).
- [ ] **Base-relative zero-diff check** (NFR-001; post-tasks squad R-01): `WP_BASE` is the lane commit this WP started from. Record it in your first history note (`git rev-parse HEAD` before your first commit); the reviewer confirms `git log --oneline "$WP_BASE"..HEAD` lists only this WP's commits. Both must hold on the final commit: `git diff --exit-code "$WP_BASE" HEAD -- tests/consolidation/characterization/verdict_corpus.json` exits 0, and `uv run --frozen python -c "from tests.consolidation.characterization_support import changed_cells; print(changed_cells('$WP_BASE'))"` prints `[]`. (A plain `git diff --exit-code` compares only the working tree with the index and misses a committed regeneration.)
- [ ] **Tracer files** (canonical writer only, no hand edits of `traces/*.md`, no `add-history` fallback; post-tasks squad R-02): `spec-kitty agent tracer-append --mission consolidation-window-provenance-01M6Y84D --category design-decisions --actor "implement WP11" --entry "<summary>. <detail>"` for the forward reference and why, the `_refused` placement, module sizes; `--category tooling-friction` for any friction. The command works from any checkout (lane worktree included) and commits to the coordination surface itself.
- [ ] Never run `make test-full`. Never claim a command passed that you did not run.

## Risks & Mitigations

- **A second facade import creeping into a new module** (a cycle): the grep in the Definition of Done and the entry-first import test catch it.
- **A patch that intercepts less after the move**: R4 and the audit; the only two-module name is `commits_in_range`, already family-patched.
- **Deleting a pinned facade import**: R3; `rtool.py prune` and `test_every_pinned_name_is_importable`.
- **A function-local import hoisted** (by an editor or `--fix`): `rtool.py check` prints `DIFFERS`.
- **Reducer-lock census**: `approved_bound_refusal` imports `materialize_snapshot` inside the function; leave it there.

## Review Guidance

- Reviewer profile: `reviewer-renata` (Claude reviewer for a cheap-tier implementer).
- **Model tier: cheap** (implementer: TokenFactory glm-5.3; reviewer: Claude; orchestrator decision 2026-11-08: keep the cheap implementer, and the reviewer checks the judgment points below explicitly). Rerun every Definition-of-Done command yourself.
- **Reviewer focus (the judgment points a cheap-tier implementer can get wrong; check each explicitly):**
  1. The forward reference is exactly one marked function-local line in `_verify_declared_ref`, with the `# TEMPORARY FORWARD REFERENCE (moves in WP15)` comment; no module-level import of the facade exists in any new module.
  2. Helper homes match the orchestrator decision: `_attest_tail`, `_RECOVERY_TAIL`, `_join_refusals`, `_ALSO_HAS`, `_BOTH_NEEDED` are in `reconciliation_rendering.py`; `_refused` and `_collect_excluded` are in `reconciliation_closed_world.py` (not the kernel); `_collect_approved_shas` is **not** moved (WP14).
  3. Import direction holds: rendering imports only claim types; closed world and bound import the kernel (and rendering where needed), never each other's later siblings or the facade.
  4. The four function-local imports inside moved bodies (`_recorded_lane_heads`, `approved_bound_refusal`, `_bound_write_branch`, `_write_branch_verdict`) are still function-local; `tests/ci/test_reducer_lock_census.py` is green without an edit.
  5. Every pinned facade name that the move made unused is kept in alias form, not deleted; the facade `__all__` still has its 10 names.
  6. The family tuple holds the three new modules, and the seeded mutation rows for the moved checks still go red (not only "the corpus is green").
- Re-run the three `rtool.py check` commands against `git show <parent of the first WP11 commit>:src/specify_cli/consolidation/reconciliation.py`.
- **Record the spot-check outcome** (post-tasks squad R-15): put each spot-check command you ran and the cell keys that went red into the review note (`spec-kitty agent tasks add-history <WP> --note ...` or the review verdict text), so the check stays verifiable after the review.
- **Mutation spot-check on the moved code.** Back the module up, break one check in the new module, expect the corpus to go red, restore:
```bash
cp $C/reconciliation_bound.py /tmp/bound.good
python3 - <<'PY'
import pathlib
p = pathlib.Path("src/specify_cli/consolidation/reconciliation_bound.py")
s = p.read_text()
old = "    return sorted(covered, key=lambda lane: lane.lane_id)"
assert s.count(old) == 1
p.write_text(s.replace(old, "    return []"))
PY
uv run --frozen pytest -q tests/consolidation/test_reconciliation_characterization.py   # must FAIL
cp /tmp/bound.good $C/reconciliation_bound.py && git diff --exit-code $C/reconciliation_bound.py
```
  Repeat for `_collect_excluded` in the closed-world module (replace its last line `return frozenset(shas), frozenset(patch_ids)` with `return frozenset(), frozenset()`). A green corpus after a mutation means the family tuple or a facade alias is wrong.

## Progress & Status

- **Record a progress note**: `spec-kitty agent tasks add-history WP11 --note "<what you did>"`
- **Change WP status**: `spec-kitty agent tasks move-task WP11 --to <status>`
- **View history and status**: `spec-kitty agent tasks status --mission consolidation-window-provenance-01M6Y84D`
