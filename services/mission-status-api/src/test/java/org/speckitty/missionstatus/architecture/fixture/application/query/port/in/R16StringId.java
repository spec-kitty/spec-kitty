package org.speckitty.missionstatus.architecture.fixture.application.query.port.in;

/** Architecture-rule fixture, planted violation of rule 16 clause c: a port method takes a String identifier. */
public interface R16StringId {
  org.speckitty.missionstatus.architecture.fixture.domain.readmodel.detail.DetailValue read(String missionId);
}
