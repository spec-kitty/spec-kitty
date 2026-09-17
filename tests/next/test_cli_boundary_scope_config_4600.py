"""#4600 boundary: a corrupt ``.kittify/config.yaml`` fails ``next`` loud, not silent.

FR-004 ("not whack-a-field") gap closed by the cli-boundary-robustness landing
fold: ``charter.activation.scope._load_charter_scope_config`` was the last
config reader on the charter-scope path that read ``.kittify/config.yaml``
without ``encoding="utf-8"`` and without wrapping the read/parse. It is reached
on every prompt build via
``runtime.next.prompt_builder._governance_context`` ->
``charter.activation.scope_router.build_with_scope`` ->
``CharterScope.resolve``, i.e. by the real ``spec-kitty next`` dispatch path.

Before the fix a non-UTF-8 (or malformed-YAML) config raised a raw
``UnicodeDecodeError``/``yaml.YAMLError`` that ``_governance_context`` swallowed
into ``except Exception: pass`` -- so ``next --result success`` *silently*
degraded to legacy governance and emitted a normal ``kind=step`` decision with
exit 0, rendering a prompt with the wrong charter context. That is the exact
#4600 brick-class the mission claims to close, missed on this reader.

After the fix the reader raises the fail-loud ``CharterPackConfigError`` whose
body names the offending file and the decode/parse cause; the ``next`` prompt
boundary surfaces that body as a ``kind=blocked`` decision -- non-zero exit, the
file named, no Python traceback, and no raw exception class name leaked.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from specify_cli import app as cli_app
from tests.next.test_next_command_integration import (
    _add_wp_files,
    _advance_runtime_to_step,
    _scaffold_project,
)

pytestmark = [pytest.mark.regression, pytest.mark.git_repo]

runner = CliRunner()

# The three ways the underlying fault could leak into operator output if the
# boundary were not fail-loud: a raw decode/parse exception, the domain
# exception's class name, or its internal machine code
# (``str(CharterPackConfigError)`` yields the code, not the file-naming body --
# so a naive re-raise regresses the acceptance bar even though it "raises the
# right type").
_FORBIDDEN_LEAKS = (
    "Traceback",
    "UnicodeDecodeError",
    "YAMLError",
    "CharterPackConfigError",
    "CHARTER_PACK_CONFIG_INVALID",
)


@pytest.mark.parametrize(
    "payload,expect_decode",
    [
        pytest.param(b"mission_type_activations:\n\xff\xfe not-utf8\n", True, id="non-utf8"),
        pytest.param(b"charter_scopes: 'unterminated\n", False, id="malformed-yaml"),
    ],
)
def test_issue_4600_corrupt_config_blocks_next_without_traceback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    payload: bytes,
    expect_decode: bool,
) -> None:
    """A real ``spec-kitty next`` dispatch fails loud on a corrupt config.

    Drives the CLI (not ``decide_next`` directly) so the assertion is on the
    operator-visible outcome of the command boundary.
    """
    base = tmp_path / "base"
    base.mkdir()
    repo_root = _scaffold_project(base)
    feature_dir = repo_root / "kitty-specs" / "042-test-feature"
    _add_wp_files(feature_dir, {"WP01": "planned"})
    _advance_runtime_to_step(repo_root, "042-test-feature", "implement")

    # Corrupt the config only after a healthy scaffold, so the fault is the
    # config content and nothing in the setup path.
    (repo_root / ".kittify" / "config.yaml").write_bytes(payload)

    monkeypatch.chdir(repo_root)
    result = runner.invoke(
        cli_app,
        ["next", "--agent", "test", "--mission", "042-test-feature", "--result", "success", "--json"],
    )

    # Non-zero exit via the normal CLI exit seam (SystemExit), never a crash.
    assert result.exit_code == 1, result.output
    assert isinstance(result.exception, SystemExit), repr(result.exception)

    output = result.output
    for leak in _FORBIDDEN_LEAKS:
        assert leak not in output, f"{leak!r} leaked into operator output:\n{output}"

    payload_json = json.loads(result.stdout)
    assert payload_json["kind"] == "blocked"
    reason = payload_json["reason"]
    # The offending file is named so the operator can find it.
    assert "config.yaml" in reason
    assert "config.yaml" in output
    if expect_decode:
        # Non-UTF-8 content indicates the decode/encoding failure explicitly.
        assert "decode" in reason.lower()
