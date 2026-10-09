"""``charter status`` must not hand out a clean bill for an incomplete graph.

WP08 re-review fold. The first fold wired
:func:`charter.offering.drg.validate_dangling_references` into ONE of the callers that
merges the real built-in layer against the operator's real configured packs
(``doctor charter-packs``'s JSON collector) and justified stopping there by calling
that caller "the one place that holds a graph it can call complete".

That was factually wrong. :func:`_collect_org_layer_status` builds its merged
graph from byte-identical inputs — ``load_built_in_graph()`` against
``load_org_drg(repo_root)`` — so it holds exactly the same complete graph. It
already ships an ``errors`` array built for precisely this kind of finding, and
before this fold it returned ``"errors": []`` for a pack whose edge endpoint
binds to nothing: a machine-readable clean bill for a graph that is not clean.
That is this mission's own defect class one layer up.

The rule that actually governs the check (now stated on
:func:`charter.offering.drg.validator.validate_dangling_references`) is a predicate on
the *merge*, not a uniqueness claim about one call site: **a caller may escalate
a dangling endpoint to an error exactly when it merged the complete graph.**
``charter lint`` is the one caller that must NOT (it merges against a
deliberately EMPTY built-in, so the check genuinely cannot run there).

These tests mirror ``test_doctor_charter_packs_org_layer`` ::

    test_collect_org_layer_data_reports_a_dangling_org_endpoint
    test_collect_org_layer_data_reports_no_dangling_endpoint_when_clean

including the clean discriminator — a gate that flags everything is worthless.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from textwrap import dedent

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_REPO_ROOT: Path = Path(__file__).resolve().parents[5]
_FIXTURE_ORG_PACK: Path = (
    _REPO_ROOT
    / "tests"
    / "architectural"
    / "_fixtures"
    / "org_packs"
    / "example_org"
)


@pytest.fixture
def tmp_repo_with_org_pack(tmp_path: Path) -> Path:
    """Minimal repo with the example_org fixture pack configured (WP06 format)."""
    pack_dest = tmp_path / "example_org"
    shutil.copytree(_FIXTURE_ORG_PACK, pack_dest)
    kittify = tmp_path / ".kittify"
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
        )
    )
    return tmp_path


def test_collect_org_layer_status_reports_a_dangling_org_endpoint(
    tmp_repo_with_org_pack: Path,
) -> None:
    """A qualified endpoint that binds to nothing reaches ``org_layer['errors']``.

    RED before this fold: ``errors == []`` while ``doctor charter-packs --json``
    reported the very same finding from the very same merge inputs.
    """
    from specify_cli.cli.commands.charter import _collect_org_layer_status

    fragment = tmp_repo_with_org_pack / "example_org" / "drg" / "fragment.yaml"
    fragment.write_text(
        fragment.read_text(encoding="utf-8").replace(
            "styleguide:plain-language", "styleguide:plain-languagee"
        ),
        encoding="utf-8",
    )

    result = _collect_org_layer_status(tmp_repo_with_org_pack)

    errors = result["errors"]
    assert isinstance(errors, list)
    assert any("styleguide:plain-languagee" in e for e in errors), (
        "charter status must name the offending token in its structured "
        f"errors channel — the one machine-readable signal it has; got {errors}"
    )


def test_collect_org_layer_status_reports_no_dangling_endpoint_when_clean(
    tmp_repo_with_org_pack: Path,
) -> None:
    """The escalation must discriminate, not fire on every pack.

    The shipped fixture references a real built-in node by qualified URN — the
    sanctioned cross-fragment authoring shape — so an unmodified pack must come
    back clean. Without this, the test above would pass on a check that flagged
    everything.
    """
    from specify_cli.cli.commands.charter import _collect_org_layer_status

    result = _collect_org_layer_status(tmp_repo_with_org_pack)

    assert result["errors"] == [], result


def test_collect_org_layer_status_surfaces_a_failed_merge_check(
    tmp_repo_with_org_pack: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A merge check that could not RUN is not a merge check that PASSED.

    The handler this pins was a bare ``except Exception: pass`` — the empty
    handler the charter's Sonar section forbids — sitting on the exact merge
    whose result now decides whether the org layer is reported clean. Swallowed,
    it turns "the completeness check crashed" into "no findings", which is the
    same false-clean one level further down.
    """
    import charter.activation.drg_activation as drg_activation
    from specify_cli.cli.commands.charter import _collect_org_layer_status

    def _boom(**_kwargs: object) -> object:
        raise RuntimeError("merge exploded")

    # ``_collect_org_layer_status`` imports ``merge_three_layers`` from
    # ``charter.activation.drg_activation`` (its re-export site), not from the
    # ``charter.drg`` facade — patch the module production actually calls.
    monkeypatch.setattr(drg_activation, "merge_three_layers", _boom)

    result = _collect_org_layer_status(tmp_repo_with_org_pack)

    errors = result["errors"]
    assert isinstance(errors, list)
    assert any("merge exploded" in e for e in errors), (
        f"the operator must learn the check did not run; got {errors}"
    )
