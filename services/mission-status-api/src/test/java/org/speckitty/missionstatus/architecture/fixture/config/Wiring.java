package org.speckitty.missionstatus.architecture.fixture.config;

@org.springframework.context.annotation.Configuration
/** Architecture-rule fixture: part of the conforming skeleton or one planted violation. */
public class Wiring {
  public org.speckitty.missionstatus.architecture.fixture.application.query.Service service() {
    return new org.speckitty.missionstatus.architecture.fixture.application.query.Service(java.util.concurrent.Executors.newSingleThreadScheduledExecutor(), new org.speckitty.missionstatus.architecture.fixture.adapter.out.filesystem.FsSource());
  }
}
