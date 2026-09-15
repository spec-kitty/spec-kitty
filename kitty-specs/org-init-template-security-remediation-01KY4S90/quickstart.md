# Quickstart: Verify template security remediations

## Stock path

```bash
spec-kitty doctrine org init /tmp/pack-legacy
# three-file scaffold unchanged
```

## Token injection (FR-001)

```bash
export GIT_TOKEN=secret-test-token
# With a fake HTTPS template URL and injectable GitSource test double /
# unit test: assert fetch URL has no oauth2:secret-test-token@
```

## Symlink (FR-003)

Create a template with `ln -s ~/.ssh/id_rsa evil` (or a fixture file outside the tree). Render must not place that file’s bytes under PACK_PATH.

## Path token (FR-005)

Template file named `{{ORG_NAME}}.md` → command fails with `substitute.path_token` (or documented rule id); no successful pack.

## Schemes (FR-007)

```bash
spec-kitty doctrine org init /tmp/p --template http://example.invalid/r --org-name acme
# non-zero; scheme rejected
```

## Force atomicity (FR-008)

Existing PACK_PATH + `--force` + induced failure after move-aside should restore or leave backup recoverable — covered by unit test of `_install_staging`.
