# Data Model: Docs lint

All shapes are frozen dataclasses in the two scripts. They are pure values with no I/O.

## UnreleasedSection (`scripts/release/validate_release.py`)

| Field | Type | Notes |
|---|---|---|
| `start_line` | `int` | 1-based line number of the `## [Unreleased]…` heading in the source file |
| `lines` | `tuple[str, ...]` | lines after the heading, up to but excluding the next level-2 release heading outside a fenced block (or EOF) |

Invariant: `unreleased_section(text)` returns `None` when no Unreleased heading exists. A line inside a ``` fence never ends the section.

## Entry (`scripts/docs/check_changelog_style.py`)

| Field | Type | Notes |
|---|---|---|
| `section` | `str` | the enclosing `###` heading text |
| `subsection` | `str \| None` | the enclosing `####` heading, if any |
| `line` | `int` | 1-based file line of the `- ` bullet |
| `lines` | `tuple[str, ...]` | the entry's own raw lines (bullet plus continuation lines at indent < 2) |
| `nested` | `tuple[tuple[str, ...], ...]` | each nested sub-item's raw lines; deeper nesting belongs to its level-1 item |
| `headline` | `str \| None` | text inside the leading `**…**`, if present |

Derived: `prose` = the joined text of `lines`; `length` = `len(prose)` in code points; `body` = the text after the headline and refs.

## Finding (shared shape in both scripts)

| Field | Type | Notes |
|---|---|---|
| `severity` | `Literal["error", "warning"]` | only `error` affects the exit code |
| `rule` | `str` | a stable rule id, e.g. `heading-order`, `refs-in-bold`, `contrast`, `length`, `banned-token`, `typo`, `us-spelling` |
| `path` | `str` | repo-relative canonical path |
| `line` | `int` | 1-based real file line (the section offset is already applied) |
| `where` | `str` | for the guard, `"[<section>] <headline excerpt ≤ 60 chars>"`; for spelling, the word |
| `fix` | `str` | an imperative, exact fix sentence |

Rendering: `path:line: [rule] where — fix`. Sort order is `(path, line, rule)`, which keeps output deterministic (NFR-003).
