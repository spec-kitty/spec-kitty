package org.speckitty.missionstatus.architecture.fixture.application.query;

/** Architecture-rule fixture, planted violation of rule 2d: reflective class loading in the application. */
public final class A2dForName {
  public Class<?> load() throws ClassNotFoundException {
    return Class.forName("java.nio.file.Files");
  }
}
