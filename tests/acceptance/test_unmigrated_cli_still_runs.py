"""An unmigrated project still runs through the real CLI (WP14, FR-017 amended, `mission_pivot_option_b`).

An *unmigrated* project carries legacy activation keys (in the ``charter.yaml``
the ``config.yaml`` ``charter:`` pointer names, and in ``config.yaml``) and has
no ``.kittify/charter/activation.yaml``. After the reduced flip every ordinary
command reads the legacy **allow** keys exactly as ``main`` does, allow-only
writes keep the legacy target, and every write that would record or change a
deny entry refuses, naming ``spec-kitty upgrade`` / ``spec-kitty migrate
activation-ledger``, with nothing written. No ledger is ever created
implicitly on such a project (hole 3).

Every case runs real subprocesses (full CLI startup). The ``charter context``
golden was captured on the Mission's ``main`` base (``f1663393``) for this exact
fixture (``tests/acceptance/fixtures/unmigrated_context_golden.json``).
"""

from __future__ import annotations

import json
import textwrap
from pathlib import Path
from typing import Any

import pytest
from ruamel.yaml import YAML

from charter.activation.activation_ledger import DENY_KEYS, LEDGER_KEYS
from charter.activation.schemas import CharterYaml
from kernel.activation_ledger_store import activation_ledger_path
from tests._support.activation_cli import cli, git, init_git_repo, snapshot, unwrapped

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_D = "024-locality-of-change"
_D_ID = "DIRECTIVE_024"
_X = "010-specification-fidelity-requirement"
_A = "001-architectural-integrity-standard"
_POINTER = ".kittify/charter/charter.yaml"
_CONFIG = ".kittify/config.yaml"
_GOLDEN = Path(__file__).parent / "fixtures" / "unmigrated_context_golden.json"
_REMEDY = "migrate activation-ledger"
_SAFE = YAML(typ="safe")

_CHARTER_YAML = textwrap.dedent(
    f"""\
    governance:
      charter:
        selected_directives: []
    directives:
      directives: []
    mission_type_activations:
    - software-dev
    activated_directives:
    - {_D}
    - {_X}
    """
)
_AGENTS = "agents:\n  available:\n  - claude\n"
_CONFIG_YAML = f"{_AGENTS}charter: {_POINTER}\nmission_type_activations:\n- software-dev\n"


def build_unmigrated_fixture(repo: Path, *, charter_yaml: str = _CHARTER_YAML, config_yaml: str = _CONFIG_YAML) -> Path:
    """The unmigrated fixture: legacy keys in the pointer ``charter.yaml`` and in ``config.yaml``, no ledger, one commit."""
    init_git_repo(repo)
    (repo / ".kittify" / "charter").mkdir(parents=True)
    (repo / _CONFIG).write_text(config_yaml, encoding="utf-8")
    if charter_yaml:
        (repo / _POINTER).write_text(charter_yaml, encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "unmigrated fixture")
    return repo


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    return build_unmigrated_fixture(tmp_path / "unmigrated")


def _load(path: Path) -> dict[str, Any]:
    return dict(_SAFE.load(path.read_text(encoding="utf-8")) or {})


def _ids(entries: Any) -> list[str]:
    return [entry["id"] if isinstance(entry, dict) else str(entry) for entry in entries or []]


def _no_deny_key_anywhere(repo: Path) -> None:
    for relative in (_CONFIG, _POINTER):
        path = repo / relative
        if path.is_file():
            assert set(_load(path)).isdisjoint(DENY_KEYS), f"{relative} carries a deny key"


def _ok(result: Any) -> None:
    assert result.returncode == 0, unwrapped(result)


# --------------------------------------------------------------------------- #
# Reads and diagnostics
# --------------------------------------------------------------------------- #


def test_version_exits_zero(repo: Path) -> None:
    _ok(cli(repo, "--version"))


def test_doctor_warns_unmigrated_and_is_otherwise_healthy(repo: Path) -> None:
    result = cli(repo, "doctor", "charter-packs", "--json")
    _ok(result)
    report = json.loads(result.stdout)["org_drg"]
    codes = {finding["code"] for finding in report["activation_ledger"]["warnings"]}
    assert "ACTIVATION_UNMIGRATED" in codes
    assert report["activation_ledger"]["errors"] == []
    assert report["errors"] == []


def test_migrate_ledger_lists_rc8_pending(repo: Path) -> None:
    result = cli(repo, "migrate", "ledger", "--json")
    _ok(result)
    steps = {step["id"]: step for step in json.loads(result.stdout)["steps"]}
    assert steps["4.0.0rc8_activation_ledger"]["state"] == "pending"


def test_charter_context_matches_main(repo: Path) -> None:
    result = cli(repo, "charter", "context", "--action", "implement", "--json", "--no-mark-loaded")
    _ok(result)
    payload = json.loads(result.stdout.replace(str(repo), "<ROOT>"))
    assert payload == json.loads(_GOLDEN.read_text(encoding="utf-8"))
    assert _D_ID in _ids(payload["all_directives"])  # positive control: the legacy allow list is read
    assert not activation_ledger_path(repo).exists()


def test_charter_yaml_with_all_ten_activation_fields_still_loads(repo: Path) -> None:
    """Hole 5: the ``CharterYaml`` activation fields stay (``extra="forbid"``)."""
    fields = [name for name in CharterYaml.model_fields if name.startswith("activated_") or name == "mission_type_activations"]
    assert len(fields) == 10
    document = _load(repo / _POINTER) | {name: [] for name in fields if name not in ("activated_directives", "mission_type_activations")}
    document["catalog"] = {"mission": "software-dev", "template_set": "software-dev-default"}
    (repo / _POINTER).write_text(json.dumps(document), encoding="utf-8")
    CharterYaml.model_validate(document)
    _ok(cli(repo, "charter", "context", "--action", "implement", "--json", "--no-mark-loaded"))


# --------------------------------------------------------------------------- #
# Allow-only writes keep the legacy target (holes 1 and 3)
# --------------------------------------------------------------------------- #


def test_activate_directive_writes_the_legacy_allow_list_only(repo: Path) -> None:
    _ok(cli(repo, "charter", "activate", "directive", _A, "--no-compile"))
    assert _A in _load(repo / _POINTER)["activated_directives"]
    assert not activation_ledger_path(repo).exists()
    _no_deny_key_anywhere(repo)


def test_preset_force_writes_no_deny_key(repo: Path) -> None:
    _ok(cli(repo, "charter", "activate", "--preset", "default", "--force", "--no-compile"))
    assert not activation_ledger_path(repo).exists()
    _no_deny_key_anywhere(repo)


def test_cascade_include_deactivated_activation_writes_no_deny_key(repo: Path) -> None:
    _ok(cli(repo, "charter", "activate", "mission-type", "software-dev", "--cascade", "all", "--include-deactivated", "--no-compile"))
    assert not activation_ledger_path(repo).exists()
    _no_deny_key_anywhere(repo)


def test_init_rerun_creates_no_ledger_and_rc8_stays_pending(repo: Path) -> None:
    before = snapshot(repo)
    _ok(cli(repo, "init", ".", "--ai", "claude"))
    assert not activation_ledger_path(repo).exists()
    assert {path: digest for path, digest in snapshot(repo).items() if path in before} == before
    steps = {step["id"]: step for step in json.loads(cli(repo, "migrate", "ledger", "--json").stdout)["steps"]}
    assert steps["4.0.0rc8_activation_ledger"]["state"] == "pending"


# --------------------------------------------------------------------------- #
# Deny writes refuse, all or nothing (hole 2, NFR-001)
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("cascade", [(), ("--cascade", "all")], ids=["direct", "cascade"])
def test_deactivate_refuses_and_writes_nothing(repo: Path, cascade: tuple[str, ...]) -> None:
    before = snapshot(repo)
    result = cli(repo, "charter", "deactivate", "directive", _D, *cascade, "--no-compile")
    assert result.returncode == 1, unwrapped(result)
    assert "spec-kitty upgrade" in unwrapped(result)
    assert _REMEDY in unwrapped(result)
    assert snapshot(repo) == before
    assert not activation_ledger_path(repo).exists()


def test_deactivate_refuses_unmigrated_before_the_floor_read(tmp_path: Path) -> None:
    config = _CONFIG_YAML + "charter_packs:\n  org:\n    packs:\n    - name: acme\n      local_path: org-packs/missing\n"
    repo = build_unmigrated_fixture(tmp_path / "unreadable-floor", config_yaml=config)
    before = snapshot(repo)
    result = cli(repo, "charter", "deactivate", "directive", _D, "--no-compile")
    assert result.returncode == 1, unwrapped(result)
    assert _REMEDY in unwrapped(result)
    assert "org-packs/missing" not in unwrapped(result), "the unmigrated refusal runs before the required-floor read"
    assert snapshot(repo) == before


def test_positive_control_after_the_move_deactivate_records_the_deny(repo: Path) -> None:
    _ok(cli(repo, "migrate", "activation-ledger"))
    _ok(cli(repo, "charter", "deactivate", "directive", _D, "--no-compile"))
    assert _D in _load(activation_ledger_path(repo))["deactivated_directives"]


# --------------------------------------------------------------------------- #
# The charter.yaml bootstrap copy (hole 4, C-003)
# --------------------------------------------------------------------------- #

_NO_POINTER_CONFIG = f"{_AGENTS}mission_type_activations:\n- software-dev\nactivated_directives:\n- {_D}\n"


def test_charter_generate_bootstrap_copies_the_legacy_allow_keys(tmp_path: Path) -> None:
    repo = build_unmigrated_fixture(tmp_path / "no-pointer", charter_yaml="", config_yaml=_NO_POINTER_CONFIG)
    _ok(cli(repo, "charter", "generate", "--no-from-interview"))
    charter = _load(repo / _POINTER)
    assert charter["activated_directives"] == [_D]
    assert set(charter).isdisjoint(DENY_KEYS)
    assert not activation_ledger_path(repo).exists()


def test_charter_generate_after_the_move_copies_no_activation_key(tmp_path: Path) -> None:
    repo = build_unmigrated_fixture(tmp_path / "moved", charter_yaml="", config_yaml=_NO_POINTER_CONFIG)
    _ok(cli(repo, "migrate", "activation-ledger"))
    assert activation_ledger_path(repo).is_file()
    (repo / _CONFIG).write_text(_NO_POINTER_CONFIG, encoding="utf-8")  # a stray copy beside the ledger
    _ok(cli(repo, "charter", "generate", "--no-from-interview"))
    assert set(_load(repo / _POINTER)).isdisjoint(LEDGER_KEYS)


# --------------------------------------------------------------------------- #
# A legacy deny key is never applied (hole 6)
# --------------------------------------------------------------------------- #


def test_a_legacy_deny_key_is_never_applied_and_blocks_the_move(tmp_path: Path) -> None:
    repo = build_unmigrated_fixture(tmp_path / "legacy-deny", charter_yaml=_CHARTER_YAML + f"deactivated_directives:\n- {_D}\n")
    result = cli(repo, "charter", "context", "--action", "implement", "--json", "--no-mark-loaded")
    _ok(result)
    assert _D_ID in _ids(json.loads(result.stdout)["all_directives"]), "a legacy deactivated_<kind> key is never applied"
    text = cli(repo, "charter", "context", "--action", "implement", "--no-mark-loaded")  # warnings are silent in --json mode
    _ok(text)
    assert text.stderr.count("deactivated_directives") == 1, text.stderr
    assert "not applied" in unwrapped(text)
    moved = cli(repo, "migrate", "activation-ledger")
    assert moved.returncode != 0, unwrapped(moved)
    assert "deactivated_directives" in unwrapped(moved)
    assert not activation_ledger_path(repo).exists()
