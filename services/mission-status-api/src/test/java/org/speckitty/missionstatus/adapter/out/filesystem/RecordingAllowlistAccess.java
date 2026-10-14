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
import org.speckitty.missionstatus.application.query.port.out.dto.ReadScope;

/**
 * The test recorder behind the {@link AllowlistAccess} seam. It notes {@code (route, scope, path class, open mode)} BEFORE the operating
 * system is asked, so a failure that the caller swallows is still on the record, and it can inject a fault for a matching access (an
 * {@code AccessDeniedException}, an {@code IOException}) without touching real permissions. Recorded paths are relative to the project
 * root. The class of an access is the class of its (scope, path) pair (FR-011); an access made on the recorder itself, not on a
 * {@link #scoped scoped view}, is made under {@link ReadScope#AUTHORED}. The route comes from a supplier that defaults to {@code "-"}:
 * a harness installs its own request-scoped marker with {@link #routeSupplier}. Lives in {@code src/test}: it never ships.
 */
public final class RecordingAllowlistAccess implements AllowlistAccess {

  /** One note of the record: the route, the read scope, the class (null when the path is on no class), the root-relative path, the mode. */
  public record ScopedAccess(String route, ReadScope scope, Allowlist.PathClass pathClass, String path, OpenMode mode) {}

  private final Path root;
  private final AllowlistAccess delegate;
  private final List<Access> accesses = Collections.synchronizedList(new ArrayList<>());
  private final List<ScopedAccess> scopedAccesses = Collections.synchronizedList(new ArrayList<>());
  private volatile Predicate<Access> faultWhen = access -> false;
  private volatile Supplier<IOException> fault = () -> new IOException("injected");
  private volatile Supplier<String> route = () -> "-";

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

  /** Installs the request-scoped route marker; every later note carries what the supplier answers at that moment. */
  public void routeSupplier(Supplier<String> supplier) {
    this.route = supplier;
  }

  /** Feeds one access that the seam did not see (a write open the production code never makes, for a positive control). */
  public void record(Path path, OpenMode mode) {
    note(ReadScope.AUTHORED, path, mode);
  }

  public List<Access> accesses() {
    synchronized (accesses) {
      return List.copyOf(accesses);
    }
  }

  /** The record with the route and the scope of each access. */
  public List<ScopedAccess> scopedAccesses() {
    synchronized (scopedAccesses) {
      return List.copyOf(scopedAccesses);
    }
  }

  public List<Violation> violations() {
    return Allowlist.violations(accesses());
  }

  public void clear() {
    accesses.clear();
    scopedAccesses.clear();
  }

  private Access note(ReadScope scope, Path path, OpenMode mode) {
    Allowlist.PathClass pathClass = Allowlist.classify(scope, root, path, mode).orElse(null);
    String relative = Allowlist.describe(root, path);
    Access access = new Access(pathClass, relative, mode);
    accesses.add(access);
    scopedAccesses.add(new ScopedAccess(route.get(), scope, pathClass, relative, mode));
    return access;
  }

  private void before(ReadScope scope, Path path, OpenMode mode) throws IOException {
    Access access = note(scope, path, mode);
    if (faultWhen.test(access)) {
      throw fault.get();
    }
  }

  @Override
  public SeekableByteChannel openRead(Path path) throws IOException {
    return openRead(ReadScope.AUTHORED, path);
  }

  @Override
  public BasicFileAttributes stat(Path path, boolean followLinks) throws IOException {
    return stat(ReadScope.AUTHORED, path, followLinks);
  }

  @Override
  public Path realPath(Path path) throws IOException {
    return realPath(ReadScope.AUTHORED, path);
  }

  @Override
  public List<String> listNames(Path dir) throws IOException {
    before(ReadScope.AUTHORED, dir, OpenMode.LIST);
    return delegate.listNames(dir);
  }

  @Override
  public NameWindow listNames(Path dir, int limit) throws IOException {
    return listNames(ReadScope.AUTHORED, dir, limit);
  }

  @Override
  public AllowlistAccess scoped(ReadScope scope) {
    return new Scoped(scope);
  }

  private SeekableByteChannel openRead(ReadScope scope, Path path) throws IOException {
    before(scope, path, OpenMode.READ);
    return delegate.openRead(path);
  }

  private BasicFileAttributes stat(ReadScope scope, Path path, boolean followLinks) throws IOException {
    before(scope, path, OpenMode.STAT);
    return delegate.stat(path, followLinks);
  }

  private Path realPath(ReadScope scope, Path path) throws IOException {
    before(scope, path, OpenMode.REALPATH);
    return delegate.realPath(path);
  }

  private NameWindow listNames(ReadScope scope, Path dir, int limit) throws IOException {
    before(scope, dir, OpenMode.LIST);
    return delegate.listNames(dir, limit);
  }

  /** A view that makes every access under one read scope. */
  private final class Scoped implements AllowlistAccess {
    private final ReadScope scope;

    Scoped(ReadScope scope) {
      this.scope = scope;
    }

    @Override
    public SeekableByteChannel openRead(Path path) throws IOException {
      return RecordingAllowlistAccess.this.openRead(scope, path);
    }

    @Override
    public BasicFileAttributes stat(Path path, boolean followLinks) throws IOException {
      return RecordingAllowlistAccess.this.stat(scope, path, followLinks);
    }

    @Override
    public Path realPath(Path path) throws IOException {
      return RecordingAllowlistAccess.this.realPath(scope, path);
    }

    @Override
    public List<String> listNames(Path dir) throws IOException {
      before(scope, dir, OpenMode.LIST);
      return delegate.listNames(dir);
    }

    @Override
    public NameWindow listNames(Path dir, int limit) throws IOException {
      return RecordingAllowlistAccess.this.listNames(scope, dir, limit);
    }

    @Override
    public AllowlistAccess scoped(ReadScope other) {
      return RecordingAllowlistAccess.this.scoped(other);
    }
  }
}
