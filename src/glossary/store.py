"""In-memory glossary store backed by event log."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from .models import TermSense


class GlossaryStore:
    """In-memory glossary store backed by event log."""

    def __init__(self, event_log_path: Path):
        self.event_log_path = event_log_path
        self._cache: dict[str, dict[str, list[TermSense]]] = {}
        # Format: {scope: {surface: [senses]}}
        # Create instance-specific cached lookup function
        self._lookup_cached = lru_cache(maxsize=10000)(self._lookup_impl)

    def add_sense(self, sense: TermSense) -> None:
        """
        Add a sense to the store.

        Args:
            sense: TermSense to add
        """
        scope = sense.scope
        surface = sense.surface.surface_text

        if scope not in self._cache:
            self._cache[scope] = {}
        if surface not in self._cache[scope]:
            self._cache[scope][surface] = []

        self._cache[scope][surface].append(sense)

        # Clear lookup cache when sense is added (cache invalidation)
        self._lookup_cached.cache_clear()

    def _lookup_impl(self, surface: str, scopes: tuple[str, ...]) -> tuple[TermSense, ...]:
        """
        Internal cached lookup implementation.

        Returns tuple instead of list for immutability (required for caching).
        """
        results: list[TermSense] = []
        for scope in scopes:
            if scope in self._cache and surface in self._cache[scope]:
                results.extend(self._cache[scope][surface])
        return tuple(results)

    def lookup(self, surface: str, scopes: tuple[str, ...]) -> list[TermSense]:
        """
        Look up term in scope hierarchy (with LRU cache).

        Args:
            surface: Term surface text (normalized)
            scopes: Tuple of scope names in precedence order

        Returns:
            List of matching TermSense objects in scope order
        """
        # Use cached implementation and convert back to list
        return list(self._lookup_cached(surface, scopes))
