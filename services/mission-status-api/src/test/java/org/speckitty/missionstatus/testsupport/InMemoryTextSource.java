package org.speckitty.missionstatus.testsupport;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import org.speckitty.missionstatus.adapter.out.filesystem.codec.StrictUtf8;
import org.speckitty.missionstatus.application.query.port.out.TextSource;
import org.speckitty.missionstatus.application.query.port.out.dto.BytesRead;
import org.speckitty.missionstatus.application.query.port.out.dto.DirListing;
import org.speckitty.missionstatus.application.query.port.out.dto.EntryStat;
import org.speckitty.missionstatus.application.query.port.out.dto.EntryStat.EntryKind;
import org.speckitty.missionstatus.application.query.port.out.dto.FileRef;
import org.speckitty.missionstatus.application.query.port.out.dto.ReadScope;
import org.speckitty.missionstatus.application.query.port.out.dto.RelativePath;
import org.speckitty.missionstatus.application.query.port.out.dto.TextRead;
import org.speckitty.missionstatus.application.query.port.out.exceptions.TextFault;

/**
 * The text-read port over an in-memory map keyed by {@code (FileRef, ReadScope)}: the double the route tests use when they must not
 * touch a file system, and the second source of the AC-13.5 subset. It enforces the same rules as {@code FilesystemTextSource}, so the
 * subset gives identical results from both: a file over the cap is {@code OverCap} (by its length), a file whose bytes are not strict
 * UTF-8 is {@code NotText} (the same {@link StrictUtf8}, a leading byte order mark kept), a missing entry or one below a file is
 * {@code Absent}, a directory read as a file is {@code NotRegular}, a link in any component is a {@link TextFault} of kind
 * {@code PATH_REFUSED} (never followed), a listing is cut at the limit with {@code limitReached}, and a registered fault is thrown.
 * A directory with no explicit entry exists when something is registered below it, and then lists the next segment of each entry.
 *
 * <p>Builders register an entry under every read scope, or under one scope when it is given. Not thread-safe while it is being built.
 */
public final class InMemoryTextSource implements TextSource {

  private sealed interface Node permits FileNode, DirNode, LinkNode, FaultNode {}

  private record FileNode(byte[] content, long modifiedEpochSecond) implements Node {}

  private record DirNode(List<String> names) implements Node {}

  private record LinkNode() implements Node {}

  private record FaultNode(TextFault.Kind kind) implements Node {}

  private record Key(FileRef ref, ReadScope scope) {}

  private final Map<Key, Node> nodes = new HashMap<>();
  private final List<Key> reads = new ArrayList<>();
  private boolean trustworthy = true;

  // ---- building --------------------------------------------------------------------------------------------------------------

  /** A regular file with these bytes, under every scope. */
  public InMemoryTextSource file(FileRef ref, byte[] content) {
    return put(ref, null, new FileNode(content.clone(), 0));
  }

  /** A regular file with these bytes, under one scope. */
  public InMemoryTextSource file(FileRef ref, ReadScope scope, byte[] content) {
    return put(ref, scope, new FileNode(content.clone(), 0));
  }

  /** A directory with exactly these names (in this order), under every scope. */
  public InMemoryTextSource dir(FileRef ref, String... names) {
    return put(ref, null, new DirNode(List.of(names)));
  }

  /** A symbolic link, under every scope; it is never followed. */
  public InMemoryTextSource link(FileRef ref) {
    return put(ref, null, new LinkNode());
  }

  /** An operating-system fault for any access to the entry, under every scope. */
  public InMemoryTextSource fault(FileRef ref, TextFault.Kind kind) {
    return put(ref, null, new FaultNode(kind));
  }

  /** Whether listings say the host's file-name decoding can be believed (the default). */
  public InMemoryTextSource trustworthy(boolean trustworthy) {
    this.trustworthy = trustworthy;
    return this;
  }

  private InMemoryTextSource put(FileRef ref, ReadScope scope, Node node) {
    for (ReadScope each : scope == null ? ReadScope.values() : new ReadScope[] {scope}) {
      nodes.put(new Key(ref, each), node);
    }
    return this;
  }

  /** Every {@code (reference, scope)} a caller asked for, in order (a test can assert which scope a route reads under). */
  public List<FileRef> readRefs() {
    return reads.stream().map(Key::ref).toList();
  }

  public List<ReadScope> readScopes() {
    return reads.stream().map(Key::scope).toList();
  }

  // ---- the port --------------------------------------------------------------------------------------------------------------

  @Override
  public DirListing list(FileRef dir, int nameLimit, ReadScope scope) {
    reads.add(new Key(dir, scope));
    if (!ancestorsAreDirectories(dir, scope)) {
      return new DirListing.Absent();
    }
    Node node = nodes.get(new Key(dir, scope));
    switch (node) {
      case null -> {
        List<String> children = children(dir, scope);
        return children.isEmpty() ? new DirListing.Absent() : window(children, nameLimit);
      }
      case FileNode file -> {
        return new DirListing.NotADirectory();
      }
      case LinkNode link -> throw new TextFault(TextFault.Kind.PATH_REFUSED);
      case FaultNode fault -> throw new TextFault(fault.kind());
      case DirNode directory -> {
        return window(directory.names(), nameLimit);
      }
    }
  }

  @Override
  public EntryStat stat(FileRef path, ReadScope scope) {
    reads.add(new Key(path, scope));
    if (!ancestorsAreDirectories(path, scope)) {
      return new EntryStat.Absent();
    }
    Node node = nodes.get(new Key(path, scope));
    return switch (node) {
      case null -> children(path, scope).isEmpty() ? new EntryStat.Absent() : new EntryStat.Present(EntryKind.DIRECTORY, 0, 0);
      case FileNode file -> new EntryStat.Present(EntryKind.FILE, file.content().length, file.modifiedEpochSecond());
      case DirNode directory -> new EntryStat.Present(EntryKind.DIRECTORY, 0, 0);
      case LinkNode link -> new EntryStat.Present(EntryKind.SYMLINK, 0, 0);
      case FaultNode fault -> throw new TextFault(fault.kind());
    };
  }

  @Override
  public BytesRead readBytes(FileRef file, int cap, ReadScope scope) {
    reads.add(new Key(file, scope));
    return switch (capped(file, cap, scope)) {
      case Capped.Bytes bytes -> new BytesRead.Bytes(bytes.content());
      case Capped.Absent absent -> new BytesRead.Absent();
      case Capped.NotRegular notRegular -> new BytesRead.NotRegular();
      case Capped.OverCap overCap -> new BytesRead.OverCap();
    };
  }

  @Override
  public TextRead readText(FileRef file, int cap, ReadScope scope) {
    reads.add(new Key(file, scope));
    return switch (capped(file, cap, scope)) {
      case Capped.Bytes bytes ->
          switch (StrictUtf8.decode(bytes.content())) {
            case StrictUtf8.Decoded.Text text -> new TextRead.Text(text.text(), bytes.content().length);
            case StrictUtf8.Decoded.Rejected rejected -> new TextRead.NotText();
          };
      case Capped.Absent absent -> new TextRead.Absent();
      case Capped.NotRegular notRegular -> new TextRead.NotRegular();
      case Capped.OverCap overCap -> new TextRead.OverCap();
    };
  }

  // ---- the shared steps ------------------------------------------------------------------------------------------------------

  private sealed interface Capped {
    record Bytes(byte[] content) implements Capped {}

    record Absent() implements Capped {}

    record NotRegular() implements Capped {}

    record OverCap() implements Capped {}
  }

  private Capped capped(FileRef file, int cap, ReadScope scope) {
    if (cap < 0) {
      throw new IllegalArgumentException("cap");
    }
    if (!ancestorsAreDirectories(file, scope)) {
      return new Capped.Absent();
    }
    Node node = nodes.get(new Key(file, scope));
    return switch (node) {
      case null -> children(file, scope).isEmpty() ? new Capped.Absent() : new Capped.NotRegular();
      case FileNode regular -> regular.content().length > cap ? new Capped.OverCap() : new Capped.Bytes(regular.content().clone());
      case DirNode directory -> new Capped.NotRegular();
      case LinkNode link -> throw new TextFault(TextFault.Kind.PATH_REFUSED);
      case FaultNode fault -> throw new TextFault(fault.kind());
    };
  }

  private DirListing window(List<String> names, int limit) {
    boolean more = names.size() > limit;
    return new DirListing.Names(more ? names.subList(0, limit) : names, more, trustworthy);
  }

  /** Whether every component before the last is a directory: a link is refused, a file or nothing at all means there is nothing at the path. */
  private boolean ancestorsAreDirectories(FileRef ref, ReadScope scope) {
    List<String> segments = ref.path().segments();
    for (int i = 1; i < segments.size(); i++) {
      FileRef ancestor = withPath(ref, new RelativePath(segments.subList(0, i)));
      Node node = nodes.get(new Key(ancestor, scope));
      switch (node) {
        case LinkNode link -> throw new TextFault(TextFault.Kind.PATH_REFUSED);
        case FaultNode fault -> throw new TextFault(fault.kind());
        case FileNode file -> {
          return false;
        }
        case DirNode directory -> {}
        case null -> {
          if (children(ancestor, scope).isEmpty()) {
            return false;
          }
        }
      }
    }
    return true;
  }

  /** The distinct next segments of the entries registered below {@code dir} under {@code scope}, in registration-independent (sorted) order. */
  private List<String> children(FileRef dir, ReadScope scope) {
    Set<String> names = new LinkedHashSet<>();
    List<String> prefix = dir.path().segments();
    for (Key key : nodes.keySet()) {
      if (key.scope() != scope || !sameBase(key.ref(), dir)) {
        continue;
      }
      List<String> segments = key.ref().path().segments();
      if (segments.size() > prefix.size() && segments.subList(0, prefix.size()).equals(prefix)) {
        names.add(segments.get(prefix.size()));
      }
    }
    return names.stream().sorted().toList();
  }

  private static boolean sameBase(FileRef a, FileRef b) {
    return switch (a) {
      case FileRef.MissionFile left -> b instanceof FileRef.MissionFile right && left.mission().equals(right.mission());
      case FileRef.ProjectFile left -> b instanceof FileRef.ProjectFile;
    };
  }

  private static FileRef withPath(FileRef ref, RelativePath path) {
    return switch (ref) {
      case FileRef.MissionFile mission -> new FileRef.MissionFile(mission.mission(), path);
      case FileRef.ProjectFile project -> new FileRef.ProjectFile(path);
    };
  }
}
