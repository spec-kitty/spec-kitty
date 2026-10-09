"""Contract test: task_class_map's task_type vocabulary vs. the shipped catalog.

``task_class_map.py`` maps every canonical dispatch verb to a
``model-to-task_type`` catalog ``task_type`` id (FR-002). Nothing enforces
that the shipped catalog (``model-to-task_type.yaml``) actually carries
``task_fit`` coverage for every task_type the map can emit -- a verb whose
task_type has zero model ``task_fit`` entries silently degrades every
recommendation for that verb to ``None`` via ``_compute_recommendation``'s
non-fatal envelope (``recommendation.candidates`` empty ->
``executor._compute_recommendation`` returns ``None``), with no test
failure anywhere to say so.

This is the exact gap the aggregate review found (21 map task_types, 5
catalog task_types, only ``code-review`` overlapping) before Fix 2 expanded
the catalog. This test is the standing guard against that vocabulary drift
recurring: it must stay GREEN after Fix 2, and must fail loudly the moment
a new verb/task_type is added to ``task_class_map`` without matching
catalog coverage.
"""

from __future__ import annotations

import pytest

from charter.offering.model_task_routing.loader import default_catalog_path, load
from specify_cli.invocation.task_class_map import known_verbs, task_type_for_verb

pytestmark = [pytest.mark.doctrine, pytest.mark.fast]


def _shipped_catalog_covered_task_types() -> set[str]:
    """The set of task_type ids the shipped catalog can actually route.

    Derived from the union of every model's ``task_fit`` entries (the
    evaluator only ever matches a candidate against ``model.task_fit``,
    never the declarative ``task_types`` metadata list) plus any
    ``tier_constraints`` task_type ids the routing policy declares. The
    ``task_types`` list itself is catalog documentation and is not
    schema-enforced to match ``task_fit`` coverage, so it is deliberately
    NOT used as the source of truth here.
    """
    result = load(catalog_path=default_catalog_path())
    assert result is not None, "shipped model-to-task_type.yaml failed to load"
    catalog = result.catalog

    covered: set[str] = set()
    for model in catalog.models:
        covered.update(fit.task_type for fit in model.task_fit)
    covered.update(tc.task_type for tc in catalog.routing_policy.tier_constraints)
    return covered


def test_task_class_map_task_types_are_subset_of_shipped_catalog() -> None:
    """Every task_type task_class_map can emit must be catalog-covered.

    Fails with the exact missing task_type ids so a future drift is
    immediately actionable -- add task_fit entries for the listed
    task_types (mirroring the tier-grouping pattern in
    ``model-to-task_type.yaml``) or remove the offending verb mapping.
    """
    map_task_types = {task_type_for_verb(verb) for verb in known_verbs()} - {None}
    catalog_task_types = _shipped_catalog_covered_task_types()

    missing = map_task_types - catalog_task_types
    assert not missing, (
        "task_class_map emits task_type(s) with no shipped catalog "
        f"task_fit coverage: {sorted(missing)}. Add task_fit entries for "
        "these task_types to "
        "src/charter/offering/model_task_routing/catalog/model-to-task_type.yaml, "
        "or remove the verb mapping from task_class_map.py."
    )
