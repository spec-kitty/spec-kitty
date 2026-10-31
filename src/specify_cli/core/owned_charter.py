"""Project validated checkout identity into the charter activation public seam."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from mission_runtime import ActionContextError, OwnedCheckout

if TYPE_CHECKING:
    from charter.activation.api import CharterScope


def charter_scope_for_owned(owned: OwnedCheckout, feature_dir: Path | None = None) -> CharterScope:
    """Project one admitted Mission identity into charter reads and fetch argv."""
    from dataclasses import replace

    from charter.activation.api import CharterScope, OwnedCharterInvocation

    if feature_dir is not None and feature_dir.resolve() != owned.mission_dir:
        raise ActionContextError("MISSION_CONTEXT_CONFLICT", "charter Mission differs from the validated owned checkout")
    scope = CharterScope.resolve(owned.owned_root, owned.mission_dir)
    return replace(scope, invocation=OwnedCharterInvocation(owned.owned_root, owned.mission_slug))
