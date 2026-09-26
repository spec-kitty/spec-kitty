"""Always-on gate: the ``.gitignore`` contract stays intact.

Source: ``tests/specify_cli/test_gitignore_contract.py``, which lives
directly under ``tests/specify_cli`` — recorded ``out_of_matrix`` in
``.github/ci-module-registry.yml`` (#4374, decide-out-of-matrix-test-dirs
ledger, lift-invariant disposition).

The source suite carries many individual historical-regression pins (dossier
snapshot rooting, worktrees root, skill projection, ops index, ...); this
lift narrows to the TWO structural invariants that make the phrase "the
gitignore contract stays intact" literally true — every drift-prone case a
future ``STATE_SURFACES`` addition could silently violate:

1. Every ``LOCAL_RUNTIME``/``IGNORED`` PROJECT-rooted state surface has a
   matching entry in the repo's own ``.gitignore``.
2. ``GitignoreManager``'s protected-entry set matches
   ``get_runtime_gitignore_entries()`` exactly (no drift between the
   generator and its consumer).

The remaining source tests are individual historical-bugfix regression pins
(one surface / one fix each), not this single contract-consistency
invariant, and are left out-of-matrix pending a future promote/deferred-
promotion decision.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = [pytest.mark.architectural]


def test_repo_gitignore_covers_local_runtime() -> None:
    from specify_cli.state.contract import (
        STATE_SURFACES,
        AuthorityClass,
        GitClass,
        StateRoot,
    )

    repo_root = Path(__file__).resolve().parents[2]
    gitignore_path = repo_root / ".gitignore"
    gitignore_content = gitignore_path.read_text()
    gitignore_lines = [line.strip() for line in gitignore_content.splitlines() if line.strip() and not line.strip().startswith("#")]

    # A TRACKED (or external/git-internal) surface is version-controlled by
    # design and must NOT be required to appear in .gitignore — this mirrors
    # the source suite's own exemption (#4928: the mission-state audit trail is
    # LOCAL_RUNTIME but git_class=TRACKED, so it is durable rather than ignored).
    exempt_from_ignore = (
        GitClass.TRACKED,
        GitClass.OUTSIDE_REPO,
        GitClass.GIT_INTERNAL,
    )
    local_runtime_project = [
        s
        for s in STATE_SURFACES
        if s.root == StateRoot.PROJECT
        and s.git_class not in exempt_from_ignore
        and (s.authority == AuthorityClass.LOCAL_RUNTIME or s.git_class == GitClass.IGNORED)
    ]

    assert local_runtime_project, "Expected at least one LOCAL_RUNTIME project surface"

    missing = []
    for surface in local_runtime_project:
        pattern = surface.path_pattern
        if not any(line.rstrip("/") == pattern.rstrip("/") or pattern.rstrip("/").startswith(line.rstrip("/") + "/") for line in gitignore_lines):
            missing.append(f"{surface.name}: {pattern}")

    assert not missing, f"Local runtime surfaces not in .gitignore: {missing}"


def test_runtime_entries_match_contract() -> None:
    from specify_cli.gitignore_manager import RUNTIME_PROTECTED_ENTRIES
    from specify_cli.state.contract import get_runtime_gitignore_entries

    contract_entries = get_runtime_gitignore_entries()
    assert set(RUNTIME_PROTECTED_ENTRIES) == set(contract_entries), (
        f"Drift detected. Manager has {set(RUNTIME_PROTECTED_ENTRIES) - set(contract_entries)} extra, "
        f"contract has {set(contract_entries) - set(RUNTIME_PROTECTED_ENTRIES)} extra"
    )
