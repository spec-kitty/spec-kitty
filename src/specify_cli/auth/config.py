"""Configuration helpers for the spec-kitty auth subsystem (feature 080).

Single source of truth for the *hosted SaaS target* URL. Endpoint opt-in
(mission ``hosted-opt-in-drain-ledger``, FR-011/FR-012, reversing #3980 D-5):
there is no packaged default target any more. ``SPEC_KITTY_SAAS_URL`` (env)
and ``config.toml [sync].server_url`` (per-machine config) are the only two
sources, with precedence resolved once by
:func:`specify_cli.auth.server_target.resolve_server_target` (env over
config). With neither source naming a target, the resolver raises
:class:`~specify_cli.auth.server_target.HostedEndpointUnconfigured` — a
:class:`~specify_cli.auth.errors.ConfigurationError` subclass — carrying
setup guidance, instead of silently defaulting to a packaged host.
#179's original fail-closed reading is restored for the "nothing configured"
case; it also still fails closed for a genuinely ambiguous env/config
split-brain, guarded before any network call.
"""

from __future__ import annotations

import os
from urllib.parse import urlsplit

_ENV_VAR = "SPEC_KITTY_SAAS_URL"

#: The first-party hosted target's *identity* — the Team Kitty host. Kept
#: under this name (F-7 m4 of the post-plan squad fold; endpoint opt-in does
#: NOT rename it) even though it no longer plays a fallback/resolution role:
#: :func:`is_canonical_hosted_url`, :func:`is_noncanonical_first_party_url`,
#: and :func:`is_retired_first_party_url` key off it purely to recognize
#: "is this URL the first-party Team Kitty host", independent of how the
#: target was resolved.
DEFAULT_HOSTED_SAAS_URL = "https://team.spec-kitty.ai"

#: Guidance printed/raised when neither ``SPEC_KITTY_SAAS_URL`` nor
#: ``config.toml [sync].server_url`` names a hosted endpoint (Sonar S1192 —
#: reused by both :func:`get_saas_base_url` and
#: :func:`specify_cli.auth.server_target.resolve_server_target`, never a
#: second, independent literal). ``{config_path}`` is filled in at raise
#: time with the resolved absolute runtime-root ``config.toml`` path — never
#: at import time, since the runtime root can be ``SPEC_KITTY_HOME``-overridden
#: per invocation.
ENDPOINT_UNCONFIGURED_GUIDANCE = "No hosted endpoint configured. Set SPEC_KITTY_SAAS_URL or [sync].server_url in {config_path}."

#: The retired first-party hosted target (#4259): the pre-launch app
#: subdomain ``config.toml [sync].server_url`` still carries on machines
#: configured before #3980 promoted :data:`DEFAULT_HOSTED_SAAS_URL`. It is
#: dead first-party infrastructure — not a self-hosted endpoint — so the
#: 4.0.0 upgrade migration
#: (``m_4_0_0_retired_hosted_target``) replaces exactly this address with
#: the canonical one, and ``auth login`` warns when a resolved target still
#: names it. Hostname-exact matching only (``_hostname_of`` below): never a
#: substring test, which could fire on an unrelated domain that merely
#: contains the literal.
RETIRED_HOSTED_SAAS_URL = "https://app.spec-kitty.ai"
RETIRED_HOSTED_SAAS_HOSTNAME = "app.spec-kitty.ai"


def _hostname_of(url: str) -> str | None:
    """Return ``url``'s parsed, lowercased hostname, or ``None``.

    ``urlsplit(...).hostname`` is the exact-host parse (component-wise, never
    a substring of the whole URL), lowercased by the property itself, with
    any port/path/query already excluded. ``None`` for a value with no host
    or one that does not parse.
    """
    try:
        return urlsplit(url.strip()).hostname
    except ValueError:
        # A value that is not a URL at all (e.g. a bare token) — no hostname
        # to compare, so never a retired-host match.
        return None


def is_retired_first_party_url(url: str) -> bool:
    """True when ``url`` points at the retired first-party app endpoint.

    Hostname-exact against :data:`RETIRED_HOSTED_SAAS_HOSTNAME` (scheme,
    port, and path are ignored: any URL whose host is the retired app host
    is the retired first-party address). Every other URL — a custom or
    self-hosted endpoint on any other domain, or a look-alike domain that
    merely contains the literal — is ``False``.
    """
    return _hostname_of(url) == RETIRED_HOSTED_SAAS_HOSTNAME


def is_noncanonical_first_party_url(url: str) -> bool:
    """True when ``url`` is first-party (``spec-kitty.ai``) but not canonical.

    Canonical is the first-party host identity (:data:`DEFAULT_HOSTED_SAAS_URL`).
    Anything else under the first-party domain — the retired app subdomain,
    a docs/staging host — is first-party infrastructure the operator almost
    certainly did not mean to target, so ``auth login`` warns (never
    rejects). A self-hosted endpoint on any other domain is ``False``:
    legitimate self-hosting is supported and is not nagged as
    "noncanonical" merely for differing from the canonical host.
    """
    host = _hostname_of(url)
    if host is None:
        return False
    if host == _hostname_of(DEFAULT_HOSTED_SAAS_URL):
        return False
    return host == "spec-kitty.ai" or host.endswith(".spec-kitty.ai")


def is_canonical_hosted_url(url: str) -> bool:
    """True when ``url``'s host is the first-party host identity's host (#4265).

    Hostname-exact against :data:`DEFAULT_HOSTED_SAAS_URL`'s host, scheme and
    port ignored — the same shape :func:`is_retired_first_party_url` and
    :func:`is_noncanonical_first_party_url` already use. A raw ``url !=
    DEFAULT_HOSTED_SAAS_URL`` string comparison (the pre-#4265 shape in
    ``auth login``) mislabels a canonical host carrying an explicit default
    port (``https://team.spec-kitty.ai:443``) as a "custom endpoint"; this
    compares the parsed host instead so an equivalent URL is recognized as
    canonical regardless of an explicit default port or scheme casing.
    """
    return _hostname_of(url) == _hostname_of(DEFAULT_HOSTED_SAAS_URL)


def get_saas_url_env_override() -> str | None:
    """Return the ``SPEC_KITTY_SAAS_URL`` override (normalized), or ``None``.

    The env-only read the canonical resolver consumes for its
    ``env_server_url`` field: a dev/self-host override of the packaged
    default. An unset or blank variable is *no opinion* — never the default
    itself — so a configured ``config.toml`` target wins without tripping the
    split-brain guard.
    """
    raw = os.environ.get(_ENV_VAR)
    if raw is None:
        return None
    normalized = raw.strip().rstrip("/")
    return normalized or None


def format_endpoint_unconfigured_message() -> str:
    """Format :data:`ENDPOINT_UNCONFIGURED_GUIDANCE` with the resolved config.toml path.

    Resolved at call time (never at import time) via
    ``specify_cli.paths.get_runtime_root()`` — a lazy import, since this
    module is imported early and must not pull in the paths subsystem at
    module-load time — so a ``SPEC_KITTY_HOME`` override taken after import
    is still honored.
    """
    from specify_cli.paths import get_runtime_config_toml_path  # noqa: PLC0415

    config_path = get_runtime_config_toml_path()
    return ENDPOINT_UNCONFIGURED_GUIDANCE.format(config_path=config_path)


def get_saas_base_url() -> str:
    """Return the hosted target: the env override, or raise if unset.

    Endpoint opt-in (FR-011/FR-012): raises
    :class:`~specify_cli.auth.server_target.HostedEndpointUnconfigured` when
    ``SPEC_KITTY_SAAS_URL`` is unset — there is no packaged default to fall
    back to any more. This accessor deliberately answers only "env override,
    or unconfigured"; callers that need ``config.toml`` precedence must read
    ``resolve_server_target().resolved_server_url``
    (:func:`specify_cli.auth.server_target.resolve_server_target`) instead.

    Fenced off every token-send path (#4755, ``contracts/issuer-target-helper.md``):
    ``auth/flows/refresh.py``, ``auth/flows/revoke.py``, ``auth/token_manager.py``,
    and ``auth/websocket/token_provisioning.py`` must never call this accessor,
    because it knows nothing about a session's issuer and would silently send
    a bearer token to the wrong host on a stale/mismatched session. Those flows
    resolve their endpoint through
    :func:`specify_cli.auth.server_target.resolve_token_endpoint` instead, which
    compares the session's issuer against the resolved target and refuses on a
    mismatch. ``tests/architectural/test_egress_consent_boundary.py``'s
    issuer-target fence enforces this non-vacuously in both directions.

    Returns:
        The hosted base URL with any trailing slashes stripped.

    Raises:
        HostedEndpointUnconfigured: ``SPEC_KITTY_SAAS_URL`` is unset (or blank).
    """
    override = get_saas_url_env_override()
    if override is not None:
        return override
    # Lazy import: server_target.py imports DEFAULT_HOSTED_SAAS_URL /
    # get_saas_url_env_override from this module at its own top level, so a
    # top-level import here would be circular.
    from specify_cli.auth.server_target import HostedEndpointUnconfigured  # noqa: PLC0415

    raise HostedEndpointUnconfigured(format_endpoint_unconfigured_message())
