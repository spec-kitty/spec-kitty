# Behavioural Contract: Untrusted-Path Audit Relocation Pairing (#6642)

This mission has no network/API surface. The "contracts" are the behavioural
guarantees of the audit gate at `tests/architectural/untrusted_path_audit/`.
Each is a testable assertion; the pinning tests live in
`tests/architectural/test_untrusted_path_containment.py`.

## C-PAIR-1 — pure-move pairing (FR-001)

- **Input**: the discovered key map and the inventory key map (composite
  `(rel_path, qualname, token)` keys, `[inventory-only]` rows excluded).
- **Pair**: a `(token, untrusted source)` group holding **exactly one** ghost
  key and **exactly one** missing key, when the token is not `…`-truncated.
- **Never pairs**: a genuine removal, a genuine new sink, a changed token, an
  ambiguous group (2:1 or 1:2), a truncated token, a source-cell mismatch.

## C-PAIR-2 — single actionable finding, still RED (FR-002)

- **Given** a recognised pure move, `main()` reports exactly ONE
  `sink moved:` finding naming both locators, suppresses that sink's
  ghost/undercount errors, and exits non-zero until the inventory is re-pinned.
- **Given** a green tree, the output is byte-identical to the pre-#6642 audit
  (plain `AUDIT OK:` summary; no relocation noise).

## C-FIX — locator-only, fail-closed `--fix` (FR-003)

- **Rewrites**: only the `file:line` and `qualname` cells of paired rows.
  Token, untrusted source, sink op, disposition and rationale are never
  touched.
- **Refuses to write**: while any non-relocation error exists; when the
  in-memory re-audit of the would-be result is not fully green.
- **Idempotent**: a second `--fix` on a green tree writes nothing.

## C-TEETH — the ratchet keeps its teeth (FR-004/FR-005/FR-007)

- A removed sink still fails (overcount/ghost only); a new undocumented sink
  still fails (undercount only). `[inventory-only]` rows never pair and stay
  exempt from the overcount guard only via their documented tag.

## C-HYGIENE — canonical source cells, no shift chains (FR-006)

- A live row's `untrusted source` cell must equal the matcher's canonical
  machine string exactly (hand annotations belong in the rationale).
- No rationale cell may carry a hand-kept line-shift chain
  (`1902→1933` arrow form or `shifted −11` prose form) — git history records
  relocations, and `--fix` re-pins the locators.
- Both guards are pinned red-first: their removal (or a regex weakening)
  turns the containment suite red.

## C-REGRESSION — architectural guard

- The audit module (`python -m tests.architectural.untrusted_path_audit.audit`)
  exits 0 on the committed tree with the summary
  `AUDIT OK: 45 inventory rows (39 AST-discovered, 6 inventory-only);
  TODO(fix)=3 safe=23 trusted=10 unreachable=9`, and any drift in either
  direction fails `tests/architectural/`.
