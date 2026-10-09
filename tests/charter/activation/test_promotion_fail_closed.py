"""``promote_activations`` fails closed on an absent key (FR-015, US5 AS-1/AS-2, #4400).

Engine level, with a ``save`` spy: a resolved absent key is written once as a
superset of its effective set; an unresolved (or unsupplied) absent key is left
absent, ``save`` is never called for it, and the reason is reported; a present
key is appended to and its effective set is ignored.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from charter.activation.activation_engine import EffectiveSet, PromotionOutcome, promote_activations

pytestmark = pytest.mark.unit

_PATH = Path("config.yaml")
_KEY = "activated_procedures"


class _SaveSpy:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def __call__(self, path: Path, data: dict[str, Any]) -> None:
        assert path == _PATH
        self.calls.append({key: list(value) if isinstance(value, list) else value for key, value in data.items()})


def _promote(config: dict[str, Any], promotions: dict[str, list[str]], effective: dict[str, EffectiveSet]) -> tuple[PromotionOutcome, _SaveSpy]:
    save = _SaveSpy()
    outcome = promote_activations(promotions, config_path=_PATH, config_data=config, save=save, effective_sets=effective)
    return outcome, save


def test_resolved_absent_key_is_written_once_as_a_superset() -> None:
    effective = {_KEY: EffectiveSet(kind="procedure", yaml_key=_KEY, ids=frozenset({"b-proc", "a-proc"}))}
    config: dict[str, Any] = {}

    outcome, save = _promote(config, {_KEY: ["c-proc", "a-proc"]}, effective)

    assert len(save.calls) == 1
    assert config[_KEY] == ["a-proc", "b-proc", "c-proc"]  # sorted effective set, then the new id
    assert set(effective[_KEY].ids) <= set(config[_KEY])
    assert outcome.left_absent == {}
    assert outcome.committed[0].activated == ["c-proc"]
    assert any("Preserved 2 effective entries" in warning for warning in outcome.committed[0].warnings)


def test_unresolved_absent_key_is_left_absent_and_reported() -> None:
    effective = {_KEY: EffectiveSet(kind="procedure", yaml_key=_KEY, resolved=False, reason="declared org pack root /x is not a directory")}
    config: dict[str, Any] = {"activated_tactics": ["t1"]}

    outcome, save = _promote(config, {_KEY: ["c-proc"]}, effective)

    assert _KEY not in config
    assert save.calls == []
    assert outcome.committed == []
    assert outcome.left_absent == {_KEY: "declared org pack root /x is not a directory"}
    (message,) = outcome.left_absent_messages()
    assert _KEY in message and "/x is not a directory" in message


def test_absent_key_without_a_supplied_set_is_left_absent() -> None:
    config: dict[str, Any] = {}

    outcome, save = _promote(config, {_KEY: ["c-proc"]}, {})

    assert _KEY not in config
    assert save.calls == []
    assert _KEY in outcome.left_absent and outcome.left_absent[_KEY]


def test_unresolved_set_without_a_reason_still_reports_one() -> None:
    effective = {_KEY: EffectiveSet(kind="procedure", yaml_key=_KEY, resolved=False)}

    outcome, _save = _promote({}, {_KEY: ["c-proc"]}, effective)

    assert outcome.left_absent[_KEY]


def test_present_key_is_append_only_and_ignores_the_effective_set() -> None:
    effective = {_KEY: EffectiveSet(kind="procedure", yaml_key=_KEY, resolved=False, reason="unused")}
    config: dict[str, Any] = {_KEY: ["x-proc"]}

    outcome, save = _promote(config, {_KEY: ["c-proc"]}, effective)

    assert config[_KEY] == ["x-proc", "c-proc"]
    assert len(save.calls) == 1
    assert outcome.left_absent == {}


def test_mixed_keys_commit_only_the_resolvable_ones() -> None:
    other = "activated_tactics"
    effective = {
        _KEY: EffectiveSet(kind="procedure", yaml_key=_KEY, resolved=False, reason="broken"),
        other: EffectiveSet(kind="tactic", yaml_key=other, ids=frozenset({"t1"})),
    }
    config: dict[str, Any] = {}

    outcome, save = _promote(config, {_KEY: ["p"], other: ["t2"]}, effective)

    assert [plan.yaml_key for plan in outcome.committed] == [other]
    assert config == {other: ["t1", "t2"]}
    assert len(save.calls) == 1 and _KEY not in save.calls[0]
    assert set(outcome.left_absent) == {_KEY}


def test_org_charter_union_leaves_an_unresolvable_key_absent_and_reports_it(tmp_path: Path) -> None:
    """Caller level (org-charter union, US5 AS-2): a missing second org pack makes the set unresolvable."""
    from ruamel.yaml import YAML

    from charter.activation.org_charter import _promote_org_required_to_config, load_org_charter_policies

    pack = tmp_path / "org-packs" / "acme"
    pack.mkdir(parents=True)
    (pack / "org-charter.yaml").write_text('schema_version: "1"\norg_name: acme\nrequired_directives:\n  - DIRECTIVE_001\n', encoding="utf-8")
    config = tmp_path / ".kittify" / "config.yaml"
    config.parent.mkdir()
    packs = [{"name": "acme", "local_path": "org-packs/acme"}, {"name": "gone", "local_path": "org-packs/does-not-exist"}]
    with config.open("w", encoding="utf-8") as fh:
        YAML().dump({"charter_packs": {"org": {"packs": packs}}, "mission_type_activations": ["software-dev"]}, fh)

    messages = _promote_org_required_to_config(load_org_charter_policies(tmp_path), tmp_path)

    assert "activated_directives" not in YAML(typ="safe").load(config.read_text(encoding="utf-8"))
    assert any("activated_directives" in message and "does-not-exist" in message for message in messages), messages
