"""ATDD anchor for the v2 ``pack.yaml`` descriptor schema (WP01, T001).

Pins the user-observable schema behaviour of :class:`PackDescriptor` after the
``pack_level`` mission (#6048):

* ``pack_level`` is a **required** field whose allowed values are exactly the
  :data:`kernel.pack_tiers.PackTier` tokens (``built-in`` / ``org`` /
  ``project``) — omitting it, or giving an unknown value, is a schema error.
* ``pack_version`` is now **conditional**: required iff ``pack_level ==
  "built-in"``, optional for org / project packs (FR-005).
* ``requires_core`` is an optional PEP 440 version specifier; a value that does
  not parse is a schema error naming the field (FR-002).
* ``active_charter`` / ``pack_drg`` are optional plain pack-relative strings
  (FR-003 / FR-004); in-pack path resolution is validated later (WP02).

These assertions exercise the model directly (``PackDescriptor(...)`` /
``model_validate``), never the loader — the deprecation-window load tolerance
for a missing ``pack_level`` is a separate surface (WP02).
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError
from ulid import ULID

from charter.offering.packs.pack_descriptor import PackDescriptor
from kernel.pack_tiers import PACK_TIERS

pytestmark = [pytest.mark.unit, pytest.mark.fast, pytest.mark.doctrine]


def _ulid() -> str:
    return str(ULID())


# ---------------------------------------------------------------------------
# pack_level — required, kernel-authority tokens only
# ---------------------------------------------------------------------------


def test_org_pack_without_pack_version_validates() -> None:
    """An org pack declares ``pack_level`` and needs no ``pack_version`` (FR-005)."""
    descriptor = PackDescriptor(pack_id=_ulid(), name="acme-org", pack_level="org")

    assert descriptor.pack_level == "org"
    assert descriptor.pack_version is None


def test_project_pack_without_pack_version_validates() -> None:
    """A project pack declares ``pack_level`` and needs no ``pack_version`` (FR-005)."""
    descriptor = PackDescriptor(pack_id=_ulid(), name="acme-project", pack_level="project")

    assert descriptor.pack_level == "project"
    assert descriptor.pack_version is None


def test_omitting_pack_level_is_a_schema_error() -> None:
    """``pack_level`` is required — omitting it raises naming the field."""
    with pytest.raises(ValidationError, match="pack_level"):
        PackDescriptor(pack_id=_ulid(), pack_version="1.0.0", name="no-level")  # type: ignore[call-arg]


@pytest.mark.parametrize("token", list(PACK_TIERS))
def test_every_kernel_tier_token_is_accepted(token: str) -> None:
    """Every :data:`kernel.pack_tiers.PACK_TIERS` token is a valid ``pack_level``."""
    version = "1.0.0" if token == "built-in" else None
    descriptor = PackDescriptor(pack_id=_ulid(), name="acme", pack_level=token, pack_version=version)  # type: ignore[arg-type]

    assert descriptor.pack_level == token


def test_unknown_pack_level_value_is_refused() -> None:
    """A ``pack_level`` outside the kernel authority is a schema error."""
    with pytest.raises(ValidationError, match="pack_level"):
        PackDescriptor(pack_id=_ulid(), name="acme", pack_level="enterprise")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# pack_version — conditional on built-in
# ---------------------------------------------------------------------------


def test_built_in_without_pack_version_is_refused() -> None:
    """A built-in pack must carry ``pack_version`` (FR-005)."""
    with pytest.raises(ValidationError, match="pack_version"):
        PackDescriptor(pack_id=_ulid(), name="built-in", pack_level="built-in")


def test_built_in_with_pack_version_validates() -> None:
    """A built-in pack with ``pack_version`` is accepted."""
    descriptor = PackDescriptor(pack_id=_ulid(), name="built-in", pack_level="built-in", pack_version="1.2.3")

    assert descriptor.pack_version == "1.2.3"


# ---------------------------------------------------------------------------
# requires_core — optional PEP 440 version specifier
# ---------------------------------------------------------------------------


def test_requires_core_accepts_a_valid_specifier() -> None:
    """A valid version-specifier range is accepted (FR-002)."""
    descriptor = PackDescriptor(
        pack_id=_ulid(),
        name="acme",
        pack_level="org",
        requires_core=">=4.0,<5.0",
    )

    assert descriptor.requires_core == ">=4.0,<5.0"


def test_requires_core_defaults_to_none() -> None:
    """``requires_core`` is optional; absent means no constraint."""
    descriptor = PackDescriptor(pack_id=_ulid(), name="acme", pack_level="org")

    assert descriptor.requires_core is None


def test_invalid_requires_core_is_a_schema_error_naming_the_field() -> None:
    """An unparsable ``requires_core`` is a schema error naming the field (FR-002)."""
    with pytest.raises(ValidationError, match="requires_core"):
        PackDescriptor(
            pack_id=_ulid(),
            name="acme",
            pack_level="org",
            requires_core="not a valid specifier!!!",
        )


# ---------------------------------------------------------------------------
# active_charter / pack_drg — optional pack-relative strings
# ---------------------------------------------------------------------------


def test_active_charter_and_pack_drg_accept_strings() -> None:
    """``active_charter`` / ``pack_drg`` accept plain pack-relative strings (FR-003/4)."""
    descriptor = PackDescriptor(
        pack_id=_ulid(),
        name="acme-org",
        pack_level="org",
        active_charter="org-charter.yaml",
        pack_drg="drg/fragment.yaml",
    )

    assert descriptor.active_charter == "org-charter.yaml"
    assert descriptor.pack_drg == "drg/fragment.yaml"


def test_active_charter_and_pack_drg_default_to_none() -> None:
    """Both layout pointers are optional and default to ``None``."""
    descriptor = PackDescriptor(pack_id=_ulid(), name="acme-org", pack_level="org")

    assert descriptor.active_charter is None
    assert descriptor.pack_drg is None


# ---------------------------------------------------------------------------
# frozen + extra-forbid preserved
# ---------------------------------------------------------------------------


def test_descriptor_is_still_frozen() -> None:
    """The model remains immutable once constructed."""
    descriptor = PackDescriptor(pack_id=_ulid(), name="acme", pack_level="org")

    with pytest.raises(ValidationError, match="frozen"):
        descriptor.pack_level = "project"  # type: ignore[misc]


def test_extra_fields_still_rejected() -> None:
    """``extra="forbid"`` is preserved — an unknown field is rejected."""
    with pytest.raises(ValidationError, match="extra"):
        PackDescriptor(pack_id=_ulid(), name="acme", pack_level="org", bogus="nope")  # type: ignore[call-arg]
