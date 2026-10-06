"""Unit tests for OrgPackConfig.subdir and effective_root seam (WP01).

Covers T001–T006 from the WP01 task specification.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from charter.offering.drg.org_pack_config import (
    OrgPackConfig,
    OrgPackEnvVarUnsetError,
    OrgPackSubdirEscapeError,
    PackRegistry,
    load_pack_registry,
    resolve_org_roots,
    save_pack_registry,
)

pytestmark = [pytest.mark.fast, pytest.mark.doctrine]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_PACK_NAME = "my-org-pack"
# Production-shaped local_path (not a toy "pack" placeholder)
_PACK_REL_PATH = "org-packs/acme-doctrine"
# Production-shaped ULID used in fixture paths to stay realistic
_MISSION_ULID = "01KVSRJ6ABCDEFGHIJKLMNOP"


def _make_pack(tmp_path: Path, *, subdir: str | None = None) -> OrgPackConfig:
    """Return an OrgPackConfig pointing at a real directory under tmp_path."""
    pack_root = tmp_path / _PACK_REL_PATH
    pack_root.mkdir(parents=True, exist_ok=True)
    return OrgPackConfig(
        name=_PACK_NAME,
        local_path=pack_root,
        subdir=subdir,
    )


def _write_config_with_subdir(
    repo_root: Path, *, pack_path: str, subdir: str | None = None
) -> None:
    """Write a canonical doctrine.org.packs config.yaml entry."""
    config_dir = repo_root / ".kittify"
    config_dir.mkdir(parents=True, exist_ok=True)
    subdir_line = f"\n        subdir: {subdir}" if subdir is not None else ""
    (config_dir / "config.yaml").write_text(
        f"doctrine:\n"
        f"  org:\n"
        f"    packs:\n"
        f"      - name: {_PACK_NAME}\n"
        f"        local_path: {pack_path}{subdir_line}\n",
        encoding="utf-8",
    )


def _write_legacy_config_with_subdir(
    repo_root: Path, *, pack_path: str, subdir: str | None = None
) -> None:
    """Write a legacy single-pack doctrine.org inline config."""
    config_dir = repo_root / ".kittify"
    config_dir.mkdir(parents=True, exist_ok=True)
    subdir_line = f"\n    subdir: {subdir}" if subdir is not None else ""
    (config_dir / "config.yaml").write_text(
        f"doctrine:\n"
        f"  org:\n"
        f"    local_path: {pack_path}{subdir_line}\n",
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# T001 / T003 — effective_root: no subdir
# ---------------------------------------------------------------------------


class TestEffectiveRootNoSubdir:
    """NFR-001: no-subdir packs behave identically to pre-WP01 behaviour."""

    def test_absolute_local_path_no_subdir(self, tmp_path: Path) -> None:
        """Absolute local_path with no subdir → resolved local_path."""
        pack_root = tmp_path / "abs-pack"
        pack_root.mkdir()
        pack = OrgPackConfig(name=_PACK_NAME, local_path=pack_root)
        result = pack.effective_root(tmp_path)
        assert result == pack_root.resolve(strict=False)

    def test_relative_local_path_no_subdir(self, tmp_path: Path) -> None:
        """Relative local_path joins with repo_root and resolves."""
        pack_root = tmp_path / "rel-pack"
        pack_root.mkdir()
        # Use a relative path string so relative-normalisation is exercised
        pack = OrgPackConfig(name=_PACK_NAME, local_path=Path("rel-pack"))
        result = pack.effective_root(tmp_path)
        assert result == (tmp_path / "rel-pack").resolve(strict=False)

    def test_no_subdir_field_defaults_to_none(self) -> None:
        pack = OrgPackConfig(name=_PACK_NAME, local_path=Path("/some/pack"))
        assert pack.subdir is None


# ---------------------------------------------------------------------------
# T003 — effective_root: with subdir
# ---------------------------------------------------------------------------


class TestEffectiveRootWithSubdir:
    """FR-001/002: subdir is joined onto local_path in the effective root."""

    def test_subdir_joined_to_absolute_local_path(self, tmp_path: Path) -> None:
        pack_root = tmp_path / "acme-doctrine"
        (pack_root / "inner").mkdir(parents=True)
        pack = OrgPackConfig(name=_PACK_NAME, local_path=pack_root, subdir="inner")
        result = pack.effective_root(tmp_path)
        assert result == (pack_root / "inner").resolve(strict=False)

    def test_subdir_joined_to_relative_local_path(self, tmp_path: Path) -> None:
        pack_root = tmp_path / "acme-doctrine"
        (pack_root / "core").mkdir(parents=True)
        pack = OrgPackConfig(
            name=_PACK_NAME, local_path=Path("acme-doctrine"), subdir="core"
        )
        result = pack.effective_root(tmp_path)
        assert result == (tmp_path / "acme-doctrine" / "core").resolve(strict=False)

    def test_nested_subdir(self, tmp_path: Path) -> None:
        pack_root = tmp_path / "doctrine-pack"
        (pack_root / "a" / "b").mkdir(parents=True)
        pack = OrgPackConfig(
            name=_PACK_NAME, local_path=pack_root, subdir="a/b"
        )
        result = pack.effective_root(tmp_path)
        assert result == (pack_root / "a" / "b").resolve(strict=False)


# ---------------------------------------------------------------------------
# T002 — subdir string-level validator
# ---------------------------------------------------------------------------


class TestSubdirValidator:
    """FR-003: reject absolute/escape paths at model-construction time."""

    def test_none_is_accepted(self) -> None:
        pack = OrgPackConfig(name=_PACK_NAME, local_path=Path("/pack"), subdir=None)
        assert pack.subdir is None

    def test_empty_string_normalised_to_none(self) -> None:
        pack = OrgPackConfig(name=_PACK_NAME, local_path=Path("/pack"), subdir="")
        assert pack.subdir is None

    def test_dot_normalised_to_none(self) -> None:
        pack = OrgPackConfig(name=_PACK_NAME, local_path=Path("/pack"), subdir=".")
        assert pack.subdir is None

    def test_valid_relative_subdir_accepted(self) -> None:
        pack = OrgPackConfig(
            name=_PACK_NAME, local_path=Path("/pack"), subdir="doctrine/v2"
        )
        assert pack.subdir == "doctrine/v2"

    def test_posix_absolute_rejected(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            OrgPackConfig(name=_PACK_NAME, local_path=Path("/pack"), subdir="/etc")
        assert "absolute" in str(exc_info.value).lower()

    def test_posix_absolute_nested_rejected(self) -> None:
        with pytest.raises(ValidationError):
            OrgPackConfig(
                name=_PACK_NAME, local_path=Path("/pack"), subdir="/usr/local/share"
            )

    def test_windows_drive_absolute_rejected(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            OrgPackConfig(
                name=_PACK_NAME, local_path=Path("/pack"), subdir=r"C:\Users\x"
            )
        assert "absolute" in str(exc_info.value).lower()

    def test_unc_absolute_rejected(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            OrgPackConfig(
                name=_PACK_NAME, local_path=Path("/pack"), subdir=r"\\server\share"
            )
        assert "absolute" in str(exc_info.value).lower()

    def test_dotdot_single_rejected(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            OrgPackConfig(name=_PACK_NAME, local_path=Path("/pack"), subdir="..")
        assert ".." in str(exc_info.value)

    def test_dotdot_in_path_rejected(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            OrgPackConfig(
                name=_PACK_NAME, local_path=Path("/pack"), subdir="../escape"
            )
        assert ".." in str(exc_info.value)

    def test_dotdot_buried_in_path_rejected(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            OrgPackConfig(
                name=_PACK_NAME, local_path=Path("/pack"), subdir="a/../../b"
            )
        assert ".." in str(exc_info.value)

    def test_subdir_validator_does_not_touch_filesystem(self, tmp_path: Path) -> None:
        """Validator must NOT stat or open the path — non-existent is fine."""
        nonexistent_pack = tmp_path / "does-not-exist"
        # Should not raise, even though the path doesn't exist
        pack = OrgPackConfig(
            name=_PACK_NAME, local_path=nonexistent_pack, subdir="subdir/that/also/missing"
        )
        assert pack.subdir == "subdir/that/also/missing"


# ---------------------------------------------------------------------------
# T003 — strict-resolve gotcha: non-existent pack dir must NOT crash
# ---------------------------------------------------------------------------


class TestEffectiveRootNonExistentDir:
    """FR-006-adjacent: a not-yet-fetched pack dir must not raise FileNotFoundError."""

    def test_missing_pack_dir_no_subdir(self, tmp_path: Path) -> None:
        pack_root = tmp_path / "not-yet-cloned"
        pack = OrgPackConfig(name=_PACK_NAME, local_path=pack_root)
        # Must not raise FileNotFoundError
        result = pack.effective_root(tmp_path)
        assert result == pack_root.resolve(strict=False)

    def test_missing_pack_dir_with_subdir(self, tmp_path: Path) -> None:
        pack_root = tmp_path / "not-yet-cloned"
        pack = OrgPackConfig(name=_PACK_NAME, local_path=pack_root, subdir="doctrine")
        # Must not raise FileNotFoundError
        result = pack.effective_root(tmp_path)
        assert result == (pack_root / "doctrine").resolve(strict=False)


# ---------------------------------------------------------------------------
# T005 — symlink-escape raises OrgPackSubdirEscapeError
# ---------------------------------------------------------------------------


class TestSymlinkEscape:
    """NFR-002: resolution-time containment check raises the named structured error."""

    def test_symlink_pointing_outside_raises_named_error(
        self, tmp_path: Path
    ) -> None:
        """A subdir that is a symlink pointing outside local_path must be rejected."""
        pack_root = tmp_path / "pack"
        pack_root.mkdir()
        outside_dir = tmp_path / "outside"
        outside_dir.mkdir()

        # Create a symlink inside the pack pointing outside
        escape_link = pack_root / "escape"
        escape_link.symlink_to(outside_dir)

        pack = OrgPackConfig(name=_PACK_NAME, local_path=pack_root, subdir="escape")
        with pytest.raises(OrgPackSubdirEscapeError):
            pack.effective_root(tmp_path)

    def test_escape_is_not_swallowed_to_empty_registry(
        self, tmp_path: Path
    ) -> None:
        """OrgPackSubdirEscapeError propagates out of resolve_org_roots (not swallowed)."""
        pack_root = tmp_path / "pack"
        pack_root.mkdir()
        outside_dir = tmp_path / "outside"
        outside_dir.mkdir()
        escape_link = pack_root / "escape"
        escape_link.symlink_to(outside_dir)

        _write_config_with_subdir(
            tmp_path, pack_path=str(pack_root), subdir="escape"
        )

        with pytest.raises(OrgPackSubdirEscapeError):
            resolve_org_roots(tmp_path)

    def test_escape_error_is_subclass_of_value_error(self) -> None:
        """OrgPackSubdirEscapeError is a ValueError subclass for compatibility."""
        assert issubclass(OrgPackSubdirEscapeError, ValueError)


# ---------------------------------------------------------------------------
# T003 — resolve_org_roots fan-in
# ---------------------------------------------------------------------------


class TestResolveOrgRoots:
    """The fan-in function returns effective roots, not raw local_path values."""

    def test_no_subdir_pack_returns_resolved_local_path(
        self, tmp_path: Path
    ) -> None:
        pack_root = tmp_path / "doctrine-root"
        pack_root.mkdir()
        _write_config_with_subdir(tmp_path, pack_path=str(pack_root))

        roots = resolve_org_roots(tmp_path)
        assert roots == [pack_root.resolve(strict=False)]
        assert roots[0] == pack_root.resolve(strict=False)

    def test_subdir_pack_returns_joined_effective_root(
        self, tmp_path: Path
    ) -> None:
        pack_root = tmp_path / "doctrine-root"
        (pack_root / "core").mkdir(parents=True)
        _write_config_with_subdir(tmp_path, pack_path=str(pack_root), subdir="core")

        roots = resolve_org_roots(tmp_path)
        assert roots == [(pack_root / "core").resolve(strict=False)]
        assert roots[0] == (pack_root / "core").resolve(strict=False)

    def test_multiple_packs_mixed_subdir(self, tmp_path: Path) -> None:
        pack_a = tmp_path / "pack-a"
        pack_a.mkdir()
        pack_b = tmp_path / "pack-b"
        (pack_b / "inner").mkdir(parents=True)

        config_dir = tmp_path / ".kittify"
        config_dir.mkdir(parents=True, exist_ok=True)
        (config_dir / "config.yaml").write_text(
            f"doctrine:\n"
            f"  org:\n"
            f"    packs:\n"
            f"      - name: pack-a\n"
            f"        local_path: {pack_a}\n"
            f"      - name: pack-b\n"
            f"        local_path: {pack_b}\n"
            f"        subdir: inner\n",
            encoding="utf-8",
        )

        roots = resolve_org_roots(tmp_path)
        assert roots == [
            pack_a.resolve(strict=False),
            (pack_b / "inner").resolve(strict=False),
        ]
        assert roots[0] == pack_a.resolve(strict=False)
        assert roots[1] == (pack_b / "inner").resolve(strict=False)


# ---------------------------------------------------------------------------
# T004 — round-trip: packs shape
# ---------------------------------------------------------------------------


class TestRoundTrip:
    """FR-005/006: subdir survives save→load; absent emits no key."""

    def test_subdir_preserved_in_round_trip(self, tmp_path: Path) -> None:
        pack_root = tmp_path / "doctrine-pack"
        pack_root.mkdir()
        pack = OrgPackConfig(
            name=_PACK_NAME, local_path=pack_root, subdir="doctrine/v2"
        )
        registry = PackRegistry(packs=[pack])
        save_pack_registry(tmp_path, registry)

        loaded = load_pack_registry(tmp_path)
        assert {p.subdir for p in loaded.packs} == {"doctrine/v2"}
        assert loaded.packs[0].subdir == "doctrine/v2"

    def test_no_subdir_does_not_emit_key(self, tmp_path: Path) -> None:
        pack_root = tmp_path / "doctrine-pack"
        pack_root.mkdir()
        pack = OrgPackConfig(name=_PACK_NAME, local_path=pack_root)
        registry = PackRegistry(packs=[pack])
        save_pack_registry(tmp_path, registry)

        config_text = (tmp_path / ".kittify" / "config.yaml").read_text(
            encoding="utf-8"
        )
        # The YAML key "subdir:" must not appear in the emitted config;
        # note that the path itself may contain "subdir" in temp-dir names,
        # so check for the YAML key pattern rather than a bare substring.
        assert "subdir:" not in config_text

    def test_no_subdir_round_trip_subdir_is_none(self, tmp_path: Path) -> None:
        pack_root = tmp_path / "doctrine-pack"
        pack_root.mkdir()
        pack = OrgPackConfig(name=_PACK_NAME, local_path=pack_root)
        registry = PackRegistry(packs=[pack])
        save_pack_registry(tmp_path, registry)

        loaded = load_pack_registry(tmp_path)
        assert loaded.packs[0].subdir is None

    def test_legacy_single_pack_shape_carries_subdir(self, tmp_path: Path) -> None:
        """Legacy inline doctrine.org shape with subdir is read correctly (T004)."""
        pack_root = tmp_path / "legacy-pack"
        pack_root.mkdir()
        _write_legacy_config_with_subdir(
            tmp_path, pack_path=str(pack_root), subdir="doctrine"
        )

        loaded = load_pack_registry(tmp_path)
        assert {p.subdir for p in loaded.packs} == {"doctrine"}
        assert loaded.packs[0].subdir == "doctrine"

    def test_legacy_single_pack_no_subdir_stays_none(self, tmp_path: Path) -> None:
        """Legacy inline doctrine.org shape without subdir → subdir is None."""
        pack_root = tmp_path / "legacy-pack"
        pack_root.mkdir()
        _write_legacy_config_with_subdir(tmp_path, pack_path=str(pack_root))

        loaded = load_pack_registry(tmp_path)
        assert loaded.packs[0].subdir is None


# ---------------------------------------------------------------------------
# T001/T002 — env-var indirection in local_path (WP01)
# ---------------------------------------------------------------------------

_ENV_VAR_NAME = "SPEC_KITTY_PACK_HOME"


class TestEnvVarExpansion:
    """FR-001-007: ``${VAR}``/``$VAR`` indirection in local_path, resolved
    read-side only at effective_root() time."""

    def test_braced_env_var_expands_at_effective_root(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        pack_root = tmp_path / "org-pack"
        pack_root.mkdir()
        monkeypatch.setenv(_ENV_VAR_NAME, str(tmp_path))

        pack = OrgPackConfig(
            name=_PACK_NAME, local_path=Path("${SPEC_KITTY_PACK_HOME}/org-pack")
        )
        result = pack.effective_root(tmp_path)
        assert result == pack_root.resolve(strict=False)

    def test_bare_dollar_env_var_expands_at_effective_root(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        pack_root = tmp_path / "org-pack"
        pack_root.mkdir()
        monkeypatch.setenv(_ENV_VAR_NAME, str(tmp_path))

        pack = OrgPackConfig(
            name=_PACK_NAME, local_path=Path("$SPEC_KITTY_PACK_HOME/org-pack")
        )
        result = pack.effective_root(tmp_path)
        assert result == pack_root.resolve(strict=False)

    def test_stored_local_path_is_not_mutated_by_expansion(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """T001: effective_root() must not write the expanded value back."""
        pack_root = tmp_path / "org-pack"
        pack_root.mkdir()
        monkeypatch.setenv(_ENV_VAR_NAME, str(tmp_path))

        pack = OrgPackConfig(
            name=_PACK_NAME, local_path=Path("${SPEC_KITTY_PACK_HOME}/org-pack")
        )
        pack.effective_root(tmp_path)
        assert str(pack.local_path) == "${SPEC_KITTY_PACK_HOME}/org-pack"

    def test_tilde_expansion_regression(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Pre-existing ``~`` expansion behaviour is unchanged (no regression)."""
        fake_home = tmp_path / "home"
        pack_root = fake_home / "org-pack"
        pack_root.mkdir(parents=True)
        monkeypatch.setenv("HOME", str(fake_home))

        pack = OrgPackConfig(name=_PACK_NAME, local_path=Path("~/org-pack"))
        result = pack.effective_root(tmp_path)
        assert result == pack_root.resolve(strict=False)
        # Stored value must still be the literal ~-form, unexpanded
        assert str(pack.local_path) == "~/org-pack"

    def test_tilde_and_env_var_compose_in_one_local_path(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """FR-004: ``~`` and ``${VAR}`` in the SAME local_path both expand.

        Regression coverage for the composition case (adversarial-squad
        follow-up): each token was previously only exercised in isolation.
        """
        fake_home = tmp_path / "home"
        pack_root = fake_home / "acme" / "org-pack"
        pack_root.mkdir(parents=True)
        monkeypatch.setenv("HOME", str(fake_home))
        monkeypatch.setenv(_ENV_VAR_NAME, "acme")

        pack = OrgPackConfig(
            name=_PACK_NAME, local_path=Path("~/${SPEC_KITTY_PACK_HOME}/org-pack")
        )
        result = pack.effective_root(tmp_path)
        assert result == pack_root.resolve(strict=False)
        # Stored value must still be the literal unexpanded form.
        assert str(pack.local_path) == "~/${SPEC_KITTY_PACK_HOME}/org-pack"

    def test_unset_braced_env_var_raises_named_error(self, tmp_path: Path) -> None:
        """FR-004: unset ${VAR} fails closed, naming the var and the pack."""
        pack = OrgPackConfig(
            name=_PACK_NAME, local_path=Path("${SPEC_KITTY_DOES_NOT_EXIST}/org-pack")
        )
        with pytest.raises(OrgPackEnvVarUnsetError) as exc_info:
            pack.effective_root(tmp_path)
        message = str(exc_info.value)
        assert "SPEC_KITTY_DOES_NOT_EXIST" in message
        assert _PACK_NAME in message

    def test_unset_bare_dollar_env_var_raises_named_error(self, tmp_path: Path) -> None:
        """FR-004: unset $VAR (bare form) also fails closed."""
        pack = OrgPackConfig(
            name=_PACK_NAME, local_path=Path("$SPEC_KITTY_DOES_NOT_EXIST/org-pack")
        )
        with pytest.raises(OrgPackEnvVarUnsetError) as exc_info:
            pack.effective_root(tmp_path)
        message = str(exc_info.value)
        assert "SPEC_KITTY_DOES_NOT_EXIST" in message
        assert _PACK_NAME in message

    def test_env_var_unset_error_is_a_value_error(self) -> None:
        assert issubclass(OrgPackEnvVarUnsetError, ValueError)

    def test_env_var_expansion_not_swallowed_by_resolve_org_roots(
        self, tmp_path: Path
    ) -> None:
        """The unset-var error must propagate out of resolve_org_roots (not
        be silently swallowed into an empty org layer)."""
        _write_config_with_subdir(
            tmp_path, pack_path="${SPEC_KITTY_DOES_NOT_EXIST}/org-pack"
        )
        with pytest.raises(OrgPackEnvVarUnsetError):
            resolve_org_roots(tmp_path)

    def test_subdir_env_var_syntax_is_not_expanded(self, tmp_path: Path) -> None:
        """subdir keeps validating (and using) the literal string — env-var
        syntax in subdir is neither expanded nor specially rejected; it is
        treated as a literal relative path component."""
        pack_root = tmp_path / "org-pack"
        (pack_root / "${NOT_EXPANDED}").mkdir(parents=True)

        pack = OrgPackConfig(
            name=_PACK_NAME, local_path=pack_root, subdir="${NOT_EXPANDED}"
        )
        assert pack.subdir == "${NOT_EXPANDED}"
        result = pack.effective_root(tmp_path)
        assert result == (pack_root / "${NOT_EXPANDED}").resolve(strict=False)

    def test_round_trip_preserves_env_var_template(self, tmp_path: Path) -> None:
        """T003: save→load round-trip preserves the literal ${VAR} template,
        never freezing an expanded absolute path into config.yaml."""
        pack = OrgPackConfig(
            name=_PACK_NAME, local_path=Path("${SPEC_KITTY_PACK_HOME}/org-pack")
        )
        registry = PackRegistry(packs=[pack])
        save_pack_registry(tmp_path, registry)

        config_text = (tmp_path / ".kittify" / "config.yaml").read_text(
            encoding="utf-8"
        )
        assert "${SPEC_KITTY_PACK_HOME}/org-pack" in config_text

        loaded = load_pack_registry(tmp_path)
        assert {str(p.local_path) for p in loaded.packs} == {
            "${SPEC_KITTY_PACK_HOME}/org-pack"
        }
        assert str(loaded.packs[0].local_path) == "${SPEC_KITTY_PACK_HOME}/org-pack"

    def test_empty_env_var_raises_named_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """FR-004: env var set to empty string fails closed (not swallowed as a valid path).

        ``os.path.expandvars`` consumes the token when the var is set to ``""``,
        leaving no ``$``-residue.  ``_unresolved_env_token`` therefore returns ``None``
        and the old code would silently produce ``/org-pack``.  The new
        ``_empty_expanded_env_token`` guard catches this case and raises.
        """
        monkeypatch.setenv("SPEC_KITTY_PACK_HOME_EMPTY", "")
        pack = OrgPackConfig(
            name=_PACK_NAME,
            local_path=Path("${SPEC_KITTY_PACK_HOME_EMPTY}/org-pack"),
        )
        with pytest.raises(OrgPackEnvVarUnsetError) as exc_info:
            pack.effective_root(tmp_path)
        message = str(exc_info.value)
        assert "SPEC_KITTY_PACK_HOME_EMPTY" in message
        assert _PACK_NAME in message
