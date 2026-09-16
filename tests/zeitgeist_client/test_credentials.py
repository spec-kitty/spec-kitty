"""Z1-T1 §3.2 item 7 / §4 N10, N11: local checkout/auth credential storage.

``<runtime_state_root>/zeitgeist-credentials``, TOML, ``filelock``-guarded
(Z1.md decision 3/4 — own file, not shared with tracker/credentials.py; uses
the existing declared-but-unused ``filelock`` dependency,
``pyproject.toml:85``). Stores ``{relay_url, token, token_issued_at,
token_kind}`` keyed by the hosted identity (``host/owner/repo``,
spec-kitty#129/#132), plus the optional FIX-M2-15 ``capability_credential``
field (omitted from the stored TOML entry entirely, not written as an empty
string, whenever a caller does not pass one — see that section below and the
module's own FIX-M2-15 docstring note). Since spec-kitty#137 a bare-name key
— the pre-#132 shape — is refused on every door: writers raise, readers read
"nothing stored", revoke is a no-op, and any write prunes bare-name entries
already on disk.

This is a scoped subset of Z1.md §3.4's full ``checkout``/``--refresh``/
``--revoke`` CLI contract: it covers the storage primitive
(``store``/``load``/``revoke``) N10/N11 exercise, not the network canary-offer
probe (that lives in the not-yet-implemented CLI adapter — see WP01
handoff).
"""

from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest

from specify_cli.zeitgeist_client import credentials

# See tests/zeitgeist_client/test_grammar.py's pytestmark comment.
pytestmark = pytest.mark.fast


@pytest.fixture()
def state_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("SPEC_KITTY_HOME", str(tmp_path / "spec-kitty-home"))
    return tmp_path / "spec-kitty-home"


def _iso_in(seconds: float) -> str:
    """An ISO expiry stamp ``seconds`` from now — the same helper shape the
    resolution tests use, local to this module for the same reason."""
    from kernel.clock import now_utc, timedelta

    return (now_utc() + timedelta(seconds=seconds)).isoformat()


def test_store_then_load_round_trips(state_root: Path):
    credentials.store(
        repo="github.com/acme/spec-kitty",
        relay_url="http://127.0.0.1:9999",
        token="tok-abc",
        token_kind="shared_team",
    )
    loaded = credentials.load(repo="github.com/acme/spec-kitty")
    assert loaded is not None
    assert loaded.relay_url == "http://127.0.0.1:9999"
    assert loaded.token == "tok-abc"
    assert loaded.token_kind == "shared_team"
    assert loaded.token_issued_at  # non-empty ISO timestamp


def test_load_returns_none_when_nothing_stored(state_root: Path):
    assert credentials.load(repo="github.com/acme/spec-kitty") is None


# --- FIX-M2-15: the second, optional capability_credential field -----------


def test_single_credential_store_round_trips_capability_credential_as_none(state_root: Path):
    """Every call site that predates FIX-M2-15 (and every self-hosted,
    single-secret deployment) never passes ``capability_credential`` —
    ``load()`` must report that as ``None``, never as an empty string or a
    KeyError, so every caller's existing "``None`` means use ``token`` for
    both gates" fallback keeps working."""
    credentials.store(repo="github.com/acme/spec-kitty", relay_url="http://a", token="tok-a", token_kind="shared_team")
    loaded = credentials.load(repo="github.com/acme/spec-kitty")
    assert loaded is not None
    assert loaded.capability_credential is None


def test_two_credential_store_round_trips_both_values_independently(state_root: Path):
    credentials.store(
        repo="github.com/acme/spec-kitty",
        relay_url="http://a",
        token="team-shared-token",
        token_kind="shared_team",
        capability_credential="actor-capability-jwt",
    )
    loaded = credentials.load(repo="github.com/acme/spec-kitty")
    assert loaded is not None
    assert loaded.token == "team-shared-token"
    assert loaded.capability_credential == "actor-capability-jwt"


def test_empty_capability_credential_is_rejected_when_provided(state_root: Path):
    with pytest.raises(ValueError):
        credentials.store(
            repo="github.com/acme/spec-kitty",
            relay_url="http://a",
            token="tok-a",
            token_kind="shared_team",
            capability_credential="",
        )
    # Never left the store corrupted/partially written.
    assert credentials.load(repo="github.com/acme/spec-kitty") is None


def test_stored_toml_omits_capability_credential_key_entirely_when_unset(state_root: Path):
    """Backward-compat proof, not just a `None` read-back: a config file
    written by this fix looks byte-for-byte like one written before it,
    for a single-credential checkout -- no `capability_credential = ""`
    key ever lands in the TOML entry, which would otherwise round-trip as
    an empty string rather than `None` (and, since `store()` itself
    rejects an explicit empty string, would signal the entry was written
    by something that bypassed this module's own validation)."""
    credentials.store(repo="github.com/acme/spec-kitty", relay_url="http://a", token="tok-a", token_kind="shared_team")
    import tomllib

    with credentials.credentials_path().open("rb") as fh:
        raw = tomllib.load(fh)
    assert "capability_credential" not in raw["github.com/acme/spec-kitty"]


def test_two_repos_hold_independent_tokens(state_root: Path):
    credentials.store(repo="github.com/acme/spec-kitty", relay_url="http://a", token="tok-a", token_kind="shared_team")
    credentials.store(repo="github.com/acme/zeitgeist", relay_url="http://b", token="tok-b", token_kind="shared_team")
    assert credentials.load(repo="github.com/acme/spec-kitty").token == "tok-a"  # type: ignore[union-attr]
    assert credentials.load(repo="github.com/acme/zeitgeist").token == "tok-b"  # type: ignore[union-attr]


def test_credentials_file_lives_under_runtime_state_root_not_tracker_file(state_root: Path):
    credentials.store(repo="github.com/acme/spec-kitty", relay_url="http://a", token="tok-a", token_kind="shared_team")
    path = credentials.credentials_path()
    assert path.name == "zeitgeist-credentials"
    assert path.parent.parent.parent == state_root
    assert path.parent.parent.name == "zeitgeist-sessions"
    assert path != state_root / "credentials"  # tracker's own file, never shared (decision 3)


def test_n10_revoke_deletes_local_token_even_when_relay_unreachable(state_root: Path):
    credentials.store(repo="github.com/acme/spec-kitty", relay_url="http://127.0.0.1:1", token="tok-a", token_kind="shared_team")
    # revoke() here is the local-wipe half only (§3.2 item 7): "never fails to
    # wipe locally even if the [server] offer drops" — the network half lives
    # in the not-yet-implemented CLI (`checkout --revoke`).
    credentials.revoke(repo="github.com/acme/spec-kitty")
    assert credentials.load(repo="github.com/acme/spec-kitty") is None


def test_n11_a_failed_refresh_never_deletes_the_previously_stored_token(state_root: Path):
    credentials.store(repo="github.com/acme/spec-kitty", relay_url="http://a", token="tok-a", token_kind="shared_team")
    # store() itself never deletes on its own failure path; a caller doing a
    # refresh that fails its network probe (401) must simply not call
    # store()/revoke() again — asserting the storage layer has no implicit
    # "clear on any write attempt" behaviour.
    with pytest.raises(ValueError):
        credentials.store(repo="github.com/acme/spec-kitty", relay_url="http://a", token="", token_kind="shared_team")
    still_there = credentials.load(repo="github.com/acme/spec-kitty")
    assert still_there is not None
    assert still_there.token == "tok-a"


# --- E3 resolution: the optional expires_at stamp ---------------------------


def test_store_without_expiry_round_trips_expires_at_as_none(state_root: Path):
    """Every entry written before E3 (and every manual checkout) has no
    expiry stamp; load() reports None, never KeyError or ""."""
    credentials.store(repo="github.com/acme/spec-kitty", relay_url="http://a", token="tok-a", token_kind="shared_team")
    loaded = credentials.load(repo="github.com/acme/spec-kitty")
    assert loaded is not None
    assert loaded.expires_at is None


def test_expires_at_round_trips_verbatim(state_root: Path):
    """The stamp is stored and read back byte-for-byte -- interpreting it
    is the caller's policy, never the store's."""
    credentials.store(
        repo="github.com/acme/spec-kitty",
        relay_url="http://a",
        token="tok-a",
        token_kind="presence",
        expires_at="2026-08-25T12:00:00+00:00",
    )
    loaded = credentials.load(repo="github.com/acme/spec-kitty")
    assert loaded is not None
    assert loaded.expires_at == "2026-08-25T12:00:00+00:00"


def test_empty_expires_at_is_rejected(state_root: Path):
    with pytest.raises(ValueError):
        credentials.store(repo="github.com/acme/spec-kitty", relay_url="http://a", token="tok-a", token_kind="presence", expires_at="")


# --- squad finding on #123: the optional host/repo_slug scope fields -------


def test_store_without_scope_round_trips_host_and_repo_slug_as_none(state_root: Path):
    """Every entry written before this fix (and every manual checkout) has
    no recorded scope; load() reports None for both, never KeyError."""
    credentials.store(repo="github.com/acme/spec-kitty", relay_url="http://a", token="tok-a", token_kind="shared_team")
    loaded = credentials.load(repo="github.com/acme/spec-kitty")
    assert loaded is not None
    assert loaded.host is None
    assert loaded.repo_slug is None


def test_host_and_repo_slug_round_trip_verbatim(state_root: Path):
    credentials.store(
        repo="github.com/acme/spec-kitty",
        relay_url="http://a",
        token="tok-a",
        token_kind="shared_team",
        host="github.int.exe.xyz",
        repo_slug="Priivacy-ai/spec-kitty",
    )
    loaded = credentials.load(repo="github.com/acme/spec-kitty")
    assert loaded is not None
    assert loaded.host == "github.int.exe.xyz"
    assert loaded.repo_slug == "Priivacy-ai/spec-kitty"


def test_empty_host_is_rejected_when_provided(state_root: Path):
    with pytest.raises(ValueError):
        credentials.store(repo="github.com/acme/spec-kitty", relay_url="http://a", token="tok-a", token_kind="shared_team", host="")


def test_empty_repo_slug_is_rejected_when_provided(state_root: Path):
    with pytest.raises(ValueError):
        credentials.store(repo="github.com/acme/spec-kitty", relay_url="http://a", token="tok-a", token_kind="shared_team", repo_slug="")


def test_stored_toml_omits_host_and_repo_slug_keys_entirely_when_unset(state_root: Path):
    """Same backward-compat proof as capability_credential/expires_at: a
    config written without a scope looks byte-for-byte like one written
    before this fix -- no `host = ""` / `repo_slug = ""` key ever lands."""
    credentials.store(repo="github.com/acme/spec-kitty", relay_url="http://a", token="tok-a", token_kind="shared_team")
    import tomllib

    with credentials.credentials_path().open("rb") as fh:
        raw = tomllib.load(fh)
    assert "host" not in raw["github.com/acme/spec-kitty"]
    assert "repo_slug" not in raw["github.com/acme/spec-kitty"]


# --- E3 resolution: negative answers ---------------------------------------


def test_negative_entry_is_stored_and_read_back(state_root: Path):
    credentials.store_negative(repo="github.com/acme/spec-kitty", reason="no_match", expires_at="2026-08-25T13:00:00+00:00")
    negative = credentials.load_negative(repo="github.com/acme/spec-kitty")
    assert negative is not None
    assert negative.reason == "no_match"
    assert negative.expires_at == "2026-08-25T13:00:00+00:00"
    assert negative.stored_at  # non-empty ISO stamp


def test_negative_entry_reads_back_as_none_through_load(state_root: Path):
    """A negative answer must look like plain "not checked out" to every
    existing load() caller -- no relay_url/token keys, no special case."""
    credentials.store(repo="github.com/acme/spec-kitty", relay_url="http://a", token="tok-a", token_kind="shared_team")
    credentials.revoke(repo="github.com/acme/spec-kitty")
    credentials.store_negative(repo="github.com/acme/spec-kitty", reason="no_match")
    assert credentials.load(repo="github.com/acme/spec-kitty") is None
    other = credentials.load(repo="gitlab.com/other/unrelated-repo")
    assert other is None


def test_load_negative_returns_none_for_positive_entry_or_missing_repo(state_root: Path):
    credentials.store(repo="github.com/acme/spec-kitty", relay_url="http://a", token="tok-a", token_kind="shared_team")
    assert credentials.load_negative(repo="github.com/acme/spec-kitty") is None
    assert credentials.load_negative(repo="gitlab.com/other/never-stored") is None


def test_storing_negative_replaces_a_positive_credential(state_root: Path):
    """A mint denial after a stored credential means that credential can no
    longer be valid -- the negative answer replaces it rather than sitting
    beside it."""
    credentials.store(repo="github.com/acme/spec-kitty", relay_url="http://a", token="tok-a", token_kind="presence")
    credentials.store_negative(repo="github.com/acme/spec-kitty", reason="capability_denied")
    assert credentials.load(repo="github.com/acme/spec-kitty") is None
    negative = credentials.load_negative(repo="github.com/acme/spec-kitty")
    assert negative is not None
    assert negative.reason == "capability_denied"


def test_storing_positive_replaces_a_negative_answer(state_root: Path):
    credentials.store_negative(repo="github.com/acme/spec-kitty", reason="no_match")
    credentials.store(repo="github.com/acme/spec-kitty", relay_url="http://a", token="tok-a", token_kind="presence")
    assert credentials.load(repo="github.com/acme/spec-kitty") is not None
    assert credentials.load_negative(repo="github.com/acme/spec-kitty") is None


def test_negative_reason_defaults_to_empty_when_omitted(state_root: Path):
    credentials.store_negative(repo="github.com/acme/spec-kitty")
    negative = credentials.load_negative(repo="github.com/acme/spec-kitty")
    assert negative is not None
    assert negative.reason == ""


# --- E3 resolution: the store is owner-only, whatever the umask -------------


def test_store_is_owner_only_file_and_directory(state_root: Path):
    """[controller-qa] MAJOR regression: E3 makes this store auto-populated
    on every status transition with relay bearers and capability JWTs — it
    must land 0o600 in a 0o700 directory even under a permissive umask,
    not whatever ``open()`` inherits (measured 0o644/0o755 before)."""
    credentials.store(repo="github.com/acme/spec-kitty", relay_url="http://a", token="tok-a", token_kind="shared_team")
    if not hasattr(os, "getuid"):  # permission bits are a POSIX assertion
        return
    path = credentials.credentials_path()
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700


def test_owner_only_mode_holds_across_every_write_path(state_root: Path):
    """store_negative() and revoke() rewrite the file through the same
    atomic replace; none of them may loosen the mode the first write set."""
    credentials.store(repo="github.com/acme/spec-kitty", relay_url="http://a", token="tok-a", token_kind="shared_team")
    credentials.store_negative(repo="gitlab.com/other/repo", reason="no_match")
    credentials.store(
        repo="github.com/acme/spec-kitty",
        relay_url="http://a",
        token="tok-a2",
        token_kind="presence",
        expires_at="2026-08-25T12:00:00+00:00",
    )
    credentials.revoke(repo="gitlab.com/other/repo")
    if not hasattr(os, "getuid"):
        return
    path = credentials.credentials_path()
    assert path.exists()
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_a_loose_pre_e3_file_is_tightened_on_read(state_root: Path):
    """[squad] Priivacy-ai/spec-kitty#37 MINOR: a store/dir left loose by a
    pre-E3 write (the old ``tmp_path.open("wb")`` path, no chmod, landing at
    the ambient umask) must not stay group/other-readable until the next
    write — ``load()`` alone must tighten it, since a manual checkout may
    never call ``store()`` again."""
    path = credentials.credentials_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.parent.chmod(0o755)
    path.write_text(
        '["github.com/acme/spec-kitty"]\nrelay_url = "http://a"\ntoken = "tok-a"\ntoken_issued_at = "2026-01-01T00:00:00+00:00"\ntoken_kind = "shared_team"\n'
    )
    path.chmod(0o644)
    assert credentials.load(repo="github.com/acme/spec-kitty") is not None
    if not hasattr(os, "getuid"):
        return
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700


def test_a_loose_pre_e3_directory_is_tightened_on_read_with_nothing_stored(state_root: Path):
    """Even a read that finds nothing stored (no file at all yet) must
    tighten a loose parent directory left behind by some other pre-E3
    artifact — the directory alone can leak which repos have ever been
    touched, and :func:`_locked` is the one door every read goes through."""
    path = credentials.credentials_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.parent.chmod(0o755)
    assert credentials.load(repo="github.com/acme/spec-kitty") is None
    if not hasattr(os, "getuid"):
        return
    assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700


# --- spec-kitty#137: bare pre-#132 name keys are refused on every door ------


LEGACY_NAME = "widget"
HOSTED_KEY = "github.com/acme/widget"


def test_store_rejects_a_bare_pre_132_name_key(state_root: Path):
    """#132 keyed every writer by resolution.store_key's host/owner/repo and
    deliberately did not migrate the old entries; a writer trying to put a
    fresh bearer back under a bare NAME is a bug — fail loudly, not
    silently under a key nothing looks up."""
    with pytest.raises(ValueError, match="host/owner/repo"):
        credentials.store(repo=LEGACY_NAME, relay_url="http://a", token="tok", token_kind="shared_team")


def test_store_negative_rejects_a_bare_pre_132_name_key(state_root: Path):
    with pytest.raises(ValueError, match="host/owner/repo"):
        credentials.store_negative(repo=LEGACY_NAME, reason="no_match")


def test_load_reads_a_bare_name_as_nothing_stored(state_root: Path):
    """The one live-shaped hazard a pre-#132 file still holds is its old
    bare-name entry: a live bearer nothing prunes or expiry-checks. Reading
    it back as "not checked out" means no lookup can ever be served from
    it, whatever key a caller passes."""
    path = credentials.credentials_path()
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.write_text(
        f'["{LEGACY_NAME}"]\nrelay_url = "http://stale"\ntoken = "stale-bearer"\ntoken_issued_at = "2026-01-01T00:00:00+00:00"\ntoken_kind = "shared_team"\n'
    )
    assert credentials.load(repo=LEGACY_NAME) is None
    assert credentials.load_negative(repo=LEGACY_NAME) is None


def test_revoke_of_a_bare_name_is_a_noop_never_an_error(state_root: Path):
    """N10: revoke must never fail to wipe. Under a bare name there is
    nothing servable left to wipe, so the no-op already leaves the store in
    exactly the state N10 demands ("not checked out" thereafter). ``load()``
    would read a bare name as ``None`` either way (deleted or merely
    unservable), so the real proof that this is a no-op — not a delete —
    is the raw TOML: the legacy entry must still be on disk afterwards."""
    credentials.revoke(repo=LEGACY_NAME)  # no entry at all
    assert credentials.load(repo=LEGACY_NAME) is None

    path = credentials.credentials_path()
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.write_text(f'["{LEGACY_NAME}"]\ntoken_kind = "not_admitted"\n')
    credentials.revoke(repo=LEGACY_NAME)  # legacy entry present on disk
    assert credentials.load(repo=LEGACY_NAME) is None

    import tomllib

    raw = tomllib.loads(path.read_text())
    assert LEGACY_NAME in raw  # untouched: revoke() is a no-op, not a delete


def test_any_successful_write_prunes_bare_name_entries_on_disk(state_root: Path):
    """#137's "never pruned" half: the stale pre-#132 bearer must not sit in
    the file forever just because nobody reads it. Every legitimate write
    (here: a mint landing under a proper host/owner/repo key) sweeps the
    abandoned shape out of the store."""
    path = credentials.credentials_path()
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.write_text(
        f'["{LEGACY_NAME}"]\n'
        'relay_url = "http://stale"\n'
        'token = "stale-bearer"\n'
        'token_issued_at = "2026-01-01T00:00:00+00:00"\n'
        'token_kind = "shared_team"\n\n'
        f'["{HOSTED_KEY}"]\n'
        'relay_url = "http://live"\n'
        'token = "live-bearer"\n'
        'token_issued_at = "2026-06-01T00:00:00+00:00"\n'
        'token_kind = "presence"\n'
    )

    credentials.store(repo="gitlab.com/acme/other", relay_url="http://a", token="tok", token_kind="shared_team")

    import tomllib

    raw = tomllib.loads(path.read_text())
    assert LEGACY_NAME not in raw
    assert raw[HOSTED_KEY]["token"] == "live-bearer"  # untouched by the sweep
    assert credentials.load(repo=HOSTED_KEY).token == "live-bearer"  # type: ignore[union-attr]


# --- #10: the admitting team rides the credential ---------------------------


def test_store_without_team_round_trips_team_as_none(state_root: Path):
    """Entries written before #10 (and every manual checkout) have no
    recorded team; load() reports None, never KeyError."""
    credentials.store(repo="github.com/acme/spec-kitty", relay_url="http://a", token="tok-a", token_kind="shared_team")
    loaded = credentials.load(repo="github.com/acme/spec-kitty")
    assert loaded is not None
    assert loaded.team is None


def test_team_round_trips_verbatim(state_root: Path):
    credentials.store(repo="github.com/acme/spec-kitty", relay_url="http://a", token="tok-a", token_kind="shared_team", team="demo")
    loaded = credentials.load(repo="github.com/acme/spec-kitty")
    assert loaded is not None
    assert loaded.team == "demo"


def test_empty_team_is_rejected_when_provided(state_root: Path):
    with pytest.raises(ValueError):
        credentials.store(repo="github.com/acme/spec-kitty", relay_url="http://a", token="tok-a", token_kind="shared_team", team="")


def test_stored_toml_omits_team_key_entirely_when_unset(state_root: Path):
    """Same backward-compat proof as every optional aspect before it."""
    credentials.store(repo="github.com/acme/spec-kitty", relay_url="http://a", token="tok-a", token_kind="shared_team")
    import tomllib

    with credentials.credentials_path().open("rb") as fh:
        raw = tomllib.load(fh)
    assert "team" not in raw["github.com/acme/spec-kitty"]


# --- #186: the focus-kind lease rides the same entry ------------------------


def _seed_main_credential(repo: str = "github.com/acme/widget") -> None:
    credentials.store(
        repo=repo,
        relay_url="http://relay",
        token="bearer",
        token_kind="presence",
        capability_credential="presence-jwt",
        expires_at=_iso_in(3600),
        host="github.com",
        repo_slug="acme/widget",
        team="demo",
    )


def test_focus_capability_merges_into_the_existing_entry(state_root: Path):
    """The focus lease is minted later than (and independently of) the main
    credential; storing it must leave every main-field value verbatim."""
    _seed_main_credential()
    focus_expires = _iso_in(1200)

    credentials.store_focus_capability(
        repo="github.com/acme/widget",
        capability_credential="focus-jwt",
        expires_at=focus_expires,
    )

    loaded = credentials.load(repo="github.com/acme/widget")
    assert loaded is not None
    assert loaded.relay_url == "http://relay"
    assert loaded.token == "bearer"
    assert loaded.token_kind == "presence"
    assert loaded.capability_credential == "presence-jwt"
    assert loaded.team == "demo"
    assert loaded.focus_capability_credential == "focus-jwt"
    assert loaded.focus_expires_at == focus_expires


def test_focus_capability_without_expiry_leaves_no_stale_stamp(state_root: Path):
    _seed_main_credential()
    credentials.store_focus_capability(repo="github.com/acme/widget", capability_credential="focus-jwt", expires_at=_iso_in(600))
    credentials.store_focus_capability(repo="github.com/acme/widget", capability_credential="focus-jwt-2")

    loaded = credentials.load(repo="github.com/acme/widget")
    assert loaded is not None
    assert loaded.focus_capability_credential == "focus-jwt-2"
    assert loaded.focus_expires_at is None


def test_reminting_the_main_credential_preserves_a_live_focus_lease(state_root: Path):
    """The two leases expire independently; a presence re-mint must not
    silently drop a still-valid focus lease."""
    _seed_main_credential()
    credentials.store_focus_capability(repo="github.com/acme/widget", capability_credential="focus-jwt", expires_at=_iso_in(1200))

    credentials.store(
        repo="github.com/acme/widget",
        relay_url="http://relay",
        token="bearer-2",
        token_kind="presence",
        capability_credential="presence-jwt-2",
        expires_at=_iso_in(3600),
        host="github.com",
        repo_slug="acme/widget",
        team="demo",
    )

    loaded = credentials.load(repo="github.com/acme/widget")
    assert loaded is not None
    assert loaded.capability_credential == "presence-jwt-2"
    assert loaded.focus_capability_credential == "focus-jwt"


def test_same_scope_remint_without_team_preserves_the_previous_team(state_root: Path):
    """A malformed admission response has no new team signal; it must not
    erase the admitting team already proven for this relay/repo scope."""
    _seed_main_credential()
    credentials.store_focus_capability(
        repo="github.com/acme/widget",
        capability_credential="focus-jwt",
        expires_at=_iso_in(1200),
    )

    credentials.store(
        repo="github.com/acme/widget",
        relay_url="http://relay",
        token="bearer-2",
        token_kind="presence",
        capability_credential="presence-jwt-2",
        expires_at=_iso_in(3600),
        host="github.com",
        repo_slug="acme/widget",
        team=None,
    )

    loaded = credentials.load(repo="github.com/acme/widget")
    assert loaded is not None
    assert loaded.team == "demo"
    assert loaded.focus_capability_credential == "focus-jwt"


def test_reminting_with_a_new_relay_url_drops_the_stale_focus_lease(state_root: Path):
    """#197: a focus lease minted for the old relay must not be served once
    the main credential's rewrite points at a different relay -- serving it
    would get every focus frame rejected until the stale lease expires."""
    _seed_main_credential()
    credentials.store_focus_capability(repo="github.com/acme/widget", capability_credential="focus-jwt", expires_at=_iso_in(1200))

    credentials.store(
        repo="github.com/acme/widget",
        relay_url="http://relay-2",
        token="bearer-2",
        token_kind="presence",
        capability_credential="presence-jwt-2",
        expires_at=_iso_in(3600),
        host="github.com",
        repo_slug="acme/widget",
        team="demo",
    )

    loaded = credentials.load(repo="github.com/acme/widget")
    assert loaded is not None
    assert loaded.relay_url == "http://relay-2"
    assert loaded.focus_capability_credential is None
    assert loaded.focus_expires_at is None


def test_reminting_under_a_new_team_drops_the_stale_focus_lease(state_root: Path):
    """#197: the focus lease is scoped to the admitting team as much as the
    relay -- a re-admission under a different team must drop it too."""
    _seed_main_credential()
    credentials.store_focus_capability(repo="github.com/acme/widget", capability_credential="focus-jwt")

    credentials.store(
        repo="github.com/acme/widget",
        relay_url="http://relay",
        token="bearer-2",
        token_kind="presence",
        capability_credential="presence-jwt-2",
        host="github.com",
        repo_slug="acme/widget",
        team="other-team",
    )

    loaded = credentials.load(repo="github.com/acme/widget")
    assert loaded is not None
    assert loaded.focus_capability_credential is None


@pytest.mark.parametrize(
    ("host", "repo_slug"),
    [
        ("gitlab.com", "acme/widget"),
        ("github.com", "acme/other-widget"),
    ],
)
def test_same_team_remint_in_new_repo_scope_drops_the_stale_focus_lease(
    state_root: Path,
    host: str,
    repo_slug: str,
):
    _seed_main_credential()
    credentials.store_focus_capability(repo="github.com/acme/widget", capability_credential="focus-jwt")

    credentials.store(
        repo="github.com/acme/widget",
        relay_url="http://relay",
        token="bearer-2",
        token_kind="presence",
        capability_credential="presence-jwt-2",
        host=host,
        repo_slug=repo_slug,
        team="demo",
    )

    loaded = credentials.load(repo="github.com/acme/widget")
    assert loaded is not None
    assert loaded.team == "demo"
    assert loaded.focus_capability_credential is None


@pytest.mark.parametrize(
    ("relay_url", "host", "repo_slug"),
    [
        ("http://other-relay", "github.com", "acme/widget"),
        ("http://relay", "gitlab.com", "acme/widget"),
        ("http://relay", "github.com", "acme/other-widget"),
    ],
)
def test_different_scope_remint_without_team_does_not_preserve_previous_team(
    state_root: Path,
    relay_url: str,
    host: str,
    repo_slug: str,
):
    _seed_main_credential()
    credentials.store_focus_capability(repo="github.com/acme/widget", capability_credential="focus-jwt")

    credentials.store(
        repo="github.com/acme/widget",
        relay_url=relay_url,
        token="bearer-2",
        token_kind="presence",
        capability_credential="presence-jwt-2",
        expires_at=_iso_in(3600),
        host=host,
        repo_slug=repo_slug,
        team=None,
    )

    loaded = credentials.load(repo="github.com/acme/widget")
    assert loaded is not None
    assert loaded.team is None
    assert loaded.focus_capability_credential is None


def test_store_negative_drops_the_focus_lease_with_the_rest(state_root: Path):
    """A not-admitted answer means no relay at all — keeping a focus lease
    against it would be a live secret pointing nowhere."""
    _seed_main_credential()
    credentials.store_focus_capability(repo="github.com/acme/widget", capability_credential="focus-jwt")

    credentials.store_negative(repo="github.com/acme/widget", reason="no_match", expires_at=_iso_in(300))

    assert credentials.load(repo="github.com/acme/widget") is None


def test_focus_capability_requires_an_existing_positive_entry(state_root: Path):
    with pytest.raises(ValueError, match="resolve_credentials first"):
        credentials.store_focus_capability(repo="github.com/acme/nowhere", capability_credential="focus-jwt")


def test_empty_focus_capability_is_rejected(state_root: Path):
    _seed_main_credential()
    with pytest.raises(ValueError):
        credentials.store_focus_capability(repo="github.com/acme/widget", capability_credential="")


def test_stored_toml_omits_focus_keys_entirely_when_unset(state_root: Path):
    """Same backward-compat proof as every optional field before this one:
    entries written earlier round-trip byte-compatibly."""
    import tomllib

    _seed_main_credential()

    with credentials.credentials_path().open("rb") as fh:
        raw = tomllib.load(fh)
    entry = raw["github.com/acme/widget"]
    assert "focus_capability_credential" not in entry
    assert "focus_expires_at" not in entry
