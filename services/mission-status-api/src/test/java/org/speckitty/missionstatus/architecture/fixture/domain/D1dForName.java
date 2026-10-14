package org.speckitty.missionstatus.architecture.fixture.domain;

/** Architecture-rule fixture, planted violation of rule 1d only: a reflective class load (java.lang types only, so rule 1b stays green). */
public final class D1dForName {
  public Class<?> load() throws ClassNotFoundException {
    return Class.forName("java.nio.file.Files");
  }
}
