"""Org doctrine source adapters.

Each concrete source implements the :class:`OrgDoctrineSource` protocol and
returns a :class:`FetchResult` describing the outcome of writing a doctrine
snapshot to a local directory.
"""

from __future__ import annotations

from .api_source import ApiSource
from .git_source import GitSource
from .https_source import HttpsBundleSource
from .protocol import FetchResult, OrgDoctrineSource

__all__ = [
    "ApiSource",
    "FetchResult",
    "GitSource",
    "HttpsBundleSource",
    "OrgDoctrineSource",
]
