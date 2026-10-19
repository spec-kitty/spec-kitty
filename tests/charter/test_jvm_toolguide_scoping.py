"""JVM toolguides (Maven/Gradle supply chain, Maven review checks) are scoped to the ``jvm`` family.

A project declaring Kotlin and Gradle must receive the shared JVM toolguides;
a Python project must receive neither; a Java project keeps receiving both.
"""

from __future__ import annotations

import pytest

from charter.activation.catalog import load_offering_catalog
from charter.activation.language_authority import declared_languages

pytestmark = pytest.mark.unit

_JVM_TOOLGUIDES = frozenset({"java-supply-chain", "maven-review-checks"})


def _toolguides_for(answer: str) -> frozenset[str]:
    return load_offering_catalog(active_languages=declared_languages(answer)).toolguides


@pytest.mark.parametrize("answer", ["Kotlin, Gradle", "Java", "Gradle"])
def test_jvm_projects_receive_both_jvm_toolguides(answer: str) -> None:
    assert _toolguides_for(answer) >= _JVM_TOOLGUIDES


def test_python_project_receives_neither_jvm_toolguide() -> None:
    assert not (_JVM_TOOLGUIDES & _toolguides_for("Python"))
