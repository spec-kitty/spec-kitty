package org.speckitty.missionstatus.architecture.fixture;

import java.util.concurrent.ConcurrentHashMap;

/** Planted violation: a decoder that keeps state in java.util.concurrent. */
public final class ConcurrentDecoder {

  private final ConcurrentHashMap<String, String> seen = new ConcurrentHashMap<>();

  public String decode(String line) {
    return seen.computeIfAbsent(line, String::strip);
  }
}
