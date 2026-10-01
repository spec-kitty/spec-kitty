"""Retired Spec Kitty skill package names."""

from __future__ import annotations

RETIRED_STANDALONE_SKILL_NAMES = frozenset({
    "spec-kitty.advise",
})

RETIRED_CANONICAL_SKILL_NAMES = frozenset({
    "debugger-debbie",
    "paula-patterns",
    # Removed by PR #2312 — internal kittyfooding, relocated to spec-kitty-saas#370.
    "spk-team-upsun-cli-sync",
    # Removed with the bundled dashboard (#5530).
    "spk-admin-dashboard",
}) | RETIRED_STANDALONE_SKILL_NAMES
