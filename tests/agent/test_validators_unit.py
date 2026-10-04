"""Unit tests for mission validators (citations, paths, etc.)."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from specify_cli.validators.research import (
    CitationIssue,
    CitationValidationResult,
    CitationFormat,
    detect_citation_format,
    is_apa_format,
    is_bibtex_format,
    is_simple_format,
    validate_citations,
    validate_source_register,
)
from specify_cli.validators.paths import (
    PathValidationError,
    PathValidationResult,
    artifact_tokens_for_mission,
    suggest_directory_creation,
    validate_mission_paths,
)


pytestmark = [pytest.mark.unit, pytest.mark.fast]

@pytest.fixture
def valid_evidence_log(tmp_path: Path) -> Path:
    csv_file = tmp_path / "evidence-log.csv"
    csv_file.write_text(
        "timestamp,source_type,citation,key_finding,confidence,notes\n"
        '2025-01-15T10:00:00,journal,"Smith, J. (2024). Title. Journal.",Finding text,high,Notes here\n'
        '2025-01-15T11:00:00,conference,"@inproceedings{jones2024,author={Jones}}",Another finding,medium,\n',
        encoding="utf-8",
    )
    return csv_file


@pytest.fixture
def invalid_evidence_log(tmp_path: Path) -> Path:
    csv_file = tmp_path / "evidence-log.csv"
    csv_file.write_text(
        "timestamp,source_type,citation,key_finding,confidence,notes\n"
        "2025-01-15T10:00:00,invalid,,Empty citation,high,\n"
        "2025-01-15T11:00:00,journal,Not a real citation,Finding,wrong,\n",
        encoding="utf-8",
    )
    return csv_file


@pytest.fixture
def valid_source_register(tmp_path: Path) -> Path:
    csv_file = tmp_path / "source-register.csv"
    csv_file.write_text(
        "source_id,citation,url,accessed_date,relevance,status\n"
        'smith2024,"Smith, J. (2024). Title. Journal.",https://doi.org/10.0/abc,2025-01-15,high,reviewed\n'
        'jones2024,"@inproceedings{jones2024,author={Jones}}",https://dl.acm.org/xyz,2025-01-16,medium,pending\n',
        encoding="utf-8",
    )
    return csv_file


@pytest.fixture
def invalid_source_register(tmp_path: Path) -> Path:
    csv_file = tmp_path / "source-register.csv"
    csv_file.write_text(
        "source_id,citation,url,accessed_date,relevance,status\n"
        ",,,2025-01-15,invalid,done\n"
        "dup,Duplicate citation,,2025-01-16,high,reviewed\n"
        "dup,Duplicate citation,,2025-01-17,high,reviewed\n",
        encoding="utf-8",
    )
    return csv_file


def test_bibtex_format_detection() -> None:
    assert is_bibtex_format("@article{smith2024, title={Title}}")
    assert not is_bibtex_format("Smith, J. (2024). Title.")


def test_apa_format_detection() -> None:
    assert is_apa_format("Smith, J. (2024). Title. Journal, 10(2), 123-145.")
    assert not is_apa_format("@article{smith2024, title={Title}}")


def test_simple_format_detection() -> None:
    assert is_simple_format("Smith (2024). Title. Source.")
    assert not is_simple_format("No year or punctuation")


def test_citation_format_detection() -> None:
    assert detect_citation_format("@article{smith2024,") is CitationFormat.BIBTEX
    assert detect_citation_format("Smith, J. (2024). Title.") is CitationFormat.APA
    assert detect_citation_format("Smith (2024). Title. Source.") is CitationFormat.SIMPLE
    assert detect_citation_format("invalid citation") is CitationFormat.UNKNOWN


def test_validate_citations_valid_file(valid_evidence_log: Path) -> None:
    result = validate_citations(valid_evidence_log)
    assert result.total_entries == 2
    assert result.error_count == 0
    # warnings allowed for certain rows
    assert result.valid_entries == 2


def test_validate_citations_invalid_file(invalid_evidence_log: Path) -> None:
    result = validate_citations(invalid_evidence_log)
    assert result.has_errors
    assert result.error_count >= 2
    assert result.total_entries == 2


def test_validate_citations_missing_file(tmp_path: Path) -> None:
    missing = tmp_path / "missing.csv"
    result = validate_citations(missing)
    assert result.has_errors
    assert "not found" in result.issues[0].message.lower()


def test_validate_source_register_valid_file(valid_source_register: Path) -> None:
    result = validate_source_register(valid_source_register)
    assert result.total_entries == 2
    assert result.error_count == 0
    assert result.valid_entries == 2


def test_validate_source_register_invalid_file(invalid_source_register: Path) -> None:
    result = validate_source_register(invalid_source_register)
    assert result.has_errors
    assert result.error_count >= 3  # empty id, duplicate id, invalid enums


def test_validate_source_register_missing_file(tmp_path: Path) -> None:
    missing = tmp_path / "missing.csv"
    result = validate_source_register(missing)
    assert result.has_errors
    assert "not found" in result.issues[0].message.lower()


def test_validation_result_format_report() -> None:
    result = CitationValidationResult(
        file_path=Path("test.csv"),
        total_entries=3,
        valid_entries=1,
        issues=[
            CitationIssue(2, "citation", "error", "Citation empty"),
            CitationIssue(3, "source_type", "warning", "Format warning"),
        ],
    )
    report = result.format_report()
    assert "ERRORS" in report
    assert "WARNINGS" in report
    assert "Line 2" in report


class _MissionStub:
    """Minimal mission-like object for path validator tests."""

    def __init__(
        self,
        name: str,
        paths: dict[str, str],
        *,
        required_artifacts: tuple[str, ...] = (),
        optional_artifacts: tuple[str, ...] = (),
    ) -> None:
        self.name = name
        self.config = SimpleNamespace(
            paths=paths,
            artifacts=SimpleNamespace(
                required=list(required_artifacts),
                optional=list(optional_artifacts),
            ),
        )


def test_validate_paths_all_exist(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()

    mission = _MissionStub("Software Dev Kitty", {"workspace": "src/", "tests": "tests/"})
    result = validate_mission_paths(mission, tmp_path, strict=False)

    assert result.is_valid
    assert result.existing_paths == ["src/", "tests/"]
    assert not result.warnings


def test_validate_paths_warns_when_missing(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    mission = _MissionStub("Software Dev Kitty", {"workspace": "src/", "tests": "tests/"})

    result = validate_mission_paths(mission, tmp_path, strict=False)

    assert not result.is_valid
    assert result.missing_paths == ["tests/"]
    assert any("tests/" in warning for warning in result.warnings)
    assert any("mkdir -p tests/" in suggestion for suggestion in result.suggestions)


def test_validate_paths_strict_mode_raises(tmp_path: Path) -> None:
    mission = _MissionStub("Software Dev Kitty", {"workspace": "src/"})

    with pytest.raises(PathValidationError) as excinfo:
        validate_mission_paths(mission, tmp_path, strict=True)

    assert excinfo.value.result.missing_paths == ["src/"]
    assert "Path Convention Errors" in excinfo.value.result.format_errors()


def test_override_remaps_workspace_to_apps(tmp_path: Path) -> None:
    """#3016: a project path_conventions override remaps the declared source root so a non-``src`` repo
    (Django ``apps/``) validates without fabricating ``src/`` and without ``--lenient``."""
    (tmp_path / "apps").mkdir()
    mission = _MissionStub("Software Dev Kitty", {"workspace": "src/", "tests": "apps/"})

    result = validate_mission_paths(
        mission, tmp_path, strict=False, path_overrides={"workspace": "apps/", "tests": "apps/"}
    )

    assert result.is_valid
    assert "apps/" in result.existing_paths
    assert not any("src/" in warning for warning in result.warnings)


def test_override_declared_but_absent_still_blocks(tmp_path: Path) -> None:
    """SC-006 (non-fakeable discriminator): an override changes WHICH directory is expected, not WHETHER
    it is enforced — a declared-but-absent ``apps/`` still blocks under strict mode."""
    mission = _MissionStub("Software Dev Kitty", {"workspace": "src/"})

    with pytest.raises(PathValidationError) as excinfo:
        validate_mission_paths(mission, tmp_path, strict=True, path_overrides={"workspace": "apps/"})

    assert excinfo.value.result.missing_paths == ["apps/"]


def test_override_only_remaps_declared_keys(tmp_path: Path) -> None:
    """C-010 remap-only: an override for a key the mission does not declare adds no new required path."""
    (tmp_path / "src").mkdir()
    mission = _MissionStub("Software Dev Kitty", {"workspace": "src/"})

    result = validate_mission_paths(
        mission, tmp_path, strict=False, path_overrides={"workspace": "src/", "data": "datadir/"}
    )

    assert result.is_valid
    assert result.missing_paths == []


def test_mission_artifact_path_resolves_against_feature_dir(tmp_path: Path) -> None:
    """A declared path that is also a mission artifact (e.g. ``contracts/``) is
    resolved against the mission's feature_dir, while build paths (``src/``) stay
    at the repo root (#2115). No repo-root fallback for the artifact path.
    """
    repo_root = tmp_path / "repo"
    (repo_root / "src").mkdir(parents=True)  # build path → repo root
    feature_dir = repo_root / "kitty-specs" / "010-feature"
    (feature_dir / "contracts").mkdir(parents=True)  # mission artifact → feature_dir
    # NOTE: contracts/ deliberately does NOT exist at repo_root.

    mission = _MissionStub(
        "Software Dev Kitty",
        {"workspace": "src/", "deliverables": "contracts/"},
        optional_artifacts=("contracts/",),
    )

    result = validate_mission_paths(
        mission, repo_root, strict=False, feature_dir=feature_dir
    )

    assert result.is_valid, result.warnings
    assert set(result.existing_paths) == {"src/", "contracts/"}
    assert not result.missing_paths


def test_mission_artifact_path_without_feature_dir_misses_at_repo_root(
    tmp_path: Path,
) -> None:
    """Non-vacuity / documents the pre-#2115 bug: with no feature_dir, ``contracts/``
    (a mission artifact under the feature dir) is wrongly sought at the repo root
    and reported missing — the false positive the fix removes by passing feature_dir.
    """
    repo_root = tmp_path / "repo"
    (repo_root / "src").mkdir(parents=True)
    feature_dir = repo_root / "kitty-specs" / "010-feature"
    (feature_dir / "contracts").mkdir(parents=True)

    mission = _MissionStub(
        "Software Dev Kitty",
        {"workspace": "src/", "deliverables": "contracts/"},
        optional_artifacts=("contracts/",),
    )

    # Pre-fix call shape (no feature_dir) — contracts/ resolves at repo_root → missing.
    result = validate_mission_paths(mission, repo_root, strict=False)

    assert result.missing_paths == ["contracts/"]


def test_artifact_tokens_for_mission_defensive_fallback_when_artifacts_missing() -> None:
    """``artifact_tokens_for_mission`` is explicitly defensive (see its own
    docstring): a real ``MissionConfig`` always carries ``artifacts``, but a
    partial mock/config that omits it entirely must fall back to "no artifact
    paths" (empty set) via the ``getattr`` chain, not raise ``AttributeError`` —
    the same fallback ``validate_mission_paths`` already applies elsewhere.
    """
    mission = SimpleNamespace(config=SimpleNamespace())  # no `artifacts` attribute at all

    assert artifact_tokens_for_mission(mission) == set()


def test_non_artifact_path_stays_repo_root_even_with_feature_dir(tmp_path: Path) -> None:
    """A declared path that is NOT a mission artifact (``tests/``) resolves against
    the repo root even when feature_dir is supplied — build paths are repo-relative.
    """
    repo_root = tmp_path / "repo"
    (repo_root / "tests").mkdir(parents=True)  # exists at repo root
    feature_dir = repo_root / "kitty-specs" / "010-feature"
    (feature_dir / "tests").mkdir(parents=True)  # decoy under feature_dir

    mission = _MissionStub("Software Dev Kitty", {"tests": "tests/"})

    result = validate_mission_paths(
        mission, repo_root, strict=False, feature_dir=feature_dir
    )

    # tests/ is not a mission artifact → repo-root resolution; present there → valid.
    assert result.is_valid
    assert result.existing_paths == ["tests/"]


def test_missing_artifact_tagged_path_reports_resolved_feature_relative_location(
    tmp_path: Path,
) -> None:
    """Case A (WP01 T003): a missing, mission-artifact-tagged path (``contracts/``)
    must be reported — in ``missing_paths``, ``suggestions``, AND ``warnings`` — as
    the resolved ``feature_dir``-relative location that was actually tested, not the
    bare declared token (#3085a). ``missing_artifact_tokens`` must carry the
    real feature_dir-relative token for this branch.
    """
    project_root = tmp_path / "repo"
    project_root.mkdir(parents=True)
    (project_root / "src").mkdir()
    feature_dir = project_root / "kitty-specs" / "some-slug"
    feature_dir.mkdir(parents=True)
    # NOTE: contracts/ deliberately absent under feature_dir.

    mission = _MissionStub(
        "Software Dev Kitty",
        {"workspace": "src/", "deliverables": "contracts/"},
        optional_artifacts=("contracts/",),
    )

    result = validate_mission_paths(
        mission, project_root, strict=False, feature_dir=feature_dir
    )

    resolved = "kitty-specs/some-slug/contracts/"
    bare_token = "contracts/"

    assert result.missing_paths == [resolved]
    assert bare_token not in result.missing_paths

    assert any(resolved in suggestion for suggestion in result.suggestions)
    # The old (buggy) suggestion named the bare token alone — assert that
    # exact wrong-directory remedy is gone, not merely that a substring match
    # happens to appear (the fixed resolved string legitimately ends with the
    # bare token as a path segment: ".../contracts/").
    assert f"mkdir -p {bare_token}" not in result.suggestions

    assert any(resolved in warning for warning in result.warnings)
    assert not any(bare_token in warning and resolved not in warning for warning in result.warnings)

    # T002: the field carries the real feature_dir-relative token (stripped).
    assert result.missing_artifact_tokens == ["contracts"]


def test_missing_build_path_stays_project_root_relative_unchanged(
    tmp_path: Path,
) -> None:
    """Case B (WP01 T004): a missing, NON-artifact-tagged build/repo-root path
    (``tests/``) must keep reporting the exact same project_root-relative string as
    before this fix — a regression guard that the artifact-tagged branch's namespace
    change (Case A) does not leak into the build/repo-root branch.
    """
    project_root = tmp_path / "repo"
    project_root.mkdir(parents=True)
    feature_dir = project_root / "kitty-specs" / "some-slug"
    feature_dir.mkdir(parents=True)
    # NOTE: tests/ deliberately absent at project_root.

    mission = _MissionStub("Software Dev Kitty", {"tests": "tests/"})

    result = validate_mission_paths(
        mission, project_root, strict=False, feature_dir=feature_dir
    )

    expected = "tests/"  # unchanged pre-WP1 value for this branch/fixture

    assert result.missing_paths == [expected]
    assert any(expected in warning for warning in result.warnings)

    # A non-artifact build/repo-root path is never a declared mission
    # artifact, so it can never survive the sole consumer's artifact_tokens
    # membership filter (summary_core.evaluate_path_conventions) — the
    # build/repo-root branch stays out of missing_artifact_tokens entirely.
    assert result.missing_artifact_tokens == []


def test_merge_site_ignores_deliverables_override_even_when_passed_directly(
    tmp_path: Path,
) -> None:
    """Defense-in-depth (adversarial squad fix #3): the reader already strips an artifact-routed
    ``deliverables`` override, but ``_remap_declared_paths``/``validate_mission_paths`` must ALSO ignore
    one, in case a future caller constructs ``path_overrides`` some other way. Routing must not flip.
    """
    repo_root = tmp_path / "repo"
    feature_dir = repo_root / "kitty-specs" / "010-feature"
    (feature_dir / "contracts").mkdir(parents=True)
    (repo_root / "src").mkdir(parents=True)

    mission = _MissionStub(
        "Software Dev Kitty",
        {"workspace": "src/", "deliverables": "contracts/"},
        optional_artifacts=("contracts/",),
    )

    result = validate_mission_paths(
        mission,
        repo_root,
        strict=False,
        feature_dir=feature_dir,
        path_overrides={"deliverables": "somewhere-else/"},
    )

    assert result.is_valid, result.warnings
    assert result.required_paths["deliverables"] == "contracts/"
    assert "somewhere-else/" not in result.required_paths.values()


def test_override_value_colliding_with_artifact_token_is_dropped(tmp_path: Path) -> None:
    """Adversarial squad fix #4: an override VALUE that collides with a mission artifact token (e.g.
    ``workspace`` -> ``"contracts"``) must be dropped (with a warning), not silently applied — applying
    it would flip ``workspace``'s routing onto ``feature_dir`` and let the real artifact directory
    spuriously satisfy a check that should test the project's actual workspace location.
    """
    repo_root = tmp_path / "repo"
    feature_dir = repo_root / "kitty-specs" / "010-feature"
    (feature_dir / "contracts").mkdir(parents=True)
    # NOTE: src/ deliberately absent at repo_root — if the override were honored, "contracts" would
    # resolve under feature_dir (which exists) and the workspace check would wrongly pass.

    mission = _MissionStub(
        "Software Dev Kitty",
        {"workspace": "src/", "deliverables": "contracts/"},
        optional_artifacts=("contracts/",),
    )

    with pytest.warns(UserWarning, match="workspace"):
        result = validate_mission_paths(
            mission,
            repo_root,
            strict=False,
            feature_dir=feature_dir,
            path_overrides={"workspace": "contracts"},
        )

    assert result.required_paths["workspace"] == "src/"
    assert "src/" in result.missing_paths


def test_suggest_directory_creation_handles_files_and_dirs() -> None:
    suggestions = suggest_directory_creation(["src/", "tests/", "README.md", "scripts"])
    joined = "Create directories in one go" in suggestions[0]
    assert joined
    assert any("touch README.md" in suggestion for suggestion in suggestions)
    assert any("mkdir -p scripts" in suggestion for suggestion in suggestions)


def test_path_validation_result_formatters() -> None:
    result = PathValidationResult(
        mission_name="Research Kitty",
        required_paths={"workspace": "research/"},
        existing_paths=[],
        missing_paths=["research/"],
        warnings=["Research Kitty expects workspace path: research/ (not found)"],
        suggestions=["mkdir -p research/"],
    )

    warnings_text = result.format_warnings()
    errors_text = result.format_errors()

    assert "Path Convention Warnings" in warnings_text
    assert "Suggestions" in warnings_text
    assert "Path Convention Errors" in errors_text
    assert "Research Kitty" in errors_text


def test_format_errors_names_lenient_before_mkdir_and_drops_unconditional_claim() -> None:
    """FR-004/FR-005/AC4 (#3730): the strict-mode failure text must not assert an
    unconditional "required" claim that ``accept --lenient`` immediately disproves,
    and must name ``--lenient`` as a remedy *before* any ``mkdir -p`` suggestion so
    an operator reads the honest escape hatch first.
    """
    result = PathValidationResult(
        mission_name="Software Dev Kitty",
        required_paths={"workspace": "src/"},
        existing_paths=[],
        missing_paths=["src/"],
        warnings=["Software Dev Kitty expects workspace path: src/ (not found)"],
        suggestions=["mkdir -p src/"],
    )

    output = result.format_errors()

    assert "--lenient" in output
    assert "mkdir -p" in output
    assert output.index("--lenient") < output.index("mkdir -p")
    assert "are required by the active mission" not in output


def test_waived_artifact_path_is_not_required(tmp_path: Path) -> None:
    """#5298: a waived mission-artifact token (``contracts``) is skipped."""
    repo_root = tmp_path / "repo"
    (repo_root / "src").mkdir(parents=True)
    feature_dir = repo_root / "kitty-specs" / "010-mission"
    feature_dir.mkdir(parents=True)
    mission = _MissionStub(
        "Software Dev Kitty",
        {"workspace": "src/", "deliverables": "contracts/"},
        optional_artifacts=("contracts/",),
    )

    result = validate_mission_paths(
        mission, repo_root, strict=False, feature_dir=feature_dir, waived_artifact_tokens=frozenset({"contracts"})
    )

    assert result.is_valid, result.warnings
    assert result.existing_paths == ["src/"]


def test_a_build_path_is_never_waived(tmp_path: Path) -> None:
    """#5298: only ARTIFACT-tagged paths can be waived -- a build path whose token
    happens to be in the waived set is still required at the repo root."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    feature_dir = repo_root / "kitty-specs" / "010-mission"
    feature_dir.mkdir(parents=True)
    mission = _MissionStub("Software Dev Kitty", {"tests": "tests/"}, optional_artifacts=("contracts/",))

    result = validate_mission_paths(
        mission, repo_root, strict=False, feature_dir=feature_dir, waived_artifact_tokens=frozenset({"tests"})
    )

    assert result.missing_paths == ["tests/"]
