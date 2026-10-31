# Research: Optional companion services wheel

The full read-only research is in
[`docs/plans/events-domain-move/companion-wheel-research.md`](../../docs/plans/events-domain-move/companion-wheel-research.md).
Its twelve recommendations were ruled "all as recommended" by the operator on 2026-10-31
(Decision Moment `01M694BE2Z24AWM044Y2EQT83S`). This file records only the decisions taken at plan time.

## R-1: How the exact `services` extra resolves in `uv.lock`

- **Decision:** make `packages/spec-kitty-services` a uv workspace member
  (`[tool.uv.workspace] members` plus `[tool.uv.sources] spec-kitty-services = { workspace = true }`).
  Ruled A by the operator on 2026-10-31 (Decision Moment `01M694GPQYVGRKCF3B582FWQ1Y`).
- **Rationale:** reproduced in a scratch project. Without a source, `uv lock` fails with
  "requirements are unsatisfiable", because the companion of version X is never on PyPI at
  release-commit time. With a workspace member, uv resolves it from static `[project]`
  metadata without running a build. The published CLI wheel metadata still carries
  `spec-kitty-services==X; extra == "services"`.
- **Alternatives:**
  - Drop the extra: this reverses ruling 2.
  - Use a range: this breaks the exact lock (ruling 3).
  - Publish a placeholder first: not possible for every release.

## R-2: Build backend of the companion

- **Decision:** a stdlib in-tree PEP 517 backend (`backend-path`) that builds the binary-free
  fallback wheel, an editable wheel and an sdist. The release script reuses the same wheel
  writer module for the platform wheels.
- **Rationale:** `uv sync --all-extras` installs the workspace member, so it needs a backend.
  A stdlib backend keeps C-004 (no new build dependency), and one writer keeps a single
  authority for the wheel layout.
- **Alternative:** hatchling. Rejected because it would make a second builder of the same
  distribution.

## R-3: Host and version guards live in the provider

- **Decision:** the provider offers nothing when any of these holds:
  - the installed `spec-kitty-cli` version differs from the manifest's `cli_version`;
  - `kernel.service_hosts.host_target()` differs from the manifest's `target`;
  - the file is missing.
  `kernel` is imported lazily; an import failure also means "offer nothing".
- **Rationale:**
  - Resolution refuses a non-matching install-slot binary with
    `SERVICE_BINARY_DIGEST_MISMATCH`, by design: it fails closed and never falls through.
  - A version skew or a forced cross-platform install is not tampering, so it should degrade
    to the fetch. The provider is the only place that can tell the difference before
    resolution judges the bytes.
  - Resolution keeps its fail-closed rule unchanged.
- **Alternative:** relax resolution to fall through on a mismatch. Rejected: that weakens
  fail-closed for genuine tampering.

## R-4: Wiring `sync_services.py` into `release.yml`

- **Decision:** call `scripts/sync_services.py --service all` and then `--check` directly in
  `build-release`, after the packs check. Do not use the `sync-services` composite action.
- **Rationale:** `tests/ci/test_sync_services.py` has a "wire it now" ratchet. Once a pin exists,
  it requires a workflow job to use the action. Using the action in the release job would
  satisfy that ratchet without wiring the conformance jobs it exists for.
- **Supply chain (DIRECTIVE_051):** no third-party dependency is added. The extra names a
  first-party distribution of the identical version, built from sha256-pinned assets, never
  rebuilt, and published through OIDC Trusted Publishing from a dedicated environment.

## Adversarial evidence

No security-impacting third-party dependency decision is made, so the dependency squad pass
is not triggered. The pre-PR adversarial squad, with a packaging and supply-chain lens, runs
at closeout per the operator's instructions, and its findings are recorded in the PR.
