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
├── org-charter.yaml                                 # pack name + required_* activation lists
├── drg/fragment.yaml                                # SINGLE DRG fragment (org tier), not sharded *.graph.yaml;
│                                                    #   declares every node and edge below
├── directives/
│   ├── operator-signal-contract.directive.yaml      # OPERATOR_SIGNAL_CONTRACT — a path that decides must also signal
│   └── no-full-heavy-suites-in-mission.directive.yaml  # NO_FULL_HEAVY_SUITES_IN_MISSION — no full architectural/e2e/perf/test-full runs during mission work
├── glossary_packs/
│   └── spk-internal.glossary-pack.yaml              # spk-internal-glossary — maintainer/engineering glossary
├── procedures/
│   ├── landing-contributor-prs.procedure.yaml       # maintainer PR-landing runbook
│   └── project-evolution-postmortem.procedure.yaml  # cycle postmortem: research squads + branded report
├── styleguides/
│   └── report-writing.styleguide.yaml               # audience-first, anti-AI-prose, Spec Kitty voice
├── tactics/
│   └── branded-deliverable.tactic.yaml              # when and how to produce a branded document
├── toolguides/
│   ├── branded-document-generation.toolguide.yaml   # the branded-PDF pipeline manifest
│   └── BRANDED_DOCUMENT_GENERATION.md               # its how-to guide
└── assets/
    ├── spec-kitty-branded-pdf.py                    # the Markdown -> branded-PDF generator
    └── spec-kitty-branded-pdf.py.asset.yaml         # its asset sidecar
```

The `project-evolution-postmortem` procedure `suggests` the `report-writing`
styleguide and the `branded-deliverable` tactic; the tactic `requires` the
`branded-document-generation` toolguide, which `requires` the
`spec-kitty-branded-pdf` asset — one authoring chain, wired in `drg/fragment.yaml`.

## Reference, don't duplicate

A lot of maintainer-flavoured doctrine already ships in `packs/built-in/`
(`red-main-release-discipline`, `tracker-organisation-workflow`,
`pr-agent-worktree-isolation`, `mission-tracer-files`, …). This pack **references**
those via DRG `refines` edges rather than re-authoring them. Only genuinely
repo-only residue (PR-landing specifics, the internal glossary, the
maintainer-only `OPERATOR_SIGNAL_CONTRACT` and `NO_FULL_HEAVY_SUITES_IN_MISSION`
directives) is authored here. `NO_FULL_HEAVY_SUITES_IN_MISSION` itself
`refines` the built-in `no-parallel-duplicate-test-runs` tactic and
`red-main-release-discipline` procedure rather than re-authoring their
test-run and red-main substance.

> First-step scaffold. See the initiative synthesis for the deferred decisions
> (built-in ownership inversion, open-packs as the permanent home, private-vs-public
> reconciliation with catalog pack #16 `spec-kitty-internal`).
