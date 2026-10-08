"""Red-first tests for the dispatch action/role verb -> catalog task_type
bridge (FR-002).

Covers:
- a known canonical verb resolves to a task_type
- an unknown verb resolves to None (advisory, non-fatal)
- the map stays in sync with ``DEFAULT_ROLE_CAPABILITIES`` canonical
  verbs (every verb declared there MUST have an entry -- this is the
  "live maintenance seam" tripwire called out in the WP01 prompt)
- every mapped task_type is a schema-legal ``task_type`` id
  (``TASK_TYPE_PATTERN``), so the map stays compatible with the catalog
  vocabulary it bridges to.
"""

from __future__ import annotations

import re

import pytest

from charter.offering.agent_profiles.capabilities import DEFAULT_ROLE_CAPABILITIES
from charter.offering.model_task_routing.models import TASK_TYPE_PATTERN

pytestmark = [pytest.mark.doctrine, pytest.mark.fast]


def _all_canonical_verbs() -> set[str]:
    verbs: set[str] = set()
    for capabilities in DEFAULT_ROLE_CAPABILITIES.values():
        verbs.update(capabilities.canonical_verbs)
    return verbs


def test_known_verb_maps_to_a_task_type() -> None:
    from specify_cli.invocation.task_class_map import task_type_for_verb

    assert task_type_for_verb("implement") is not None
    assert isinstance(task_type_for_verb("implement"), str)


def test_unknown_verb_maps_to_none() -> None:
    from specify_cli.invocation.task_class_map import task_type_for_verb

    assert task_type_for_verb("teleport") is None
    assert task_type_for_verb("") is None


@pytest.mark.parametrize("verb", sorted(_all_canonical_verbs()))
def test_map_covers_every_canonical_verb(verb: str) -> None:
    """Live maintenance seam: adding a role/verb to capabilities.py without
    updating task_class_map.py must fail this test."""
    from specify_cli.invocation.task_class_map import task_type_for_verb

    assert task_type_for_verb(verb) is not None, (
        f"canonical verb {verb!r} from DEFAULT_ROLE_CAPABILITIES has no "
        "task_class_map entry"
    )


def test_known_verbs_returns_exactly_the_maintained_namespace() -> None:
    from specify_cli.invocation.task_class_map import known_verbs

    assert _all_canonical_verbs().issubset(known_verbs())


def test_every_mapped_task_type_is_schema_legal() -> None:
    """The map's values must be legal catalog task_type ids so the
    bridge stays compatible with the vocabulary it targets."""
    from specify_cli.invocation.task_class_map import known_verbs, task_type_for_verb

    pattern = re.compile(TASK_TYPE_PATTERN)
    for verb in known_verbs():
        task_type = task_type_for_verb(verb)
        assert task_type is not None
        assert pattern.match(task_type), f"{task_type!r} for verb {verb!r} is not schema-legal"
