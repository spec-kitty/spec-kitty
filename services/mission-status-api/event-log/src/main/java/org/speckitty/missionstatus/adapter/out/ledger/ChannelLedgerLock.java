package org.speckitty.missionstatus.adapter.out.ledger;

import java.io.IOException;
import java.nio.channels.FileChannel;
import java.nio.channels.FileLock;
import java.nio.channels.OverlappingFileLockException;
import java.nio.file.FileSystemException;
import java.nio.file.Files;
import java.nio.file.LinkOption;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.nio.file.attribute.FileAttribute;
import java.nio.file.attribute.PosixFilePermissions;
import java.util.Set;
import java.util.concurrent.atomic.AtomicBoolean;

/**
 * The JDK's lock over the whole lock file ({@code LockFileEx} on Windows). On Windows it excludes {@code kernel.locks}' {@code msvcrt.locking}
 * byte-range lock at byte 0. It is not used on Linux, where this lock and {@code flock(2)} are independent. A second holder in the same JVM
 * counts as contention, as a second holder in another process does.
 */
final class ChannelLedgerLock implements LedgerLock {

  private static final FileAttribute<?>[] OWNER_ONLY = ownerOnly();

  private static FileAttribute<?>[] ownerOnly() {
    boolean posix = java.nio.file.FileSystems.getDefault().supportedFileAttributeViews().contains("posix");
    return posix ? new FileAttribute<?>[] {PosixFilePermissions.asFileAttribute(PosixFilePermissions.fromString("rw-------"))} : new FileAttribute<?>[0];
  }

  @Override
  public Held tryAcquire(Path lockFile) throws IOException {
    Files.createDirectories(lockFile.toAbsolutePath().getParent());
    FileChannel channel = open(lockFile);
    FileLock lock;
    try {
      lock = channel.tryLock();
    } catch (OverlappingFileLockException e) {
      lock = null;
    } catch (IOException | RuntimeException e) {
      channel.close();
      throw e;
    }
    if (lock == null) {
      channel.close();
      return null;
    }
    FileLock held = lock;
    AtomicBoolean open = new AtomicBoolean(true);
    return () -> {
      if (open.getAndSet(false)) {
        try {
          held.release();
        } finally {
          channel.close();
        }
      }
    };
  }

  private static FileChannel open(Path lockFile) throws IOException {
    Set<StandardOpenOption> options = Set.of(StandardOpenOption.CREATE, StandardOpenOption.READ, StandardOpenOption.WRITE);
    try {
      return FileChannel.open(lockFile, withNoFollow(options), OWNER_ONLY);
    } catch (FileSystemException e) {
      if (Files.isSymbolicLink(lockFile)) {
        throw new IOException(lockFile + " is a symbolic link; refusing to lock through it", e);
      }
      throw e;
    }
  }

  private static Set<java.nio.file.OpenOption> withNoFollow(Set<StandardOpenOption> options) {
    Set<java.nio.file.OpenOption> all = new java.util.HashSet<>(options);
    all.add(LinkOption.NOFOLLOW_LINKS);
    return all;
  }
}
