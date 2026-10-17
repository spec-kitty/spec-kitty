# Charter-activation scenario suite — grounding note

<!-- Not part of the behaviour description. Grounding record for the charter-ACTIVATION BDD suite,
the activation-layer companion to the offering suite's grounding note at ../charter/RESEARCH.md.
Promise-first (the fast charter tests and the live seams are read as EVIDENCE, never transcribed).
The frozen promise->contract map is QA's to author and ratify (spec-kitty-qa#801); until then every
scenario carries @wip. Updated: 2026-10-17. -->

This note records the grounding for the charter-**activation** outcome features under
`tests/scenarios/charter-activation/`. The suite exists to give the **activation** entry-point seam
(`charter.activation.api`) the same consumer-outcome contract net the **offering** seam already has
(`../charter/`, `Refs #6286`), ahead of the charter package/repository extraction (ADR
`2026-10-12-2`, epic **#6099**). The offering suite deliberately excluded activation ("the activation
layer extracts later"); this suite is that net.

## Why this matters now — the open-packs / offering extraction

The pack-ecosystem features (`provisioning-governance-packs/`, `the-default-governance-profile/`)
are authored **forward-looking**: they describe the behaviour that the extraction tracks are moving
toward, so the consumer contract survives the repo split. The tracks, all open:

| Issue / ADR | Track | Status |
|---|---|---|
| **#3504** (ADR `2026-08-16-2`, Option B) | **Re-vendor pipeline**: a release-time CI step checks out a **pinned + checksummed** `spec-kitty-open-packs` ref and copies it into `packs/built-in/` **before `hatch build`**, so the wheel force-includes byte-identical content and `resolve_pack_root("built-in")` is unchanged. Consumer install unchanged; only *provenance* moves. The chosen near-term path. | open |
| **#3022** (ADR-1 Option C) | **Runtime-fetch externalization**: built-in becomes an externally-*fetched* pack at runtime (`pack_roots` / `OrgPackMissingError`), resolved through the *same* public seam a customer's org pack already uses. Deferred north-star, pending the manifest/checksum work. | open |
| **#6099** (ADR `2026-10-12-2`) | **Extract the charter offering layer** to its own version-locked, independently-released repository, consumed only via `charter.offering.api` / `charter.activation.api`; grow the layer-rule / import-boundary gates to treat `charter` as an external contract package (like `spec-kitty-events` / `spec-kitty-tracker`). GA-gating. | open |
| **#5243** | External org packs lack a canonical **install / update / uninstall** lifecycle. | open |
| **#4984** | A configured-but-missing org pack currently **fails open** across governed consumers — the provisioning promise is that it must **fail closed** (see scenario "A pack the system cannot resolve is refused, not treated as empty"). | open (bug) |
| **#2466 / #5193 / #3505** | Pack ecosystem; pack skills (ADR `2026-09-27-1`); explicit opt-in for the maintainer/internal pack (ADR-2 — never auto-seeded). | open |

**What #3504 (the chosen path) needs to land:** (1) a release-time pipeline that checks out a pinned
open-packs ref recorded in-repo and **verifies it by checksum** before use; (2) copies the pinned
tree into `packs/built-in/` **before `hatch build`**; (3) runs the parity/corpus gates
(`test_packaging_parity.py`, `.github/workflows/packs.yml`) **after** the vendor step; (4) a local
`materialize` path so contributor checkouts can populate `packs/built-in/`; (5) the invariants held
throughout — `packs/internal/` never ships (`test_packaging_safety.py`), built-in stays byte-identical
in every consumer install, and no packaging code/gates change for the source-location move.

## Provisioning — the seams a pack resolves through (evidence, read not transcribed)

- **Resolve a pack tier's root, fail-closed.** `resolve_pack_root(tier, org_root, project_root)`
  (`src/charter/offering/pack_paths.py`) returns an existing directory for `built-in` / `org` /
  `project`, and raises `PackRootNotFound` rather than falling open to an arbitrary tree.
- **Declare a pack.** An org pack is configured in `.kittify/config.yaml` under
  `charter_packs.org.packs` as an `OrgPackConfig` (`src/charter/offering/drg/org_pack_config.py`):
  a **local filesystem path** (with `$ENV` expansion and an optional `subdir`), or a **published
  reference** fetched into a local snapshot (`src/specify_cli/charter_packs/snapshot.py` + the fetch
  CLI). Every pack declares its level in `pack.yaml` (`pack_level`, ADR `2026-10-11-2`); loading
  refuses a level that disagrees with where it is configured.
- **Load it, fail-closed.** `load_org_pack(pack_name, pack_root, layer_index)`
  (`src/charter/offering/drg/org_pack_loader.py`) reads `<pack_root>/drg/fragment.yaml` and raises
  `OrgPackMissingError` when the root or fragment is absent. Later-declared packs layer over earlier
  ones (operator-authoritative fields win).

## The minimal / default activation profile (evidence)

What a project is governed by **before it turns anything on** is two related facts:

1. **The absent-key default.** `ArtifactKind.effective_when_absent`
   (`src/charter/offering/artifact_kinds.py`, FR-005) is `"all"` for every kind except `SKILL`, and
   `"required"` for `SKILL` (`_REQUIRED_WHEN_ABSENT_KINDS == {SKILL}`). So a kind whose activation key
   is absent is **unrestricted** — every available artifact of that kind (built-in + any resolved
   org pack) is in force — except **skills**, where only the org packs' `required_skills` (plus
   built-in skill defaults, empty at MVP) are in force. This is why registering a pack never silently
   adds N commands to every tool (ADR `2026-09-27-1` / #5193).
2. **The two named baselines are activation presets the built-in pack ships** (ADR `2026-10-06-2`,
   `packs/built-in/presets/{default,minimal}.yaml`, applied with `charter activate --preset <name>`):
   - **`default`** lists no ids and carries no kind gate, so it leans on rule (1): every built-in
     artifact is effective and all four built-in mission types (`software-dev`, `documentation`,
     `research`, `plan`) activate. New built-in artifacts are effective without editing the preset.
   - **`minimal`** curates a small set of foundational directives and tactics and activates only
     `software-dev`; every other kind carries no key, so it stays unrestricted until the project
     narrows it. A deliberately small baseline for a project that does not run the full interview.
   - The **maintainer/internal** org pack is never auto-seeded; in force only on explicit opt-in
     (#3505, ADR-2).

This suite's `the-default-governance-profile/` feature is the consumer reading of these facts; the
offering suite already asserts the *skill exception* half (`PR-CHARTER-GOVERNANCE-001`), so this
suite owns the lifecycle reading — "what is in force before I choose anything, and how provisioning
a pack changes it" — not a re-assertion of the offering promise.

## Features and the consumer outcome each states

| Folder | Consumer outcome |
|--------|------------------|
| `turning-governance-on-and-off/` | Adopting or retiring a rule changes what is in force; adopting one more never drops the rest; naming something that does not exist changes nothing. |
| `turning-off-keeps-the-rest-sound/` | Retiring a choice keeps anything still relied on (and names why), and refuses — with the way forward — on a kind never put under explicit control. |
| `brings-what-it-depends-on/` | Adopting a choice can bring what it depends on in one step, can be scoped, warns about what a bare adoption left out, and never offers to turn on something that cannot stand alone. |
| `provisioning-governance-packs/` | The backend is supplied with packs that resolve through public seams (a filesystem location or a published reference); an unresolvable pack is refused, never treated as empty; several packs layer in supply order; and a configured pack's parts are brought into force deliberately, changing what the runtime offers (a mission type the project can run, a profile that applies). |
| `the-default-governance-profile/` | Before a project turns anything on it is governed by all the governance available to it, except shareable commands, which apply only when the charter requires or selects them; maintainer-only governance is in force only on explicit opt-in; and a project may instead start from the small curated `minimal` baseline. |

## For QA, when ratifying

- The grounding evidence above (FR/ADR, `src/charter/offering/*`, `src/charter/activation/*`, the
  preset files, the open-packs issues) is the raw material for the promise→contract ledger — read it,
  do not transcribe it into the scenario text.
- The provisioning and default-profile features are **forward-looking**: some of their steps describe
  behaviour the extraction tracks are still landing (#3504/#3022/#6099). Bind a step only once the
  seam it witnesses is real; until then `@wip` keeps the promise captured without gating.
- **Overlap caveat (unchanged):** the skill exception and selection overlay are already asserted
  *through* the offering suite. This suite covers the lifecycle **verbs** and the **pack ecosystem**
  the offering suite excluded, not a re-assertion of those.
