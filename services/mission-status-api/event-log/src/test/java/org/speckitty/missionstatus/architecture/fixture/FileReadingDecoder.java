package org.speckitty.missionstatus.architecture.fixture;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;

/** Planted violation: a decoder that opens the file itself. */
public final class FileReadingDecoder {

  private FileReadingDecoder() {}

  public static byte[] read(Path path) throws IOException {
    return Files.readAllBytes(path);
  }
}
