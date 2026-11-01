---
title: 'ADR 2 (2026-04-08): Package-Bundled Templates as Sole Source'
description: 'Templates resolve only from the installed package: the GitHub tarball download path and the template-root flag are deleted, leaving one env override for maintainers.'
status: Accepted
doc_status: active
kind: ADR
date: '2026-04-08'
---

## Context and Problem Statement

`spec-kitty init` historically supported three distinct template sources:

1. **Package-bundled (default):** Templates embedded in the installed `spec-kitty-cli` package, resolved via `importlib.resources`.
2. **Remote GitHub download:** init would download a tarball from the spec-kitty GitHub repository when `--github-token` or `--debug` was passed. This was originally designed to support a "bootstrap without a full install" scenario.
3. **Local repo override:** When the `--template-root` CLI flag or the `SPEC_KITTY_TEMPLATE_ROOT` environment variable was set, init would load templates from the specified local path. This was intended for maintainers testing in-development template changes.

The multi-source model created several problems:

1. **Network dependency during init.** The remote download path required network access, TLS validation (`--skip-tls` existed to bypass it), and a GitHub token for private repositories. A simple machine-setup command should not require network calls when the package is already installed.

2. **Dead code paths.** The remote download scenario — bootstrapping without an installed package — is no longer valid. spec-kitty is distributed exclusively via pipx, and the installed package always contains the templates. The remote path is never used in practice.

3. **Surface area bloat.** Flags `--debug`, `--skip-tls`, and `--github-token` existed solely to configure the remote download path. They contributed to a confusing CLI surface with no valid end-user use case.

4. **`github_client.py` maintenance cost.** The module implementing remote download adds code that must be maintained, tested, and kept current with GitHub's API — for a scenario that no longer occurs.

## Decision Drivers

* **Eliminate network dependency:** init should work reliably in air-gapped environments and CI.
* **Reduce surface area:** Every flag or code path that has no valid end-user use case is a maintenance liability.
* **Clarity:** "Where do templates come from?" should have exactly one answer.
* **Maintainer workflow:** Developers testing template changes should still have a mechanism — but it should not require a CLI flag.

## Considered Options

* **Option A: Package-bundled templates as sole source, env var for maintainers (chosen)**
* **Option B: Keep remote mode behind a hidden flag**
* **Option C: Keep `--template-root` as a hidden CLI flag**

## Decision Outcome

**Chosen option: Option A — Package-bundled templates are the unconditional source.**

The template source is always the installed `spec-kitty-cli` package. The `SPEC_KITTY_TEMPLATE_ROOT` environment variable remains available for maintainers who need to test template changes from a local checkout without installing. Everything else is removed.

### What Is Removed

| Removed artifact | Location | Notes |
|-----------------|----------|-------|
| `github_client.py` | `src/specify_cli/template/github_client.py` | Entire module deleted |
| Remote tarball download | `init.py:1149–1163` | Dead code path removed |
| `--template-root` CLI flag | `init.py:750` | Env var remains for maintainers |
| `--debug` CLI flag | `init.py:744` | Only wired to remote download path |
| `--skip-tls` CLI flag | `init.py:743` | Only wired to remote download path |
| `--github-token` CLI flag | `init.py:745–748` | Only wired to remote download path |
| Local-repo root detection | `template/manager.py:get_local_repo_root` | Not needed when env var is sufficient |

### What Remains

* `SPEC_KITTY_TEMPLATE_ROOT` environment variable: when set, resolves templates from the given path. This is the supported mechanism for maintainer local testing. It is not documented in end-user help text.
* `importlib.resources`-based resolution: the default and sole end-user path.

### Consequences

#### Positive

* No network access during init. Works fully offline and in CI.
* `github_client.py` and its tests are deleted, reducing the maintenance surface.
* Three flags (`--debug`, `--skip-tls`, `--github-token`) disappear from the CLI help output, simplifying the user-facing surface.
* Template resolution is a single code path, easier to test and reason about.

#### Negative

* Developers who previously used `--template-root` to test local changes must switch to `SPEC_KITTY_TEMPLATE_ROOT`. This is a maintainer-only workflow change with no end-user impact.

#### Neutral

* The package-bundled path was already the default; the vast majority of users experience no change.

### Confirmation

Correct behavior is confirmed when: `spec-kitty init` completes successfully without any network calls; and `SPEC_KITTY_TEMPLATE_ROOT=/path/to/local spec-kitty init` correctly uses templates from the local path. Both conditions are covered in the integration test suite.

## Pros and Cons of the Options

### Option A: Package-bundled templates as sole source (chosen)

Remove all non-package template sources and their associated CLI flags. Retain `SPEC_KITTY_TEMPLATE_ROOT` as an undocumented maintainer escape hatch.

**Pros:**
* Offline-capable.
* No flags to maintain for the remote path.
* One code path to test.

**Cons:**
* Maintainers lose the `--template-root` CLI convenience (minor; env var is equivalent).

### Option B: Keep remote mode behind a hidden flag

Retain `--template-root` and the remote download path but hide them from `--help` output.

**Pros:**
* Preserves the capability for edge cases not yet anticipated.

**Cons:**
* Hidden flags are still code that must be maintained, tested, and kept secure.
* The remote download path requires network infrastructure (GitHub API tokens, TLS configuration) for a scenario with no known use case.
* "Hidden" is not "removed" — users can still discover and invoke hidden flags; the surface area reduction is cosmetic.

**Why Rejected:** Maintenance burden with no active user. If a legitimate use case emerges in the future, a new flag can be added with a documented scope.

### Option C: Keep `--template-root` as a hidden CLI flag

Retain the CLI flag but hide it, removing the remote download path only.

**Pros:**
* Preserves CLI discoverability if a maintainer forgets about the env var.

**Cons:**
* The env var (`SPEC_KITTY_TEMPLATE_ROOT`) already exists and covers the identical use case.
* Hidden CLI flags require documentation, parsing code, and test coverage.
* Two mechanisms for the same thing is one too many.

**Why Rejected:** The env var is sufficient. Having both creates ambiguity about which takes precedence and doubles the test surface for an identical capability.

## More Information

* **Spec:** `kitty-specs/076-init-command-overhaul/spec.md` — "Flags to Remove" table (`--debug`, `--skip-tls`, `--github-token`, `--template-root`), "Code Paths to Remove" table (remote GitHub tarball download, local-repo template override)
* **Related ADR:** ADR-A (2026-04-08-1) — Global `~/.kittify/` as machine-level runtime
* **Code locations:**
  * `src/specify_cli/template/github_client.py` — module to be deleted
  * `src/specify_cli/template/manager.py` — `get_local_repo_root` to be removed
  * `src/specify_cli/init.py:743–750` — flags being removed
