package org.speckitty.missionstatus.architecture.fixture;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;

/** Planted violation: a type that reads a file. */
public final class FileReadingType {

  private FileReadingType() {}

  public static byte[] read(Path path) throws IOException {
    return Files.readAllBytes(path);
  }
}
