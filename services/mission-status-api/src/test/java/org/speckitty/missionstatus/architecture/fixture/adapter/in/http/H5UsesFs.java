package org.speckitty.missionstatus.architecture.fixture.adapter.in.http;

/** Architecture-rule fixture: planted violation of rule 5 (inbound adapter reaching the outbound adapter). */
public final class H5UsesFs {
  public Object source() {
    return new org.speckitty.missionstatus.architecture.fixture.adapter.out.filesystem.FsSource();
  }
}
