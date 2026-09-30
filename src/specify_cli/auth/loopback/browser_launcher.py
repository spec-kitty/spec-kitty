"""Cross-platform browser launching via stdlib :mod:`webbrowser`.

The design constraint here is deliberate: **only** use the stdlib
``webbrowser`` module, never shell out to ``open``/``xdg-open``/``start``.
``webbrowser`` already handles platform detection, the ``$BROWSER`` env
variable, and the X11/Wayland GUI presence check; rolling our own
subprocess logic would reinvent that wheel and be harder to mock in tests.

If no browser controller is available (headless CI, SSH session, broken
``$BROWSER``), the orchestrator should fall back to the Device Authorization
flow (feature 080, WP03).
"""

from __future__ import annotations

import logging
import webbrowser

log = logging.getLogger(__name__)


class BrowserLauncher:
    """Cross-platform browser launcher using stdlib :mod:`webbrowser`."""

    @staticmethod
    def launch(url: str) -> bool:
        """Open ``url`` in the default browser.

        Args:
            url: The authorization URL to open. Must already include all
                OAuth query parameters (``client_id``, ``redirect_uri``,
                ``state``, ``code_challenge``, …).

        Returns:
            ``True`` if the browser was launched successfully, ``False``
            otherwise. Callers should fall back to the Device Authorization
            flow when this returns ``False``.
        """
        try:
            opened = webbrowser.open(url, new=2, autoraise=True)
            if not opened:
                log.warning("webbrowser.open returned False for %s", url)
            return opened
        except webbrowser.Error as exc:
            log.warning("Failed to launch browser: %s", exc)
            return False
