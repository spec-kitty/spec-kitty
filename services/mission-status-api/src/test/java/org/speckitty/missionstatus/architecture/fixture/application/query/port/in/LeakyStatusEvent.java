package org.speckitty.missionstatus.architecture.fixture.application.query.port.in;

/** Architecture-rule fixture, planted violation of PortExposesNoLedgerRowTest: a port method returns a raw StatusEvent. */
public interface LeakyStatusEvent {
  org.speckitty.missionstatus.domain.model.StatusEvent leak();
}
