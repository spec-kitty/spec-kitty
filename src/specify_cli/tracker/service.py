"""High-level tracker orchestration for CLI commands.

Thin facade over ``LocalTrackerService`` (beads, fp) based on the bound
provider in project config. The former SaaS/hosted providers (linear, jira,
github, gitlab) were removed from open-core together with the hosted tracker
surface (#6164); they now resolve as removed providers and are refused.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from specify_cli.tracker.config import (
    ALL_SUPPORTED_PROVIDERS,
    LOCAL_PROVIDERS,
    REMOVED_PROVIDERS,
    load_tracker_config,
)


class TrackerServiceError(RuntimeError):
    """Raised when tracker service operations fail."""


class StaleBindingError(TrackerServiceError):
    """Raised when binding_ref is stale (deleted/disabled on host).

    The caller should prompt the user to rebind via
    ``spec-kitty tracker bind --provider <provider>``.
    """

    def __init__(self, message: str, *, binding_ref: str, error_code: str) -> None:
        super().__init__(message)
        self.binding_ref = binding_ref
        self.error_code = error_code


def parse_kv_pairs(entries: list[str]) -> dict[str, str]:
    """Parse repeated key=value CLI arguments into a dictionary."""
    parsed: dict[str, str] = {}
    for entry in entries:
        if "=" not in entry:
            raise TrackerServiceError(f"Invalid --credential value '{entry}'. Expected key=value.")
        key, value = entry.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key or not value:
            raise TrackerServiceError(f"Invalid --credential value '{entry}'. Expected key=value.")
        parsed[key] = value
    return parsed


class TrackerService:
    """Facade dispatching to the local (beads/fp) backend by provider."""

    def __init__(self, repo_root: Path) -> None:
        self._repo_root = repo_root

    # ------------------------------------------------------------------
    # Backend resolution
    # ------------------------------------------------------------------

    def _resolve_backend(self) -> Any:
        """Load config and return the local service backend."""
        from specify_cli.tracker.local_service import LocalTrackerService

        config = load_tracker_config(self._repo_root)
        if not config.provider:
            raise TrackerServiceError("No tracker bound. Run `spec-kitty tracker bind` first.")
        if config.provider in LOCAL_PROVIDERS:
            return LocalTrackerService(self._repo_root, config)
        if config.provider in REMOVED_PROVIDERS:
            raise TrackerServiceError(
                f"Provider '{config.provider}' is no longer supported. "
                "See the Spec Kitty documentation for supported providers."
            )
        raise TrackerServiceError(f"Unknown provider: {config.provider}")

    @staticmethod
    def supported_providers() -> tuple[str, ...]:
        """Return all currently supported provider names, sorted."""
        return tuple(sorted(ALL_SUPPORTED_PROVIDERS))

    # ------------------------------------------------------------------
    # bind (pre-dispatch by provider kwarg)
    # ------------------------------------------------------------------

    def bind(self, **kwargs: Any) -> Any:
        """Bind a tracker provider -- dispatches to the local backend."""
        from specify_cli.tracker.local_service import LocalTrackerService

        provider: str = kwargs.get("provider", "")
        if provider in LOCAL_PROVIDERS:
            return LocalTrackerService(
                self._repo_root, load_tracker_config(self._repo_root)
            ).bind(**kwargs)
        if provider in REMOVED_PROVIDERS:
            raise TrackerServiceError(f"Provider '{provider}' is no longer supported.")
        raise TrackerServiceError(f"Unknown provider: {provider}")

    # ------------------------------------------------------------------
    # Delegating methods
    # ------------------------------------------------------------------

    def unbind(self) -> None:
        return self._resolve_backend().unbind()

    def status(self) -> dict[str, Any]:
        """Retrieve project-scoped tracker status."""
        return self._resolve_backend().status()

    def sync_pull(self, **kwargs: Any) -> dict[str, Any]:
        return self._resolve_backend().sync_pull(**kwargs)

    def sync_push(self, **kwargs: Any) -> dict[str, Any]:
        return self._resolve_backend().sync_push(**kwargs)

    def sync_run(self, **kwargs: Any) -> dict[str, Any]:
        return self._resolve_backend().sync_run(**kwargs)

    def sync_publish(self, **kwargs: Any) -> dict[str, Any]:
        return self._resolve_backend().sync_publish(**kwargs)

    def map_add(self, **kwargs: Any) -> None:
        return self._resolve_backend().map_add(**kwargs)

    def map_list(self) -> list[dict[str, Any]]:
        return self._resolve_backend().map_list()
