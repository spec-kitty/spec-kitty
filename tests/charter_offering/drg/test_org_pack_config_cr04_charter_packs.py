"""``.kittify/config.yaml`` org-pack registry: ``charter_packs.org.packs`` is the only shape read.

Mission ``charter-pack-cutover-01M491G6`` (#3732, FR-011) deleted the read-side
shims for the retired ``doctrine.org`` and ``organisation_packs`` keys: the
upgrade migration rewrites them and the CLI-root ``LEGACY_CHARTER_STATE`` gate
refuses a project that still has them. The registry reader therefore ignores
them (an empty registry, never an error, so ``PackContext.from_config`` stays
total) and never warns.
"""

from __future__ import annotations

import warnings
from pathlib import Path

import pytest

from charter.offering.drg.org_pack_config import load_pack_registry, require_declared_org_roots

pytestmark = [pytest.mark.fast, pytest.mark.doctrine]


def _write_config(repo_root: Path, text: str) -> Path:
    config_dir = repo_root / ".kittify"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / "config.yaml"
    config_path.write_text(text, encoding="utf-8")
    return config_path


def _packs_block(top_key: str, name: str, root: Path) -> str:
    return f"{top_key}:\n  org:\n    packs:\n      - name: {name}\n        local_path: {root}\n"


def test_charter_packs_org_packs_reads_without_warning(tmp_path: Path) -> None:
    org_root = tmp_path / "org-pack"
    org_root.mkdir()
    _write_config(tmp_path, _packs_block("charter_packs", "example-org", org_root))

    with warnings.catch_warnings():
        warnings.simplefilter("error")
        registry = load_pack_registry(tmp_path)

    assert registry.names() == ["example-org"]


@pytest.mark.parametrize("strict", [False, True], ids=["lenient", "strict"])
@pytest.mark.parametrize(
    "legacy_text",
    [
        "doctrine:\n  org:\n    packs:\n      - name: legacy-org\n        local_path: {root}\n",
        "doctrine:\n  org:\n    local_path: {root}\n",
        "organisation_packs:\n  - name: legacy-org\n    path: {root}\n",
    ],
    ids=["doctrine-org-packs", "doctrine-org-single-pack", "organisation-packs"],
)
def test_a_retired_key_is_not_read_and_not_rejected(tmp_path: Path, legacy_text: str, strict: bool) -> None:
    """A legacy-only config yields an empty registry, silently, in both modes (the CLI gate owns refusal)."""
    org_root = tmp_path / "org-pack"
    org_root.mkdir()
    _write_config(tmp_path, legacy_text.format(root=org_root))

    with warnings.catch_warnings():
        warnings.simplefilter("error")
        registry = load_pack_registry(tmp_path, strict=strict)

    assert registry.names() == []


def test_canonical_block_is_read_beside_a_stale_retired_key(tmp_path: Path) -> None:
    canonical_root = tmp_path / "canonical-pack"
    canonical_root.mkdir()
    legacy_root = tmp_path / "legacy-pack"
    legacy_root.mkdir()
    _write_config(tmp_path, _packs_block("charter_packs", "canonical-org", canonical_root) + _packs_block("doctrine", "legacy-org", legacy_root))

    assert load_pack_registry(tmp_path).names() == ["canonical-org"]


def test_unnamed_single_pack_block_is_a_config_error(tmp_path: Path) -> None:
    """``charter_packs.org.local_path`` is no second pack shape: lenient warns and reads nothing, strict raises."""
    org_root = tmp_path / "org-pack"
    org_root.mkdir()
    _write_config(tmp_path, f"charter_packs:\n  org:\n    local_path: {org_root}\n")

    with pytest.warns(UserWarning, match=r"charter_packs\.org\.packs\[\]"):
        assert load_pack_registry(tmp_path).names() == []
    with pytest.raises(ValueError, match=r"charter_packs\.org\.local_path"):
        load_pack_registry(tmp_path, strict=True)
    with pytest.raises(ValueError, match="cannot be read"):
        require_declared_org_roots(tmp_path)


def test_org_block_without_packs_is_an_empty_registry(tmp_path: Path) -> None:
    _write_config(tmp_path, "charter_packs:\n  org: {}\n")

    assert load_pack_registry(tmp_path, strict=True).names() == []


def test_an_unreadable_registry_is_the_typed_refusal_on_both_bases(tmp_path: Path) -> None:
    """Issue #6772: the strict registry refusal is the typed ``OrgPackRegistryUnreadableError``.

    The typed error must be BOTH an ``ActiveCharterConfigError`` (so it carries
    ``ACTIVE_CHARTER_CONFIG_INVALID`` and every ``except ActiveCharterConfigError``
    arm — ``charter activate``'s config refusal among them — renders it identically
    to ``charter deactivate``'s strict required-floor read) AND a ``ValueError``
    (so the fail-closed org-chain readers that document ``except ValueError`` —
    ``effective_set``, ``preset_application``, ``manifest_loader`` — keep their
    refusal behaviour unchanged). The dual base is the contract; pin both.

    The seam (C-004 one-way boundary): ``require_declared_org_roots`` raises the
    offering-owned ``UnreadableOrgPackRegistry``; the activation-side strict
    chain authority (``resolve_pack_chain(strict=True)``) — the read ``charter
    activate`` and the preset/effective-set reasoners go through — maps exactly
    that error onto the typed refusal.
    """
    _write_config(tmp_path, "charter_packs: [1, 2]\n")

    from charter.activation.activation_ledger import ActiveCharterConfigError, OrgPackRegistryUnreadableError
    from charter.activation.layer_roots import resolve_pack_chain
    from charter.offering.drg.org_pack_config import UnreadableOrgPackRegistry

    # Offering-side: the refusal is offering-owned — a ValueError, not yet typed.
    with pytest.raises(UnreadableOrgPackRegistry) as offering_side:
        require_declared_org_roots(tmp_path)
    assert not isinstance(offering_side.value, ActiveCharterConfigError)

    # Activation-side: the strict chain authority maps it onto the typed error.
    with pytest.raises(OrgPackRegistryUnreadableError) as raised:
        resolve_pack_chain(tmp_path, strict=True)

    error = raised.value
    # Base 1: an ActiveCharterConfigError, so the CLI reports the one honest code on both verbs.
    assert isinstance(error, ActiveCharterConfigError)
    assert error.code == "ACTIVE_CHARTER_CONFIG_INVALID"
    assert error.body.startswith("the org pack registry cannot be read:")
    # Base 2: still a ValueError, so the strict org-chain readers' contracts hold.
    assert isinstance(error, ValueError)
    # str(exc) stays the human message (not the code): strict readers interpolate it.
    assert str(error) == error.body
    # The body is the offering-side message, unchanged by the mapping.
    assert error.body == str(offering_side.value)
    # The cause is chained, so the underlying parse failure stays visible in the traceback.
    assert isinstance(raised.value.__cause__, UnreadableOrgPackRegistry)


def test_a_declared_but_unfetched_pack_stays_a_plain_value_error(tmp_path: Path) -> None:
    """Issue #6772: only the unreadable-registry arm is typed; the fetch remedy case stays distinguishable."""
    absent_root = tmp_path / "not-fetched"
    _write_config(tmp_path, _packs_block("charter_packs", "unfetched-org", absent_root))

    from charter.activation.activation_ledger import ActiveCharterConfigError
    from charter.activation.layer_roots import resolve_pack_chain

    with pytest.raises(ValueError, match="unfetched-org") as raised:
        require_declared_org_roots(tmp_path)

    assert not isinstance(raised.value, ActiveCharterConfigError)

    # Through the strict chain authority too: the mapping must not swallow the
    # fetch remedy into a config-invalid refusal (activate keeps ACTIVATION_FAILED).
    with pytest.raises(ValueError, match="unfetched-org") as chain_side:
        resolve_pack_chain(tmp_path, strict=True)

    assert not isinstance(chain_side.value, ActiveCharterConfigError)


def test_the_offering_raise_never_imports_activation() -> None:
    """The offering module's refusal crosses no seam at all (C-004 one-way boundary).

    ``charter.offering`` may not import ``charter.activation`` at any scope
    (gated statically by ``tests/architectural/test_charter_offering_does_not_import_activation.py``);
    the typed error is produced by the activation-side mapping in
    ``layer_roots.resolve_pack_chain`` instead. Runtime complement of the
    static gate: importing ``org_pack_config`` and driving its refusal path
    leaves ``charter.activation.activation_ledger`` unloaded.
    """
    import subprocess
    import sys

    probe = """
import pathlib, sys, tempfile

import charter.offering.drg.org_pack_config as m

assert "charter.activation.activation_ledger" not in sys.modules

d = pathlib.Path(tempfile.mkdtemp())
(d / ".kittify").mkdir()
(d / ".kittify" / "config.yaml").write_text("charter_packs: [1, 2]\\n")
try:
    m.require_declared_org_roots(d)
except ValueError as exc:
    assert type(exc).__name__ == "UnreadableOrgPackRegistry"
    assert "charter.activation.activation_ledger" not in sys.modules
    sys.exit(0)
sys.exit(1)
"""
    subprocess.run([sys.executable, "-c", probe], check=True)
