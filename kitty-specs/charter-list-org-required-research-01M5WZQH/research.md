# Research: `charter list` omits in-force org-required ids (#6417)

Discovery for issue [#6417](https://github.com/spec-kitty/spec-kitty/issues/6417)
(parent epic #6518). Base: `origin/main` at `e28ddabf`. Every claim cites the file or
command it comes from; anything without a source is labelled a hypothesis.

## Question

`spec-kitty charter list` prints `directive │ (All built-ins — no explicit activation)` for a
project whose org pack declares `required_directives: [team-rule]`, while
`spec-kitty doctor charter-packs --json` reports `{"id": "team-rule", "source": "org-required"}`.
Is this a product gap, scenario drift, or both?

## Decisions

### D1. Product gap: the listing never folds the required floor into an absent-key row

Root cause. `list_cmd` builds every row from `ActiveCharterManager.list_activated`
(`src/charter/activation/pack_manager.py:1221-1251`), which returns the raw allow keys of the
activation ledger and `None` for an absent key. The only org-required logic in the command is
FR-023 (`required_not_in_force`, `src/charter/activation/activation_ledger.py:1098-1122`), which
skips every kind whose allow key is absent (`if allow is None: continue`). An absent key with a
non-empty required floor therefore renders as "All built-ins" and never names the required id,
although that id is in force:

- the effective set of an absent `"all"` kind admits every available token that is not denied
  (`PackContext.admits`, `src/charter/activation/pack_context.py:267-279`);
- the deny a reader applies already subtracts the org required floor (`load_denied` /
  `_effective_deny`, `pack_context.py:383-415`), so a denied-but-required id is still admitted;
- `skill` (`effective_when_absent == "required"`) is materialised to the required floor by
  `PackContext.from_config` (`_read_activated_skills` / `_absent_key_default`,
  `pack_context.py:855-895`), but `list_activated` still reports the raw `None`, so the skill row
  is also mislabelled "All built-ins".

Decision (operator ruling 1): the fix derives the in-force required ids from `PackContext`
(`effective_ids` over the real availability), not from a second computation. It lives in
`charter.activation` behind `charter.activation.api`, beside `required_not_in_force`, so a later
`spec-kitty-charter` service cutover reads it through the same seam.

### D2. Scenario drift as well: the fixture puts the rule where no layer reads it

Shell port of the scenario fixture (`acceptance-jvm/src/test/java/kitty/acceptance/steps/CharterSteps.java`:
`REQUIRE_RULE_ORG_CHARTER`, `RULE_NODES`, `teamRule`, `TEAM_PACK_REGISTRATION`), run against the
installed CLI: [research/repro.sh](research/repro.sh).

| Fixture | `charter list` names `team-rule` | `charter context --action implement` | `doctor charter-packs` |
| --- | --- | --- | --- |
| As committed: `directive/team-rule.directive.yaml` (singular), `id: team-rule`, `body:` | no | `Charter catalog miss for directive:team-rule; cause=missing_artifact` | exit 0 |
| Corrected: `directives/team-rule.directive.yaml`, `id: TEAM_RULE`, `intent:`, `enforcement: required` | no (the product gap) | `team-rule (source: org)` / `Intent: the team-wide default` | exit 0 |

- Org packs are scanned flat at `<root>/<plural>/` (`kind_vocabulary._scan_roots` docstring,
  `src/charter/activation/kind_vocabulary.py:159-205`), so `directive/` is never read.
- The committed body also fails the `Directive` model (`id` pattern `^[A-Z][A-Z0-9_-]*$`,
  `intent`/`enforcement` required, `extra="forbid"`; `src/charter/offering/directives/models.py:104-122`),
  so even in the right folder the loader skips it with "Skipping invalid org directive".

Decision: fix both. With an honest in-force derivation (D1, "an id no layer provides is not
claimed in force"), the scenario only goes green when the fixture's rule is really provided. The
corrected fixture keeps `PR-CHARTER-GOVERNANCE-003` sound (doctor exit 0 above).

### D3. JSON contract change (OP-CONTRACT-003), versioned

Operator ruling 4: for an absent-key row with in-force required ids, `activated` becomes the sorted
in-force required ids (was `null`); every row gains `allow_list_present: bool`; the payload gains
`schema_version: "2"`. Convention check: charter-area JSON uses string versions
(`_fresh_project_layer.py:80` `"schema_version": "2"`, `_synthesis.py:148` `"1"`,
`agent_retrospect.py:179` `"1"`); `upgrade.py` uses an int. Use the string form.

### D4. Scenario tags after the fix

Precedent for a repaired `@wip @defect` scenario: `tests/scenarios/upgrade/migration-ledger.feature:146`
(#6416) drops `@wip`, `@wip-owner`, `@wip-since` and `@defect`, and turns the maintainer note into a
past-tense account. Follow it; `tests/scenarios/charter/PROMISES.md` row `PR-CHARTER-GOVERNANCE-002`
becomes `bound`.

## Consumers of `charter list --json` (blast radius)

Found with `grep -rln` over `src tests acceptance-jvm docs .agents packs scripts`:

| Consumer | Reads | Affected by D3 |
| --- | --- | --- |
| `tests/specify_cli/cli/commands/charter/test_charter_list_commands.py` | `activated`, `available`, `deactivated` | yes, extend + key-presence pins |
| `tests/specify_cli/cli/commands/charter/test_activate_preset.py:67` | `activated` per kind | only with org required ids (none in its fixtures) |
| `tests/acceptance/charter_pack_cutover/test_presets.py:57,140` | `activated` per kind, an org pack with `required_tactics` | yes if the tactics key is absent there; run it |
| `tests/acceptance/charter_pack_cutover/generate_golden_before.py:210` | `activated` per kind | golden generator; check its golden files |
| `tests/acceptance/charter_pack_cutover/test_cli_surface.py`, `test_gates_latency_messaging.py`, `test_rename_skills_glossary.py`, `test_project_pack_root.py` | invoke the command | run |
| `tests/specify_cli/migration/test_legacy_charter_gate.py`, `tests/cli/test_mission_agnostic_flag.py` | invoke the command | run |
| `acceptance-jvm/.../CharterSteps.java` | human output only | fixture fix (D2) |
| `docs/api/charter-commands.md` §`charter list --json` | contract text | update |
| `docs/context/charter.md`, `docs/architecture/activation-ledger-and-charter-contract.md`, `src/charter/activation/ERROR_CODES.md` | mention the command | check wording |

No `src/` code parses the `charter list --json` payload (hypothesis from the grep; no hit outside tests and docs).

## Red-first tests

1. Python CLI-level test through `charter list` (CliRunner) on the corrected fixture: absent
   directive key + org `required_directives` provided by the org pack: the table names the id
   and `--json` carries it in `activated` with `allow_list_present: false`. Red on `e28ddabf`.
2. Un-`@wip` `PR-CHARTER-GOVERNANCE-002` with the corrected fixture. The JVM suite needs Java 25;
   this container has OpenJDK 21 and the Adoptium download is refused by the egress proxy (403),
   so the Cucumber run cannot happen here (`acceptance-jvm/README.md` "Cloud sessions"); the
   nightly `acceptance-bdd` lane runs it. Test 1 backs it.

## Open questions for specify / plan

- Q1. Where availability comes from: reuse the `--all` scan (`list_available_detailed` over the
  full org chain) so the in-force claim and the availability view agree. (Plan.)
- Q2. A required id no layer provides on an absent-key row: show nothing, or a marker? Ruling 1
  says it must not be claimed in force; a "not provided by any layer" marker would be new
  surface. Default: not shown in the cell; doctor already reports the floor. (Specify.)
- Q3. `skill` row: report `allow_list_present: false` and the materialised floor ∩ availability,
  never the floor twice. (Plan.)
