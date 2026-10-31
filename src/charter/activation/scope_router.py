"""Scope-aware wrapper around :func:`charter.activation.context.build_charter_context`.

Combines :meth:`charter.activation.scope.CharterScope.resolve` with the existing
``build_charter_context`` call so callers in the prompt-rendering pipeline
get monorepo-aware charter resolution without changing
``build_charter_context``'s signature (which is owned by WP07).

For single-project repos (no ``charter_scopes:`` configured),
``CharterScope.resolve`` returns the default scope with
``scope.root == repo_root`` and the wrapper is a pass-through. The 23
``test_wp_prompt_governance_contract.py`` fixtures pass unchanged
(NFR-001 binding).

See ADR-8 (``docs/adr/3.x/2026-05-18-1-monorepo-charter-scope.md``).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from charter.activation.context import CharterContextResult, build_charter_context
from charter.activation.scope import CharterScope

__all__ = ["build_with_scope"]


def build_with_scope(
    repo_root: Path,
    feature_dir: Path,
    *,
    scope: CharterScope | None = None,
    **kwargs: Any,
) -> CharterContextResult:
    """Resolve the charter scope for *feature_dir* then build context.

    Parameters
    ----------
    repo_root:
        Repository root (the ``.kittify/`` directory containing
        ``config.yaml`` lives here).
    feature_dir:
        Filesystem directory whose enclosing charter should govern the
        rendered context. For single-project repos this argument is
        ignored after scope resolution (the default scope has
        ``root == repo_root``).
    **kwargs:
        Forwarded verbatim to :func:`charter.activation.context.build_charter_context`.

    Returns
    -------
    :class:`charter.activation.context.CharterContextResult`
        The rendered charter context payload from the resolved scope.

    Raises
    ------
    charter.activation.scope.CharterScopeConflict
        When two configured scopes have incompatible nesting that renders
        *feature_dir* ambiguous.
    charter.activation.scope.CharterScopeNotFound
        When ``charter_scopes:`` is configured but no scope encloses
        *feature_dir*.
    """
    resolved_scope = scope if scope is not None else CharterScope.resolve(repo_root, feature_dir)
    # For the single-project default, scope.root == repo_root and this call
    # is byte-identical to today. For monorepos, scope.root is the
    # per-package charter root.
    #
    # WP04 (#883): the same *feature_dir* also keys the action-doctrine grain
    # off ``meta.json mission_type`` (never the project-level ``template_set``
    # proxy).  Callers that already pass ``mission_type``/``feature_dir`` in
    # *kwargs* keep precedence; otherwise the scope feature_dir supplies it.
    kwargs.setdefault("feature_dir", feature_dir)
    if scope is not None:
        kwargs["scope"] = resolved_scope
    return build_charter_context(resolved_scope.root, **kwargs)
