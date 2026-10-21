"""``charter.activation.activation_ledger``: vocabulary, typed load and the deny guard (FR-001, FR-002, FR-014, FR-020).

One mode (operator ruling ``mission_pivot_option_b``): a stray legacy key
beside a ledger warns once and the ledger wins (FR-020); an unmigrated project
reads its legacy allow keys, never a legacy deny key (hole 6).
"""

from __future__ import annotations

import subprocess
import sys
import warnings
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest
from ruamel.yaml import YAML

from charter.activation.activation_ledger import (
    DENY_KEYS,
    KIND_ALLOW_KEYS,
    LEDGER_KEYS,
    NON_KIND_ALLOW_KEYS,
    ActivationLedger,
    ActiveCharterConfigError,
    DenyListChoice,
    DenyListWriteRefused,
    _deny_changes,
    allow_key,
    deny_key,
    load_activation_ledger,
    prepare_ledger_write,
    refuse_unmigrated_deny_write,
    report_legacy_deny_keys,
    report_stray_legacy_keys,
    resolve_ledger_source,
)
from charter.activation.charter_yaml_io import apply_yaml_write
from charter.offering.artifact_kinds import ArtifactKind
from kernel.activation_ledger_store import ACTIVATION_LEDGER, ActivationSource, legacy_activation_scope
from tests._factories.activation_ledger import legacy_seed, read_activation_ledger, seed_activation_ledger

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_REPO_ROOT = Path(__file__).resolve().parents[3]
_POINTER = ".kittify/charter/charter.yaml"


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _ledger_file(root: Path, text: str) -> Path:
    return _write(root / ACTIVATION_LEDGER, text)


@contextmanager
def _config_error_naming(text: str) -> Iterator[None]:
    """``ActiveCharterConfigError`` whose ``body`` names *text* (``str()`` is the code)."""
    with pytest.raises(ActiveCharterConfigError) as excinfo:
        yield
    assert text in excinfo.value.body, excinfo.value.body


# --------------------------------------------------------------------------- #
# Vocabulary pin (D2, C-004)
# --------------------------------------------------------------------------- #


def test_kind_allow_keys_derive_from_the_enum_in_enum_order() -> None:
    assert tuple(f"activated_{k.plural}" for k in ArtifactKind if k.activatable) == KIND_ALLOW_KEYS


def test_non_kind_allow_keys() -> None:
    assert NON_KIND_ALLOW_KEYS == ("activated_kinds", "mission_type_activations")


def test_deny_keys_derive_from_the_enum_in_enum_order() -> None:
    assert tuple(f"deactivated_{k.plural}" for k in ArtifactKind if k.activatable) == DENY_KEYS


def test_ledger_keys_order() -> None:
    assert LEDGER_KEYS == NON_KIND_ALLOW_KEYS + KIND_ALLOW_KEYS + DENY_KEYS


def test_key_helpers() -> None:
    assert allow_key(ArtifactKind.AGENT_PROFILE) == "activated_agent_profiles"
    assert deny_key(ArtifactKind.DIRECTIVE) == "deactivated_directives"


def test_non_activatable_kind_has_no_key() -> None:
    with pytest.raises(ValueError, match="not charter-activatable"):
        deny_key(ArtifactKind.TEMPLATE)


# --------------------------------------------------------------------------- #
# Typed load, LEDGER source: L1 / L2
# --------------------------------------------------------------------------- #


def test_typed_load_of_a_ledger(tmp_path: Path) -> None:
    _ledger_file(
        tmp_path,
        "mission_type_activations: [software-dev]\nactivated_tactics: [t1, t2]\nactivated_directives: []\ndeactivated_directives: [D]\n",
    )
    ledger = load_activation_ledger(tmp_path)
    assert isinstance(ledger, ActivationLedger)
    assert (ledger.source, ledger.exists, ledger.path) == (ActivationSource.LEDGER, True, tmp_path / ACTIVATION_LEDGER)
    assert ledger.mission_type_activations == ("software-dev",)
    assert ledger.activated_kinds is None
    assert ledger.allow_for(ArtifactKind.TACTIC) == ("t1", "t2")
    assert ledger.allow_for(ArtifactKind.DIRECTIVE) == ()
    assert ledger.allow_for(ArtifactKind.SKILL) is None
    assert ledger.deny_for(ArtifactKind.DIRECTIVE) == ("D",)
    assert ledger.deny_for(ArtifactKind.TACTIC) == ()
    assert ledger.raw() == {
        "mission_type_activations": ["software-dev"],
        "activated_directives": [],
        "activated_tactics": ["t1", "t2"],
        "deactivated_directives": ["D"],
    }
    assert hash(ledger) == hash(load_activation_ledger(tmp_path))


def test_fresh_project_is_an_empty_ledger_that_does_not_exist(tmp_path: Path) -> None:
    ledger = load_activation_ledger(tmp_path)
    assert (ledger.source, ledger.exists) == (ActivationSource.LEDGER, False)
    assert ledger.raw() == {}


def test_unknown_non_deny_key_fails_closed(tmp_path: Path) -> None:
    _ledger_file(tmp_path, "activated_tactics: [t1]\nschema_version: 2\n")
    with _config_error_naming("schema_version"):
        load_activation_ledger(tmp_path)


def test_unknown_deny_key_is_kept_and_listed(tmp_path: Path) -> None:
    _ledger_file(tmp_path, "deactivated_newkinds: [x]\n")
    ledger = load_activation_ledger(tmp_path)
    assert ledger.unknown_deny_keys == ("deactivated_newkinds",)
    assert ledger.raw() == {"deactivated_newkinds": ["x"]}


@pytest.mark.parametrize(
    "text",
    ["activated_tactics: t1\n", "activated_tactics: {a: 1}\n", "activated_tactics: [1]\n", "deactivated_tactics: [[x]]\n"],
)
def test_bad_value_shapes_fail_closed(tmp_path: Path, text: str) -> None:
    _ledger_file(tmp_path, text)
    with _config_error_naming("activated_tactics"):
        load_activation_ledger(tmp_path)


def test_null_reads_as_absent(tmp_path: Path) -> None:
    _ledger_file(tmp_path, "activated_tactics: null\ndeactivated_tactics: null\n")
    ledger = load_activation_ledger(tmp_path)
    assert ledger.allow_for(ArtifactKind.TACTIC) is None
    assert ledger.deny_for(ArtifactKind.TACTIC) == ()
    assert ledger.raw() == {}


def test_malformed_ledger_is_a_config_error(tmp_path: Path) -> None:
    _ledger_file(tmp_path, "- a\n")
    with pytest.raises(ActiveCharterConfigError):
        load_activation_ledger(tmp_path)


# --------------------------------------------------------------------------- #
# Typed load, LEGACY sources (in the upgrade scope and unmigrated)
# --------------------------------------------------------------------------- #


def test_legacy_mapping_is_projected_and_never_trips_l1(tmp_path: Path) -> None:
    _write(tmp_path / ".kittify" / "config.yaml", f"charter: {_POINTER}\n")
    _write(
        tmp_path / _POINTER,
        "schema_version: '2.0.0'\ngovernance: {testing: {}}\ncatalog: {mission: software-dev}\nactivated_directives: [d1]\nmission_type_activations: [research]\n",
    )
    with legacy_activation_scope(tmp_path):
        ledger = load_activation_ledger(tmp_path)
    assert (ledger.source, ledger.path) == (ActivationSource.LEGACY, tmp_path / _POINTER)
    assert ledger.allow_for(ArtifactKind.DIRECTIVE) == ("d1",)
    assert ledger.raw() == {"mission_type_activations": ["research"], "activated_directives": ["d1"]}


def test_legacy_config_yaml_without_pointer(tmp_path: Path) -> None:
    _write(tmp_path / ".kittify" / "config.yaml", "agents: {}\nactivated_tactics: [t]\n")
    with legacy_activation_scope(tmp_path):
        ledger = load_activation_ledger(tmp_path)
    assert (ledger.source, ledger.path) == (ActivationSource.LEGACY, tmp_path / ".kittify" / "config.yaml")
    assert ledger.allow_for(ArtifactKind.TACTIC) == ("t",)


def test_legacy_loader_is_injectable(tmp_path: Path) -> None:
    _write(tmp_path / ".kittify" / "config.yaml", "activated_tactics: [t]\n")
    with legacy_activation_scope(tmp_path):
        ledger = load_activation_ledger(tmp_path, legacy_loader=lambda _root: {"activated_tactics": ["injected"], "agents": {}})
    assert ledger.allow_for(ArtifactKind.TACTIC) == ("injected",)


def test_legacy_non_list_value_is_still_refused(tmp_path: Path) -> None:
    _write(tmp_path / ".kittify" / "config.yaml", "activated_tactics: t\n")
    with legacy_activation_scope(tmp_path), _config_error_naming("must be a list"):
        load_activation_ledger(tmp_path)


def test_dangling_pointer_keeps_its_golden_text(tmp_path: Path) -> None:
    _write(tmp_path / ".kittify" / "config.yaml", "charter: .kittify/charter/missing.yaml\n")
    with legacy_activation_scope(tmp_path), pytest.raises(ActiveCharterConfigError) as excinfo:
        load_activation_ledger(tmp_path)
    missing = tmp_path / ".kittify/charter/missing.yaml"
    assert excinfo.value.body == (
        f".kittify/config.yaml 'charter:' pointer names {missing}, which does not exist.\n"
        "Remediation: fix .kittify/config.yaml (or the charter.yaml it points to) or run "
        "`spec-kitty upgrade` to restore the default active charter shape."
    )


def test_an_unmigrated_project_reads_its_legacy_allow_keys(tmp_path: Path) -> None:
    config = _write(tmp_path / ".kittify" / "config.yaml", "activated_tactics: [t]\nactivated_kinds: [tactics]\n")
    resolved = resolve_ledger_source(tmp_path)
    assert (resolved.source, resolved.unmigrated) == (ActivationSource.LEGACY, True)
    ledger = load_activation_ledger(tmp_path)
    assert (ledger.source, ledger.path, ledger.exists) == (ActivationSource.LEGACY, config, True)
    assert ledger.allow_for(ArtifactKind.TACTIC) == ("t",)
    assert ledger.activated_kinds == ("tactics",)


def test_a_legacy_deny_key_is_never_applied_and_warns_once(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Hole 6: the LEGACY projection drops ``deactivated_<kind>`` and reports it."""
    path = _write(tmp_path / ".kittify" / "config.yaml", "activated_tactics: [t]\ndeactivated_tactics: [t]\n")
    ledger = load_activation_ledger(tmp_path)
    load_activation_ledger(tmp_path)
    assert ledger.deny_for(ArtifactKind.TACTIC) == ()
    assert ledger.allow_for(ArtifactKind.TACTIC) == ("t",)
    reported = [line for line in capsys.readouterr().err.splitlines() if "deactivated_tactics" in line]
    assert len(reported) == 1, reported
    assert str(path) in reported[0]
    assert "not applied" in reported[0]


def test_a_legacy_deny_key_is_not_reported_on_a_data_read(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _write(tmp_path / ".kittify" / "config.yaml", "activated_tactics: [t]\ndeactivated_directives: [d]\n")
    ledger = load_activation_ledger(tmp_path, report_stray=False)
    assert ledger.deny_for(ArtifactKind.DIRECTIVE) == ()
    assert capsys.readouterr().err == ""


def test_report_legacy_deny_keys_nothing_to_report(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    report_legacy_deny_keys(tmp_path / "config.yaml", {"activated_tactics": ["t"], 7: "not a key"})
    assert capsys.readouterr().err == ""


def test_refuse_unmigrated_deny_write_names_keys_files_and_the_remedy(tmp_path: Path) -> None:
    config = _write(tmp_path / ".kittify" / "config.yaml", "activated_tactics: [t]\nactivated_kinds: [tactics]\n")
    with pytest.raises(ActiveCharterConfigError) as excinfo:
        refuse_unmigrated_deny_write(tmp_path)
    body = excinfo.value.body
    assert f"activated_kinds, activated_tactics in {config}" in body
    assert "spec-kitty upgrade" in body and "spec-kitty migrate activation-ledger" in body
    assert body.endswith("Nothing was written.")


@pytest.mark.parametrize("seed", ["ledger", "fresh", "scope"])
def test_refuse_unmigrated_deny_write_passes_a_migrated_fresh_or_in_scope_project(tmp_path: Path, seed: str) -> None:
    """Positive controls for the predicate: only an unmigrated project refuses."""
    if seed == "ledger":
        _write(tmp_path / ".kittify" / "config.yaml", "activated_tactics: [t]\n")
        _ledger_file(tmp_path, "activated_tactics: [t]\n")
    elif seed == "scope":
        _write(tmp_path / ".kittify" / "config.yaml", "activated_tactics: [t]\n")
    if seed == "scope":
        with legacy_activation_scope(tmp_path):
            refuse_unmigrated_deny_write(tmp_path)
    else:
        refuse_unmigrated_deny_write(tmp_path)


def test_unmigrated_positive_control_with_a_ledger(tmp_path: Path) -> None:
    """F15: the unmigrated fixture plus a ledger loads; the stray keys are data."""
    config = _write(tmp_path / ".kittify" / "config.yaml", "activated_tactics: [t]\n")
    _ledger_file(tmp_path, "activated_tactics: [from-ledger]\n")
    ledger = load_activation_ledger(tmp_path, report_stray=False)
    assert ledger.allow_for(ArtifactKind.TACTIC) == ("from-ledger",)
    assert ledger.stray_legacy_keys == ((config, ("activated_tactics",)),)


def test_report_stray_warns_once(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    stray = ((tmp_path / "config.yaml", ("activated_tactics",)),)
    report_stray_legacy_keys(stray)
    report_stray_legacy_keys(stray)
    lines = capsys.readouterr().err.splitlines()
    assert len(lines) == 1
    assert "activated_tactics" in lines[0]
    assert "activation ledger (activation.yaml) wins" in lines[0]


def test_report_stray_nothing_to_report(capsys: pytest.CaptureFixture[str]) -> None:
    report_stray_legacy_keys(())
    assert capsys.readouterr().err == ""


# --------------------------------------------------------------------------- #
# Write and the deny_change guard (FR-014, NFR-001)
# --------------------------------------------------------------------------- #


def _apply(root: Path, values: dict[str, object], *, deny_change: DenyListChoice | None = None) -> None:
    apply_yaml_write(prepare_ledger_write(root, values, deny_change=deny_change))


def test_deny_change_without_choice_is_refused_and_writes_nothing(tmp_path: Path) -> None:
    path = _ledger_file(tmp_path, "# keep me\nactivated_tactics: [t1]\n")
    before = path.read_bytes()
    with pytest.raises(DenyListWriteRefused) as excinfo:
        prepare_ledger_write(tmp_path, {"deactivated_tactics": ["t1"]})
    assert (excinfo.value.key, excinfo.value.added, excinfo.value.removed) == ("deactivated_tactics", ("t1",), ())
    assert isinstance(excinfo.value, ActiveCharterConfigError)
    assert path.read_bytes() == before


def test_deny_removal_without_choice_is_refused(tmp_path: Path) -> None:
    _ledger_file(tmp_path, "deactivated_tactics: [t1, t2]\n")
    with pytest.raises(DenyListWriteRefused) as excinfo:
        prepare_ledger_write(tmp_path, {}, remove=("deactivated_tactics",))
    assert excinfo.value.removed == ("t1", "t2")


def test_deny_change_with_choice_succeeds(tmp_path: Path) -> None:
    _ledger_file(tmp_path, "activated_tactics: [t1]\n")
    _apply(tmp_path, {"deactivated_tactics": ["t9", "t1", "t9"]}, deny_change=DenyListChoice.DEACTIVATE)
    assert read_activation_ledger(tmp_path) == {"activated_tactics": ["t1"], "deactivated_tactics": ["t1", "t9"]}


@pytest.mark.parametrize("existing", ["", "deactivated_tactics: []\n", "deactivated_tactics: null\n"])
@pytest.mark.parametrize("written", [[], None])
def test_absent_empty_and_null_compare_equal(tmp_path: Path, existing: str, written: list[str] | None) -> None:
    _ledger_file(tmp_path, existing + "activated_tactics: [t1]\n")
    _apply(tmp_path, {"deactivated_tactics": written, "activated_tactics": ["t2"]})
    assert read_activation_ledger(tmp_path) == {"activated_tactics": ["t2"]}


def test_empty_deny_list_is_removed_on_write(tmp_path: Path) -> None:
    _ledger_file(tmp_path, "deactivated_tactics: [t1]\nactivated_tactics: [t1]\n")
    _apply(tmp_path, {"deactivated_tactics": []}, deny_change=DenyListChoice.ACTIVATE)
    assert read_activation_ledger(tmp_path) == {"activated_tactics": ["t1"]}


def test_new_keys_are_appended_in_ledger_key_order(tmp_path: Path) -> None:
    _ledger_file(tmp_path, "activated_tactics: [t1]\n")
    _apply(
        tmp_path,
        {"deactivated_directives": ["D"], "activated_directives": ["A"], "activated_kinds": ["directives"]},
        deny_change=DenyListChoice.DEACTIVATE,
    )
    assert list(read_activation_ledger(tmp_path)) == ["activated_tactics", "activated_kinds", "activated_directives", "deactivated_directives"]


def test_comments_survive(tmp_path: Path) -> None:
    _ledger_file(tmp_path, "# header comment\nactivated_tactics: [t1]  # inline\n")
    _apply(tmp_path, {"activated_directives": ["A"]})
    text = (tmp_path / ACTIVATION_LEDGER).read_text(encoding="utf-8")
    assert "# header comment" in text
    assert "# inline" in text


def test_unknown_deny_key_passes_through_untouched(tmp_path: Path) -> None:
    _ledger_file(tmp_path, "deactivated_newkinds: [x, a]\n")
    _apply(tmp_path, {"activated_tactics": ["t"]})
    assert read_activation_ledger(tmp_path) == {"deactivated_newkinds": ["x", "a"], "activated_tactics": ["t"]}


def test_write_creates_the_file_and_parents(tmp_path: Path) -> None:
    _apply(tmp_path, {"mission_type_activations": ["software-dev"]})
    assert read_activation_ledger(tmp_path) == {"mission_type_activations": ["software-dev"]}


def test_write_refuses_an_invalid_existing_ledger(tmp_path: Path) -> None:
    path = _ledger_file(tmp_path, "bogus: 1\n")
    with _config_error_naming("bogus"):
        prepare_ledger_write(tmp_path, {"activated_tactics": ["t"]})
    assert path.read_text(encoding="utf-8") == "bogus: 1\n"


@pytest.mark.parametrize(
    ("values", "remove"),
    [({"bogus": ["x"]}, ()), ({}, ("bogus",)), ({"activated_tactics": ["t"]}, ("activated_tactics",))],
)
def test_write_rejects_unknown_or_overlapping_keys(tmp_path: Path, values: dict[str, object], remove: tuple[str, ...]) -> None:
    with pytest.raises(ValueError, match="(?i)activation ledger key"):
        prepare_ledger_write(tmp_path, values, remove=remove)


def test_deny_changes_pure_helper() -> None:
    before = {"deactivated_tactics": ["a", "b"], "deactivated_directives": None, "deactivated_newkinds": ["q"]}
    after = {"deactivated_tactics": ["b", "c"], "deactivated_skills": ["s"], "deactivated_directives": []}
    assert _deny_changes(before, after) == (
        ("deactivated_tactics", ("c",), ("a",)),
        ("deactivated_skills", ("s",), ()),
    )
    assert _deny_changes({"deactivated_tactics": []}, {}) == ()


# --------------------------------------------------------------------------- #
# Test factory
# --------------------------------------------------------------------------- #


def test_factory_seeds_and_reads_the_ledger(tmp_path: Path) -> None:
    path = seed_activation_ledger(tmp_path, activated_tactics=["t"], deactivated_directives=["D"])
    assert path == tmp_path / ACTIVATION_LEDGER
    assert read_activation_ledger(tmp_path) == {"activated_tactics": ["t"], "deactivated_directives": ["D"]}
    assert read_activation_ledger(tmp_path / "nowhere") == {}


@pytest.mark.parametrize(("surface", "rel"), [("charter_yaml", _POINTER), ("config_yaml", ".kittify/config.yaml")])
def test_factory_legacy_seed(tmp_path: Path, surface: str, rel: str) -> None:
    path = legacy_seed(tmp_path, surface=surface, activated_tactics=["t"])
    assert path == tmp_path / rel
    with legacy_activation_scope(tmp_path):
        ledger = load_activation_ledger(tmp_path)
    assert (ledger.source, ledger.allow_for(ArtifactKind.TACTIC)) == (ActivationSource.LEGACY, ("t",))


def test_factory_legacy_seed_rejects_an_unknown_surface(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="surface"):
        legacy_seed(tmp_path, surface="nowhere", activated_tactics=["t"])


# --------------------------------------------------------------------------- #
# Import direction (F20)
# --------------------------------------------------------------------------- #


def test_seam_does_not_import_pack_context_or_pack_manager() -> None:
    code = (
        "import sys\n"
        "import charter.activation.activation_ledger\n"
        "bad = [m for m in ('charter.activation.pack_context', 'charter.activation.pack_manager') if m in sys.modules]\n"
        "print(bad)\n"
        "raise SystemExit(1 if bad else 0)\n"
    )
    completed = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=60, check=False)
    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_error_home_moved_without_an_alias_copy() -> None:
    from charter.activation import pack_context

    assert pack_context.ActiveCharterConfigError is ActiveCharterConfigError


def test_yaml_written_is_plain_mapping(tmp_path: Path) -> None:
    _apply(tmp_path, {"activated_tactics": ["t"]})
    assert YAML(typ="safe").load((tmp_path / ACTIVATION_LEDGER).read_text(encoding="utf-8")) == {"activated_tactics": ["t"]}


# --------------------------------------------------------------------------- #
# Review cycle 1 regressions
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("seed", "values", "remove", "choice"),
    [
        ("deactivated_tactics: [t1]\n", {"deactivated_tactics": []}, (), DenyListChoice.ACTIVATE),
        ("activated_tactics: [t1]\n", {"activated_tactics": None}, (), None),
        ("activated_tactics: [t1]\n", {}, ("activated_tactics",), None),
    ],
)
def test_a_write_that_empties_the_ledger_leaves_an_empty_mapping(
    tmp_path: Path, seed: str, values: dict[str, object], remove: tuple[str, ...], choice: DenyListChoice | None
) -> None:
    """Issue 1: the deactivate-then-reactivate round trip on a fresh project empties the ledger."""
    _ledger_file(tmp_path, seed)
    apply_yaml_write(prepare_ledger_write(tmp_path, values, remove=remove, deny_change=choice))
    assert (tmp_path / ACTIVATION_LEDGER).read_text(encoding="utf-8") == "{}\n"
    ledger = load_activation_ledger(tmp_path)
    assert (ledger.source, ledger.exists, ledger.raw()) == (ActivationSource.LEDGER, True, {})


def test_deactivate_then_reactivate_round_trip_on_a_fresh_project(tmp_path: Path) -> None:
    apply_yaml_write(prepare_ledger_write(tmp_path, {"deactivated_tactics": ["t1"]}, deny_change=DenyListChoice.DEACTIVATE))
    apply_yaml_write(prepare_ledger_write(tmp_path, {"deactivated_tactics": []}, deny_change=DenyListChoice.ACTIVATE))
    assert load_activation_ledger(tmp_path).raw() == {}


@pytest.mark.parametrize(
    "values",
    [
        {"activated_tactics": "t2"},
        {"deactivated_tactics": "t2"},
        {"activated_tactics": [1]},
        {"deactivated_tactics": [["x"]]},
        {"mission_type_activations": {"a": 1}},
    ],
)
def test_written_values_are_checked_against_l2(tmp_path: Path, values: dict[str, object]) -> None:
    """Issue 2: a written value is a list of strings or ``None``; nothing is coerced or written."""
    path = _ledger_file(tmp_path, "deactivated_tactics: [t1]\nactivated_tactics: [t1]\n")
    before = path.read_bytes()
    with pytest.raises(ValueError, match="list of string ids"):
        prepare_ledger_write(tmp_path, values, deny_change=DenyListChoice.DEACTIVATE)
    assert path.read_bytes() == before


@pytest.mark.parametrize("text", ["a: [unclosed\n", "- a\n- b\n"])
def test_malformed_config_yaml_text_matches_pack_context(tmp_path: Path, text: str) -> None:
    """Issue 3: the seam keeps today's ``.kittify/config.yaml`` golden text, byte for byte."""
    from charter.activation import pack_context

    _write(tmp_path / ".kittify" / "config.yaml", text)
    with pytest.raises(ActiveCharterConfigError) as golden:
        pack_context._load_config(tmp_path)
    with pytest.raises(ActiveCharterConfigError) as seam:
        load_activation_ledger(tmp_path)
    assert seam.value.body == golden.value.body
    with legacy_activation_scope(tmp_path), pytest.raises(ActiveCharterConfigError) as scoped:
        load_activation_ledger(tmp_path)
    assert scoped.value.body == golden.value.body


def test_pointer_naming_a_directory_keeps_todays_text(tmp_path: Path) -> None:
    """Issue 3: pointer existence is ``exists()``, so a directory pointer is an invalid-YAML error as today."""
    from charter.activation import pack_context

    (tmp_path / ".kittify" / "charter" / "adir").mkdir(parents=True)
    _write(tmp_path / ".kittify" / "config.yaml", "charter: .kittify/charter/adir\n")
    # WP03: pack_context reads through the seam, so the legacy surface is read inside the upgrade scope here too.
    with legacy_activation_scope(tmp_path), pytest.raises(ActiveCharterConfigError) as golden:
        pack_context._load_charter_activation_source(tmp_path, pack_context._load_config(tmp_path))
    with legacy_activation_scope(tmp_path), pytest.raises(ActiveCharterConfigError) as seam:
        load_activation_ledger(tmp_path)
    assert seam.value.body == golden.value.body


def test_ledger_with_an_unknown_deny_key_is_hashable(tmp_path: Path) -> None:
    """Issue 4: data-model §1 says frozen and hashable; ``raw()`` still returns lists."""
    _ledger_file(tmp_path, "deactivated_newkinds: [x]\n")
    ledger = load_activation_ledger(tmp_path)
    assert hash(ledger) == hash(load_activation_ledger(tmp_path))
    assert ledger.raw() == {"deactivated_newkinds": ["x"]}


def test_unknown_deny_key_must_still_be_a_list_of_ids(tmp_path: Path) -> None:
    _ledger_file(tmp_path, "deactivated_newkinds: x\n")
    with _config_error_naming("deactivated_newkinds"):
        load_activation_ledger(tmp_path)


def test_a_report_is_a_plain_stderr_line_not_a_python_warning(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """F10: the report reaches the operator as ``Warning: ...`` on stderr, never a raw ``UserWarning`` with an internal path."""
    stray = ((tmp_path / "f10" / "config.yaml", ("activated_tactics",)),)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        report_stray_legacy_keys(stray)
    captured = capsys.readouterr()
    assert caught == []
    assert captured.out == ""
    assert captured.err.startswith("Warning: Legacy activation keys")
    assert "UserWarning" not in captured.err and "activation_ledger.py" not in captured.err
