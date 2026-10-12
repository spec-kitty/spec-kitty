# Diagnosis — Gate D over-match (#6096)

**Mission**: `dead-path-docs-gate-anchor-01M4RJTJ`
**Date**: 2026-10-12
**Author**: planner-priti / claude (grounded on `origin/main` @ `8a911083`)

## 1. The matching mechanism and why it over-matches

Gate D is `tests/architectural/test_dead_builtin_doc_paths.py::test_no_live_doc_names_a_pre_move_builtin_path`.
It enforces that no **live** doc under `docs/` points at a retired top-level
built-in home by feeding `_MOVED_BUILTIN_DOC_RE` to `git grep -nE`:

```python
_MOVED_BUILTIN_DOC_RE = r"src/charter/offering/[a-z_]+/built-in|src/charter/offering/[a-zA-Z0-9_.-]*\.graph\.yaml"
subprocess.run(["git", "grep", "-nE", _MOVED_BUILTIN_DOC_RE, "--", "docs", *_GUARD_DOC_EXCLUSIONS], ...)
# returncode 0 == matches found (dead refs present); 1 == clean.
```

`git grep -E` matches the pattern as an **unanchored substring**: BRE/ERE under
`git grep` has no look-behind, and the pattern has **no left boundary**. So any
longer path whose tail is `…/src/charter/offering/<kind>/built-in` (or
`…/src/charter/offering/*.graph.yaml`) matches as if it named the retired
**top-level** `src/charter/offering/…` path. The gate therefore treats any
`…/src/…` occurrence as a top-level `src/` reference — a false-positive /
precision defect (no functional/product impact).

## 2. Red-first demonstration (the defect, witnessed on the current regex)

A synthetic `docs/` tree with one genuine top-level reference and three tails
(a `packs/.../src/...` path, an absolute `/home/runner/.../src/...` path, and a
`.../blob/main/src/...graph.yaml` URL), scanned with the **current** regex:

```
$ RE='src/charter/offering/[a-z_]+/built-in|src/charter/offering/[a-zA-Z0-9_.-]*\.graph\.yaml'
$ git grep -nE "$RE" -- docs
docs/absolute_tail.md:1:Absolute runner path: /home/runner/work/spec-kitty/spec-kitty/src/charter/offering/foo/built-in
docs/genuine_toplevel.md:1:See src/charter/offering/foo/built-in for the retired home.
docs/nested_tail.md:1:The pack content lives at packs/internal/x/src/charter/offering/foo/built-in today.
docs/url_tail.graph.md:1:URL tail: https://github.com/spec-kitty/spec-kitty/blob/main/src/charter/offering/foo.graph.yaml
grep exit: 0
```

All four match. Only `genuine_toplevel.md` **should** — the other three are the
defect (false positives).

## 3. The fix, witnessed to be correct in both directions

Prepend an explicit left-boundary alternation (issue #6096 option a) — admit a
match only at start-of-line or after a non-path, non-word character:

```
(^|[^A-Za-z0-9_./-])(src/charter/offering/[a-z_]+/built-in|src/charter/offering/[a-zA-Z0-9_.-]*\.graph\.yaml)
```

Against the same tree (plus line-start / space / quote / markdown-link `(`
positive controls):

```
$ git grep -nE "$RE_FIX" -- docs
docs/atstart.md:2:src/charter/offering/qux/built-in
docs/genuine_toplevel.md:1:See src/charter/offering/foo/built-in for the retired home.
docs/mdlink.md:1:[link](src/charter/offering/baz.graph.yaml)
docs/quoted.md:1:edit "src/charter/offering/bar/built-in" now
```

The three tails are dropped; every genuine top-level reference (line-start,
space-, quote-, and markdown-link-`(`-preceded) is still caught. `/`-preceded
tails are rejected, which matches #6096's intent: blob-URL / nested-literal
`src/` coverage belongs to the general gate
`test_no_dead_src_path_literals.py` (its `(?<!\w)src/` Python-`re` lookbehind
catches the blob-URL shape), not to Gate D.

## 4. Non-vacuity invariant (what must survive — Standing Order 5 / C-011)

The committed regression test exercises the **real** `git grep` + the module's
`_MOVED_BUILTIN_DOC_RE` against a synthetic git repo, asserting both directions:

- the nested-tail fixture is **not** reported (the over-match is gone), AND
- a genuine top-level fixture **is** reported (the guard keeps its reach).

It is **self-mutation-proven**: removing the left-boundary anchor re-reds the
over-match assertion, and breaking the match re-reds the positive-control
assertion. A gate-unmask cannot self-validate — hence both directions on the
same fixture. The live gate must still return zero on the real clean `docs/`
tree and still red on a planted genuine top-level dead ref, with
`_GUARD_DOC_EXCLUSIONS` (docs/adr, docs/plans, the retrieval index, the
relocation migration note) left intact.

## 5. Sibling-gate audit (each gate #6096 asks about)

| Gate / module | Mechanism | Shares the identical `git grep`-no-left-boundary root cause? |
|---|---|---|
| **Gate D** — `test_dead_builtin_doc_paths.py` | `git grep -nE` with unanchored `_MOVED_BUILTIN_DOC_RE` | **Yes — this is the defect.** |
| `test_no_dead_cli_paths.py` — Gate A (`_GRAPH_MONOLITH_RE`) | Python `re` over `_text_files`; pattern leads with `[\w./<>*-]*` that **absorbs** the prefix, keyed on a `doctrine/`/`charter-packs/` segment (deliberately prefix-agnostic) | No — different engine; no top-level `src/` anchor is claimed. |
| `test_no_dead_cli_paths.py` — Gate B (`_SHIPPED_PATH_RE`) | Python `re`; requires a preceding `<seg>/` before `shipped/` (deliberately prefix-agnostic) | No — matches a defect class that is intentionally position-independent. |
| `test_no_dead_doctrine_paths.py` — Gate C | Resolves relative markdown links on disk (`_resolves`/`_escapes_boundary`) | No — no regex-boundary mechanism at all. |
| `test_no_dead_src_path_literals.py` | Python `re` with `(?<!\w)src/` **negative lookbehind** (a real, documented left boundary) + on-disk existence check | No — different engine; already left-bounded. Its lookbehind excludes a preceding word char but not `/`/`.`/`-`, so a `…/src/…` tail can be judged against the top-level tree; this is a **narrower, pre-existing nuance on a different gate**, not the same `git grep` root cause. |

**Conclusion**: only Gate D carries the identical `git grep`-no-left-boundary
root cause. Per the change-scope reconciler (smallest-viable-diff + locality of
change), the fix stays scoped to Gate D. The `test_no_dead_src_path_literals.py`
lookbehind nuance is recorded here and in the PR as a **follow-up observation**
(it is a different gate, a different engine, already green, and widening it
would grow the file set beyond the stated goal), not folded into this PR.
