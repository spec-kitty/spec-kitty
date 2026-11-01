# Implementation Plan: charter-service pin release line

**Branch**: `issue-6909-charter-service-pin-line` | **Date**: 2026-11-01 | **Spec**: [spec.md](./spec.md)
**Input**: Mission specification from `kitty-specs/charter-service-pin-line-01M6BTXZ/spec.md`

## Summary

Core already pins the charter service, but describes it in spec-kitty-events terms and
cannot prove provenance. This mission makes the pin model name the charter repository:

1. a per-service default release repository in the vendor layer (`charter-service` ->
   `https://github.com/spec-kitty/spec-kitty-charter`, the events services -> events);
2. the recorded (non-provisional) charter asset prefix and repository wording in the pin
   module docstring, `pins/README.md` and `service vendor --help`;
3. a build-provenance check at vendor time (`gh attestation verify`, signer workflow and
   source tag ref) that refuses before the lockfile is written, with `--no-attestation` as
   the explicit escape and no `gh` on the user fetch/start path;
4. an end-to-end CLI test proving a `charter-service` fixture pin is digest-verified on
   `service fetch` and that tampered bytes are refused.

No new dependency, no change to the pin schema, the tag rule, targets, jar fallback or
`launchable`.

## Technical Context

**Language/Version**: Python 3.11+ (repository floor; `pyproject.toml` `requires-python = ">=3.11"`)
**Primary Dependencies**: Typer, ruamel.yaml, packaging; existing `kernel.git.remote` and `kernel.release_assets` owners. No new Python dependency.
**Storage**: YAML pin lockfiles under `pins/`; the vendored asset cache is unchanged.
**Testing**: pytest (`fast` tier) with the `file://` fixture release from `tests/kernel/service_release_fixture.py`; a monkeypatched `gh` seam for the provenance path.
**Target Platform**: the spec-kitty CLI on Linux, macOS and Windows (the vendor path is maintainer-only; the check shells out to `gh`, never to the user runtime).
**Project Type**: single Python package (`src/kernel` root layer, `src/specify_cli` application layer).
**Performance Goals**: no measurable runtime cost on fetch/start (0 `gh` calls); the vendor path adds at most one `gh` invocation per pinned asset (a manual, rare operation).
**Constraints**: `file://` repositories perform 0 network requests and 0 subprocess calls; attestation refusals echo no digest and no URL userinfo; `kernel` imports neither `charter` nor `specify_cli`.
**Scale/Scope**: 2 source modules (`kernel/service_pin.py`, `specify_cli/services/vendor.py`), 1 new module (`specify_cli/services/attestation.py`), the `service` CLI group, `pins/README.md`, the service-pins how-to, tests, changelog.

## Charter Check

*GATE: must pass before Phase 0 and re-check after Phase 1.*

| Charter rule | How this plan satisfies it |
| --- | --- |
| Single canonical authority | One tag rule (`kernel.service_pin._TAG_RE`), one repository-validity rule (`check_repository`), one download owner (`kernel.release_assets`), one git contact owner (`kernel.git.remote`). The new repository default table is the one place that names repositories. |
| Architecture: shared package boundaries / internal runtime boundary | The repository default lives in `specify_cli.services.vendor` (application layer), not in `kernel`. The kernel keeps the prefix table and the tag rule only. |
| ATDD-first / DIRECTIVE_034 | Each new behaviour gets a test through the production entry point first: `vendor_pin` / the `service vendor` CLI for the default repository and provenance, the `service fetch` CLI for the fixture pin. |
| RED-first for the fix | The failing tests are written and observed red against the current tree before the production change. |
| DIRECTIVE_041 test quality | New tests guard standing invariants (a default never silently points at another repository; an unverifiable release never writes a pin; a tampered asset never caches). No per-WP shape tests. |
| DIRECTIVE_024 locality / smallest viable diff | No refactor of the pin model; the vendor function keeps its signature and gains one keyword. Only the surfaces the issue names change. |
| `change-apply-smallest-viable-diff` | Reuse `VendorError` codes, `_verified_asset`, `build_release`, `pin_path`; no new error hierarchy, no new cache path. |
| NO_FULL_HEAVY_SUITES_IN_MISSION | Run only the touched modules: `tests/specify_cli/services/test_vendor.py`, `tests/specify_cli/services/test_service_cli.py`, `tests/kernel/test_service_pin.py`, `tests/ci/test_service_pins_gate.py`, plus the architectural ownership gates. |
| Terminology canon | Say "release repository", "pin", "build attestation"; never "feature". The charter service is a service, not a package. |

## Project Structure

### Documentation (this mission)

```
kitty-specs/charter-service-pin-line-01M6BTXZ/
├── plan.md              # This file
├── research.md          # Phase 0 output (discovery + plan extension)
├── quickstart.md        # Phase 1 output (operator verification steps)
├── checklists/requirements.md
├── spec.md
└── tasks.md             # Phase 2 output (/spec-kitty.tasks - NOT created here)
```

No `data-model.md`: the change adds no entity or persisted field; the pin schema is
unchanged (a repository value already exists on every pin). No `contracts/`: no external
contract changes; the CLI's user surface is the documented help text. `meta.json` records
`"contracts": "none"` at finalize time if the accept step asks.

### Source Code (repository root)

```
src/kernel/service_pin.py             # prefix table comment/docstring (naming only)
src/specify_cli/services/vendor.py    # DEFAULT_REPOSITORIES, default_repository(), provenance call
src/specify_cli/services/attestation.py   # NEW: gh attestation verify seam + stable codes
src/specify_cli/cli/commands/service.py   # --no-attestation, --tag/--repository help, docstring
pins/README.md                        # per-service release home; provenance step
docs/development/how-to/service-pins.md   # vendor/provenance guidance; refusal codes
docs/changelog/CHANGELOG.md           # [Unreleased] entry
tests/specify_cli/services/test_vendor.py       # defaults, provenance, unchanged-lockfile refusals
tests/specify_cli/services/test_attestation.py  # NEW: command shape, codes, no digest echo
tests/specify_cli/services/test_service_cli.py  # charter-service fixture fetch end to end + help text
tests/kernel/test_service_pin.py                # recorded prefix table (ratchet)
```

## Phase 0: Outline & Research

Discovery's findings are extended in [research.md](./research.md) (decisions D1-D4, the
evidence inventory, and three open questions with their resolutions). No
`[NEEDS CLARIFICATION]` marker remains; no Decision Moment was deferred (the operator
opened the mission from issue #6909 unattended).

Key resolved questions:

1. **Where the repository default belongs** — vendor layer, not kernel (D1).
2. **Whether to check provenance on fetch** — no; vendor only, the pin stays the trust
   root (D3, C-003).
3. **What a `file://` repository does** — skip the provenance step; it has no attestation
   (D3, NFR-001).

## Phase 1: Design

### The provenance seam

A new module `src/specify_cli/services/attestation.py` owns one function:

```python
def verify_release_attestation(asset: Path, *, repository: str, tag: str) -> None
```

- Derives `owner/repo` from `https://github.com/<owner>/<repo>` and the signer workflow
  `<owner>/<repo>/.github/workflows/service-release.yml`.
- Runs, with no shell:
  `gh attestation verify <asset> --repo <slug> --signer-workflow <slug>/.github/workflows/service-release.yml --source-ref refs/tags/<tag>`
  (the exact invocation spec-kitty-charter ADR-0046 decision 6 and spec-kitty-events
  ADR 0003 document).
- Raises `AttestationError` with a stable code:
  - `SERVICE_ATTESTATION_UNSUPPORTED` — the repository is not a GitHub `https://` URL (no
    signer workflow derivable);
  - `SERVICE_ATTESTATION_UNAVAILABLE` — `gh` is not on `PATH`, or could not be executed;
  - `SERVICE_ATTESTATION_FAILED` — `gh` exited non-zero (missing attestation, another
    signer workflow, another source ref).
- A failure message names the asset and the remedy, never a digest and never URL userinfo
  (the repository URL is normalized through the same redaction rule the pin module uses).

`kernel` stays free of `gh`: the seam lives in `specify_cli.services`.

### Vendor integration

`vendor_pin` gains `verify_attestation: bool = True` (keyword-only, keeps every existing
caller working). `_download_release` passes the flag to `_verified_asset`, which calls the
seam after the digest check and before returning the `ServiceAsset`. A refusal unwinds
before `write_service_pin`, so the lockfile stays byte-identical. `file://` repositories
skip the seam.

The CLI adds `--no-attestation` (a bump-only flag; `--check` rejects it like the other bump
options) and maps the three new codes to exit 1 (a release refusal, not a usage error).

### Default repository table

```python
EVENTS_REPOSITORY = "https://github.com/spec-kitty/spec-kitty-events"
CHARTER_REPOSITORY = "https://github.com/spec-kitty/spec-kitty-charter"
DEFAULT_REPOSITORIES = MappingProxyType({
    "write-service": EVENTS_REPOSITORY,
    "read-service": EVENTS_REPOSITORY,
    "charter-service": CHARTER_REPOSITORY,
})

def default_repository(service: str) -> str: ...
```

`vendor_pin` resolves `repository or current.repository or default_repository(service)`.
The table's keys are asserted equal to `KNOWN_SERVICES` and the policy registry, so a new
service cannot ship without a default.

### Naming and docs

- `kernel.service_pin`: the charter entry comment becomes "spec-kitty-charter ADR-0046
  decision 4 records this name"; the module docstring says the tag comes from the
  service's own repository.
- `pins/README.md`: each service's release home; the provenance rule; the `--no-attestation`
  escape.
- `service.py`: `--tag` and `--repository` help name the service's own release repository
  and spec-kitty-charter for the charter service; the command docstring says "the
  service's release", not "a spec-kitty-events release"; the `--no-attestation` flag is
  documented next to `--repository`.
- `docs/development/how-to/service-pins.md`: replace the manual "cross-check out of band"
  note with the automatic check, keep the manual command as the independent second source,
  add the new refusal codes.

### Implementation Concern Map

| IC | Concern | Files |
| --- | --- | --- |
| IC-01 | Per-service default repository | `vendor.py`, `test_vendor.py` |
| IC-02 | Recorded prefix + owning repository in docs/help | `service_pin.py`, `pins/README.md`, `service.py`, `test_service_pin.py`, `test_service_cli.py` |
| IC-03 | Build-provenance refusal before the pin is written | `attestation.py` (new), `vendor.py`, `service.py`, `test_attestation.py`, `test_vendor.py` |
| IC-04 | Charter-service install digest proof with a fixture pin | `test_service_cli.py` |

## Risks and mitigations

| Risk | Mitigation |
| --- | --- |
| A mandatory `gh` step breaks a maintainer bump on a machine without `gh`. | The refusal code names the remedy; `--no-attestation` is the documented explicit escape; `file://` skips. |
| Provenance on every asset is slow (one `gh` call each). | Vendor is a manual, rare operation; the check runs only over the assets the pin records, and the flag is a single pass. |
| The `gh` output or a failure message leaks a token or digest. | Messages are built by us from the asset name and normalized repository; `gh` stderr is summarized, not echoed wholesale; tests assert no 64-hex digest and no userinfo. |
| A future service is added without a default repository. | A test asserts `DEFAULT_REPOSITORIES` keys equal `KNOWN_SERVICES` and the policy registry (same shape as the existing prefix test). |
| The new flag weakens the check by being easy to use. | It is named `--no-attestation`, documented as "never for a real bump", and the default is on; the red test proves the default refuses. |

## Test plan (red-first)

1. `test_vendor.py::test_the_default_repository_is_per_service` — red before the table.
2. `test_vendor.py::test_a_charter_service_bump_defaults_to_the_charter_repository` — red
   before the resolution change.
3. `test_attestation.py` — module does not exist yet: red.
4. `test_vendor.py` provenance cases — red before the `_verified_asset` call: a fake seam
   records one call per asset; a raising seam leaves the lockfile unchanged; a `file://`
   release records none.
5. `test_service_cli.py::test_fetch_verifies_a_charter_service_fixture_pin` and
   `..._refuses_tampered_bytes` — the first passes today (positive control), the second
   passes today too because the digest check already exists: this pair is the [ratchet]
   proof the issue asks for; confirm it fails if the digest comparison is removed (manual
   half-fix check).
6. `test_service_cli.py::test_vendor_help_names_the_owning_release_repository` — red before
   the help change.

## Verification commands

```bash
uv run pytest tests/specify_cli/services/test_vendor.py tests/specify_cli/services/test_attestation.py tests/specify_cli/services/test_service_cli.py tests/kernel/test_service_pin.py tests/ci/test_service_pins_gate.py -q
uv run ruff check src/kernel/service_pin.py src/specify_cli/services/ src/specify_cli/cli/commands/service.py tests/specify_cli/services/ tests/kernel/test_service_pin.py
uv run ruff format --check src/kernel/service_pin.py src/specify_cli/services/ src/specify_cli/cli/commands/service.py
uv run mypy src/specify_cli/services/attestation.py src/specify_cli/services/vendor.py
uv run pytest tests/architectural/test_remote_contact_owner.py tests/architectural/test_release_asset_download_owner.py -q
```
