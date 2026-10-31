# Research — glossary-residue-three-senses-01M66977

Grounding for issue spec-kitty/spec-kitty#6759, captured 2026-10-30 on
`main`@512567ee (branch `issue-6759-glossary-residue`).

## Decisions

1. **The issue reproduces on current main.** `grep -rn "residue" docs/context/`
   returns exactly one hit, an unrelated prose use in `team-kitty.md` ("The word
   survives only as residue in identifiers…"). No glossary entry exists for the
   Mission-directory sense, while the three code senses are live:
   - `is_kitty_specs_residue` — `src/specify_cli/context/mission_resolver.py:543`
     (write seam; #6627/#6668/#6669; a `spec.md` on disk keeps a folder out of
     residue so the upgrade sweep can repair it; #6680 is the issue's cited
     follow-up reference for the write-seam sense).
   - `RESIDUE_DIRECTORY` — `src/specify_cli/audit/models.py:35`, emitted by
     `src/specify_cli/audit/engine.py` (`_scan_missions` → `_residue_result`)
     when `not is_mission_dir` (#5812; FR-008 of #5875 keeps the engine on the
     looser rule).
   - `not is_selectable_mission_dir` —
     `src/specify_cli/context/mission_resolver.py:459`, consumed by
     `src/specify_cli/status/identity_audit.py` (`doctor identity` residue
     states, #5875 operator ruling 2026-10-27): no `meta.json`; untracked
     id-less `meta.json` in a git repository; unreadable `meta.json`.
2. **Not superseded.** `git log -S` shows the senses landed via merged PRs for
   #5875, #5812, #6669, #6627; `docs/changelog/CHANGELOG.md` has Unreleased-era
   entries for #5875/#6669/#6627 describing the three rules but no glossary
   entry; no open PR titles match "residue". Issue #6759 is open, was
   unassigned, and is now claimed (Ivan-Melck, `status:claimed`,
   `taken-by-human`).
3. **Home for the entry: `docs/context/orchestration.md`.** The sibling
   overloaded-term disambiguations live there (`### PRIMARY partition`, `###
   Lane Consolidation`, `### Routing`, `### The drain`), the issue names this
   the same footgun class as `primary`/`merge`/`routing`, and the Mission
   classification senses (selection / write seam / audit) are orchestration
   context. Anchor will be `#residue`.
4. **Test model.** `tests/docs/test_artifact_placement_seam_page.py` already
   pins the `Routing` disambiguation structurally (presence, sense names,
   guards) — the new test follows that shape in `tests/docs/`, red-first on the
   planning base.
5. **Contextive regeneration is in scope.** `orchestration` is a
   Contextive-mapped context (`.kittify/traceability/contextive-map.yaml`,
   scopes `src/specify_cli/status` and `src/specify_cli/consolidation`), so
   adding a term requires regenerating the committed
   `src/specify_cli/.contextive/orchestration.yml`
   (`scripts/generate_contextive_glossaries.py generate`); its `check` mode
   must stay green.
6. **AGENTS.md Terminology Canon gets one bullet.** The canon flags
   `primary`/`merge`/`routing` footguns with links into the glossary; a residue
   bullet there makes the entry discoverable from the dev guidelines. The
   glossary stays the single authority (C-001).

## Evidence

- Issue body and code sites quoted above; docstring links already in `src/`
  use the relative form (e.g. `src/specify_cli/state/contract.py:137`
  ``Glossary: ``docs/context/orchestration.md#target-owned-bookkeeping``.``).
- Existing entry schema: `docs/context/glossary-conventions.md` (Definition /
  Context / Status / Applicable to; optional `Do NOT use when`, `Related
  terms`, `Note`).
- Style: `styleguide:kitty-glossary-writing` (clear not clever; functional
  over compositional; HiC-consistent; no implementation leaking beyond the
  owning-symbol citations the sibling entries carry).

## Open questions

- None blocking. (Placement after `### The drain` in orchestration.md keeps
  the disambiguation cluster together; plan confirms.)
