package org.speckitty.missionstatus.architecture.fixture.adapter.in.other;

/** Architecture-rule fixture, planted violation of rule 3: a sibling inbound adapter reaches the query service. */
public final class UsesService {
  public Object reach() {
    return new org.speckitty.missionstatus.architecture.fixture.application.query.Service(null, null);
  }
}
