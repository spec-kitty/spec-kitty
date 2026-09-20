"""Implementation of ``spec-kitty auth whoami``.

Prints the authenticated user's email on stdout and exits 0.
Prints nothing and exits 1 if not authenticated or session is expired.

Designed for machine consumption — canary preflight scripts read the first
non-empty output line as the identity token. The ``SaaS:`` endpoint line
(#176) is therefore printed *after* the email so that contract holds; humans
get it in the same shape :func:`specify_cli.cli.commands._auth_status.status_impl`
prints it — both commands print it via the shared
:func:`specify_cli.cli.commands._auth_saas_target.print_saas_target` (#192).
"""

from __future__ import annotations

import sys

import typer

from specify_cli.auth import get_token_manager
from specify_cli.cli.commands._auth_saas_target import print_saas_target


def whoami_impl() -> None:
    """Print the current user's email and exit 0, or exit 1 if not authenticated."""
    tm = get_token_manager()
    session = tm.get_current_session()

    if session is None:
        # #4761: when storage failed closed (e.g. unsafe session-file
        # permissions), say so on stderr so the cause is distinguishable from
        # a plain logged-out state. stdout stays empty and the exit code stays
        # 1 per the documented machine contract — the storage message itself
        # carries the remedy (chmod 600), not "run auth login", which would
        # overwrite the file storage refused to read.
        assessment = getattr(tm, "session_assessment", None)
        detail = getattr(assessment, "detail", None)
        if detail:
            print(f"spec-kitty auth whoami: {detail}", file=sys.stderr)
        raise typer.Exit(1)

    if session.is_refresh_token_expired():
        raise typer.Exit(1)

    # Bare print on purpose: the first non-empty line must stay a plain,
    # unstyled identity token even under FORCE_COLOR (rich would highlight
    # the email). The SaaS lines below go through the shared console.
    print(session.email)
    print_saas_target(session)


__all__ = ["whoami_impl"]
