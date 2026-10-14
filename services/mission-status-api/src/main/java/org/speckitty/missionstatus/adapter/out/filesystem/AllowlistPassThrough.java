package org.speckitty.missionstatus.adapter.out.filesystem;

import java.io.IOException;
import java.nio.channels.SeekableByteChannel;
import java.nio.file.DirectoryIteratorException;
import java.nio.file.DirectoryStream;
import java.nio.file.Files;
import java.nio.file.LinkOption;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.nio.file.attribute.BasicFileAttributes;
import java.util.ArrayList;
import java.util.List;
import org.speckitty.missionstatus.application.query.port.out.dto.ReadScope;

/** The production {@link AllowlistAccess}: the operating system, with no link followed on a read. */
final class AllowlistPassThrough implements AllowlistAccess {

  static final AllowlistPassThrough INSTANCE = new AllowlistPassThrough();

  private AllowlistPassThrough() {}

  @Override
  public SeekableByteChannel openRead(Path path) throws IOException {
    return Files.newByteChannel(path, StandardOpenOption.READ, LinkOption.NOFOLLOW_LINKS);
  }

  @Override
  public BasicFileAttributes stat(Path path, boolean followLinks) throws IOException {
    return followLinks
        ? Files.readAttributes(path, BasicFileAttributes.class)
        : Files.readAttributes(path, BasicFileAttributes.class, LinkOption.NOFOLLOW_LINKS);
  }

  @Override
  public Path realPath(Path path) throws IOException {
    return path.toRealPath();
  }

  @Override
  public List<String> listNames(Path dir) throws IOException {
    try (DirectoryStream<Path> entries = Files.newDirectoryStream(dir)) {
      return names(entries);
    }
  }

  /** Every name of one stream. */
  static List<String> names(DirectoryStream<Path> entries) throws IOException {
    List<String> names = new ArrayList<>();
    try {
      for (Path entry : entries) {
        names.add(entry.getFileName().toString());
      }
    } catch (DirectoryIteratorException e) {
      throw e.getCause();
    }
    return names;
  }

  @Override
  public AllowlistAccess scoped(ReadScope scope) {
    return this;
  }

  @Override
  public NameWindow listNames(Path dir, int limit) throws IOException {
    try (DirectoryStream<Path> entries = Files.newDirectoryStream(dir)) {
      return window(entries, limit);
    }
  }

  /** At most {@code limit} names, pulled lazily from one stream: never more than {@code limit + 1} of them. */
  static NameWindow window(DirectoryStream<Path> entries, int limit) throws IOException {
    if (limit < 0) {
      throw new IllegalArgumentException("nameLimit must not be negative: " + limit);
    }
    List<String> names = new ArrayList<>();
    boolean more = false;
    try {
      for (Path entry : entries) {
        if (names.size() == limit) {
          more = true;
          break;
        }
        names.add(entry.getFileName().toString());
      }
    } catch (DirectoryIteratorException e) {
      throw e.getCause();
    }
    return new NameWindow(names, more);
  }
}
