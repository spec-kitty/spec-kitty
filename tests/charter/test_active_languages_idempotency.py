"""Issue #3292 regression: ``charter generate`` non-idempotency.

Root cause (verified, see ``charter.activation.language_scope.infer_repo_languages`` and
``charter.activation.compiler.compile_charter`` docstrings for the full contract):
``compile_charter`` used to independently re-scan the interview text on every
compile and unconditionally stamp the (possibly empty) result into
``catalog.languages``. ``charter.activation.doctrine_service_builder``'s language gate
(via ``infer_repo_languages``) then read that persisted empty list back as
authoritative "admit none" on the *next* run -- even though the compile that
produced it had no real language signal at all. A fresh repo's first
``charter generate`` therefore resolved language-scoped styleguides/
toolguides with real content (no ``charter.yaml`` existed yet, so the gate
saw "no signal" -> admit all), while the *second* invocation of the exact
same command, on an untouched repo, silently degraded those same artifacts
to ``"Definition unavailable in bundled doctrine."`` placeholders.

The fix unifies both call sites on the single authority
``charter.activation.language_scope.infer_repo_languages`` and makes an empty/no-signal
result round-trip as an *absent* structured field (schema-null / omitted
key) rather than a persisted empty list, so it can never be misread as a
deliberate "admit none" answer on the next run.
"""

from __future__ import annotations

import contextlib
import subprocess
from pathlib import Path

import pytest
from ruamel.yaml import YAML
from typer.testing import CliRunner

from charter.activation.compiler import compile_charter
from charter.activation.interview import apply_answer_overrides, default_interview
from charter.activation.language_scope import infer_repo_languages
from specify_cli.cli.commands.charter import app as charter_app

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]

runner = CliRunner()

_PLACEHOLDER_SUMMARY = "Definition unavailable in bundled doctrine."
_PYTHON_STYLEGUIDE_ID = "STYLEGUIDE:python-conventions"


# ---------------------------------------------------------------------------
# Shared fixtures / helpers
# ---------------------------------------------------------------------------


def _git_init(repo: Path) -> None:
    subprocess.run(["git", "init", "--initial-branch=main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "commit.gpgsign", "false"], cwd=repo, check=True, capture_output=True)


def _write_curated_charter_md(repo: Path) -> None:
    charter_dir = repo / ".kittify" / "charter"
    charter_dir.mkdir(parents=True, exist_ok=True)
    (charter_dir / "charter.md").write_text("# Curated Charter\n\nHand-authored governance prose.\n", encoding="utf-8")


def _invoke_generate(repo: Path, *args: str) -> object:
    with contextlib.chdir(repo):
        return runner.invoke(charter_app, ["generate", *args], catch_exceptions=False)


def _read_catalog(repo: Path) -> dict:
    yaml = YAML(typ="safe")
    charter_yaml_path = repo / ".kittify" / "charter" / "charter.yaml"
    document = yaml.load(charter_yaml_path.read_text(encoding="utf-8"))
    return document["catalog"]


def _summary_for(references: list[dict], reference_id: str) -> str | None:
    for reference in references:
        if reference["id"] == reference_id:
            return str(reference["summary"])
    return None


# ---------------------------------------------------------------------------
# RED-first repro: `charter generate` must be idempotent for a
# language-agnostic / language-absent interview (issue #3292).
# ---------------------------------------------------------------------------


def test_charter_generate_is_idempotent_for_language_agnostic_default_interview(
    tmp_path: Path,
) -> None:
    """Two back-to-back ``charter generate --no-from-interview`` runs on an
    untouched repo must produce byte-identical (modulo timestamps) catalog
    content -- specifically, the SAME ``languages`` value and the SAME,
    real (non-placeholder) language-scoped reference content both times.

    Confirmed RED against the pre-fix code (manual revert-and-rerun, not
    committed here): run 1 resolved ``python-conventions`` with its real
    "Guard clauses..." summary and 258 references while stamping
    ``catalog.languages: []``; run 2, on the SAME untouched repo, read that
    persisted ``[]`` back as authoritative "admit none" and degraded
    ``python-conventions`` (and 3 other language-scoped artifacts) to the
    ``"Definition unavailable in bundled doctrine."`` placeholder, dropping
    the reference count to 249.
    """
    _git_init(tmp_path)
    _write_curated_charter_md(tmp_path)

    first = _invoke_generate(tmp_path, "--no-from-interview", "--json")
    assert first.exit_code == 0, f"first generate failed: {first.stdout!r}"
    catalog_1 = _read_catalog(tmp_path)

    second = _invoke_generate(tmp_path, "--no-from-interview", "--json", "--force")
    assert second.exit_code == 0, f"second generate failed: {second.stdout!r}"
    catalog_2 = _read_catalog(tmp_path)

    # (a) byte-identical catalog, modulo the metadata timestamp: languages
    # and the full reference set must be stable across regenerate.
    assert catalog_1.get("languages") == catalog_2.get("languages")
    assert catalog_1["references"] == catalog_2["references"]
    assert len(catalog_1["references"]) == len(catalog_2["references"])

    # (b) no placeholder content on the second run.
    placeholder_count = sum(1 for reference in catalog_2["references"] if reference["summary"] == _PLACEHOLDER_SUMMARY)
    assert placeholder_count == 0, (
        f"{placeholder_count} language-scoped reference(s) degraded to the bundled-doctrine placeholder on the second `charter generate` run"
    )

    # (c) a real, language-scoped styleguide keeps its genuine title/summary
    # on BOTH runs -- not just "some non-empty summary", the actual content.
    summary_1 = _summary_for(catalog_1["references"], _PYTHON_STYLEGUIDE_ID)
    summary_2 = _summary_for(catalog_2["references"], _PYTHON_STYLEGUIDE_ID)
    assert summary_1 is not None, "python-conventions styleguide missing on first run"
    assert summary_2 is not None, "python-conventions styleguide missing on second run"
    assert summary_1 == summary_2
    assert summary_1 != _PLACEHOLDER_SUMMARY
    assert "guard clauses" in summary_1.lower()


def test_charter_generate_is_idempotent_across_three_runs(tmp_path: Path) -> None:
    """Extends the two-run repro to three runs -- guards against a fix that
    merely delays the degradation by one generation rather than closing the
    feedback loop."""
    _git_init(tmp_path)
    _write_curated_charter_md(tmp_path)

    catalogs = []
    for index in range(3):
        args = ["--no-from-interview", "--json"] + (["--force"] if index else [])
        result = _invoke_generate(tmp_path, *args)
        assert result.exit_code == 0, f"generate run {index} failed: {result.stdout!r}"
        catalogs.append(_read_catalog(tmp_path))

    for catalog in catalogs[1:]:
        assert catalog.get("languages") == catalogs[0].get("languages")
        assert catalog["references"] == catalogs[0]["references"]


# ---------------------------------------------------------------------------
# Unit coverage: infer_repo_languages' new `interview` override + the tier-2
# empty-scan-is-not-a-signal fix.
# ---------------------------------------------------------------------------


def test_infer_repo_languages_interview_override_used_when_no_disk_transcript(
    tmp_path: Path,
) -> None:
    """A caller mid-compile (no persisted transcript yet) passes its
    in-memory interview and gets the SAME non-empty answer a disk-backed
    caller would get from an equivalent transcript."""
    interview = apply_answer_overrides(
        default_interview(mission="software-dev", profile="minimal"),
        answers={"languages_frameworks": "Rust services with cargo and rustc tooling"},
    )

    assert infer_repo_languages(tmp_path, interview=interview) == ["rust"]


def test_infer_repo_languages_empty_interview_override_resolves_to_none(
    tmp_path: Path,
) -> None:
    """#3292 fix: an interview that names no recognized language is no
    longer treated as a legitimate empty answer -- it resolves to ``None``
    (no signal), same as no interview at all."""
    interview = default_interview(mission="software-dev", profile="minimal")

    assert infer_repo_languages(tmp_path, interview=interview) is None


def test_infer_repo_languages_compiled_tier_still_wins_over_interview_override(
    tmp_path: Path,
) -> None:
    """The *interview* override never bypasses tier 1: a real prior compile
    remains authoritative even when a fresh interview disagrees."""
    from ruamel.yaml import YAML as _YAML

    charter_yaml_path = tmp_path / ".kittify" / "charter" / "charter.yaml"
    charter_yaml_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "2.0.0",
        "catalog": {
            "mission": "software-dev",
            "template_set": "default",
            "languages": ["typescript"],
            "references": [],
        },
    }
    yaml = _YAML()
    yaml.default_flow_style = False
    with charter_yaml_path.open("w", encoding="utf-8") as handle:
        yaml.dump(payload, handle)

    interview = apply_answer_overrides(
        default_interview(mission="software-dev", profile="minimal"),
        answers={"languages_frameworks": "Python backend with pytest checks"},
    )

    assert infer_repo_languages(tmp_path, interview=interview) == ["typescript"]


# ---------------------------------------------------------------------------
# Unit coverage: compile_charter's own active_languages field now agrees
# with infer_repo_languages (single authority, requirement 2).
# ---------------------------------------------------------------------------


def test_compile_charter_active_languages_is_none_with_no_signal(tmp_path: Path) -> None:
    """A fresh repo (no prior charter.yaml) compiled from a language-agnostic
    interview must resolve ``active_languages`` to ``None`` -- not ``[]`` --
    so downstream persistence never stamps a meaningless authoritative empty
    list (issue #3292's write-side fix)."""
    interview = default_interview(mission="software-dev", profile="minimal")

    compiled = compile_charter(mission="software-dev", interview=interview, repo_root=tmp_path)

    assert compiled.active_languages is None


def test_compile_charter_active_languages_agrees_with_infer_repo_languages(
    tmp_path: Path,
) -> None:
    """Single authority (requirement 2): compile_charter's stamp and a
    direct call to infer_repo_languages with the SAME interview must never
    diverge -- they route through the identical function."""
    interview = apply_answer_overrides(
        default_interview(mission="software-dev", profile="minimal"),
        answers={"languages_frameworks": "Rust services with cargo and rustc tooling"},
    )

    compiled = compile_charter(mission="software-dev", interview=interview, repo_root=tmp_path)
    direct = infer_repo_languages(tmp_path, interview=interview)

    assert compiled.active_languages == direct == ["rust"]
