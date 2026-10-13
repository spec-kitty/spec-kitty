package org.speckitty.missionstatus.architecture.fixture.adapter.out.filesystem.codec;

/** Architecture-rule fixture: planted violation of rule 12 (second control: file API in the decoder). */
public final class C12bFiles {
  public String read(java.nio.file.Path path) throws java.io.IOException {
    return java.nio.file.Files.readString(path);
  }
}
