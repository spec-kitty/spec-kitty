---
title: Fork packaging hooks
description: How renamed or private-index forks customize Spec Kitty upgrade checks and package identity via entry points—without overlaying core sources.
doc_status: active
updated: '2026-09-30'
type: how-to
related:
- docs/guides/how-to/installation/upgrade-cli.md
- docs/guides/how-to/installation/install-and-upgrade.md
audience: docs/context/audience/external/architect-evaluator.md
---
# Fork packaging hooks

Publish a renamed Spec Kitty CLI (different distribution name and/or a private
PEP 503 simple index) **without rewriting** files under `src/specify_cli/**`.

Stock `spec-kitty-cli` from public PyPI registers nothing. Absence of hooks
preserves today’s public-PyPI / `spec-kitty-cli` behavior.

## What Spec Kitty owns vs what you own

| Owned by Spec Kitty upstream | Owned by the packager |
|---|---|
| Runtime resolvers (`specify_cli.distribution`) | Tag → version mapping |
| Entry-point contracts and stock defaults | `pyproject.toml` name / version |
| Built-in `PyPIProvider` + `SimpleIndexProvider` | Private-index upload and credentials |
| Compat planner / remediation / notifier wiring | CI triggers, VCS tag filters, webhooks |
| This guide and stock regression behavior | Agent Docker / build workarounds |
| | SaaS / E2E release gates in your pipelines |

Do **not** sed/cp overlays onto `session_presence/upgrade_check.py`,
`version_utils.py`, `compat/provider.py`, `compat/planner.py`,
`compat/remediation.py`, or `core/version_checker.py`. Register hooks instead.

## End-state publish flow

1. Check out the release tag you intend to redistribute.
2. Set your distribution `name` / `version` in `pyproject.toml`.
3. Add a thin packager module (examples below) **outside** `src/specify_cli/`
   or as a sibling package you ship in the same wheel.
4. Register entry points in `pyproject.toml`.
5. `python -m build` and upload to your index.
6. Installers use your package name; upgrade checks and remediation follow the
   hooks automatically.

## Phase 1 — Package identity + upgrade provider

Minimal fork: rename the wheel and (optionally) point upgrade lookups at a
custom provider.

```toml
[project]
name = "acme-spec-kitty-cli"
version = "3.2.0"

[project.entry-points."spec_kitty.cli_package"]
main = "acme_spec_kitty_dist:PACKAGE_NAME"

[project.entry-points."spec_kitty.upgrade_provider"]
acme = "acme_spec_kitty_dist:AcmeSimpleIndexProvider"
```

```python
# acme_spec_kitty_dist.py  (packager-owned; not under src/specify_cli/)
from specify_cli.distribution.simple_index import SimpleIndexProvider

PACKAGE_NAME = "acme-spec-kitty-cli"

class AcmeSimpleIndexProvider(SimpleIndexProvider):
    def __init__(self) -> None:
        super().__init__(
            index_url="https://example.invalid/simple/",
            package_prefix="acme_spec_kitty_cli",
        )
```

Use `example.invalid` (or your real host) only in **your** module — never as
an upstream default.

### Multi-provider selection

If several `spec_kitty.upgrade_provider` entry points are registered, set
`SPEC_KITTY_UPGRADE_PROVIDER=<entry-point-name>` to pick one. Unknown names do
not invent a provider; resolution falls back to the stock public-PyPI provider.

The distribution **package name** is never controlled by a runtime environment
variable.

## Phase 2 — Full distribution profile

Prefer a single profile when you also need aliases, remediation index URLs,
data-freshness TTL, or to suppress the "no upgrade available" notifier.

```toml
[project.entry-points."spec_kitty.distribution_profile"]
main = "acme_spec_kitty_dist:build_profile"
```

```python
from specify_cli.distribution.profile import DistributionProfile
from specify_cli.distribution.simple_index import SimpleIndexProvider

PACKAGE_NAME = "acme-spec-kitty-cli"

class AcmeSimpleIndexProvider(SimpleIndexProvider):
    def __init__(self) -> None:
        super().__init__(
            index_url="https://example.invalid/simple/",
            package_prefix="acme_spec_kitty_cli",
        )

def build_profile() -> DistributionProfile:
    return DistributionProfile(
        package_name=PACKAGE_NAME,
        package_aliases=("spec-kitty-cli",),  # transitional / editable installs
        upgrade_provider=AcmeSimpleIndexProvider(),
        index_url="https://example.invalid/simple/",
        extra_index_url=None,
        data_freshness_seconds=3600,  # re-query TTL only; nag display throttle unchanged
        disable_public_pypi_notifier=True,
        version_label=None,  # None → banner uses package_name
    )
```

### What the profile drives

| Field | Effect |
|---|---|
| `package_name` / `package_aliases` | Version lookup, planner queries, remediation argv |
| `upgrade_provider` | Latest-version source for session-presence + compat planner |
| `index_url` / `extra_index_url` | Appended as `--index-url` / `--extra-index-url` on pip/pipx/uv remediation |
| `data_freshness_seconds` | Cache re-query TTL only (display/nag throttle stays stock) |
| `disable_public_pypi_notifier` | Suppresses the public-PyPI “no upgrade” notice |
| `version_label` | Optional `--version` banner label |

Phase 1 entry-point groups remain valid thin aliases: if no profile is
registered, Spec Kitty synthesizes a minimal profile from
`spec_kitty.cli_package` + `spec_kitty.upgrade_provider`.

If a registered profile entry point cannot be loaded or constructed, Spec Kitty
does **not** fall back to public PyPI. It resolves a degraded profile that
performs no network lookup, suppresses the no-upgrade notice, and shows manual
guidance instead of an upgrade command. Fix the profile entry point and restart
the CLI to restore fork-specific remediation.

## Phase 3 — Validation checklist

- [ ] Stock install (no entry points): public PyPI + `spec-kitty-cli` behavior unchanged
- [ ] `--version` / installed-version lookup use the fork name (and aliases if set)
- [ ] Upgrade refresh / compat planner call your provider for the fork package name
- [ ] Remediation commands include `--index-url` when the profile sets it and still pass CHK028 (allowlist length 512, same character class)
- [ ] No-upgrade notifier stays quiet when `disable_public_pypi_notifier=True`
- [ ] No files under `src/specify_cli/**` were modified for the publish

## Related guides

- [Upgrade the Spec Kitty CLI](upgrade-cli.md) — operator upgrade commands for stock installs
- [Install and upgrade overview](install-and-upgrade.md) — CLI vs project upgrade distinction
