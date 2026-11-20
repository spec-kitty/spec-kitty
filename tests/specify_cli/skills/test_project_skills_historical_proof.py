"""A project skill file holding a render Spec Kitty shipped earlier is refreshed (#2527).

Reproduced on ``a053b674``: a managed project skill file byte-equal to an older
shipped render stayed stale after ``doctor tool-surfaces --fix`` (reported only as
"skipped"), because the manifest records today's hash. Proven historical bytes are
Spec Kitty's own output, so the fix replaces them, keeping a backup as it does for
any replacement; a user's edit still needs consent.
"""

from __future__ import annotations

import base64
import stat
from pathlib import Path

import pytest

from specify_cli.core.config import CLAUDE_CONFIG_DIR_ENV
from specify_cli.tool_surface.service import run_tool_surfaces

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

#: ``src/doctrine/skills/spk-run-implement-review/SKILL.md`` at ``dd83e5b6f`` (2026-07-13).
_OLD_RUN_IMPLEMENT_REVIEW = base64.b64decode("".join(_RUN_IMPLEMENT_REVIEW_2026_07_13_B64))
_SKILL = Path(".claude/skills/spk-run-implement-review/SKILL.md")


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("SPEC_KITTY_HOME", str(home / ".kittify"))
    monkeypatch.delenv(CLAUDE_CONFIG_DIR_ENV, raising=False)
    project = tmp_path / "project"
    (project / ".kittify").mkdir(parents=True)
    (project / ".kittify" / "config.yaml").write_text("project:\n  uuid: test-uuid-2527\nagents:\n  available:\n    - claude\n", encoding="utf-8")
    run_tool_surfaces(project, ("claude",), fix=True)
    assert (project / _SKILL).is_file(), "control: the fix installs the managed project skills"
    return project


def _backups_holding(project: Path, data: bytes) -> list[Path]:
    return [path for path in (project / ".kittify").rglob("*") if path.is_file() and path.read_bytes() == data]


def _overwrite(path: Path, data: bytes) -> None:
    """Write *data* over a file the sync installed read-only (0444), as a user editing it would."""
    path.chmod(path.stat().st_mode | stat.S_IWUSR)
    path.write_bytes(data)


def test_historical_render_in_a_project_is_refreshed_with_a_backup(project: Path) -> None:
    current = (project / _SKILL).read_bytes()
    _overwrite(project / _SKILL, _OLD_RUN_IMPLEMENT_REVIEW)

    run_tool_surfaces(project, ("claude",), fix=True)

    assert (project / _SKILL).read_bytes() == current
    assert _backups_holding(project, _OLD_RUN_IMPLEMENT_REVIEW), "the replaced bytes are kept in a backup"


def test_edited_project_skill_still_needs_consent(project: Path) -> None:
    edited = (project / _SKILL).read_bytes() + b"\nmy note\n"
    _overwrite(project / _SKILL, edited)

    run_tool_surfaces(project, ("claude",), fix=True)

    assert (project / _SKILL).read_bytes() == edited
