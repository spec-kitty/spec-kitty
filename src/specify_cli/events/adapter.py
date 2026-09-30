"""
Adapter layer for spec-kitty-events library.

Reports whether the library is importable and how to install it. The CLI-side
``Event`` / ``LamportClock`` wrappers were sync-transport residue and were
removed (dead-code review 2026-09-30).
"""

from importlib.util import find_spec

# The public spec_kitty_events PyPI package is a hard dependency; the flag is
# kept for the CLI's startup guard (``specify_cli.__init__``).
HAS_LIBRARY = find_spec("spec_kitty_events") is not None


class EventAdapter:
    """Main adapter for spec-kitty-events library integration."""

    @staticmethod
    def check_library_available() -> bool:
        """Check if spec-kitty-events library is available."""
        return HAS_LIBRARY

    @staticmethod
    def get_missing_library_error() -> str:
        """Get error message for missing library with setup instructions."""
        return (
            "spec-kitty-events library not installed.\n\n"
            "This library is required for event log functionality.\n\n"
            "Setup instructions:\n"
            "1. Ensure you have SSH access to https://github.com/spec-kitty/spec-kitty-events\n"
            "2. Run: pip install -e .\n\n"
            "For CI/CD setup, see: docs/development/ssh-deploy-keys.md\n"
        )
