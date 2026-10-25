package org.speckitty.missionstatus.architecture.fixture;

import java.nio.file.Files;
import java.nio.file.Path;

/** Planted violation: a decoder that reaches for the file system through {@code java.nio.file} alone (no {@code java.io} type). */
public final class FileReadingDecoder {

  private FileReadingDecoder() {}

  public static boolean exists(String name) {
    return Files.exists(Path.of(name));
  }
}
