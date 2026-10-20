"""Unit tests for ``doctor charter-packs`` org-layer section (WP07 / FR-007).

Verifies:
- ``_render_org_layer_section`` prints pack name + node/edge counts for fetched packs.
- ``_render_org_layer_section`` handles OrgPackMissingError gracefully (no crash).
- ``_collect_org_layer_data`` returns structured dict for JSON output.
- ``doctor charter-packs`` command includes ``org_drg`` key in ``--json`` output
  when org packs are configured.
- ``doctor charter-packs`` does not crash when no org packs are configured.

Per WP07: diagnostic commands are READ-ONLY and must never crash on operator
misconfiguration. All exception paths must produce a usable (non-crashing)
diagnostic output.
"""

from __future__ import annotations

import json
import shutil
from io import StringIO
from pathlib import Path
from textwrap import dedent
from unittest.mock import patch

import pytest
from rich.console import Console
from typer.testing import CliRunner

from charter.offering.drg.models import DRGGraph, DRGNode, NodeKind

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_REPO_ROOT: Path = Path(__file__).resolve().parents[4]
_FIXTURE_ORG_PACK: Path = (
    _REPO_ROOT
    / "tests"
    / "architectural"
    / "_fixtures"
    / "org_packs"
    / "example_org"
)

runner = CliRunner()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_repo_with_org_pack(tmp_path: Path) -> Path:
    """Minimal repo with the example_org fixture pack configured (WP06 loader format)."""
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


@pytest.fixture
def tmp_repo_without_org_pack(tmp_path: Path) -> Path:
    """Minimal repo with no org packs configured."""
    kittify = tmp_path / ".kittify"
    kittify.mkdir()
    (kittify / "config.yaml").write_text(
        dedent(
            """\
            agents:
              available:
                - claude
            """
        )
    )
    return tmp_path


# ---------------------------------------------------------------------------
# _render_org_layer_section tests
# ---------------------------------------------------------------------------


def test_render_org_layer_section_shows_pack_counts(
    tmp_repo_with_org_pack: Path,
) -> None:
    """When org pack is configured and fetched, section shows pack name and counts."""
    from specify_cli.cli.commands.doctor import _render_org_layer_section

    buf = StringIO()
    console = Console(file=buf, highlight=False, markup=False)
    _render_org_layer_section(tmp_repo_with_org_pack, console)
    output = buf.getvalue()

    assert "example-org" in output, (
        f"pack name 'example-org' must appear in output: {output!r}"
    )
    # Must show node/edge counts
    assert "nodes" in output or "edges" in output, (
        f"output must show node/edge counts: {output!r}"
    )


def test_render_org_layer_section_names_a_dangling_org_endpoint(
    tmp_repo_with_org_pack: Path,
) -> None:
    """The human section must name the finding, on its own verdict line.

    ``_collect_org_layer_data`` declares itself a mirror of *this* function
    ("Mirrors the human-readable output of ``_render_org_layer_section``"). The
    first WP08 fold wired the completeness check into the JSON collector only,
    so the mirror broke: ``doctor charter-packs --json`` reported the dangling
    endpoint under ``org_drg.errors`` while the same command's human output
    showed the pack ``✓ loaded``, a ``collisions: none`` line, and nothing at
    all about the endpoint — a clean-looking section for the exact graph the
    JSON call had just failed.

    RED before this fold: the offending token appears nowhere in the rendered
    section.
    """
    from specify_cli.cli.commands.doctor import _render_org_layer_section

    fragment = tmp_repo_with_org_pack / "example_org" / "drg" / "fragment.yaml"
    fragment.write_text(
        fragment.read_text(encoding="utf-8").replace(
            "styleguide:plain-language", "styleguide:plain-languagee"
        ),
        encoding="utf-8",
    )

    buf = StringIO()
    console = Console(file=buf, highlight=False, markup=False, width=200)
    _render_org_layer_section(tmp_repo_with_org_pack, console)
    output = buf.getvalue()

    assert "styleguide:plain-languagee" in output, (
        f"the section must name the offending token; got {output!r}"
    )
    # ``markup=False`` on the test console keeps rich tags literal, so match the
    # verdict label and its count separately rather than across the ``[/red]``.
    assert "dangling endpoints:" in output, (
        "the token must be presented as a finding with its own verdict line, "
        f"not buried in prose; got {output!r}"
    )
    assert "1 org edge endpoint(s)" in output, output
    # ``collisions: none`` stays — and stays true. Collisions and dangling
    # endpoints are two checks; suppressing one verdict because the other
    # failed would lose the answer to a question the operator also asked.
    assert "collisions: none" in output, output


def test_render_org_layer_section_reports_clean_when_no_dangling_endpoint(
    tmp_repo_with_org_pack: Path,
) -> None:
    """The escalation must discriminate, not fire on every pack.

    Clean-discriminator for the test above: the shipped fixture references a
    real built-in node by qualified URN — the sanctioned cross-fragment
    authoring shape — so an unmodified pack renders an explicitly clean verdict
    and names no token. Without this, the test above would pass on a renderer
    that flagged everything.
    """
    from specify_cli.cli.commands.doctor import _render_org_layer_section

    buf = StringIO()
    console = Console(file=buf, highlight=False, markup=False, width=200)
    _render_org_layer_section(tmp_repo_with_org_pack, console)
    output = buf.getvalue()

    assert "collisions: none" in output, output
    assert "dangling endpoints: none" in output, output
    assert "plain-language" not in output, output


# ---------------------------------------------------------------------------
# ``collisions:`` verdict line vs. permitted org overrides of built-ins (#5777)
#
# ``merge_three_layers`` does not raise for a same-kind org override of a
# built-in node: the org node takes the built-in's place and the merged node is
# tagged ``org:<pack>``. The human section used to print ``collisions: none``
# after EVERY merge that did not raise, so it contradicted the "Sanctioned /
# Unsanctioned built-in override(s)" blocks printed further down the report.
#
# The merge and the built-in graph are stubbed (test doubles) so each case
# controls exactly which built-in nodes an org pack replaced, without a pack
# fixture that has to track the shipped doctrine.
# ---------------------------------------------------------------------------

_BUILT_IN_URN = "tactic:shared"


def _drg_node(urn: str, provenance: str) -> DRGNode:
    return DRGNode(urn=urn, kind=NodeKind.TACTIC, label="Node", provenance=provenance)


def _drg_graph(*nodes: DRGNode) -> DRGGraph:
    return DRGGraph(
        schema_version="1.0",
        generated_at="2026-06-27T00:00:00Z",
        generated_by="unit-test",
        nodes=list(nodes),
        edges=[],
    )


def _render_with_stubbed_merge(
    repo_root: Path, built_in: DRGGraph, merged: DRGGraph
) -> str:
    """Render the org section with ``load_built_in_graph`` and the merge stubbed."""
    from specify_cli.cli.commands.doctor import _render_org_layer_section

    buf = StringIO()
    console = Console(file=buf, highlight=False, markup=False, width=200)
    with (
        patch("charter.drg.load_built_in_graph", return_value=built_in),
        patch(
            "charter.activation.drg_activation.merge_three_layers",
            return_value=merged,
        ),
    ):
        _render_org_layer_section(repo_root, console)
    return buf.getvalue()


def test_collisions_line_reports_a_permitted_builtin_override(
    tmp_repo_with_org_pack: Path,
) -> None:
    """RED before the fix: the merged node is org-tagged, yet the line said ``none``."""
    built_in = _drg_graph(_drg_node(_BUILT_IN_URN, "built-in"))
    merged = _drg_graph(_drg_node(_BUILT_IN_URN, "org:example-org"))

    output = _render_with_stubbed_merge(tmp_repo_with_org_pack, built_in, merged)

    assert (
        "collisions: 1 permitted org override of a built-in (see the sanction report)"
        in output
    ), output
    assert "collisions: none" not in output, output


def test_collisions_line_counts_every_permitted_builtin_override(
    tmp_repo_with_org_pack: Path,
) -> None:
    built_in = _drg_graph(
        _drg_node("tactic:alpha", "built-in"), _drg_node("tactic:beta", "built-in")
    )
    merged = _drg_graph(
        _drg_node("tactic:alpha", "org:example-org"),
        _drg_node("tactic:beta", "org:example-org"),
    )

    output = _render_with_stubbed_merge(tmp_repo_with_org_pack, built_in, merged)

    assert (
        "collisions: 2 permitted org overrides of built-ins (see the sanction report)"
        in output
    ), output
    assert "collisions: none" not in output, output


def test_collisions_line_stays_none_when_an_org_node_overrides_nothing(
    tmp_repo_with_org_pack: Path,
) -> None:
    """Discriminator: an org node at a NEW urn is not a collision with a built-in."""
    built_in = _drg_graph(_drg_node(_BUILT_IN_URN, "built-in"))
    merged = _drg_graph(
        _drg_node(_BUILT_IN_URN, "built-in"),
        _drg_node("tactic:org-only", "org:example-org"),
    )

    output = _render_with_stubbed_merge(tmp_repo_with_org_pack, built_in, merged)

    assert "collisions: none" in output, output
    assert "permitted org override" not in output, output


def test_collision_count_agrees_with_the_canonical_override_finder() -> None:
    """The renderer's count must not drift from ``find_overridden_builtins``.

    ``_profile_health_render`` may not import ``override_policy`` (that internal
    is reachable only from ``_charter_pack_collect``; see
    ``tests/architectural/test_runtime_charter_doctrine_boundary.py``), so the
    render side applies the same provenance rule locally. This pins the two to
    one answer, including the cases that must NOT count.
    """
    from charter.offering.drg.override_policy import find_overridden_builtins
    from specify_cli.cli.commands._profile_health_render import (
        _permitted_builtin_overrides,
    )

    built_in = _drg_graph(
        _drg_node("tactic:alpha", "built-in"),
        _drg_node("tactic:beta", "built-in"),
        _drg_node("tactic:gamma", "built-in"),
    )
    merged = _drg_graph(
        _drg_node("tactic:alpha", "org:pack"),  # permitted org override: counts
        _drg_node("tactic:beta", "project"),  # project tier: out of scope
        _drg_node("tactic:gamma", "built-in"),  # untouched
        _drg_node("tactic:novel", "org:pack"),  # org node at a new urn: not an override
    )

    expected = [
        override.urn
        for override in find_overridden_builtins(
            merged, frozenset(node.urn for node in built_in.nodes)
        )
    ]

    assert _permitted_builtin_overrides(merged, built_in) == expected == ["tactic:alpha"]


def test_render_org_layer_section_no_crash_on_missing_pack(
    tmp_path: Path,
) -> None:
    """When pack path doesn't exist, section renders error message without crashing."""
    from specify_cli.cli.commands.doctor import _render_org_layer_section

    kittify = tmp_path / ".kittify"
    kittify.mkdir()
    (kittify / "config.yaml").write_text(
        dedent(
            """\
            charter_packs:
              org:
                packs:
                  - name: missing-pack
                    local_path: /nonexistent/path/to/pack
            """
        )
    )

    buf = StringIO()
    console = Console(file=buf, highlight=False, markup=False)
    # Must not raise an exception
    _render_org_layer_section(tmp_path, console)
    output = buf.getvalue()
    # Should mention the error or missing pack
    assert "missing" in output.lower() or "error" in output.lower() or "pack" in output.lower(), (
        f"expected error/missing indication in output: {output!r}"
    )


def test_render_org_layer_section_no_packs_configured(
    tmp_repo_without_org_pack: Path,
) -> None:
    """When no org packs configured, section indicates none configured."""
    from specify_cli.cli.commands.doctor import _render_org_layer_section

    buf = StringIO()
    console = Console(file=buf, highlight=False, markup=False)
    _render_org_layer_section(tmp_repo_without_org_pack, console)
    output = buf.getvalue()

    assert "no organisation packs" in output.lower() or "no packs" in output.lower() or "(no" in output, (
        f"expected 'no packs configured' indication: {output!r}"
    )


# ---------------------------------------------------------------------------
# _collect_org_layer_data tests
# ---------------------------------------------------------------------------


def test_collect_org_layer_data_returns_configured_packs(
    tmp_repo_with_org_pack: Path,
) -> None:
    """Returns structured dict with configured_packs list when packs exist."""
    from specify_cli.cli.commands.doctor import _collect_org_layer_data

    result = _collect_org_layer_data(tmp_repo_with_org_pack)

    assert "configured_packs" in result
    packs = result["configured_packs"]
    assert isinstance(packs, list)
    assert len(packs) == 1
    pack = packs[0]
    assert pack.get("name") == "example-org"
    assert pack.get("fetched") is True
    assert isinstance(pack.get("node_count"), int)
    assert isinstance(pack.get("edge_count"), int)


def test_collect_org_layer_data_reports_a_dangling_org_endpoint(
    tmp_repo_with_org_pack: Path,
) -> None:
    """A qualified endpoint that binds to nothing is an ERROR here (WP08 fold).

    ``merge_three_layers`` accepts a fully-qualified endpoint verbatim and only
    WARNs when it resolves to nothing, because it cannot tell whether its caller
    merged the whole graph or a deliberate subset — ``charter lint`` merges org
    fragments against an EMPTY built-in graph on purpose.

    ``_collect_org_layer_data`` is the caller that DOES hold a complete graph:
    the real shipped built-in against the operator's real configured packs. So
    it escalates, and — because ``CharterPackHealthReport.healthy`` reads
    ``org_drg['errors']`` — a typo'd endpoint now flips ``doctor charter-packs`` to
    RC=1 instead of passing clean.

    Before the fold, no production caller of ``merge_three_layers`` ran
    ``validate_graph``/``assert_valid`` at all, so this returned no errors.
    """
    from specify_cli.cli.commands.doctor import _collect_org_layer_data

    fragment = tmp_repo_with_org_pack / "example_org" / "drg" / "fragment.yaml"
    fragment.write_text(
        fragment.read_text(encoding="utf-8").replace(
            "styleguide:plain-language", "styleguide:plain-languagee"
        ),
        encoding="utf-8",
    )

    result = _collect_org_layer_data(tmp_repo_with_org_pack)

    dangling = result.get("dangling_endpoints")
    assert isinstance(dangling, list) and dangling, (
        f"a typo'd qualified endpoint must be reported, got {result!r}"
    )
    assert any("styleguide:plain-languagee" in e for e in dangling), (
        f"the report must name the offending token; got {dangling}"
    )
    errors = result.get("errors")
    assert isinstance(errors, list)
    assert any("styleguide:plain-languagee" in e for e in errors), (
        "the finding must reach org_drg['errors'] — that is the channel "
        f"CharterPackHealthReport.healthy reads; got {errors}"
    )


def test_collect_org_layer_data_reports_no_dangling_endpoint_when_clean(
    tmp_repo_with_org_pack: Path,
) -> None:
    """The escalation must discriminate, not fire on every pack.

    The shipped fixture references a real built-in node by qualified URN — the
    sanctioned cross-fragment authoring shape — so an unmodified pack must come
    back clean. Without this, the test above would pass on a check that flagged
    everything.

    The clean signal is an EMPTY ``dangling_endpoints``, not an absent one. This
    assertion previously read ``is None`` and so pinned the key's conditional
    presence — under which "the check ran and found nothing" and "the check
    never ran" produced the identical payload. See
    ``test_charter_pack_hard_fail_surfacing.test_dangling_endpoints_key_is_always_present``.
    """
    from specify_cli.cli.commands.doctor import _collect_org_layer_data

    result = _collect_org_layer_data(tmp_repo_with_org_pack)

    assert result.get("dangling_endpoints") == [], result
    assert result.get("errors") == []


def test_collect_org_layer_data_surfaces_a_failed_merge_check(
    tmp_repo_with_org_pack: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A merge check that could not RUN is not a merge check that PASSED.

    Twin of the ``charter status`` case: the handler wrapping this merge was a
    bare ``except Exception: pass``. Since the fold, the merge inside it also
    decides whether the org layer is reported complete, so swallowing the
    failure turns "the completeness check crashed" into ``errors: []`` — and
    ``CharterPackHealthReport.healthy`` reads that array, so ``doctor charter-packs``
    would exit 0 having verified nothing.
    """
    import charter.activation.drg_activation as drg_activation
    from specify_cli.cli.commands.doctor import _collect_org_layer_data

    def _boom(**_kwargs: object) -> object:
        raise RuntimeError("merge exploded")

    # ``_collect_org_layer_data`` imports ``merge_three_layers`` from
    # ``charter.activation.drg_activation`` (its re-export site), not from the
    # ``charter.drg`` facade — patch the module production actually calls.
    monkeypatch.setattr(drg_activation, "merge_three_layers", _boom)

    result = _collect_org_layer_data(tmp_repo_with_org_pack)

    errors = result.get("errors")
    assert isinstance(errors, list)
    assert any("merge exploded" in e for e in errors), (
        f"a diagnostic that could not verify must not report healthy; got {errors}"
    )


def test_collect_org_layer_data_empty_packs_when_none_configured(
    tmp_repo_without_org_pack: Path,
) -> None:
    """Returns empty configured_packs when no org packs are in config."""
    from specify_cli.cli.commands.doctor import _collect_org_layer_data

    result = _collect_org_layer_data(tmp_repo_without_org_pack)
    packs = result.get("configured_packs", [])
    assert packs == [], f"expected empty packs list, got: {packs}"


def test_collect_org_layer_data_error_on_missing_pack(
    tmp_path: Path,
) -> None:
    """Returns errors list when pack path doesn't exist."""
    from specify_cli.cli.commands.doctor import _collect_org_layer_data

    kittify = tmp_path / ".kittify"
    kittify.mkdir()
    (kittify / "config.yaml").write_text(
        dedent(
            """\
            charter_packs:
              org:
                packs:
                  - name: ghost-pack
                    local_path: /nonexistent/path/to/ghost-pack
            """
        )
    )

    result = _collect_org_layer_data(tmp_path)
    errors = result.get("errors", [])
    assert errors, f"expected errors list when pack is missing, got: {result}"


# ---------------------------------------------------------------------------
# CLI integration: doctor charter-packs --json includes org_drg key
# ---------------------------------------------------------------------------


def _build_kittify_config_for_test(
    repo_root: Path, pack_path: Path, pack_name: str = "test-pack"
) -> None:
    """Write a minimal .kittify/config.yaml for the doctrine.org.packs schema."""
    config_dir = repo_root / ".kittify"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "config.yaml").write_text(
        dedent(
            f"""
            charter_packs:
              org:
                packs:
                  - name: {pack_name}
                    local_path: {pack_path}
            """
        ).lstrip()
    )


def test_doctor_charter_packs_json_includes_org_drg_key_when_packs_configured(
    tmp_repo_with_org_pack: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``doctor charter-packs --json`` includes ``org_drg`` key when org packs configured.

    Uses the canonical ``charter_packs.org.packs`` config format (which ``load_org_drg`` reads),
    distinct from the ``doctrine.org.packs`` format (which ``load_pack_registry`` reads).
    The ``org_drg`` key is populated from ``_collect_org_layer_data`` regardless
    of whether ``load_pack_registry`` finds packs.
    """
    from specify_cli.cli.commands.doctor import app as doctor_app

    monkeypatch.chdir(tmp_repo_with_org_pack)

    with patch(
        "specify_cli.cli.commands.doctor.locate_project_root",
        return_value=tmp_repo_with_org_pack,
    ):
        result = runner.invoke(doctor_app, ["charter-packs", "--json"])

    # Exit code is always 0 for doctor charter-packs (diagnostic only)
    assert result.exit_code == 0, (
        f"doctor charter-packs exited with code {result.exit_code}: {result.output}"
    )

    try:
        payload = json.loads(result.output)
    except json.JSONDecodeError as exc:
        pytest.fail(
            f"doctor charter-packs --json did not produce valid JSON: {exc}\n"
            f"output: {result.output!r}"
        )

    assert "org_drg" in payload, (
        f"doctor charter-packs JSON must include 'org_drg' key. Got keys: {list(payload.keys())}"
    )


def test_doctor_charter_packs_json_includes_org_drg_key_when_no_packs(
    tmp_repo_without_org_pack: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``doctor charter-packs --json`` includes ``org_drg`` key even when no packs configured."""
    from specify_cli.cli.commands.doctor import app as doctor_app

    monkeypatch.chdir(tmp_repo_without_org_pack)

    with patch(
        "specify_cli.cli.commands.doctor.locate_project_root",
        return_value=tmp_repo_without_org_pack,
    ):
        result = runner.invoke(doctor_app, ["charter-packs", "--json"])

    assert result.exit_code == 0, (
        f"doctor charter-packs exited with code {result.exit_code}: {result.output}"
    )

    try:
        payload = json.loads(result.output)
    except json.JSONDecodeError as exc:
        pytest.fail(
            f"doctor charter-packs --json did not produce valid JSON: {exc}\n"
            f"output: {result.output!r}"
        )

    assert "org_drg" in payload, (
        f"doctor charter-packs JSON must always include 'org_drg' key. Got: {list(payload.keys())}"
    )
    org_drg = payload["org_drg"]
    packs = org_drg.get("configured_packs", [])
    assert packs == [], f"expected empty packs when none configured, got: {packs}"
