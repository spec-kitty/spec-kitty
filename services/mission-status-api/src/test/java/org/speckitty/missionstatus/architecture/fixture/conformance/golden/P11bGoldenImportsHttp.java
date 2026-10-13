package org.speckitty.missionstatus.architecture.fixture.conformance.golden;

/** Architecture-rule fixture: planted violation of rule 11b (golden class importing an adapter other than the filesystem one). */
public final class P11bGoldenImportsHttp {
  public Object controller() {
    return new org.speckitty.missionstatus.architecture.fixture.adapter.in.http.Controller();
  }
}
