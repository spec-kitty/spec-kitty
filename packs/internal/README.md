# `spec-kitty-internal` — org-tier doctrine pack (NOT shipped to consumers)

This is Spec Kitty's own **internal** doctrine pack: the doctrine that governs
*contributors, maintainers, and the core team* of the Spec Kitty project itself.
It is loaded as an **org-tier** pack (registered in `.kittify/config.yaml` under
`doctrine.org.packs`), overlaying the public `packs/built-in/` product doctrine.

## Why this is a separate pack — and why it is NOT built-in

- The `built-in` tier (`packs/built-in/`) is the **public product doctrine** that
  ships to every consumer via the PyPI wheel. It is single-rooted and resolved by
  a kernel ancestor-walk (`kernel.sibling_paths.resolve_installed_sibling`), so it
  **cannot** host a second pack.
- Maintainer-only doctrine (how *we* land PRs, process the tracker, keep main
  honest, run our internal glossary) must **not** be force-shipped to consumers.
  It is therefore an **org pack**, and `pyproject.toml` narrows the wheel/sdist
  `packs` include to `packs/built-in/` specifically so this tree never ships.
  `tests/cross_cutting/packaging/test_packaging_safety.py` guards that boundary.

## Layout (org-tier shape — differs from `built-in`)

```
packs/internal/
├── org-charter.yaml                                 # pack name, skill_namespace (kitty) + required_* activation lists
├── drg/fragment.yaml                                # SINGLE DRG fragment (org tier), not sharded *.graph.yaml;
│                                                    #   declares every node and edge below
├── directives/
│   ├── operator-signal-contract.directive.yaml      # OPERATOR_SIGNAL_CONTRACT — a path that decides must also signal
│   └── no-full-heavy-suites-in-mission.directive.yaml  # NO_FULL_HEAVY_SUITES_IN_MISSION — no full architectural/e2e/perf/test-full runs during mission work
├── skills/
│   ├── land-pr.skill.yaml                           # kitty-land-pr: thin entry point to landing-contributor-prs
│   ├── issue-triage.skill.yaml                      # kitty-issue-triage: thin entry point to issue-triage-pass
│   ├── mission-from-issue.skill.yaml                # kitty-mission-from-issue: thin entry point to issue-to-mission-delivery
│   ├── report-debrief.skill.yaml                    # kitty-report-debrief: thin entry point to executive-debrief-generation
│   └── *.skill.md                                   # their prompt bodies (goal, inputs, ordered pointers, stop conditions)
├── glossary_packs/
│   └── spk-internal.glossary-pack.yaml              # spk-internal-glossary — maintainer/engineering glossary
├── procedures/
│   ├── landing-contributor-prs.procedure.yaml       # maintainer PR-landing runbook (behind kitty-land-pr)
│   ├── issue-triage-pass.procedure.yaml             # orchestrated batch triage of open issues (behind kitty-issue-triage)
│   ├── issue-to-mission-delivery.procedure.yaml     # issues to a green, ready-for-review PR (behind kitty-mission-from-issue)
│   ├── memory-curation-and-escalation.procedure.yaml  # agent-memory curation and escalation
│   ├── project-evolution-postmortem.procedure.yaml  # cycle postmortem: research squads + branded report
│   ├── test-suite-quality-assessment.procedure.yaml # static triage, domain review squads, shrink-only follow-through
│   ├── executive-debrief-generation.procedure.yaml  # collect, synthesize, render and hand over a debrief (behind kitty-report-debrief)
│   ├── cloud-session-dispatch.procedure.yaml        # hand tracker issues to an autonomous cloud runner (behind spk-dispatch-cloud)
│   ├── spec-kitty-arch-gate-adjudication.procedure.yaml  # refines built-in post-merge-arch-gate-adjudication
│   └── spec-kitty-red-main-policy.procedure.yaml    # refines built-in red-main-release-discipline
├── styleguides/
│   ├── executive-debrief.styleguide.yaml            # house style for executive debriefs (refines report-writing)
│   ├── report-writing.styleguide.yaml               # audience-first, anti-AI-prose, Spec Kitty voice
│   ├── spec-kitty-docs-lint-config.styleguide.yaml  # this repo's docs structural-lint config (refines common-docs)
│   ├── spec-kitty-package-tiers.styleguide.yaml     # this repo's package-to-tier map (refines tiered-standards)
│   └── spec-kitty-tracker-labels.styleguide.yaml    # this repo's label scheme (refines planning-and-tracking)
├── tactics/
│   ├── branded-deliverable.tactic.yaml              # when and how to produce a branded document
│   ├── spec-kitty-gate-non-vacuity-exemplar.tactic.yaml  # exemplar audit (refines architectural-gate-non-vacuity)
│   └── spec-kitty-ratchet-cost.tactic.yaml          # ratchets cost CI money on every run (refines frozen-baseline-shrink-only-ratchet)
├── toolguides/
│   ├── branded-document-generation.toolguide.yaml   # the branded-PDF pipeline manifest
│   ├── BRANDED_DOCUMENT_GENERATION.md               # its how-to guide
│   ├── terminology-guard.toolguide.yaml             # this repo's legacy-terminology test (moved from built-in)
│   ├── TERMINOLOGY_GUARD.md                         # its how-to guide
│   ├── test-quality-triage.toolguide.yaml           # how to run the test-quality scanner
│   └── TEST_QUALITY_TRIAGE.md                       # its how-to guide (flag codes, outputs, false positives)
└── assets/
    ├── spec-kitty-branded-pdf.py                    # the Markdown -> branded-PDF generator
    ├── spec-kitty-branded-pdf.py.asset.yaml         # its asset sidecar
    ├── test-quality-scan.py                         # static test-quality triage (runs no tests)
    ├── test-quality-scan.py.asset.yaml              # its asset sidecar
    ├── validate-pr-body.py                          # PR-body contract validator (five sections, git-grep discovery check)
    ├── validate-pr-body.py.asset.yaml               # its asset sidecar
    └── debrief/                                     # executive-debrief tooling; the template loads logo.png and fonts/ by relative path
        ├── collect-debrief.py                       # deterministic GitHub facts as one JSON document (debrief-collector)
        ├── render-debrief.py                        # one-pager renderer with the reference guard (debrief-renderer)
        ├── debrief-template.html                    # one-pager HTML template (debrief-template)
        ├── logo.png                                 # Spec Kitty logo (debrief-logo)
        ├── fonts/FallingSky-{Regular,Bold,Extrabold}.otf  # display face (debrief-font-falling-sky-*)
        └── *.asset.yaml                             # one sidecar per file above
```

Asset sidecar `path` values are relative to this `assets/` folder (org-tier
anchor), so `spec-kitty doctrine asset path <id>` resolves them to a real file.
The debrief files sit in a `debrief/` subfolder so the template's relative links
to the logo and fonts keep working.

The `project-evolution-postmortem` procedure `suggests` the `report-writing`
styleguide and the `branded-deliverable` tactic; the tactic `requires` the
`branded-document-generation` toolguide, which `requires` the
`spec-kitty-branded-pdf` asset — one authoring chain, wired in `drg/fragment.yaml`.

The `test-suite-quality-assessment` procedure `requires` the
`test-quality-triage` toolguide, which `requires` the `test-quality-scan`
asset, and it `suggests` the built-in test doctrine it applies
(`test-desiderata-and-boundaries`, `testing-principles`, `DIRECTIVE_041`,
`development-assist-test-cleanup`, `adversarial-squad-deployment`). Kick off a
run with `make test-quality-scan`.

## Pack skills

The four skills in `skills/` are the team-shared maintainer commands. Each is a thin
entry point that carries no doctrine of its own: a `requires` edge in
`drg/fragment.yaml` points it at the procedure that holds the rules, and the rendered
`SKILL.md` tells the agent to load that procedure with
`spec-kitty charter context --include <urn>`. The namespace is `kitty`, so they
render as `kitty-land-pr`, `kitty-issue-triage`, `kitty-mission-from-issue` and
`kitty-report-debrief`, and `required_skills` puts all four in force for every project that registers this pack.
See [Create and activate a pack skill](../../docs/development/how-to/create-a-pack-skill.md).

## Reference, don't duplicate

Built-in doctrine is repository-agnostic; the Spec Kitty specifics of a
built-in artifact live here in a node that **refines** it (the `spec-kitty-*`
nodes above, #5203), rather than re-authoring the built-in artifact. A
shrink-only census (`tests/architectural/test_builtin_pack_provenance_ratchet.py`)
fails when new repo-local paths or provenance tokens (issue numbers, WP/FR ids)
land in `packs/built-in/`. Only genuinely
repo-only residue (PR-landing specifics, the internal glossary, the
maintainer-only `OPERATOR_SIGNAL_CONTRACT` and `NO_FULL_HEAVY_SUITES_IN_MISSION`
directives) is authored here. `NO_FULL_HEAVY_SUITES_IN_MISSION` itself
`refines` the built-in `no-parallel-duplicate-test-runs` tactic and
`red-main-release-discipline` procedure rather than re-authoring their
test-run and red-main substance.

> First-step scaffold. See the initiative synthesis for the deferred decisions
> (built-in ownership inversion, open-packs as the permanent home, private-vs-public
> reconciliation with catalog pack #16 `spec-kitty-internal`).
