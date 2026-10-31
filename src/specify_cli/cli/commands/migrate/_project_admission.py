"""Write admission after canonical migration project discovery."""

from pathlib import Path

from kernel.git_topology import git_toplevel_uncached
from kernel.paths import get_kittify_home
from kernel.resolution import resolve_rejecting_loops
from specify_cli.core.paths import get_project_root_override


def admit_migration_project_root(repo_root: Path, *, require_git: bool = False) -> Path:
    """Validate the discovered scope before scanning or creating metadata.

    Explicit valid corpus-root overrides retain Tier 1 authority. Ordinary
    non-global, non-Git projects retain marker-based discovery. An inferred
    global runtime marker needs fresh repository authority; Git metadata
    operations require it even when the operator supplied an override.
    """
    root = resolve_rejecting_loops(repo_root)
    if not require_git:
        override = get_project_root_override()
        if override is not None and resolve_rejecting_loops(override) == root:
            return root
        runtime_home = resolve_rejecting_loops(get_kittify_home())
        if root != runtime_home and resolve_rejecting_loops(root / ".kittify") != runtime_home:
            return root
    observed = git_toplevel_uncached(root)
    if observed != root:
        raise RuntimeError(f"Cannot authorize migration: {root} is not a repository working-tree root.")
    return observed
