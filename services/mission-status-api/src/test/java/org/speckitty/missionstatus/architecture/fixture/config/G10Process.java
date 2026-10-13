package org.speckitty.missionstatus.architecture.fixture.config;

/** Architecture-rule fixture: planted violation of rule 10 (ProcessBuilder). */
public final class G10Process {
  public Object builder() {
    return new ProcessBuilder("true");
  }
}
