# Design Decisions

> Capture the rationale that would otherwise evaporate.

**Prompting questions**
- What decision was made?
- What alternatives were considered?
- What was the rationale — why this option over the others?

---

## Entries

<!-- YYYY-MM-DD — Decision: [what]. Alternatives: [what else]. Rationale: [why this one]. -->

2026-09-21 — Decision: content-detection lives in a NEW pure module (`scripts/ci/prose_only.py`) plus workflow wiring, NOT inside `gate_selection.py`. Alternatives: (a) add blob-fetching branch inside `gate_selection.select_gates` as the issue's prose suggested. Rationale (#4842 F1/F2): `gate_selection.py` is deliberately a pure function of a path list, reused by the WP17 completeness oracle and WP18 local parity with synthetic probe paths that have no git blobs; injecting IO there breaks the #2476 single-authority invariant and its arch guards. The `ci-modules.yml` changed-files step already has base+HEAD and runs `git diff`, so blob access belongs there.

2026-09-21 — Decision: the classifier parses both sides with `type_comments=True` and compares the type-comment token set in addition to the docstring-stripped `ast.dump(include_attributes=False)`. Alternatives: bare AST compare (the issue's stated mechanism). Rationale (#4842 F3): default `ast.parse` discards `# type:` comments, so a bare AST compare returns identical trees for a changed type comment → false "prose-only" → mypy skipped on a real type change. The classifier must treat `# type:`/`# noqa`/`# pragma` deltas as code. This is the load-bearing fail-closed hole.

2026-09-21 — Decision (post-tasks adversarial squad, operator-approved): a proven prose-only `.py` is treated as "not code for CI" UNIFORMLY across THREE surfaces, not two. Paula F1 found the missed third surface: `ci-aggregate.yml`'s diff-cover ≥90% gate backfills an unselected module's coverage from a stale run, so skipping a docstring-changed module's shard makes its changed docstring lines read as uncovered → false-red on a docstring PR (violates #4437 honesty). Alternatives: (A) safe-partial — keep the module matrix, only down-route the arch battery; (B) full+honest — also exclude prose-only `.py` from the diff-cover diff patch. Operator chose B: a prose-only `.py` gets the same treatment a docs-only PR already gets (no coverable diff), so ~90% of the fan-out is saved without a coverage false-red.

2026-09-21 — Decision (squad Paula F2, autonomous): expose `prose_only` from a SEPARATE job (not the `changes` job), so `gate_selection.py`'s `_GROUP_REF = needs\.changes\.outputs\.(\w+)` never captures it as a phantom routing group. Alternatives: edit the gate_selection oracle to exempt a control output (would touch the single-authority surface / break FR-007). Rationale: a `needs.<other-job>.outputs.prose_only` reference is invisible to the changes-group regex, so the SC-004 oracles stay green and gate_selection.py stays untouched.

2026-09-21 — Decision (squad Renata HIGH-1 + Paula F3, autonomous): the pure classifier classifies `.py` content ONLY. It does NOT self-classify doc/corpus/unmapped-src paths (a pure helper cannot, without re-encoding the path map — the #2476/C-001 hazard). research R2's claim ("unmapped src is never proven-prose") was FALSE and is retracted. Safety is re-homed to the wiring: the workflow step reuses `gate_selection` for path classification, and keeps the FR-004 `unmatched_src` catch-all ANDed so `prose_only` can only SUBTRACT an already-selected code lane, never defeat the catch-all.

2026-09-21 — Decision (squad Renata HIGH-3/4 + MEDIUM-1/2, autonomous): classifier hardening — (HIGH-3) never `return True` before the tokenize+doctest guards run; compute AST-equality AND guards, then AND. (HIGH-4) normalize each comment (strip `#`, strip whitespace, lowercase keyword) before matching `type:`/`noqa`/`pragma` so `#type:`/`#noqa` no-space spellings are caught. (MEDIUM-1) a delta in a line-1/2 encoding cookie (`coding[:=]`) or shebang (`#!`) ⇒ not prose. (MEDIUM-2) strip ONLY `body[0]` that is `Expr(Constant(str))` on Module/Class/FunctionDef — never a `JoinedStr`, a `BinOp`, or a non-first bare string. Also add `# ruff:`/`# fmt:`/`# mypy:`/`# pyright:`/`# isort:` to the guarded-directive set for defense-in-depth.

2026-09-21 — Residual risk logged (squad Renata HIGH-2): a docstring is a runtime `__doc__` object; the down-route is safe only if no CODE-SHARD test asserts on docstring-derived output (only the docs lane, forced on, and doctests, fail-closed, are mitigated). WP will grep the suite for `__doc__`/`getdoc` assertions and document the residual if any live in a code shard.

2026-09-21 — Decision (brownfield, planning R1): the wiring spans TWO workflows, not one. `ci-modules.yml` routes via a Python `select_modules(path list)` (reducible), but `ci-router.yml` routes via `dorny/paths-filter` (content-blind Action) and is where the arch battery + docs lane live. Alternatives: reduce the ci-modules list only (my own F2 framing). Rationale: reducing the ci-modules list alone leaves the arch battery and per-group shards (ci-router.yml) running and the docs lane skipped — the inversion unfixed. So `ci-router.yml`'s `changes` job must emit a `prose_only` output consumed by the arch-battery/code-shard `if:` (subtract) and the tests-docs `if:` (add). Caught during planning brownfield inspection, before implement.

2026-09-21 — Decision (brownfield, planning R4): a docstring containing a `>>>` doctest prompt whose content changed is treated as CODE (not prose-only). Alternatives: (a) add a dedicated doctest lane to the down-route set; (b) ignore doctests. Rationale: tests/docs has no doctest runner; doctests execute (if anywhere) inside the module matrix the down-route skips, so ignoring them would skip a changed doctest. Failing closed on doctest-bearing docstring changes is narrow, provable, and needs no new lane — same philosophy as the # type: guard.

2026-09-21 — Decision: the down-route POSITIVELY enables the docs/help-drift/doctest lane, it does not merely drop the prose-only `.py` from the path list. Alternatives: subtract-only (drop the path, let selection fall out). Rationale (#4842 F4): `tests-docs` is gated on `docs/**`; a docstring change in `src/**.py` never touches `docs/**`, so subtraction alone leaves the docs lane skipped — reproducing the exact inversion the issue exists to fix. lint/format/terminology/layer-rules/regen-check are already always-on, so those need no action.

























