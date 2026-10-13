package org.speckitty.missionstatus.architecture.fixture.testsupport;

/** Architecture-rule fixture: part of the conforming skeleton or one planted violation. */
public final class Support {
  public org.speckitty.missionstatus.architecture.fixture.application.query.port.in.Query query() {
    return new org.speckitty.missionstatus.architecture.fixture.application.query.Service(null, new org.speckitty.missionstatus.architecture.fixture.adapter.out.filesystem.FsSource());
  }

  public org.speckitty.missionstatus.architecture.fixture.adapter.out.filesystem.codec.Decoder decoder() {
    return new org.speckitty.missionstatus.architecture.fixture.adapter.out.filesystem.codec.Decoder();
  }
}
