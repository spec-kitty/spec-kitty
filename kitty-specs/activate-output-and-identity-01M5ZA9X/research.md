# Research: Activate output and identity (Phase 0 grounding)

Base: `origin/main` @ `581b5c46` (2026-10-27). All citations re-verified on that commit.

## 1. Code grounding (cited lines re-verified)

| Brief / issue citation | Current location | Finding |
|---|---|---|
| `pack_manager.py:~581` `_narrow_inputs` | `src/charter/activation/pack_manager.py:581-619` | Confirmed. Appends `NARROW_UNRESOLVED_WARNING` whenever the key is absent and `in_force` is False; mission-type (`kind is None`) takes the same branch although nothing was in force. |
| `pack_manager.py:~1089-1097` warning concatenation | `pack_manager.py:1089` (`_preservation_set`), `:1097` (`[*preservation_warnings, *narrow.warnings]`) | Confirmed. Preservation warnings are computed before `--only` and concatenated with the narrow ones. |
| #6457 "initialized from the 4 mission types" | `pack_manager.py:500-506` (`_preservation_ids`, mission-type note) | Confirmed. |
| #6457 widened: every unresolved kind | `pack_manager.py:507-511` (generic "could not be resolved ...; initialized from N ids") | Confirmed; also printed beside the narrow warning. |
| #6458 plain path freezes | `pack_manager.py:495-497` (`when_absent != "all"` -> `PackContext.allow_for`), engine `_materialise_absent` (`activation_engine.py:~299-319`) appends `FROZEN_LIST_NOTE`, which recommends `--only` (`:240-243`). | Confirmed. |
| #6458 `--only` freezes | `_narrow_inputs` -> `org_required_stems` (`pack_manager.py:617`); `plan_narrowed_list` writes it (`activation_engine.py:~332`). No warning. | Confirmed. |
| #6458 present list stops org default | `pack_context.py:863-866` (`declared is not None` returns the list), `_absent_key_default` `:886-895`. | Confirmed. |
| Interview-exclusion rationale | `src/charter/activation/org_charter.py:~102-107` (`_INTERVIEW_SEEDED_KIND_FIELDS`) | "writing its key would freeze today's list, so a later addition to the org's `required_<kind>` would stop applying." |
| #6459 `identity_index.py:~244-250` | `src/charter/activation/identity_index.py:244-250` (`_lookup`: `by_stem.get(token) or by_id.get(token)`) | Confirmed stem-first, layer-agnostic. |
| #6459 `resolver.py:~206-242` | `src/charter/activation/resolver.py:217-242` (`_gated`) | Confirmed: a token the index knows resolves through `activation_id` (stem first); a built-in declared id that is also a higher-layer stem resolves to the higher-layer artifact. |
| #6403 glossary | `docs/context/governance.md:79`, `docs/context/charter.md:54` | Confirmed wrong `PACK_LEVEL_MISSING` clause. Code: `org_pack_loader.py:528-555` warns and loads; `pack_validator.py:706` `_PACK_LEVEL_MISSING_IS_ERROR = False`, `:759-767` advisory. Note (triage on #6403): the org-loader warning branches do not consult the validator switch, so the wording must not promise that flipping it alone changes loading. |

### Red-first reproductions (live, installed CLI from this checkout)

- #6457: `spec-kitty charter activate --no-compile mission-type software-dev --only` on an empty project printed "initialized from the 4 mission types available ..." and "What stopped being in force cannot be listed: the effective set could not be resolved." beside "No longer in force (0)", with 1 entry written. Reproduced.
- #6458: `activate skill x` (absent key, org requires `required-one`) wrote `[required-one, x]` and printed the generic note recommending `--only`; `activate skill x --only` wrote the same and printed no warning. Reproduced.
- #6459: existing coverage pins only the opposite cross-layer direction at the index level (`tests/charter/activation/test_identity_index.py:319-330`); no resolver-level test for built-in declared id vs higher-layer stem.
- #6403: docs; no runtime reproduction needed.

## 2. Architectural alignment

- ADR `2026-10-16-1` (+ Amendment 2026-10-19): charter stays in core; nothing here crosses `charter.offering.api`. All changes are inside `charter.activation` (engine/manager) and the `specify_cli` renderer. No layer-rule or package change.
- ADR `2026-10-19-1` (activation ledger): no change to what is written or how deny lists move.
- Epic #6518 (activation contract): owns allow-list vs org-required-floor semantics (#6684, #6685) and spelling (#6435). This mission changes output text only (C-001), so nothing here is redone by #6518 except that, if #6685 changes the default for a first activation, the plain-path skill warning's trigger may move with it. Accepted by the operator brief ("#6458 WARNING PART ONLY").
- #6099 conformance corpus / `charter list --json` (OP-CONTRACT-003, #6417): untouched; `activate` has a JSON envelope only for `--preset`, which this mission does not change.

## 3. Related issues and in-flight work

- Open PRs at grounding time: #6717, #6716 (#6193), #6705, #6620, #5540. None touches `pack_manager.py`, `activation_engine.py`, `resolver.py`, `org-doctrine-layer.md` or the two glossary entries.
- #6439 shares the Pack Level entry sentence ("tier" wording, Contract Scenario): out of scope; only the `PACK_LEVEL_MISSING` clause changes.
- #6684/#6685/#6686, #6435: referenced, not changed.

## 4. Tidy-first

- One behaviour-preserving preparatory refactor: carry the unresolved-set *reason* out of `_preservation_ids` (today only logged) so the narrow warning can state it, without changing any current output.

## Decisions (Decision Moments, resolved)

- `only_output`: narrow lines only; add a "Now listed for <kind> (N): ..." line; mission-type absent key gets no unresolved warning; other unresolved kinds get one warning with the reason.
- `skill_freeze_warning`: one shared constant in the engine keyed on `effective_when_absent == "required"`; plain path only on an absent key (replacing the `--only` advice); `--only` every run.
- `scope`: #6457 widened; #6459 test + doc; #6458 warning only; #6403 docs only.

## Addendum (2026-10-27): #6527 local slice

Operator added the local slice of #6527 (with #6433, #6435) to this mission. Full grounding with file:line citations and experiments: [research-6527-grounding.md](./research-6527-grounding.md).

Decisions (Decision Moments, resolved): add as WP04/WP05; consistency check warns and keeps unknown tokens; compile resolves through `IdentityIndex` but stays strict on a truly unknown token; no normalising ledger migration; a token with no single stem is kept as given with a warning on every writer; built-in step contracts get indexed in `IdentityIndex`. Integration slice (ACL export, `activation_invalid`, #6520) stays with epic #6518, so the PR says "Refs #6527".
