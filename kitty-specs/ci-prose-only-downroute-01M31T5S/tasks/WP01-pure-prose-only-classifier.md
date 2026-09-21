---
work_package_id: WP01
title: Pure prose-only classifier
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-006
planning_base_branch: feat/ci-prose-only-downroute
merge_target_branch: feat/ci-prose-only-downroute
branch_strategy: Planning artifacts for this mission were generated on feat/ci-prose-only-downroute. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into feat/ci-prose-only-downroute unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-ci-prose-only-downroute-01M31T5S
base_commit: 1931f00a686a986a3f6ded4a1283e125221602e3
created_at: '2026-09-21T11:44:42.595663+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
history:
- created by /spec-kitty.tasks 2026-09-21
agent_profile: python-pedro
authoritative_surface: scripts/ci/
create_intent:
- scripts/ci/prose_only.py
- tests/ci/test_prose_only.py
execution_mode: code_change
owned_files:
- scripts/ci/prose_only.py
- tests/ci/test_prose_only.py
role: implementer
tags: []
tracker_refs: []
---

## ⚡ Do This First: Load Agent Profile

Before reading anything else, load your assigned profile so your identity,
boundaries, and governance scope are active:

```
/ad-hoc-profile-load python-pedro
```

Then proceed to the Objective.

## Objective

Create `scripts/ci/prose_only.py` — a **pure, fail-closed** predicate that decides
whether a Python file changed only in comments and docstrings — plus small
aggregate helpers. No filesystem, git, or network IO; no `yaml`/`fnmatch` import.
This is the foundation WP02 builds on; get the fail-closed cases exactly right.

Read `kitty-specs/ci-prose-only-downroute-01M31T5S/contracts/prose-only-classifier.md`
(the module + test contract) and `research.md` R4/R5 before coding.

## Context

`scripts/ci/gate_selection.py` is deliberately a pure path→group router and MUST
NOT be touched (that is WP02's guard too). This classifier is the *content* half,
kept as a separate module so `gate_selection.py` stays path-pure (#4842 F1/F2,
#2476 single authority). The classifier is called later from the CI workflows over
git base/head blobs; here it only takes two source strings.

## Subtasks

> **Adversarial-squad update (see research R10).** The pure module now classifies
> `.py` CONTENT only — the PR-level verdict (which needs path classification) moved
> to the WP02 wiring. Extra guards were added: whitespace-insensitive directive
> matching, an expanded directive set, encoding-cookie/shebang, and strict `body[0]`
> docstring stripping.

### T001 — Red-first test suite (`tests/ci/test_prose_only.py`)

Write the tests FIRST and watch them fail. Cover the full contract table in
`contracts/prose-only-classifier.md` (updated). At minimum:

- **True (prose-only)**: changed module/class/function docstring (no `>>>`); changed
  `#` comment; code reflowed but token-identical; BOM/CRLF/trailing-whitespace-only.
- **False (code)**: changed default (`def f(x=1)`→`x=2`); added statement/branch;
  changed non-docstring string literal (error text).
- **False (directive, R5/HIGH-4/LOW)**: changed `# type:`; **no-space `#type:`**;
  added/removed `# noqa` and `#noqa`; changed `# pragma: no cover`; `# fmt: off`
  added; `# ruff: noqa` added (note: does NOT contain the substring `# noqa`).
- **False (encoding/shebang, MEDIUM-1)**: changed `# -*- coding: … -*-`; changed
  `#!` shebang.
- **False (docstring precision, MEDIUM-2)**: an f-string first statement whose value
  changed; a bare string that is NOT `body[0]` (second statement) whose value changed.
- **False (doctest, R4)**: a docstring whose `>>>` example content changed.
- **False (fail-closed, FR-006)**: invalid-Python head (`SyntaxError`);
  `IndentationError`; `base_src=None` (new file); empty base.
- **`reduced_paths`**: drops a prose-only `.py`, keeps a code `.py` and any non-`.py`.

Assert the observable contract (the boolean + `reason`), not internals
(DIRECTIVE_041). The **no-space `#type:`** and the **f-string-first-statement** cases
are the load-bearing red-first regressions: each must fail a naive implementation
(substring match / strip-any-string-expr) and pass only once the guard is right.

### T002 — Implement `is_prose_only(base_src, head_src)` (guard order — HIGH-3)

Compute EVERY term below and AND them; there is **no early `return True`** before the
guards run, and every pass is inside one fail-closed try (any exception ⇒ False):

- Parse both sides `ast.parse(src, type_comments=True)`.
- `strip_docstrings`: remove ONLY `body[0]` when it is `Expr(Constant(str))` on
  `Module`/`ClassDef`/`FunctionDef`/`AsyncFunctionDef` — never a `JoinedStr`, a
  `BinOp`/implicit concat, a non-first bare string, or a string used as a value
  (MEDIUM-2).
- AST-equality term = `ast.dump(stripped, include_attributes=False)` equal on both.

### T003 — Directive / encoding / doctest guards (R4/R5, HIGH-4, MEDIUM-1, LOW)

- Tokenize both sides; **normalize** each comment (strip `#`, strip whitespace,
  lowercase leading keyword) before matching. Any multiset delta among comments whose
  normalized form begins with `type:`/`noqa`/`pragma`/`ruff:`/`fmt:`/`mypy:`/
  `pyright:`/`isort:` ⇒ `False` (`reason="type_comment"`/`"noqa_pragma"`/`"directive"`).
- Line-1/2 encoding cookie (`coding[:=]\s*[-\w.]+`) or `#!` shebang delta ⇒ `False`
  (`reason="encoding"`/`"shebang"`).
- Any *changed* docstring containing a `>>>` prompt ⇒ `False` (`reason="doctest"`).

### T004 — Pure reduction helper (verdict re-homed to WP02)

- `reduced_paths(changed, blob_getter)` → for each `.py`, drop it iff
  `is_prose_only(base, head)` is True; keep every non-`.py` path and every non-prose
  `.py`. Pure; `blob_getter(path) -> (base, head)`; classifies only `.py`.
- Do **NOT** implement a PR-level `pr_is_prose_only` here — the aggregate verdict
  needs doc/corpus/mapped-path classification, which belongs in the WP02 wiring
  behind `gate_selection` (research R9, squad HIGH-1). Keep `prose_only.py` free of
  `yaml`/`fnmatch`/IO.

### T005 — Quality gate

Run `ruff check scripts/ci/prose_only.py tests/ci/test_prose_only.py`,
`ruff format --check` on both, and `mypy scripts/ci/prose_only.py`. Zero issues,
zero new suppressions (NFR-003). Confirm no `import yaml` / `import fnmatch` and no
IO (NFR-001).

## Branch Strategy

Planning/base branch: `feat/ci-prose-only-downroute`. Final merge target:
`feat/ci-prose-only-downroute` (consolidated locally, then PR'd to `skupstream/main`
by the operator). The execution worktree is allocated per computed lane from
`lanes.json` — do not hand-construct it; enter via `spec-kitty implement WP01`.

## Definition of Done

- All contract cases in T001 pass; the no-space `#type:`, encoding/shebang,
  f-string-first-statement, and doctest guards are each proven by a test that fails
  without the guard.
- `is_prose_only` and `reduced_paths` implemented and pure (no PR-verdict here).
- ruff/format/mypy clean; no IO, no `yaml`/`fnmatch`; no early `return True`.
- `gate_selection.py` untouched.

## Risks / Reviewer guidance

- **Biggest risk**: a false "prose-only" on real code. Reviewer: try to construct a
  code change the classifier calls prose-only — especially around type comments,
  doctests, and string-valued (non-docstring) literals.
- Confirm `include_attributes=False` (line-insensitive) and `type_comments=True`
  (so `# type:` participates) — both are load-bearing.
