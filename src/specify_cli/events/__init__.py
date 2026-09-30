"""Event log integration package.

Public API:
    sanitize_event_for_log: Strip PII fields from an event envelope dict.
    EventAdapter: Adapter for spec-kitty-events library integration.
    HAS_LIBRARY: Whether the optional spec-kitty-events library is installed.
"""

from .adapter import EventAdapter, HAS_LIBRARY
from .sanitizer import sanitize_event_for_log

__all__ = [
    "EventAdapter",
    "HAS_LIBRARY",
    "sanitize_event_for_log",
]
