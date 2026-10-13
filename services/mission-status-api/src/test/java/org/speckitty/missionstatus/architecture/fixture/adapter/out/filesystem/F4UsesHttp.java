package org.speckitty.missionstatus.architecture.fixture.adapter.out.filesystem;

/** Architecture-rule fixture: planted violation of rule 4 (outbound adapter reaching the inbound adapter). */
public final class F4UsesHttp {
  public Object controller() {
    return new org.speckitty.missionstatus.architecture.fixture.adapter.in.http.Controller();
  }
}
