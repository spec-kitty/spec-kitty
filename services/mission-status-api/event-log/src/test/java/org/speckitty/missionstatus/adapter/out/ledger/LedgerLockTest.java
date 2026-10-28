package org.speckitty.missionstatus.adapter.out.ledger;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.junit.jupiter.api.Assumptions.assumeTrue;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.attribute.PosixFilePermission;
import java.time.Duration;
import java.util.Locale;
import java.util.stream.Stream;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.MethodSource;

/**
 * The ledger locks: exclusion, release, the bounded wait, the lock file they create, and a refused symbolic link. That these locks also
 * exclude the CLI's {@code kernel.locks} holder is the #6193 lock-interop spike's evidence (docs/development/reference/lock-interop-spike.md).
 */
class LedgerLockTest {

  private static final boolean WINDOWS = System.getProperty("os.name").toLowerCase(Locale.ROOT).contains("win");

  @TempDir Path dir;

  /** This OS's lock, and on Linux and macOS also the FileChannel lock (the Windows one), so both run where they can. */
  static Stream<LedgerLock> locks() {
    return WINDOWS ? Stream.of(new ChannelLedgerLock()) : Stream.of(new FlockLedgerLock(), new ChannelLedgerLock());
  }

  @Test
  void thisOsGetsTheSpikeProvenLock() {
    assertThat(LedgerLocks.forThisOs()).isInstanceOf(WINDOWS ? ChannelLedgerLock.class : FlockLedgerLock.class);
  }

  @Test
  void eachSupportedPlatformGetsItsOwnOpenAndErrnoConstants() {
    assertThat(FlockLedgerLock.constantsFor("Linux", "amd64")).isEqualTo(FlockLedgerLock.LINUX_X64);
    assertThat(FlockLedgerLock.constantsFor("Linux", "aarch64")).isEqualTo(FlockLedgerLock.LINUX_AARCH64);
    assertThat(FlockLedgerLock.constantsFor("Mac OS X", "aarch64")).isEqualTo(FlockLedgerLock.MACOS);
    assertThat(FlockLedgerLock.LINUX_AARCH64.oNofollow()).as("AArch64 Linux has its own O_NOFOLLOW").isNotEqualTo(FlockLedgerLock.LINUX_X64.oNofollow());
    assertThatThrownBy(() -> FlockLedgerLock.constantsFor("Linux", "riscv64")).isInstanceOf(UnsupportedOperationException.class);
    assertThatThrownBy(() -> FlockLedgerLock.constantsFor("FreeBSD", "amd64")).isInstanceOf(UnsupportedOperationException.class);
    assertThatThrownBy(() -> FlockLedgerLock.constantsFor("Windows 11", "amd64")).isInstanceOf(UnsupportedOperationException.class);
  }

  @ParameterizedTest
  @MethodSource("locks")
  void aHeldLockExcludesASecondHolderUntilReleased(LedgerLock lock) throws IOException {
    Path lockFile = dir.resolve("x.lock");
    LedgerLock.Held first = lock.tryAcquire(lockFile);
    assertThat(first).isNotNull();
    assertThat(lock.tryAcquire(lockFile)).as("a second holder is excluded").isNull();
    first.close();
    first.close(); // idempotent: a second close must not release anything else
    try (LedgerLock.Held again = lock.tryAcquire(lockFile)) {
      assertThat(again).as("released").isNotNull();
    }
  }

  @ParameterizedTest
  @MethodSource("locks")
  void theBoundedWaitTimesOut(LedgerLock lock) throws IOException {
    Path lockFile = dir.resolve("x.lock");
    try (LedgerLock.Held held = lock.tryAcquire(lockFile)) {
      assertThat(held).isNotNull();
      long start = System.nanoTime();
      assertThatThrownBy(() -> lock.acquire(lockFile, Duration.ofMillis(300)))
          .isInstanceOf(LedgerLockTimeoutException.class)
          .hasMessageContaining(lockFile.toString());
      assertThat(Duration.ofNanos(System.nanoTime() - start)).isGreaterThanOrEqualTo(Duration.ofMillis(300));
    }
  }

  @ParameterizedTest
  @MethodSource("locks")
  void theLockCreatesItsParentAndAnOwnerOnlyLockFile(LedgerLock lock) throws IOException {
    Path lockFile = dir.resolve("a").resolve("b").resolve("x.lock");
    try (LedgerLock.Held held = lock.acquire(lockFile, Duration.ofSeconds(1))) {
      assertThat(held).isNotNull();
    }
    assertThat(lockFile).exists();
    if (!WINDOWS) {
      assertThat(Files.getPosixFilePermissions(lockFile)).containsExactlyInAnyOrder(PosixFilePermission.OWNER_READ, PosixFilePermission.OWNER_WRITE);
    }
  }

  @ParameterizedTest
  @MethodSource("locks")
  void aSymbolicLinkAtTheLockPathIsRefused(LedgerLock lock) throws IOException {
    assumeTrue(!WINDOWS, "creating a symbolic link needs a privilege on Windows");
    Path target = Files.writeString(dir.resolve("payload"), "keep me");
    Path lockFile = Files.createSymbolicLink(dir.resolve("x.lock"), target);
    assertThatThrownBy(() -> lock.tryAcquire(lockFile)).isInstanceOf(IOException.class).hasMessageContaining("symbolic link");
    assertThat(Files.readString(target)).isEqualTo("keep me");
  }
}
