# Research: Charter identity single authority (#6433)

Grounding performed on `main` at `dfe9efb0e8` before specifying. Reproductions use the
shipped CLI on a ledger-seeded project, which is the pre-existing entry point.

## 1. What has already landed

`git log -S` and the file history show three of the four paths the issue names are closed:

| Commit | What it closed |
| --- | --- |
| `07caa6025c` (#6406, #6407) | `IdentityIndex` itself; resolver, `--include`, selection block, presets, `charter list` route through it. |
| `a8dd1812a6` (#6457, #6435, #6433 partial, #6527 slice) | `compiler.resolve_config_activated_roots`, the consistency check, `filter_graph_by_activation` and preset application resolve through one `IdentityIndex`; writers store stems; built-in step contracts are indexed. |
| `5096461bd2` / `f71213ccfa` (#6749, branch `issue-6749-charter-consistency-project-layer`) | the consistency check's project layer. |

So the routing half of #6433 is done, and the Mission must not redo it (C-005). The
surviving half is the issue's *expected* clause: "make `resolve_artifact_urn` a thin
wrapper over the index (or move the directive round-trip rule into the index), and pin
one behaviour for unknown tokens".

## 2. The remaining second implementation

`src/charter/activation/kind_vocabulary.py` still carries three scan-and-match loops:

- `resolve_artifact_urn` (~:440) — stem first, then declared id; directives additionally
  route through `resolve_config_id` so a declared id is accepted only when some filename
  round-trips to it.
- `resolve_config_id` (~:627) — the inverse; walks the file list, and for directives
  re-checks each candidate stem with `_directive_stem_represents`.
- `resolve_selected_id_to_stem` (~:717) — builds a stem set by walking the file list.

They share the scanner primitives with `IdentityIndex._scan`, but each re-implements the
match order. The index is therefore not the authority for anything that goes through
them.

Direct callers on `main` (excluding tests):

```
src/specify_cli/cli/commands/charter/activate.py:240              _source_urn
src/specify_cli/cli/commands/charter/deactivate.py:108            _source_urn
src/specify_cli/cli/commands/charter/deactivate.py:154            _active_urns
src/specify_cli/cli/commands/charter/_resynthesis_preflight.py:64 _cascade_source
```

## 3. Reproductions

### 3.1 The facade disagrees with the index (unit)

```
$ uv run python -c '... resolve_artifact_urn vs IdentityIndex.declared_id ...'
directive:DIRECTIVE_024 | factory: RAISED UnknownArtifactIdError | index: DIRECTIVE_024
24                      | factory: RAISED UnknownArtifactIdError | index: DIRECTIVE_024
DIRECTIVE_024           | factory: directive:DIRECTIVE_024        | index: DIRECTIVE_024
024-locality-of-change  | factory: directive:DIRECTIVE_024        | index: DIRECTIVE_024
```

The write path accepts all four spellings (writers store the stem), and the runtime gate
resolves all four. Two of four are refused by the facade.

### 3.2 `activate --cascade` silently drops the cascade (CLI)

Fixture: `tmp_path` project, `.kittify/config.yaml` = `{}`, activation ledger seeded with
`mission_type_activations=["software-dev"]`; command run with `--no-compile`.

```
$ spec-kitty charter activate directive 024-locality-of-change --cascade all
Activated: 024-locality-of-change
...
Cascade-activated: directive/reconcile-change-scope-tensions

$ spec-kitty charter activate directive directive:DIRECTIVE_024 --cascade all
Activated: 024-locality-of-change
...
(no cascade line)

$ spec-kitty charter activate directive 24 --cascade all
Activated: 024-locality-of-change
...
(no cascade line)
```

All three activate the same artifact (ledgers identical). Only the stem cascades.
`_source_urn` returns `None`, and the command treats `None` as "no cascade", so neither
the cascade nor the referenced-but-not-cascaded warning prints. This is a silent loss of
work the operator asked for, not a cosmetic difference.

### 3.3 `deactivate --cascade` silently drops the shared-artifact safety report (CLI)

```
$ spec-kitty charter deactivate directive 024-locality-of-change --cascade all
Deactivated: 024-locality-of-change
Skipped (shared artifact): directive:RECONCILE_CHANGE_SCOPE_TENSIONS (still
referenced by agent_profile:analyst-annie)

$ spec-kitty charter deactivate directive directive:DIRECTIVE_024 --cascade all
Deactivated: 024-locality-of-change
(no skip line)
```

The exclusion is written either way, but the report that says a shared artifact was kept
because an active agent profile still references it disappears. That report is the
operator's only signal that the cascade considered the child at all.

## 4. Design constraints discovered

- **Import direction.** `identity_index.py` already imports `kind_vocabulary`, so the
  facade-to-index dependency must be a function-local import. `identity_index`'s own
  docstring forbids importing `resolver`/`profile_resolution`; `kind_vocabulary` is fine.
- **Directive semantics differ by direction, and must not be flattened.**
  `IdentityIndex.declared_id` accepts a hand-written declared directive id even when its
  filename cannot represent it (compile and the consistency check rely on that; a writer
  refuses it via `stored_spelling`/`collision_error`). `resolve_artifact_urn` refuses that
  same id (`UnrepresentableDirectiveIdError`). The facade must keep refusing, expressed as
  "the index knows the id but can name no stem" — the index's existing
  `stem()`/`_representable_stem` already encodes exactly that rule.
- **Scan cost.** `_iter_artifact_paths` memoises scans and id reads in a `ResolutionPass`.
  `IdentityIndex._scan` currently calls `_scan_roots`/`_scan_dir_matches` directly, so it
  would re-glob per call unless it reads through the same memo. Callers that thread a pass
  today (`_CascadeIds`, `deactivate`) are exactly the ones this Mission touches.
- **Existing pins to keep green unchanged**: `tests/charter/test_kind_vocabulary.py`,
  `tests/charter/test_config_stem_parity.py`, `tests/charter/test_directive_identity_mapping.py`,
  `tests/charter/test_kind_vocabulary_recursion_parity.py`, `tests/charter/test_answers_inert_and_org_union.py`,
  `tests/charter/activation/test_compile_check_identity_6433.py`. They pin the facade's
  behaviour including its error types, so they are the parity harness for IC-01.

## 5. Unknown-token policies on `main` (to be pinned, not changed)

| Surface | Policy today | Where |
| --- | --- | --- |
| Runtime gate (`resolver._gated` / `IdentityIndex.activation_id`) | warn and keep, best-effort id | `identity_index.activation_id` |
| Consistency check | report once in `unknown_references`, keep the stored list | `consistency_check._check_unknown_references` |
| Compile (`resolve_config_activated_roots`) | refuse with `UnknownArtifactIdError` naming the activation store | `compiler._resolve_config_activated_id` |
| Cascade source (`_source_urn`) | no source, so no cascade and no error (the activation itself still happens) | `activate._source_urn` |

`tests/charter/activation/test_compile_check_identity_6433.py` already documents the first
three; this Mission adds the fourth and pins all four together (FR-007).
