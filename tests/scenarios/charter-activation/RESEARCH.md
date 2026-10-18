# Charter-activation scenario suite — grounding note

<!-- Not part of the behaviour description. Grounding record for the charter-ACTIVATION BDD suite,
the activation-layer companion to the offering suite's grounding note at ../charter/RESEARCH.md.
Promise-first (the fast charter tests and the live seams are read as EVIDENCE, never transcribed).
PROMISES.md is now a human-unratified proposal for QA #801, not a frozen contract. BINDINGS.md
records each scenario's actual binding shape and planned witness; every scenario remains @wip.
Updated: 2026-10-18. -->

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

The ordinary-default and minimal-preset scenarios must respect these separate per-kind and
mission-ledger facts. The original blanket "everything" and "only the minimal baseline" wording
was too broad. The offering suite already asserts the *skill exception*
(`PR-CHARTER-GOVERNANCE-001`); this proposal replaces the duplicate skill-absence scenario with
an actual adoption transition (one skill becomes effective/projected while its sibling does not).
The ordinary-pack extension scenario no longer repeats the offering-owned absence assertion.

## Features and the consumer outcome each states

| Folder | Consumer outcome |
|--------|------------------|
| `turning-governance-on-and-off/` | Adopting or retiring a rule changes what is in force; adopting one more never drops the rest; naming something that does not exist changes nothing. |
| `turning-off-keeps-the-rest-sound/` | Cascade retirement keeps a rule shared by another active choice, proves the retired choice actually left, and refuses to fabricate a list for an unrestricted kind. This is not a universal prohibition on direct retirement. |
| `brings-what-it-depends-on/` | Adopting a choice can bring what it depends on in one step, can be scoped, warns about what a bare adoption left out, and never offers to turn on something that cannot stand alone. |
| `provisioning-governance-packs/` | Pack mission-type/profile adoption changes real work, and non-requiring pack registration respects explicit restrictions. Four acquisition/composition drafts remain held for separate ownership review, not promoted into activation promises. Supply-order wording is scoped to same-layout collisions. |
| `the-default-governance-profile/` | Ordinary unrestricted defaults, adoption/project-tool projection of one selected skill, ordinary pack extension of the default, and a minimal preset limited to its governed keys. Maintainer-only policy remains held without a new activation ID. |

## For QA, when ratifying

- The grounding evidence above (FR/ADR, `src/charter/offering/*`, `src/charter/activation/*`, the
  preset files, the open-packs issues) is the raw material for the promise→contract ledger — read it,
  do not transcribe it into the scenario text.
- The provisioning and default-profile notes above include **forward-looking** tracks; those issue
  descriptions and current implementation are not ratification. BINDINGS.md separates grounded
  READY-TO-BIND engineering work from authority/ownership/policy holds. Missing vocabulary is not
  a product defect. Implement real witnesses for agreed cases, including documented product reds;
  never manufacture a fixture or stub assertion to remove WIP.
- **Overlap caveat (unchanged):** the skill exception and selection overlay are already asserted
  *through* the offering suite. This suite covers the lifecycle **verbs** and the **pack ecosystem**
  the offering suite excluded, not a re-assertion of those.

## Review corrections — 2026-10-18

The reviewed base is `0746bec30cbb473329d9a02333bafada716ecfd7`. The proposed sources still have
five files and 22 scenarios. Common setup is bound; every scenario-specific outcome step remains
unbound. The static per-case counts in BINDINGS.md are not executions. No acceptance pass/red,
ratifier, approved contract, new Product Promise or WIP promotion is claimed by this review.

### Starting states and non-noop witnesses

- A rule merely "not adopted" may already be effective under an absent-key default. Adoption
  now begins available-but-explicitly-inactive; retirement begins effective in an explicit set,
  with no independent team requirement keeping it effective.
- An unrestricted project has no additional available rule waiting outside its effective set.
  The preservation case explicitly adopts **one already-effective rule**, with at least one
  other effective rule that must survive. The effective-before set, not a shipped ID list, is
  the comparison baseline.
- Shared cascade retirement names two active sources and their shared target, and proves the
  retired source is gone. That defeats an always-no-op retirement while preserving the target.
- Cascade cases distinguish activatable references, out-of-scope references, and non-activatable
  template/assets. Scope applies to referenced **artifacts**, not their whole kinds. Independent
  review added an unrelated inactive artifact within a selected kind: whole-kind activation must
  fail that control. No-cascade warnings do not promise incomplete dependency sets are rejected.
- Skill adoption checks both effective membership and project-local tool projection. Independent
  review added before/after absence of the unselected sibling's tool entry: projecting both skills
  must fail even if the effective-set resolver lists only the selected one.
- Unknown-ID refusal is on a valid charter and a valid kind, distinct from offering-owned
  broken-charter refusal. The scenario also preserves the saved choices; exact English prose
  and CLI output bytes are not its contract.

### Provisioning/default contradiction, resolved by explicit state

The two original drafts used the same default Background but asserted incompatible universal
rules: provisioning changes nothing, yet ordinary newly available governance becomes effective.
Accepted ADR 2026-10-06-2 Decisions 1/2 and the cutover specification FR-002/003/019 resolve this:

- **A17:** explicitly restricted kinds, plus a new pack requiring no additional governance.
  Availability expands; effective selections stay restricted. New org requirements are excluded
  because their union is an existing offering-owned contract.
- **A20:** an unrestricted ordinary kind. A newly available ordinary rule becomes effective and
  existing effective rules remain. Skills and the separate mission-type ledger are not generalized
  into this default.
- **A22:** minimal governs its curated directives/tactics and mission-type entries; it does not
  restrict every other kind. Start with known extra directives/tactics effective, prove those
  non-required extras leave, and separately verify a known open-kind artifact remains effective.

These are source-supported corrections, not an agent decision to change product policy.

### Scope and authority holds

The four acquisition/composition cases and the maintainer-only case remain in source, WIP,
without proposed activation IDs. The source note's release-time re-vendor track (#3504) does
not establish a runtime fetch/install guarantee. #5243 describes the missing canonical external
pack lifecycle. #4984 reports a real fail-open problem, but doctor already failing is not the
required governed-consumer witness. This review did not reproduce #4984 at the reviewed base.

The chain specification
`kitty-specs/org-pack-chain-authority-01M4JXF5/spec.md` User Story 1 / NFR-005 preserves a
mixed-layout flat-wins exception; the layering case is therefore limited to same-layout
collisions instead of promising universal last-pack-wins behavior.

Two historical citation problems are deliberately not hidden:

1. `FR-014` in the original activation-layer specification is action-sequence activation, not
   the exact `requires`/`suggests` relation set. `cascade.py` currently traverses those relations,
   while activation-layer FR-007 / activate Behavior 7 ground generic reference propagation.
2. The kind-filtered cascade specification cites
   `2026-08-20-1-cascade-kind-complete-relation-set.md`, absent from this checkout. Its recorded
   operator ruling still grounds loud template/asset exclusion, but it does not recover that
   missing ADR. Recover the decision or get explicit human approval for the stronger relation-set
   wording before freezing A07.

ADR 2026-05-16-1 is overlay/merge authority, not the unknown-ID atomicity requirement. The
proposal instead names the historical activate contract's Behavior 2, the current documented
validation-before-commit rule, and the implementation as corroborating evidence. Historical
activate/deactivate contracts are cited only for relevant behaviors: their old default-list
seeding, old kind counts and literal upgrade remedy are superseded, not reinstated.

### Identity and ownership changes

Seven WIP scenario names change to correct their scope; no QA Markdown page is retired and no
`moved_to` is created:

| Case | Previous scenario name | Proposed source identity |
| --- | --- | --- |
| A03 | Adopting one more rule never drops the rules already in force | Explicitly adopting a rule preserves the unrestricted rules already in force |
| A07 | Adopting a choice can bring everything it depends on in one step | Adopting a choice can bring its required and suggested governance in one step |
| A10 | Adoption never offers to turn on something that cannot stand on its own | Adoption reports templates and assets as not independently activatable |
| A17 | Provisioning a pack does not by itself change what is in force | Provisioning a pack respects the project's existing restrictions |
| A18 | Before choosing anything, a project is governed by all the governance available to it | Before choosing anything, ordinary governance follows the unrestricted default |
| A19 | Shareable commands are the exception — they apply only when the charter asks for them | Adopting a shareable command brings it into force without adopting its sibling |
| A20 | Provisioning a pack extends the default without forcing its commands on every tool | Provisioning ordinary governance extends an unrestricted default |

Historical evidence retains its original path/name/digest; do not relabel it as results for these
revised assertions. A19 intentionally changes from an offering-owned absence assertion to a
positive activation/projection transition. This is a proposed contract change for review, not a
claim that the old and new tests are equivalent.

The proposed PR-* contract-ledger namespace follows the offering pattern. It is not PP-* Product
Promise ratification or a rename of either namespace. The 17 candidates, five holds, ratifier
questions and promotion boundary are all explicit in PROMISES.md and BINDINGS.md. Action-context
and broader atomicity remain deferred without inventing additional scenarios or duplicating
existing offering contracts.
