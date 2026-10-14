package org.speckitty.missionstatus.testsupport;

import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.channels.NonWritableChannelException;
import java.nio.channels.SeekableByteChannel;
import java.nio.file.Path;
import java.nio.file.attribute.BasicFileAttributes;
import java.nio.file.attribute.FileTime;
import java.util.List;
import java.util.Objects;
import java.util.concurrent.atomic.AtomicLong;
import java.util.function.Predicate;
import org.speckitty.missionstatus.adapter.out.filesystem.AllowlistAccess;
import org.speckitty.missionstatus.application.query.port.out.dto.ReadScope;

/**
 * A decorating {@link AllowlistAccess} that makes a file grow between the size check and the read (AC-7.1, AC-5.4 race leg). For a path
 * the predicate selects, {@code stat} and the open handle both report a small declared size (for example 100 bytes) while a read serves
 * a much larger body (for example 300000 bytes). A reader that trusted the declared size would read the lot; the capped reader must stop
 * at {@code cap + 1} bytes and answer over-cap. {@link #bytesRead()} says how many bytes were really pulled, so a test can pin the bound.
 *
 * <p>Two variants: {@link Variant#DECLARED_SIZE_LIES} (the handle reports the declared size on every call) and
 * {@link Variant#GROWS_AFTER_SIZE_CHECK} (the handle reports the declared size on its first call only, and the real size afterwards: the
 * file grew after the handle check). Any other path is passed through untouched.
 */
public final class CapRaceInjector implements AllowlistAccess {

  /** How the handle lies. */
  public enum Variant {
    DECLARED_SIZE_LIES,
    GROWS_AFTER_SIZE_CHECK
  }

  /** What the injector pulled out of the lying file; shared by every scoped view of one injector. */
  private static final class Counter {
    final AtomicLong bytes = new AtomicLong();
  }

  private final AllowlistAccess delegate;
  private final Predicate<Path> selects;
  private final long declaredSize;
  private final byte[] actual;
  private final Variant variant;
  private final Counter counter;

  public CapRaceInjector(AllowlistAccess delegate, Predicate<Path> selects, long declaredSize, byte[] actual) {
    this(delegate, selects, declaredSize, actual, Variant.DECLARED_SIZE_LIES);
  }

  public CapRaceInjector(AllowlistAccess delegate, Predicate<Path> selects, long declaredSize, byte[] actual, Variant variant) {
    this(delegate, selects, declaredSize, actual, variant, new Counter());
  }

  private CapRaceInjector(AllowlistAccess delegate, Predicate<Path> selects, long declaredSize, byte[] actual, Variant variant, Counter counter) {
    this.delegate = Objects.requireNonNull(delegate, "delegate");
    this.selects = Objects.requireNonNull(selects, "selects");
    this.declaredSize = declaredSize;
    this.actual = Objects.requireNonNull(actual, "actual").clone();
    this.variant = Objects.requireNonNull(variant, "variant");
    this.counter = counter;
  }

  /** The bytes that were really served to readers of the lying file. */
  public long bytesRead() {
    return counter.bytes.get();
  }

  @Override
  public SeekableByteChannel openRead(Path path) throws IOException {
    if (!selects.test(path)) {
      return delegate.openRead(path);
    }
    // the real open is made (and closed) so that the recorder notes the read and an absent file is still absent
    delegate.openRead(path).close();
    return new LyingChannel(actual, declaredSize, variant, counter.bytes);
  }

  @Override
  public BasicFileAttributes stat(Path path, boolean followLinks) throws IOException {
    BasicFileAttributes real = delegate.stat(path, followLinks);
    return selects.test(path) && real.isRegularFile() ? new DeclaredSize(real, declaredSize) : real;
  }

  @Override
  public Path realPath(Path path) throws IOException {
    return delegate.realPath(path);
  }

  @Override
  public List<String> listNames(Path dir) throws IOException {
    return delegate.listNames(dir);
  }

  @Override
  public NameWindow listNames(Path dir, int limit) throws IOException {
    return delegate.listNames(dir, limit);
  }

  @Override
  public AllowlistAccess scoped(ReadScope scope) {
    return new CapRaceInjector(delegate.scoped(scope), selects, declaredSize, actual, variant, counter);
  }

  /** The attributes of the real file, with a size that is not true. */
  private record DeclaredSize(BasicFileAttributes real, long size) implements BasicFileAttributes {
    @Override
    public FileTime lastModifiedTime() {
      return real.lastModifiedTime();
    }

    @Override
    public FileTime lastAccessTime() {
      return real.lastAccessTime();
    }

    @Override
    public FileTime creationTime() {
      return real.creationTime();
    }

    @Override
    public boolean isRegularFile() {
      return real.isRegularFile();
    }

    @Override
    public boolean isDirectory() {
      return real.isDirectory();
    }

    @Override
    public boolean isSymbolicLink() {
      return real.isSymbolicLink();
    }

    @Override
    public boolean isOther() {
      return real.isOther();
    }

    @Override
    public Object fileKey() {
      return real.fileKey();
    }
  }

  /** A read-only channel over the large body whose {@link #size()} says something else. */
  private static final class LyingChannel implements SeekableByteChannel {
    private final byte[] body;
    private final long declared;
    private final Variant variant;
    private final AtomicLong served;
    private int position;
    private boolean sizeAsked;
    private boolean open = true;

    LyingChannel(byte[] body, long declared, Variant variant, AtomicLong served) {
      this.body = body;
      this.declared = declared;
      this.variant = variant;
      this.served = served;
    }

    @Override
    public int read(ByteBuffer destination) {
      if (position >= body.length) {
        return -1;
      }
      int count = Math.min(destination.remaining(), body.length - position);
      destination.put(body, position, count);
      position += count;
      served.addAndGet(count);
      return count;
    }

    @Override
    public long size() {
      boolean first = !sizeAsked;
      sizeAsked = true;
      return variant == Variant.DECLARED_SIZE_LIES || first ? declared : body.length;
    }

    @Override
    public int write(ByteBuffer source) {
      throw new NonWritableChannelException();
    }

    @Override
    public long position() {
      return position;
    }

    @Override
    public SeekableByteChannel position(long newPosition) {
      position = (int) Math.min(newPosition, body.length);
      return this;
    }

    @Override
    public SeekableByteChannel truncate(long size) {
      throw new NonWritableChannelException();
    }

    @Override
    public boolean isOpen() {
      return open;
    }

    @Override
    public void close() {
      open = false;
    }
  }
}
