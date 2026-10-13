package org.speckitty.missionstatus.architecture.fixture.adapter.out.filesystem.codec;

/** Architecture-rule fixture: part of the conforming skeleton or one planted violation. */
public final class Decoder {
  public org.speckitty.missionstatus.architecture.fixture.domain.Value decode(String line) {
    return new org.speckitty.missionstatus.architecture.fixture.domain.Value(line);
  }
}
