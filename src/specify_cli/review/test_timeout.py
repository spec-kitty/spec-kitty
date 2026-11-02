"""One project-owned execution budget for baseline and candidate review tests."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

DEFAULT_TEST_TIMEOUT_SECONDS = 300
#: Budget for a run that executes the WHOLE declared review command (#6865).
#:
#: The 300-second default above was priced for a bounded, scoped run. A
#: repository whose declared command runs in full (the production
#: ``DeclaredCommandScopeSource`` narrows nothing per file) is not that shape, so
#: the scoped default under-bounds it and the transition is refused at the
#: timeout. Evidence for this number: this repository's ``make test-fast``
#: measured 215.31 s of pytest on a 40-core host with other suites running
#: (2026-11-02), and its CI bounds a whole per-PR lane at 20 minutes
#: (``.github/workflows/ci-aggregate.yml``). A project that declares
#: ``review.test_timeout_seconds`` always gets its own value instead.
WHOLE_COMMAND_TEST_TIMEOUT_SECONDS = 1_200
MAX_TEST_TIMEOUT_SECONDS = 86_400


class InvalidReviewTestTimeout(ValueError):
    """A declared review budget cannot safely bound a subprocess run."""


def resolve_review_test_timeout(repo_root: Path, override: int | None = None, *, whole_command: bool = False) -> int:
    """Read a positive, whole-second per-run budget, retaining explicit API overrides.

    The one-day ceiling bounds platform wait conversions and accidental oversized
    declarations. Invalid declarations refuse execution rather than becoming an
    unverified passing gate. Resolve against the command's configuration
    authority, not a detached baseline.

    ``whole_command`` selects the *default* only, and only when the project
    declares neither an API override nor ``review.test_timeout_seconds``: a run
    that executes the whole declared review command is bounded by
    :data:`WHOLE_COMMAND_TEST_TIMEOUT_SECONDS`, a bounded target list by
    :data:`DEFAULT_TEST_TIMEOUT_SECONDS` (#6865). A declared value always wins,
    so the shape default can never mask a project's own budget — or an invalid
    declaration, which still raises.
    """
    default_seconds = WHOLE_COMMAND_TEST_TIMEOUT_SECONDS if whole_command else DEFAULT_TEST_TIMEOUT_SECONDS
    value: object = override
    if override is None:
        path = repo_root / ".kittify" / "config.yaml"
        try:
            config = YAML(typ="safe").load(path) if path.exists() else None
        except (YAMLError, OSError, UnicodeDecodeError) as exc:
            raise InvalidReviewTestTimeout(f"Cannot read review.test_timeout_seconds from {path}: {exc}") from exc
        if config is not None and not isinstance(config, Mapping):
            raise InvalidReviewTestTimeout("Review configuration must be a mapping")
        review = (config or {}).get("review")
        if review is not None and not isinstance(review, Mapping):
            raise InvalidReviewTestTimeout("review must be a mapping")
        value = (review or {}).get("test_timeout_seconds", default_seconds)
    return validate_review_test_timeout(value)


def validate_review_test_timeout(value: object) -> int:
    """Validate the same budget domain for declarations and persisted receipts."""
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= MAX_TEST_TIMEOUT_SECONDS:
        raise InvalidReviewTestTimeout(f"review.test_timeout_seconds must be an integer from 1 to {MAX_TEST_TIMEOUT_SECONDS}")
    return value
