"""E3 credential resolution (Priivacy-ai/spec-kitty#9): cached relay
credential, capability mint on miss/expiry, short-TTL negative answers.

Three layers are covered separately:

- :func:`resolution.repo_slug_and_host` — the ``owner/repo`` + host Team
  Kitty admits by, from a checkout's origin URL; hosted forms only.
- :class:`resolution.SaasCapabilityGateway` — the two HTTP calls against
  the endpoints' real wire shapes (respx), including every non-2xx the
  resolver has to tell apart.
- the resolution core (:func:`resolution.resolve_credentials` over a real
  git clone at the bottom, its identity-free core everywhere else) — cache
  hit/expiry, negative TTL, force-after-403, and "never cache a transient
  failure".

The gateway double in the core tests is a scripted subclass of the real
class: it records its calls and plays back answers/exceptions per layer,
so no core branch depends on HTTP and no HTTP test depends on the store.
"""

from __future__ import annotations

import json as json_module
import subprocess
from pathlib import Path
from types import SimpleNamespace
from collections.abc import Iterator

import httpx
import pytest
import respx
from kernel.clock import now_utc, parse_iso, timedelta

from specify_cli.auth import reset_token_manager
from specify_cli.auth.session import StoredSession, Team
from specify_cli.saas_client import auth as saas_auth_module
from specify_cli.saas_client.errors import SaasAuthError
from specify_cli.zeitgeist_client import credentials, resolution
from specify_cli.zeitgeist_client.resolution import (
    KIND_PRESENCE,
    CapabilityDenied,
    GatewayError,
    MintedCredential,
    SaasCapabilityGateway,
)

pytestmark = pytest.mark.fast


def _iso_in(seconds: float) -> str:
    return (now_utc() + timedelta(seconds=seconds)).isoformat()


MINT_BODY = {
    "session_ref": "01ABC",
    "deployment_id": "dep-1",
    "repo_slug": "acme/widget",
    "kind": "presence",
    "relay_url": "http://127.0.0.1:9100",
    "relay_token": "shared-bearer",
    "capability_credential": "actor-jwt",
    "expires_at": _iso_in(3600),
}


@pytest.fixture()
def state_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("SPEC_KITTY_HOME", str(tmp_path / "spec-kitty-home"))
    return tmp_path / "spec-kitty-home"


class ScriptedGateway(SaasCapabilityGateway):
    """Records calls, plays back scripted outcomes. Never touches the
    network -- __init__ is deliberately not chained."""

    def __init__(
        self,
        *,
        admission: object = None,
        mint: object = None,
    ) -> None:
        self.admission_script = admission if admission is not None else {"admitted": True}
        self.mint_script = (
            mint
            if mint is not None
            else MintedCredential(
                relay_url="http://relay",
                relay_token="bearer",
                capability_credential="jwt",
                expires_at=_iso_in(3600),
            )
        )
        self.admission_calls: list[dict[str, str | None]] = []
        self.mint_calls: list[dict[str, str | None]] = []

    def check_repo_admission(self, *, repo_slug: str, host: str | None = None) -> resolution.AdmissionAnswer:
        self.admission_calls.append({"repo_slug": repo_slug, "host": host})
        outcome = self.admission_script
        if isinstance(outcome, Exception):
            raise outcome
        return resolution.AdmissionAnswer(
            admitted=bool(outcome.get("admitted", False)),  # type: ignore[union-attr]
            team_slug=(outcome or {}).get("team_slug"),  # type: ignore[union-attr]
            reason=(outcome or {}).get("reason"),  # type: ignore[union-attr]
        )

    def mint_capability(
        self,
        *,
        repo_slug: str,
        kind: str = KIND_PRESENCE,
        team_slug: str | None = None,
    ) -> MintedCredential:
        self.mint_calls.append({"repo_slug": repo_slug, "kind": kind, "team_slug": team_slug})
        outcome = self.mint_script
        if isinstance(outcome, Exception):
            raise outcome
        assert isinstance(outcome, MintedCredential)
        return outcome


# ---------------------------------------------------------------------------
# repo_slug_and_host: the identity Team Kitty admits by
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("origin", "expected"),
    [
        ("git@github.com:acme/widget.git", ("acme/widget", "github.com")),
        ("https://github.com/acme/widget.git", ("acme/widget", "github.com")),
        ("ssh://git@gitlab.com:2222/org/team/repo.git", ("org/team/repo", "gitlab.com")),
        ("git@gitlab.com:org/team/repo.git", ("org/team/repo", "gitlab.com")),
        # Case is normalized: the server stores and matches slugs lowercase.
        ("https://GitHub.com/ACME/Widget.GIT", ("acme/widget", "github.com")),
        # A .git suffix is optional on either form.
        ("git@github.com:acme/widget", ("acme/widget", "github.com")),
    ],
)
def test_hosted_remote_urls_parse_to_slug_and_host(origin: str, expected: tuple[str, str]) -> None:
    assert resolution.repo_slug_and_host(origin) == expected


@pytest.mark.parametrize(
    "origin",
    [
        "",
        "/srv/git/widget.git",  # bare local path
        "./sibling-repo",
        "../elsewhere/repo.git",
        "file:///srv/git/widget.git",  # file scheme
        "/home/dev/clones/widget.git",  # local-path origin of a test clone
        "git@github.com:single-segment",  # no owner segment
        "C:/Users/dev/repo",  # Windows drive-letter path, not an SCP-like remote
        "c:\\Users\\dev\\repo",  # same, lowercase drive letter and backslashes
    ],
)
def test_non_hosted_remotes_have_nothing_to_ask_about(origin: str) -> None:
    """A local or unparseable remote yields (None, None): guessing an
    ``owner/repo`` from it would be exactly the spoofable identity
    repo_identity refuses to mint."""
    assert resolution.repo_slug_and_host(origin) == (None, None)


class TestStoreKey:
    """spec-kitty#129: the credential store is keyed by the full
    ``(host, owner/repo)`` identity, not the bare repo NAME."""

    def test_key_is_host_then_slug(self) -> None:
        assert resolution.store_key(host="github.com", repo_slug="acme/widget") == "github.com/acme/widget"

    def test_same_name_under_different_owners_yields_distinct_keys(self) -> None:
        assert resolution.store_key(host="github.com", repo_slug="acme/widget") != resolution.store_key(host="github.com", repo_slug="evil/widget")

    def test_same_slug_on_different_hosts_yields_distinct_keys(self) -> None:
        assert resolution.store_key(host="github.com", repo_slug="acme/widget") != resolution.store_key(host="gitlab.com", repo_slug="acme/widget")

    def test_unknown_host_still_keys_uniquely_by_slug(self) -> None:
        # No hosted grammar produces an empty host, so "" cannot collide
        # with a real host segment.
        assert resolution.store_key(host=None, repo_slug="acme/widget") == "/acme/widget"


class TestParseStoreKey:
    """spec-kitty#137: the CLI accepts a caller-supplied ``host/owner/repo``
    key and never a bare NAME — after #132 nothing is stored under a bare
    name, so accepting one could only ever serve an abandoned pre-#132
    bearer."""

    def test_host_owner_repo_passes_through(self) -> None:
        assert resolution.parse_store_key("github.com/acme/widget") == "github.com/acme/widget"

    def test_subgrouped_slug_keeps_every_segment_after_the_host(self) -> None:
        assert resolution.parse_store_key("gitlab.com/org/team/repo") == "gitlab.com/org/team/repo"

    def test_is_case_folded_like_a_parsed_origin(self) -> None:
        assert resolution.parse_store_key("GitHub.com/Acme/Widget") == "github.com/acme/widget"

    @pytest.mark.parametrize("value", ["github.com/acme/widget.git", "  github.com/acme/widget  ", "github.com/acme/widget/"])
    def test_pasted_from_a_remote_url_shapes_are_normalized(self, value: str) -> None:
        assert resolution.parse_store_key(value) == "github.com/acme/widget"

    @pytest.mark.parametrize("value", ["widget", "acme/widget", "", "/acme/widget"])
    def test_bare_and_degenerate_keys_are_rejected(self, value: str) -> None:
        with pytest.raises(resolution.StoreKeyError):
            resolution.parse_store_key(value)

    @pytest.mark.parametrize("value", ["https://github.com/acme/widget", "ssh://git@github.com/acme/widget"])
    def test_a_pasted_url_with_a_scheme_is_rejected_not_misparsed(self, value: str) -> None:
        """A prior version silently swallowed the scheme into the host
        segment (``https://github.com/acme/widget`` -> the wrong key
        ``https:/github.com/acme/widget``) instead of rejecting it."""
        with pytest.raises(resolution.StoreKeyError):
            resolution.parse_store_key(value)

    @pytest.mark.parametrize(
        "value",
        [
            "github.com/acme/.git",
            "github.com/acme/.GIT",
            "github.com/acme/.git/",
        ],
    )
    def test_a_git_suffixed_owner_only_path_is_rejected_not_emptied(self, value: str) -> None:
        """Stripping a trailing ``.git`` off ``github.com/acme/.git`` would
        otherwise leave an empty last segment -- a key `store_key` never
        writes, so it must be rejected rather than silently accepted."""
        with pytest.raises(resolution.StoreKeyError):
            resolution.parse_store_key(value)

    def test_a_pasted_url_with_an_embedded_token_never_echoes_it(self) -> None:
        """spec-kitty#150 MAJOR: a pasted clone URL with an embedded PAT --
        ``https://x-access-token:<PAT>@host/owner/repo``, exactly what
        `gh`/GitHub-App clones write into ``.git/config`` -- must not have
        the token show up in the refusal message."""
        token = "ghp_SECRETTOKEN123"  # noqa: S105 - test fixture, not a real credential
        with pytest.raises(resolution.StoreKeyError) as exc_info:
            resolution.parse_store_key(f"https://x-access-token:{token}@github.com/acme/widget")
        assert token not in str(exc_info.value)


class TestStoreKeyForCheckout:
    """The read-only half of :func:`resolve_credentials`' identity
    derivation: the key the subscription/operability commands read under,
    derived from cwd exactly as the bridge derives its credential."""

    def test_hosted_checkout_yields_its_store_key(self, clone: Path) -> None:
        assert resolution.store_key_for_checkout(clone) == "github.com/acme/widget"

    def test_directory_with_no_git_identity_has_no_key(self, tmp_path: Path, no_git_ancestry_inside_tmp_path: None) -> None:
        plain = tmp_path / "not-a-repo"
        plain.mkdir()
        assert resolution.store_key_for_checkout(plain) is None

    def test_local_only_origin_has_no_key(self, tmp_path: Path) -> None:
        bare = tmp_path / "server" / "acme" / "widget.git"
        bare.mkdir(parents=True)
        subprocess.run(["git", "init", "--bare", "-q"], cwd=bare, check=True, capture_output=True)
        dest = tmp_path / "local-only"
        subprocess.run(["git", "clone", "-q", str(bare), str(dest)], check=True, capture_output=True)
        assert resolution.store_key_for_checkout(dest) is None


# ---------------------------------------------------------------------------
# SaasCapabilityGateway against the endpoints' real wire shapes (respx)
# ---------------------------------------------------------------------------

BASE = "http://teamkitty.test"
ADMISSION = f"{BASE}/api/v1/sync/repo-admission/"
MINT = f"{BASE}/api/v1/live/capability/cli/"


def _gateway(**kwargs: object) -> SaasCapabilityGateway:
    return SaasCapabilityGateway(BASE, "test-token", **kwargs)  # type: ignore[arg-type]


class TestAdmissionPreFlight:
    def test_sends_slug_and_host_query_params(self) -> None:
        with respx.mock:
            route = respx.get(ADMISSION).respond(200, json={"admitted": False, "reason": "no_match"})
            answer = _gateway().check_repo_admission(repo_slug="acme/widget", host="github.com")
        assert route.called
        sent = dict(httpx.QueryParams(route.calls[0].request.url.query))
        assert sent == {"repo_slug": "acme/widget", "host": "github.com"}
        assert answer.admitted is False
        assert answer.reason == "no_match"

    def test_omits_host_param_when_unknown(self) -> None:
        with respx.mock:
            route = respx.get(ADMISSION).respond(200, json={"admitted": False, "reason": "no_match"})
            _gateway().check_repo_admission(repo_slug="acme/widget")
        sent = dict(httpx.QueryParams(route.calls[0].request.url.query))
        assert sent == {"repo_slug": "acme/widget"}

    def test_parses_admitted_shape_with_team_slug(self) -> None:
        with respx.mock:
            respx.get(ADMISSION).respond(
                200,
                json={
                    "admitted": True,
                    "team": {"id": "T1", "slug": "acme", "name": "Acme"},
                    "provider": "github",
                    "repo_slug": "acme/widget",
                },
            )
            answer = _gateway().check_repo_admission(repo_slug="acme/widget")
        assert answer.admitted is True
        assert answer.team_slug == "acme"

    @pytest.mark.parametrize("status", [401, 403, 500])
    def test_any_non_2xx_is_a_transient_gateway_error(self, status: int) -> None:
        """The pre-flight never produces a cached answer from a status
        code -- an unusable session must not read as 'no team'."""
        with respx.mock:
            respx.get(ADMISSION).respond(status, text="denied")
            with pytest.raises(GatewayError):
                _gateway().check_repo_admission(repo_slug="acme/widget")

    def test_transport_fault_raises_gateway_error(self) -> None:
        with respx.mock:
            respx.get(ADMISSION).mock(side_effect=httpx.ConnectError("refused"))
            with pytest.raises(GatewayError):
                _gateway().check_repo_admission(repo_slug="acme/widget")

    def test_unreadable_body_raises_gateway_error(self) -> None:
        with respx.mock:
            respx.get(ADMISSION).respond(200, text="not json")
            with pytest.raises(GatewayError):
                _gateway().check_repo_admission(repo_slug="acme/widget")


class TestCapabilityMint:
    def test_success_parses_the_full_credential_triple(self) -> None:
        with respx.mock:
            route = respx.post(MINT).respond(201, json=MINT_BODY)
            minted = _gateway(team_slug="acme").mint_capability(repo_slug="acme/widget")
        assert route.called
        request = route.calls[0].request
        assert request.headers["Authorization"] == "Bearer test-token"
        assert request.headers["X-Team-Slug"] == "acme"
        assert json_module.loads(request.content) == {"repo_slug": "acme/widget", "kind": "presence"}
        assert minted.relay_url == MINT_BODY["relay_url"]
        assert minted.relay_token == MINT_BODY["relay_token"]
        assert minted.capability_credential == MINT_BODY["capability_credential"]
        assert minted.expires_at == MINT_BODY["expires_at"]

    def test_per_call_team_slug_overrides_the_static_selector(self) -> None:
        """The mint is asked of the team the pre-flight proved admits the
        repo, not whichever membership the local auth context happens to
        name — Team Kitty treats ``X-Team-Slug`` as a hard selector, so a
        member of teams A+B whose context selects A would deterministically
        403 a mint for a repo only B admits."""
        with respx.mock:
            route = respx.post(MINT).respond(201, json=MINT_BODY)
            _gateway(team_slug="team-a").mint_capability(repo_slug="acme/widget", team_slug="team-b")
        assert route.calls[0].request.headers["X-Team-Slug"] == "team-b"

    def test_no_override_falls_back_to_the_static_selector(self) -> None:
        with respx.mock:
            route = respx.post(MINT).respond(201, json=MINT_BODY)
            _gateway(team_slug="team-a").mint_capability(repo_slug="acme/widget")
        assert route.calls[0].request.headers["X-Team-Slug"] == "team-a"

    def test_neither_override_nor_static_sends_no_team_header(self) -> None:
        with respx.mock:
            route = respx.post(MINT).respond(201, json=MINT_BODY)
            _gateway().mint_capability(repo_slug="acme/widget")
        assert "X-Team-Slug" not in route.calls[0].request.headers

    def test_denial_carries_the_status_code(self) -> None:
        with respx.mock:
            respx.post(MINT).respond(403, json={"detail": "Capability denied.", "code": "repository_not_admitted"})
            with pytest.raises(CapabilityDenied) as exc_info:
                _gateway().mint_capability(repo_slug="acme/widget")
        assert exc_info.value.status_code == 403

    def test_unauthenticated_mint_is_also_a_capability_denied(self) -> None:
        with respx.mock:
            respx.post(MINT).respond(401)
            with pytest.raises(CapabilityDenied) as exc_info:
                _gateway().mint_capability(repo_slug="acme/widget")
        assert exc_info.value.status_code == 401

    def test_server_error_is_transient(self) -> None:
        with respx.mock:
            respx.post(MINT).respond(503, json={"detail": "mint_failed"})
            with pytest.raises(GatewayError) as exc_info:
                _gateway().mint_capability(repo_slug="acme/widget")
        assert not isinstance(exc_info.value, CapabilityDenied)

    def test_body_missing_relay_fields_is_transient_not_fatal(self) -> None:
        with respx.mock:
            respx.post(MINT).respond(201, json={"session_ref": "01ABC"})
            with pytest.raises(GatewayError):
                _gateway().mint_capability(repo_slug="acme/widget")

    def test_single_credential_response_yields_none_capability_field(self) -> None:
        body = dict(MINT_BODY, capability_credential="")
        with respx.mock:
            respx.post(MINT).respond(201, json=body)
            minted = _gateway().mint_capability(repo_slug="acme/widget")
        # Same reading as credentials.load: absent/empty means "use token".
        assert minted.capability_credential is None


# ---------------------------------------------------------------------------
# Expiry interpretation (verbatim stamps, caller policy lives here)
# ---------------------------------------------------------------------------


def test_expired_true_only_for_a_past_stamp() -> None:
    assert resolution._expired(_iso_in(-1)) is True
    assert resolution._expired(_iso_in(3600)) is False


def test_missing_or_garbled_stamps_never_expire() -> None:
    assert resolution._expired(None) is False
    assert resolution._expired("") is False
    assert resolution._expired("not-a-stamp") is False


def test_naive_stamp_never_raises_and_is_coerced_to_utc() -> None:
    """[squad] #14 MINOR (#36): ``expires_at`` is stored verbatim from the
    mint, and a stamp with no UTC offset (a self-hosted Team Kitty running
    ``USE_TZ=False``) parses fine but cannot be compared against the aware
    clock — ``aware >= naive`` raises ``TypeError``. Rather than treat that
    as unparseable and pin the entry to "never expires" forever, the naive
    stamp is assumed UTC and compared normally: never raises, and expires
    exactly when an equivalent aware stamp would."""
    assert resolution._expired("2026-08-25T12:00:00") is True  # naive, in the past
    assert resolution._expired("2999-01-01T00:00:00") is False  # naive, in the future


# ---------------------------------------------------------------------------
# The resolution core: cache, mint, negative TTL, force
# ---------------------------------------------------------------------------


# The store key is the hosted identity since #132 — a bare NAME key would be
# refused by credentials.store itself (spec-kitty#137).
KEY = "github.com/acme/widget"
SLUG = "acme/widget"
HOST = "github.com"


class TestCacheShortCircuits:
    def test_unexpired_positive_answers_without_touching_the_network(self, state_root: Path) -> None:
        credentials.store(
            repo=KEY,
            relay_url="http://cached",
            token="tok",
            token_kind="presence",
            expires_at=_iso_in(3600),
        )
        gateway = ScriptedGateway()
        stored = resolution._resolve(key=KEY, repo_slug=SLUG, host=HOST, gateway=gateway, kind=KIND_PRESENCE, force=False)
        assert stored is not None
        assert stored.relay_url == "http://cached"
        assert gateway.admission_calls == [] and gateway.mint_calls == []

    def test_unexpired_negative_answers_no_without_network(self, state_root: Path) -> None:
        """A repo no team admits costs one lookup per TTL window, never one
        per transition."""
        credentials.store_negative(repo=KEY, reason="no_match", expires_at=_iso_in(300))
        gateway = ScriptedGateway()
        assert resolution._resolve(key=KEY, repo_slug=SLUG, host=HOST, gateway=gateway, kind=KIND_PRESENCE, force=False) is None
        assert gateway.admission_calls == [] and gateway.mint_calls == []

    def test_force_skips_both_cached_answers_and_remints(self, state_root: Path) -> None:
        """The relay-403 recovery path: even a perfectly fresh credential is
        discarded when the caller says the relay just refused it."""
        credentials.store(repo=KEY, relay_url="http://stale", token="tok", token_kind="presence", expires_at=_iso_in(3600))
        credentials.store_negative(repo="gitlab.com/other/repo", reason="no_match", expires_at=_iso_in(300))
        gateway = ScriptedGateway(admission={"admitted": False, "reason": "no_match"})
        assert resolution._resolve(key=KEY, repo_slug=SLUG, host=HOST, gateway=gateway, kind=KIND_PRESENCE, force=True) is None
        assert len(gateway.admission_calls) == 1
        assert credentials.load_negative(repo=KEY) is not None

    def test_naive_stamp_on_a_stored_credential_answers_from_cache(self, state_root: Path) -> None:
        """End to end through the cache path: a stored entry whose verbatim
        stamp has no UTC offset must answer from the store — never raise
        out of resolution — for as long as the coerced-to-UTC stamp says
        it is still valid."""
        credentials.store(
            repo=KEY,
            relay_url="http://naive",
            token="tok",
            token_kind="presence",
            expires_at="2999-01-01T00:00:00",  # naive, far in the future
        )
        gateway = ScriptedGateway()
        stored = resolution._resolve(key=KEY, repo_slug=SLUG, host=HOST, gateway=gateway, kind=KIND_PRESENCE, force=False)
        assert stored is not None
        assert stored.relay_url == "http://naive"
        # Answered from cache — no network was touched deciding it.
        assert gateway.admission_calls == [] and gateway.mint_calls == []

    def test_naive_stamp_on_a_negative_answer_stays_silent_without_raising(self, state_root: Path) -> None:
        """And on the negative path: an unparseable-at-comparison stamp must
        not turn "stay silent" into "raise" — for as long as the coerced
        stamp says the negative TTL has not lapsed."""
        credentials.store_negative(repo=KEY, reason="no_match", expires_at="2999-01-01T00:00:00")
        gateway = ScriptedGateway()
        assert resolution._resolve(key=KEY, repo_slug=SLUG, host=HOST, gateway=gateway, kind=KIND_PRESENCE, force=False) is None
        assert gateway.admission_calls == [] and gateway.mint_calls == []

    def test_expired_naive_stamp_on_a_stored_credential_falls_through_to_the_mint(self, state_root: Path) -> None:
        """[squad] #14 MINOR (#36): a naive stamp in the past must not pin
        the credential as immortal — it falls through to the mint exactly
        like an equivalent aware expired stamp would."""
        credentials.store(
            repo=KEY,
            relay_url="http://stale-naive",
            token="tok",
            token_kind="presence",
            expires_at="2026-08-25T12:00:00",  # naive, in the past
        )
        gateway = ScriptedGateway()
        stored = resolution._resolve(key=KEY, repo_slug=SLUG, host=HOST, gateway=gateway, kind=KIND_PRESENCE, force=False)
        assert stored is not None
        assert stored.relay_url == "http://relay"  # the freshly minted one, not the stale cache
        assert len(gateway.admission_calls) == 1 and len(gateway.mint_calls) == 1

    def test_expired_naive_stamp_on_a_negative_answer_asks_again(self, state_root: Path) -> None:
        """[squad] #14 MINOR (#36): a naive stamp in the past on a negative
        entry must not pin "stay silent" forever — it retries the network
        exactly like an equivalent aware expired negative stamp would."""
        credentials.store_negative(repo=KEY, reason="no_match", expires_at="2026-08-25T12:00:00")
        gateway = ScriptedGateway()
        stored = resolution._resolve(key=KEY, repo_slug=SLUG, host=HOST, gateway=gateway, kind=KIND_PRESENCE, force=False)
        assert stored is not None  # this time admitted, per ScriptedGateway()'s default script
        assert len(gateway.admission_calls) == 1


class TestCachedAnswer:
    """:func:`resolution.cached_answer` — the gateway-free peek `_resolve`
    and `resolve_credentials` both build on (Priivacy-ai/spec-kitty#151)."""

    def test_miss_when_nothing_stored(self, state_root: Path) -> None:
        assert resolution.cached_answer(KEY, repo_slug=SLUG, host=HOST) == (False, None, None)

    def test_hit_on_an_unexpired_positive(self, state_root: Path) -> None:
        credentials.store(repo=KEY, relay_url="http://cached", token="tok", token_kind="presence", expires_at=_iso_in(3600))
        hit, value, negative = resolution.cached_answer(KEY, repo_slug=SLUG, host=HOST)
        assert hit is True
        assert value is not None
        assert negative is None
        assert value.relay_url == "http://cached"

    def test_hit_on_an_unexpired_negative(self, state_root: Path) -> None:
        credentials.store_negative(repo=KEY, reason="no_match", expires_at=_iso_in(300))
        hit, value, negative = resolution.cached_answer(KEY, repo_slug=SLUG, host=HOST)
        assert hit is True
        assert value is None
        assert negative is not None
        assert negative.reason == "no_match"

    def test_miss_on_an_expired_positive(self, state_root: Path) -> None:
        credentials.store(repo=KEY, relay_url="http://stale", token="tok", token_kind="presence", expires_at=_iso_in(-1))
        assert resolution.cached_answer(KEY, repo_slug=SLUG, host=HOST) == (False, None, None)

    def test_miss_on_an_out_of_scope_entry(self, state_root: Path) -> None:
        credentials.store(
            repo=KEY,
            relay_url="http://cached",
            token="tok",
            token_kind="presence",
            expires_at=_iso_in(3600),
            host="gitlab.com",
            repo_slug="other/repo",
        )
        assert resolution.cached_answer(KEY, repo_slug=SLUG, host=HOST) == (False, None, None)


class TestScopeRevalidation:
    """Squad finding on #123: the store key was the bare repo NAME, which
    two differently-hosted repos could share -- #132 moved the key to
    ``resolution.store_key``'s ``host/owner/repo``."""

    def test_cache_hit_for_the_same_scope_is_trusted(self, state_root: Path) -> None:
        credentials.store(
            repo=KEY,
            relay_url="http://cached",
            token="tok",
            token_kind="presence",
            expires_at=_iso_in(3600),
            host=HOST,
            repo_slug=SLUG,
        )
        gateway = ScriptedGateway()
        stored = resolution._resolve(key=KEY, repo_slug=SLUG, host=HOST, gateway=gateway, kind=KIND_PRESENCE, force=False)
        assert stored is not None
        assert stored.relay_url == "http://cached"
        assert gateway.admission_calls == [] and gateway.mint_calls == []

    def test_cache_hit_scoped_to_a_different_repo_slug_falls_through_to_a_fresh_check(self, state_root: Path) -> None:
        """A hostile same-name checkout must not read someone else's cached
        admitted credential -- a scope mismatch is a cache miss, not a hit."""
        credentials.store(
            repo=KEY,
            relay_url="http://someone-elses-relay",
            token="someone-elses-token",
            token_kind="presence",
            expires_at=_iso_in(3600),
            host=HOST,
            repo_slug="other-owner/widget",
        )
        gateway = ScriptedGateway()
        stored = resolution._resolve(key=KEY, repo_slug=SLUG, host=HOST, gateway=gateway, kind=KIND_PRESENCE, force=False)
        assert stored is not None
        assert stored.relay_url == "http://relay"  # freshly minted, not the mismatched cache entry
        assert len(gateway.admission_calls) == 1
        assert len(gateway.mint_calls) == 1

    def test_cache_hit_scoped_to_a_different_host_falls_through_to_a_fresh_check(self, state_root: Path) -> None:
        credentials.store(
            repo=KEY,
            relay_url="http://someone-elses-relay",
            token="someone-elses-token",
            token_kind="presence",
            expires_at=_iso_in(3600),
            host="gitlab.com",
            repo_slug=SLUG,
        )
        gateway = ScriptedGateway()
        stored = resolution._resolve(key=KEY, repo_slug=SLUG, host=HOST, gateway=gateway, kind=KIND_PRESENCE, force=False)
        assert stored is not None
        assert stored.relay_url == "http://relay"
        assert len(gateway.admission_calls) == 1

    def test_legacy_entry_with_no_recorded_scope_is_still_trusted(self, state_root: Path) -> None:
        """Every credential minted before this fix (and every manual
        `zeitgeist checkout`) has no recorded scope -- it must keep being
        served from cache exactly as before, or every existing checkout
        would silently re-mint on its next transition."""
        credentials.store(
            repo=KEY,
            relay_url="http://legacy",
            token="legacy-tok",
            token_kind="presence",
            expires_at=_iso_in(3600),
        )
        gateway = ScriptedGateway()
        stored = resolution._resolve(key=KEY, repo_slug=SLUG, host=HOST, gateway=gateway, kind=KIND_PRESENCE, force=False)
        assert stored is not None
        assert stored.relay_url == "http://legacy"
        assert gateway.admission_calls == [] and gateway.mint_calls == []

    def test_a_fresh_mint_records_its_own_scope(self, state_root: Path) -> None:
        gateway = ScriptedGateway()
        resolution._resolve(key=KEY, repo_slug=SLUG, host=HOST, gateway=gateway, kind=KIND_PRESENCE, force=False)
        stored = credentials.load(repo=KEY)
        assert stored is not None
        assert stored.repo_slug == SLUG
        assert stored.host == HOST


class TestNotAdmitted:
    def test_admission_miss_stores_a_short_ttl_negative(self, state_root: Path) -> None:
        gateway = ScriptedGateway(admission={"admitted": False, "reason": "no_match"})
        assert resolution._resolve(key=KEY, repo_slug=SLUG, host=HOST, gateway=gateway, kind=KIND_PRESENCE, force=False) is None
        negative = credentials.load_negative(repo=KEY)
        assert negative is not None
        assert negative.reason == "no_match"
        # The stamp really is a ~NEGATIVE_TTL_S horizon, parsed back.
        expiry = now_utc() + timedelta(seconds=resolution.NEGATIVE_TTL_S)
        assert resolution._expired(negative.expires_at) is False
        assert negative.expires_at is not None and abs((_parse(negative.expires_at) - expiry).total_seconds()) < 5

    def test_expired_negative_asks_again_and_can_flip_to_admitted(self, state_root: Path) -> None:
        credentials.store_negative(repo=KEY, reason="no_match", expires_at=_iso_in(-1))
        gateway = ScriptedGateway()
        stored = resolution._resolve(key=KEY, repo_slug=SLUG, host=HOST, gateway=gateway, kind=KIND_PRESENCE, force=False)
        assert stored is not None
        assert credentials.load_negative(repo=KEY) is None


class TestMintPaths:
    def test_miss_mints_and_stores_under_the_canonical_key(self, state_root: Path) -> None:
        gateway = ScriptedGateway()
        stored = resolution._resolve(key=KEY, repo_slug=SLUG, host=HOST, gateway=gateway, kind=KIND_PRESENCE, force=False)
        assert gateway.admission_calls == [{"repo_slug": SLUG, "host": HOST}]
        assert gateway.mint_calls == [{"repo_slug": SLUG, "kind": "presence", "team_slug": None}]
        assert stored is not None
        assert stored.relay_url == "http://relay"
        assert stored.token_kind == "presence"
        assert stored.capability_credential == "jwt"
        # What came back is what the store holds -- same entry, same key.
        assert credentials.load(repo=KEY) == stored
        assert credentials.load_negative(repo=KEY) is None

    def test_mint_is_asked_of_the_team_admission_named(self, state_root: Path) -> None:
        """[squad] MAJOR regression: a member of teams A+B whose local auth
        context selects A, for a repo only B admits. The pre-flight answers
        ``admitted=true`` *naming B* — that slug is the disambiguating datum,
        and the mint must carry it as its ``X-Team-Slug``, or Team Kitty
        re-checks admission against A and deterministically 403s an admitted
        member into a cached negative."""
        gateway = ScriptedGateway(admission={"admitted": True, "team_slug": "team-b"})
        stored = resolution._resolve(key=KEY, repo_slug=SLUG, host=HOST, gateway=gateway, kind=KIND_PRESENCE, force=False)
        assert gateway.mint_calls == [{"repo_slug": SLUG, "kind": "presence", "team_slug": "team-b"}]
        assert stored is not None
        # And the positive answer is cached, not a 5-minute silence.
        assert credentials.load(repo=KEY) == stored

    def test_mint_403_becomes_a_negative_answer(self, state_root: Path) -> None:
        """Membership revoked between pre-flight and mint: Team Kitty said
        no about THIS repo, so remember the no briefly."""
        gateway = ScriptedGateway(mint=CapabilityDenied("denied", status_code=403))
        assert resolution._resolve(key=KEY, repo_slug=SLUG, host=HOST, gateway=gateway, kind=KIND_PRESENCE, force=False) is None
        negative = credentials.load_negative(repo=KEY)
        assert negative is not None
        assert negative.reason == "capability_denied"

    def test_mint_401_caches_nothing(self, state_root: Path) -> None:
        """An unusable session says nothing about the repo -- next call must
        ask again, not inherit a false 'not admitted'."""
        gateway = ScriptedGateway(mint=CapabilityDenied("unauthorized", status_code=401))
        assert resolution._resolve(key=KEY, repo_slug=SLUG, host=HOST, gateway=gateway, kind=KIND_PRESENCE, force=False) is None
        assert credentials.load(repo=KEY) is None
        assert credentials.load_negative(repo=KEY) is None

    @pytest.mark.parametrize(
        "failure",
        [
            GatewayError("timeout"),
            GatewayError("HTTP 500"),
        ],
    )
    def test_transient_failures_cache_nothing(self, state_root: Path, failure: Exception) -> None:
        """A Team Kitty blip must not pin a false 'no team' onto an admitted
        repo for the whole negative TTL."""
        gateway = ScriptedGateway(admission=failure)
        assert resolution._resolve(key=KEY, repo_slug=SLUG, host=HOST, gateway=gateway, kind=KIND_PRESENCE, force=False) is None
        assert credentials.load(repo=KEY) is None
        assert credentials.load_negative(repo=KEY) is None

    def test_expired_positive_credential_falls_through_to_the_mint(self, state_root: Path) -> None:
        credentials.store(
            repo=KEY,
            relay_url="http://old",
            token="old-tok",
            token_kind="presence",
            expires_at=_iso_in(-1),
        )
        gateway = ScriptedGateway()
        stored = resolution._resolve(key=KEY, repo_slug=SLUG, host=HOST, gateway=gateway, kind=KIND_PRESENCE, force=False)
        assert len(gateway.mint_calls) == 1
        assert stored is not None
        assert stored.token == "bearer"


def _parse(stamp: str):
    return parse_iso(stamp)


# ---------------------------------------------------------------------------
# resolve_credentials end to end over a real clone: canonical key + slug
# derivation wired together (the only git-backed tests in this file)
# ---------------------------------------------------------------------------


def _checkout_with_origin(bare: Path, dest: Path, origin: str) -> Path:
    """A minimal checkout whose origin claims ``origin``."""
    bare.mkdir(parents=True)
    subprocess.run(["git", "init", "--bare", "-q"], cwd=bare, check=True, capture_output=True)
    dest.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "clone", "-q", str(bare), str(dest)], check=True, capture_output=True)
    subprocess.run(["git", "remote", "set-url", "origin", origin], cwd=dest, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=dest, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=dest, check=True, capture_output=True)
    (dest / "f.txt").write_text("x")
    subprocess.run(["git", "add", "f.txt"], cwd=dest, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=dest, check=True, capture_output=True)
    return dest


@pytest.fixture()
def clone(tmp_path: Path) -> Path:
    """A checkout whose origin claims to be github.com/acme/widget."""
    return _checkout_with_origin(
        tmp_path / "gh" / "acme" / "widget.git",
        tmp_path / "work" / "acme" / "widget",
        "https://github.com/acme/widget.git",
    )


class TestResolveCredentialsEndToEnd:
    def test_identity_and_slug_are_derived_from_the_checkout_itself(self, state_root: Path, clone: Path, instead_of_rewrite: str) -> None:
        gateway = ScriptedGateway()
        stored = resolution.resolve_credentials(clone, gateway=gateway)  # type: ignore[arg-type]
        assert stored is not None
        # Store key: the (host, owner/repo) identity Team Kitty admits by ...
        assert credentials.load(repo="github.com/acme/widget") == stored
        # ... while Team Kitty is asked about the owner/repo slug + host.
        # The fixture rewrites github.com onto a machine-local transport
        # proxy; the checkout's own origin must win (#81) — a proxy host
        # here was Team Kitty being asked to admit a forge it never knew.
        assert gateway.admission_calls == [{"repo_slug": "acme/widget", "host": "github.com"}]
        assert instead_of_rewrite not in str(gateway.admission_calls)

    def test_second_call_never_leaves_the_machine(self, state_root: Path, clone: Path) -> None:
        first = ScriptedGateway()
        assert resolution.resolve_credentials(clone, gateway=first) is not None  # type: ignore[arg-type]
        second = ScriptedGateway()
        cached = resolution.resolve_credentials(clone, gateway=second)  # type: ignore[arg-type]
        assert cached is not None
        assert second.admission_calls == [] and second.mint_calls == []

    def test_directory_with_no_git_identity_stays_silent(
        self,
        state_root: Path,
        tmp_path: Path,
        no_git_ancestry_inside_tmp_path: None,
    ) -> None:
        plain = tmp_path / "not-a-repo"
        plain.mkdir()
        gateway = ScriptedGateway()
        assert resolution.resolve_credentials(plain, gateway=gateway) is None  # type: ignore[arg-type]
        assert gateway.admission_calls == []

    def test_local_path_origin_has_nothing_to_ask_about(self, state_root: Path, tmp_path: Path) -> None:
        bare = tmp_path / "server" / "acme" / "widget.git"
        bare.mkdir(parents=True)
        subprocess.run(["git", "init", "--bare", "-q"], cwd=bare, check=True, capture_output=True)
        dest = tmp_path / "local-only"
        subprocess.run(["git", "clone", "-q", str(bare), str(dest)], check=True, capture_output=True)
        gateway = ScriptedGateway()
        assert resolution.resolve_credentials(dest, gateway=gateway) is None  # type: ignore[arg-type]
        assert gateway.admission_calls == []


class TestResolveCredentialsHonorsASharedDeadline:
    """#203: a caller broadcasting one status transition shares ONE Git
    deadline across credential resolution, presence identity, and the focus
    capability lookup — each independently minting its own fresh
    ``repo_identity.Deadline()`` stacks three 2.0s budgets under the
    fan-out seam's 10s bound. These assert the shared object is actually
    threaded through to ``origin_url``, not silently re-minted."""

    def test_resolve_credentials_passes_the_given_deadline_to_origin_url(self, state_root: Path, clone: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        shared = resolution.repo_identity.Deadline()
        seen: list[object] = []
        real_origin_url = resolution.repo_identity.origin_url

        def _spy(cwd: str, deadline=None):
            seen.append(deadline)
            return real_origin_url(cwd, deadline)

        monkeypatch.setattr(resolution.repo_identity, "origin_url", _spy)
        gateway = ScriptedGateway()
        resolution.resolve_credentials(clone, gateway=gateway, deadline=shared)  # type: ignore[arg-type]

        assert seen == [shared], "resolve_credentials must forward the caller's Deadline, not mint its own"

    def test_resolve_credentials_mints_its_own_deadline_when_none_is_given(self, state_root: Path, clone: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        seen: list[object] = []
        real_origin_url = resolution.repo_identity.origin_url

        def _spy(cwd: str, deadline=None):
            seen.append(deadline)
            return real_origin_url(cwd, deadline)

        monkeypatch.setattr(resolution.repo_identity, "origin_url", _spy)
        gateway = ScriptedGateway()
        resolution.resolve_credentials(clone, gateway=gateway)  # type: ignore[arg-type]

        assert len(seen) == 1  # one origin_url call, not a named set
        assert isinstance(seen[0], resolution.repo_identity.Deadline)

    def test_resolve_focus_capability_passes_the_given_deadline_to_origin_url(self, state_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        credentials.store(repo=KEY, relay_url="http://relay", token="bearer", token_kind=KIND_PRESENCE)
        shared = resolution.repo_identity.Deadline()
        seen: list[object] = []

        def _spy(cwd: str, deadline=None):
            seen.append(deadline)
            return "https://github.com/acme/widget.git"

        monkeypatch.setattr(resolution.repo_identity, "origin_url", _spy)
        gateway = ScriptedGateway(
            mint=MintedCredential(
                relay_url="http://relay",
                relay_token="bearer",
                capability_credential="focus-jwt",
                expires_at=_iso_in(1800),
            )
        )
        resolution.resolve_focus_capability("/checkout", gateway=gateway, deadline=shared)

        assert seen == [shared], "resolve_focus_capability must forward the caller's Deadline, not mint its own"


ACME_KEY = "github.com/acme/widget"
EVIL_KEY = "github.com/evil/widget"


class _ScriptedLoginSession:
    """A stored ``auth login`` session + its manager, for bridging tests.

    The session starts with an already-expired access token; ``refresh_if_needed``
    rotates it the way the renewable-session flow leaves the manager's session,
    and records that it ran."""

    def __init__(self) -> None:
        now = now_utc()
        self.refresh_calls = 0
        self.session = StoredSession(
            user_id="user-1",
            email="member@example.com",
            name="Member",
            teams=[Team(id="t1", name="Acme", role="member", is_private_teamspace=False)],
            default_team_id="t1",
            access_token="access-expired",
            refresh_token="refresh-v1",
            session_id="sess-1",
            issued_at=now,
            access_token_expires_at=now - timedelta(seconds=30),
            refresh_token_expires_at=None,
            scope="openid",
            storage_backend="file",
            last_used_at=now,
            auth_method="authorization_code",
        )

    def get_current_session(self) -> StoredSession:
        return self.session

    async def refresh_if_needed(self) -> bool:
        self.refresh_calls += 1
        self.session.access_token = "access-refreshed"
        self.session.access_token_expires_at = now_utc() + timedelta(seconds=900)
        return True


class TestOAuthSessionCarriesTheMint:
    """spec-kitty#198: a member on the documented path has no service token —
    env and ``.kittify/saas-auth.json`` are empty and all they ever ran is
    ``spec-kitty auth login``. Resolution must still mint, off the stored
    OAuth session, refreshing it first when its access token has expired.

    These drive the REAL gateway (respx) through ``resolve_credentials``'s
    own default-gateway construction, so what is asserted is the bearer that
    actually reaches Team Kitty."""

    @pytest.fixture(autouse=True)
    def _fresh_token_manager(self) -> Iterator[None]:
        # The bridge consults the process-wide TokenManager singleton, which
        # caches whichever SPEC_KITTY_HOME was current when it was first
        # built — reset so every test reads its own isolated store.
        reset_token_manager()
        yield
        reset_token_manager()

    @pytest.fixture()
    def expired_login(self, monkeypatch: pytest.MonkeyPatch) -> _ScriptedLoginSession:
        """No env auth anywhere; the bridge resolves to an expired session."""
        for var in ("SPEC_KITTY_SAAS_TOKEN", "SPEC_KITTY_SAAS_URL", "SPEC_KITTY_TEAM_SLUG"):
            monkeypatch.delenv(var, raising=False)
        login = _ScriptedLoginSession()
        target = SimpleNamespace(resolved_server_url=BASE)
        monkeypatch.setattr(saas_auth_module, "_token_manager", lambda: login)
        monkeypatch.setattr(saas_auth_module, "_resolved_server_target", lambda: target)
        return login

    def test_expired_session_is_refreshed_then_minted(self, state_root: Path, clone: Path, expired_login: _ScriptedLoginSession) -> None:
        with respx.mock:
            admission = respx.get(ADMISSION).respond(200, json={"admitted": True, "team": {"id": "T1", "slug": "acme", "name": "Acme"}})
            mint = respx.post(MINT).respond(201, json=MINT_BODY)
            stored = resolution.resolve_credentials(clone)

        assert expired_login.refresh_calls == 1
        # Both Team Kitty calls rode the REFRESHED bearer, not the expired one.
        assert admission.calls[0].request.headers["Authorization"] == "Bearer access-refreshed"
        assert mint.calls[0].request.headers["Authorization"] == "Bearer access-refreshed"
        assert stored is not None
        assert credentials.load(repo=KEY) == stored

    def test_unadmitted_repo_through_the_bridge_stays_silent(self, state_root: Path, clone: Path, expired_login: _ScriptedLoginSession) -> None:
        with respx.mock:
            respx.get(ADMISSION).respond(200, json={"admitted": False, "reason": "no team admits acme/widget"})
            mint = respx.post(MINT).respond(201, json=MINT_BODY)
            stored = resolution.resolve_credentials(clone)

        assert stored is None
        assert not mint.called  # never asked for a capability it may not have
        assert credentials.load_negative(repo=KEY) is not None


class TestTwoCheckoutProbe:
    """spec-kitty#129's acceptance probe: ``acme/widget`` and ``evil/widget``
    are two same-named checkouts that differ in owner. Under the bare-name
    store key they shared ONE entry — the second checkout could be served
    (or overwrite) the first's cached credential, each resolution evicted
    the other's token back onto the network, and one checkout's "not
    admitted" negative silenced the other for the whole TTL."""

    @pytest.fixture()
    def two_clones(self, tmp_path: Path) -> tuple[Path, Path]:
        acme = _checkout_with_origin(
            tmp_path / "gh-acme" / "widget.git",
            tmp_path / "work" / "acme" / "widget",
            "https://github.com/acme/widget.git",
        )
        evil = _checkout_with_origin(
            tmp_path / "gh-evil" / "widget.git",
            tmp_path / "work" / "evil" / "widget",
            "https://github.com/evil/widget.git",
        )
        return acme, evil

    def test_each_checkout_mints_and_stores_under_its_own_key(self, state_root: Path, two_clones: tuple[Path, Path]) -> None:
        acme, evil = two_clones
        acme_gateway = ScriptedGateway()
        evil_gateway = ScriptedGateway()
        first = resolution.resolve_credentials(acme, gateway=acme_gateway)  # type: ignore[arg-type]
        second = resolution.resolve_credentials(evil, gateway=evil_gateway)  # type: ignore[arg-type]
        assert first is not None and second is not None
        # Distinct keys: neither entry is reachable under the other's.
        assert credentials.load(repo=ACME_KEY) == first
        assert credentials.load(repo=EVIL_KEY) == second
        assert credentials.load(repo="widget") is None
        # And each mint was asked about its own owner/repo slug.
        assert [call["repo_slug"] for call in acme_gateway.mint_calls] == ["acme/widget"]
        assert [call["repo_slug"] for call in evil_gateway.mint_calls] == ["evil/widget"]

    def test_second_checkout_mints_its_own_not_the_first_cached_one(self, state_root: Path, two_clones: tuple[Path, Path]) -> None:
        acme, evil = two_clones
        assert resolution.resolve_credentials(acme, gateway=ScriptedGateway()) is not None  # type: ignore[arg-type]
        evil_gateway = ScriptedGateway(
            mint=MintedCredential(
                relay_url="http://evil-relay",
                relay_token="evil-bearer",
                capability_credential="evil-jwt",
                expires_at=_iso_in(3600),
            )
        )
        stored = resolution.resolve_credentials(evil, gateway=evil_gateway)  # type: ignore[arg-type]
        assert stored is not None
        # Minted its own credential for its own slug -- not a re-serve of the
        # entry acme's resolution had already cached under the shared name.
        assert stored.relay_url == "http://evil-relay"
        assert [call["repo_slug"] for call in evil_gateway.mint_calls] == ["evil/widget"]
        assert credentials.load(repo=EVIL_KEY) == stored

    def test_one_checkouts_cached_answer_survives_the_other_resolving(self, state_root: Path, two_clones: tuple[Path, Path]) -> None:
        """Under the shared key each checkout's mint evicted the other's,
        forcing both onto the network on every transition; distinct keys
        keep both caches warm."""
        acme, evil = two_clones
        assert resolution.resolve_credentials(acme, gateway=ScriptedGateway()) is not None  # type: ignore[arg-type]
        assert resolution.resolve_credentials(evil, gateway=ScriptedGateway()) is not None  # type: ignore[arg-type]
        fresh_gateway = ScriptedGateway()
        cached = resolution.resolve_credentials(acme, gateway=fresh_gateway)  # type: ignore[arg-type]
        assert cached is not None
        assert fresh_gateway.admission_calls == [] and fresh_gateway.mint_calls == []

    def test_not_admitted_for_one_does_not_silence_the_other(self, state_root: Path, two_clones: tuple[Path, Path]) -> None:
        acme, evil = two_clones
        evil_gateway = ScriptedGateway(admission={"admitted": False, "reason": "no_match"})
        assert resolution.resolve_credentials(evil, gateway=evil_gateway) is None  # type: ignore[arg-type]
        assert credentials.load_negative(repo=EVIL_KEY) is not None
        acme_gateway = ScriptedGateway()
        stored = resolution.resolve_credentials(acme, gateway=acme_gateway)  # type: ignore[arg-type]
        # Admitted all along -- evil's negative must not answer for it.
        assert stored is not None
        assert len(acme_gateway.mint_calls) == 1


class TestDefaultGatewayConstruction:
    def test_env_config_builds_the_real_gateway(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setenv("SPEC_KITTY_SAAS_URL", "http://saas.test")
        monkeypatch.setenv("SPEC_KITTY_SAAS_TOKEN", "tok")
        monkeypatch.setenv("SPEC_KITTY_TEAM_SLUG", "acme")
        built = resolution._default_gateway(tmp_path)
        assert built is not None
        assert built._base_url == "http://saas.test"

    def test_nothing_configured_raises_saas_auth_error(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.delenv("SPEC_KITTY_SAAS_URL", raising=False)
        monkeypatch.delenv("SPEC_KITTY_SAAS_TOKEN", raising=False)
        monkeypatch.delenv("SPEC_KITTY_TEAM_SLUG", raising=False)
        empty_root = tmp_path / "checkout-without-auth-file"
        (empty_root / ".git").mkdir(parents=True)
        with pytest.raises(SaasAuthError):
            resolution._default_gateway(empty_root)

    def test_unconfigured_checkout_resolves_quietly_to_none(self, state_root: Path, monkeypatch: pytest.MonkeyPatch, clone: Path) -> None:
        """The full quiet path: a real checkout, nothing configured -- the
        seam must see None, never an exception."""
        monkeypatch.delenv("SPEC_KITTY_SAAS_URL", raising=False)
        monkeypatch.delenv("SPEC_KITTY_SAAS_TOKEN", raising=False)
        monkeypatch.delenv("SPEC_KITTY_TEAM_SLUG", raising=False)
        assert resolution.resolve_credentials(clone, auth_repo_root=clone) is None
        assert credentials.load(repo="github.com/acme/widget") is None

    def test_cached_credential_answers_offline_even_when_nothing_is_configured_to_authenticate_with(
        self, state_root: Path, monkeypatch: pytest.MonkeyPatch, clone: Path
    ) -> None:
        """Priivacy-ai/spec-kitty#151: a stored credential must answer
        offline before the gateway is ever built, so a checkout with a
        cached credential but no auth configured anywhere still gets it —
        not the quiet ``None`` an auth failure would otherwise produce."""
        monkeypatch.delenv("SPEC_KITTY_SAAS_URL", raising=False)
        monkeypatch.delenv("SPEC_KITTY_SAAS_TOKEN", raising=False)
        monkeypatch.delenv("SPEC_KITTY_TEAM_SLUG", raising=False)
        credentials.store(
            repo="github.com/acme/widget",
            relay_url="http://relay",
            token="bearer",
            token_kind=KIND_PRESENCE,
            expires_at=_iso_in(3600),
            host="github.com",
            repo_slug="acme/widget",
            team="demo",
        )
        stored = resolution.resolve_credentials(clone, auth_repo_root=clone)
        assert stored is not None
        assert stored.team == "demo"

    def test_cached_negative_answers_offline_even_when_nothing_is_configured_to_authenticate_with(
        self, state_root: Path, monkeypatch: pytest.MonkeyPatch, clone: Path
    ) -> None:
        """Same fix, the remembered-negative branch."""
        monkeypatch.delenv("SPEC_KITTY_SAAS_URL", raising=False)
        monkeypatch.delenv("SPEC_KITTY_SAAS_TOKEN", raising=False)
        monkeypatch.delenv("SPEC_KITTY_TEAM_SLUG", raising=False)
        credentials.store_negative(repo="github.com/acme/widget", reason="stale-reason")
        assert resolution.resolve_credentials(clone, auth_repo_root=clone) is None
        # Distinguishing "cached no" from "auth error, no answer" matters to
        # callers like `spec-kitty routes` — confirm it stayed a cache hit,
        # not a fall-through past a `SaasAuthError`, via the negative record
        # itself: still present and unexpired, never touched by this call.
        negative = credentials.load_negative(repo="github.com/acme/widget")
        assert negative is not None
        assert negative.reason == "stale-reason"


# --- #10: the admitting team is recorded with the mint ----------------------


class TestMintRecordsAdmittingTeam:
    def test_fresh_mint_stores_the_admission_answered_team_slug(self, state_root: Path) -> None:
        """The pre-flight is the one place the admitting team's slug is ever
        in hand; dropping it would leave `spec-kitty routes` nothing to name."""
        gateway = ScriptedGateway(admission={"admitted": True, "team_slug": "demo"})
        stored = resolution._resolve(key=KEY, repo_slug=SLUG, host=HOST, gateway=gateway, kind=KIND_PRESENCE, force=False)
        assert stored is not None
        assert stored.team == "demo"
        assert credentials.load(repo=KEY) == stored

    def test_admission_without_a_team_slug_stores_team_none(self, state_root: Path) -> None:
        gateway = ScriptedGateway(admission={"admitted": True})
        stored = resolution._resolve(key=KEY, repo_slug=SLUG, host=HOST, gateway=gateway, kind=KIND_PRESENCE, force=False)
        assert stored is not None
        assert stored.team is None

    def test_remint_with_missing_admission_team_preserves_existing_team(self, state_root: Path) -> None:
        credentials.store(
            repo=KEY,
            relay_url="http://relay",
            token="old-bearer",
            token_kind=KIND_PRESENCE,
            expires_at=_iso_in(-1),
            host=HOST,
            repo_slug=SLUG,
            team="demo",
        )
        credentials.store_focus_capability(
            repo=KEY,
            capability_credential="focus-jwt",
            expires_at=_iso_in(1200),
        )
        gateway = ScriptedGateway(admission={"admitted": True})

        stored = resolution._resolve(key=KEY, repo_slug=SLUG, host=HOST, gateway=gateway, kind=KIND_PRESENCE, force=False)

        assert stored is not None
        assert stored.team == "demo"
        assert stored.focus_capability_credential == "focus-jwt"
        assert gateway.mint_calls == [{"repo_slug": SLUG, "kind": KIND_PRESENCE, "team_slug": None}]


# ---------------------------------------------------------------------------
# resolve_focus_capability (#186): the second lease a wired client needs
# ---------------------------------------------------------------------------


def _pin_checkout_origin(monkeypatch: pytest.MonkeyPatch, url: str = "https://github.com/acme/widget.git") -> None:
    """Serve the identity half of the public function without git."""
    monkeypatch.setattr(resolution.repo_identity, "origin_url", lambda cwd, deadline=None: url)


class TestResolveFocusCapability:
    def test_cached_unexpired_lease_answers_without_touching_the_network(self, state_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _pin_checkout_origin(monkeypatch)
        credentials.store(
            repo=KEY,
            relay_url="http://relay",
            token="bearer",
            token_kind=KIND_PRESENCE,
            capability_credential="presence-jwt",
            expires_at=_iso_in(3600),
            team="demo",
        )
        credentials.store_focus_capability(repo=KEY, capability_credential="focus-jwt", expires_at=_iso_in(1200))
        gateway = ScriptedGateway()

        jwt = resolution.resolve_focus_capability("/checkout", gateway=gateway)

        assert jwt == "focus-jwt"
        assert gateway.mint_calls == [] and gateway.admission_calls == []

    def test_miss_mints_the_focus_kind_against_the_stored_team(self, state_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _pin_checkout_origin(monkeypatch)
        credentials.store(
            repo=KEY,
            relay_url="http://relay",
            token="bearer",
            token_kind=KIND_PRESENCE,
            expires_at=_iso_in(3600),
            team="demo",
        )
        gateway = ScriptedGateway(
            mint=MintedCredential(
                relay_url="http://relay",
                relay_token="bearer",
                capability_credential="focus-jwt",
                expires_at=_iso_in(1800),
            )
        )

        jwt = resolution.resolve_focus_capability("/checkout", gateway=gateway)

        assert jwt == "focus-jwt"
        assert gateway.mint_calls == [{"repo_slug": SLUG, "kind": resolution.KIND_FOCUS, "team_slug": "demo"}]
        stored = credentials.load(repo=KEY)
        assert stored is not None
        # The merge keeps the main lease intact and adds the focus one.
        assert stored.token == "bearer"
        assert stored.capability_credential is None
        assert stored.focus_capability_credential == "focus-jwt"

    def test_expired_lease_remints(self, state_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _pin_checkout_origin(monkeypatch)
        credentials.store(repo=KEY, relay_url="http://relay", token="bearer", token_kind=KIND_PRESENCE)
        credentials.store_focus_capability(repo=KEY, capability_credential="stale-focus-jwt", expires_at=_iso_in(-60))
        gateway = ScriptedGateway(
            mint=MintedCredential(
                relay_url="http://relay",
                relay_token="bearer",
                capability_credential="fresh-focus-jwt",
                expires_at=_iso_in(1800),
            )
        )

        jwt = resolution.resolve_focus_capability("/checkout", gateway=gateway)

        assert jwt == "fresh-focus-jwt"

    def test_force_skips_a_live_lease(self, state_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _pin_checkout_origin(monkeypatch)
        credentials.store(repo=KEY, relay_url="http://relay", token="bearer", token_kind=KIND_PRESENCE)
        credentials.store_focus_capability(repo=KEY, capability_credential="live-focus-jwt", expires_at=_iso_in(1200))
        gateway = ScriptedGateway()  # scripted default mints capability "jwt"

        jwt = resolution.resolve_focus_capability("/checkout", gateway=gateway, force=True)

        assert len(gateway.mint_calls) == 1
        assert jwt == "jwt"

    def test_denial_returns_none_and_never_writes_a_negative(self, state_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """A focus denial says nothing about admission — caching it under the
        shared key would silence the moment stream for the whole negative TTL."""
        _pin_checkout_origin(monkeypatch)
        credentials.store(repo=KEY, relay_url="http://relay", token="bearer", token_kind=KIND_PRESENCE)
        gateway = ScriptedGateway(mint=CapabilityDenied("denied", status_code=403))

        assert resolution.resolve_focus_capability("/checkout", gateway=gateway) is None

        stored = credentials.load(repo=KEY)
        assert stored is not None  # main lease untouched
        assert credentials.load_negative(repo=KEY) is None

    def test_transient_gateway_failure_returns_none_and_caches_nothing(self, state_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _pin_checkout_origin(monkeypatch)
        credentials.store(repo=KEY, relay_url="http://relay", token="bearer", token_kind=KIND_PRESENCE)
        gateway = ScriptedGateway(mint=GatewayError("timeout"))

        assert resolution.resolve_focus_capability("/checkout", gateway=gateway) is None
        assert credentials.load(repo=KEY) is not None
        stored = credentials.load(repo=KEY)
        assert stored is not None and stored.focus_capability_credential is None

    def test_mint_without_a_capability_credential_is_unusable(self, state_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _pin_checkout_origin(monkeypatch)
        credentials.store(repo=KEY, relay_url="http://relay", token="bearer", token_kind=KIND_PRESENCE)
        gateway = ScriptedGateway(mint=MintedCredential(relay_url="http://relay", relay_token="bearer", capability_credential=None, expires_at=_iso_in(600)))

        assert resolution.resolve_focus_capability("/checkout", gateway=gateway) is None
        stored = credentials.load(repo=KEY)
        assert stored is not None and stored.focus_capability_credential is None

    def test_no_main_credential_means_nothing_to_mint_against(self, state_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _pin_checkout_origin(monkeypatch)
        gateway = ScriptedGateway()

        assert resolution.resolve_focus_capability("/checkout", gateway=gateway) is None
        assert gateway.mint_calls == [] and gateway.admission_calls == []

    def test_local_only_remote_stays_silent(self, state_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _pin_checkout_origin(monkeypatch, url="/srv/git/local.git")
        gateway = ScriptedGateway()

        assert resolution.resolve_focus_capability("/checkout", gateway=gateway) is None
        assert gateway.mint_calls == []


class TestResolveFocusCapabilityScopeRevalidation:
    def test_out_of_scope_entry_is_a_miss_not_a_hit(self, state_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Defense in depth (#129's reading, mirrored from the main
        resolution): an entry whose recorded (host, repo_slug) disagrees with
        the identity it sits under serves neither its main lease nor a mint."""
        _pin_checkout_origin(monkeypatch)
        credentials.store(
            repo=KEY,
            relay_url="http://evil",
            token="bearer",
            token_kind=KIND_PRESENCE,
            expires_at=_iso_in(3600),
            host="github.com",
            repo_slug="evil/widget",  # not the identity this key names
        )
        gateway = ScriptedGateway()

        assert resolution.resolve_focus_capability("/checkout", gateway=gateway) is None
        assert gateway.mint_calls == []
