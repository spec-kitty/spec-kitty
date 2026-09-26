"""PR-BOUNDARY-001: focused unit test for ``AssetPreparation.overwrite_internal()``.

``agent_commands.py`` used to reach across module boundaries into
``AssetPreparation``'s private ``_effect()`` to write the agent-commands
freshness stamp, suppressed with ``# noqa: SLF001``. ``overwrite_internal()``
is the promoted public primitive that carries ``_effect()``'s exact "always
overwrite, no drift-preservation" semantics, documented as the supported way
for an OUT-OF-MODULE owner to write an internal, cache-only bookkeeping file
(never a user-facing managed asset -- that stays on ``asset()``).

This test proves the one property that matters for that contract: unlike
``asset()``, ``overwrite_internal()`` never preserves drifted/corrupted
content -- it always stages a fresh overwrite, so a hand-corrupted or
torn-write stamp self-heals on the very next successful write instead of
being preserved forever.

pr-FRESH-002: ``overwrite_internal()`` also guards its own target -- it
must refuse a path that is not the ".lock"-suffixed, cache-root-confined
shape every real internal bookkeeping file uses (``_VERSION_FILENAME``,
``_FRESHNESS_STAMP_FILENAME``, the persistent owner lock), so a future
misuse pointing it at a user-facing managed asset fails loudly instead of
silently clobbering it. The two baseline tests below now target
``freshness.lock`` (not ``freshness.json``) to stay inside that guard;
``test_overwrite_internal_rejects_a_non_internal_target`` proves the
refusal itself.
"""

from __future__ import annotations

import pytest

from pathlib import Path

from specify_cli.runtime.asset_preparation import AssetPreparation, digest
from specify_cli.tool_surface.operations import ApplyConsent, FileState, OperationRoot, OwnershipProof

pytestmark = [pytest.mark.unit, pytest.mark.fast]


def _prepared(tmp_path: Path) -> AssetPreparation:
    return AssetPreparation(
        "slash_commands",
        OperationRoot("slash_commands", "global", tmp_path),
        tmp_path / "cache",
        ".slash-commands.lock",
        ApplyConsent(),
    )


def test_overwrite_internal_stages_a_fresh_write_for_a_new_path(tmp_path: Path) -> None:
    """Baseline: writing a not-yet-existing internal file stages a "create"."""
    prepared = _prepared(tmp_path)
    target = tmp_path / "cache" / "freshness.lock"
    payload = b'{"cli_version": "1.0.0"}'

    prepared.overwrite_internal(
        target,
        FileState("file", sha256=digest(payload), mode=0o644),
        payload,
        OwnershipProof("managed_path", "slash_commands:freshness-stamp"),
    )

    write = prepared.writes[target]
    assert write.content == payload
    assert write.effect.action == "create"


def test_overwrite_internal_never_preserves_drifted_content(tmp_path: Path) -> None:
    """Unlike ``asset()``, a hand-corrupted stamp is overwritten, not preserved.

    Simulates the exact failure mode the module-boundary comment names: the
    inventory records the stamp as previously "owned" with one hash, but the
    bytes on disk (a torn write or hand edit) now hash to something else.
    ``asset()`` would call ``preserve()`` and refuse to touch it (correct for
    a user-facing file); ``overwrite_internal()`` must instead stage the
    fresh overwrite unconditionally -- self-healing, never permanently stuck.
    """
    prepared = _prepared(tmp_path)
    target = tmp_path / "cache" / "freshness.lock"
    target.parent.mkdir(parents=True)
    corrupted_bytes = b"not valid json at all"
    target.write_bytes(corrupted_bytes)

    relative = target.relative_to(prepared.root.path).as_posix()
    prepared.previous = {relative: {"kind": "file", "sha256": digest(b'{"cli_version": "0.9.0"}'), "mode": 0o644, "target": None, "mtime_ns": None}}
    prepared.entries = dict(prepared.previous)

    fresh_payload = b'{"cli_version": "1.0.0"}'
    prepared.overwrite_internal(
        target,
        FileState("file", sha256=digest(fresh_payload), mode=0o644),
        fresh_payload,
        OwnershipProof("managed_path", "slash_commands:freshness-stamp"),
    )

    assert not prepared.dispositions, f"overwrite_internal() must never preserve drift, got: {prepared.dispositions}"
    write = prepared.writes[target]
    assert write.content == fresh_payload
    assert write.effect.action == "update"


def test_overwrite_internal_allows_an_internal_cache_root_lock_path(tmp_path: Path) -> None:
    """Positive case: a real internal-shape path (cache root, ``.lock`` name,
    matching the ``_VERSION_FILENAME``/``_FRESHNESS_STAMP_FILENAME``
    convention) is accepted -- the guard must not reject legitimate use."""
    prepared = _prepared(tmp_path)
    target = tmp_path / "cache" / "agent-commands-freshness.lock"
    payload = b'{"cli_version": "1.0.0"}'

    prepared.overwrite_internal(
        target,
        FileState("file", sha256=digest(payload), mode=0o644),
        payload,
        OwnershipProof("managed_path", "slash_commands:freshness-stamp"),
    )

    write = prepared.writes[target]
    assert write.content == payload


def test_overwrite_internal_rejects_a_user_facing_managed_path(tmp_path: Path) -> None:
    """pr-FRESH-002: a target outside the owner cache root -- e.g. a
    rendered, user-facing managed asset under the destination tree
    ``asset()``/``tree()`` write to -- must raise loudly, never silently
    clobber the file."""
    prepared = _prepared(tmp_path)
    managed_target = tmp_path / "commands" / "spec-kitty.specify.md"

    with pytest.raises(ValueError, match="non-internal target"):
        prepared.overwrite_internal(
            managed_target,
            FileState("file", sha256=digest(b"content"), mode=0o444),
            b"content",
            OwnershipProof("managed_path", "slash_commands:spec-kitty.specify.md"),
        )

    assert managed_target not in prepared.writes


def test_overwrite_internal_rejects_a_cache_root_path_without_the_lock_suffix(tmp_path: Path) -> None:
    """A path can sit in the cache root and still be refused: only the
    ``.lock`` late-apply shape is internal bookkeeping. The inventory manifest
    (``<owner>-assets.json``) deliberately stays on this side of the guard --
    it is written only through ``finish()``'s own direct ``_effect()`` call,
    never through this public primitive."""
    prepared = _prepared(tmp_path)
    inventory_shaped_target = tmp_path / "cache" / "slash_commands-assets.json"

    with pytest.raises(ValueError, match="non-internal target"):
        prepared.overwrite_internal(
            inventory_shaped_target,
            FileState("file", sha256=digest(b"{}"), mode=0o644),
            b"{}",
            OwnershipProof("managed_path", "slash_commands:inventory"),
        )

    assert inventory_shaped_target not in prepared.writes
