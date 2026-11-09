# Research: Docsite shared build definition

Grounding: [research/code-grounding.md](research/code-grounding.md).

## R-1: Composite action or reusable workflow

- **Decision:** reusable workflow (`on: workflow_call`).
- **Rationale:** #6936 adds a job-level `services:` PlantUML container; a composite action runs inside the caller's job and cannot declare `services:`. A reusable workflow owns its job, so the container, Playwright install and timeout live with the build. Operator decision 2026-11-09 (Decision Moment `01M70VNZ46K3BZR8WVHJ81CWR0`).
- **Alternatives considered:** composite action + a copied `services:` block in every caller (two copies of a pinned image digest: rejected, single authority); keeping the steps inline and duplicating them into the deploy at #6938 (rejected, D-11).

## R-2: Does the gate still see the build?

- **Decision:** keep the caller job key `docs-site` and its display name; the called job is named `build`.
- **Rationale:** `scripts/ci/router_gate.py:111-127` classifies every row of the run, not just `needs:`. GitHub reports a called job as `<caller name> / <callee name>`, so the build's row is `docs site (doc-kitty build) / build` and blocks on any non-success conclusion. `router-gate.needs` still lists `docs-site`, so `needs` waits for it. The `needs:`-equals-all-jobs invariant (`test_dual_mode_contract.py`) is over job keys and still holds.
- **Alternatives considered:** adding the row name to an allowlist (rejected: no allowlists, and none is needed).

## R-3: The deploy-reuse input

- **Decision:** one boolean input `pages-artifact` (default `false`). `false`: `actions/upload-artifact` of `site/dist` as `docs-site-<run_attempt>` (as today). `true`: `actions/upload-pages-artifact` of `site/dist` (the `github-pages` artifact `actions/deploy-pages` consumes); the plain upload is skipped.
- **Rationale:** the deploy needs the Pages artifact format; everything before the upload is identical. Upload needs no extra permission.
- **Alternatives considered:** always upload both (doubles artifact storage on every PR); let the deploy re-download and re-upload (an extra job hop and a second definition of the upload).

## R-4: Supply chain

`actions/upload-pages-artifact` v5.0.0 = `fc324d3547104276b827a68afc52ff2a11cc49c9` (`git ls-remote https://github.com/actions/upload-pages-artifact refs/tags/v5.0.0`; the `v5` tag points at the same commit). First-party GitHub action, already used (tag-pinned) by `docs-pages.yml`. No package-manager changes.
