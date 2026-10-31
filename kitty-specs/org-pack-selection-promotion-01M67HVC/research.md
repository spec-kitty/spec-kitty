# Research: Promote org-pack interview selections on upgrade (#6686)

## Reproduction (current `main`, `512567eee7`)

Fixture: `.kittify/config.yaml` registering an org pack whose `directives/` file is
`qa-003-no-fake-green.directive.yaml` with `id: QA_003`; a present
`activated_directives: [001-architectural-integrity-standard]` list; `answers.yaml`
with `selected_directives: [QA_003]`. Running `4.0.0rc8_promote_interview_selections`:

```
success: True
changes: ['No interview selections to promote: every selection is already in force']
warnings: ['Unresolved interview selections skipped (not promoted): directive:QA_003']
ledger: {'activated_directives': ['001-architectural-integrity-standard']}
```

The org id is reported unresolved and never promoted — the defect in #6686. The same
fixture through `charter interview` resolves `QA_003` to `qa-003-no-fake-green` and
promotes it, because that path resolves through `IdentityIndex`.

## Code map

| Where | What it does today |
| --- | --- |
| `src/specify_cli/upgrade/migrations/m_4_0_0rc8_promote_interview_selections.py` | `_StemResolver` wraps `resolve_selected_id_to_stem(kind, raw_id, offering_root=resolve_offering_root())` — built-in layer only. `_resolve_selections` is the per-kind loop (dedupe + unresolved collection). |
| `src/specify_cli/cli/commands/charter/interview.py` `_promote_interview_selections` | Builds `IdentityIndex.from_roots(offering_root, resolve_pack_chain(strict=False), resolve_layer_roots(repo_root))` and runs its own copy of the same loop (`index.stored_spelling` / `index.knows`). |
| `src/charter/activation/identity_index.py` | `IdentityIndex.build(repo_root)` indexes project pack, org packs and built-in — the authority `charter context` uses since #6406/#6407. |
| `src/charter/activation/api.py` | The one sanctioned seam; `IdentityIndex`, `resolve_selected_id_to_stem`, `promote_activations`, `resolve_activation_write_target` are already exported here. |

## Decisions

- **D-1 — Route promotion through `IdentityIndex`, not a second lookup.** The defect is
  the same class as #6407: a consumer resolving against the built-in layer only. The
  fix builds on the authority `charter context` already reads; no new precedence rule
  and no third resolution path.
- **D-2 — Put the shared loop behind `charter.activation.api`.** The #6678 landing
  review flagged the duplicated loop. One resolver (selection-shaped view: ids in,
  `activated_<kind>` stems out, unresolved ids named) removes the copy and keeps the
  upgrade step's cheap-import property (index built lazily, only when a selection
  exists).
- **D-3 — Keep each writer's error policy, share only the resolution.** Today an
  unknown id is reported by the upgrade and warned by the interview; an ambiguous
  directive identity is reported as unresolved by the upgrade and refused with
  `ActivationIdCollisionError` by the interview (Decision `file_name_collision`,
  pinned by `tests/charter/activation/test_stored_spelling_6527.py`). The resolver
  therefore returns structured outcomes (stems / unresolved / ambiguous) and the
  interview asks it to refuse ambiguity; the upgrade reports it. Neither behaviour
  changes, both get org- and project-layer resolution.
- **D-4 — Stem spelling is the promoted value.** As before: a declared id maps to the
  file stem, never back to the id, so a list holding the stem is not duplicated
  (#6423).
- **D-5 — Built-in behaviour is unchanged.** `IdentityIndex.build` includes the
  built-in layer last, so every id the current code resolves still resolves to the
  same stem.

## Open questions

- Mission-step-contract selections do not resolve in either writer (`kind_vocabulary`);
  the shared resolver will not invent support. Out of scope per the issue, unless the
  identity index already answers for the kind (it does index it, so the shared path may
  improve it as a side effect — to be pinned by a test only if it works).
- Whether `_stem_spelled_config` (interview, `--narrow-activation` only) should also use
  the shared resolver's spelling helper: yes if it is a straight swap, since it is the
  same rule on a present list.
