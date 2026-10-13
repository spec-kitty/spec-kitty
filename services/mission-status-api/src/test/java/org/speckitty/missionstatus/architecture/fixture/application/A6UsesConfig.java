package org.speckitty.missionstatus.architecture.fixture.application;

/** Architecture-rule fixture: planted violation of rule 6 (config used by application). */
public final class A6UsesConfig {
  public Object wiring() {
    return new org.speckitty.missionstatus.architecture.fixture.config.Wiring();
  }
}
