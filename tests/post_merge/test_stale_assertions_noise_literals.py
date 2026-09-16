"""Unit tests for the #3957 structural noise-literal gate.

``_is_noise_literal`` extends the #2343 genuineness stop-list with three
structural rules that closed its residual (#3957):

- one-character literals (F-60: ``open()`` mode strings like ``"a"``),
- ``open()`` file-mode combinations ("rb", "w+", "ab+", ...),
- single bare lowercase words with no symbol shape (F-79: "items", "url",
  "payload").

Symbol-shaped single tokens ("E001", "old_key", "BadRequest") and multi-word
literals ("bad request") remain signal — genuineness, not length, is still
the rule (FR-004).
"""

from __future__ import annotations

import pytest

from specify_cli.post_merge.stale_assertions import _is_noise_literal

pytestmark = [pytest.mark.unit, pytest.mark.fast]


class TestIsNoiseLiteral:
    """Unit tests for the _is_noise_literal helper (#3957)."""

    @pytest.mark.parametrize(
        "value",
        [
            # F-60: one-character literals.
            "a",
            "r",
            "w",
            "x",
            "1",
            # open() file-mode combinations.
            "rb",
            "wb",
            "ab",
            "r+",
            "w+",
            "a+",
            "w+b",
            "ab+",
            # F-79: single bare lowercase words.
            "items",
            "url",
            "payload",
            "checklist",
            "schema",
            # #2343 stop-list still applies (delegation).
            "ok",
            "error",
            "unknown",
            "message",
            # Empty / punctuation-only.
            "",
            "   ",
            "---",
            "\n",
        ],
    )
    def test_noise_literals_are_suppressed(self, value: str) -> None:
        assert _is_noise_literal(value) is True, f"{value!r} must be classified as noise (never assert-critical signal)"

    @pytest.mark.parametrize(
        "value",
        [
            # Symbol-shaped single tokens: uppercase, digit, underscore.
            "E001",
            "old_key",
            "ERR_TIMEOUT",
            "BadRequest",
            "sha256",
            # Multi-word literals.
            "bad request",
            "old error message",
            "Connection refused — retry",
            # Structured fragments (path, template) are not bare words.
            "/old/path",
            "v1/items",
        ],
    )
    def test_signal_literals_are_emitted(self, value: str) -> None:
        assert _is_noise_literal(value) is False, f"{value!r} must remain signal (symbol-shaped or multi-word)"
