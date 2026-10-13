package org.speckitty.missionstatus.architecture.fixture.application.query;

/** Architecture-rule fixture: part of the conforming skeleton or one planted violation. */
public final class Service implements org.speckitty.missionstatus.architecture.fixture.application.query.port.in.Query {
  private final java.util.concurrent.ScheduledExecutorService executor;
  private final org.speckitty.missionstatus.architecture.fixture.application.query.port.out.Source source;

  public Service(java.util.concurrent.ScheduledExecutorService executor, org.speckitty.missionstatus.architecture.fixture.application.query.port.out.Source source) {
    this.executor = executor;
    this.source = source;
  }

  @Override
  public org.speckitty.missionstatus.architecture.fixture.domain.Value value() {
    return source.read();
  }
}
