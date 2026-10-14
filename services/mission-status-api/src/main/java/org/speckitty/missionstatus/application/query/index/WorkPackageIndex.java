package org.speckitty.missionstatus.application.query.index;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashSet;
import java.util.List;
import java.util.Optional;
import java.util.Set;
import java.util.function.Consumer;
import org.speckitty.missionstatus.application.query.artifact.Eligibility;
import org.speckitty.missionstatus.application.query.port.out.FrontmatterDecoder;
import org.speckitty.missionstatus.application.query.port.out.TextSource;
import org.speckitty.missionstatus.application.query.port.out.dto.BytesRead;
import org.speckitty.missionstatus.application.query.port.out.dto.DirListing;
import org.speckitty.missionstatus.application.query.port.out.dto.EntryStat;
import org.speckitty.missionstatus.application.query.port.out.dto.FileRef;
import org.speckitty.missionstatus.application.query.port.out.dto.MissionRef;
import org.speckitty.missionstatus.application.query.port.out.dto.ReadScope;
import org.speckitty.missionstatus.application.query.port.out.dto.RelativePath;
import org.speckitty.missionstatus.domain.model.CodePoints;
import org.speckitty.missionstatus.domain.model.Diagnostic;
import org.speckitty.missionstatus.domain.model.DiagnosticCode;
import org.speckitty.missionstatus.domain.model.FrontmatterResult;
import org.speckitty.missionstatus.domain.model.WpId;

/**
 * The one component that defines what a Work Package is, for {@code getMission}, {@code getWorkPackage} and {@code getWorkPackageDetail}
 * alike (FR-006). It mirrors the oracle's {@code wp_task_files} and {@code index_work_packages}, over the text-read port and the
 * frontmatter decoder port only; it names no YAML, no file and no codec.
 *
 * <ol>
 *   <li>The candidates are the entries of {@code tasks/} whose name starts with {@code WP} and ends with {@code .md}, case-sensitively,
 *       in the order of their UTF-8 bytes. An absent {@code tasks/} is an empty set; one that is not a directory is a fault.
 *   <li>A candidate that is not an eligible artifact path, or is a link or a directory, is skipped, and its target is never read. A
 *       candidate that cannot be read, or is over 1 MiB, is a fault.
 *   <li>A file whose bytes do not decode, or whose frontmatter is not a valid {@code WPMetadata}, or that holds no valid
 *       {@code work_package_id}, is skipped. Every skip writes {@code wp_file_skipped} with the Mission's {@code mid8} and no path.
 *   <li>The first valid file in byte order wins an identifier; a later file with the same identifier is never served and writes
 *       {@code wp_id_duplicate}.
 *   <li>The locale rule (D-73): when the host's file-name decoding is not trustworthy and a candidate holds a non-ASCII character, the
 *       whole index is refused, never a partial one. A non-candidate name is not looked at.
 * </ol>
 *
 * <p>One file is read, decoded and dropped at a time. The body of the first valid file that holds the requested identifier is kept, and no
 * other body; there is no second read of any file.
 *
 * <p>Public, with a public constructor, because {@code config} constructs it. It holds no per-call state.
 */
public final class WorkPackageIndex {

  /** A Work Package file may be at most this many bytes (1 MiB, provisional: FR-006 item 2). */
  static final int FILE_CAP_BYTES = 1_048_576;

  /** The most names read from {@code tasks/}; a longer directory is refused rather than indexed in part. */
  static final int LISTING_LIMIT = 100_000;

  private static final String PREFIX = "WP";
  private static final String SUFFIX = ".md";
  private static final EntryStat TASKS_DIRECTORY = new EntryStat.Present(EntryStat.EntryKind.DIRECTORY, 0, 0);

  /**
   * The index of one Mission: the winners in identifier order, and the body of the requested Work Package when its file was among them.
   */
  public record Result(List<IndexedWorkPackage> workPackages, Optional<String> capturedBody) {
    public Result {
      workPackages = List.copyOf(workPackages);
    }
  }

  private final TextSource textSource;
  private final FrontmatterDecoder decoder;

  public WorkPackageIndex(TextSource textSource, FrontmatterDecoder decoder) {
    this.textSource = java.util.Objects.requireNonNull(textSource, "textSource");
    this.decoder = java.util.Objects.requireNonNull(decoder, "decoder");
  }

  /**
   * Builds the index of one Mission. Diagnostics go through {@code diagnostics} as they happen; a thrown fault leaves the ones already
   * written in place.
   *
   * @param mid8 the Mission's {@code mid8}, for the diagnostics
   * @param captureBodyOf the Work Package whose body is wanted from the same read that indexes its file
   */
  public Result build(MissionRef mission, String mid8, Optional<WpId> captureBodyOf, Consumer<Diagnostic> diagnostics) {
    List<WpFile> candidates = candidates(mission);
    List<IndexedWorkPackage> winners = new ArrayList<>();
    Set<String> held = new HashSet<>();
    String body = null;
    for (WpFile candidate : candidates) {
      FrontmatterResult.Parsed parsed = read(mission, candidate);
      Optional<WpId> id = parsed == null ? Optional.empty() : WpId.parse(parsed.metadata().workPackageId());
      if (id.isEmpty()) {
        diagnostics.accept(new Diagnostic(DiagnosticCode.WP_FILE_SKIPPED, mid8, null));
      } else if (!held.add(id.get().value())) {
        diagnostics.accept(new Diagnostic(DiagnosticCode.WP_ID_DUPLICATE, mid8, null));
      } else {
        winners.add(new IndexedWorkPackage(id.get(), candidate.name(), parsed.metadata()));
        if (captureBodyOf.isPresent() && captureBodyOf.get().equals(id.get())) {
          body = parsed.body();
        }
      }
    }
    winners.sort(Comparator.comparing(entry -> entry.id().value()));
    return new Result(winners, Optional.ofNullable(body));
  }

  // ---- candidate selection --------------------------------------------------------------------------------------------------

  private List<WpFile> candidates(MissionRef mission) {
    FileRef tasks = new FileRef.MissionFile(mission, RelativePath.of(WpFile.TASKS));
    DirListing listing = textSource.list(tasks, LISTING_LIMIT, ReadScope.AUTHORED);
    switch (listing) {
      case DirListing.Absent absent -> {
        return List.of();
      }
      case DirListing.NotADirectory notADirectory -> throw new WorkPackageIndexFault(WorkPackageIndexFault.Kind.TASKS_NOT_A_DIRECTORY);
      case DirListing.Names names -> {
        return candidates(names);
      }
    }
  }

  private static List<WpFile> candidates(DirListing.Names names) {
    if (names.limitReached()) {
      throw new WorkPackageIndexFault(WorkPackageIndexFault.Kind.LISTING_TOO_LARGE);
    }
    List<String> sorted = new ArrayList<>(names.names().stream().filter(WorkPackageIndex::isCandidate).toList());
    if (!names.trustworthy() && sorted.stream().anyMatch(WorkPackageIndex::hasNonAscii)) {
      throw new WorkPackageIndexFault(WorkPackageIndexFault.Kind.NAMES_UNTRUSTWORTHY);
    }
    sorted.sort(CodePoints::compare);
    return sorted.stream().map(WpFile::new).toList();
  }

  private static boolean isCandidate(String name) {
    return name.startsWith(PREFIX) && name.endsWith(SUFFIX);
  }

  private static boolean hasNonAscii(String name) {
    return name.chars().anyMatch(unit -> unit > 0x7F);
  }

  // ---- one file -------------------------------------------------------------------------------------------------------------

  /** The decoded file, or null when it is skipped. */
  private FrontmatterResult.Parsed read(MissionRef mission, WpFile candidate) {
    if (!Eligibility.isEligiblePath(candidate.artifactPath()) || !isSafeSegment(candidate.name())) {
      return null;
    }
    FileRef file = candidate.in(mission);
    EntryStat leaf = textSource.stat(file, ReadScope.AUTHORED);
    if (!Eligibility.isEligible(candidate.artifactPath(), leaf, List.of(TASKS_DIRECTORY))) {
      return null;
    }
    BytesRead read = textSource.readBytes(file, FILE_CAP_BYTES, ReadScope.AUTHORED);
    return switch (read) {
      case BytesRead.Bytes bytes -> decoded(decoder.decodeWorkPackage(bytes.content()));
      case BytesRead.NotRegular notRegular -> null;
      case BytesRead.Absent absent -> throw new WorkPackageIndexFault(WorkPackageIndexFault.Kind.FILE_UNREADABLE);
      case BytesRead.OverCap overCap -> throw new WorkPackageIndexFault(WorkPackageIndexFault.Kind.FILE_TOO_LARGE);
    };
  }

  private static FrontmatterResult.Parsed decoded(FrontmatterResult result) {
    return result instanceof FrontmatterResult.Parsed parsed ? parsed : null;
  }

  private static boolean isSafeSegment(String name) {
    try {
      new RelativePath(List.of(name));
      return true;
    } catch (IllegalArgumentException unsafe) {
      return false;
    }
  }
}
