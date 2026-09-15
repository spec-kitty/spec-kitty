"""``spec-kitty routes`` — where this checkout broadcasts, and who admits it
(Priivacy-ai/spec-kitty#10, replacing the reshaped TEAM-ADMIT-M2-11).

The old ``spec-kitty sync routes`` answered a question the deleted sync
transport owned: where does my data go, and which teams see it. With the
transport gone the question that remains is the ephemeral-team-status one:
**which team admits this repository, and which relay do its moments reach** —
or *no accessible route was found for the credentials used*. A negative
answer does not establish whether another account or team admits the repository.
This command reads the same seam every status transition already uses.

One code path, no second implementation: :func:`routes` reads the same
store every status transition does — :func:`zeitgeist_client.resolution.cached_answer`
for the offline peek, then :func:`zeitgeist_client.resolution.resolve_credentials`
(the E3 seam whose cache / remembered-negative / mint branches every
transition rides) only when that peek misses. A cache hit — positive or a
remembered negative — must answer without ever requiring auth to be
configured (Priivacy-ai/spec-kitty#151); only a genuine miss touches the
network, mints if the store still cannot answer, and stores whatever Team
Kitty answers — positive credential or short-TTL negative — exactly as a
transition would. The command reports honestly which of the three states
it is in:

* a stored credential answers offline, instantly;
* a remembered negative (no accessible route) answers offline too,
  until its TTL runs out and the seam asks again;
* nothing stored means the seam could not get an answer this run — Team
  Kitty unreachable or the mint refused — and the command says that rather
  than dressing silence up as "not admitted".

The admitting team's name comes back with the mint (the admission pre-flight
that precedes it is the one place the slug is ever in hand);
``resolution`` records it on the stored credential so later invocations can
print it without asking again.

Faults exit non-zero with the reason named: no canonical repo identity, no
hosted remote (there is nothing to admit), nothing configured to authenticate
with, Team Kitty unreachable. A recorded negative is *not* a fault: no accessible
relay was resolved, so it exits zero with scoped guidance. Cached answers do not prove the identity
of the currently stored OAuth account.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import typer
from rich.markup import escape

from specify_cli.auth.server_target import ServerTargetSplitBrainError
from specify_cli.cli.console import console
from specify_cli.saas_client.auth import load_auth_context
from specify_cli.saas_client.errors import SaasAuthError
from specify_cli.zeitgeist_client import credentials, repo_identity, resolution

_JSON_OPTION = typer.Option(False, "--json", help="Emit plain JSON instead of a human-readable summary.")


def _fail(message: str) -> None:
    console.print(f"[red]Error:[/red] {message}")
    raise typer.Exit(1)


def _resolve_checkout() -> tuple[str, str, str | None]:
    """``(store_key, owner/repo slug, host)`` for this checkout, failing
    loudly on each way a checkout can have nothing to ask any team about.

    The store key must match ``resolution.resolve_credentials``'s own —
    ``resolution.store_key(host, repo_slug)`` since spec-kitty#129, not the
    bare repo name — or this command's own negative-cache lookup below reads
    a different entry than the one resolution just wrote."""
    cwd = os.getcwd()
    try:
        deadline = repo_identity.Deadline()
        name = repo_identity.repo_name(cwd, deadline)
        origin = repo_identity.origin_url(cwd, deadline)
    except repo_identity.RepoIdentityError as exc:
        _fail(f"could not identify this checkout ({exc}); run this from inside a Spec Kitty mission repository.")
    slug, host = resolution.repo_slug_and_host(origin)
    if slug is None:
        _fail(f"{name!r} has no hosted forge remote, so no team can admit it and there is no relay to show. Nothing about this checkout is broadcast.")
    return resolution.store_key(host=host, repo_slug=slug), slug, host


def _gateway_for(cwd: Path) -> resolution.SaasCapabilityGateway:
    """The real Team Kitty transport, built the same way the status fan-out
    builds its own — env vars first, then ``<root>/.kittify/saas-auth.json``,
    then the OAuth session ``spec-kitty auth login`` wrote (#198), so the
    documented login path needs no service token to see its own routes."""
    try:
        ctx = load_auth_context(repo_root=cwd)
    except SaasAuthError as exc:
        if isinstance(exc.__cause__, ServerTargetSplitBrainError):
            _fail(escape(str(exc)))
        _fail(f"nothing configured to authenticate with ({escape(str(exc))}). Run `spec-kitty auth login` first.")
    return resolution.SaasCapabilityGateway(ctx.saas_url, ctx.token, team_slug=ctx.team_slug)


def _print_routes(payload: dict[str, Any]) -> None:
    console.print()
    console.print("[cyan]Spec Kitty Team Routing[/cyan]")
    console.print()
    if payload["admitted"]:
        console.print(f"[bold]team: {payload['team'] or '(not recorded)'} · relay: {payload['relay_url']}[/bold]")
        credential = payload.get("credential") or {}
        expires = credential.get("expires_at") or "(no recorded expiry)"
        console.print(f"  repository  {payload['repository']['host']}/{payload['repository']['slug']}")
        console.print(f"  store key   {payload['repository']['repo_key']}")
        console.print(f"  credential  {credential.get('token_kind')}  expires {expires}")
    else:
        reason = payload.get("reason")
        suffix = f" [dim](reason: {reason})[/dim]" if reason else ""
        console.print(f"[bold]No accessible team route found — no relay[/bold]{suffix}")
        console.print(f"  repository  {payload['repository']['host']}/{payload['repository']['slug']}")
        console.print("  This result does not establish whether another account or team admits the repository.")
        console.print("  Check your account with [bold]spec-kitty auth status[/bold].")
        console.print("  To use another account, run [bold]spec-kitty auth login --force[/bold] and select it in the browser.")
        console.print("  Service credentials (SPEC_KITTY_SAAS_TOKEN or .kittify/saas-auth.json) take precedence over browser login.")
        console.print("  Check repository admission in a team you can access. Cached negative results may persist until expiry.")
    console.print()


def routes(as_json: bool = _JSON_OPTION) -> None:
    """Show which team admits this checkout and which relay carries its moments."""
    key, slug, host = _resolve_checkout()

    # A cached answer — positive or a remembered negative — answers offline
    # and must not require auth to be configured first (Priivacy-ai/spec-kitty#151):
    # only a genuine cache miss needs the gateway (and thus a working auth
    # context) at all.
    hit, stored, negative = resolution.cached_answer(key, repo_slug=slug, host=host)
    if not hit:
        gateway = _gateway_for(Path(os.getcwd()))
        stored = resolution.resolve_credentials(os.getcwd(), gateway=gateway)
        negative = credentials.load_negative(repo=key)

    payload: dict[str, Any]
    if stored is not None:
        payload = {
            "repository": {"repo_key": key, "slug": slug, "host": host},
            "admitted": True,
            "team": stored.team,
            "relay_url": stored.relay_url,
            "credential": {"token_kind": stored.token_kind, "expires_at": stored.expires_at},
        }
    elif negative is not None:
        payload = {
            "repository": {"repo_key": key, "slug": slug, "host": host},
            "admitted": False,
            "team": None,
            "relay_url": None,
            "reason": negative.reason or None,
        }
    else:
        _fail(
            "Team Kitty gave no answer for this checkout this run (unreachable, or "
            "the capability request was refused without a recorded reason). Check "
            "`spec-kitty auth status` and your connection, then retry."
        )

    if as_json:
        console.emit_json(payload)
        return
    _print_routes(payload)
