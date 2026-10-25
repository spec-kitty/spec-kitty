package org.speckitty.missionstatus.architecture.fixture;

import java.net.URI;

/** Planted violation: a decoder that reaches a package outside the allowlist (java.net stands in for any framework or transport). */
public final class OutsidePackageDecoder {

  private OutsidePackageDecoder() {}

  public static URI decode(String line) {
    return URI.create(line);
  }
}
