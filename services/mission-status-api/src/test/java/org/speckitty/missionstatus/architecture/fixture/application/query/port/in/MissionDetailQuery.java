package org.speckitty.missionstatus.architecture.fixture.application.query.port.in;

/** Architecture-rule fixture, conforming: a detail port with a typed (non-String) parameter and no checked exception. */
public interface MissionDetailQuery {
  org.speckitty.missionstatus.architecture.fixture.domain.readmodel.detail.DetailValue mission(org.speckitty.missionstatus.architecture.fixture.domain.readmodel.detail.DetailValue id);
}
