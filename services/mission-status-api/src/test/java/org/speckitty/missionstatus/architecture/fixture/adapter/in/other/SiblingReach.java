package org.speckitty.missionstatus.architecture.fixture.adapter.in.other;

/** Architecture-rule fixture, planted violation of rule 3 only: an inbound adapter reaches a sibling inbound adapter (adapter.in.http), and nothing else forbidden. */
public final class SiblingReach {
  public Object reach() {
    return new org.speckitty.missionstatus.architecture.fixture.adapter.in.http.Controller();
  }
}
