# Research: `charter activate` without `--cascade` and artifacts already in force (#6742)

## Reproduction (on `main@512567eee7`)

Two fixtures, both with a `.kittify/config.yaml` that carries only
`mission_type_activations` (no `activated_<kind>` key):

1. `spec-kitty charter activate --repo-root <tmp> --no-compile mission-type software-dev --only`
   prints one `Warning: referenced <kind>/<id> was not activated (no --cascade).` per
   referenced artifact (20 directives on the fixture; the issue reports ~150 lines on a
   fully-initialized project), each of which is in force, because an absent
   `activated_directives` key means "all directives".
2. `spec-kitty charter activate --repo-root <tmp> --no-compile directive
   001-architectural-integrity-standard` prints the same warning for every referenced
   directive, including the ones the same run just wrote into the list it initialized
   from the effective set.

Exit code 0 in both cases: the activation itself is fine, only the report lies.

## Decision 1 — the membership question already has one authority

`PackContext.admits(kind, token, available)` (`src/charter/activation/pack_context.py`)
is documented as "the membership accessor, M2". It nets out the deny list first, then:
an absent allow list admits a token of `available` when
`ArtifactKind.effective_when_absent == "all"`; a present list (including the org-required
floor `from_config` materializes for `skill`) admits its own tokens. That is exactly the
"is it in force" question, so the CLI asks it there instead of re-deriving the three-state
rule.

Consequence: no new membership logic, and deny handling stays where it already is.
Only `skill` has `effective_when_absent == "required"`; every other activatable kind is
"all", so the absent-`all` branch covers the reported case.

## Decision 2 — evaluate against the state the command leaves behind

The check runs after the direct write (`_no_cascade_report` is already called after
`manager.activate` + `commit_project_registration`). This matters for `--only`:
`activate directive 001 --only` narrows `activated_directives` to the selection, so a
referenced `003` is genuinely *not* in force afterwards and must keep the warning. Reading
the pre-write state would print "already in force" for it, which would be false about the
resulting project.

## Decision 3 — text: a `Note`, not a `Warning`, with the reason

`render_no_cascade_warning` prints, before the remaining warnings:

```text
Note: referenced tactic/c-tac is already in force (no explicit list); not added by this command.
Note: referenced directive/003-… is already in force (listed in activated_directives); not added by this command.
```

The reason comes from the activation ledger's three-state allow (`ledger.allow`, the
canonical reader on `charter.activation.api`): `None` (key absent) reads "no explicit
list"; a present list reads "listed in `activated_<plural>`". This is the distinction the
issue asks for, and it is true for the `skill` floor too (absent key ⇒ "no explicit list").

Style basis: the existing non-failure line for the same class of news is
`Preset '<name>' … is already in force in <file>; nothing changed.`, and the shared
`Not cascaded: … (kind not charter-activatable)` line is `[dim]`, deliberately not a
warning (issue #3705 ruling, `_cascade_shared.py`).

## Decision 4 — hint gating moves to the remaining skipped set

`NoCascadeReport.hint` (engine) is gated on the engine's `skipped` bucket, which counts
every non-deactivated reference. Once the already-in-force references leave that bucket,
the hint "Re-run with `--cascade` … to activate the referenced artifacts" must not be
printed when nothing is left to activate. The CLI gate becomes: hint only when the
*remaining* skipped list is non-empty. A shape where every reference is already in force
therefore prints no hint at all — the same non-vacuity argument the kind-filtered-only
case already made (`test_hint_gate_on_skipped_not_has_skipped_is_not_vacuous`).

## Decision 5 — `--json` gets its own list, `referenced_not_cascaded` keeps its meaning

`ActivationChangeReport.to_json()` currently emits
`referenced_not_cascaded = referenced.warned` (skipped + deactivated). Adding the in-force
entries there would make the key's name false. So:

- `referenced_not_cascaded` (existing key): the artifacts that really are not in force
  (skipped + deactivated) — unchanged name and meaning, smaller content;
- `referenced_already_in_force` (new key): `[{kind, id, urn}]` for the new bucket;
- `referenced_kind_filtered`: unchanged.

The consumer-facing docs live in `docs/api/charter-commands.md` (change-report table,
prose, both worked examples).

## Open questions resolved before plan

- Does `deactivate` need the same treatment? No: deactivate reports its in-force children as
  `still_active_unrestricted` / `skipped_required`, which already carry the right meaning;
  `render_no_cascade_warning` is called only from the `scope is None` branch of
  `charter activate`.
- Does the line order change? The notes print in the position the removed warnings
  occupied (before the deactivated warnings, before the hint, before the kind-filtered
  lines), so the remaining order is untouched.

## Evidence

- `src/specify_cli/cli/commands/charter/activate.py`: `_no_cascade_report`,
  `render_no_cascade_warning`, `_activation_change_report`.
- `src/specify_cli/cli/commands/charter/_activation_report.py`: CLI `NoCascadeReport`,
  `ActivationChangeReport.to_json`.
- `src/charter/activation/cascade.py`: engine `NoCascadeReport` (pure graph; unchanged).
- `src/charter/activation/pack_context.py`: `admits`, `allow_for`, `_absent_key_default`.
- `docs/api/charter-commands.md`: the documented text and JSON contract.
- Tests encoding the old wording: `test_activation_text_golden.py`,
  `test_activation_json_6525.py`, `test_charter_activate_commands_cascade_output.py`,
  `test_activate_include_deactivated.py`.
