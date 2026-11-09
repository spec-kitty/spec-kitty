---
work_package_id: WP12
title: Move the verifier
dependencies:
- WP11
requirement_refs:
- FR-019
- C-006
- NFR-001
- NFR-008
planning_base_branch: feat/consolidation-window-provenance
merge_target_branch: feat/consolidation-window-provenance
branch_strategy: Planning artifacts for this mission were generated on feat/consolidation-window-provenance. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into feat/consolidation-window-provenance unless the human explicitly redirects the landing branch.
subtasks:
- T064
- T065
- T066
- T067
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
- src/specify_cli/consolidation/reconciliation_verifier.py
execution_mode: code_change
model: glm-5.3
owned_files:
- src/specify_cli/consolidation/reconciliation.py
- src/specify_cli/consolidation/reconciliation_verifier.py
- tests/consolidation/reconciliation_family.py
- tests/consolidation/test_reconciliation_module_imports.py
- tests/consolidation/test_reconciliation.py
- tests/consolidation/test_canceled_dependency_attribution.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP12 – Move the verifier

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
- **Report progress**: `spec-kitty agent tasks add-history WP12 --note "..."`.

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`,````bash`

---

## Objectives & Success Criteria

You **move** code. You change **no behaviour**. This is the third of six sequential moves that split `src/specify_cli/consolidation/reconciliation.py` behind a re-exporting facade (WP10 to WP15; plan IC-11, IC-12). WP10 created the kernel and the claim types; WP11 created the rendering, closed-world and bound modules. WP12 moves the verifier, the largest single unit:

| New module | Symbols | Lines moved |
|---|---|---|
| `reconciliation_verifier.py` | 14: `VerifyStatus`, `Divergence` (whole, with its clause text and order), `VerifyResult`, `MergeOutcomeVerifier`, `is_legitimate_three_way_resolution`, `claim_integrity_refusal`, the helpers only they use, and the three refusal texts only the verifier uses | about 875 |

The facade gains one re-export block and shrinks to about 1,850 lines. The new module is about 965 lines, under the 1,200-line ceiling (NFR-003).

**Done means:**

1. `rtool.py check` prints `same` for all 14 moved symbols (FR-019, C-006).
2. Zero verdict change (NFR-001): the Phase 1/2 oracles give the same counts as before you started, with the golden file byte-identical, and the verifier mutation rows (`verifier-squash-axis`, `verifier-presence-axis`, `verifier-canceled-axis`) plus `canceled-dependency` still turn their cells red (NFR-008).
3. The facade still exports every moved name (C-005). `VerifyStatus`, `VerifyResult`, `MergeOutcomeVerifier` and `claim_integrity_refusal` are imported by `run_state.py`, `phase_gate.py`, `phase_claim.py`, `forecast.py` and others through the facade: none of them is edited.
4. Two test patches are retargeted (T066). Without them two existing tests go red, which is the patch-lookup hazard (R4) and is expected.
5. ruff, `ruff format --check --force-exclude` and mypy are clean on every touched file with no new suppression, allowlist row or registry entry (NFR-005, C-014).

**`claim_integrity_refusal` moves here, with the verifier (orchestrator decision, 2026-11-08).** `MergeOutcomeVerifier.verify` calls `claim_integrity_refusal(approved_wp_set)` (baseline `reconciliation.py:918`) and `claim_integrity_refusal` calls `MergeOutcomeVerifier._refusal_reason(claim)` (baseline `:2874`): the two call each other, so they must share a module. Its only other collaborator is `ApprovedWpCommitSet` (claim types, WP10). Moving it in this work package removes the import cycle instead of bridging it; WP14 does not move it again. The facade keeps it in `__all__` and re-exports it from `reconciliation_verifier`.

**One forward reference, and only one.** `_approved_content_divergence` calls `unmet_approved_content` (it moves with the presence slice in WP15). That module may not be imported at module level from here without a cycle, so T064 adds one function-local import from the facade, marked `# TEMPORARY FORWARD REFERENCE (moves in WP15)` (the same convention WP11 and WP14 use: one function-local import from the facade, marked with the work package that removes it; WP15 removes every such line and its durable test proves none is left). `rtool.py check` ignores exactly that kind of line. Add no other import of the facade.

**Do not:**

- Do not edit a moved body: not a typo, not dead code, not a complexity fix, not a function-local import. Function-local imports move with their function and stay function-local.
- Do not move any symbol that is not in your lists. Do not regenerate the golden file or the surface pin (never set `SPEC_KITTY_REGEN_VERDICT_CORPUS` or `SPEC_KITTY_REGEN_RECONCILIATION_SURFACE`); do not edit `tests/consolidation/characterization/verdict_corpus.json`, `tests/consolidation/reconciliation_surface.json` or `tests/consolidation/test_reconciliation_seeded_mutations.py`.
- Do not add a module to `CHURN_SURFACE_MODULES`, a row to `tests/architectural/dead_symbol_allowlist.yaml`, a `# noqa` / `# type: ignore`, a changelog fragment or a version bump. No `__init__.py` is created or touched.
- Do not touch `rollback.py`, `executor.py`, `phase_*.py`, `forecast.py` or any caller (C-009). Do not run `make test-full`.
- Do not move `unmet_approved_content` or anything else outside the list in T064. `MergeOutcomeVerifier._refusal_reason` is a static method of the class and moves with it; `claim_integrity_refusal` is in the list and moves too.
- The only test edits allowed are the two retargets in T066 and the one-line additions to the family tuple and to `SPLIT_MODULES`.

**If any expected output below differs** (a different unused-import list, a `DIFFERS` line, a red oracle, a golden-file diff, a third red test): **stop**, record the command and output with `spec-kitty agent tasks add-history WP12 --note "..."`, and ask the orchestrator. Never edit a test, a pin or the golden file to make it pass.

## Context & Constraints

- `kitty-specs/consolidation-window-provenance-01M6Y84D/plan.md`: IC-11, IC-12. `spec.md`: FR-019, FR-020, C-005, C-006, NFR-001, NFR-003, NFR-005, NFR-008. `research.md`: R-06, R-07, R-08.
- **Dependency analysis (done when this prompt was written).** Apart from the one forward reference, the verifier symbols (including `claim_integrity_refusal`, which reads only `MergeOutcomeVerifier._refusal_reason` and `ApprovedWpCommitSet`) reference only each other, the claim types (`ApprovedWpCommitSet`, `CanceledDependencyContent`, `MissingApprovedContent`), the kernel (`_is_bookkeeping`), the rendering module (`_RECOVERY_TAIL`, `_attest_tail`, `_describe_approved_content_missing`, `_describe_canceled_content`, `_describe_canceled_reachable`) and imported names. All of those exist after WP10 and WP11.
- **The patch hazard in this work package.** The verifier now looks up `merge_tree_write_tree_available` (through `is_legitimate_three_way_resolution`) and `path_state_at` (through `_canceled_dependency_divergence` and `_approved_content_divergence`) in its own module. Two tests patch those names on the facade, so after the move the patch replaces a facade binding that nothing looks up and the test fails:
  - `tests/consolidation/test_reconciliation.py::test_squash_fails_closed_when_merge_tree_write_tree_unavailable` (patches `merge_tree_write_tree_available`);
  - `tests/consolidation/test_canceled_dependency_attribution.py::test_verifier_step_noop_without_entries_refuses_without_window_base_and_on_probe_error` (patches `path_state_at`). This retarget belongs to WP12, because the verifier move is what breaks the patch (orchestrator decision, 2026-11-08). WP13 also owns this file, but only for the further canceled-slice retargets (`attestation_stamps`, `OVERRIDABLE_REASONS`, `canceled_spine_content`) its own move breaks.
  Both are retargeted through the family helper in T066. The `RECONCILIATION_FAMILY` helper patches every family module that binds the name, so the patch keeps intercepting exactly what it intercepted before.
- Both names are pinned by the surface pin (the tests patch them on the facade), so the facade must keep them importable even though it no longer uses them: T065 keeps them as alias re-exports (R3).
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

Shorthand: `C=src/specify_cli/consolidation`. WP10 and WP11 must already be merged into your worktree: confirm `$C/reconciliation_rendering.py` exists. First record the BEFORE results of the oracle block (see "Definition of Done") on the untouched tree; after your change the counts must be identical.

## Branch Strategy

- **Strategy**: Planning artifacts were generated on kitty/mission-consolidation-window-provenance-01M6Y84D; completed changes must merge into feat/consolidation-window-provenance.
- **Planning base branch**: feat/consolidation-window-provenance
- **Merge target branch**: feat/consolidation-window-provenance

> Populated by `finalize-tasks`. Execution worktrees are allocated per computed lane from `lanes.json`.

```bash
spec-kitty agent action implement WP12 --agent <name> --mission consolidation-window-provenance-01M6Y84D
```

## Subtasks & Detailed Guidance

### Subtask T064 – Move the verifier symbols to `reconciliation_verifier.py`

- **Steps**:
  1. Create `$C/reconciliation_verifier.py` containing **only** this header:

```python
"""The merge-outcome verifier of the reconciliation gate (Mission consolidation-window-provenance-01M6Y84D, WP12).

``VerifyStatus``, ``Divergence`` (whole, with its clause text and order), ``VerifyResult``,
``MergeOutcomeVerifier`` with the helpers only they use, and ``claim_integrity_refusal`` (it and
``MergeOutcomeVerifier`` call each other, so they share this module). Moved verbatim out of ``reconciliation.py``;
that module re-exports every name, so no caller changes (C-005, C-006).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from enum import Enum, auto
from pathlib import Path

from specify_cli.consolidation.git_probes import (
    GitProbeError,
    blob_id_at,
    changed_paths_in_range,
    changed_paths_of,
    commits_in_range,
    is_merge_commit,
    merge_own_changed_paths,
    merge_tree_write_tree_available,
    patch_id_of,
    patch_ids_in_range,
    path_state_at,
    sha_reachable_from,
    three_way_merge_blob,
)
from specify_cli.consolidation.reconciliation_claim_types import ApprovedWpCommitSet, CanceledDependencyContent, MissingApprovedContent
from specify_cli.consolidation.reconciliation_kernel import _is_bookkeeping
from specify_cli.consolidation.reconciliation_rendering import (
    _RECOVERY_TAIL,
    _attest_tail,
    _describe_approved_content_missing,
    _describe_canceled_content,
    _describe_canceled_reachable,
)
from specify_cli.consolidation.wp_attribution import CanceledPathState
```

  2. Move the 14 symbols (the three `_REFUSE_*` texts keep the comment blocks above them):

```bash
python3 "$WORK/rtool.py" move $C/reconciliation.py $C/reconciliation_verifier.py VerifyStatus _RESTORE_IN_PROGRESS Divergence VerifyResult _with_attribution_hint _merge_canceled_content_into_result _fold_divergence _refuse_merged_independent_change MergeOutcomeVerifier is_legitimate_three_way_resolution _REFUSE_EMPTY_AUTHORED_BLOBS _REFUSE_NO_AUTHORSHIP_AUTHORITY _REFUSE_WINDOW_BASE_UNRESOLVED claim_integrity_refusal
```

     Expect `moved 14 symbol(s), 875 lines` (give or take a line of comment). Before the next step, `uv run --frozen ruff check --select F,E9 $C/reconciliation_verifier.py` reports exactly one `F821`: `unmet_approved_content`. That is the forward reference. (`claim_integrity_refusal` is now defined in this module, so `verify` resolves it locally.)
  3. Add the one forward reference. Run this edit exactly (it fails loudly if a target is not found exactly once):

```bash
python3 - <<'PY'
import pathlib
p = pathlib.Path("src/specify_cli/consolidation/reconciliation_verifier.py")
s = p.read_text()

b = '        executor, exactly like every other divergence.\n        """\n        if not claim.enforce_closed_world or not claim.approved_lane_content:'
assert s.count(b) == 1
s = s.replace(b, (
    "        executor, exactly like every other divergence.\n"
    '        """\n'
    "        # TEMPORARY FORWARD REFERENCE (moves in WP15): `unmet_approved_content` stays in reconciliation.py until the\n"
    "        # authorship + presence slice moves. WP15 replaces this line with a top-level import from reconciliation_authorship.\n"
    "        from specify_cli.consolidation.reconciliation import unmet_approved_content\n\n"
    "        if not claim.enforce_closed_world or not claim.approved_lane_content:"
))
p.write_text(s)
PY
```

  4. Append `__all__` (`python3 "$WORK/rtool.py" exports reconciliation_verifier`, "# 14 names.", copy only the `__all__` line to the end of the module), then:

```bash
uv run --frozen ruff check --select F,E9 $C/reconciliation_verifier.py
uv run --frozen ruff format $C/reconciliation_verifier.py
```

     Expect `All checks passed!`.
- **Notes**: `Divergence.describe` calls the `_describe_*` helpers; they come from the rendering module (WP11). Keep `Divergence` and `VerifyResult` whole (C-006).

### Subtask T065 – Facade re-exports and the family tuple

- **Steps**:
  1. Print the facade block and paste it directly above `logger = logging.getLogger(__name__)` (use the part after `# Paste into reconciliation.py above ...`):

```bash
python3 "$WORK/rtool.py" exports reconciliation_verifier      # 14 names
```

  2. Find the imports the move made unused:

```bash
uv run --frozen ruff check --select F401,F811 --output-format json $C/reconciliation.py | python3 "$WORK/rtool.py" prune
```

     Expect 9 lines: `replace`, `Enum`, `auto`, `changed_paths_in_range`, `merge_own_changed_paths`, `merge_tree_write_tree_available`, `patch_ids_in_range`, `path_state_at`, `three_way_merge_blob`. `merge_tree_write_tree_available` and `path_state_at` must read `KEEP-AS-ALIAS` (the surface pin lists them); the other seven read `delete`. Turn the two pinned imports into `merge_tree_write_tree_available as merge_tree_write_tree_available` and `path_state_at as path_state_at` **by hand first**, then delete the rest:

```bash
uv run --frozen ruff check --select F401,F811 --fix $C/reconciliation.py
uv run --frozen ruff format $C/reconciliation.py $C/reconciliation_verifier.py
uv run --frozen ruff check $C/reconciliation.py $C/reconciliation_verifier.py
```

     The last command must print `All checks passed!`.
  3. Extend `tests/consolidation/reconciliation_family.py`: import `reconciliation_verifier` with the existing import line and append it to `RECONCILIATION_FAMILY` after WP11's entries.
  4. Extend `SPLIT_MODULES` in `tests/consolidation/test_reconciliation_module_imports.py` with `"reconciliation_verifier"`; the file must then report `7 passed`.

### Subtask T066 – Retarget the two patches

- **Steps**: Run `python3 "$WORK/rtool.py" audit` from the repository root. Expect:

```text
commits_in_range                   looked up in: reconciliation, reconciliation_closed_world, reconciliation_kernel, reconciliation_verifier
path_state_at                      looked up in: reconciliation_verifier
merge_tree_write_tree_available    looked up in: reconciliation_verifier
resolve_canceled_wp                looked up in: reconciliation
attestation_stamps                 looked up in: reconciliation
OVERRIDABLE_REASONS                looked up in: reconciliation
canceled_spine_content             looked up in: reconciliation
_final_authored_walk               looked up in: reconciliation, reconciliation_closed_world
```

  Two names are no longer looked up in the facade at all. Make exactly these edits:

  1. `tests/consolidation/test_reconciliation.py`: add `from tests.consolidation.reconciliation_family import setattr_reconciliation_family` after the line `from tests.terminus.conftest import record_evidence_prerequisites`, and replace
     `monkeypatch.setattr("specify_cli.consolidation.reconciliation.merge_tree_write_tree_available", lambda _repo_root: False)`
     with
     `setattr_reconciliation_family(monkeypatch, "merge_tree_write_tree_available", lambda _repo_root: False)`.
  2. `tests/consolidation/test_canceled_dependency_attribution.py`: add the same import line before `from tests.terminus.canceled_dependency_support import (`, and replace
     `monkeypatch.setattr(f"{_RECONCILIATION}.path_state_at", boom)`
     with
     `setattr_reconciliation_family(monkeypatch, "path_state_at", boom)`.
     Leave the other `{_RECONCILIATION}` patches in that file alone: `attestation_stamps`, `OVERRIDABLE_REASONS` and `canceled_spine_content` are still looked up in the facade until WP13, and `_RECONCILIATION` is still used by them.
  3. Re-run the audit: nothing changes. Then the two tests (and their files) must pass:

```bash
uv run --frozen pytest -q tests/consolidation/test_reconciliation.py tests/consolidation/test_canceled_dependency_attribution.py tests/consolidation/test_reconciliation_family_guard.py
```

- **Notes**: The family guard (WP04) fails if a string patch still names a facade name the facade no longer looks up; it is your safety net for any patch I did not list. If it names a third test, stop and ask.

### Subtask T067 – Oracle gates and module size

- **Steps**: Run `python3 "$WORK/rtool.py" check "$WORK/reconciliation.before.py" $C/reconciliation_verifier.py VerifyStatus _RESTORE_IN_PROGRESS Divergence VerifyResult _with_attribution_hint _merge_canceled_content_into_result _fold_divergence _refuse_merged_independent_change MergeOutcomeVerifier is_legitimate_three_way_resolution _REFUSE_EMPTY_AUTHORED_BLOBS _REFUSE_NO_AUTHORSHIP_AUTHORITY _REFUSE_WINDOW_BASE_UNRESOLVED claim_integrity_refusal` (14 `same`), then the whole "Definition of Done". Record `wc -l $C/reconciliation*.py` in the history note and the tracer file. Expect roughly: `reconciliation.py` 1,850, verifier 965, closed world 490, bound 355, kernel 335, claim types 335, rendering 150.

## Test Strategy

No new behaviour, so the proof is the Phase 1/2 oracles with identical counts and a byte-identical golden file, `rtool.py check` (the moved text is unchanged) and the retargeted tests. The verifier mutation rows prove each axis is still reachable by the corpus after the move. The entry-first import test (now 7 modules) proves no module-level cycle.

## Definition of Done

Run these **exactly**, from the worktree root, and paste each final summary line into the history note. The reviewer reruns everything.

```bash
# 1. moved code is the same code (14 `same`, nothing else)
python3 "$WORK/rtool.py" check "$WORK/reconciliation.before.py" $C/reconciliation_verifier.py VerifyStatus _RESTORE_IN_PROGRESS Divergence VerifyResult _with_attribution_hint _merge_canceled_content_into_result _fold_divergence _refuse_merged_independent_change MergeOutcomeVerifier is_legitimate_three_way_resolution _REFUSE_EMPTY_AUTHORED_BLOBS _REFUSE_NO_AUTHORSHIP_AUTHORITY _REFUSE_WINDOW_BASE_UNRESOLVED claim_integrity_refusal

# 2. no pinned file changed (run before every commit; must print nothing)
git diff --exit-code -- tests/consolidation/characterization/ tests/consolidation/reconciliation_surface.json tests/consolidation/test_reconciliation_seeded_mutations.py

# 3. exactly one forward reference in the verifier module (`unmet_approved_content`), none elsewhere in the new modules besides WP11's one in the closed-world module
grep -n "consolidation.reconciliation import" $C/reconciliation_verifier.py $C/reconciliation_closed_world.py $C/reconciliation_bound.py $C/reconciliation_rendering.py $C/reconciliation_kernel.py $C/reconciliation_claim_types.py

# 4. the import test
uv run --frozen pytest -q tests/consolidation/test_reconciliation_module_imports.py
```

Step 3 must print exactly two lines: one in `reconciliation_verifier.py` (the `unmet_approved_content` import T064 adds) and one in `reconciliation_closed_world.py` (WP11's). The two comment lines T064 adds above the import do not match the pattern. If you see any other count, stop and ask; never add or remove an import to make the count match (post-tasks squad R-04).

Then the Phase 1/2 oracle block (counts equal to your BEFORE run), then the verifier rows by name:

```bash
uv run --frozen pytest -q tests/consolidation/test_reconciliation_characterization.py        # the golden verdict corpus (WP02)
uv run --frozen pytest -q tests/consolidation/test_refusal_precedence_matrix.py              # refusal order and text (WP03)
uv run --frozen pytest -q tests/consolidation/test_reconciliation_surface_pin.py tests/consolidation/test_reconciliation_family_guard.py   # names, identity, patch lookups (WP04)
uv run --frozen pytest -q -rxX tests/consolidation/test_reconciliation_intended_verdicts.py  # must report only xfailed (WP05)
uv run --frozen pytest -q tests/consolidation/test_reconciliation_seeded_mutations.py        # every mutation still turns its cell red (WP06)
uv run --frozen pytest -q -rxX tests/consolidation/test_claim_inputs_parity.py               # Phase 2 parity pins (WP09)
```

```bash
uv run --frozen pytest -q tests/consolidation/test_reconciliation_seeded_mutations.py -k "verifier-squash-axis or verifier-presence-axis or verifier-canceled-axis or canceled-dependency"
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
uv run --frozen ruff check $C/reconciliation.py $C/reconciliation_verifier.py tests/consolidation/reconciliation_family.py tests/consolidation/test_reconciliation_module_imports.py tests/consolidation/test_reconciliation.py tests/consolidation/test_canceled_dependency_attribution.py
uv run --frozen ruff format --check --force-exclude $C/reconciliation.py $C/reconciliation_verifier.py tests/consolidation/reconciliation_family.py tests/consolidation/test_reconciliation_module_imports.py tests/consolidation/test_reconciliation.py tests/consolidation/test_canceled_dependency_attribution.py
uv run --frozen mypy $C/reconciliation.py $C/reconciliation_verifier.py tests/consolidation/reconciliation_family.py tests/consolidation/test_reconciliation_module_imports.py
make test-fast
```

Checklist:

- [ ] 14 `same` lines; no `DIFFERS` or `MISSING`.
- [ ] Golden file, surface pin JSON and mutation-table file untouched; oracle counts equal the BEFORE counts; the four mutation rows pass; intended-verdict file reports only `xfailed`.
- [ ] The grep prints exactly two forward-reference lines: the one `unmet_approved_content` import in the verifier module and WP11's one in the closed-world module. No `claim_integrity_refusal` import of the facade exists anywhere.
- [ ] The facade still binds `merge_tree_write_tree_available` and `path_state_at` (alias form); the two retargeted tests pass; no other test file changed.
- [ ] `git diff --stat` shows only: the facade, `reconciliation_verifier.py`, `reconciliation_family.py`, `test_reconciliation_module_imports.py`, `test_reconciliation.py`, `test_canceled_dependency_attribution.py` (plus tracer notes). No suppression, allowlist row, registry entry, changelog fragment or version change.
- [ ] `__all__` declared in the new module; the facade's own `__all__` still has its 10 names.
- [ ] `tests/consolidation/test_single_rollback_authority.py` passes (C-009).
- [ ] **Base-relative zero-diff check** (NFR-001; post-tasks squad R-01): `WP_BASE` is the lane commit this WP started from. Record it in your first history note (`git rev-parse HEAD` before your first commit); the reviewer confirms `git log --oneline "$WP_BASE"..HEAD` lists only this WP's commits. Both must hold on the final commit: `git diff --exit-code "$WP_BASE" HEAD -- tests/consolidation/characterization/verdict_corpus.json` exits 0, and `uv run --frozen python -c "from tests.consolidation.characterization_support import changed_cells; print(changed_cells('$WP_BASE'))"` prints `[]`. (A plain `git diff --exit-code` compares only the working tree with the index and misses a committed regeneration.)
- [ ] **Tracer files** (canonical writer only, no hand edits of `traces/*.md`, no `add-history` fallback; post-tasks squad R-02): `spec-kitty agent tracer-append --mission consolidation-window-provenance-01M6Y84D --category design-decisions --actor "implement WP12" --entry "<summary>. <detail>"` for `claim_integrity_refusal` moved with the verifier, the one forward reference and who removes it, the `path_state_at` retarget landing here, module sizes; `--category tooling-friction` for any friction. The command works from any checkout (lane worktree included) and commits to the coordination surface itself.
- [ ] Never run `make test-full`. Never claim a command passed that you did not run.

## Risks & Mitigations

- **A third patch going vacuous**: the family guard fails on it; stop and ask rather than guessing a retarget.
- **Deleting a pinned facade import** (`path_state_at`, `merge_tree_write_tree_available`): R3; `rtool.py prune` marks them and `test_every_pinned_name_is_importable` fails otherwise.
- **A forward reference turned into a module-level import**: an import cycle; the grep and the entry-first import test catch it.
- **Method bodies edited in passing** (the class is 540 lines): `rtool.py check` compares the whole class AST.
- **Wrong order of forward-reference edits**: each target string must occur exactly once; the edit script asserts it.

## Review Guidance

- Reviewer profile: `reviewer-renata` (Claude reviewer for a cheap-tier implementer).
- **Model tier: cheap** (implementer: TokenFactory glm-5.3; reviewer: Claude). Rerun every Definition-of-Done command yourself.
- Check the one forward-reference line is the only difference from the old code (`rtool.py check` hides it, so read it once) and that WP15 is named in its comment.
- **Reviewer focus (the judgment points a cheap-tier implementer can get wrong; check each explicitly):**
  1. `claim_integrity_refusal` sits in `reconciliation_verifier.py` next to `MergeOutcomeVerifier`, its body unchanged, and the facade re-exports it in alias form; `phase_claim.py` and `forecast.py` are not edited.
  2. No module-level import of the facade, of `reconciliation_claim` or of `reconciliation_authorship` exists in the verifier module (the entry-first import test reports `7 passed`).
  3. The two retargeted patches use `setattr_reconciliation_family`, and each was proven live (the fake reached) rather than merely green.
  4. The pinned facade imports `merge_tree_write_tree_available` and `path_state_at` were kept in alias form, not deleted; the other seven unused imports were deleted.
  5. `test_canceled_dependency_attribution.py` changed in exactly one patch line plus one import; its other `{_RECONCILIATION}` patches are untouched (WP13's).
  6. Function-local imports inside moved bodies stayed function-local; no body was "tidied".
- **Record the spot-check outcome** (post-tasks squad R-15): put each spot-check command you ran and the cell keys that went red into the review note (`spec-kitty agent tasks add-history <WP> --note ...` or the review verdict text), so the check stays verifiable after the review.
- **Mutation spot-check on the moved code.** Back the module up, break one axis, expect the corpus to go red, restore:
```bash
cp $C/reconciliation_verifier.py /tmp/verifier.good
python3 - <<'PY'
import pathlib
p = pathlib.Path("src/specify_cli/consolidation/reconciliation_verifier.py")
s = p.read_text()
old = "        return any(not self._is_bookkeeping_path(path, claim) for path in paths)"
assert s.count(old) == 1
p.write_text(s.replace(old, "        return False"))
PY
uv run --frozen pytest -q tests/consolidation/test_reconciliation_characterization.py   # must FAIL
cp /tmp/verifier.good $C/reconciliation_verifier.py && git diff --exit-code $C/reconciliation_verifier.py
```
  A green corpus after a mutation means the family tuple or a facade alias is wrong.

## Progress & Status

- **Record a progress note**: `spec-kitty agent tasks add-history WP12 --note "<what you did>"`
- **Change WP status**: `spec-kitty agent tasks move-task WP12 --to <status>`
- **View history and status**: `spec-kitty agent tasks status --mission consolidation-window-provenance-01M6Y84D`
