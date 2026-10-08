"""Fail before collection when pytest imports another checkout's CLI source.

The guard deliberately has no opt-out: a lane that tests an installed wheel
must still run under pytest.ini's ``pythonpath = src``.
"""

from pathlib import Path


def assert_checkout_source(module_file: str | Path | None, checkout: Path) -> None:
    expected = (checkout / "src/specify_cli/__init__.py").resolve()
    actual = Path(module_file).resolve() if module_file is not None else None
    if actual != expected:
        raise RuntimeError(
            f"specify_cli imported from outside this checkout: {actual}; expected {expected}. "
            "Run pytest with this checkout's interpreter and test dependencies "
            "(for example, uv run --extra test python -m pytest)."
        )
