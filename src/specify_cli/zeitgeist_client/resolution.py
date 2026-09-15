"""Credential resolution for a checkout: cached relay credential, or mint
one from Team Kitty, or a remembered no (E3 — Priivacy-ai/spec-kitty#9).

The seam contract this serves (design page ``ephemeral-team-status.html``,
CLI column): every status transition resolves credentials for its own
(checkout, repo) once — from the existing ``credentials.py`` TOML store,
keyed by the ``(host, owner/repo)`` identity Team Kitty admits by
(:func:`store_key`) — and only when the store cannot answer does it talk
to Team Kitty, once per token lifetime:

1. A stored, unexpired credential answers immediately. No network.
2. A stored, unexpired *negative* answer ("no team admits this repo")
   answers "do nothing". No network — the MVP's "a repo no team admitted
   produces nothing anywhere" must not cost a round trip per transition.
3. Otherwise (miss, expired stamp, or the caller forcing after a relay
   ``403``): ``GET /api/v1/sync/repo-admission/`` pre-flight first — M2-09's
   separate admission lookup kept as-is; collapsing it into the mint is
   DEFERRED.md §4 — then ``POST /api/v1/live/capability/cli/``, whose
   ``relay_url``/``relay_token``/``capability_credential``/``expires_at``
   answer is stored here.
4. Not admitted (or the mint answering ``403`` — membership revoked between
   the two calls means the same thing locally) ⇒ a short-TTL negative answer
   is stored and nothing else happens.

Every way this module can fail is environmental — no git identity, a local
or unparseable remote, nothing configured to authenticate with, Team Kitty
unreachable, admission denied — and every one of them resolves to
``None`` plus a debug log, never an exception into the caller's seam: the
caller is fire-and-forget status fan-out, and "the moment is simply lost —
by design" includes the moments lost to an unresolvable credential. The
one deliberate asymmetry: failures of the *network kind* (timeout, 5xx,
unreadable body) are never cached, so a Team Kitty blip does not pin a
false "no team" onto a repo for the negative TTL; only a genuine
"not admitted"/"denied" answer earns a negative entry.

The gateway (:class:`SaasCapabilityGateway`) is the only network code here,
kept apart from :mod:`specify_cli.saas_client.client` on purpose: that
client routes every call through the hosted-sync durable-operation
machinery (consent gate, target authority, transport leases) that E4 is
deleting, and presence broadcast must neither queue nor require hosted-sync
consent — team admission is the gate. Its two requests mirror the two
endpoints' real contracts (see the SaaS repo's ``cli_read_views.py`` and
``apps/live_capability/views.mint_cli_credential``).

Like the rest of this subpackage, expiry stamps are stored verbatim and
*interpreted* here: an expired positive credential falls through to the
mint path, an expired negative one asks Team Kitty again. An entry with no
stamp never expires — every entry written before stamps existed keeps
working exactly as before.

The store key is the full ``(host, owner/repo)`` identity Team Kitty admits
by (:func:`store_key`) — not the bare repo NAME, which two differently-
hosted repos can share (spec-kitty#129): under a shared name a hostile
same-name checkout could read another repo's cached credential, one
checkout's "not admitted" negative silenced the other for the whole
negative TTL, and each resolution overwrote the other's cached token,
forcing both back onto the network every transition. A cache hit is also
revalidated against the current ``(host, repo_slug)`` before being trusted
(:func:`_same_scope`) — defense in depth for an entry whose recorded scope
disagrees with the key it sits under; an entry with no recorded scope
(minted before scopes existed, or via the manual ``zeitgeist checkout``
path) is trusted as before.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import httpx

from kernel.clock import UTC, now_utc, parse_iso, timedelta

from specify_cli.saas_client.auth import AuthContext, load_auth_context
from specify_cli.saas_client.errors import SaasAuthError

from . import credentials, repo_identity
from .credentials import NegativeEntry, StoredCredential
from .session_identity import logical_session_id

logger = logging.getLogger(__name__)

#: What a CLI capability is minted *for*. ``event.publish`` is granted to
#: the presence credential kind (design page, Zeitgeist column), so
#: presence is the kind resolution defaults to; focus rides the same store.
KIND_PRESENCE = "presence"

#: The second grant a wired client needs (#186): zeitgeist grants the
#: ``focus.start``/``.heartbeat``/``.pause``/``.end`` ops only to the
#: ``focus`` kind, never to ``presence`` — and conversely a focus-kind token
#: cannot publish moments. One checkout therefore holds two leases, stored
#: side by side under one entry (:func:`credentials.store_focus_capability`).
KIND_FOCUS = "focus"

#: One attempt per endpoint, bounded well under the seam's own 750 ms offer
#: budget so a slow Team Kitty eats the budget instead of blowing it.
DEFAULT_TIMEOUT_S = 2.0

#: How long a stored "no team admits this repo" stands before the next
#: transition asks again. Short: admission is something a team admin fixes
#: in minutes, and the whole point of remembering the no is sparing the
#: network per-transition, not forever.
NEGATIVE_TTL_S = 300

_TEAM_SLUG_HEADER = "X-Team-Slug"

# Remote-URL grammar for the ``owner/repo`` slug + host Team Kitty admits
# by — the same hosted forms ``sync.git_metadata`` parses (SSH, HTTPS,
# ``ssh://``, SCP-like ``user@host:path``), rejected identically for
# local-file remotes. Local here because importing that module would drag
# in the whole doomed ``sync`` package; the rules are pinned by tests.
_SCP_LIKE_REMOTE_RE = re.compile(r"^(?:[^@/]+@)?(?P<host>[^:/]+):(?P<path>.+)$")


@dataclass(frozen=True)
class AdmissionAnswer:
    """The pre-flight answer, reduced to what resolution decides on."""

    admitted: bool
    team_slug: str | None = None
    reason: str | None = None


@dataclass(frozen=True)
class MintedCredential:
    """What ``POST /api/v1/live/capability/cli/`` hands back."""

    relay_url: str
    relay_token: str
    capability_credential: str | None
    expires_at: str
    session_ref: str | None = None


class GatewayError(Exception):
    """Team Kitty could not be asked, or answered unusably: transport
    fault, timeout, non-2xx, malformed body. Transient by definition —
    the resolver never caches these."""


class CapabilityDenied(GatewayError):
    """Team Kitty refused to mint (HTTP 401/403). Carries the status so
    the resolver can tell a genuine denial (403 — cache the no) from an
    unusable session (401 — cache nothing)."""

    def __init__(self, message: str, *, status_code: int) -> None:
        super().__init__(message)
        self.status_code = status_code


class SaasCapabilityGateway:
    """The two Team Kitty calls credential resolution needs, and nothing
    else. Bearer-authenticated like every other CLI→SaaS call; an optional
    team slug rides ``X-Team-Slug`` as a *selector* among the caller's own
    memberships — it can never grant one the session lacks, but a wrong
    selection deterministically refuses a membership the caller does have,
    which is why :meth:`mint_capability` accepts a per-call override."""

    def __init__(
        self,
        base_url: str,
        token: str,
        *,
        team_slug: str | None = None,
        timeout_s: float = DEFAULT_TIMEOUT_S,
        _http: httpx.Client | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._team_slug = team_slug
        self._timeout_s = timeout_s
        self._http = _http or httpx.Client(
            headers={"Authorization": f"Bearer {token}"},
            timeout=timeout_s,
        )

    def _headers(self, team_slug_override: str | None = None) -> dict[str, str]:
        slug = team_slug_override or self._team_slug
        if slug:
            return {_TEAM_SLUG_HEADER: slug}
        return {}

    def check_repo_admission(self, *, repo_slug: str, host: str | None = None) -> AdmissionAnswer:
        """``GET /api/v1/sync/repo-admission/?repo_slug=<>&host=<>``."""
        params: dict[str, str] = {"repo_slug": repo_slug}
        if host is not None:
            params["host"] = host
        try:
            resp = self._http.get(
                f"{self._base_url}/api/v1/sync/repo-admission/",
                params=params,
                headers=self._headers(),
            )
        except httpx.HTTPError as exc:
            raise GatewayError(f"admission pre-flight failed: {exc}") from exc
        if not resp.is_success:
            # Includes 401/403: from here an unusable session is
            # indistinguishable from a network fault — ask again next time,
            # cache nothing.
            raise GatewayError(f"admission pre-flight returned HTTP {resp.status_code}")
        try:
            data = resp.json()
        except ValueError as exc:
            raise GatewayError(f"admission pre-flight returned an unreadable body: {exc}") from exc
        if not isinstance(data, dict):
            raise GatewayError("admission pre-flight returned a non-object body")
        team = data.get("team")
        return AdmissionAnswer(
            admitted=bool(data.get("admitted", False)),
            team_slug=team.get("slug") if isinstance(team, dict) else None,
            reason=str(data["reason"]) if data.get("reason") is not None else None,
        )

    def mint_capability(
        self,
        *,
        repo_slug: str,
        kind: str = KIND_PRESENCE,
        team_slug: str | None = None,
    ) -> MintedCredential:
        """``POST /api/v1/live/capability/cli/`` — the member-facing mint
        (FIX-M2-15): relay URL, shared bearer, per-actor capability JWT and
        the credential's own expiry, together.

        ``team_slug`` overrides the gateway's static selector for this one
        call. Resolution always passes the team slug its admission pre-flight
        just answered with: Team Kitty honors ``X-Team-Slug`` as a hard
        selector and then re-checks admission *team-scoped*, so a member of
        teams A+B whose auth context selects A would deterministically 403 a
        mint for a repo only B admits — asking the team the pre-flight proved
        admits the repo is what makes the two calls agree."""
        selector = logical_session_id()
        try:
            resp = self._http.post(
                f"{self._base_url}/api/v1/live/capability/cli/",
                json={"repo_slug": repo_slug, "kind": kind, "logical_session_id": selector},
                headers=self._headers(team_slug),
            )
        except httpx.HTTPError as exc:
            raise GatewayError(f"capability mint failed: {exc}") from exc
        if resp.status_code in (401, 403):
            raise CapabilityDenied(
                f"capability mint denied with HTTP {resp.status_code}",
                status_code=resp.status_code,
            )
        if not resp.is_success:
            raise GatewayError(f"capability mint returned HTTP {resp.status_code}")
        try:
            data = resp.json()
        except ValueError as exc:
            raise GatewayError(f"capability mint returned an unreadable body: {exc}") from exc
        if not isinstance(data, dict):
            raise GatewayError("capability mint returned a non-object body")
        relay_url = data.get("relay_url")
        relay_token = data.get("relay_token")
        expires_at = data.get("expires_at")
        if not relay_url or not relay_token or not expires_at:
            raise GatewayError("capability mint response is missing relay_url/relay_token/expires_at")
        session_ref = data.get("session_ref")
        if not isinstance(session_ref, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", session_ref):
            raise GatewayError("capability mint response has no valid session_ref")
        if data.get("logical_session_id") != selector:
            raise GatewayError("capability mint response does not bind the logical session")
        capability_credential = data.get("capability_credential")
        return MintedCredential(
            relay_url=str(relay_url),
            relay_token=str(relay_token),
            # Omitted (not empty) means single-credential checkout -- the
            # same reading credentials.load applies on disk.
            capability_credential=str(capability_credential) if capability_credential else None,
            expires_at=str(expires_at),
            session_ref=session_ref,
        )


def repo_slug_and_host(origin_url: str) -> tuple[str | None, str | None]:
    """The ``(owner/repo, host)`` pair Team Kitty admits and mints by, from
    a checkout's origin URL — ``(None, None)`` for anything that is not a
    hosted remote (local paths, file:// remotes, unparseable shapes): there
    is nothing to ask Team Kitty about those, and guessing a slug from a
    directory name would be exactly the spoofable identity
    ``repo_identity`` refuses to mint."""
    cleaned = origin_url.strip()
    if not cleaned or cleaned.startswith(("/", "./", "../")):
        return None, None
    parsed = urlparse(cleaned)
    host: str | None
    path: str | None
    if parsed.scheme == "file":
        return None, None
    if parsed.scheme and parsed.netloc:
        host = parsed.hostname
        path = parsed.path
    else:
        match = _SCP_LIKE_REMOTE_RE.match(cleaned)
        if not match:
            return None, None
        host = match.group("host") or None
        # A single-character "host" immediately before the ":" is a Windows
        # drive letter (``C:/Users/dev/repo``), not an SCP-like remote — the
        # grammar is ambiguous between the two and a drive letter is never a
        # real git host (spec-kitty#45).
        if host is not None and len(host) == 1:
            return None, None
        path = match.group("path")

    normalized = (path or "").strip().lstrip("/").rstrip("/")
    # Case-insensitive on the suffix (a remote spelled ``.GIT`` is exotic
    # but unambiguous), unlike sync.git_metadata's case-sensitive strip --
    # every realistic input parses identically either way.
    if normalized.lower().endswith(".git"):
        normalized = normalized[:-4]
    # Full path, subgroup segments included -- a GitLab ``org/team/repo``
    # remote admits as ``org/team/repo``, not its last two segments.
    segments = [segment for segment in normalized.split("/") if segment]
    if host is None or len(segments) < 2:
        return None, None
    slug = "/".join(segments)
    return slug.lower(), host.lower()


def store_key(*, host: str | None, repo_slug: str) -> str:
    """The credential-store key for one hosted identity: ``host/owner/repo``.

    The bare repo NAME two differently-hosted checkouts can share was
    spec-kitty#129's defect: one entry per name meant a same-named checkout
    could be served (or overwrite) another repo's cached answer, and a
    "not admitted" negative for one silenced the other for the whole
    negative TTL. Keying by the pair Team Kitty admits and mints by makes
    every identity its own entry; :func:`_same_scope` stays as the
    revalidation of what is recorded *inside* an entry. ``host`` cannot
    contain ``/`` (neither URL grammar produces one), so the first segment
    is always the host and no two identities share a key.
    """
    return f"{host or ''}/{repo_slug}"


class StoreKeyError(ValueError):
    """A caller-supplied store key is not a usable ``host/owner/repo`` key —
    above all a bare NAME, the pre-#132 shape this store deliberately no
    longer serves (spec-kitty#137)."""


def _redact_userinfo(value: str) -> str:
    """Drop anything before the last ``@`` before a caller-supplied value
    is echoed back in an error message. No key :func:`store_key` writes
    ever contains ``@``, so a legitimate key is untouched; a pasted clone
    URL's userinfo (``https://x-access-token:<PAT>@host/owner/repo`` — what
    `gh`/GitHub-App clones write into ``.git/config``, and the most likely
    thing to be pasted here) is exactly what this strips before it can
    reach stdout."""
    return value.rsplit("@", 1)[-1] if "@" in value else value


def parse_store_key(value: str) -> str:
    """Canonicalize a caller-supplied credential-store key to the exact
    lowercase form :func:`store_key` writes: ``host/owner/repo``, case
    folded like :func:`repo_slug_and_host` folds a parsed origin, an
    optional trailing ``.git`` stripped for a caller pasting one straight
    off a remote URL.

    Raises :class:`StoreKeyError` for anything else — most importantly a
    bare NAME, which after #132 can only ever match an abandoned pre-#132
    entry (a live-shaped bearer nothing prunes or expiry-checks), never a
    real checkout's credential; or a pasted URL's ``scheme://`` prefix,
    which would otherwise silently mis-parse into the host segment (e.g.
    ``https://github.com/acme/widget`` → ``https:/github.com/acme/widget``)
    instead of being rejected. The rejection message never echoes the raw
    ``value`` verbatim (:func:`_redact_userinfo`) — a rejected value is, by
    definition, exactly the shape a pasted credential-bearing clone URL
    takes, and the refusal must not be the thing that leaks the credential
    (spec-kitty#150 MAJOR)."""
    cleaned = value.strip()
    displayed = _redact_userinfo(cleaned)
    error = StoreKeyError(
        f"{displayed!r} is not a Zeitgeist credential-store key: pass host/owner/repo "
        "(e.g. github.com/acme/widget), or run from inside the checkout with no key at all"
    )
    if urlparse(cleaned).scheme:
        raise error
    segments = [segment.lower() for segment in cleaned.split("/") if segment]
    if len(segments) < 3:
        raise error
    slug_segments = segments[1:]
    if slug_segments[-1].endswith(".git"):
        slug_segments[-1] = slug_segments[-1][: -len(".git")]
    if any(not segment for segment in slug_segments):
        raise error
    return store_key(host=segments[0], repo_slug="/".join(slug_segments))


def store_key_for_checkout(cwd: str | Path) -> str | None:
    """The store key of the checkout at ``cwd`` — the same
    ``(host, owner/repo)`` derivation :func:`resolve_credentials` performs
    on its origin remote (:func:`repo_identity.origin_url`, so the same
    symlink/ambiguity hardening applies), without resolution's network half.

    ``None`` when there is no resolvable hosted identity: not a git
    checkout, ambiguous identity, no origin remote, or a local-only remote.
    Read-only by design — the subscription/operability commands that call
    this must never mint or write the store as a side effect of looking."""
    try:
        origin = repo_identity.origin_url(str(cwd), repo_identity.Deadline())
    except repo_identity.RepoIdentityError:
        return None
    slug, host = repo_slug_and_host(origin)
    if slug is None or host is None:
        return None
    return store_key(host=host, repo_slug=slug)


def _expired(expires_at: str | None) -> bool:
    """Whether a verbatim ISO stamp has passed. Unstamped (every entry
    written before stamps existed) and genuinely unparseable entries never
    expire — a corrupt stamp must not lock a working credential out of its
    store.

    A stamp without an offset (a self-hosted Team Kitty running
    ``USE_TZ=False`` mints naive stamps) parses fine but cannot be compared
    against the aware clock as-is — ``aware >= naive`` raises
    ``TypeError``. Rather than treat that as unparseable and let the
    credential (or a negative "stay silent" answer) never expire, a
    successfully-parsed naive stamp is assumed UTC and compared normally: by
    the time the comparison below runs, ``parsed`` is always aware (coerced
    just above if it wasn't already), and comparing two aware ``datetime``
    values never raises ``TypeError`` regardless of differing ``tzinfo``."""
    if not expires_at:
        return False
    try:
        parsed = parse_iso(expires_at)
    except ValueError:
        return False
    if parsed.tzinfo is None:
        logger.debug("naive expires_at stamp %r coerced to UTC", expires_at)
        parsed = parsed.replace(tzinfo=UTC)
    return now_utc() >= parsed


def _default_gateway(auth_repo_root: Path) -> SaasCapabilityGateway:
    """Build the real gateway from the same auth sources every other
    CLI→SaaS transport uses (env vars, then ``<root>/.kittify/saas-auth.json``,
    then the stored ``auth login`` session — #198). Raises
    :class:`SaasAuthError` when nothing is configured — logged by the caller."""
    ctx: AuthContext = load_auth_context(repo_root=auth_repo_root)
    return SaasCapabilityGateway(
        ctx.saas_url,
        ctx.token,
        team_slug=ctx.team_slug,
    )


def cached_answer(key: str, *, repo_slug: str, host: str | None) -> tuple[bool, StoredCredential | None, NegativeEntry | None]:
    """Peek the local store for a still-valid answer — positive or a
    remembered negative — without touching the network or requiring auth
    to be configured. This is the offline fast path the module docstring
    promises; a caller must be able to reach it even when nothing is
    configured to authenticate with yet, so it never needs a gateway
    (Priivacy-ai/spec-kitty#151).

    Returns ``(True, credential, None)`` for a positive cache hit,
    ``(True, None, negative)`` for a remembered negative still inside its
    TTL, or ``(False, None, None)`` on a miss — the caller must resolve over
    the network. Returning the negative entry lets callers report its reason
    without another store read."""
    stored = credentials.load(repo=key)
    if stored is not None and not _expired(stored.expires_at) and _same_scope(stored, repo_slug=repo_slug, host=host):
        return True, stored, None
    negative = credentials.load_negative(repo=key)
    if negative is not None and not _expired(negative.expires_at):
        return True, None, negative
    return False, None, None


def _resolve(
    *,
    key: str,
    repo_slug: str,
    host: str | None,
    gateway: SaasCapabilityGateway,
    kind: str,
    force: bool,
) -> StoredCredential | None:
    """Resolution over an already-derived identity — the git-independent
    core, so every branch above is testable without a checkout."""
    if not force:
        hit, value, _negative = cached_answer(key, repo_slug=repo_slug, host=host)
        if hit:
            return value

    try:
        answer = gateway.check_repo_admission(repo_slug=repo_slug, host=host)
    except GatewayError as exc:
        logger.debug("zeitgeist credentials: admission pre-flight unavailable (%s)", exc)
        return None
    if not answer.admitted:
        credentials.store_negative(
            repo=key,
            reason=answer.reason or "",
            expires_at=(now_utc() + timedelta(seconds=NEGATIVE_TTL_S)).isoformat(),
        )
        return None

    try:
        # Ask the team the pre-flight just proved admits this repo — not
        # whatever static auth context happens to select. A member of several
        # teams whose local context names the wrong one (or none, leaving the
        # server to fall back to a default) would otherwise 403 a mint for a
        # repo that *is* admitted to them, and the cached negative would hide
        # their presence for as long as the mismatch held.
        minted = gateway.mint_capability(
            repo_slug=repo_slug,
            kind=kind,
            team_slug=answer.team_slug,
        )
    except CapabilityDenied as exc:
        # 403 is Team Kitty saying no (membership/admission changed under
        # us between pre-flight and mint) — remember it briefly. 401 is an
        # unusable session, not an answer about the repo — cache nothing.
        if exc.status_code == 403:
            credentials.store_negative(
                repo=key,
                reason="capability_denied",
                expires_at=(now_utc() + timedelta(seconds=NEGATIVE_TTL_S)).isoformat(),
            )
        else:
            logger.debug("zeitgeist credentials: mint unusable (HTTP %s)", exc.status_code)
        return None
    except GatewayError as exc:
        logger.debug("zeitgeist credentials: mint unavailable (%s)", exc)
        return None

    credentials.store(
        repo=key,
        relay_url=minted.relay_url,
        token=minted.relay_token,
        token_kind=kind,
        capability_credential=minted.capability_credential,
        expires_at=minted.expires_at,
        host=host,
        repo_slug=repo_slug,
        # #10: remember WHO admitted this repo — the pre-flight above is the
        # one place the slug is ever in hand, and `spec-kitty routes` reads it
        # back so a member can see which team binds this checkout without
        # asking Team Kitty again.
        team=answer.team_slug,
        session_ref=minted.session_ref,
    )
    return credentials.load(repo=key)


def _same_scope(stored: StoredCredential, *, repo_slug: str, host: str | None) -> bool:
    """Whether a cached credential was minted for the identity we hold now.

    The store key already separates identities (:func:`store_key`), so an
    entry reached under this checkout's key was written for it — this check
    is defense in depth for an entry whose recorded ``(host, repo_slug)``
    disagrees with the key it sits under (a manual writer, a future caller
    that keys differently): such an entry is a cache miss, not a hit. An
    entry with no recorded scope (minted before scopes existed, or via the
    manual ``zeitgeist checkout`` path) is trusted as before: the same
    backward-compatible reading ``expires_at`` already gets when it is
    absent.
    """
    if stored.repo_slug is None and stored.host is None:
        return True
    return stored.repo_slug == repo_slug and stored.host == host


def resolve_credentials(
    cwd: str | Path,
    *,
    kind: str = KIND_PRESENCE,
    force: bool = False,
    gateway: SaasCapabilityGateway | None = None,
    auth_repo_root: str | Path | None = None,
    deadline: repo_identity.Deadline | None = None,
) -> StoredCredential | None:
    """Credentials binding this checkout to its team's relay, or ``None``
    when this checkout must stay silent (no resolvable identity, no hosted
    remote, nothing configured, not admitted, Team Kitty unreachable).

    Args:
        cwd: The checkout (any directory inside it) to resolve for.
        kind: Capability kind to mint — :data:`KIND_PRESENCE` unless a
            caller specifically needs another grant.
        force: Skip the cache entirely and mint afresh. The relay-``403``
            recovery path: a caller whose stored credential just got
            rejected re-resolves with ``force=True`` rather than waiting
            out a stamp that is plainly wrong.
        gateway: Override the real Team Kitty transport (tests, alternate
            deployments). Built from the standard auth context when omitted.
        auth_repo_root: Where the fallback ``.kittify/saas-auth.json`` is
            read from when env vars are unset — the checkout root the
            caller already knows. Defaults to ``cwd``.
        deadline: Share a caller's already-open Git budget (e.g. the same
            one a presence/focus resolution in the same handler invocation
            is using) instead of allocating a fresh ``repo_identity.Deadline()``
            here (Priivacy-ai/spec-kitty#203).
    """
    cwd_str = str(cwd)
    try:
        # One Git read: the verbatim origin URL is where both the store
        # key's (host, owner/repo) scope and Team Kitty's admission question
        # come from. It used to also feed repo_name()'s bare-name key
        # (spec-kitty#129) — a name two differently-hosted repos share.
        deadline = deadline or repo_identity.Deadline()
        origin = repo_identity.origin_url(cwd_str, deadline)
    except repo_identity.RepoIdentityError as exc:
        logger.debug("zeitgeist credentials: no canonical identity for %s (%s)", cwd_str, exc)
        return None

    slug, host = repo_slug_and_host(origin)
    if slug is None:
        logger.debug("zeitgeist credentials: %s has no hosted remote to ask about", cwd_str)
        return None

    key = store_key(host=host, repo_slug=slug)

    # A cache hit answers offline and must not require auth to be
    # configured — checking before the gateway is built, not after
    # (Priivacy-ai/spec-kitty#151).
    if not force:
        hit, value, _negative = cached_answer(key, repo_slug=slug, host=host)
        if hit:
            return value

    resolved_gateway = gateway
    if resolved_gateway is None:
        try:
            resolved_gateway = _default_gateway(Path(auth_repo_root) if auth_repo_root is not None else Path(cwd))
        except SaasAuthError as exc:
            logger.debug("zeitgeist credentials: nothing configured to authenticate with (%s)", exc)
            return None

    return _resolve(
        key=key,
        repo_slug=slug,
        host=host,
        gateway=resolved_gateway,
        kind=kind,
        force=force,
    )


def resolve_focus_capability(
    cwd: str | Path,
    *,
    gateway: SaasCapabilityGateway | None = None,
    force: bool = False,
    auth_repo_root: str | Path | None = None,
    deadline: repo_identity.Deadline | None = None,
) -> str | None:
    """The checkout's ``focus``-kind capability JWT, or ``None`` when focus
    frames must stay silent (#186).

    The companion to :func:`resolve_credentials` for the second lease a
    wired client needs: zeitgeist grants the ``focus.*`` ops only to the
    ``focus`` kind (:data:`KIND_FOCUS`), never to the presence kind that
    carries ``event.publish``, so focus emission mints — and
    :func:`credentials.store_focus_capability` stores, merged into the same
    entry — its own capability. The relay bearer is shared, so this only
    ever runs against an entry :func:`resolve_credentials` already created;
    no entry means nothing to mint against and ``None`` back.

    Deliberately narrower than :func:`resolve_credentials` in one respect:
    failure here NEVER writes a negative answer. A focus denial (or Team
    Kitty being down at focus-mint time) says nothing about admission —
    caching it under the shared key would silence the moment stream too.
    Every failure resolves to ``None`` plus a debug log, like everywhere
    else in this package.

    Args:
        cwd: The checkout to resolve for (same derivation as
            :func:`resolve_credentials`).
        gateway: Override the real Team Kitty transport. Built from the
            standard auth context when omitted.
        force: Re-mint even over a stored, unexpired lease.
        auth_repo_root: Where the fallback ``.kittify/saas-auth.json`` is
            read from; defaults to ``cwd``.
        deadline: Share a caller's already-open Git budget (e.g. the same
            one credential/presence resolution in the same handler
            invocation is using) instead of allocating a fresh
            ``repo_identity.Deadline()`` here — previously this always
            opened its own, stacking a third independent budget onto one
            broadcast (Priivacy-ai/spec-kitty#203).
    """
    cwd_str = str(cwd)
    try:
        origin = repo_identity.origin_url(cwd_str, deadline or repo_identity.Deadline())
    except repo_identity.RepoIdentityError as exc:
        logger.debug("zeitgeist focus capability: no canonical identity for %s (%s)", cwd_str, exc)
        return None
    slug, host = repo_slug_and_host(origin)
    if slug is None:
        logger.debug("zeitgeist focus capability: %s has no hosted remote to ask about", cwd_str)
        return None

    key = store_key(host=host, repo_slug=slug)
    stored = credentials.load(repo=key)
    if stored is None:
        logger.debug("zeitgeist focus capability: no main credential under %s", key)
        return None
    if not _same_scope(stored, repo_slug=slug, host=host):
        # Same defense in depth as the main resolution: an entry whose
        # recorded scope disagrees with the identity it sits under is a
        # cache miss (a hostile same-name writer's lease must not serve this
        # checkout), and nothing here may mint on top of it.
        logger.debug("zeitgeist focus capability: stored credential is out of scope for %s", key)
        return None
    if not force and stored.focus_capability_credential and not _expired(stored.focus_expires_at):
        return stored.focus_capability_credential

    resolved_gateway = gateway
    if resolved_gateway is None:
        try:
            resolved_gateway = _default_gateway(Path(auth_repo_root) if auth_repo_root is not None else Path(cwd))
        except SaasAuthError as exc:
            logger.debug("zeitgeist focus capability: nothing configured to authenticate with (%s)", exc)
            return None

    # Ask the team the entry was admitted by (#10), mirroring the main
    # mint's team agreement rule.
    try:
        minted = resolved_gateway.mint_capability(
            repo_slug=slug,
            kind=KIND_FOCUS,
            team_slug=stored.team,
        )
    except CapabilityDenied as exc:
        logger.debug("zeitgeist focus capability: mint denied (HTTP %s); moments unaffected", exc.status_code)
        return None
    except GatewayError as exc:
        logger.debug("zeitgeist focus capability: mint unavailable (%s)", exc)
        return None
    if not minted.capability_credential:
        logger.debug("zeitgeist focus capability: mint returned no capability credential")
        return None

    credentials.store_focus_capability(
        repo=key,
        capability_credential=minted.capability_credential,
        expires_at=minted.expires_at,
        session_ref=minted.session_ref,
    )
    return minted.capability_credential


@dataclass(frozen=True)
class FocusLease:
    """An inseparable focus capability and its issuer-owned raw session ID."""

    capability_credential: str
    session_ref: str


def resolve_focus_lease(cwd: str | Path, *, deadline: repo_identity.Deadline | None = None) -> FocusLease | None:
    """Resolve focus authority and identity together, refusing a racing replacement."""
    capability = resolve_focus_capability(cwd, deadline=deadline)
    if capability is None:
        return None
    origin = repo_identity.origin_url(str(cwd), deadline or repo_identity.Deadline())
    slug, host = repo_slug_and_host(origin)
    if slug is None:
        return None
    stored = credentials.load(repo=store_key(host=host, repo_slug=slug))
    if stored is None or stored.focus_capability_credential != capability or not stored.focus_session_ref:
        return None
    return FocusLease(capability, stored.focus_session_ref)
