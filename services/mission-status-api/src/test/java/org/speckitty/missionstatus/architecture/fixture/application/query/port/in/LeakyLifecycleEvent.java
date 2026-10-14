package org.speckitty.missionstatus.architecture.fixture.application.query.port.in;

/** Architecture-rule fixture, planted violation of PortExposesNoLedgerRowTest: a port method returns a raw LifecycleEvent. */
public interface LeakyLifecycleEvent {
  org.speckitty.missionstatus.domain.model.LifecycleEvent leak();
}
