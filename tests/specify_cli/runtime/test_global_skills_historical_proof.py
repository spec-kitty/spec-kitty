"""The user-global skill sync refreshes only what Spec Kitty provably wrote (#7700, #5983, #2527).

A file in a global skill root whose bytes are a render an earlier release shipped
for the same ``<skill>/<path>`` is Spec Kitty's own output: the sync refreshes it
(or retires it, for a retired skill). Anything else stays byte-for-byte as it is,
is reported, and keeps ``agent-skills.lock`` from claiming the skills are current.
The historical bytes below are frozen copies of shipped renders, so the test never
reads git history.
"""

from __future__ import annotations

import base64
from pathlib import Path

import pytest

from specify_cli.core.config import CLAUDE_CONFIG_DIR_ENV
from specify_cli.runtime import agent_skills
from specify_cli.runtime.asset_preparation import digest
from specify_cli.tool_surface.operations import OwnerAssessment

pytestmark = [pytest.mark.fast]

_RUN_IMPLEMENT_REVIEW_2026_07_13_B64 = (
    "LS0tCm5hbWU6IHNway1ydW4taW1wbGVtZW50LXJldmlldwpkZXNjcmlwdGlvbjogIk9yY2hlc3RyYXRlIFNwZWMgS2l0dHkg"
    "d29yay1wYWNrYWdlIGltcGxlbWVudGF0aW9uIGFuZCByZXZpZXcgbG9vcHMgdW50aWwgYWxsIHBhY2thZ2VzIGFyZSBkb25l"
    "LCBhcHByb3ZlZCwgb3IgY29ycmVjdGx5IHJlamVjdGVkLiIKLS0tCgojIHNway1ydW4taW1wbGVtZW50LXJldmlldwoKVXNl"
    "IHRoaXMgc2tpbGwgd2hlbiBhIG1pc3Npb24gaXMgaW4gaW1wbGVtZW50YXRpb24vcmV2aWV3IGxhbmVzIG9yIHRoZSB1c2Vy"
    "CndhbnRzIHRoZSBhZ2VudCB0byBjb29yZGluYXRlIGltcGxlbWVudGVycyBhbmQgcmV2aWV3ZXJzLgoKIyMgRmxvdwoKMS4g"
    "VXNlIGBzcGstcnVuLW5leHRgIHRvIGlkZW50aWZ5IHRoZSBhY3RpdmUgV1AgYW5kIGxhbmUuCjIuIERpc3BhdGNoIGltcGxl"
    "bWVudGF0aW9uIG9ubHkgZnJvbSBydW50aW1lLXByb3ZpZGVkIHByb21wdCBjb250ZXh0LgozLiBSZXZpZXcgZWFjaCBXUCBp"
    "bmRlcGVuZGVudGx5IHdpdGggYHNway1ydW4tcmV2aWV3LXdwYC4KNC4gT24gcmVqZWN0aW9uLCBmZWVkIHN0cnVjdHVyZWQg"
    "cmV2aWV3ZXIgZmVlZGJhY2sgYmFjayBpbnRvIHRoZSBuZXh0CiAgIGltcGxlbWVudGF0aW9uIGF0dGVtcHQuCjUuIENvbnRp"
    "bnVlIHVudGlsIHJ1bnRpbWUgcmV0dXJucyB0ZXJtaW5hbCBvciBhIGJsb2NrZXIuCgojIyBTdWItQWdlbnQgTG9uZy1HYXRl"
    "IENvbnRyYWN0CgpgbW92ZS10YXNrIC0tdG8gZm9yX3Jldmlld2AgcnVucyB0aGUgcHJlLXJldmlldyByZWdyZXNzaW9uIGdh"
    "dGUKc3luY2hyb25vdXNseSBhcyBwYXJ0IG9mIHRoZSB0cmFuc2l0aW9uICgjMjU3MC8jMjQ5My8jMjU1NSk6IGl0IGRlcml2"
    "ZXMgdGhlCmFmZmVjdGVkIHRlc3Qgc2NvcGUgZm9yIHRoZSBNaXNzaW9uJ3MgY2hhbmdlZCBmaWxlcyBhbmQgcnVucyBpdCBh"
    "dCBoZWFkCmJlZm9yZSB0aGUgY29tbWFuZCByZXR1cm5zLiBUaGF0IHNjb3BlZCBydW4gaXMgYSByZWFsIHN1YnByb2Nlc3Mg"
    "YW5kIGNhbgp0YWtlIGZyb20gc2Vjb25kcyB0byBhIGZldyBtaW51dGVzIGRlcGVuZGluZyBvbiBzY29wZSBzaXplLgoKLSBB"
    "IGRpc3BhdGNoZWQgaW1wbGVtZW50L3JldmlldyBzdWItYWdlbnQgTVVTVCAqKnBvbGwgdGhlIGdhdGUgaW52b2NhdGlvbiB0"
    "bwogIGNvbXBsZXRpb24qKiDigJQgdHJlYXQgdGhlIGBtb3ZlLXRhc2sgLS10byBmb3JfcmV2aWV3YCBjb21tYW5kIGFzIHN0"
    "aWxsIGluCiAgZmxpZ2h0IHVudGlsIGl0IGV4aXRzLCBub3QgYXMgYSBmaXJlLWFuZC1mb3JnZXQgaGFuZC1iYWNrLiBEbyBu"
    "b3QgYXNzdW1lCiAgY29udHJvbCByZXR1cm5zIGltbWVkaWF0ZWx5LCBhbmQgZG8gbm90IGtpbGwgb3IgcmV0cnkgdGhlIGNv"
    "bW1hbmQgd2hpbGUgaXQKICBpcyBzdGlsbCBydW5uaW5nLgotIFRvIHNraXAgdGhlIGdhdGUgZm9yIGEgc2luZ2xlIGludm9j"
    "YXRpb24sIHBhc3MgYC0tc2tpcC1wcmUtcmV2aWV3LWdhdGVgLgogIFRvIGRpc2FibGUgaXQgcHJvY2Vzcy13aWRlLCBzZXQg"
    "YFNQRUNfS0lUVFlfU1lOQ19ESVNBQkxFYCBvcgogIGBTUEVDX0tJVFRZX1NZTkNfTUlOSU1BTF9JTVBPUlRgICh0aGUgZ2F0"
    "ZSByZXVzZXMgdGhlIHN5bmMgbGF5ZXIncwogIGV4aXN0aW5nIGRpc2FibGUgdG9nZ2xlcyByYXRoZXIgdGhhbiBhZGRpbmcg"
    "YSB0aGlyZCBlbnYgdmFyKS4gRWl0aGVyCiAgb3B0LW91dCBza2lwcyB0aGUgZ2F0ZSBiZWZvcmUgaXQgcmVzb2x2ZXMgYSB3"
    "b3Jrc3BhY2Ugb3Igc3Bhd25zIHRoZQogIHN1YnByb2Nlc3MuCi0gQWJzZW50IGFuIG9wdC1vdXQsIHRoZSBnYXRlIGFsd2F5"
    "cyBlbmZvcmNlcyBieSBkZWZhdWx0LiBBbiBvcmNoZXN0cmF0b3IKICBvYnNlcnZpbmcgYSBzdWItYWdlbnQgdGhhdCBhcHBl"
    "YXJzIHRvIGhhbmcgb24gYSBgZm9yX3Jldmlld2AgdHJhbnNpdGlvbgogIHNob3VsZCBmaXJzdCBjaGVjayB3aGV0aGVyIHRo"
    "ZSBnYXRlJ3Mgc2NvcGVkIHRlc3Qgc3VicHJvY2VzcyBpcyBzdGlsbAogIHJ1bm5pbmcgYmVmb3JlIHRyZWF0aW5nIHRoZSBz"
    "dWItYWdlbnQgYXMgc3R1Y2suCgojIyBMZWdhY3kgQWxpYXMKCkZvciBkZXRhaWxlZCBvcmNoZXN0cmF0aW9uIG1lY2hhbmlj"
    "cywgdXNlIGBzcGVjLWtpdHR5LWltcGxlbWVudC1yZXZpZXdgIHdoZW4KYXZhaWxhYmxlLgo="
)

_GATE_MERGE_LAST_SHIPPED_B64 = (
    "LS0tCm5hbWU6IHNway1nYXRlLW1lcmdlCmRlc2NyaXB0aW9uOiAiTWVyZ2UgYW4gYWNjZXB0ZWQgU3BlYyBLaXR0eSBtaXNz"
    "aW9uIHNhZmVseSwgcHJlc2VydmluZyBnaXQgaW52YXJpYW50cywgbWlzc2lvbiBzdGF0ZSwgYW5kIHBvc3QtbWVyZ2UgZm9s"
    "bG93LXRocm91Z2guIgotLS0KCiMgc3BrLWdhdGUtbWVyZ2UKClVzZSB0aGlzIHNraWxsIGFmdGVyIGBzcGstZ2F0ZS1hY2Nl"
    "cHRgIHBhc3NlcyBvciB3aGVuIGEgdXNlciBhc2tzIHRvIG1lcmdlIGEKbWlzc2lvbi4KCiMjIEZsb3cKCjEuIENvbmZpcm0g"
    "dGhlIG1pc3Npb24gcGFzc2VkIGFjY2VwdC4KMi4gUnVuIGAvc3BlYy1raXR0eS5tZXJnZWAgb3IgdGhlIGVxdWl2YWxlbnQg"
    "Q0xJIGNvbW1hbmQuCjMuIFJlc29sdmUgZ2l0L3dvcmt0cmVlIGJsb2NrZXJzIHdpdGggYHNway1hZG1pbi1naXQtd29ya2Zs"
    "b3dgLgo0LiBBZnRlciBtZXJnZSwgcm91dGUgdG8gYHNway1nYXRlLW1pc3Npb24tcmV2aWV3YC4KNS4gVGhlbiByb3V0ZSB0"
    "byBgc3BrLWdhdGUtcmV0cm9zcGVjdGl2ZWAuCgojIyBSdWxlCgpEbyBub3QgbWVyZ2UgcmVqZWN0ZWQsIGJsb2NrZWQsIG9y"
    "IHBhcnRpYWxseSByZXZpZXdlZCB3b3JrLgo="
)

#: ``src/doctrine/skills/spk-run-implement-review/SKILL.md`` at ``dd83e5b6f`` (2026-07-13).
_OLD_RUN_IMPLEMENT_REVIEW = base64.b64decode("".join(_RUN_IMPLEMENT_REVIEW_2026_07_13_B64))
#: ``src/charter/offering/skills/spk-gate-merge/SKILL.md`` as last shipped, before the #3080 rename retired it.
_OLD_GATE_MERGE = base64.b64decode("".join(_GATE_MERGE_LAST_SHIPPED_B64))


@pytest.fixture
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("SPEC_KITTY_HOME", str(home / ".kittify"))
    monkeypatch.delenv(CLAUDE_CONFIG_DIR_ENV, raising=False)
    return home


def _seed(home: Path, relative: str, data: bytes) -> Path:
    path = home / ".claude" / "skills" / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def _effect_paths(assessment: OwnerAssessment) -> set[Path]:
    return {assessment.root.path / effect.path for effect in assessment.effects}


def _stamp(home: Path) -> Path:
    return home / ".kittify" / "cache" / "agent-skills.lock"


def test_frozen_fixtures_are_the_shipped_bytes() -> None:
    assert digest(_OLD_RUN_IMPLEMENT_REVIEW) == "56df985f0ef13174cda1d874929a4eb58a9b9675675f9921ad1dd6a0eb320fda"
    assert digest(_OLD_GATE_MERGE) == "9066c7b7f505f3d2b8e8f54372679c97f91caa02b55e4bc79b5aaefcf1400ba8"


def test_historical_render_is_refreshed_and_stamped(home: Path) -> None:
    stale = _seed(home, "spk-run-implement-review/SKILL.md", _OLD_RUN_IMPLEMENT_REVIEW)

    assessment = agent_skills.assess_global_agent_skills()

    assert assessment.complete, assessment.diagnostics
    assert stale in _effect_paths(assessment)
    assert _stamp(home) in _effect_paths(assessment)
    agent_skills.ensure_global_agent_skills()
    assert stale.read_bytes() != _OLD_RUN_IMPLEMENT_REVIEW


def test_unproven_canonical_file_is_kept_and_withholds_the_stamp(home: Path) -> None:
    mine = _seed(home, "spk-run-implement-review/SKILL.md", b"# my own notes\n")

    assessment = agent_skills.assess_global_agent_skills()

    assert mine not in _effect_paths(assessment)
    assert _stamp(home) not in _effect_paths(assessment)
    agent_skills.ensure_global_agent_skills()
    assert mine.read_bytes() == b"# my own notes\n"
    assert not _stamp(home).exists()
    kept = agent_skills.kept_global_skill_files(agent_skills.assess_global_agent_skills())
    assert [(item.path, item.kind) for item in kept] == [(mine, "stale_canonical")]


def test_retired_skill_is_removed_only_when_its_bytes_are_proven(home: Path) -> None:
    proven = _seed(home, "spk-gate-merge/SKILL.md", _OLD_GATE_MERGE)

    agent_skills.ensure_global_agent_skills()

    assert not proven.exists()
    assert not proven.parent.exists()
    assert _stamp(home).is_file()


def test_edited_retired_skill_is_kept_and_reported(home: Path) -> None:
    edited = _seed(home, "spk-gate-merge/SKILL.md", _OLD_GATE_MERGE + b"\nmy addition\n")

    agent_skills.ensure_global_agent_skills()

    assert edited.read_bytes() == _OLD_GATE_MERGE + b"\nmy addition\n"
    kept = agent_skills.kept_global_skill_files(agent_skills.assess_global_agent_skills())
    assert [(item.path, item.kind) for item in kept] == [(edited, "edited_retired")]


def test_custom_skill_is_kept_and_does_not_block_the_stamp(home: Path) -> None:
    custom = _seed(home, "my-team-skill/SKILL.md", b"---\nname: my-team-skill\n---\n")

    agent_skills.ensure_global_agent_skills()

    assert custom.read_bytes() == b"---\nname: my-team-skill\n---\n"
    assert _stamp(home).is_file()
    assert agent_skills.kept_global_skill_files(agent_skills.assess_global_agent_skills()) == ()


def test_startup_and_tool_surfaces_fix_reach_the_same_bytes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """FR-011: the startup sync and ``doctor tool-surfaces --fix`` agree on a historical render."""
    from specify_cli.tool_surface.service import run_tool_surfaces

    results: list[bytes] = []
    for label in ("startup", "fix"):
        home = tmp_path / label / "home"
        home.mkdir(parents=True)
        monkeypatch.setenv("HOME", str(home))
        monkeypatch.setenv("SPEC_KITTY_HOME", str(home / ".kittify"))
        monkeypatch.delenv(CLAUDE_CONFIG_DIR_ENV, raising=False)
        target = _seed(home, "spk-run-implement-review/SKILL.md", _OLD_RUN_IMPLEMENT_REVIEW)
        if label == "startup":
            agent_skills.ensure_global_agent_skills()
        else:
            project = tmp_path / label / "project"
            (project / ".kittify").mkdir(parents=True)
            (project / ".kittify" / "config.yaml").write_text("project:\n  uuid: test-uuid-7700\nagents:\n  available:\n    - claude\n", encoding="utf-8")
            run_tool_surfaces(project, ("claude",), fix=True)
        results.append(target.read_bytes())

    assert results[0] == results[1]
    assert results[0] != _OLD_RUN_IMPLEMENT_REVIEW


def test_the_byte_proof_adds_no_destination_read(home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """NFR-001: the historical proof is judged on ``asset()``'s own observation of the file.

    A warm destination is read twice per assessment (``asset()`` compares it, the effect
    probe confirms it); proving it a shipped render must not add a third read.
    """
    from specify_cli.runtime import asset_preparation

    agent_skills.ensure_global_agent_skills()
    target = home / ".claude" / "skills" / "spk-run-implement-review" / "SKILL.md"
    real = asset_preparation.node_state
    reads: list[Path] = []

    def counting(path: Path, *, read_content: bool = True) -> object:
        if path == target and read_content:
            reads.append(path)
        return real(path, read_content=read_content)

    monkeypatch.setattr(asset_preparation, "node_state", counting)
    agent_skills.assess_global_agent_skills()

    assert len(reads) == 2


def test_a_warm_sync_neither_probes_placement_nor_reserializes_the_inventory(home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """NFR-001: an anchored inventory places its keys without a filesystem probe, and an
    unchanged inventory is not serialized again (bounded counts, not timings)."""
    from specify_cli.runtime import asset_preparation

    agent_skills.ensure_global_agent_skills()
    probes: list[str] = []
    serializations: list[str] = []
    real_place = asset_preparation._place_legacy_key
    real_serialize = asset_preparation._serialize_inventory

    def counting_place(relative: str, candidates: list[Path], confinement: tuple[Path, ...]) -> Path | None:
        probes.append(relative)
        placed: Path | None = real_place(relative, candidates, confinement)
        return placed

    def counting_serialize(entries: dict[str, dict[str, object]], anchor: str) -> bytes:
        serializations.append(anchor)
        return bytes(real_serialize(entries, anchor))

    monkeypatch.setattr(asset_preparation, "_place_legacy_key", counting_place)
    monkeypatch.setattr(asset_preparation, "_serialize_inventory", counting_serialize)
    assessment = agent_skills.assess_global_agent_skills()

    assert not assessment.effects
    assert probes == []
    assert serializations == []
