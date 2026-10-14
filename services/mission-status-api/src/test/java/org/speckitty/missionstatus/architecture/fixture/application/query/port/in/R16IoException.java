package org.speckitty.missionstatus.architecture.fixture.application.query.port.in;

/** Architecture-rule fixture, planted violation of rule 16 clause b: a port method declares a checked exception. */
public interface R16IoException {
  org.speckitty.missionstatus.architecture.fixture.domain.readmodel.detail.DetailValue read(org.speckitty.missionstatus.architecture.fixture.domain.readmodel.detail.DetailValue id) throws java.io.IOException;
}
