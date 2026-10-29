package org.speckitty.missionstatus.spike.lockinterop;

import java.io.IOException;
import java.nio.channels.FileChannel;
import java.nio.channels.FileLock;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;

/**
 * The JDK's own file lock, {@link FileChannel#tryLock()} over the whole file: {@code fcntl(F_SETLK)} record locks on Linux and macOS,
 * {@code LockFileEx} on Windows. This is the lock ADR 2026-10-22-1 D-4 assumed would interoperate with {@code flock(2)}.
 */
final class FileChannelLock implements JavaLock {

  @Override
  public String name() {
    return "java-filechannel";
  }

  @Override
  public Held tryAcquire(Path lockFile) throws IOException {
    FileChannel channel = FileChannel.open(lockFile, StandardOpenOption.CREATE, StandardOpenOption.READ, StandardOpenOption.WRITE);
    FileLock lock;
    try {
      lock = channel.tryLock();
    } catch (IOException | RuntimeException e) {
      channel.close();
      throw e;
    }
    if (lock == null) {
      channel.close();
      return null;
    }
    return () -> {
      try {
        lock.release();
      } finally {
        channel.close();
      }
    };
  }
}
