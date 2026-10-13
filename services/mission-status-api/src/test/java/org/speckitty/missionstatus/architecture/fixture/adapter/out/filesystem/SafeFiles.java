package org.speckitty.missionstatus.architecture.fixture.adapter.out.filesystem;

/** Architecture-rule fixture: part of the conforming skeleton or one planted violation. */
public final class SafeFiles {
  public String read(java.nio.file.Path path) throws java.io.IOException {
    return java.nio.file.Files.readString(path);
  }
}
