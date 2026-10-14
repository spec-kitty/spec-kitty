package org.speckitty.missionstatus.architecture.fixture.application.query;

import java.nio.ByteBuffer;

/** Architecture-rule fixture, planted violation of rule 2b only: an application class that wraps bytes in a {@code ByteBuffer} (D-70, AC-7.3). */
public final class A2cByteBuffer {
  public ByteBuffer wrap(byte[] bytes) {
    return ByteBuffer.wrap(bytes);
  }
}
