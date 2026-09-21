# Contract: prose-only classifier + routing wiring

## Module contract — `scripts/ci/prose_only.py` (NEW, pure)

```python
def is_prose_only(base_src: str | None, head_src: str | None) -> bool:
    """True iff head_src differs from base_src only in comments and docstrings.

    Pure: no filesystem, git, or network IO; no `yaml`/`fnmatch` import.
    Fail-closed: returns False on ANY uncertainty.
    """
```

**Behavioral requirements** — compute ALL of the following and AND them; there is
**no early `return True`** before the guards run (squad HIGH-3):

1. **Prose-only proof (FR-001, C-002)** — the AST-equality term is True only when:
   - both sides parse: `ast.parse(src, type_comments=True)` succeeds on each;
   - docstring-stripped dumps are equal:
     `ast.dump(strip_docstrings(tree), include_attributes=False)` equal on both
     sides (position-insensitive, so added comment lines do not diff);
   - `strip_docstrings` removes **only** `body[0]` when it is `Expr` whose `.value`
     is `Constant` with a `str` value, on `Module`/`ClassDef`/`FunctionDef`/
     `AsyncFunctionDef` — **never** a `JoinedStr` (f-string), a `BinOp`/implicit
     concatenation, a non-first bare string, or a string used as a value
     (squad MEDIUM-2).
2. **Directive-comment guard (FR-002, R5, squad HIGH-4/LOW)** — a `tokenize` pass
   collects every comment; each is **normalized** (strip leading `#`, strip
   surrounding whitespace, lowercase the leading keyword) before matching, so
   `#type:`, `#  type:`, `#noqa` are caught. Any multiset difference in the set of
   comments whose normalized form begins with `type:`, `noqa`, `pragma`, `ruff:`,
   `fmt:`, `mypy:`, `pyright:`, or `isort:` ⇒ term False. (`# type: ignore` is also
   caught independently via `Module.type_ignores` in the dump.)
3. **Encoding/shebang guard (FR-002, squad MEDIUM-1)** — a delta on line 1–2 in a
   source-encoding cookie (`coding[:=]\s*[-\w.]+`) or a leading `#!` shebang ⇒ term
   False.
4. **Doctest guard (R4)** — if any docstring that *changed* between sides contains
   a doctest prompt (`>>>`) on either side ⇒ term False (treated as code).
5. **Fail-closed (FR-006)** — `SyntaxError`, `IndentationError`, `tokenize` error,
   `ValueError`, a `None`/empty base (new file), an unfamiliar construct, or any
   other exception ⇒ return False. Every pass is inside the fail-closed guard so an
   error on either side yields False, never an escape. Never raise.

**Scope (squad HIGH-1 / R9)**: the per-file predicate (`is_prose_only` /
`prose_only_reason`) decides `.py` *content* only. It does NOT decide whether a
*path* is doc/corpus/mapped/unmapped. **Non-requirements**: the per-file
predicate does NOT fetch blobs, read the router YAML, import `yaml`, or know
about lanes — it never imports `fnmatch` either, and is a two-string predicate
(NFR-001).

`fnmatch` is imported exactly once in this module, inside the PR-level
`prose_only_pr_verdict` aggregate below (architect MINOR-2) — that function
still fetches no blobs and reads no router YAML itself; both the glob tuple
and the blob content are injected by the caller, so the module as a whole
stays IO-free even though it is no longer strictly a "two-string predicate"
module.

**Known residual — `__doc__`-as-runtime-data (intended boundary, not a bug)**: a
docstring-only edit is classified prose-only, but spec-kitty is a `typer` CLI whose
command `--help` text is *derived from the command's docstring*, so a docstring edit
is a real user-facing-output change that this classifier still routes off the code
matrix. This is deliberate — the classifier decides *content*, not *consumption*. The
help-text-drift subclass is covered elsewhere, not per-PR code shards: the always-on
docs lane runs `tests/docs/test_module_docstring_doc_refs.py` (#4849, the `docs/*.md`
doc-pointer subclass) and the doctest guard (R4) covers executable doctests; a plain
help-*wording* assertion (e.g. `tests/cli/**` asserting a command's `--help` string)
is caught by the nightly full run, not the down-routed matrix. A future agent seeing
a nightly-only help-text red should treat it as this documented boundary, not a
classifier defect. (Hardening this — a guard that any `tests/architectural`/prose-
reading test lives in an always-on lane — is a tracked follow-up, not part of this
mission.)

## Aggregate contract — reduction + verdict

**Updated (architect MINOR-2)**: the PR-level verdict aggregate was originally
re-implemented inline in the `prose-scan` job's heredoc (squad HIGH-1 / R9's
original ruling kept it out of `prose_only.py`), which left it covered only by
workflow string-assertions and never executed as a unit. It is now a second
pure, unit-tested function in `prose_only.py` — still not "the wiring": it
still takes its `doc_globs` and `blob_getter` as injected arguments, does no
git/yaml IO of its own, and `gate_selection`/router-YAML loading still happens
only in the workflow step (which passes in the already-resolved glob tuple):

- `reduced_paths(changed, blob_getter)` — a `prose_only.py` helper operating over
  the changed set: drop each `.py` for which `is_prose_only(base, head)` is True;
  keep every non-`.py` path and every non-prose `.py` unchanged. Pure (takes a
  `blob_getter`), classifies only `.py`.
- `prose_only_pr_verdict(paths, blob_getter, doc_globs)` — a `prose_only.py`
  function computing the PR verdict: True iff every changed path is either
  (a) a `.py` proven prose-only, or (b) a path matching one of the injected
  `doc_globs` (via `fnmatch`; the wiring resolves these from `gate_selection`'s
  `docs`/`corpus` filter groups) — AND at least one changed `.py` was
  prose-only. A changed path that is neither (config/packaging/unmapped-src/
  non-doc) ⇒ `False` (fail-closed; squad HIGH-1). The `prose-scan` job in
  `ci-router.yml` calls this function directly instead of re-implementing the
  aggregate inline.

**Invariant (corrected, R2)**: safety is structural in the wiring, not the
classifier — every down-routable `if:` keeps its existing gate ANDed with
`prose_only != 'true'`, so `prose_only` can only *subtract* an already-selected code
lane and can never defeat the FR-004 `unmatched` catch-all. `prose_only=true` is
NOT assumed to imply "no unmapped src"; the wiring simply cannot widen.

## Wiring contract — `ci-modules.yml`

- In the `changed-files` step (which already has `base`, `HEAD_SHA`, and runs
  `git diff`), after building the file list, replace it with `reduced_paths(...)`
  before it is handed to `select_modules`. Blob fetch: `git show <sha>:<path>`
  (base and head); a `git show` failure for a path ⇒ that path is NOT dropped
  (fail-closed — it stays in the list and routes normally).
- `select_modules` and `gate_selection.py` are unchanged (FR-007, C-001).

## Wiring contract — `ci-router.yml` (separate-job mechanism, squad F2/R9)

- Add a NEW job (e.g. `prose-scan`) that checks out, computes the PR verdict via
  the classifier + `gate_selection` path classification over `git diff` base..head,
  and exposes `outputs.prose_only`. It MUST be a separate job so the reference is
  `needs.prose-scan.outputs.prose_only` — invisible to `gate_selection.py`'s
  `_GROUP_REF = needs\.changes\.outputs\.(\w+)`, so `prose_only` is never parsed as a
  routing group and the SC-004 oracles stay green. `gate_selection.py` is untouched.
- `architectural-heavy`: add `prose-scan` to `needs:`; append
  `&& needs.prose-scan.outputs.prose_only != 'true'` to `if:`.
- every `tests-<code-group>` (merge/status/cli/…): same `needs:` + `if:` append.
- `tests-docs`: add `prose-scan` to `needs:`; `if:` becomes
  `needs.changes.outputs.docs == 'true' || needs.prose-scan.outputs.prose_only == 'true'`.
- `router-gate` terminal aggregator: add `prose-scan` to its `needs:` (it already
  treats an `if:`-skip as pass, so a skipped code lane still passes).
- The `changes` job and its `unmatched` compute step are UNTOUCHED.
- **degenerate-base fail-closed**: if base is the null SHA or the diff cannot be
  computed, `prose_only=false` (mirrors `selection-forced-full`).

## Wiring contract — `ci-aggregate.yml` (coverage honesty, squad F1 / FR-009)

- Before `diff-cover` scores the diff, exclude proven-prose-only `.py` from the
  scored diff patch (`critical.diff.patch` / the equivalent diff input), so there is
  no coverable changed line for those files — the same trivially-green path a
  docs-only PR takes. Do NOT alter the ≥90% threshold or the SELECTED-vs-UNSELECTED
  backfill logic; only shrink the scored diff by the prose-only files.
- Reuse the SAME classifier so the exclusion set is identical to WP02's reduction
  (single source of truth for "is this `.py` prose-only").

## Test contract

`tests/ci/test_prose_only.py` (unit, in-memory strings — NFR-001):

| Case | Input | Expect |
|------|-------|--------|
| docstring edit | same code, different module/func docstring (no `>>>`) | True |
| comment edit | same code, different `#` comment | True |
| whitespace/format inside code, tokens identical | reflowed but equal AST | True |
| changed default | `def f(x=1)` → `def f(x=2)` | False (`code_diff`) |
| added branch | extra `if` statement | False (`code_diff`) |
| non-docstring string literal | error message text changed | False (`code_diff`) |
| `# type:` change | `x = []  # type: list[int]` → `list[str]` | False (`type_comment`) |
| no-space `#type:` | `#type: list[int]` → `#type: list[str]` | False (whitespace-insensitive, HIGH-4) |
| `# noqa` change | added/removed `# noqa` / `#noqa` | False (`noqa_pragma`) |
| `# ruff:`/`# fmt:` change | `# fmt: off` added/removed | False (directive set, LOW) |
| `# pragma: no cover` removed | coverage directive delta | False (`noqa_pragma`) |
| encoding cookie change | `# -*- coding: utf-8 -*-` → `latin-1` | False (`encoding`, MEDIUM-1) |
| shebang change | `#!/usr/bin/env python3` → `python3.11` | False (`shebang`, MEDIUM-1) |
| doctest docstring change | docstring `>>>` example edited | False (`doctest`) |
| f-string first statement | first stmt `f"{go()}"` value changed | False (not a docstring, MEDIUM-2) |
| second-statement bare string | `x=1` then a changed bare string | False (not `body[0]`, MEDIUM-2) |
| parse error head | head is invalid Python | False (`parse_error`) |
| new file (no base) | `base_src=None` | False (`no_base`) |
| mixed docstring + code | one file docstring-only, another code | aggregate False |
| prose `.py` + config file | docstring edit + `pyproject.toml` change | aggregate False (non-doc non-`.py`, HIGH-1) |

Same file also unit-tests `prose_only_pr_verdict` directly (architect MINOR-2):
all-prose-`.py` set → True; a mixed prose+code `.py` set → False; a non-doc
non-`.py` path (e.g. `pyproject.toml`) → False; a doc-only set with no proven
prose `.py` → False (the "at least one" requirement); a `blob_getter` that
raises or returns `None` → False (fail-closed); an empty `paths` → False.

`tests/ci/test_ci_module_wiring.py` (extend):
- reduced-path list drops a proven prose-only `.py` and `select_modules` returns
  the empty/narrowed set; a mixed diff is not reduced.
- **golden**: pin the down-routed lane set (module matrix ✗, arch battery ✗, code
  shards ✗, tests-docs ✓, always-on ✓) — SC-001.

Architectural guards that MUST stay green (path purity, SC-004):
`tests/architectural/test_gate_selection_authority.py`,
`test_local_gate_parity.py`, `test_ci_integrity_oracle_nonvacuous.py`.
