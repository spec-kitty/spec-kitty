# Contract — `spec-kitty charter generate --json` (additive change)

**Backed by**: FR-004 (mission `charter-generation-drops-scoped-references-01M3M1KF`, issue #5257)

## Status

This is an **additive, backward-compatible** change to an existing, already-shipped JSON contract
(`src/specify_cli/cli/commands/charter/generate.py`'s `--json` emit block). No existing key is
removed, renamed, or changed in type. A new top-level key is added.

## Before (existing shape, unchanged fields)

```json
{
  "result": "success",
  "success": true,
  "charter_path": "...",
  "interview_source": "...",
  "mission": "...",
  "template_set": "...",
  "selected_paradigms": [...],
  "selected_directives": [...],
  "available_tools": [...],
  "references_count": 42,
  "library_files": [...],
  "files_written": [...],
  "diagnostics": ["Unresolved reference: styleguide/java-conventions (scope_filtered): ..."]
}
```

`diagnostics` remains a flat `list[str]` — every existing consumer that treats it as such continues
to work unchanged. Per-line content is extended (FR-002) to carry a `(cause)` suffix and a short
detail, but the field's own type and key name never change.

## After (new field, additive)

```json
{
  "...": "... all fields above, unchanged ...",
  "unresolved_references": [
    {
      "kind": "styleguide",
      "id": "java-conventions",
      "cause": "scope_filtered",
      "detail": "artifact 'java-conventions' is present but its applies_to_languages scope does not include the active language set ('python')."
    }
  ]
}
```

- `unresolved_references` is **always present** when `diagnostics` would otherwise be produced by this
  code path (empty list `[]` when there are no unresolved DRG-backed references) — matching
  `diagnostics`'s own always-present convention, so a consumer can rely on key presence rather than
  using `.get()` with a default.
- `kind` is one of the DRG-backed kinds `_render_kind_references` covers: `directive`, `tactic`,
  `styleguide`, `toolguide`, `procedure`, `agent_profile`.
- `id` is the bare activated id (no `KIND:` prefix — matches the raw id as configured in
  `.kittify/config.yaml`, not the `CharterReference.id` field's `KIND:id` form).
- `cause` is the `charter.activation._catalog_miss.CatalogMissCause` enum's `.value` string:
  `"missing_artifact"`, `"typo_suspected"`, or `"scope_filtered"`. (`"schema_validation_suspected"` is
  reserved for callers with ground-truth loader-drop knowledge, which this call site does not have —
  see `_catalog_miss.py`'s own docstring — so it is not expected to appear here in practice.)
- `detail` is the human-readable classifier suggestion text `classify_catalog_miss`/
  `classify_scope_filtered_miss` already produce (unchanged text from those existing, already-tested
  primitives — this contract does not introduce a new message format, only surfaces the existing one
  structurally).

## Why additive-alongside, not widening `diagnostics` entries into objects

Any existing consumer (CI scripts, readiness probes, `_finalize_sync_result`'s own sync-warning
concatenation, which appends plain strings into the same `diagnostics` list) that treats `diagnostics`
as `list[str]` keeps working unchanged. Widening the existing field's element type to `str | dict`
would be a breaking shape change for every such consumer, with no compile-time signal in a
dynamically-typed JSON contract to catch the break. A new, always-present key is additive and
detectable (`"unresolved_references" in payload`) without touching the existing key's shape at all.

## Round-3 addition — graph-load-failure diagnostic entry (operator ruling on PLAN-FRESH2-001)

`unresolved_references` gains one additional, distinct entry shape for the case where the WHOLE DRG
graph fails to load (`charter.activation.compiler._resolve_transitive_reference_graph`'s `except
Exception: return fallback` branch — see plan.md's "WP-CORE reconciliation" point 3, round-3
amendment, part (c)). This is not a per-artifact miss — no per-kind breakdown exists to attribute
it to a specific kind or id — so it uses reserved sentinel values instead of a real `kind`/`id`
pair:

```json
{
  "kind": "_graph",
  "id": "_load_failure",
  "cause": "graph_load_failed",
  "detail": "<short exception summary>"
}
```

- `kind: "_graph"` / `id: "_load_failure"` are reserved sentinel values (leading underscore,
  distinct from any real DRG-backed `kind`/`id` — no built-in kind or activated id is ever
  literally named `_graph`/`_load_failure`), so a consumer can specifically detect this entry (or
  filter it out) without confusing it for a per-artifact miss.
- `cause: "graph_load_failed"` is a new value in this field, distinct from the three
  `CatalogMissCause` values documented above (`missing_artifact`, `typo_suspected`,
  `scope_filtered`) — this entry is not per-id classified via `classify_catalog_miss`/
  `classify_scope_filtered_miss` at all.
- **Type: `cause` is a plain `str` on the compiler-internal structured record, NOT the
  `CatalogMissCause` enum type** (closes PLAN-FRESH3-004). `CatalogMissCause`
  (`src/charter/activation/_catalog_miss.py:129-161`) is a closed 4-member `str, Enum` with no
  `"graph_load_failed"` member, and `CatalogMissDiagnosis.cause`
  (`_catalog_miss.py:164-174`) is strictly typed `CatalogMissCause`, not `str`. Typing the new
  structured-records sink's `cause` field as `str` lets the three real `CatalogMissCause.value`
  strings (produced for the per-artifact-miss entries above) and this new sentinel value coexist
  in the same JSON field without adding a member to `CatalogMissCause` — `_catalog_miss.py` stays
  REUSED, NOT MODIFIED (see plan.md's Project Structure section and the "binding mechanism decisions
  retained from prior rounds" list under "WP-CORE reconciliation" point 3).
- `detail` is a short summary of the underlying exception (not a `_catalog_miss` classifier
  suggestion — there is no id to classify).
- **This entry does NOT cause `generate` to exit non-zero.** The operator's explicit ruling on
  PLAN-FRESH2-001 is that a total graph-load failure is loud and structured, not fail-closed; it
  also does NOT participate in the whole-kind aggregate fail-closed count (plan.md's round-3
  amendment, part (c), explains why: the aggregate check counts per-kind ids that were actually
  classified, and a total graph-load failure has no per-kind breakdown to classify).
- The same diagnostic text appears as a plain-string entry in `diagnostics: list[str]` too
  (FR-002's reason-bearing convention applies to this diagnostic as well, e.g. `"Graph load failed:
  <exception summary>. Transitive closure not resolved; direct-root ids only."`).

## Round-5 addition — unattributable `graph.unresolved` entries (closes PLAN-FRESH4-003, invariant I3)

`unresolved_references` gains four further entry shapes for `graph.unresolved` URNs that cannot be
attributed to one of the six DRG-backed kinds `_render_kind_references` tracks (directive/tactic/
styleguide/toolguide/procedure/agent_profile). Per plan.md's invariant I3 ("every structured
diagnostic record carries a defined `kind`, `id` and `cause`"), each of these still gets a real
entry — never silently dropped:

1. **No `":"` in the URN (malformed — no kind prefix at all).**
   ```json
   {"kind": "_unattributed", "id": "<the full URN string>", "cause": "malformed_urn", "detail": "malformed URN, no kind prefix"}
   ```
   `kind: "_unattributed"` is a reserved sentinel (same leading-underscore convention as `_graph`/
   `_load_failure` above), used only when no kind could be parsed from the URN at all.

2. **`kind_prefix` has no `ArtifactKind` counterpart** (`ArtifactKind(kind_prefix)` raises
   `ValueError` — e.g. `action`, `glossary_scope`, `glossary`, `mission_type`, or any other
   unrecognized string).
   ```json
   {"kind": "<the raw kind_prefix, verbatim>", "id": "<the bare id after the \":\" split>", "cause": "unattributed_kind", "detail": "unrecognized artifact kind: <kind_prefix>"}
   ```

3. **`kind_prefix` is a valid `ArtifactKind` whose repository genuinely resolves to `None`** (`template`,
   `asset`, `anti_pattern` — whose repository is `None` by design, per
   `DoctrineService.raw_repository(kind)`'s documented behavior for kinds outside the nine gated
   raw-repository kinds).
   ```json
   {"kind": "<the ArtifactKind's singular value, verbatim>", "id": "<the bare id>", "cause": "unattributed_kind", "detail": "no repository for kind: <kind_prefix>"}
   ```

4. **`kind_prefix` is a valid `ArtifactKind` that DOES resolve to a real, non-`None` repository, but
   whose plural is outside the six kinds `_render_kind_references` tracks** (a valid-but-untracked
   kind such as `paradigm`, `mission_step_contract`, `glossary_pack` — round-6 split, closes
   PLAN-FRESH5-003: the detail text must not claim "no repository" for a kind that has one).
   ```json
   {"kind": "<the ArtifactKind's singular value, verbatim>", "id": "<the bare id>", "cause": "unattributed_kind", "detail": "kind '<kind_prefix>' is not one of the six DRG-backed kinds tracked for reference resolution"}
   ```

Both new `cause` values are plain `str`, distinct from the four `CatalogMissCause` values and from
`"graph_load_failed"` — same typing rule as the round-3 addition above (`_catalog_miss.py` stays
REUSED, NOT MODIFIED). `detail` in all four cases is a short human-readable string explaining why
the entry could not be attributed (not a `_catalog_miss` classifier suggestion — there is nothing to
classify); items 3 and 4 share the `cause` value `"unattributed_kind"` but carry distinct, accurate
`detail` text for their distinct root causes. **None of these four entries participates in the
six-kind whole-kind aggregate fail-closed count** (plan.md's I2) — same exemption reasoning as the
graph-load-failure entry: there is no per-kind bucket among the six tracked kinds to honestly
attribute them to.

## Relationship to `CharterPreflightResult`

Not related. This contract governs `charter generate --json`'s own stdout payload. The preflight
contract (`contracts/charter-preflight-json.md` in `kitty-specs/charter-ux-and-org-pack-vocabulary-01KSAF14/`)
governs a structurally different, unrelated command (`spec-kitty charter preflight`) and is
**not modified** by this mission — see plan.md's Charter Check section.
