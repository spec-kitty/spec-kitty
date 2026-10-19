"""Multi-language evidence, gate exemption, stable hash and additive JSON (#6444, FR-010..FR-014)."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from charter.activation.evidence.code_reader import CodeReadingCollector
from charter.activation.evidence.orchestrator import EvidenceOrchestrator
from charter.activation.synthesizer.evidence import CodeSignals, EvidenceBundle
from charter.activation.synthesizer.request import (
    SynthesisRequest,
    SynthesisTarget,
    compute_inputs_hash,
)
from charter.activation.synthesizer.write_pipeline import _is_generic_scoped
from specify_cli.cli.commands.charter import app
from specify_cli.task_utils import TaskCliError

pytestmark = [pytest.mark.regression, pytest.mark.fast]

runner = CliRunner()

# Evidence-bundle hash of ``_python_only`` captured on the lane head BEFORE the FR-010
# change; origin/main computes the same value for the same fixture (FR-012).
_PYTHON_ONLY_HASH = "57586695cea44c2351958ce06828ce982a60821e1d4289355f58a52af83424e5"


def _write(root: Path, rel: str, text: str = "") -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _python_only(root: Path) -> Path:
    _write(root, "pyproject.toml", "[project]\nname='x'\n")
    _write(root, "src/app.py", "x = 1\n")
    _write(root, "tests/test_app.py", "def test_a(): pass\n")
    _write(root, "conftest.py")
    return root


def _kotlin_and_typescript(root: Path) -> Path:
    """Root ``build.gradle.kts`` with mostly ``.kt`` sources, plus a root ``package.json`` with ``.ts`` sources."""
    _write(root, "build.gradle.kts")
    _write(root, "package.json", "{}")
    for index in range(6):
        _write(root, f"src/main/kotlin/com/acme/K{index}.kt")
    for index in range(3):
        _write(root, f"web/T{index}.ts")
    return root


def _nested_polyglot(root: Path) -> Path:
    for index in range(4):
        _write(root, f"backend/src/main/kotlin/com/acme/K{index}.kt")
        _write(root, f"frontend/src/ui/T{index}.ts")
    _write(root, "backend/build.gradle.kts")
    _write(root, "frontend/package.json", "{}")
    return root


def _signals(
    *,
    stack_id: str = "python",
    primary_language: str = "python",
    scope_tag: str = "python",
    languages: tuple[str, ...] = (),
) -> CodeSignals:
    return CodeSignals(
        stack_id=stack_id,
        primary_language=primary_language,
        frameworks=(),
        test_frameworks=(),
        scope_tag=scope_tag,
        representative_files=("src/app.py",),
        detected_at="2026-10-19T00:00:00+00:00",
        languages=languages,
    )


def _request(signals: CodeSignals) -> SynthesisRequest:
    target = SynthesisTarget(
        kind="directive",
        slug="x-y",
        title="T",
        artifact_id="PROJECT_001",
        source_section="testing_philosophy",
        source_urns=(),
    )
    return SynthesisRequest(
        target=target,
        interview_snapshot={"language_scope": ["python"]},
        doctrine_snapshot={},
        drg_snapshot={"nodes": [], "edges": [], "schema_version": "1"},
        run_id="01KPE222CD1MMCYEGB3ZCY51VR",
        adapter_hints=None,
        evidence=EvidenceBundle(code_signals=signals),
    )


def _hash(signals: CodeSignals) -> str:
    return compute_inputs_hash(_request(signals), "fixture", "1.0.0")


# ---------------------------------------------------------------------------
# FR-010: observed languages
# ---------------------------------------------------------------------------


def test_kotlin_and_typescript_list_both_primary_first(tmp_path: Path) -> None:
    signals = CodeReadingCollector(_kotlin_and_typescript(tmp_path)).collect()
    assert signals.primary_language == "kotlin"
    assert signals.scope_tag == "kotlin"
    assert signals.languages == ("kotlin", "typescript")


def test_nested_manifests_still_list_both_languages(tmp_path: Path) -> None:
    signals = CodeReadingCollector(_nested_polyglot(tmp_path)).collect()
    assert set(signals.languages) == {"kotlin", "typescript"}
    assert signals.languages[0] == signals.primary_language


def test_go_and_rust_are_listed_without_doctrine(tmp_path: Path) -> None:
    _write(tmp_path, "go.mod")
    _write(tmp_path, "main.go")
    _write(tmp_path, "Cargo.toml")
    for index in range(3):
        _write(tmp_path, f"src/m{index}.rs")
    signals = CodeReadingCollector(tmp_path).collect()
    assert signals.languages == ("rust", "go")
    assert signals.primary_language == "rust"


def test_residue_below_the_threshold_is_not_listed(tmp_path: Path) -> None:
    _python_only(tmp_path)
    for index in range(8):
        _write(tmp_path, f"src/m{index}.py")
    _write(tmp_path, "karma.conf.js")
    _write(tmp_path, "scripts/build.js")
    signals = CodeReadingCollector(tmp_path).collect()
    assert signals.languages == ("python",)


def test_single_language_repository_lists_one_entry(tmp_path: Path) -> None:
    signals = CodeReadingCollector(_python_only(tmp_path)).collect()
    assert signals.languages == ("python",)


def test_share_rule_adds_a_language_without_a_manifest(tmp_path: Path) -> None:
    """TypeScript has no manifest anywhere, yet its share of the sources (>= 20%) lists it."""
    _python_only(tmp_path)
    for index in range(2):
        _write(tmp_path, f"src/extra{index}.py")
    for index in range(3):
        _write(tmp_path, f"web/t{index}.ts")
    # Essential, not a workaround: a single-language repository never runs the uncapped source
    # count (NFR-005), so the share rule only fires once a second manifest (here ``go.mod``)
    # names another language. TypeScript itself still has no manifest.
    _write(tmp_path, "go.mod")
    signals = CodeReadingCollector(tmp_path).collect()
    assert "typescript" in signals.languages
    assert signals.languages[0] == signals.primary_language


def test_share_rule_runs_when_a_deeper_manifest_names_another_language(tmp_path: Path) -> None:
    """Backend at the root, frontend in a subdirectory: the deeper manifest must not hide it."""
    _write(tmp_path, "pyproject.toml", "[project]\nname='x'\n")
    for index in range(2):
        _write(tmp_path, f"src/m{index}.py")
    _write(tmp_path, "web/package.json", "{}")
    _write(tmp_path, "web/tsconfig.json", "{}")
    for index in range(8):
        _write(tmp_path, f"web/src/t{index}.ts")
    signals = CodeReadingCollector(tmp_path).collect()
    assert signals.primary_language == "python"
    assert signals.languages == ("python", "typescript")


def test_unknown_repository_lists_nothing(tmp_path: Path) -> None:
    signals = CodeReadingCollector(tmp_path).collect()
    assert signals.primary_language == "unknown"
    assert signals.languages == ()


def test_single_language_non_jvm_repository_walks_the_tree_once(tmp_path: Path) -> None:
    _python_only(tmp_path)
    with patch("charter.activation.evidence.code_reader.count_sources_uncapped") as uncapped:
        CodeReadingCollector(tmp_path).collect()
    uncapped.assert_not_called()


def test_polyglot_repository_counts_sources_once(tmp_path: Path) -> None:
    import charter.activation.evidence.code_reader as reader

    real = reader.count_sources_uncapped
    calls: list[Path] = []

    def counting(root: Path) -> Counter[str]:
        calls.append(root)
        return real(root)

    with patch.object(reader, "count_sources_uncapped", counting):
        CodeReadingCollector(_kotlin_and_typescript(tmp_path)).collect()
    assert len(calls) == 1


def test_signals_reject_languages_not_led_by_the_primary() -> None:
    with pytest.raises(ValueError, match="languages must start with primary_language"):
        _signals(languages=("go", "python"))


# ---------------------------------------------------------------------------
# FR-012: stable hash
# ---------------------------------------------------------------------------


def test_single_language_evidence_hash_is_pinned(tmp_path: Path) -> None:
    signals = CodeReadingCollector(_python_only(tmp_path)).collect()
    assert _hash(signals) == _PYTHON_ONLY_HASH


def test_one_language_does_not_enter_the_hash() -> None:
    assert _hash(_signals(languages=("python",))) == _hash(_signals())


def test_polyglot_languages_enter_the_hash() -> None:
    base = _hash(_signals())
    poly = _hash(_signals(languages=("python", "go")))
    assert poly != base
    assert poly != _hash(_signals(languages=("python", "rust")))


# ---------------------------------------------------------------------------
# FR-011: neutrality gate
# ---------------------------------------------------------------------------


def _bundle(*languages: str) -> EvidenceBundle:
    primary = languages[0]
    return EvidenceBundle(code_signals=_signals(stack_id=primary, primary_language=primary, scope_tag=primary, languages=tuple(languages)))


@pytest.mark.parametrize("slug", ["kotlin-style-guide", "typescript-style-guide", "jvm-build-guide"])
def test_gate_exempts_any_observed_language_or_its_family(slug: str) -> None:
    assert _is_generic_scoped("tactic", slug, _bundle("kotlin", "typescript")) is False


def test_gate_still_lints_generic_slugs_in_a_polyglot_repository() -> None:
    assert _is_generic_scoped("tactic", "testing-philosophy", _bundle("kotlin", "typescript")) is True
    assert _is_generic_scoped("tactic", "java-style-guide", _bundle("kotlin", "typescript")) is True


def test_gate_exempts_a_declared_language() -> None:
    assert _is_generic_scoped("tactic", "go-style-guide", _bundle("python"), ("go",)) is False
    assert _is_generic_scoped("tactic", "go-style-guide", None, ("go",)) is False
    assert _is_generic_scoped("tactic", "testing-philosophy", _bundle("python"), ("go",)) is True


def test_gate_treats_unknown_scope_as_generic() -> None:
    unknown = EvidenceBundle(code_signals=_signals(stack_id="unknown", primary_language="unknown", scope_tag="unknown"))
    assert _is_generic_scoped("tactic", "unknown-style-guide", unknown) is True


def test_declared_languages_come_from_language_scope_or_the_alias() -> None:
    from charter.activation.synthesizer.write_pipeline import _declared_scope_languages

    assert _declared_scope_languages({"language_scope": ["Go", " Rust "]}) == ("go", "rust")
    assert _declared_scope_languages({"languages_frameworks": "Kotlin and Spring"}) == ("kotlin",)
    assert _declared_scope_languages({"languages_frameworks": ["Kotlin", "Gradle"]}) == ("kotlin",)
    assert _declared_scope_languages({"testing_philosophy": "x"}) == ()


def test_language_scope_entries_resolve_through_the_language_authority() -> None:
    from charter.activation.synthesizer.write_pipeline import _declared_scope_languages

    declared = _declared_scope_languages({"language_scope": ["Kotlin and Spring"]})
    assert declared == ("kotlin",)
    assert _is_generic_scoped("tactic", "kotlin-style-guide", None, declared) is False
    assert _declared_scope_languages({"language_scope": ["Gradle"]}) == ("jvm",)


# ---------------------------------------------------------------------------
# Corpus: primary language only
# ---------------------------------------------------------------------------


def _corpus(root: Path, language: str) -> None:
    _write(
        root,
        f"{language}.corpus.yaml",
        f"snapshot_id: {language}-v1.0.0\nprofile_key: {language}\nentries:\n  - topic: t\n    tags: [a]\n    guidance: g\n",
    )


def test_corpus_is_chosen_by_the_primary_language_only(tmp_path: Path) -> None:
    repo = _kotlin_and_typescript(tmp_path / "repo")
    corpus_root = tmp_path / "corpus"
    _corpus(corpus_root, "typescript")
    result = EvidenceOrchestrator(repo_root=repo, corpus_root=corpus_root).collect()
    assert result.bundle.code_signals is not None
    assert result.bundle.code_signals.languages == ("kotlin", "typescript")
    # typescript is observed but is not the primary: its corpus is not loaded.
    assert result.bundle.corpus_snapshot is None
    _corpus(corpus_root, "kotlin")
    again = EvidenceOrchestrator(repo_root=repo, corpus_root=corpus_root).collect()
    assert again.bundle.corpus_snapshot is not None
    assert again.bundle.corpus_snapshot.snapshot_id == "kotlin-v1.0.0"


# ---------------------------------------------------------------------------
# FR-014: additive JSON
# ---------------------------------------------------------------------------

_STATUS_CODE_KEYS = {
    "stack_id",
    "primary_language",
    "frameworks",
    "test_frameworks",
    "representative_files_count",
    "representative_files_preview",
}


def test_status_json_carries_languages_and_keeps_every_key(tmp_path: Path) -> None:
    repo = _kotlin_and_typescript(tmp_path)
    with (
        patch("specify_cli.cli.commands.charter.find_repo_root", return_value=repo),
        patch("specify_cli.cli.commands.charter.ensure_charter_bundle_fresh", side_effect=TaskCliError("Charter not found")),
    ):
        result = runner.invoke(app, ["status", "--json"])
    assert result.exit_code == 0, result.output
    code = json.loads(result.output)["synthesis"]["evidence"]["code"]
    assert code["languages"] == ["kotlin", "typescript"]
    assert code["primary_language"] == "kotlin"
    assert set(code) >= _STATUS_CODE_KEYS


def test_synthesize_dry_run_evidence_json_carries_languages(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _kotlin_and_typescript(tmp_path)
    monkeypatch.chdir(repo)  # the charter write-root probe refuses a linked worktree cwd
    with patch("specify_cli.cli.commands.charter.find_repo_root", return_value=repo):
        result = runner.invoke(app, ["synthesize", "--adapter", "fixture", "--dry-run-evidence", "--json"])
    assert result.exit_code == 0, result.output
    code = json.loads(result.output)["evidence"]["code_signals"]
    assert code["languages"] == ["kotlin", "typescript"]
    assert set(code) >= {"stack_id", "primary_language", "representative_files_count"}
