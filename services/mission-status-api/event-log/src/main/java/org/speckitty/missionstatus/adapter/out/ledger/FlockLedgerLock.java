package org.speckitty.missionstatus.adapter.out.ledger;

import java.io.IOException;
import java.lang.foreign.Arena;
import java.lang.foreign.FunctionDescriptor;
import java.lang.foreign.Linker;
import java.lang.foreign.MemoryLayout;
import java.lang.foreign.MemorySegment;
import java.lang.foreign.ValueLayout;
import java.lang.invoke.MethodHandle;
import java.lang.invoke.VarHandle;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Locale;
import java.util.concurrent.atomic.AtomicBoolean;

/**
 * {@code flock(LOCK_EX | LOCK_NB)} through the Foreign Function and Memory API: the very lock {@code kernel.locks} takes with
 * {@code fcntl.flock} on Linux and macOS. The lock file is opened {@code O_NOFOLLOW} (a symbolic link is refused, as {@code kernel.locks}
 * refuses one) and {@code O_CLOEXEC} (a spawned process never inherits the lock), mode {@code 0600}. Closing the descriptor releases the
 * lock; the holder closes it once only, so a reused descriptor number is never closed by mistake.
 *
 * <p>A deployable that uses it enables native access ({@code --enable-native-access=ALL-UNNAMED}, or {@code Enable-Native-Access} in a jar
 * manifest); without it the JDK prints a warning. A native image must register the downcalls; none is reachable from the query service's
 * native binary today. The path is passed to {@code open(2)} encoded as UTF-8.
 */
final class FlockLedgerLock implements LedgerLock {

  /** The {@code open(2)}, {@code flock(2)} and errno constants of one platform. */
  record Constants(int oCreat, int oNofollow, int oCloexec, int ewouldblock, int eloop) {}

  private static final int O_RDWR = 2;
  private static final int LOCK_EX = 2;
  private static final int LOCK_NB = 4;
  private static final int MODE_0600 = 0600;
  /** EINTR is 4 on Linux and macOS. */
  private static final int EINTR = 4;

  /** Linux on x86-64 and on AArch64 (whose O_NOFOLLOW differs), and macOS (the same values on both architectures). */
  static final Constants LINUX_X64 = new Constants(0x40, 0x20000, 0x80000, 11, 40);
  static final Constants LINUX_AARCH64 = new Constants(0x40, 0x8000, 0x80000, 11, 40);
  static final Constants MACOS = new Constants(0x200, 0x100, 0x1000000, 35, 62);

  private static final Linker LINKER = Linker.nativeLinker();
  private static final MemoryLayout CAPTURE = Linker.Option.captureStateLayout();
  private static final VarHandle ERRNO = CAPTURE.varHandle(MemoryLayout.PathElement.groupElement("errno"));
  private static final MethodHandle OPEN =
      downcall(
          "open",
          FunctionDescriptor.of(ValueLayout.JAVA_INT, ValueLayout.ADDRESS, ValueLayout.JAVA_INT, ValueLayout.JAVA_INT),
          Linker.Option.firstVariadicArg(2),
          Linker.Option.captureCallState("errno"));
  private static final MethodHandle FLOCK =
      downcall("flock", FunctionDescriptor.of(ValueLayout.JAVA_INT, ValueLayout.JAVA_INT, ValueLayout.JAVA_INT), Linker.Option.captureCallState("errno"));
  private static final MethodHandle CLOSE = downcall("close", FunctionDescriptor.of(ValueLayout.JAVA_INT, ValueLayout.JAVA_INT));

  private final Constants constants;

  FlockLedgerLock() {
    this(constantsFor(System.getProperty("os.name"), System.getProperty("os.arch")));
  }

  FlockLedgerLock(Constants constants) {
    this.constants = constants;
  }

  /** The constants of a supported platform; any other refuses, rather than guess another system's flag values. */
  static Constants constantsFor(String osName, String osArch) {
    String os = osName.toLowerCase(Locale.ROOT);
    if (os.contains("mac")) {
      return MACOS;
    }
    if (os.contains("linux")) {
      return switch (osArch) {
        case "amd64", "x86_64" -> LINUX_X64;
        case "aarch64", "arm64" -> LINUX_AARCH64;
        default -> throw new UnsupportedOperationException("flock ledger lock: unsupported Linux architecture " + osArch);
      };
    }
    throw new UnsupportedOperationException("flock ledger lock: supported on Linux and macOS only, not " + osName);
  }

  private static MethodHandle downcall(String symbol, FunctionDescriptor descriptor, Linker.Option... options) {
    return LINKER.downcallHandle(LINKER.defaultLookup().find(symbol).orElseThrow(), descriptor, options);
  }

  @Override
  public Held tryAcquire(Path lockFile) throws IOException {
    // Absolute, so the path open(2) sees does not depend on the process working directory matching user.dir.
    Path absolute = lockFile.toAbsolutePath();
    Files.createDirectories(absolute.getParent());
    try (Arena arena = Arena.ofConfined()) {
      MemorySegment state = arena.allocate(CAPTURE);
      MemorySegment path = arena.allocateFrom(absolute.toString());
      int flags = O_RDWR | constants.oCreat() | constants.oNofollow() | constants.oCloexec();
      int fd;
      int errno;
      do {
        fd = (int) OPEN.invokeExact(state, path, flags, MODE_0600);
        errno = fd < 0 ? (int) ERRNO.get(state, 0L) : 0;
      } while (fd < 0 && errno == EINTR);
      if (fd < 0) {
        if (errno == constants.eloop()) {
          throw new IOException(lockFile + " is a symbolic link; refusing to lock through it");
        }
        throw new IOException("open(" + lockFile + ") failed, errno " + errno);
      }
      return lockOrClose(state, fd, lockFile);
    } catch (IOException | RuntimeException | Error e) {
      throw e;
    } catch (Throwable e) {
      throw new IOException(e);
    }
  }

  /** Takes the lock on {@code fd}, or closes {@code fd} on every path that does not hand it to a holder. */
  private Held lockOrClose(MemorySegment state, int fd, Path lockFile) throws Throwable {
    boolean handedOver = false;
    try {
      int result = (int) FLOCK.invokeExact(state, fd, LOCK_EX | LOCK_NB);
      if (result == 0) {
        handedOver = true;
        AtomicBoolean open = new AtomicBoolean(true);
        return () -> {
          if (open.getAndSet(false)) {
            close(fd);
          }
        };
      }
      int errno = (int) ERRNO.get(state, 0L);
      // EINTR counts as contention: the bounded wait simply tries again.
      if (errno == constants.ewouldblock() || errno == EINTR) {
        return null;
      }
      throw new IOException("flock(" + lockFile + ") failed, errno " + errno);
    } finally {
      if (!handedOver) {
        close(fd);
      }
    }
  }

  private static void close(int fd) throws IOException {
    try {
      int ignored = (int) CLOSE.invokeExact(fd);
    } catch (Throwable e) {
      throw new IOException(e);
    }
  }
}
