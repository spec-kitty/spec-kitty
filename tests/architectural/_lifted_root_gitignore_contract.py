"""Single home of the two structural .gitignore-contract invariants (#5015).

``tests/specify_cli/test_gitignore_contract.py`` (out of matrix) and its always-on lift
``tests/architectural/test_lifted_root_gitignore_contract.py`` both import these, so the per-PR gate runs
exactly what the source suite runs and the two cannot drift apart.
"""

from pathlib import Path


def test_repo_gitignore_covers_local_runtime() -> None:
    """Every LOCAL_RUNTIME project surface has a matching .gitignore entry."""
    from specify_cli.state.contract import (
        STATE_SURFACES,
        AuthorityClass,
        GitClass,
        StateRoot,
    )

    repo_root = Path(__file__).resolve().parents[2]  # up to repo root
    gitignore_path = repo_root / ".gitignore"
    gitignore_content = gitignore_path.read_text()
    gitignore_lines = [line.strip() for line in gitignore_content.splitlines() if line.strip() and not line.strip().startswith("#")]

    # All project-rooted surfaces that must be ignored. A TRACKED (or
    # external/git-internal) surface is version-controlled by design and must
    # NOT be required to appear in .gitignore — this mirrors state/doctor.py's
    # own exemption (#4928: the mission-state audit trail is LOCAL_RUNTIME but
    # git_class=TRACKED, so it is durable rather than ignored).
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
        # A gitignore line covers a pattern when it is an exact match or a
        # true parent-directory prefix (directory boundary required).
        # Bare startswith is intentionally avoided: ".agent" is a raw string
        # prefix of ".agents/skills/..." but NOT a parent directory of it,
        # so it must not satisfy coverage for that surface (#2423 follow-up).
        if not any(line.rstrip("/") == pattern.rstrip("/") or pattern.rstrip("/").startswith(line.rstrip("/") + "/") for line in gitignore_lines):
            missing.append(f"{surface.name}: {pattern}")

    assert not missing, f"Local runtime surfaces not in .gitignore: {missing}"


def test_runtime_entries_match_contract() -> None:
    """GitignoreManager entries are derived from state contract."""
    from specify_cli.gitignore_manager import RUNTIME_PROTECTED_ENTRIES
    from specify_cli.state.contract import get_runtime_gitignore_entries

    contract_entries = get_runtime_gitignore_entries()
    assert set(RUNTIME_PROTECTED_ENTRIES) == set(contract_entries), (
        f"Drift detected. Manager has {set(RUNTIME_PROTECTED_ENTRIES) - set(contract_entries)} extra, "
        f"contract has {set(contract_entries) - set(RUNTIME_PROTECTED_ENTRIES)} extra"
    )
