package org.speckitty.missionstatus.architecture.fixture.adapter.in.http.detail;

/** Architecture-rule fixture, planted violation of rule 15: a detail controller calls a deriver of the read model. */
public final class R15Controller {
  public int get() {
    return new org.speckitty.missionstatus.architecture.fixture.domain.readmodel.derive.R15Deriver().derive();
  }
}
