package org.speckitty.missionstatus.testsupport;

import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.file.FileVisitResult;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.SimpleFileVisitor;
import java.nio.file.attribute.BasicFileAttributes;

/**
 * Temporary directories of the fixture factories. One base directory per JVM, removed by a shutdown hook (links are deleted, never
 * followed), so a run leaves nothing behind. The path of a scratch directory is never printed: the repository is public.
 */
final class ScratchDirs {

  private static Path base;

  private ScratchDirs() {}

  /** A fresh empty directory below the per-JVM base. */
  static synchronized Path create() {
    try {
      if (base == null) {
        base = Files.createTempDirectory("ms-golden-");
        Path toDelete = base;
        Runtime.getRuntime().addShutdownHook(new Thread(() -> deleteTree(toDelete)));
      }
      return Files.createTempDirectory(base, "case-");
    } catch (IOException failure) {
      throw new UncheckedIOException(failure);
    }
  }

  /** Deletes a tree without following links; a failure to delete is ignored (the operating system cleans the temporary directory). */
  static void deleteTree(Path root) {
    try {
      Files.walkFileTree(
          root,
          new SimpleFileVisitor<>() {
            @Override
            public FileVisitResult visitFile(Path file, BasicFileAttributes attributes) throws IOException {
              Files.deleteIfExists(file);
              return FileVisitResult.CONTINUE;
            }

            @Override
            public FileVisitResult postVisitDirectory(Path dir, IOException failure) throws IOException {
              Files.deleteIfExists(dir);
              return FileVisitResult.CONTINUE;
            }
          });
    } catch (IOException ignored) {
      // best effort at shutdown
    }
  }
}
