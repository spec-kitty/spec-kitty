package org.speckitty.missionstatus.architecture.fixture.conformance.port;

/** Architecture-rule fixture: part of the conforming skeleton or one planted violation. */
public final class PortCase {
  public String run() {
    return new org.speckitty.missionstatus.architecture.fixture.testsupport.Support().query().value().text();
  }
}
