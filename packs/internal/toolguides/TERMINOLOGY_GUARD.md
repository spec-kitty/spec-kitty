# Terminology Guard

## Overview

The legacy-terminology guard is an architectural test that scans active source files
(`src/`, `tests/`, `docs/`) for terms that have been superseded by the Terminology Canon.
It enforces canonical naming at the commit level — if a superseded term reappears in prose
or code, CI fails and the change is rejected before merge.

## When to Run

Before pushing any changes to `src/charter/offering/` or user-facing prose. The test runs in the
`tests/architectural/` suite, which is a CI-only shard — it does not run with the default
`fast-tests-*` filter. Run it explicitly before pushing:

```bash
pytest tests/architectural/test_no_legacy_terminology.py -q
```

## Command

```bash
pytest tests/architectural/test_no_legacy_terminology.py -q
```

## Understanding Failure Output

A failure message identifies the term, the canonical replacement, and the file(s) where it
was found. Example structure:

```
FAILED tests/architectural/test_no_legacy_terminology.py::test_forbidden_term_does_not_appear[<term>]
Forbidden legacy term '<term>' reappeared in active source.
Canonical term is '<replacement>' (see .kittify/glossaries/spec_kitty_core.yaml).
Hits (N):
  <file>:<line>:<content>
```

The `_FORBIDDEN_TERMS` list is defined inside the test file using string fragments (to
avoid the test flagging itself).

## How to Fix

Reword the prose to use the canonical term. Do **not** add a suppression, an exemption,
or a skip — the guard exists precisely to prevent exemption creep.

The guard runs as a plain fixed-string scan (`git grep --fixed-strings`) over the scanned
paths — it has no awareness of markdown structure, code fences, or inline backticks. A
superseded term written inside a code block or in backtick-quoted prose **still trips the
guard** if the file lives under a scanned path. There is no code-block or quoting exemption.

To refer to a superseded term by name without tripping the guard, use meta-language in
place of the literal string — for example, "the superseded selector term" or "the retired
status wording" rather than the exact string the guard matches. The guard's own test file
uses this technique: it builds its forbidden-term list from string fragments so the test
file does not match itself.

Excluded paths: `kitty-specs/` (historical mission snapshots) and `docs/adr/`
(immutable decision records) are exempt. The rest of `src/`, `tests/`, and `docs/` is
fully scanned.
