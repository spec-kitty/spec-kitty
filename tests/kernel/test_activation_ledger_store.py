"""``kernel.activation_ledger_store``: path, raw read, scope and the one source resolver (FR-017).

Every row of the one-mode table (data-model.md §5, operator ruling
``mission_pivot_option_b``) is one case here: the ledger when it exists; the
legacy surface inside the upgrade scope; the legacy surface with
``unmigrated_keys`` for an unmigrated project; the ledger (``exists=False``)
for a fresh project.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from kernel import activation_ledger_store as store
from kernel.activation_ledger_store import (
    ACTIVATION_LEDGER,
    ActivationLedgerFormatError,
    ActivationSource,
    activation_ledger_path,
    in_legacy_activation_scope,
    legacy_activation_scope,
    read_activation_ledger_raw,
    resolve_activation_source,
    resolve_legacy_pointer,
)
from kernel.errors import KittyInternalConsistencyError

pytestmark = [pytest.mark.fast]

_POINTER = ".kittify/charter/charter.yaml"
#: The ``config.yaml`` pointer key the activation seam supplies (the kernel spells none of it).
_POINTER_KEY = "charter"
_KEYS = frozenset({"activated_kinds", "activated_directives", "deactivated_tactics", "mission_type_activations"})


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _config(root: Path, text: str) -> Path:
    return _write(root / ".kittify" / "config.yaml", text)


def _charter(root: Path, text: str) -> Path:
    _config(root, f"charter: {_POINTER}\n")
    return _write(root / _POINTER, text)


def _ledger(root: Path, text: str = "activated_tactics: [t1]\n") -> Path:
    return _write(root / ACTIVATION_LEDGER, text)


def _resolve(root: Path) -> store.ResolvedActivationSource:
    return resolve_activation_source(root, legacy_keys=_KEYS, pointer_key=_POINTER_KEY)


# --------------------------------------------------------------------------- #
# Path
# --------------------------------------------------------------------------- #


def test_ledger_path_constant() -> None:
    assert Path(".kittify", "charter", "activation.yaml") == ACTIVATION_LEDGER
    assert activation_ledger_path(Path("/r")) == Path("/r/.kittify/charter/activation.yaml")


def test_the_resolver_has_one_mode_and_no_unmigrated_source() -> None:
    assert {source.value for source in ActivationSource} == {"ledger", "legacy"}
    assert not any(name.startswith("activation_st") for name in store.__all__)


# --------------------------------------------------------------------------- #
# The one-mode table
# --------------------------------------------------------------------------- #


class TestOneMode:
    def test_ledger_exists_no_legacy_keys(self, tmp_path: Path) -> None:
        _charter(tmp_path, "governance: {}\n")
        _ledger(tmp_path)
        resolved = _resolve(tmp_path)
        assert (resolved.source, resolved.ledger_exists, resolved.stray_legacy_keys, resolved.unmigrated) == (ActivationSource.LEDGER, True, (), False)

    def test_ledger_exists_with_legacy_keys_reports_them_stray(self, tmp_path: Path) -> None:
        charter = _charter(tmp_path, "activated_directives: [d1]\ngovernance: {}\n")
        config = _config(tmp_path, f"charter: {_POINTER}\nactivated_kinds: [directives]\n")
        _ledger(tmp_path)
        resolved = _resolve(tmp_path)
        assert resolved.source is ActivationSource.LEDGER
        assert resolved.stray_legacy_keys == (
            (config, ("activated_kinds",)),
            (charter, ("activated_directives",)),
        )
        assert resolved.unmigrated is False

    @pytest.mark.parametrize("seed", ["blank", "config_keys", "pointer_keys"])
    def test_no_ledger_inside_scope_is_legacy(self, tmp_path: Path, seed: str) -> None:
        if seed == "config_keys":
            _config(tmp_path, "activated_directives: [d1]\n")
        elif seed == "pointer_keys":
            _charter(tmp_path, "activated_directives: [d1]\n")
        with legacy_activation_scope(tmp_path):
            resolved = _resolve(tmp_path)
        assert (resolved.source, resolved.ledger_exists, resolved.unmigrated) == (ActivationSource.LEGACY, False, False)
        if seed == "pointer_keys":
            assert (resolved.pointer, resolved.pointer_exists) == (tmp_path / _POINTER, True)

    def test_no_ledger_outside_scope_with_legacy_keys_is_unmigrated_legacy(self, tmp_path: Path) -> None:
        charter = _charter(tmp_path, "activated_directives: [d1]\ndeactivated_tactics: [t]\n")
        config = _config(tmp_path, f"charter: {_POINTER}\nactivated_kinds: [directives]\n")
        resolved = _resolve(tmp_path)
        assert (resolved.source, resolved.unmigrated, resolved.ledger_exists) == (ActivationSource.LEGACY, True, False)
        assert resolved.unmigrated_keys == (
            (config, ("activated_kinds",)),
            (charter, ("activated_directives", "deactivated_tactics")),
        )
        assert (resolved.pointer, resolved.pointer_exists) == (charter, True)

    def test_positive_control_same_fixture_plus_ledger_is_ledger(self, tmp_path: Path) -> None:
        """F15: the unmigrated fixture plus a ledger resolves LEDGER, not unmigrated."""
        _charter(tmp_path, "activated_directives: [d1]\ndeactivated_tactics: [t]\n")
        _config(tmp_path, f"charter: {_POINTER}\nactivated_kinds: [directives]\n")
        _ledger(tmp_path)
        resolved = _resolve(tmp_path)
        assert (resolved.source, resolved.unmigrated, resolved.unmigrated_keys) == (ActivationSource.LEDGER, False, ())

    def test_config_keys_without_a_pointer_are_unmigrated(self, tmp_path: Path) -> None:
        config = _config(tmp_path, "activated_directives: [d1]\n")
        resolved = _resolve(tmp_path)
        assert (resolved.source, resolved.pointer) == (ActivationSource.LEGACY, None)
        assert resolved.unmigrated_keys == ((config, ("activated_directives",)),)

    def test_a_dangling_pointer_outside_scope_is_legacy_not_fresh(self, tmp_path: Path) -> None:
        _config(tmp_path, "charter: .kittify/charter/missing.yaml\n")
        resolved = _resolve(tmp_path)
        assert (resolved.source, resolved.pointer_exists, resolved.unmigrated) == (ActivationSource.LEGACY, False, False)

    @pytest.mark.parametrize("seed", ["blank", "config_no_keys", "pointer_no_keys"])
    def test_neither_is_a_fresh_ledger(self, tmp_path: Path, seed: str) -> None:
        if seed == "config_no_keys":
            _config(tmp_path, "agents: {}\n")
        elif seed == "pointer_no_keys":
            _charter(tmp_path, "governance: {}\n")
        resolved = _resolve(tmp_path)
        assert (resolved.source, resolved.ledger_exists, resolved.unmigrated) == (ActivationSource.LEDGER, False, False)


# --------------------------------------------------------------------------- #
# Pointer rule
# --------------------------------------------------------------------------- #


def test_dangling_pointer_is_reported_not_raised(tmp_path: Path) -> None:
    _config(tmp_path, "charter: .kittify/charter/missing.yaml\n")
    with legacy_activation_scope(tmp_path):
        resolved = _resolve(tmp_path)
    assert resolved.source is ActivationSource.LEGACY
    assert (resolved.pointer, resolved.pointer_exists) == (tmp_path / ".kittify/charter/missing.yaml", False)


def test_pointer_rule_string_only(tmp_path: Path) -> None:
    _config(tmp_path, "charter:\n  synthesis_inputs: {}\n")
    assert resolve_legacy_pointer(tmp_path, pointer_key=_POINTER_KEY) == (None, False)


def test_pointer_rule_absolute(tmp_path: Path) -> None:
    target = _write(tmp_path / "elsewhere" / "charter.yaml", "{}\n")
    _config(tmp_path, f"charter: {target}\n")
    assert resolve_legacy_pointer(tmp_path, pointer_key=_POINTER_KEY) == (target, True)


def test_pointer_rule_no_config(tmp_path: Path) -> None:
    assert resolve_legacy_pointer(tmp_path, pointer_key=_POINTER_KEY) == (None, False)


def test_malformed_config_raises_the_kernel_format_error(tmp_path: Path) -> None:
    _config(tmp_path, "a: [unclosed\n")
    with pytest.raises(ActivationLedgerFormatError):
        resolve_legacy_pointer(tmp_path, pointer_key=_POINTER_KEY)


# --------------------------------------------------------------------------- #
# Raw read
# --------------------------------------------------------------------------- #


def test_raw_read_absent_is_none(tmp_path: Path) -> None:
    assert read_activation_ledger_raw(tmp_path) is None


def test_raw_read_zero_bytes_is_empty_mapping(tmp_path: Path) -> None:
    _ledger(tmp_path, "")
    assert read_activation_ledger_raw(tmp_path) == {}


def test_raw_read_mapping(tmp_path: Path) -> None:
    _ledger(tmp_path, "activated_tactics: [t1]\n")
    assert read_activation_ledger_raw(tmp_path) == {"activated_tactics": ["t1"]}


@pytest.mark.parametrize("text", ["- a\n- b\n", "a: [unclosed\n", "just a scalar\n"])
def test_raw_read_bad_content_raises(tmp_path: Path, text: str) -> None:
    _ledger(tmp_path, text)
    with pytest.raises(ActivationLedgerFormatError) as excinfo:
        read_activation_ledger_raw(tmp_path)
    assert isinstance(excinfo.value, KittyInternalConsistencyError)
    assert excinfo.value.code == "ACTIVATION_LEDGER_FORMAT_INVALID"


# --------------------------------------------------------------------------- #
# Scope
# --------------------------------------------------------------------------- #


def test_scope_is_reentrant(tmp_path: Path) -> None:
    assert not in_legacy_activation_scope(tmp_path)
    with legacy_activation_scope(tmp_path):
        with legacy_activation_scope(tmp_path):
            assert in_legacy_activation_scope(tmp_path)
        assert in_legacy_activation_scope(tmp_path)
    assert not in_legacy_activation_scope(tmp_path)


def test_scope_matches_canonical_root(tmp_path: Path) -> None:
    main = tmp_path / "main"
    worktree = main / ".worktrees" / "lane-a"
    worktree.mkdir(parents=True)
    with legacy_activation_scope(worktree, canonical_root=main):
        assert in_legacy_activation_scope(main)
        assert in_legacy_activation_scope(worktree)
        assert not in_legacy_activation_scope(tmp_path / "other")
    assert not in_legacy_activation_scope(main)


def test_scope_matches_unresolved_spelling(tmp_path: Path) -> None:
    (tmp_path / "a").mkdir()
    with legacy_activation_scope(tmp_path / "a" / ".."):
        assert in_legacy_activation_scope(tmp_path)


# --------------------------------------------------------------------------- #
# Probe cache (NFR-003)
# --------------------------------------------------------------------------- #


def test_probe_is_cached_on_path_mtime_size(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    config = _config(tmp_path, "activated_directives: [d1]\n")
    loads: list[Path] = []
    real = store._safe_load_mapping

    def _spy(path: Path) -> Any:
        loads.append(path)
        return real(path)

    monkeypatch.setattr(store, "_safe_load_mapping", _spy)
    _resolve(tmp_path)
    first = len(loads)
    assert first >= 1
    _resolve(tmp_path)
    assert len(loads) == first, "an unchanged file is not re-probed"
    config.write_text("activated_directives: [d1, d2, d3]\n", encoding="utf-8")
    resolved = _resolve(tmp_path)
    assert len(loads) > first, "a changed file is re-probed"
    assert resolved.unmigrated_keys == ((config, ("activated_directives",)),)


# --------------------------------------------------------------------------- #
# FR-020: one warning per process, JSON stdout stays clean
# --------------------------------------------------------------------------- #


def test_stray_keys_warn_once_and_json_stays_parseable(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    from charter.activation.activation_ledger import load_activation_ledger

    _config(tmp_path, f"charter: {_POINTER}\nmission_type_activations: [software-dev]\n")
    _write(tmp_path / _POINTER, "activated_directives: [d1]\n")
    _ledger(tmp_path, "mission_type_activations: [software-dev]\n")

    first = load_activation_ledger(tmp_path)
    load_activation_ledger(tmp_path)
    captured = capsys.readouterr()
    stray = [line for line in captured.err.splitlines() if "activated_directives" in line]
    assert len(stray) == 1, captured.err
    assert "activation ledger (activation.yaml) wins" in stray[0]
    assert first.stray_legacy_keys
    assert captured.out == ""

    from typer.testing import CliRunner

    from specify_cli.cli.commands.charter import charter_app

    result = CliRunner().invoke(charter_app, ["list", "--repo-root", str(tmp_path), "--json"], catch_exceptions=False)
    assert result.exit_code == 0, result.output
    json.loads(result.stdout)


# --------------------------------------------------------------------------- #
# The legacy save in the one mode (C-003): never a deny key
# --------------------------------------------------------------------------- #


def test_a_legacy_save_refuses_a_deny_change_in_the_one_mode(tmp_path: Path) -> None:
    from charter.activation.activation_ledger import ActiveCharterConfigError
    from charter.activation.pack_manager import prepare_activation_write

    config = _config(tmp_path, "activated_directives: [d1]\n")
    before = config.read_bytes()
    with pytest.raises(ActiveCharterConfigError) as caught:
        prepare_activation_write(tmp_path, {"deactivated_directives": ["d1"]})
    assert "migrate activation-ledger" in caught.value.body
    assert config.read_bytes() == before
    assert not activation_ledger_path(tmp_path).exists()


# --------------------------------------------------------------------------- #
# Review cycle 1 regressions
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("text", ["", "{}\n"])
def test_an_empty_ledger_file_still_counts_as_ledger_exists(tmp_path: Path, text: str) -> None:
    """Issue 1: an emptied ledger stays the authority; legacy keys beside it are stray, not unmigrated."""
    config = _config(tmp_path, "activated_directives: [d1]\n")
    _ledger(tmp_path, text)
    resolved = _resolve(tmp_path)
    assert (resolved.source, resolved.ledger_exists) == (ActivationSource.LEDGER, True)
    assert resolved.stray_legacy_keys == ((config, ("activated_directives",)),)


def test_pointer_existence_is_exists_not_is_file(tmp_path: Path) -> None:
    """Issue 3: today's rule is ``exists()``; a directory pointer exists."""
    target = tmp_path / ".kittify" / "charter" / "adir"
    target.mkdir(parents=True)
    _config(tmp_path, "charter: .kittify/charter/adir\n")
    assert resolve_legacy_pointer(tmp_path, pointer_key=_POINTER_KEY) == (target, True)


def test_probe_skips_a_directory_pointer(tmp_path: Path) -> None:
    (tmp_path / ".kittify" / "charter" / "adir").mkdir(parents=True)
    _config(tmp_path, "charter: .kittify/charter/adir\n")
    assert _resolve(tmp_path).source is ActivationSource.LEDGER


def test_malformed_config_error_names_the_relative_path(tmp_path: Path) -> None:
    _config(tmp_path, "- a\n")
    with pytest.raises(ActivationLedgerFormatError) as excinfo:
        resolve_legacy_pointer(tmp_path, pointer_key=_POINTER_KEY)
    assert excinfo.value.body == ".kittify/config.yaml root must be a mapping."


def test_a_lazy_canonical_root_resolves_only_for_another_path(tmp_path: Path) -> None:
    main = tmp_path / "main"
    worktree = main / ".worktrees" / "lane-a"
    worktree.mkdir(parents=True)
    calls: list[str] = []

    def _root() -> Path:
        calls.append("resolved")
        return main

    with legacy_activation_scope(worktree, canonical_root=_root):
        assert in_legacy_activation_scope(worktree)
        assert calls == []
        assert in_legacy_activation_scope(main)
        assert calls == ["resolved"]
    assert not in_legacy_activation_scope(main)


def test_a_lazy_canonical_root_of_none_adds_no_root(tmp_path: Path) -> None:
    other = tmp_path / "other"
    other.mkdir()
    with legacy_activation_scope(tmp_path, canonical_root=lambda: None):
        assert in_legacy_activation_scope(tmp_path)
        assert not in_legacy_activation_scope(other)


def test_the_pointer_key_is_a_caller_parameter(tmp_path: Path) -> None:
    """The kernel spells no pointer key: the caller's key selects the value, from one cached probe."""
    first = _write(tmp_path / "first.yaml", "{}\n")
    _config(tmp_path, f"charter: {first}\nother: missing.yaml\nnested: {{a: 1}}\n")
    assert resolve_legacy_pointer(tmp_path, pointer_key=_POINTER_KEY) == (first, True)
    assert resolve_legacy_pointer(tmp_path, pointer_key="other") == (tmp_path / "missing.yaml", False)
    assert resolve_legacy_pointer(tmp_path, pointer_key="nested") == (None, False)
    assert resolve_legacy_pointer(tmp_path, pointer_key="absent") == (None, False)
