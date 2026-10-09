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
    # Retired with the hosted Team Kitty surface (ADR 2026-10-06-1).
    "spk-team-auth",
    "spk-team-connectors",
    "spk-team-sync",
    "spk-team-tracker",
    # Renamed/folded by #3732 (FR-008): spk-charter-* / spk-practice-*.
    "ad-hoc-profile-load",
    "spec-kitty-bulk-edit-classification",
    "spec-kitty-charter-doctrine",
    "spec-kitty-constitution-doctrine",
    "spec-kitty-glossary-context",
    "spec-kitty-spdd-reasons",
    "spk-doctrine-bulk-edit",
    "spk-doctrine-charter",
    "spk-doctrine-glossary",
    "spk-doctrine-profile-load",
    "spk-doctrine-semantic-compression",
    "spk-doctrine-show-me",
    "spk-doctrine-spdd-reasons",
}) | RETIRED_STANDALONE_SKILL_NAMES
