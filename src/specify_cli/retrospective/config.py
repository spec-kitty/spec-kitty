"""Compatibility shim for the legacy ``retrospective.config`` surface.

This module is retained to preserve back-compat for callers that import from
``specify_cli.retrospective.config``.  The canonical surface for controlling
whether the retrospective lifecycle is enabled is now
``specify_cli.retrospective.policy.resolve_policy``.

``is_retrospective_enabled()`` was the pre-3.2 entry point. It is preserved
here as a thin wrapper over the durable policy resolver for callers that
haven't migrated yet.

**Retirement plan:**
- Deprecation target: spec-kitty 3.3.0
- Follow-up issue: https://github.com/spec-kitty/spec-kitty/issues/TBD
  (Issue title: "Retire retrospective.config + mode shim modules")
- Rationale: external callers may still import this module. Product behavior
  is now policy-driven: default enabled, durable opt-out via
  ``retrospective.enabled: false`` in charter/config, and env vars only
  observed as deprecated test/developer overrides.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from specify_cli.retrospective.mode import ModeResolutionError as ModeResolutionError  # noqa: F401
from specify_cli.retrospective.policy import resolve_policy


def is_retrospective_enabled(
    repo_root: Path,
    *,
    env: Mapping[str, str] | None = None,
) -> bool:
    """Return True if retrospective learning is enabled for this project.

    .. deprecated::
        Use ``specify_cli.retrospective.policy.resolve_policy()`` instead.
        This function is retained for back-compat through spec-kitty 3.2.x.

    Args:
        repo_root: Project root used to locate ``.kittify/charter/charter.md``.
        env: Environment mapping for testing; defaults to ``os.environ``.

    Returns:
        True unless durable charter/config policy sets
        ``retrospective.enabled: false``.

    Raises:
        PolicyResolutionError: re-raised from the policy resolver if charter
            or config retrospective policy is malformed.
    """
    policy, _source_map = resolve_policy(repo_root, env=env)
    return policy.enabled
