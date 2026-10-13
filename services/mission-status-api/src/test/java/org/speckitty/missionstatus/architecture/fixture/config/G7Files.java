package org.speckitty.missionstatus.architecture.fixture.config;

/** Architecture-rule fixture: planted violation of rule 7 (file API in config). */
public final class G7Files {
  public String read(java.nio.file.Path path) throws java.io.IOException {
    return java.nio.file.Files.readString(path);
  }
}
