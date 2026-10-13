package org.speckitty.missionstatus.nativesmoke;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.Locale;
import java.util.OptionalLong;
import java.util.concurrent.TimeUnit;

/**
 * Thread count and resident set of ANOTHER process, without a native library: {@code /proc/<pid>/status} on Linux, {@code ps} on macOS,
 * a one-line PowerShell call on Windows. Test code only. A figure the operating system cannot give is empty, and the caller records "not
 * measurable on this leg" (never a silent skip).
 */
final class ProcessMetrics {

  private ProcessMetrics() {}

  static OptionalLong threads(long pid) {
    String os = System.getProperty("os.name", "").toLowerCase(Locale.ROOT);
    if (os.contains("linux")) {
      return procStatus(pid, "Threads:", 1);
    }
    if (os.contains("mac") || os.contains("darwin")) {
      // `ps -M` prints a header and then one line per thread
      List<String> lines = run("ps", "-M", "-p", Long.toString(pid));
      return lines.size() > 1 ? OptionalLong.of(lines.size() - 1) : OptionalLong.empty();
    }
    if (os.contains("windows")) {
      return parse(run("powershell", "-NoProfile", "-NonInteractive", "-Command", "(Get-Process -Id " + pid + ").Threads.Count"), 1);
    }
    return OptionalLong.empty();
  }

  private static final String CARRIER_FULL_PREFIX = "ForkJoinPool-";
  private static final int COMM_LENGTH = 15;
  private static final java.util.regex.Pattern CARRIER_TAIL = java.util.regex.Pattern.compile("^(.*?)(\\d+)-worker-(\\d+)$");

  /**
   * Linux: the threads of the process that are virtual-thread carriers (named {@code ForkJoinPool-n-worker-m}). The carrier pool is
   * capped by the core count and does not grow with connections, so the NFR-004 thread budget is read net of it, as on the JVM leg, and
   * the peak number of carriers is asserted at most the core count. Empty when the platform cannot name threads: the raw count is then used.
   * See {@link #isCarrierName} for what the 15-character kernel limit lets this see.
   */
  static OptionalLong carriers(long pid) {
    Path tasks = Path.of("/proc", Long.toString(pid), "task");
    if (!Files.isDirectory(tasks)) {
      return OptionalLong.empty();
    }
    long carriers = 0;
    try (var entries = Files.list(tasks)) {
      for (Path task : entries.toList()) {
        try {
          if (isCarrierName(Files.readString(task.resolve("comm"), StandardCharsets.UTF_8).strip())) {
            carriers++;
          }
        } catch (IOException gone) {
          // the thread ended between the listing and the read
        }
      }
    } catch (IOException | RuntimeException unreadable) {
      return OptionalLong.empty();
    }
    return OptionalLong.of(carriers);
  }

  /**
   * Whether a kernel thread name ({@code comm}, at most 15 characters) is the name of a carrier. The native image keeps the LAST 15
   * characters of {@code ForkJoinPool-n-worker-m}, so the name is accepted when it is {@code <suffix of "ForkJoinPool-">n-worker-m}
   * and either it is exactly 15 characters long (a truncated tail) or it is the whole, untruncated name. What it cannot see: a thread
   * of another pool whose name ends in {@code ...Pool-n-worker-m} and whose last 15 characters equal a carrier's cannot be told apart
   * from a carrier by the kernel name alone. That is the residual, and it needs a differently named pool with this exact worker
   * naming; the JVM leg, which sees whole names, has no such gap.
   */
  static boolean isCarrierName(String comm) {
    java.util.regex.Matcher m = CARRIER_TAIL.matcher(comm);
    if (!m.matches()) {
      return false;
    }
    String prefix = m.group(1);
    if (prefix.equals(CARRIER_FULL_PREFIX)) {
      return true;
    }
    return comm.length() == COMM_LENGTH && !prefix.isEmpty() && CARRIER_FULL_PREFIX.endsWith(prefix);
  }

  /** Linux: the thread names of the process grouped without digits (the classification input of a thread-count miss); empty elsewhere. */
  static String threadNames(long pid) {
    Path tasks = Path.of("/proc", Long.toString(pid), "task");
    if (!Files.isDirectory(tasks)) {
      return "(thread names not available on this leg)";
    }
    java.util.Map<String, Integer> byName = new java.util.TreeMap<>();
    try (var entries = Files.list(tasks)) {
      for (Path task : entries.toList()) {
        try {
          byName.merge(Files.readString(task.resolve("comm"), StandardCharsets.UTF_8).strip().replaceAll("[0-9]+", "#"), 1, Integer::sum);
        } catch (IOException gone) {
          // the thread ended between the listing and the read
        }
      }
    } catch (IOException | RuntimeException unreadable) {
      return "(thread names not readable)";
    }
    return byName.toString();
  }

  /** Resident set size in bytes. */
  static OptionalLong residentBytes(long pid) {
    String os = System.getProperty("os.name", "").toLowerCase(Locale.ROOT);
    if (os.contains("linux")) {
      return procStatus(pid, "VmRSS:", 1024);
    }
    if (os.contains("mac") || os.contains("darwin")) {
      return parse(run("ps", "-o", "rss=", "-p", Long.toString(pid)), 1024);
    }
    if (os.contains("windows")) {
      return parse(run("powershell", "-NoProfile", "-NonInteractive", "-Command", "(Get-Process -Id " + pid + ").WorkingSet64"), 1);
    }
    return OptionalLong.empty();
  }

  /** The first number after {@code key} in {@code /proc/<pid>/status}, times {@code factor}. */
  private static OptionalLong procStatus(long pid, String key, long factor) {
    try {
      for (String line : Files.readAllLines(Path.of("/proc", Long.toString(pid), "status"), StandardCharsets.UTF_8)) {
        if (line.startsWith(key)) {
          return OptionalLong.of(Long.parseLong(line.substring(key.length()).strip().split("\\s+")[0]) * factor);
        }
      }
    } catch (IOException | RuntimeException unreadable) {
      // the process may have gone, or the file system has no /proc
    }
    return OptionalLong.empty();
  }

  private static OptionalLong parse(List<String> lines, long factor) {
    for (String line : lines) {
      String text = line.strip();
      if (!text.isEmpty()) {
        try {
          return OptionalLong.of(Long.parseLong(text) * factor);
        } catch (NumberFormatException notANumber) {
          return OptionalLong.empty();
        }
      }
    }
    return OptionalLong.empty();
  }

  private static List<String> run(String... command) {
    try {
      Process process = new ProcessBuilder(command).redirectErrorStream(true).start();
      List<String> lines;
      try (BufferedReader reader = new BufferedReader(new InputStreamReader(process.getInputStream(), StandardCharsets.UTF_8))) {
        lines = reader.lines().toList();
      }
      process.waitFor(30, TimeUnit.SECONDS);
      return lines;
    } catch (IOException failure) {
      return List.of();
    } catch (InterruptedException interrupted) {
      Thread.currentThread().interrupt();
      return List.of();
    }
  }
}
