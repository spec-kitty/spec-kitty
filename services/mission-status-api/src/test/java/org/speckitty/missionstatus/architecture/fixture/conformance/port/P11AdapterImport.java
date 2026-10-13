package org.speckitty.missionstatus.architecture.fixture.conformance.port;

/** Architecture-rule fixture: planted violation of rule 11 (port-level class importing an adapter). */
public final class P11AdapterImport {
  public Object source() {
    return new org.speckitty.missionstatus.architecture.fixture.adapter.out.filesystem.FsSource();
  }
}
