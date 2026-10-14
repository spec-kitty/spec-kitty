package org.speckitty.missionstatus.architecture.fixture.application.query.port.in;

/** Architecture-rule fixture, planted violation of PortExposesNoLedgerRowTest: a port method returns a raw LedgerLine. */
public interface LeakyLedgerLine {
  org.speckitty.missionstatus.domain.model.LedgerLine leak();
}
