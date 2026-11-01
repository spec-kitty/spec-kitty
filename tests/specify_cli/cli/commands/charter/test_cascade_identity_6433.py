"""The ``--cascade`` walk starts from the artifact you named, however you spelled it (#6433).

``activate``/``deactivate`` resolve the cascade source through the one
:class:`~charter.activation.identity_index.IdentityIndex`, so a file stem, a declared id
and a ``<kind>:<id>`` URN all reach the same DRG node. Before #6433 the source resolution
went through ``resolve_artifact_urn``, which refused a URN: the activation was written, and
the cascade (or the shared-artifact safety report) silently disappeared.

Each test asserts the stem run as the positive control on the same fixture, so the
assertion cannot pass vacuously.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import Result
from typer.testing import CliRunner

from specify_cli.cli.commands.charter import charter_app
from tests._factories.activation_ledger import read_activation_ledger, seed_activation_ledger

pytestmark = [pytest.mark.fast]

_RUNNER = CliRunner()
_STEM = "024-locality-of-change"
_DECLARED = "DIRECTIVE_024"
_URN = f"directive:{_DECLARED}"
_NORMALISED = "24"
#: What the built-in DRG reaches from DIRECTIVE_024 (mission ``--cascade all`` target).
_CASCADED = "Cascade-activated: directive/reconcile-change-scope-tensions"
#: The shared artifact the deactivation cascade keeps because an active profile references it.
_SHARED_SKIP = "Skipped (shared artifact): directive:RECONCILE_CHANGE_SCOPE_TENSIONS"


def _project(root: Path, *, activated: list[str] | None = None) -> Path:
    (root / ".kittify").mkdir(parents=True, exist_ok=True)
    (root / ".kittify" / "config.yaml").write_text("{}\n", encoding="utf-8")
    seed_activation_ledger(root, mission_type_activations=["software-dev"], activated_directives=activated or [])
    return root


def _charter(root: Path, *args: str) -> Result:
    return _RUNNER.invoke(charter_app, [args[0], "--repo-root", str(root), "--no-compile", *args[1:]])


@pytest.mark.parametrize("token", [_STEM, _URN, _NORMALISED], ids=["stem", "urn", "normalised-id"])
def test_activate_cascade_starts_from_the_named_artifact_however_it_is_spelled(tmp_path: Path, token: str) -> None:
    root = _project(tmp_path)

    result = _charter(root, "activate", "directive", token, "--cascade", "all")

    assert result.exit_code == 0, result.output
    assert _CASCADED in result.output, result.output


@pytest.mark.parametrize("token", [_STEM, _URN, _NORMALISED], ids=["stem", "urn", "normalised-id"])
def test_deactivate_cascade_reports_the_shared_artifact_however_it_is_spelled(tmp_path: Path, token: str) -> None:
    root = _project(tmp_path, activated=["001-architectural-integrity-standard", _STEM])

    result = _charter(root, "deactivate", "directive", token, "--cascade", "all")

    assert result.exit_code == 0, result.output
    assert _SHARED_SKIP in result.output, result.output


def test_the_spellings_write_the_same_activation(tmp_path: Path) -> None:
    """Positive control for the two above: the ledgers are identical, so only the cascade differed."""
    ledgers: dict[str, list[str]] = {}
    for token in (_STEM, _URN, _NORMALISED):
        root = tmp_path / token.replace(":", "-")
        root.mkdir()
        _charter(_project(root), "activate", "directive", token, "--cascade", "all")
        ledgers[token] = read_activation_ledger(root)["activated_directives"]

    assert ledgers[_STEM] == ledgers[_URN] == ledgers[_NORMALISED]
    assert _STEM in ledgers[_STEM]


def test_one_index_serves_the_whole_active_set(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """NFR-004: the active-URN set resolves through one index per command, not one per token."""
    from charter.activation import identity_index as identity_index_module

    builds: list[int] = []
    original = identity_index_module.IdentityIndex.from_roots.__func__

    def counting(cls, **kwargs):  # type: ignore[no-untyped-def]
        builds.append(1)
        return original(cls, **kwargs)

    monkeypatch.setattr(identity_index_module.IdentityIndex, "from_roots", classmethod(counting))
    counts: list[int] = []
    for extra in ([], ["025-boy-scout-rule", "028-search-tool-discipline", "029-agent-commit-signing-policy"]):
        root = tmp_path / f"active-{len(extra)}"
        root.mkdir()
        _charter(
            _project(root, activated=["001-architectural-integrity-standard", _STEM, *extra]),
            "deactivate",
            "directive",
            _STEM,
            "--cascade",
            "all",
        )
        counts.append(len(builds))
        builds.clear()

    # Adding active artifacts must not add index builds: the loop shares one index.
    assert counts[0] >= 1, counts  # the command does build one
    assert counts[0] == counts[1], counts
