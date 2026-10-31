"""The cascade resolves every target's config stem in one pass, before the first write (#6777).

`_activate_cascade_targets` maps each cascade target's DRG URN to its config-stem ID and
then activates it. Before #6777 each target resolved its own URN with a *fresh*
`ResolutionPass`, so a full `--cascade all` walk (114 targets) re-walked and re-parsed the
whole doctrine catalog 121 times (114 activations plus seven render-only lookups): 5309 id
reads, 5028 artifact-file parses, ~30 s of a ~80 s run. `ResolutionPass` exists precisely to share those reads across one read-only
pass; #5526 gave the pass to the cascade *render* loops, and the activation loop was
missed because `_cascade_activation_report` created its pass after the loop.

The ordering half is the same contract from the other side: `ResolutionPass`'s docstring
requires that a pass never span a write to the files it reads, so the whole lookup batch
must complete before the first `manager.activate()` call.

Positive control (same fixture, `acceptance-criteria-non-vacuity`): every test here asserts
it *observed* one resolution per target before it says anything about the pass they share,
so a probe that sees nothing fails loudly instead of passing. The production path's own
end-to-end proof stays where it was — `test_stored_spelling_6527.py::
test_writer_stores_stems_only[cascade]` drives the real `charter activate --cascade all`
CLI and asserts the stored lists — so this helper-level guard cannot go green while the
wiring that calls it is missing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from charter.activation.kind_vocabulary import ResolutionPass
from specify_cli.cli.commands.charter import activate as activate_module
from specify_cli.cli.commands.charter.activate import _CascadeIds, _activate_cascade_targets

#: A cascade walk with more than one kind and more than one target per kind, in the shape
#: the DRG walk hands over (``{kind: [bare DRG id, ...]}``).
ACTIVATED = {
    "directive": ["DIRECTIVE_001"],
    "tactic": ["acceptance-test-first", "model-task-routing"],
    "styleguide": ["python-testing"],
}
TARGETS = sum(len(ids) for ids in ACTIVATED.values())


@dataclass
class _Probe:
    """What the run did, in order: resolutions and activations interleaved as they happened."""

    order: list[str] = field(default_factory=list)
    lookups: list[tuple[str, ResolutionPass | None]] = field(default_factory=list)


class _RecordingManager:
    """Stand-in for ``ActiveCharterManager``: records the call order, activates nothing."""

    def __init__(self, probe: _Probe) -> None:
        self.probe = probe

    def activate(self, ctx: object, kind: str, artifact_id: str, **kwargs: Any) -> None:
        self.probe.order.append(f"activate:{kind}:{artifact_id}")


@pytest.fixture
def probe(monkeypatch: pytest.MonkeyPatch) -> _Probe:
    """A run whose ``config_id`` resolutions and activations are both recorded, in order."""
    recorded = _Probe()

    def _resolve(urn: str, offering_root: Path, layer_roots: object, org_roots: object, resolution_pass: ResolutionPass | None = None) -> str:
        recorded.order.append(f"resolve:{urn}")
        recorded.lookups.append((urn, resolution_pass))
        return urn.partition(":")[2]

    monkeypatch.setattr(activate_module, "drg_urn_to_config_id", _resolve)
    return recorded


def _run_cascade(probe: _Probe) -> list[object]:
    ids = _CascadeIds(Path("/nonexistent-offering"), None, [])
    return _activate_cascade_targets(_RecordingManager(probe), object(), ACTIVATED, ids, reinstate=False)  # type: ignore[arg-type]


def test_every_cascade_target_resolves_through_the_same_resolution_pass(probe: _Probe) -> None:
    entries = _run_cascade(probe)

    # Positive control: the probe observed one resolution per target (not zero), and the
    # activations it stands in for really ran.
    assert len(entries) == TARGETS
    assert len(probe.lookups) == TARGETS, f"the cascade resolved {len(probe.lookups)} of {TARGETS} targets"
    passes = [resolution_pass for _urn, resolution_pass in probe.lookups]
    assert passes[0] is not None, "the cascade resolved its targets with no resolution pass, re-reading the catalog per target"
    assert len({id(item) for item in passes}) == 1, (
        f"{len({id(item) for item in passes})} resolution passes for {TARGETS} targets: the catalog is re-read once per target"
    )


def test_the_whole_lookup_batch_precedes_the_first_activation_write(probe: _Probe) -> None:
    entries = _run_cascade(probe)

    # Positive control: both kinds of event were observed, so the order means something.
    assert len(entries) == TARGETS
    assert [item for item in probe.order if item.startswith("resolve:")]
    writes = [index for index, item in enumerate(probe.order) if item.startswith("activate:")]
    assert writes, f"no activation was recorded: {probe.order}"
    assert all(item.startswith("activate:") for item in probe.order[writes[0] :]), f"a resolution ran after the first activation write: {probe.order}"
