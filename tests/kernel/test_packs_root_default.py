"""Tests for kernel.paths.get_packs_root_default — C-EXP-3 (WP01 T005).

Also covers kernel.paths.get_runtime_state_root (WP01 T001) — the stdlib-safe
state-root primitive added alongside the packs-root default in the same
file, kept separate from get_kittify_home (the .kittify asset home).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from kernel.paths import (
    get_built_in_pack_root,
    get_kittify_home,
    get_packs_root_default,
    get_runtime_state_root,
)

pytestmark = pytest.mark.fast


class TestGetPacksRootDefault:
    """C-EXP-3: get_packs_root_default() == get_built_in_pack_root().parent."""

    def test_equals_built_in_pack_root_parent(self) -> None:
        assert get_packs_root_default() == get_built_in_pack_root().parent

    def test_token_plus_built_in_round_trips_no_double_join(self) -> None:
        """${SPEC_KITTY_PACKS_ROOT}/built-in must reconstruct get_built_in_pack_root()
        exactly — no double-joined .../built-in/built-in."""
        default_root = get_packs_root_default()
        expected = get_built_in_pack_root()
        assert Path(f"{default_root}/built-in") == expected
        assert "built-in/built-in" not in str(default_root)

    def test_env_override_round_trips_through_default(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        override_root = tmp_path / "org-packs"
        (override_root / "built-in").mkdir(parents=True)
        monkeypatch.setenv("SPEC_KITTY_PACKS_ROOT", str(override_root))

        assert get_built_in_pack_root() == override_root / "built-in"
        assert get_packs_root_default() == override_root


class TestGetRuntimeStateRoot:
    """T001: stdlib-safe state-root primitive, distinct from get_kittify_home."""

    def test_env_override_used_verbatim(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        override = tmp_path / "custom-state-root"
        monkeypatch.setenv("SPEC_KITTY_HOME", str(override))
        assert get_runtime_state_root() == override

    def test_posix_default_is_dot_spec_kitty_under_home(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("SPEC_KITTY_HOME", raising=False)
        monkeypatch.setattr("kernel.paths.is_windows", lambda: False)
        assert get_runtime_state_root() == Path.home() / ".spec-kitty"

    def test_distinct_from_kittify_home_by_directory_name(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The state root and the .kittify asset home are separate roots — never collapsed."""
        monkeypatch.delenv("SPEC_KITTY_HOME", raising=False)
        monkeypatch.setattr("kernel.paths.is_windows", lambda: False)
        assert get_runtime_state_root().name == ".spec-kitty"
        assert get_kittify_home().name == ".kittify"
        assert get_runtime_state_root() != get_kittify_home()

    def test_windows_uses_platformdirs_non_roaming(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import platformdirs

        monkeypatch.delenv("SPEC_KITTY_HOME", raising=False)
        monkeypatch.setattr("kernel.paths.is_windows", lambda: True)
        monkeypatch.setattr(
            platformdirs,
            "user_data_dir",
            lambda *_a, **_kw: r"C:\Users\test\AppData\Local\spec-kitty",
        )
        result = get_runtime_state_root()
        assert result == Path(r"C:\Users\test\AppData\Local\spec-kitty")

    def test_pure_no_directory_created(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Purity: calling this must not create the directory on disk."""
        target = tmp_path / "not-yet-created"
        monkeypatch.setenv("SPEC_KITTY_HOME", str(target))
        get_runtime_state_root()
        assert not target.exists()
