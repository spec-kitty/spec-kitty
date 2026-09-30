"""Connector factory for local (beads/fp) tracker integrations.

SaaS-backed providers (jira, linear, github, gitlab) are handled by the
SaaS control plane and do not need local connectors.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


class TrackerFactoryError(RuntimeError):
    """Raised when connector construction fails."""


SUPPORTED_PROVIDERS: tuple[str, ...] = ("beads", "fp")


def normalize_provider(provider: str) -> str:
    """Normalize a provider name to its canonical form."""
    return provider.strip().lower()


def build_connector(
    *,
    provider: str,
    workspace: str,
    credentials: Mapping[str, Any],
) -> Any:
    """Build a TaskTrackerConnector instance for a local provider."""
    provider_name = normalize_provider(provider)
    if provider_name not in SUPPORTED_PROVIDERS:
        raise TrackerFactoryError(f"Unsupported provider '{provider}'. Supported: {', '.join(SUPPORTED_PROVIDERS)}")

    try:
        from spec_kitty_tracker import (
            BeadsConnector,
            BeadsConnectorConfig,
            FPConnector,
            FPConnectorConfig,
        )
    except Exception as exc:  # pragma: no cover - dependency boundary
        raise TrackerFactoryError("spec-kitty-tracker is not installed. Install it to use tracker commands.") from exc

    if provider_name == "beads":
        config = BeadsConnectorConfig(
            workspace=workspace,
            command=str(credentials.get("command") or "bd"),
            cwd=str(credentials.get("cwd")) if credentials.get("cwd") else None,
        )
        return BeadsConnector(config)

    if provider_name == "fp":
        config = FPConnectorConfig(
            workspace=workspace,
            command=str(credentials.get("command") or "fp"),
            cwd=str(credentials.get("cwd")) if credentials.get("cwd") else None,
        )
        return FPConnector(config)

    raise TrackerFactoryError(f"Unhandled provider: {provider_name}")
