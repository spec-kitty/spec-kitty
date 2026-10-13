package org.speckitty.missionstatus.nativesmoke;

import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.List;
import java.util.Locale;

/**
 * The per-leg digest (AC-15e): the SHA-256 of the concatenated RAW response bodies, in replay order, and nothing else. A body is hashed
 * as it was received; it is never parsed, canonicalised or re-serialised, and the operating system and the architecture never enter the
 * hash. They only name the file ({@code digest-<os>-<arch>.json}), which {@code scripts/ci/mission_status_gate_checks.py digests} reads.
 */
final class Digest {

  static final String OS_KEY = "os";
  static final String ARCH_KEY = "arch";
  static final String REQUEST_COUNT_KEY = "requestCount";
  static final String BODY_COUNT_KEY = "bodyCount";
  static final String SHA256_KEY = "sha256";

  private Digest() {}

  static String sha256(List<byte[]> bodies) {
    if (bodies.isEmpty()) {
      throw new IllegalArgumentException("no body to hash: an empty replay has no digest");
    }
    MessageDigest digest = newDigest();
    for (byte[] body : bodies) {
      digest.update(body);
    }
    return hex(digest.digest());
  }

  static String hex(byte[] bytes) {
    StringBuilder out = new StringBuilder(bytes.length * 2);
    for (byte b : bytes) {
      out.append(Character.forDigit((b >> 4) & 0xF, 16)).append(Character.forDigit(b & 0xF, 16));
    }
    return out.toString();
  }

  private static MessageDigest newDigest() {
    try {
      return MessageDigest.getInstance("SHA-256");
    } catch (NoSuchAlgorithmException impossible) {
      throw new IllegalStateException(impossible);
    }
  }

  /** Writes {@code digest-<os>-<arch>.json} into {@code directory} (created if needed) and returns its path. */
  static Path write(Path directory, String os, String arch, int requestCount, int bodyCount, String sha256) {
    try {
      Files.createDirectories(directory);
      Path file = directory.resolve("digest-" + os + "-" + arch + ".json");
      String json =
          "{\"" + OS_KEY + "\":\"" + os + "\",\"" + ARCH_KEY + "\":\"" + arch + "\",\"" + REQUEST_COUNT_KEY + "\":" + requestCount + ",\"" + BODY_COUNT_KEY + "\":" + bodyCount
              + ",\"" + SHA256_KEY + "\":\"" + sha256 + "\"}\n";
      Files.writeString(file, json, StandardCharsets.UTF_8);
      return file;
    } catch (IOException failure) {
      throw new UncheckedIOException(failure);
    }
  }

  static String osToken(String osName) {
    String name = osName.toLowerCase(Locale.ROOT);
    if (name.startsWith("linux")) {
      return "linux";
    }
    if (name.startsWith("mac") || name.startsWith("darwin")) {
      return "macos";
    }
    if (name.startsWith("windows")) {
      return "windows";
    }
    throw new IllegalArgumentException("unsupported operating system: " + osName);
  }

  static String archToken(String archName) {
    String name = archName.toLowerCase(Locale.ROOT);
    if (name.equals("amd64") || name.equals("x86_64") || name.equals("x64")) {
      return "x64";
    }
    if (name.equals("aarch64") || name.equals("arm64")) {
      return "arm64";
    }
    throw new IllegalArgumentException("unsupported architecture: " + archName);
  }
}
