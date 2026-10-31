"""#6767 -- one reader of the synthesis ownership record, one unreadable-record error.

The record is the synthesis manifest plus each listed entry's provenance sidecar; the
created-artifacts record (``.kittify/charter/synthesized-artifacts.yaml``, with the legacy
tactics record unioned in) is its one documented fallback. Every unreadable condition raises
:class:`SynthesisMembershipUnreadableError` with the documented code, never an empty set.

Each absence assertion is paired with a positive control on the same fixture
(``acceptance-criteria-non-vacuity``).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Literal

import pytest

from charter.activation.synthesizer.errors import SynthesisMembershipUnreadableError
from charter.activation.synthesizer.manifest import (
    CREATED_ARTIFACTS_PATH,
    LEGACY_CREATED_ARTIFACTS_PATH,
    MANIFEST_PATH,
    ManifestArtifactEntry,
    SynthesisManifest,
    dump_yaml,
    finalize_manifest,
    manifest_slugs,
    read_created_record,
    sidecar_artifact_urn,
    synthesized_ids,
    synthesized_urns,
)
from charter.activation.synthesizer.path_guard import PathGuard
from charter.activation.synthesizer.provenance import ProvenanceEntry
from charter.activation.synthesizer.provenance import dump_yaml as dump_provenance

pytestmark = [pytest.mark.fast]

_OwnedKind = Literal["directive", "tactic", "styleguide"]
_RUN_ID = "01KPE222TESTRUNID0000000001"


@pytest.fixture
def guard(tmp_path: Path) -> PathGuard:
    return PathGuard(tmp_path, extra_allowed_prefixes=[tmp_path])


def _entry(kind: _OwnedKind, slug: str) -> ManifestArtifactEntry:
    return ManifestArtifactEntry(
        kind=kind,
        slug=slug,
        path=f".kittify/charter-packs/{kind}/{slug}.{kind}.yaml",
        provenance_path=f".kittify/charter/provenance/{kind}-{slug}.yaml",
        content_hash="a" * 64,
    )


def _sidecar(kind: _OwnedKind, slug: str, urn: str, *, adapter_id: str = "fixture") -> ProvenanceEntry:
    return ProvenanceEntry(
        artifact_urn=urn,
        artifact_kind=kind,
        artifact_slug=slug,
        artifact_content_hash="a" * 64,
        inputs_hash="b" * 64,
        adapter_id=adapter_id,
        adapter_version="1.0.0",
        synthesizer_version="3.2.0a5",
        source_section="mission_type",
        source_urns=[],
        source_input_ids=[],
        generated_at="2026-04-17T12:00:00+00:00",
        produced_at="2026-04-17T12:00:00+00:00",
        corpus_snapshot_id="(none)",
        synthesis_run_id=_RUN_ID,
    )


def _write_manifest(repo_root: Path, guard: PathGuard, entries: list[ManifestArtifactEntry]) -> None:
    manifest = finalize_manifest(
        SynthesisManifest(
            created_at="2026-04-17T12:00:00+00:00",
            run_id=_RUN_ID,
            adapter_id="fixture",
            adapter_version="1.0.0",
            synthesizer_version="3.2.0a5",
            manifest_hash="0" * 64,
            artifacts=entries,
        )
    )
    path = repo_root / MANIFEST_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    dump_yaml(manifest, path, guard)


def _write_sidecar(repo_root: Path, guard: PathGuard, sidecar: ProvenanceEntry) -> None:
    path = repo_root / f".kittify/charter/provenance/{sidecar.artifact_kind}-{sidecar.artifact_slug}.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    dump_provenance(sidecar, path, guard)


def _write_record(repo_root: Path, body: str, *, legacy: bool = False) -> None:
    path = repo_root / (LEGACY_CREATED_ARTIFACTS_PATH if legacy else CREATED_ARTIFACTS_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def _corrupt_manifest(repo_root: Path) -> None:
    path = repo_root / MANIFEST_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("artifacts: [this is: not a manifest\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# The happy paths
# ---------------------------------------------------------------------------


def test_absent_manifest_is_empty_and_reads_no_record(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Nothing was synthesized, so the created-artifacts record is never read."""

    def _no_read(_repo_root: Path) -> object:
        raise AssertionError("the created-artifacts record must not be read when the manifest is absent")

    monkeypatch.setattr("charter.activation.synthesizer.manifest.read_created_record", _no_read)

    assert synthesized_urns(tmp_path, "directive") == frozenset()
    assert synthesized_urns(tmp_path, "tactic") == frozenset()


def test_returns_only_the_requested_kind(tmp_path: Path, guard: PathGuard) -> None:
    entries = [_entry("directive", "project-intent-directive"), _entry("tactic", "review-policy-tactic")]
    _write_manifest(tmp_path, guard, entries)
    _write_sidecar(tmp_path, guard, _sidecar("directive", "project-intent-directive", "directive:PROJECT_001"))
    _write_sidecar(tmp_path, guard, _sidecar("tactic", "review-policy-tactic", "tactic:review-policy-tactic"))

    assert synthesized_urns(tmp_path, "directive") == frozenset({"directive:PROJECT_001"})
    assert synthesized_urns(tmp_path, "tactic") == frozenset({"tactic:review-policy-tactic"})
    assert synthesized_urns(tmp_path, "styleguide") == frozenset()


def test_synthesized_ids_are_the_urn_id_segment(tmp_path: Path, guard: PathGuard) -> None:
    _write_manifest(tmp_path, guard, [_entry("directive", "project-intent-directive")])
    _write_sidecar(tmp_path, guard, _sidecar("directive", "project-intent-directive", "directive:PROJECT_001"))

    assert synthesized_ids(tmp_path, "directive") == frozenset({"PROJECT_001"})


def test_direct_write_registration_is_not_ownership(tmp_path: Path, guard: PathGuard) -> None:
    entries = [_entry("directive", "project-intent-directive"), _entry("directive", "team-001")]
    _write_manifest(tmp_path, guard, entries)
    _write_sidecar(tmp_path, guard, _sidecar("directive", "project-intent-directive", "directive:PROJECT_001"))
    _write_sidecar(
        tmp_path,
        guard,
        _sidecar("directive", "team-001", "directive:TEAM_001", adapter_id="project-direct-write"),
    )

    assert synthesized_urns(tmp_path, "directive") == frozenset({"directive:PROJECT_001"})


def test_reregistered_synthesized_urn_stays_owned(tmp_path: Path, guard: PathGuard) -> None:
    """One synthesis-written record of the URN is enough; a later registration does not take it away.

    This is the directive shape: project registration derives a different slug for a directive
    (``PROJECT_001`` -> ``project-001``), so the synthesized entry survives beside it.
    """
    entries = [_entry("directive", "project-intent-directive"), _entry("directive", "project-001")]
    _write_manifest(tmp_path, guard, entries)
    _write_sidecar(tmp_path, guard, _sidecar("directive", "project-intent-directive", "directive:PROJECT_001"))
    _write_sidecar(
        tmp_path,
        guard,
        _sidecar("directive", "project-001", "directive:PROJECT_001", adapter_id="project-direct-write"),
    )

    assert synthesized_urns(tmp_path, "directive") == frozenset({"directive:PROJECT_001"})


def test_reregistered_reach_only_artifact_stays_owned_when_its_entry_was_replaced(tmp_path: Path, guard: PathGuard) -> None:
    """The registration replaced the single entry AND its sidecar: the record still says synthesis created it.

    Project registration keys the manifest by ``(kind, slug)`` and, for a slug-keyed kind, the
    slug is the id — so a re-registered synthesized tactic loses its synthesis-written entry.
    The created-artifacts record is the durable memory of creation, so ownership survives;
    losing it would drop the tactic from ``reach_only_ids`` and deliver it as a root even while
    its directive is inactive (#6767 FR-010).
    """
    _write_manifest(tmp_path, guard, [_entry("tactic", "review-policy-tactic")])
    _write_sidecar(
        tmp_path,
        guard,
        _sidecar("tactic", "review-policy-tactic", "tactic:review-policy-tactic", adapter_id="project-direct-write"),
    )
    _write_record(tmp_path, "created_tactics:\n  - review-policy-tactic\n")

    assert synthesized_urns(tmp_path, "tactic") == frozenset({"tactic:review-policy-tactic"})


def test_hand_authored_registration_stays_unowned_when_the_record_never_listed_it(tmp_path: Path, guard: PathGuard) -> None:
    """Positive control for the row above: a hand-authored file the record never lists is not owned."""
    _write_manifest(tmp_path, guard, [_entry("tactic", "my-hand-authored-tactic")])
    _write_sidecar(
        tmp_path,
        guard,
        _sidecar("tactic", "my-hand-authored-tactic", "tactic:my-hand-authored-tactic", adapter_id="project-direct-write"),
    )
    _write_record(tmp_path, "created_tactics:\n  - review-policy-tactic\n")

    assert synthesized_urns(tmp_path, "tactic") == frozenset()


def test_unreadable_record_keeps_a_registered_artifact_owned(tmp_path: Path, guard: PathGuard) -> None:
    """With the record unreadable the registration cannot be told from synthesis output: stay owned (fail closed)."""
    _write_manifest(tmp_path, guard, [_entry("tactic", "review-policy-tactic")])
    _write_sidecar(
        tmp_path,
        guard,
        _sidecar("tactic", "review-policy-tactic", "tactic:review-policy-tactic", adapter_id="project-direct-write"),
    )
    _write_record(tmp_path, "created_tactics: [\n  broken\n")

    assert synthesized_urns(tmp_path, "tactic") == frozenset({"tactic:review-policy-tactic"})


# ---------------------------------------------------------------------------
# The one fallback: an unreadable manifest or sidecar falls back to the record
# ---------------------------------------------------------------------------


def test_unreadable_manifest_falls_back_to_the_created_record(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    _corrupt_manifest(tmp_path)
    _write_record(tmp_path, "created_tactics:\n  - how-we-apply-directive-024\n")

    with caplog.at_level(logging.WARNING):
        urns = synthesized_urns(tmp_path, "tactic")

    assert urns == frozenset({"tactic:how-we-apply-directive-024"})
    assert CREATED_ARTIFACTS_PATH.as_posix() in caplog.text


def test_unreadable_manifest_falls_back_to_the_legacy_tactics_record(tmp_path: Path) -> None:
    _corrupt_manifest(tmp_path)
    _write_record(tmp_path, "created_tactics:\n  - legacy-tactic\n", legacy=True)

    assert synthesized_urns(tmp_path, "tactic") == frozenset({"tactic:legacy-tactic"})


def test_dangling_manifest_symlink_is_unreadable_not_absent(tmp_path: Path) -> None:
    """A symlink whose target is gone is an unreadable record, never "nothing was synthesized"."""
    path = tmp_path / MANIFEST_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.symlink_to(tmp_path / "gone.yaml")
    _write_record(tmp_path, "created_tactics:\n  - how-we-apply-directive-024\n")

    assert synthesized_urns(tmp_path, "tactic") == frozenset({"tactic:how-we-apply-directive-024"})


def test_missing_sidecar_for_a_reach_only_kind_answers_from_the_manifest_entry(tmp_path: Path, guard: PathGuard, monkeypatch: pytest.MonkeyPatch) -> None:
    """A non-directive kind's node identity is ``<kind>:<slug>``, so the entry answers without the sidecar."""

    def _no_read(_repo_root: Path) -> object:
        raise AssertionError("the created-artifacts record is not needed for a slug-keyed kind")

    monkeypatch.setattr("charter.activation.synthesizer.manifest.read_created_record", _no_read)
    _write_manifest(tmp_path, guard, [_entry("tactic", "review-policy-tactic")])

    assert synthesized_urns(tmp_path, "tactic") == frozenset({"tactic:review-policy-tactic"})


def test_unreadable_sidecar_of_a_reach_only_kind_answers_from_the_manifest_entry(tmp_path: Path, guard: PathGuard) -> None:
    """A corrupt sidecar cannot make a slug-keyed artifact unowned (fail-closed for delivery gating)."""
    _write_manifest(tmp_path, guard, [_entry("tactic", "review-policy-tactic")])
    sidecar = tmp_path / ".kittify/charter/provenance/tactic-review-policy-tactic.yaml"
    sidecar.parent.mkdir(parents=True, exist_ok=True)
    sidecar.write_text("artifact_urn: [unclosed\n", encoding="utf-8")

    assert synthesized_urns(tmp_path, "tactic") == frozenset({"tactic:review-policy-tactic"})


def test_unreadable_sidecar_of_a_directive_falls_back_to_the_record(tmp_path: Path, guard: PathGuard) -> None:
    """A directive's id lives in the sidecar alone: unusable there, the record stands in."""
    _write_manifest(tmp_path, guard, [_entry("directive", "project-intent-directive")])
    sidecar = tmp_path / ".kittify/charter/provenance/directive-project-intent-directive.yaml"
    sidecar.parent.mkdir(parents=True, exist_ok=True)
    sidecar.write_text("artifact_urn: [unclosed\n", encoding="utf-8")
    _write_record(tmp_path, "created_directives:\n  - PROJECT_001\n")

    # The record does not track directives, so the one coded error is the answer (never a guess).
    with pytest.raises(SynthesisMembershipUnreadableError) as caught:
        synthesized_urns(tmp_path, "directive")

    assert caught.value.offending_artifact == ".kittify/charter/provenance/directive-project-intent-directive.yaml"
    assert "does not track directives" in caught.value.body


@pytest.mark.parametrize(
    ("record", "record_state"),
    [
        pytest.param(None, "absent or lists no tactic", id="record-absent"),
        pytest.param("created_tactics: [\n  broken\n", "unreadable", id="record-unparseable"),
        pytest.param("created_tactics: not-a-list\n", "unreadable", id="record-wrong-shape"),
        pytest.param("created_tactics: []\n", "absent or lists no tactic", id="record-lists-no-tactic"),
        pytest.param("created_styleguides:\n  - other\n", "absent or lists no tactic", id="record-other-kind"),
    ],
)
def test_unreadable_manifest_without_a_usable_record_raises(tmp_path: Path, record: str | None, record_state: str) -> None:
    if record is not None:
        _write_record(tmp_path, record)
    _corrupt_manifest(tmp_path)

    with pytest.raises(SynthesisMembershipUnreadableError) as caught:
        synthesized_urns(tmp_path, "tactic")

    error = caught.value
    assert error.code == "SYNTHESIS_MEMBERSHIP_UNREADABLE"
    assert MANIFEST_PATH.as_posix() in error.body
    assert CREATED_ARTIFACTS_PATH.as_posix() in error.body
    assert record_state in error.body
    assert error.kind == "tactic"


def test_unreadable_manifest_for_an_untracked_kind_raises_without_reading_the_record(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The record tracks reach-only kinds only: it has no answer for directives, so refuse (never guess)."""

    def _no_read(_repo_root: Path) -> object:
        raise AssertionError("the record cannot answer for directives and must not be read")

    monkeypatch.setattr("charter.activation.synthesizer.manifest.read_created_record", _no_read)
    _corrupt_manifest(tmp_path)

    with pytest.raises(SynthesisMembershipUnreadableError) as caught:
        synthesized_urns(tmp_path, "directive")

    assert "does not track directives" in caught.value.body


# ---------------------------------------------------------------------------
# The one sidecar reader's refusals
# ---------------------------------------------------------------------------


def test_missing_sidecar_for_a_directive_entry_raises(tmp_path: Path, guard: PathGuard) -> None:
    """The manifest records the file stem, not the directive id, so the URN is unknowable without it."""
    _write_manifest(tmp_path, guard, [_entry("directive", "project-intent-directive")])

    with pytest.raises(SynthesisMembershipUnreadableError) as caught:
        synthesized_urns(tmp_path, "directive")

    assert caught.value.offending_artifact == ".kittify/charter/provenance/directive-project-intent-directive.yaml"
    assert ".kittify/charter/provenance/directive-project-intent-directive.yaml" in caught.value.body


def test_sidecar_without_artifact_urn_raises(tmp_path: Path, guard: PathGuard) -> None:
    path = tmp_path / ".kittify/charter/provenance/directive-project-intent-directive.yaml"
    _write_manifest(tmp_path, guard, [_entry("directive", "project-intent-directive")])
    _write_sidecar(tmp_path, guard, _sidecar("directive", "project-intent-directive", "directive:PROJECT_001"))
    path.write_text(
        "\n".join(line for line in path.read_text(encoding="utf-8").splitlines() if not line.startswith("artifact_urn")) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(SynthesisMembershipUnreadableError) as caught:
        synthesized_urns(tmp_path, "directive")

    assert "artifact_urn" in caught.value.body


@pytest.mark.parametrize("urn", ["tactic:PROJECT_001", "directive:", "PROJECT_001"])
def test_sidecar_urn_of_the_wrong_shape_raises(tmp_path: Path, guard: PathGuard, urn: str) -> None:
    _write_manifest(tmp_path, guard, [_entry("directive", "project-intent-directive")])
    _write_sidecar(tmp_path, guard, _sidecar("directive", "project-intent-directive", urn))

    with pytest.raises(SynthesisMembershipUnreadableError) as caught:
        synthesized_urns(tmp_path, "directive")

    assert "is not a directive URN" in caught.value.body


def test_sidecar_path_outside_the_provenance_root_raises(tmp_path: Path, guard: PathGuard) -> None:
    entry = _entry("directive", "project-intent-directive").model_copy(update={"provenance_path": "../escape.yaml"})
    _write_manifest(tmp_path, guard, [entry])

    with pytest.raises(SynthesisMembershipUnreadableError) as caught:
        synthesized_urns(tmp_path, "directive")

    assert "escape.yaml" in caught.value.body


def test_sidecar_of_another_kind_is_not_read(tmp_path: Path, guard: PathGuard) -> None:
    """A missing sidecar of a kind nobody asked for cannot refuse the read (positive control: the asked kind answers)."""
    entries = [_entry("directive", "project-intent-directive"), _entry("tactic", "review-policy-tactic")]
    _write_manifest(tmp_path, guard, entries)
    _write_sidecar(tmp_path, guard, _sidecar("directive", "project-intent-directive", "directive:PROJECT_001"))

    assert synthesized_urns(tmp_path, "directive") == frozenset({"directive:PROJECT_001"})


def test_sidecar_artifact_urn_is_the_one_strict_reader(tmp_path: Path, guard: PathGuard) -> None:
    entry = _entry("tactic", "review-policy-tactic")
    _write_manifest(tmp_path, guard, [entry])
    _write_sidecar(tmp_path, guard, _sidecar("tactic", "review-policy-tactic", "tactic:review-policy-tactic"))

    assert sidecar_artifact_urn(tmp_path, entry) == "tactic:review-policy-tactic"


def test_sidecar_artifact_urn_is_none_for_a_direct_write_registration(tmp_path: Path, guard: PathGuard) -> None:
    entry = _entry("tactic", "my-hand-authored-tactic")
    _write_manifest(tmp_path, guard, [entry])
    _write_sidecar(
        tmp_path,
        guard,
        _sidecar("tactic", "my-hand-authored-tactic", "tactic:my-hand-authored-tactic", adapter_id="project-direct-write"),
    )

    assert sidecar_artifact_urn(tmp_path, entry) is None


# ---------------------------------------------------------------------------
# The lenient write-side helper keeps its contract
# ---------------------------------------------------------------------------


def test_manifest_slugs_is_lenient(tmp_path: Path, guard: PathGuard) -> None:
    """The first-time diff needs "what the manifest said before", never an ownership refusal."""
    assert manifest_slugs(tmp_path, "tactic") == frozenset()
    _corrupt_manifest(tmp_path)
    assert manifest_slugs(tmp_path, "tactic") == frozenset()

    (tmp_path / MANIFEST_PATH).unlink()
    _write_manifest(tmp_path, guard, [_entry("tactic", "review-policy-tactic")])

    assert manifest_slugs(tmp_path, "tactic") == frozenset({"review-policy-tactic"})


# ---------------------------------------------------------------------------
# One code, one meaning
# ---------------------------------------------------------------------------


def test_the_error_is_the_documented_code() -> None:
    error = SynthesisMembershipUnreadableError(
        "body",
        record_path="r.yaml",
        offending_artifact="p.yaml",
        reason="gone",
        kind="directive",
    )

    assert error.code == "SYNTHESIS_MEMBERSHIP_UNREADABLE"
    assert error.body == "body"
    assert str(error) == "body"  # both renderers show the remedy, never a bare code
    assert (error.record_path, error.offending_artifact, error.reason, error.kind) == (
        "r.yaml",
        "p.yaml",
        "gone",
        "directive",
    )


def test_the_reader_and_the_error_are_public(monkeypatch: pytest.MonkeyPatch) -> None:
    from charter.activation.synthesizer import manifest

    for name in ("synthesized_urns", "synthesized_ids", "sidecar_artifact_urn", "manifest_slugs"):
        assert name in manifest.__all__, name
    assert read_created_record is manifest.read_created_record
