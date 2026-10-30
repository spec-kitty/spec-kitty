"""Runner of the pack-containment conformance table (#6733).

``pack_containment_cases.yaml`` is the corpus: plain data that states one rule — *a path an org
pack declares must stay inside its own pack* — and what each reporting surface must answer for a
given pack shape. This runner scaffolds each case's pack with the canonical ``charter org init``
(so the only faults are the ones the case declares), installs the case's paths, and asserts the
case's ``expect`` against the three production entry points:

* ``doctor`` — :func:`specify_cli.cli.commands.doctor._collect_org_layer_data` (the real collector
  behind ``spec-kitty doctor charter-packs --json``);
* ``status`` — :func:`specify_cli.cli.commands.charter._collect_org_layer_status`;
* ``validate`` — the ``spec-kitty charter org validate`` CLI (rendering + exit code).

Why the table exists: #6418 taught the doctor to report an escaping fragment ``body_path`` and
asset sidecar ``path``; #6733 found ``charter status`` silent on both and ``charter org validate``
silent on the fragment half. A rule that lives only in three command implementations drifts again;
a rule stated as data can be run against the spec-kitty-charter replacement. Revert either fix and
the corresponding surface's assertions go red.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from pathlib import Path
from textwrap import dedent
from typing import Any

import pytest
import yaml
from typer.testing import CliRunner

from specify_cli.cli.commands.charter import charter_app

pytestmark = [pytest.mark.fast]

CASES_FILE = Path(__file__).with_name("pack_containment_cases.yaml")
SCHEMA = "pack-containment-conformance/1"

_NODE_ID = "team-asset"
_ASSET_ID = "team-logo"

runner = CliRunner()


def load_cases() -> dict[str, Any]:
    """The conformance table, parsed (plain YAML)."""
    loaded: dict[str, Any] = yaml.safe_load(CASES_FILE.read_text(encoding="utf-8"))
    assert loaded["schema"] == SCHEMA, f"unexpected corpus schema: {loaded['schema']!r}"
    return loaded


CASES = load_cases()


def _rows() -> list[Any]:
    return [pytest.param(case, id=case["id"]) for case in CASES["cases"]]


# ---------------------------------------------------------------------------
# The pack shape under test
# ---------------------------------------------------------------------------


def _build_project(root: Path, pack: Mapping[str, str]) -> Path:
    """Scaffold one org pack in *root*, configure it, and install the case's declared paths."""
    pack_dest = root / "example_org"
    init_result = runner.invoke(charter_app, ["org", "init", str(pack_dest)])
    assert init_result.exit_code == 0, init_result.output
    kittify = root / ".kittify"
    kittify.mkdir()
    (kittify / "config.yaml").write_text(
        dedent(
            f"""\
            charter_packs:
              org:
                packs:
                  - name: example-org
                    local_path: {pack_dest}
            """
        ),
        encoding="utf-8",
    )
    if "node_body_path" in pack:
        _add_node(pack_dest, pack["node_body_path"])
    if "asset_path" in pack:
        _add_asset(pack_dest, pack["asset_path"])
    return root


def _add_node(pack_dir: Path, body_path: str) -> None:
    fragment = pack_dir / "drg" / "fragment.yaml"
    data = yaml.safe_load(fragment.read_text(encoding="utf-8"))
    data["nodes"] = [
        *(data.get("nodes") or []),
        {"id": _NODE_ID, "kind": "assets", "title": "Team asset", "body_path": body_path},
    ]
    fragment.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def _add_asset(pack_dir: Path, asset_path: str) -> None:
    assets = pack_dir / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    (assets / f"{_ASSET_ID}.asset.yaml").write_text(yaml.safe_dump({"id": _ASSET_ID, "mime": "text/plain", "path": asset_path}), encoding="utf-8")


# ---------------------------------------------------------------------------
# Adapters, one per reporting surface
# ---------------------------------------------------------------------------


def observe_doctor(repo: Path, pack_dir: Path) -> dict[str, Any]:
    """``doctor charter-packs``: the two escape lists and the verdict channel."""
    from specify_cli.cli.commands.doctor import _collect_org_layer_data

    org_drg = _collect_org_layer_data(repo)
    codes = [escape["code"] for key in ("body_path_escapes", "asset_path_escapes") for escape in org_drg[key]]
    errors = list(org_drg["errors"])
    return {"codes": sorted(codes), "names": _names_in(errors), "errors": len(errors)}


def observe_status(repo: Path, pack_dir: Path) -> dict[str, Any]:
    """``charter status``: the org layer's single ``errors`` channel."""
    from specify_cli.cli.commands.charter import _collect_org_layer_status

    errors = list(_collect_org_layer_status(repo)["errors"])
    return {"errors": len(errors), "names": _names_in(errors)}


def observe_validate(repo: Path, pack_dir: Path) -> dict[str, Any]:
    """``charter org validate``: exit code and rendered finding categories."""
    result = runner.invoke(charter_app, ["org", "validate", str(pack_dir)])
    categories = sorted(_categories_in(result.output))
    return {"ok": result.exit_code == 0, "categories": categories}


_ADAPTERS: Mapping[str, Callable[[Path, Path], dict[str, Any]]] = {
    "doctor": observe_doctor,
    "status": observe_status,
    "validate": observe_validate,
}


def _names_in(errors: list[str]) -> list[str]:
    """The finding names this corpus knows, sorted, present in *errors* (stable comparison)."""
    return sorted(name for name in (_ASSET_ID, _NODE_ID) if any(name in error for error in errors))


def _categories_in(output: str) -> set[str]:
    """The ``(category)`` tokens the validator renderer prints, for a stable comparison."""
    known = {"body_path_escape", "asset_path_escape"}
    return {token for token in known if f"({token})" in output}


def assert_expected(case: Mapping[str, Any], surface: str, observed: Mapping[str, Any]) -> None:
    """Exactly the case's ``expect[surface]``; an expect key the adapter did not observe fails."""
    expect: Mapping[str, Any] = case["expect"][surface]
    unknown = sorted(set(expect) - set(observed))
    assert not unknown, f"{case['id']}/{surface}: expect keys this adapter does not observe: {unknown}"
    assert {key: observed[key] for key in expect} == dict(expect), f"{case['id']}/{surface}"


# ---------------------------------------------------------------------------
# The three surfaces, per case
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("case", _rows())
@pytest.mark.parametrize("surface", sorted(_ADAPTERS))
def test_surfaces_agree_on_the_pack_shape(case: Mapping[str, Any], surface: str, tmp_path: Path) -> None:
    """One case, one surface: the table is the convergence claim, so every cell is asserted."""
    repo = _build_project(tmp_path, case["pack"])

    observed = _ADAPTERS[surface](repo, repo / "example_org")

    assert_expected(case, surface, observed)


@pytest.mark.parametrize("case", _rows())
def test_every_case_names_all_three_surfaces(case: Mapping[str, Any]) -> None:
    """A case that forgot a surface would silently weaken the convergence claim."""
    assert set(case["expect"]) == set(_ADAPTERS), case["id"]


def test_doctor_json_is_still_the_documented_shape(tmp_path: Path) -> None:
    """Guard the premise the doctor adapter reads: two always-present lists and an errors list."""
    from specify_cli.cli.commands.doctor import _collect_org_layer_data

    repo = _build_project(tmp_path, CASES["cases"][0]["pack"])
    payload = _collect_org_layer_data(repo)
    dump = json.dumps(payload)

    for key in ("body_path_escapes", "asset_path_escapes", "errors"):
        assert key in payload, f"doctor charter-packs --json lost {key}: {dump[:400]}"
