"""Red-first coverage for the doubled-leaf synthesis-writer defect (#3819).

Background / investigation summary
-----------------------------------
Issue #3819 was filed after a doubled-leaf write was found committed into a
PR: byte-identical duplicates at ``.kittify/charter/provenance/provenance/
<file>`` and ``.kittify/charter-packs/styleguide/styleguide/<file>`` — a leaf
directory appended onto a base that already ends in that same leaf.

This WP's brief pointed at ``src/charter/bundle.py`` (``PROVENANCE_DIR``) and
``src/charter/activation/synthesizer/manifest.py`` (``_PROVENANCE_PATH_PREFIX``)
as the writer. Investigation (driving the full public synthesis pipeline —
``charter.activation.synthesizer.orchestrator.synthesize()`` — repeatedly
against a ``tmp_path`` project with the exact fixture set that produced the
historically-doubled files, plus a full static read of every path-join in
``write_pipeline.py``/``staging.py``/``manifest.py``) found the actual
artifact writer is ``write_pipeline.py`` (not owned by this WP), and its
current path-join logic does **not** double any path — see
``TestFullSynthesisProducesNoDoubledPaths`` below, which exercises that
public entry point directly and passes today without modification.

Neither ``manifest.py`` nor ``bundle.py`` (this WP's owned surface) contains
any artifact-file-writing path-join at all: ``manifest.py`` only serializes
the ``synthesis-manifest.yaml`` *document*, and its ``_PROVENANCE_PATH_PREFIX``
is used solely to *validate* (``Path.relative_to``) an already-complete
manifest-entry path, never to construct one. ``bundle.py`` is a read-only
validator.

What **is** a genuine, provable, in-scope gap: ``bundle.py``'s
``validate_synthesis_state()`` recursively globs for artifacts
(``pack_root.rglob(f"*{suffix}")``) and keys its cross-checks off
``Path.name`` alone. A doubled-leaf copy shares its correctly-placed
sibling's basename, so the existing checks (``_check_artifacts_have_
provenance`` / ``_check_provenance_have_artifacts``) never flag it — the
corruption is invisible to the one function whose job is to catch exactly
this kind of on-disk inconsistency. ``TestDoubledLeafDetection`` below is the
literal red-first test for that gap: red before ``_check_no_doubled_leaf_paths``
existed, green after.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from charter.bundle import validate_synthesis_state
from charter.activation.synthesizer.synthesize_pipeline import canonical_yaml

pytestmark = [pytest.mark.unit]


# ---------------------------------------------------------------------------
# Shared fixture helpers (mirrors tests/charter/synthesizer/test_bundle_
# validate_extension.py's on-disk fixture-building style)
# ---------------------------------------------------------------------------


def _tactic_body(slug: str = "my-tactic") -> bytes:
    # Explicit annotation: the ``charter.*`` mypy override (pyproject.toml
    # [[tool.mypy.overrides]]) sets follow_imports="skip" for intra-package
    # imports, which erases canonical_yaml's declared "-> bytes" return type
    # to Any at this call site.
    body: bytes = canonical_yaml({"id": slug, "title": "My Tactic", "summary": "A tactic."})
    return body


def _write_artifact(repo: Path, subdir: str, filename: str, content: bytes) -> Path:
    path = repo / ".kittify" / "charter-packs" / subdir / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def _write_provenance(repo: Path, filename: str, content: str) -> Path:
    path = repo / ".kittify" / "charter" / "provenance" / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return path


def _minimal_valid_provenance(kind: str, slug: str) -> str:
    """A minimally-valid provenance sidecar body (parseable YAML mapping)."""
    return f"artifact_urn: '{kind}:{slug}'\nartifact_kind: '{kind}'\nartifact_slug: '{slug}'\n"


# ---------------------------------------------------------------------------
# T012 (red-first): validate_synthesis_state must detect a doubled-leaf
# artifact directory. This is genuinely red before bundle.py's
# _check_no_doubled_leaf_paths existed — the pre-existing checks are blind
# to it (see module docstring) — and green after.
# ---------------------------------------------------------------------------


class TestDoubledLeafDetection:
    def test_flags_doubled_provenance_directory(self, tmp_path: Path) -> None:
        """A byte-identical duplicate under provenance/provenance/ is an error."""
        body = _minimal_valid_provenance("tactic", "my-tactic")
        _write_artifact(tmp_path, "tactic", "my-tactic.tactic.yaml", _tactic_body())
        _write_provenance(tmp_path, "tactic-my-tactic.yaml", body)

        # The doubled-leaf write: same bytes, nested one level too deep.
        _write_provenance(tmp_path, "provenance/tactic-my-tactic.yaml", body)

        result = validate_synthesis_state(tmp_path)

        assert not result.passed, "validate_synthesis_state() must fail when a doubled-leaf provenance/provenance/ artifact is present (#3819)"
        assert any("provenance/provenance" in err or "#3819" in err for err in result.errors), f"expected a doubled-leaf error, got: {result.errors}"

    def test_flags_doubled_styleguide_directory(self, tmp_path: Path) -> None:
        """A byte-identical duplicate under doctrine/styleguide/styleguide/ is an error."""
        body = canonical_yaml({"id": "python-style-guide", "title": "Python Style Guide"})
        _write_artifact(tmp_path, "styleguide", "python-style-guide.styleguide.yaml", body)
        _write_provenance(
            tmp_path,
            "styleguide-python-style-guide.yaml",
            _minimal_valid_provenance("styleguide", "python-style-guide"),
        )

        # The doubled-leaf write: same bytes, nested under styleguide/styleguide/.
        _write_artifact(
            tmp_path,
            "styleguide/styleguide",
            "python-style-guide.styleguide.yaml",
            body,
        )

        result = validate_synthesis_state(tmp_path)

        assert not result.passed, "validate_synthesis_state() must fail when a doubled-leaf doctrine/styleguide/styleguide/ artifact is present (#3819)"
        assert any("styleguide/styleguide" in err or "#3819" in err for err in result.errors), f"expected a doubled-leaf error, got: {result.errors}"

    def test_clean_bundle_without_doubled_leaf_still_passes(self, tmp_path: Path) -> None:
        """The new check must not false-positive on a normal, non-doubled bundle."""
        body = _tactic_body()
        _write_artifact(tmp_path, "tactic", "my-tactic.tactic.yaml", body)
        _write_provenance(
            tmp_path,
            "tactic-my-tactic.yaml",
            _minimal_valid_provenance("tactic", "my-tactic"),
        )

        result = validate_synthesis_state(tmp_path)

        assert result.passed, f"expected a clean bundle to pass, got errors: {result.errors}"


# ---------------------------------------------------------------------------
# Regression guard: drive the actual public synthesis entry point
# (orchestrator.synthesize(), via FixtureAdapter — same fixture set that
# historically produced the doubled files, see PR that filed #3819) against
# a tmp_path project and assert no doubled-path artifact results. This
# passes today (no reproducible defect found in the current writer — see
# module docstring) and locks the SC-004 acceptance criterion in place.
# ---------------------------------------------------------------------------


class TestFullSynthesisProducesNoDoubledPaths:
    @pytest.fixture
    def _fixture_root(self) -> Path:
        return Path(__file__).parent / "fixtures" / "synthesizer"

    def test_synthesize_and_resynthesize_produce_no_doubled_paths(self, tmp_path: Path, _fixture_root: Path) -> None:
        from charter.activation.synthesizer import (
            FixtureAdapter,
            SynthesisRequest,
            SynthesisTarget,
            synthesize,
        )

        interview_snapshot = {
            "mission_type": "software_dev",
            "language_scope": ["python"],
            "testing_philosophy": "test-driven development with high coverage",
            "neutrality_posture": "balanced",
            "selected_directives": ["DIRECTIVE_003"],
            "risk_appetite": "moderate",
        }
        doctrine_snapshot = {
            "directives": {
                "DIRECTIVE_003": {
                    "id": "DIRECTIVE_003",
                    "title": "Decision Documentation",
                    "body": "Document significant architectural decisions via ADRs.",
                }
            },
            "tactics": {},
            "styleguides": {},
        }
        drg_snapshot = {
            "nodes": [{"urn": "directive:DIRECTIVE_003", "kind": "directive"}],
            "edges": [],
            "schema_version": "1",
        }

        adapter = FixtureAdapter(fixture_root=_fixture_root)
        target = SynthesisTarget(
            kind="directive",
            slug="mission-type-scope-directive",
            title="Mission Type Scope Directive",
            artifact_id="PROJECT_001",
            source_section="mission_type",
        )

        repo_root = tmp_path
        (repo_root / ".kittify" / "charter").mkdir(parents=True, exist_ok=True)
        (repo_root / ".kittify" / "charter-packs").mkdir(parents=True, exist_ok=True)

        # Run twice (a plain re-sync is the common real-world trigger for a
        # double-write defect if one exists in the writer).
        for run_id in (
            "01KPE222CD1MMCYEGB3ZCY51VR",
            "01KPE222CD1MMCYEGB3ZCY51VS",
        ):
            request = SynthesisRequest(
                target=target,
                interview_snapshot=interview_snapshot,
                doctrine_snapshot=doctrine_snapshot,
                drg_snapshot=drg_snapshot,
                run_id=run_id,
                adapter_hints={"language": "python"},
            )
            synthesize(request, adapter=adapter, repo_root=repo_root)

        doubled = [
            p.relative_to(repo_root).as_posix()
            for p in repo_root.rglob("*")
            if p.is_file()
            and (
                "provenance/provenance" in p.relative_to(repo_root).as_posix()
                or "styleguide/styleguide" in p.relative_to(repo_root).as_posix()
                or "directive/directive" in p.relative_to(repo_root).as_posix()
                or "tactic/tactic" in p.relative_to(repo_root).as_posix()
            )
        ]
        assert doubled == [], f"synthesis run produced doubled-path artifacts: {doubled}"

        result = validate_synthesis_state(repo_root)
        assert result.passed, f"expected the synthesized bundle to validate clean: {result.errors}"
