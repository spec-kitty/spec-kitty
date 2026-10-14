package org.speckitty.missionstatus.architecture.fixture.application.query.index;

/** Architecture-rule fixture: planted violation of rule 12c (an application class that references the codec instead of calling the port). */
public final class A12cUsesCodec {
  public Object decoder() {
    return new org.speckitty.missionstatus.architecture.fixture.adapter.out.filesystem.codec.Decoder();
  }
}
