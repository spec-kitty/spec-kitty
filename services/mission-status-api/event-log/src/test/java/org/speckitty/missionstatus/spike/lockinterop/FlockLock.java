package org.speckitty.missionstatus.spike.lockinterop;

import java.io.IOException;
import java.lang.foreign.Arena;
import java.lang.foreign.FunctionDescriptor;
import java.lang.foreign.Linker;
import java.lang.foreign.MemoryLayout;
import java.lang.foreign.MemorySegment;
import java.lang.foreign.SymbolLookup;
import java.lang.foreign.ValueLayout;
import java.lang.invoke.MethodHandle;
import java.lang.invoke.VarHandle;
import java.nio.file.Path;
import java.util.Locale;

/**
 * The candidate alternative for Linux and macOS: {@code flock(2)} itself, called through the Foreign Function and Memory API (final
 * since Java 22), so the Java writer takes the very lock {@code kernel.locks} takes with {@code fcntl.flock}. POSIX only; never loaded
 * on Windows.
 */
final class FlockLock implements JavaLock {

  private static final int O_RDWR = 2;
  private static final int LOCK_EX = 2;
  private static final int LOCK_NB = 4;
  private static final String OS_NAME = System.getProperty("os.name").toLowerCase(Locale.ROOT);
  private static final boolean MAC = OS_NAME.contains("mac");

  static {
    // The open(2) and errno constants below are those of Linux and macOS only; any other system must not silently get Linux's.
    if (!MAC && !OS_NAME.contains("linux")) {
      throw new ExceptionInInitializerError("FlockLock supports Linux and macOS only, not " + OS_NAME);
    }
  }
  private static final int O_CREAT = MAC ? 0x200 : 0x40;
  private static final int EWOULDBLOCK = MAC ? 35 : 11;

  private static final Linker LINKER = Linker.nativeLinker();
  private static final SymbolLookup LIBC = LINKER.defaultLookup();
  private static final MemoryLayout CAPTURE = Linker.Option.captureStateLayout();
  private static final VarHandle ERRNO = CAPTURE.varHandle(MemoryLayout.PathElement.groupElement("errno"));
  private static final MethodHandle OPEN =
      downcall(
          "open",
          FunctionDescriptor.of(ValueLayout.JAVA_INT, ValueLayout.ADDRESS, ValueLayout.JAVA_INT, ValueLayout.JAVA_INT),
          Linker.Option.firstVariadicArg(2),
          Linker.Option.captureCallState("errno"));
  private static final MethodHandle FLOCK =
      downcall(
          "flock",
          FunctionDescriptor.of(ValueLayout.JAVA_INT, ValueLayout.JAVA_INT, ValueLayout.JAVA_INT),
          Linker.Option.captureCallState("errno"));
  private static final MethodHandle CLOSE = downcall("close", FunctionDescriptor.of(ValueLayout.JAVA_INT, ValueLayout.JAVA_INT));

  private static MethodHandle downcall(String symbol, FunctionDescriptor descriptor, Linker.Option... options) {
    return LINKER.downcallHandle(LIBC.find(symbol).orElseThrow(), descriptor, options);
  }

  @Override
  public String name() {
    return "java-ffm-flock";
  }

  @Override
  public Held tryAcquire(Path lockFile) throws IOException {
    try (Arena arena = Arena.ofConfined()) {
      MemorySegment state = arena.allocate(CAPTURE);
      int fd = (int) OPEN.invokeExact(state, arena.allocateFrom(lockFile.toString()), O_RDWR | O_CREAT, 0600);
      if (fd < 0) {
        throw new IOException("open(" + lockFile + ") failed, errno " + (int) ERRNO.get(state, 0L));
      }
      int result = (int) FLOCK.invokeExact(state, fd, LOCK_EX | LOCK_NB);
      if (result == 0) {
        return () -> close(fd);
      }
      int errno = (int) ERRNO.get(state, 0L);
      close(fd);
      if (errno == EWOULDBLOCK) {
        return null;
      }
      throw new IOException("flock(" + lockFile + ") failed, errno " + errno);
    } catch (IOException | RuntimeException | Error e) {
      throw e;
    } catch (Throwable e) {
      throw new IOException(e);
    }
  }

  /** Closing the descriptor releases the {@code flock}, as it does for the Python holder. */
  private static void close(int fd) throws IOException {
    try {
      int ignored = (int) CLOSE.invokeExact(fd);
    } catch (Throwable e) {
      throw new IOException(e);
    }
  }
}
