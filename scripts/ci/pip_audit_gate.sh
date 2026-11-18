#!/usr/bin/env bash
# Nightly pip-audit gate (#7390, #5083): audit the locked dependency set and fail
# only on an advisory not listed in scripts/ci/pip-audit-ignore.txt.
# Usage: scripts/ci/pip_audit_gate.sh [requirements-out-path]
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
req="${1:-${RUNNER_TEMP:-/tmp}/pip-audit-requirements.txt}"
# --all-groups as well as --all-extras: the release job installs the non-default
# `sbom` group (cyclonedx-bom and its closure, #7704), so it must be audited too.
uv export --frozen --no-hashes --all-extras --all-groups --no-emit-project --no-emit-workspace -o "$req" >/dev/null
ignores=()
while read -r line; do
  id="${line%%#*}"
  id="${id//[[:space:]]/}"
  if [ -n "$id" ]; then ignores+=(--ignore-vuln "$id"); fi
done < "$here/pip-audit-ignore.txt"
uv run --frozen --no-sync pip-audit --disable-pip --no-deps -r "$req" "${ignores[@]}"
