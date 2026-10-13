package org.speckitty.missionstatus.architecture.fixture.adapter.out.filesystem;

/** Architecture-rule fixture: part of the conforming skeleton or one planted violation. */
public final class FsSource implements org.speckitty.missionstatus.architecture.fixture.application.query.port.out.Source {
  @Override
  public org.speckitty.missionstatus.architecture.fixture.domain.Value read() {
    return new org.speckitty.missionstatus.architecture.fixture.adapter.out.filesystem.codec.Decoder().decode("line");
  }
}
