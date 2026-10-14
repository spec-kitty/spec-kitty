package org.speckitty.missionstatus.application.query.artifact;

import java.time.Instant;
import java.time.ZoneOffset;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.List;
import java.util.Objects;
import java.util.PriorityQueue;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.function.Consumer;
import org.speckitty.missionstatus.application.query.port.in.exceptions.DetailRefusal;
import org.speckitty.missionstatus.application.query.port.out.TextSource;
import org.speckitty.missionstatus.application.query.port.out.dto.DirListing;
import org.speckitty.missionstatus.application.query.port.out.dto.EntryStat;
import org.speckitty.missionstatus.application.query.port.out.dto.FileRef;
import org.speckitty.missionstatus.application.query.port.out.dto.MissionRef;
import org.speckitty.missionstatus.application.query.port.out.dto.ReadScope;
import org.speckitty.missionstatus.application.query.port.out.dto.RelativePath;
import org.speckitty.missionstatus.application.query.port.out.exceptions.TextFault;
import org.speckitty.missionstatus.domain.model.CodePoints;
import org.speckitty.missionstatus.domain.model.Diagnostic;
import org.speckitty.missionstatus.domain.model.DiagnosticCode;
import org.speckitty.missionstatus.domain.readmodel.derive.ArtifactKinds;
import org.speckitty.missionstatus.domain.readmodel.detail.ArtifactEntry;

/**
 * The bounded walk and the bounded sorted collection of the artifact listing (FR-004).
 *
 * <p><b>The walk.</b> Every directory is listed once, with {@code WALK_NAMES - counter} as the name limit; every name a listing returns
 * counts one (regular files, directories, links, ineligible names and the two root records alike; the Mission directory itself does
 * not). A walk whose counter reaches 100000 is served; the name that would be the 100001st stops it with 500
 * {@code artifact_listing_unreadable}. A directory is entered when it is a real directory whose own path has fewer than 512 characters;
 * a link, or a directory at 512, counts as a name and its content does not. The two root records are counted and then left alone: they
 * are not statted, because the read fence has no class for them under the artifact scope.
 *
 * <p><b>The collection.</b> The eligible files are collected in a bounded max-heap of the 1001 smallest paths under
 * {@link CodePoints#compare} (the code-point order of a path is its UTF-8 byte order), so no sort of the whole walk exists. The heap
 * never holds more than 1001 paths; the 1001st says {@code truncated}.
 *
 * <p><b>The flag.</b> {@code readable} is decided for the final at most 1000 entries only, by the same {@link ArtifactReader#probe} the
 * content route runs, except that a size above the cap is decided from the stat alone and the file is not opened.
 */
public final class ArtifactWalk {

  private static final DateTimeFormatter SECONDS = DateTimeFormatter.ofPattern("uuuu-MM-dd'T'HH:mm:ss'Z'").withZone(ZoneOffset.UTC);

  /** What the walk found: the first entries in byte order, and whether more existed. */
  public record Result(List<ArtifactEntry> entries, boolean truncated) {
    public Result {
      entries = List.copyOf(entries);
    }
  }

  /** A collected file: its path and the two numbers of its stat. */
  private record Candidate(String path, long sizeBytes, long modifiedEpochSecond) {}

  private final TextSource source;
  private final ArtifactReader reader;
  private final Consumer<Diagnostic> diagnostics;
  private final AtomicInteger collectorHighWater = new AtomicInteger();

  public ArtifactWalk(TextSource source, ArtifactReader reader, Consumer<Diagnostic> diagnostics) {
    this.source = Objects.requireNonNull(source, "source");
    this.reader = Objects.requireNonNull(reader, "reader");
    this.diagnostics = Objects.requireNonNull(diagnostics, "diagnostics");
  }

  /**
   * Walks the primary directory of the Mission.
   *
   * @throws DetailRefusal {@code NOT_FOUND} when the directory has gone, {@code ARTIFACT_LISTING_UNREADABLE} (with its diagnostic) when
   *     a directory cannot be listed, the bound is exceeded or the host cannot decode a non-ASCII name
   */
  public Result walk(MissionRef mission, String mid8) {
    return new Walking(mission, mid8).run();
  }

  /** The most paths the collector ever held at one time, over every walk of this object. A test accessor; nothing in production reads it. */
  int collectorHighWater() {
    return collectorHighWater.get();
  }

  /** One walk: its counter, its collector and the stack of the directories entered. */
  private final class Walking {
    private final MissionRef mission;
    private final String mid8;
    private final PriorityQueue<Candidate> collector = new PriorityQueue<>((left, right) -> CodePoints.compare(right.path(), left.path()));
    private final List<EntryStat> ancestors = new ArrayList<>();
    private int counter;
    private int eligible;

    Walking(MissionRef mission, String mid8) {
      this.mission = mission;
      this.mid8 = mid8;
    }

    Result run() {
      visit("");
      List<Candidate> smallest = new ArrayList<>(collector);
      smallest.sort((left, right) -> CodePoints.compare(left.path(), right.path()));
      List<ArtifactEntry> entries = new ArrayList<>();
      for (Candidate candidate : smallest.subList(0, Math.min(smallest.size(), ArtifactLimits.LISTING_ENTRIES))) {
        entry(candidate).ifPresent(entries::add);
      }
      return new Result(entries, eligible > ArtifactLimits.LISTING_ENTRIES);
    }

    private FileRef ref(String path) {
      return new FileRef.MissionFile(mission, path.isEmpty() ? RelativePath.ROOT : RelativePath.of(path));
    }

    /** Lists one directory and looks at each name it returns. */
    private void visit(String directory) {
      boolean root = directory.isEmpty();
      DirListing listing;
      try {
        listing = source.list(ref(directory), ArtifactLimits.WALK_NAMES - counter, ReadScope.ARTIFACT);
      } catch (TextFault fault) {
        gone(fault, root);
        return;
      }
      switch (listing) {
        case DirListing.Absent absent -> {
          if (root) {
            throw DetailRefusal.notFound();
          }
        }
        case DirListing.NotADirectory notADirectory -> {
          if (root) {
            throw DetailRefusal.notFound();
          }
        }
        case DirListing.Names names -> {
          if (!names.trustworthy() && names.names().stream().anyMatch(ArtifactWalk::hasNonAscii)) {
            throw listingUnreadable();
          }
          counter += names.names().size();
          if (names.limitReached()) {
            throw listingUnreadable();
          }
          for (String name : names.names()) {
            look(directory, name);
          }
        }
      }
    }

    /** A fault of a listing or a stat: a directory that went or became a link is skipped below the root; anything else refuses the listing. */
    private void gone(TextFault fault, boolean root) {
      switch (fault.kind()) {
        case VANISHED -> {
          if (root) {
            throw DetailRefusal.notFound();
          }
        }
        case PATH_REFUSED -> {
          if (root) {
            diagnostics.accept(new Diagnostic(DiagnosticCode.PATH_REFUSED, mid8, null));
            throw DetailRefusal.notFound();
          }
        }
        case DIR_UNREADABLE, FILE_UNREADABLE -> throw listingUnreadable();
      }
    }

    private DetailRefusal listingUnreadable() {
      diagnostics.accept(new Diagnostic(DiagnosticCode.ARTIFACT_LISTING_UNREADABLE, mid8, null));
      return DetailRefusal.artifactListingUnreadable();
    }

    /** One name of a listing. The name is already counted. */
    private void look(String directory, String name) {
      if (!segment(name) || (directory.isEmpty() && Eligibility.isRootRecord(name))) {
        return;
      }
      String path = directory.isEmpty() ? name : directory + "/" + name;
      EntryStat stat;
      try {
        stat = source.stat(ref(path), ReadScope.ARTIFACT);
      } catch (TextFault fault) {
        gone(fault, false);
        return;
      }
      if (!(stat instanceof EntryStat.Present present)) {
        return;
      }
      switch (present.kind()) {
        case DIRECTORY -> {
          if (path.codePointCount(0, path.length()) < ArtifactLimits.PATH_CHARACTERS) {
            ancestors.add(present);
            visit(path);
            ancestors.removeLast();
          }
        }
        case FILE -> {
          if (Eligibility.isEligible(path, present, ancestors)) {
            collect(new Candidate(path, present.sizeBytes(), present.modifiedEpochSecond()));
          }
        }
        case SYMLINK, OTHER -> {}
      }
    }

    private void collect(Candidate candidate) {
      eligible++;
      if (collector.size() < ArtifactLimits.COLLECTOR_ENTRIES) {
        collector.add(candidate);
      } else if (CodePoints.compare(candidate.path(), collector.peek().path()) < 0) {
        collector.poll();
        collector.add(candidate);
      }
      collectorHighWater.accumulateAndGet(collector.size(), Math::max);
    }

    /** The entry of a collected file, or empty when it vanished or stopped being a regular file while the flag was decided. */
    private java.util.Optional<ArtifactEntry> entry(Candidate candidate) {
      boolean readable = false;
      if (candidate.sizeBytes() <= ArtifactLimits.CONTENT_CAP_BYTES) {
        switch (reader.probe(mission, candidate.path())) {
          case ArtifactReader.Probe.Readable ok -> readable = true;
          case ArtifactReader.Probe.Refused refused -> {
            if (refused.kind() == DetailRefusal.Kind.ARTIFACT_UNREADABLE) {
              diagnostics.accept(new Diagnostic(DiagnosticCode.ARTIFACT_UNREADABLE, mid8, null));
            }
          }
          case ArtifactReader.Probe.Gone gone -> {
            return java.util.Optional.empty();
          }
        }
      }
      return java.util.Optional.of(
          new ArtifactEntry(
              candidate.path(), ArtifactKinds.kindOf(candidate.path()), candidate.sizeBytes(), SECONDS.format(Instant.ofEpochSecond(candidate.modifiedEpochSecond())), readable));
    }
  }

  /** Whether a directory entry name can be one segment of a relative path of the port. */
  private static boolean segment(String name) {
    return !name.isEmpty() && !name.equals(".") && !name.equals("..") && name.indexOf('/') < 0 && name.indexOf('\\') < 0 && name.indexOf('\0') < 0;
  }

  private static boolean hasNonAscii(String text) {
    for (int i = 0; i < text.length(); i++) {
      if (text.charAt(i) > 0x7f) {
        return true;
      }
    }
    return false;
  }
}
