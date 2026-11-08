"""Lane-specific environment helpers.

WP01/T006 (FR-006): Two parallel SaaS / Django lanes must not share a single
test database. The fix is to derive a lane-suffixed test database identifier
from the mission slug and lane id, and surface it via an environment variable
that the per-lane test invocation reads.

The contract is intentionally small and decoupled:

* ``lane_test_db_name(mission_slug, lane_id)`` returns the DB name string.
* ``lane_test_env(mission_slug, lane_id)`` returns the env var mapping that
  test runners should merge into their environment.

Downstream callers (test runners, Django settings modules, docker-compose
overlays) read ``SPEC_KITTY_TEST_DB_NAME`` from the process environment.

Lane id is normalized to ASCII-safe form to keep it valid as a database name
across PostgreSQL, MySQL, and SQLite filenames.
"""

from __future__ import annotations

import hashlib
import re
from typing import Final

# The single canonical env var. Code outside this module that wants a
# per-lane DB name should read from os.environ[SPEC_KITTY_TEST_DB_NAME_ENV].
SPEC_KITTY_TEST_DB_NAME_ENV: Final[str] = "SPEC_KITTY_TEST_DB_NAME"

# Conservative pattern: alphanumerics + underscore + dash. Database identifier
# rules vary; this is the intersection that works on Postgres, MySQL, and as
# a SQLite filename component.
_DB_SAFE_RE: Final[re.Pattern[str]] = re.compile(r"\W+", flags=re.ASCII)

# PostgreSQL truncates identifiers to 63 bytes (NAMEDATALEN - 1); MySQL caps
# at 64. The intersection that keeps a distinct name distinct at the engine
# boundary is 63 bytes (#3122).
_DB_NAME_MAX_BYTES: Final[int] = 63
_DIGEST_HEX_CHARS: Final[int] = 8


def _slugify(value: str) -> str:
    """Reduce *value* to ``[A-Za-z0-9_]`` runs, collapsing other chars to ``_``."""
    if not value:
        return ""
    return _DB_SAFE_RE.sub("_", value).strip("_")


def _cap_db_name(name: str) -> str:
    """Cap *name* at :data:`_DB_NAME_MAX_BYTES` without losing distinctness.

    An over-long composed name is truncated to the longest prefix that leaves
    room for ``_`` plus a stable 8-hex-char digest of the full name (#3122),
    so two distinct (mission, lane) pairs whose names only differ past the
    window still produce different capped names. The input is ASCII-safe by
    construction (both segments are slugified), so byte length == char count.
    """
    if len(name) <= _DB_NAME_MAX_BYTES:
        return name
    digest = hashlib.sha1(name.encode(), usedforsecurity=False).hexdigest()[:_DIGEST_HEX_CHARS]
    keep = _DB_NAME_MAX_BYTES - _DIGEST_HEX_CHARS - 1  # - 1 for the ``_``
    return f"{name[:keep]}_{digest}"


def lane_test_db_name(mission_slug: str, lane_id: str) -> str:
    """Compute the test database name for a (mission_slug, lane_id) pair.

    Format: ``test_<safe-mission>_<safe-lane>``. Both segments are slugified to
    ``[A-Za-z0-9_]`` runs. The ``test_`` prefix matches Django's convention
    so existing Django settings modules can pick this up without further
    transformation. The composed name is capped at 63 bytes with a stable
    digest suffix when it would exceed that (PostgreSQL's identifier limit,
    #3122), so distinct pairs stay distinct at the engine boundary.

    Examples:
        >>> lane_test_db_name("083-my-feature", "lane-a")
        'test_083_my_feature_lane_a'
        >>> lane_test_db_name("flag.suite", "lane-planning")
        'test_flag_suite_lane_planning'

    Raises:
        ValueError: when ``mission_slug`` or ``lane_id`` is empty after
            slugification.
    """
    safe_mission = _slugify(mission_slug)
    safe_lane = _slugify(lane_id)
    if not safe_mission:
        raise ValueError(
            f"mission_slug={mission_slug!r} produced an empty slug after sanitization"
        )
    if not safe_lane:
        raise ValueError(
            f"lane_id={lane_id!r} produced an empty slug after sanitization"
        )
    return _cap_db_name(f"test_{safe_mission}_{safe_lane}")


def lane_test_env(mission_slug: str, lane_id: str) -> dict[str, str]:
    """Return the env-var mapping a per-lane test runner should merge in.

    Currently exposes a single key, ``SPEC_KITTY_TEST_DB_NAME``. The mapping
    shape is stable so additional lane-scoped env vars can be added in the
    future without breaking callers that ``env.update(lane_test_env(...))``.

    Example:
        >>> env = lane_test_env("083-my-feature", "lane-a")
        >>> env["SPEC_KITTY_TEST_DB_NAME"]
        'test_083_my_feature_lane_a'
    """
    return {SPEC_KITTY_TEST_DB_NAME_ENV: lane_test_db_name(mission_slug, lane_id)}
