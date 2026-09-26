"""References-parity auto-refresh completion (#2777, FR-011, NFR-006, WP06).

Covers ``preflight.references_refresh`` — WP06's implementation of the
extension point WP04 installed at ``preflight.runner.refresh_references_if_needed``
(see ``test_boundary_heal.py``'s T019 section for the call-site wiring pin).

* ``test_references_parity_drift_recompiles_the_catalog``: end to end
  against the REAL ``charter generate`` code path (``compile_charter`` +
  ``write_compiled_charter``, invoked in-process through
  ``typer.testing.CliRunner`` rather than a hand-faked stand-in) — a
  references-parity cause recompiles ``charter.yaml``'s ``catalog.references``
  back to the current, real doctrine-derived content, and leaves a curated
  ``charter.md`` byte-for-byte unchanged (NFR-006 / #2772).
* ``test_non_references_parity_cause_is_a_true_noop``: the "never
  unconditionally" gate (T024) — a cause that does not name
  ``synthesized_drg`` never spawns ``generate`` and never touches the
  filesystem.
* ``test_is_references_parity_cause_*``: direct unit coverage of the pure
  gating predicate across the reachable cause-set combinations (see
  ``references_refresh``'s module docstring for why a bare ``built_in_only``
  project reaches a stale-without-``synthesized_drg`` cause set).
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any

import pytest
from ruamel.yaml import YAML
from typer.testing import CliRunner

from specify_cli.charter_runtime.preflight import references_refresh
from specify_cli.cli.commands.charter import app as charter_app

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]

_runner = CliRunner()

_CURATED_CHARTER_MD = "# Curated Charter\n\nHand-authored governance prose.\n"

#: Mirrors ``_GENERATE_CMD_PREFIX`` -- kept as an
#: independent literal (not a reach into the module's private attribute) so
#: this test asserts on the OBSERVABLE argv shape, not an implementation
#: detail.
_GENERATE_CMD_PREFIX: tuple[str, ...] = ("spec-kitty", "charter", "generate")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _git_init(repo: Path) -> None:
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=repo, check=True)
    subprocess.run(["git", "config", "commit.gpgsign", "false"], cwd=repo, check=True)


def _write_curated_charter_md(repo: Path) -> Path:
    """Seed a hand-authored ``charter.md`` -- ``generate`` must never write it
    (data-model.md Landmine 3 / #2772)."""
    charter_dir = repo / ".kittify" / "charter"
    charter_dir.mkdir(parents=True, exist_ok=True)
    path = charter_dir / "charter.md"
    path.write_text(_CURATED_CHARTER_MD, encoding="utf-8")
    return path


def _invoke_generate_in_process(repo: Path, argv: list[str]) -> subprocess.CompletedProcess[str]:
    """Run the REAL ``generate`` Typer command in-process via ``CliRunner``.

    ``find_repo_root()`` resolves from ``os.getcwd()`` (see
    ``test_charter_generate_autotrack.py``'s established convention), so the
    process cwd is switched to *repo* for the duration of the call and
    restored afterwards.
    """
    old_cwd = os.getcwd()
    try:
        os.chdir(repo)
        result = _runner.invoke(charter_app, argv, catch_exceptions=False)
    finally:
        os.chdir(old_cwd)
    return subprocess.CompletedProcess(
        args=["spec-kitty", "charter", *argv],
        returncode=result.exit_code,
        stdout=result.stdout,
        stderr="",
    )


def _make_generate_subprocess_fake(repo: Path, seen_calls: list[list[str]]) -> Any:
    """Fake ``subprocess.run`` that lets real ``git`` calls through and routes
    ``spec-kitty charter generate`` to the real command in-process (no real
    OS subprocess spawned, matching the ``test_boundary_heal.py`` convention
    for ``spec-kitty charter synthesize``)."""
    real_run = subprocess.run

    def fake_run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        if cmd[:1] == ["git"]:
            return real_run(cmd, **kwargs)
        seen_calls.append(list(cmd))
        if tuple(cmd[:3]) == _GENERATE_CMD_PREFIX:
            return _invoke_generate_in_process(repo, cmd[2:])
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    return fake_run


def _load_yaml(path: Path) -> dict[str, Any]:
    yaml = YAML(typ="safe")
    data = yaml.load(path.read_text(encoding="utf-8"))
    return dict(data) if data else {}


def _dump_yaml(path: Path, data: dict[str, Any]) -> None:
    yaml = YAML(typ="safe")
    with path.open("w", encoding="utf-8") as handle:
        yaml.dump(data, handle)


def _seed_baseline_repo(repo: Path, seen_calls: list[list[str]]) -> Path:
    """Real git repo + curated charter.md + a real, freshly-generated
    charter.yaml (via the in-process fake, so the baseline itself already
    exercises the exact same code path the hook under test will use).

    Returns the ``charter.yaml`` path.
    """
    _git_init(repo)
    _write_curated_charter_md(repo)

    fake = _make_generate_subprocess_fake(repo, seen_calls)
    result = fake(["spec-kitty", "charter", "generate", "--no-from-interview"])
    assert result.returncode == 0, f"baseline generate failed: {result.stdout!r}"
    seen_calls.clear()  # baseline call doesn't count toward the assertions below

    charter_yaml_path = repo / ".kittify" / "charter" / "charter.yaml"
    assert charter_yaml_path.exists()
    return charter_yaml_path


# ---------------------------------------------------------------------------
# End-to-end: references-parity drift recompiles the catalog, honors #2772
# ---------------------------------------------------------------------------


def test_references_parity_drift_recompiles_the_catalog(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen_calls: list[list[str]] = []
    charter_yaml_path = _seed_baseline_repo(tmp_path, seen_calls)
    charter_md_path = tmp_path / ".kittify" / "charter" / "charter.md"

    baseline = _load_yaml(charter_yaml_path)
    baseline_references = baseline["catalog"]["references"]
    assert baseline_references, "fixture sanity: baseline generate produced no references"

    # Simulate references-parity drift: truncate the compiled catalog's
    # references so it no longer reflects current activation.
    drifted = _load_yaml(charter_yaml_path)
    drifted["catalog"]["references"] = []
    _dump_yaml(charter_yaml_path, drifted)
    assert _load_yaml(charter_yaml_path)["catalog"]["references"] == []

    charter_md_before = charter_md_path.read_bytes()

    monkeypatch.setattr(
        subprocess, "run", _make_generate_subprocess_fake(tmp_path, seen_calls)
    )

    ran = references_refresh.refresh_references_if_needed(tmp_path, cause="synthesized_drg")

    assert ran is True
    assert any(
        tuple(c[:3]) == _GENERATE_CMD_PREFIX for c in seen_calls
    ), seen_calls

    healed = _load_yaml(charter_yaml_path)
    healed_references = healed["catalog"]["references"]
    # Compare by activated-id SET, not full deep equality: a pre-existing,
    # WP06-unrelated quirk in `compile_charter`'s language-scoped doctrine
    # lookup (repro'd directly against plain `spec-kitty charter generate
    # --no-from-interview` run twice against the same repo, with no
    # references_refresh code involved at all) degrades a handful of
    # python/typescript-specific styleguide/toolguide `title`/`summary`
    # strings to a "Definition unavailable in bundled doctrine" placeholder
    # on a SECOND generate call -- `id`/`kind`/`source_path`/`local_path`
    # stay stable. The id-set comparison is what AS3 actually requires
    # ("content reflects current activation" -- i.e. the SAME activated set
    # is recompiled, not left as the injected empty/truncated drift) without
    # coupling this test to that separate, out-of-scope defect.
    assert {ref["id"] for ref in healed_references} == {
        ref["id"] for ref in baseline_references
    }, (
        "references-parity refresh must recompile the catalog back to "
        "current activation, not leave the drifted/truncated content"
    )
    assert len(healed_references) == len(baseline_references)

    charter_md_after = charter_md_path.read_bytes()
    assert charter_md_after == charter_md_before, (
        "NFR-006: curated charter.md must be 0 bytes changed by the refresh"
    )


def test_references_parity_drift_recompiles_using_the_existing_mission_and_template_set(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The targeted refresh must not silently reset a non-default mission
    type / template set to ``generate``'s hardcoded ``software-dev``
    fallback -- it reads the existing ``catalog.mission``/``template_set``
    and threads them through explicitly."""
    seen_calls: list[list[str]] = []
    charter_yaml_path = _seed_baseline_repo(tmp_path, seen_calls)

    baseline = _load_yaml(charter_yaml_path)
    assert baseline["catalog"]["mission"] == "software-dev"
    assert baseline["catalog"]["template_set"]

    monkeypatch.setattr(
        subprocess, "run", _make_generate_subprocess_fake(tmp_path, seen_calls)
    )
    references_refresh.refresh_references_if_needed(tmp_path, cause="synthesized_drg")

    generate_call = next(
        c for c in seen_calls if tuple(c[:3]) == _GENERATE_CMD_PREFIX
    )
    assert "--mission-type" in generate_call
    assert generate_call[generate_call.index("--mission-type") + 1] == "software-dev"
    assert "--template-set" in generate_call
    assert (
        generate_call[generate_call.index("--template-set") + 1]
        == baseline["catalog"]["template_set"]
    )


# ---------------------------------------------------------------------------
# Gating -- "never unconditionally" (T024)
# ---------------------------------------------------------------------------


def test_non_references_parity_cause_is_a_true_noop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen_calls: list[list[str]] = []
    charter_yaml_path = _seed_baseline_repo(tmp_path, seen_calls)

    # Same drift simulation as the positive test -- if this cause spuriously
    # triggered `generate`, the drifted marker would disappear.
    drifted = _load_yaml(charter_yaml_path)
    drifted["catalog"]["references"] = []
    _dump_yaml(charter_yaml_path, drifted)

    monkeypatch.setattr(
        subprocess, "run", _make_generate_subprocess_fake(tmp_path, seen_calls)
    )

    ran = references_refresh.refresh_references_if_needed(tmp_path, cause="charter_source,synced_bundle")

    assert ran is False
    assert seen_calls == [], "a non-references-parity cause must never invoke generate"
    assert _load_yaml(charter_yaml_path)["catalog"]["references"] == [], (
        "no-op must leave the drifted content exactly as-is"
    )


# ---------------------------------------------------------------------------
# Unit coverage: the pure gating predicate
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("cause", "expected"),
    [
        ("synthesized_drg", True),
        ("charter_source,synced_bundle,synthesized_drg", True),
        ("charter_source,synced_bundle", False),
        ("charter_source", False),
        ("", False),
    ],
)
def test_is_references_parity_cause(cause: str, expected: bool) -> None:
    assert references_refresh.is_references_parity_cause(cause) is expected


def test_references_parity_cause_name_is_a_runner_layer() -> None:
    """The references-parity cause name must be a real runner layer name.

    ``references_refresh._REFERENCES_PARITY_CAUSE_NAME`` is sourced from
    ``preflight.runner.SYNTHESIZED_DRG_LAYER`` rather than re-declared as its
    own literal (see the module docstring's mapping note and this fold's
    single-source refactor). This is the binding test that makes a future
    rename of the layer name fail loudly instead of silently no-op'ing the
    references-parity heal: assert the cause name is a member of the
    runner's own ``_LAYER_ORDER`` layer-key set, not just equal to a
    hardcoded string.
    """
    from specify_cli.charter_runtime.preflight import runner as runner_module

    layer_keys = {key for key, _label in runner_module._LAYER_ORDER}
    assert references_refresh._REFERENCES_PARITY_CAUSE_NAME in layer_keys
    assert references_refresh._REFERENCES_PARITY_CAUSE_NAME == runner_module.SYNTHESIZED_DRG_LAYER


# ---------------------------------------------------------------------------
# T010 -- shared ``catalog.mission``/``catalog.template_set`` accessor parity
# (Finding B, #4993)
# ---------------------------------------------------------------------------


def test_read_catalog_mission_and_template_set_matches_shared_accessor(
    tmp_path: Path,
) -> None:
    """AC-B1: this module's ``catalog.mission``/``catalog.template_set``
    reader must resolve the identical value the shared accessor
    (``charter.activation.charter_yaml_io.read_catalog_field``, Finding B /
    #4993) returns directly for the same repo -- both now read through the
    one canonical parser rather than this module's former ad-hoc
    ``YAML(typ="safe")`` read."""
    from charter.activation.charter_yaml_io import read_catalog_field

    seen_calls: list[list[str]] = []
    _seed_baseline_repo(tmp_path, seen_calls)

    mission, template_set = references_refresh._read_catalog_mission_and_template_set(tmp_path)

    assert mission == read_catalog_field(tmp_path, "mission") == "software-dev"
    assert template_set == read_catalog_field(tmp_path, "template_set")
    assert template_set is not None


def test_read_catalog_mission_and_template_set_absent_charter_yaml(tmp_path: Path) -> None:
    """AC-B2: an absent ``charter.yaml`` yields the same absent
    ``(None, None)`` result as before the refactor."""
    assert references_refresh._read_catalog_mission_and_template_set(tmp_path) == (None, None)
