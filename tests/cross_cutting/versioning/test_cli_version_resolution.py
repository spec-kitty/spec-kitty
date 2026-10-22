"""``specify_cli.__version__`` / ``cli_version()`` resolution in-process (#6584).

The deferral itself is pinned through the real entry point in
``test_cli_version_deferred.py``.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from specify_cli import version_utils

pytestmark = pytest.mark.unit


@pytest.fixture
def fresh_cli_version() -> Iterator[None]:
    version_utils.cli_version.cache_clear()
    yield
    version_utils.cli_version.cache_clear()


@pytest.mark.usefixtures("fresh_cli_version")
@pytest.mark.parametrize(
    ("override", "expected"),
    [("9.9.9-test", "9.9.9-test"), (None, "0.5.0-dev")],
    ids=["env-override", "default-without-override"],
)
def test_cli_version_in_test_mode(monkeypatch: pytest.MonkeyPatch, override: str | None, expected: str) -> None:
    monkeypatch.setenv("SPEC_KITTY_TEST_MODE", "1")
    if override is None:
        monkeypatch.delenv("SPEC_KITTY_CLI_VERSION", raising=False)
    else:
        monkeypatch.setenv("SPEC_KITTY_CLI_VERSION", override)
    assert version_utils.cli_version() == expected


@pytest.mark.usefixtures("fresh_cli_version")
def test_cli_version_outside_test_mode_is_get_version_resolved_once(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[int] = []

    def fake_get_version() -> str:
        calls.append(1)
        return "1.2.3"

    monkeypatch.delenv("SPEC_KITTY_TEST_MODE", raising=False)
    monkeypatch.setattr(version_utils, "get_version", fake_get_version)
    assert version_utils.cli_version() == "1.2.3"
    assert version_utils.cli_version() == "1.2.3"
    assert calls == [1]


@pytest.mark.usefixtures("fresh_cli_version")
def test_package_version_attribute_delegates_to_cli_version(monkeypatch: pytest.MonkeyPatch) -> None:
    import specify_cli

    # An earlier read in this process may have stored the value as a module
    # attribute. setitem records the prior state (restored, or removed, on
    # teardown) so the value this test stores cannot leak; then drop the key
    # so this read goes through __getattr__.
    namespace = vars(specify_cli)
    monkeypatch.setitem(namespace, "__version__", "placeholder")
    del namespace["__version__"]
    monkeypatch.setenv("SPEC_KITTY_TEST_MODE", "1")
    monkeypatch.setenv("SPEC_KITTY_CLI_VERSION", "7.0.0-attr")
    assert specify_cli.__version__ == "7.0.0-attr"
    assert vars(specify_cli)["__version__"] == "7.0.0-attr", "first read should store the value as a module attribute"
    from specify_cli import __version__

    assert __version__ == "7.0.0-attr"
