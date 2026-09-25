"""Coverage for the live-work typed-codec repository-id derivation (#4990).

Adopting ``spec-kitty-events>=10.4.0`` activates the typed ``WorkObservation``
codec, whose ``RepositoryIdentity.repository_id`` must match
``^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$`` (no slashes) — distinct from the
``owner/name`` ``display_slug``. The CLI holds only the slug, so
``_conforming_repository_id`` derives a deterministic, pattern-conforming id
from it (interim pending the server-vetted id, saas#1814).
"""

from __future__ import annotations

import re

import pytest

from specify_cli.live_work.codec import _conforming_repository_id

pytestmark = pytest.mark.fast

#: The shared contract's repository_id pattern (spec_kitty_events 10.x).
_REPO_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


@pytest.mark.parametrize(
    "slug",
    [
        "spec-kitty/spec-kitty-events",
        "owner/name",
        "OWNER/Repo.Name_2",
        "a" * 200,  # over-long: must truncate to <=64
        "團隊/專案",  # non-ASCII: sanitized to conforming ASCII-ish token
        "/leading-slash",
        "._-only-punct-start",
        "x",
    ],
)
def test_derived_repository_id_conforms_to_contract_pattern(slug: str) -> None:
    derived = _conforming_repository_id(slug)
    assert _REPO_ID.match(derived), f"{derived!r} from {slug!r} violates repository_id pattern"
    assert 1 <= len(derived) <= 64


def test_derivation_is_deterministic() -> None:
    slug = "spec-kitty/spec-kitty-events"
    assert _conforming_repository_id(slug) == _conforming_repository_id(slug)


def test_slug_slashes_become_hyphens_and_display_form_is_recoverable() -> None:
    # The owner/name is preserved in spirit (slashes -> hyphens), so the id
    # stays human-recognizable while conforming; display_slug carries the
    # true owner/name unchanged at the call site.
    assert _conforming_repository_id("spec-kitty/spec-kitty-events") == "spec-kitty-spec-kitty-events"


def test_all_disallowed_start_falls_back() -> None:
    # A slug that sanitizes to an empty / punctuation-only token still yields
    # a valid, alnum-leading id (never an empty or pattern-violating value).
    assert _REPO_ID.match(_conforming_repository_id("///"))
    assert _REPO_ID.match(_conforming_repository_id("...."))
