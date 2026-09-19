"""Unit matrix for :func:`kernel.guarded_read.read_guarded` (mission
cli-error-surface-seam-01M2WJD2, WP01/T002).

Covers the full contract in ``contracts/guarded-read-primitive.md``: happy
path (single read), ``OSError``, ``UnicodeDecodeError``, a declared caller
exception, an undeclared exception propagating unchanged, ``mode="bytes"``
parity, and ``__cause__`` chaining.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from kernel.errors import GuardedReadError
from kernel.guarded_read import read_guarded


class _CustomReadError(GuardedReadError):
    """A caller-declared ``error_cls`` subclass, distinct from the base."""


def test_happy_path_returns_parse_result_unchanged(tmp_path: Path) -> None:
    path = tmp_path / "data.txt"
    path.write_text("hello world", encoding="utf-8")

    result = read_guarded(path, lambda text: text.upper())

    assert result == "HELLO WORLD"


def test_happy_path_reads_the_file_exactly_once(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "data.txt"
    path.write_text("content", encoding="utf-8")

    read_calls: list[Path] = []
    original_read_text = Path.read_text

    def _spy_read_text(self: Path, *args: object, **kwargs: object) -> str:
        read_calls.append(self)
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", _spy_read_text)

    read_guarded(path, lambda text: text)

    assert read_calls == [path]


def test_missing_file_raises_guarded_read_error(tmp_path: Path) -> None:
    path = tmp_path / "missing.txt"

    with pytest.raises(GuardedReadError) as exc_info:
        read_guarded(path, lambda text: text)

    assert exc_info.value.path == str(path)
    assert isinstance(exc_info.value.__cause__, OSError)


def test_permission_denied_raises_guarded_read_error(tmp_path: Path) -> None:
    path = tmp_path / "locked.txt"
    path.write_text("secret", encoding="utf-8")
    path.chmod(0o000)
    try:
        with pytest.raises(GuardedReadError) as exc_info:
            read_guarded(path, lambda text: text)
        assert isinstance(exc_info.value.__cause__, OSError)
    finally:
        path.chmod(0o644)


def test_undecodable_bytes_raise_guarded_read_error_in_text_mode(tmp_path: Path) -> None:
    path = tmp_path / "bad_bytes.txt"
    path.write_bytes(b"\xff\xfe\x00\x01")

    with pytest.raises(GuardedReadError) as exc_info:
        read_guarded(path, lambda text: text, mode="text")

    assert isinstance(exc_info.value.__cause__, UnicodeDecodeError)


def test_declared_caller_exception_collapses_into_error_cls(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    path.write_text("{not valid json", encoding="utf-8")

    with pytest.raises(_CustomReadError) as exc_info:
        read_guarded(
            path,
            json.loads,
            errors=(json.JSONDecodeError,),
            error_cls=_CustomReadError,
        )

    assert exc_info.value.path == str(path)
    assert isinstance(exc_info.value.__cause__, json.JSONDecodeError)


def test_undeclared_exception_propagates_unchanged(tmp_path: Path) -> None:
    path = tmp_path / "data.txt"
    path.write_text("content", encoding="utf-8")

    def _buggy_parse(_text: str) -> None:
        raise KeyError("boom — a real bug in parse, not a declared failure")

    with pytest.raises(KeyError, match="boom"):
        read_guarded(path, _buggy_parse, errors=(json.JSONDecodeError,))


def test_bytes_mode_reads_raw_bytes_without_decoding(tmp_path: Path) -> None:
    path = tmp_path / "binary.bin"
    path.write_bytes(b"\xff\xfe\x00\x01")

    result = read_guarded(path, lambda content: content, mode="bytes")

    assert result == b"\xff\xfe\x00\x01"


def test_bytes_mode_missing_file_still_raises_guarded_read_error(tmp_path: Path) -> None:
    path = tmp_path / "missing.bin"

    with pytest.raises(GuardedReadError):
        read_guarded(path, lambda content: content, mode="bytes")


def test_error_carries_original_exception_as_cause(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    path.write_text("{not valid json", encoding="utf-8")

    with pytest.raises(json.JSONDecodeError) as bare_exc_info:
        json.loads(path.read_text(encoding="utf-8"))

    with pytest.raises(GuardedReadError) as exc_info:
        read_guarded(path, json.loads, errors=(json.JSONDecodeError,))

    assert isinstance(exc_info.value.__cause__, json.JSONDecodeError)
    assert str(exc_info.value.__cause__) == str(bare_exc_info.value)


def test_error_reason_and_str_match_underlying_message(tmp_path: Path) -> None:
    path = tmp_path / "missing.txt"

    with pytest.raises(GuardedReadError) as exc_info:
        read_guarded(path, lambda text: text)

    exc = exc_info.value
    assert exc.reason is not None
    assert str(exc) == exc.reason


def test_default_error_cls_is_guarded_read_error_base(tmp_path: Path) -> None:
    path = tmp_path / "missing.txt"

    with pytest.raises(GuardedReadError) as exc_info:
        read_guarded(path, lambda text: text)

    assert type(exc_info.value) is GuardedReadError
