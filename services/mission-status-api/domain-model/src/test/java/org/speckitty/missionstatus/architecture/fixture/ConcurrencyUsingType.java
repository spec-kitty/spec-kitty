package org.speckitty.missionstatus.architecture.fixture;

import java.util.concurrent.ConcurrentHashMap;

/** Planted violation: a type that depends on java.util.concurrent. */
public final class ConcurrencyUsingType {

  private final ConcurrentHashMap<String, String> map = new ConcurrentHashMap<>();

  public String get(String key) {
    return map.get(key);
  }
}
