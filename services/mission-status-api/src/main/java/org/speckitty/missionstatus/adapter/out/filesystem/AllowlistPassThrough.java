package org.speckitty.missionstatus.adapter.out.filesystem;

import java.io.IOException;
import java.nio.channels.SeekableByteChannel;
import java.nio.file.DirectoryStream;
import java.nio.file.Files;
import java.nio.file.LinkOption;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.nio.file.attribute.BasicFileAttributes;
import java.util.ArrayList;
import java.util.List;

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
    List<String> names = new ArrayList<>();
    try (DirectoryStream<Path> entries = Files.newDirectoryStream(dir)) {
      for (Path entry : entries) {
        names.add(entry.getFileName().toString());
      }
    }
    return names;
  }
}
