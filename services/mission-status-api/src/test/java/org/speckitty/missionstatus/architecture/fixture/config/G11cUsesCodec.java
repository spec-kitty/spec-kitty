package org.speckitty.missionstatus.architecture.fixture.config;

/** Architecture-rule fixture: planted violation of rule 11 (codec used outside testsupport and the filesystem adapter). */
public final class G11cUsesCodec {
  public Object decoder() {
    return new org.speckitty.missionstatus.architecture.fixture.adapter.out.filesystem.codec.Decoder();
  }
}
