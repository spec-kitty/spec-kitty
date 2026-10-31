"""How each pinned service is launched, and which ones the CLI may launch at all (#6590, WP04 T018).

One :class:`ServicePolicy` per service names its scope (one instance per git
common dir, or per worktree), whether the CLI may start it, and the arguments
of its start command. The arguments follow the accepted launch contract
(``kitty-specs/pinned-service-binaries-01M64N66/contracts/launch-contract.md``)
exactly; no flag is invented here.

Only the write service is launchable today. The charter service is recorded
for shape only until the charter seam work enables it, and the read service is
never launched by the CLI (ADR 2026-10-29-1 D-6, spec C-007).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Literal

__all__ = ["ServicePolicy", "policy_for"]

ServiceScope = Literal["git_common_dir", "worktree"]
_SERVE = "serve"
_NOT_LAUNCHABLE_RULE = "ADR 2026-10-29-1 D-6"


@dataclass(frozen=True)
class ServicePolicy:
    """The launch shape of one service: its scope, whether the CLI starts it, and its start arguments."""

    service: str
    scope: ServiceScope
    launchable: bool
    start_args: Callable[[Path], list[str]]

    def require_launchable(self) -> None:
        """Raise ``ValueError`` for a service the CLI never starts: calling the launcher for it is a programming error."""
        if not self.launchable:
            raise ValueError(f"the CLI does not launch {self.service} ({_NOT_LAUNCHABLE_RULE})")


def _write_service_args(git_common_dir: Path) -> list[str]:
    return [_SERVE, "--git-common-dir", str(git_common_dir)]


def _charter_service_args(worktree: Path) -> list[str]:
    return [_SERVE, "--worktree", str(worktree)]


def _read_service_args(_scope: Path) -> list[str]:
    raise ValueError(f"the CLI never launches read-service ({_NOT_LAUNCHABLE_RULE})")


WRITE_SERVICE = ServicePolicy(service="write-service", scope="git_common_dir", launchable=True, start_args=_write_service_args)
#: Recorded for shape only: launchable once the charter seam work enables it.
CHARTER_SERVICE = ServicePolicy(service="charter-service", scope="worktree", launchable=False, start_args=_charter_service_args)
#: Pinned for CI conformance only; the CLI never launches it (C-007).
READ_SERVICE = ServicePolicy(service="read-service", scope="git_common_dir", launchable=False, start_args=_read_service_args)

_POLICIES: Mapping[str, ServicePolicy] = MappingProxyType({policy.service: policy for policy in (WRITE_SERVICE, CHARTER_SERVICE, READ_SERVICE)})


def policy_for(service: str) -> ServicePolicy:
    """The policy of *service*; an unknown name is a ``ValueError``."""
    try:
        return _POLICIES[service]
    except KeyError:
        raise ValueError(f"no launch policy for service {service!r}; known: {sorted(_POLICIES)}") from None
