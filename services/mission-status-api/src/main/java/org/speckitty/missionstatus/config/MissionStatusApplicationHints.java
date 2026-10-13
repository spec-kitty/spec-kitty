package org.speckitty.missionstatus.config;

import org.springframework.aot.hint.RuntimeHints;
import org.springframework.aot.hint.RuntimeHintsRegistrar;

/**
 * Native-image resource hints for resources the code reads by name. Without a hint a classpath resource is absent in the native
 * binary (research.md spike record, T008 item 3). Later work packages add the other resources they read.
 */
class MissionStatusApplicationHints implements RuntimeHintsRegistrar {

  @Override
  public void registerHints(RuntimeHints hints, ClassLoader classLoader) {
    hints.resources().registerPattern("contract/openapi.yaml");
  }
}
