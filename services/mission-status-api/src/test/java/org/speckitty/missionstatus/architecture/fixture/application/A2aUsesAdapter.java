package org.speckitty.missionstatus.architecture.fixture.application;

/** Architecture-rule fixture: planted violation of rule 2 (adapter in application). */
public final class A2aUsesAdapter {
  public Object controller() {
    return new org.speckitty.missionstatus.architecture.fixture.adapter.in.http.Controller();
  }
}
