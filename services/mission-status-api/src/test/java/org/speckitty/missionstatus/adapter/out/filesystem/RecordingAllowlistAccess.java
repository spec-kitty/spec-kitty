package org.speckitty.missionstatus.adapter.out.filesystem;

import java.io.IOException;
import java.nio.channels.SeekableByteChannel;
import java.nio.file.Path;
import java.nio.file.attribute.BasicFileAttributes;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.function.Predicate;
import java.util.function.Supplier;
import org.speckitty.missionstatus.adapter.out.filesystem.Allowlist.Access;
import org.speckitty.missionstatus.adapter.out.filesystem.Allowlist.OpenMode;
import org.speckitty.missionstatus.adapter.out.filesystem.Allowlist.Violation;

/**
 * The test recorder behind the {@link AllowlistAccess} seam. It notes {@code (path class, open mode)} BEFORE the operating system is
 * asked, so a failure that the caller swallows is still on the record, and it can inject a fault for a matching access (an
 * {@code AccessDeniedException}, an {@code IOException}) without touching real permissions. Recorded paths are relative to the project
 * root. Lives in {@code src/test}: it never ships.
 */
public final class RecordingAllowlistAccess implements AllowlistAccess {

  private final Path root;
  private final AllowlistAccess delegate;
  private final List<Access> accesses = Collections.synchronizedList(new ArrayList<>());
  private volatile Predicate<Access> faultWhen = access -> false;
  private volatile Supplier<IOException> fault = () -> new IOException("injected");

  public RecordingAllowlistAccess(Path root) {
    this(root, AllowlistAccess.passThrough());
  }

  public RecordingAllowlistAccess(Path root, AllowlistAccess delegate) {
    this.root = root;
    this.delegate = delegate;
  }

  /** Makes every access that matches fail with the supplied exception, after it has been recorded. */
  public void failWhen(Predicate<Access> match, Supplier<IOException> exception) {
    this.faultWhen = match;
    this.fault = exception;
  }

  /** Feeds one access that the seam did not see (a write open the production code never makes, for a positive control). */
  public void record(Path path, OpenMode mode) {
    accesses.add(new Access(Allowlist.classify(root, path).orElse(null), Allowlist.describe(root, path), mode));
  }

  public List<Access> accesses() {
    synchronized (accesses) {
      return List.copyOf(accesses);
    }
  }

  public List<Violation> violations() {
    return Allowlist.violations(accesses());
  }

  public void clear() {
    accesses.clear();
  }

  private void before(Path path, OpenMode mode) throws IOException {
    Access access = new Access(Allowlist.classify(root, path).orElse(null), Allowlist.describe(root, path), mode);
    accesses.add(access);
    if (faultWhen.test(access)) {
      throw fault.get();
    }
  }

  @Override
  public SeekableByteChannel openRead(Path path) throws IOException {
    before(path, OpenMode.READ);
    return delegate.openRead(path);
  }

  @Override
  public BasicFileAttributes stat(Path path, boolean followLinks) throws IOException {
    before(path, OpenMode.STAT);
    return delegate.stat(path, followLinks);
  }

  @Override
  public Path realPath(Path path) throws IOException {
    before(path, OpenMode.REALPATH);
    return delegate.realPath(path);
  }

  @Override
  public List<String> listNames(Path dir) throws IOException {
    before(dir, OpenMode.LIST);
    return delegate.listNames(dir);
  }
}
