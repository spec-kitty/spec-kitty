package org.speckitty.missionstatus.adapter.in.http.flow;

import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.HexFormat;
import java.util.List;

/**
 * AC-16b: the fingerprint of a project directory is the content hash, the listing (every name, so a lock or temporary file shows) and
 * the modification time of every file and directory.
 */
final class Fingerprint {

  private Fingerprint() {}

  static List<String> of(Path root) {
    List<String> entries = new ArrayList<>();
    try (var walk = Files.walk(root)) {
      for (Path path : walk.sorted().toList()) {
        String name = root.relativize(path).toString();
        String time = Files.getLastModifiedTime(path, java.nio.file.LinkOption.NOFOLLOW_LINKS).toMillis() + "";
        if (Files.isSymbolicLink(path)) {
          entries.add("L " + name + " -> " + Files.readSymbolicLink(path) + " " + time);
        } else if (Files.isDirectory(path)) {
          try (var children = Files.list(path)) {
            entries.add("D " + name + " " + children.count() + " " + time);
          }
        } else {
          entries.add("F " + name + " " + Files.size(path) + " " + HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(Files.readAllBytes(path))) + " " + time);
        }
      }
    } catch (IOException failure) {
      throw new UncheckedIOException(failure);
    } catch (java.security.NoSuchAlgorithmException impossible) {
      throw new IllegalStateException(impossible);
    }
    return entries;
  }
}
