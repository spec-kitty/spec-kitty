"""Doctrine fetch/pack tooling for spec-kitty org doctrine layer.

This package provides the OrgDoctrineSource protocol and concrete fetch-source
implementations (git, HTTPS/Artifactory bundle, API) plus snapshot management
utilities.

Layer: ``specify_cli`` (depends on ``charter``, ``doctrine``, ``kernel``).

See mission ``layered-doctrine-org-layer-01KRNPEE`` and ADR
``2026-03-27-1`` for the architectural context.
"""

from __future__ import annotations

from .config import (
    OrgPackConfig,
    PackRegistry,
    assert_pack_local_paths_exist,
    load_pack_registry,
    resolve_org_roots,
    save_pack_registry,
)
from .org_charter import MissingDoctrinePackError
from .snapshot import fetch_pack, write_snapshot
from .sources import (
    ApiSource,
    FetchResult,
    GitSource,
    HttpsBundleSource,
    OrgDoctrineSource,
)

__all__ = [
    "ApiSource",
    "FetchResult",
    "GitSource",
    "HttpsBundleSource",
    "MissingDoctrinePackError",
    "OrgDoctrineSource",
    "OrgPackConfig",
    "PackRegistry",
    "assert_pack_local_paths_exist",
    "fetch_pack",
    "load_pack_registry",
    "resolve_org_roots",
    "save_pack_registry",
    "write_snapshot",
]
