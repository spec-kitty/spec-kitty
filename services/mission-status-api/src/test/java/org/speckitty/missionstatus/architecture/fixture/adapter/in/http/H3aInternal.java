package org.speckitty.missionstatus.architecture.fixture.adapter.in.http;

/** Architecture-rule fixture: planted violation of rule 3 (application internals in the controller). */
public final class H3aInternal {
  public Object service() {
    return new org.speckitty.missionstatus.architecture.fixture.application.query.Service(null, null);
  }
}
