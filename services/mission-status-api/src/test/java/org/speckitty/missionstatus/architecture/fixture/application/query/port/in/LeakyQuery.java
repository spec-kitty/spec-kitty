package org.speckitty.missionstatus.architecture.fixture.application.query.port.in;

/** Architecture-rule fixture, planted violation of PortExposesNoLedgerRowTest: a port method returns a raw ledger type. */
public interface LeakyQuery {
  org.speckitty.missionstatus.domain.model.LineKind leak();
}
