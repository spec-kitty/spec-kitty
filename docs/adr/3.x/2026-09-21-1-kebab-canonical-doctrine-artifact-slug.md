---
title: 'ADR: kebab-case canonical doctrine artifact slug — id/slug decoupling, single slug authority, manifest-driven bundle validation'
description: 'Kebab-case canonical slug for project doctrine artifacts, set by one slug_for authority and a manifest-driven bundle validator; id/slug decoupled, filename migration dropped.'
status: Accepted
date: '2026-09-21'
updated: '2026-09-21'
---

## Context and Problem Statement

Mission `doctrine-slug-canonicalization-01M31SP9`. Project-registered doctrine artifacts
(directives, tactics, styleguides, procedures, agent profiles) are written to disk by
three independent surfaces: the scaffolder (`author_guidance()`), the registration
engine (`project_registration.py`, `commit_project_registration()`), and the bundle
validator (`charter bundle validate`, `src/charter/offering/drg/bundle.py`). Each surface
derived a project directive's on-disk slug/filename independently, and the derivations
disagreed:

- The registration engine writes a directive's provenance sidecar as
  `<kind>-<kebab-slug>.yaml`, computed inline at `project_registration.py:187` as
  `quote(identifier.lower().replace("_", "-"), safe="")` for directives.
- The bundle validator's filename parser expected a different shape and reported **2
  errors per project directive** validated (#4832) — the engine's own kebab-slug output
  did not round-trip through the validator's independent parse.
- The validator's recognised-kind table (`_KIND_SUFFIX`/`_ALL_ARTIFACT_PATTERNS`) covered
  only 3 of the 5 kinds the engine actually writes sidecars for, so it also rejected the
  engine's own `agent_profile` sidecars outright (#4833) — and `procedure` was a latent
  identical twin of the same bug, not yet reported but structurally present.

No single module owned "what is the canonical slug for artifact kind K and identifier
ID" — each consumer re-derived it, and the derivations silently diverged
(DIRECTIVE_043: canonical-source-unification violation). `charter bundle validate` was,
in effect, validating against a slug convention none of the writers implemented.

## Decision

### D1 — Kebab-case is the canonical slug; `id` is preserved and formally decoupled from slug

The on-disk filename/slug for a project-registered artifact is `kebab(id)` (for
directives: lowercased, `_` → `-`, URL-quoted); the authored `id` (SCREAMING-case for
directives, e.g. `LOVE_THY_ENEMY`) is preserved inside the file as canonical identity.
`id` and slug are formally decoupled: `id` is identity, slug is a derived on-disk handle.
The built-in precedent (`disciplined-refactoring.directive.yaml` ↔
`id: DISCIPLINED_REFACTORING`) demonstrates that shipped built-ins already decouple a
human slug from the authored id — `025-boy-scout-rule.directive.yaml` ↔
`id: DIRECTIVE_025` is a *descriptive* slug, not an instance of mechanical `kebab(id)`
(`kebab("DIRECTIVE_025")` would be `directive-025`), so the built-in `NNN-`/descriptive
naming convention is not extended to project artifacts — `slug_for` governs only the
project-registration path.

### D2 — Single `slug_for(kind, id)` authority, preserving the engine's URL-encoding

One pure `slug_for(kind, identifier)` function (`src/charter/offering/artifact_kinds.py`,
beside `_PATTERNS`) is the sole slug-derivation authority, consumed by both the
scaffolder and the registration engine. It is extracted verbatim from the engine's
existing inline expression and **preserves `quote(…, safe="")`**: directive identifiers
lowercase/underscore-to-hyphen then URL-quote; other kinds URL-quote as-is. Dropping the
`quote()` wrap (an early draft's "verbatim kebab" framing) would reintroduce a
provenance-directory path escape for a namespaced identifier such as
`agent_profile:team/ops-responder` and regress the existing guard at
`tests/charter/test_project_registration.py:165-166`; `quote()` is a no-op on
kebab/SCREAMING identifiers, so directives are unaffected by keeping it.

### D3 — Recognised-kind set derives from one importable `DIRECT_WRITE_KINDS` constant

The validator's kind table is extended from 3 to the full 5 registration-writing kinds
(`directive, tactic, styleguide, procedure, agent_profile`; `agent_profile` →
`.agent.yaml`), fixing #4833. The kind list itself is minted once as a module-level,
importable `DIRECT_WRITE_KINDS` constant (previously a function-local tuple), and every
consumer — the scanner, the manifest's artifact-kind `Literal`, and the validator's kind
table — derives from that one constant, with a parity test asserting agreement. This
closes the drift class by construction rather than by convention.

### D4 — Hybrid manifest-driven bundle validation

The validator resolves *registered* artifacts through the synthesis manifest's
`(kind, slug, path, provenance_path)` records — which the manifest already captures for
every direct-write artifact, requiring no writer extension — and **retains** the
filesystem walk plus filename parse for the orphan/legacy direction (an on-disk artifact
or sidecar absent from the manifest). A purely manifest-driven validator cannot detect
that class of corruption, so the hybrid shape is deliberate: manifest lookup for positive
resolution of registered artifacts, disk sweep for orphans.

### D5 — Migration dropped: go-forward-only

No filename migration or self-heal ships with this change. Existing repositories with
SCREAMING-case (or otherwise non-canonical) artifact filenames validate green under D4
purely because the manifest — not the filename — is now the resolution path for
registered artifacts, with authored files left untouched. A rename was rejected because
it is cosmetic (the manifest already carries the kebab slug regardless of on-disk
filename, so D3+D4 alone fix #4832 for existing repositories) and because renaming an
artifact's file stem is not safe: `activated_directives` keys off the file stem
(`kind_vocabulary.py:434`), so a hand-authored directive whose stem does not equal its id
would be silently dropped from the activated set on rename (the #3816 failure class). A
migration would also invert the registration module's "never mutate authored source"
invariant and require clobber/dirty-tree/crash-atomicity engineering with no existing
mechanism to lean on. Dropping the migration removes this dormant risk entirely for zero
loss of the green-validate outcome.

### D6 — `#4834` kept as an independent correctness fix

The `_registration_records` path/provenance-drift re-write (the early-`continue` at
`project_registration.py:195`) is kept, no longer as a migration precondition but as a
standalone fix: it guards the manifest against recording a stale path when an artifact's
content is unchanged but its path has drifted.

## Consequences

**Positive:**

- New project artifacts are born validate-clean under the canonical slug convention —
  the scaffolder, engine, and validator now agree by construction.
- Existing repositories with SCREAMING-filename directives validate green through the
  manifest without any rename, so the fix is non-disruptive to established projects.
- The drift class between the three surfaces is closed by construction (DIRECTIVE_043):
  a sixth registration-writing kind added later must be added to `DIRECT_WRITE_KINDS`
  once, and the parity test fails if any consumer is missed.
- `#4834`'s stale-path/provenance drift is fixed independently of the slug convention
  work, closing a latent manifest-correctness gap.

**Trade-offs / follow-ups:**

- A pre-existing repository's on-disk filenames remain non-canonical (SCREAMING-case)
  indefinitely unless an operator renames them by hand; this is accepted rather than
  automated, per D5's rationale.
- The bundle validator's orphan/legacy-direction filesystem walk still relies on
  filename parsing (D4), so a legacy artifact with an unparseable filename is reported
  as an orphan rather than resolved — an accepted, pre-existing limitation of the
  filesystem-walk path, not introduced by this change.

Both the post-plan brownfield adversarial point-cut (3 profile-loaded lenses:
architect-alphonso, debugger-debbie, reviewer-renata) and the post-tasks anti-laziness
point-cut (reviewer-renata, paula-patterns) reviewed this design; every contested
finding was folded into a decision or an explicit accepted-with-rationale disposition —
see `research.md` § Adversarial evidence for the full findings/disposition table (no
finding silently dropped).

## Alternatives Considered

- **Unquoted "verbatim kebab" `slug_for`.** Rejected — reintroduces a provenance-
  directory path escape for namespaced identifiers (CRITICAL, 3-lens convergent
  adversarial finding); see D2.
- **Filename migration/self-heal on validate or upgrade.** Rejected — cosmetic given D4
  alone fixes #4832 for existing repos, and unsafe: risks silently dropping stem-keyed
  directive activations (#3816 class) and inverts the "never mutate authored source"
  invariant with no existing clobber/atomicity mechanism; see D5.
- **Exempting engine-written kinds from the validator's kind check instead of extending
  the table.** Rejected — would silently disable orphan detection for those kinds.
- **Purely manifest-driven bundle validation (drop the filesystem walk entirely).**
  Rejected — cannot detect an on-disk artifact or sidecar absent from the manifest,
  which is exactly the orphan/ghost corruption class the validator exists to catch.

## References

- Mission `kitty-specs/doctrine-slug-canonicalization-01M31SP9/`: `research.md`
  (Decisions 1–6, § Adversarial evidence — post-plan brownfield and post-tasks
  anti-laziness point-cuts), `spec.md` (FR-004, FR-005, FR-008, NFR-002, NFR-004).
- Issues: #4832 (validator false-positive on project directives), #4833 (validator
  rejects engine's own `agent_profile` sidecars; `procedure` a latent twin), #4834
  (`_registration_records` path/provenance drift), #3816 (stem-keyed activation drop
  class the dropped migration would have risked), #2519 (convergence note).
- Implementation: `src/charter/offering/artifact_kinds.py` (`DIRECT_WRITE_KINDS`,
  `slug_for`), `src/charter/offering/drg/project_scan.py`, `src/charter/activation/
  synthesizer/manifest.py`, `src/charter/offering/drg/bundle.py`,
  `src/charter/activation/project_registration.py`.
- Directive: DIRECTIVE_043 (canonical-source-unification).
