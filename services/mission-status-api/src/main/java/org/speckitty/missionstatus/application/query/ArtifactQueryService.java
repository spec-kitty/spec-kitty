package org.speckitty.missionstatus.application.query;

import java.util.ArrayList;
import java.util.List;
import java.util.Objects;
import java.util.Optional;
import java.util.regex.Pattern;
import org.speckitty.missionstatus.application.query.port.in.MissionArtifactQuery;
import org.speckitty.missionstatus.application.query.port.in.exceptions.ArtifactRefused;
import org.speckitty.missionstatus.application.query.port.out.MissionArtifactSource;
import org.speckitty.missionstatus.application.query.port.out.dto.ArtifactBytes;
import org.speckitty.missionstatus.application.query.port.out.dto.ArtifactFile;
import org.speckitty.missionstatus.application.query.port.out.dto.MissionRef;
import org.speckitty.missionstatus.application.query.port.out.exceptions.SourceFault;
import org.speckitty.missionstatus.domain.model.CodePoints;
import org.speckitty.missionstatus.domain.readmodel.artifact.ArtifactContent;
import org.speckitty.missionstatus.domain.readmodel.artifact.ArtifactEntry;
import org.speckitty.missionstatus.domain.readmodel.artifact.ArtifactKind;
import org.speckitty.missionstatus.domain.readmodel.artifact.ArtifactListing;
import org.speckitty.missionstatus.domain.readmodel.artifact.ArtifactMediaType;
import org.speckitty.missionstatus.domain.readmodel.artifact.ArtifactNameRule;
import org.speckitty.missionstatus.domain.readmodel.artifact.ArtifactPathRule;
import org.speckitty.missionstatus.domain.readmodel.artifact.ArtifactRefusalCode;
import org.speckitty.missionstatus.domain.readmodel.artifact.ArtifactText;
import org.speckitty.missionstatus.domain.readmodel.artifact.ArtifactTimestamp;
import org.speckitty.missionstatus.domain.readmodel.artifact.StatusRecordNames;
import org.speckitty.missionstatus.domain.redaction.LeakClasses;

/**
 * The artifact reads, in the order of decision of the reference reader ({@code tests/contract/_mission_status_artifacts.py}).
 *
 * <p>Content read: a missing, repeated or malformed path is 400; an unknown or ill-formed Mission id is 404; a Mission directory that
 * is gone, a link or outside the root is 404 and one that cannot be stat-ed is 500. Then, per file: not eligible is 404, an
 * eligibility the operating system will not answer is 500, an open or read failure is 500, more than the cap by the open handle is
 * 413 (the content is not read), and the bytes decide 413, 415, 422 or 200.
 *
 * <p>Listing: every regular, non-link file of the walk that is eligible, sorted by the UTF-8 bytes of the path (code-point order),
 * the first 1000, each with the stat taken again (a file gone by then is omitted) and a {@code readable} flag that is the content
 * decision itself (a file over the cap is decided from its size and not opened). Any listing fault is 500 {@code
 * artifact_listing_unreadable}.
 */
public final class ArtifactQueryService implements MissionArtifactQuery {

  private static final Pattern MISSION_ID = Pattern.compile("[0-9A-HJKMNP-TV-Z]{26}");

  private final MissionArtifactSource source;
  private final ArtifactText text;

  public ArtifactQueryService(MissionArtifactSource source, LeakClasses leaks) {
    this.source = Objects.requireNonNull(source, "source");
    this.text = new ArtifactText(leaks);
  }

  @Override
  public ArtifactListing listArtifacts(String missionId) {
    MissionRef mission = missionDirectory(missionId, ArtifactRefusalCode.ARTIFACT_LISTING_UNREADABLE);
    try {
      List<String> found = new ArrayList<>();
      for (String path : source.walk(mission)) {
        if (isEligible(mission, path)) {
          found.add(path);
        }
      }
      found.sort(CodePoints::compare);
      List<ArtifactEntry> entries = new ArrayList<>();
      for (String path : found.subList(0, Math.min(found.size(), ArtifactListing.MAX_ENTRIES))) {
        entry(mission, path).ifPresent(entries::add);
      }
      return new ArtifactListing(missionId, entries, found.size() > ArtifactListing.MAX_ENTRIES);
    } catch (SourceFault fault) {
      throw new ArtifactRefused(ArtifactRefusalCode.ARTIFACT_LISTING_UNREADABLE);
    }
  }

  @Override
  public ArtifactContent readArtifact(String missionId, List<String> paths) {
    if (paths == null || paths.size() != 1 || paths.get(0) == null || !ArtifactPathRule.isValid(paths.get(0))) {
      throw new ArtifactRefused(ArtifactRefusalCode.INVALID_ARTIFACT_PATH);
    }
    MissionRef mission = missionDirectory(missionId, ArtifactRefusalCode.ARTIFACT_UNREADABLE);
    String path = paths.get(0);
    Outcome outcome = readFile(mission, path);
    if (outcome.refusal() != null) {
      throw new ArtifactRefused(outcome.refusal());
    }
    return new ArtifactContent(path, ArtifactKind.classify(path), ArtifactMediaType.of(path), outcome.sizeBytes(), outcome.decision().redacted(), outcome.decision().content());
  }

  /** The Mission's directory, or the refusal: 404 when it is unknown or not there, {@code unreadable} when it cannot be stat-ed. */
  private MissionRef missionDirectory(String missionId, ArtifactRefusalCode unreadable) {
    if (missionId == null || !MISSION_ID.matcher(missionId).matches()) {
      throw new ArtifactRefused(ArtifactRefusalCode.NOT_FOUND);
    }
    MissionRef mission = source.findMission(missionId).orElseThrow(() -> new ArtifactRefused(ArtifactRefusalCode.NOT_FOUND));
    boolean present;
    try {
      present = source.missionDirPresent(mission);
    } catch (SourceFault fault) {
      throw new ArtifactRefused(unreadable);
    }
    if (!present) {
      throw new ArtifactRefused(ArtifactRefusalCode.NOT_FOUND);
    }
    return mission;
  }

  /**
   * The one eligibility rule: a valid path, not a root status record, the name of an artifact, and a regular file with no link on the
   * way. Faults propagate.
   */
  private boolean isEligible(MissionRef mission, String path) {
    return ArtifactPathRule.isValid(path)
        && !StatusRecordNames.isStatusRecord(path)
        && ArtifactNameRule.isArtifactName(path)
        && source.isRegularFileWithoutLinks(mission, path);
  }

  /** The content decision of one file, which the listing's {@code readable} flag reuses. */
  private Outcome readFile(MissionRef mission, String path) {
    boolean eligible;
    try {
      eligible = isEligible(mission, path);
    } catch (SourceFault fault) {
      return Outcome.refused(ArtifactRefusalCode.ARTIFACT_UNREADABLE);
    }
    if (!eligible) {
      return Outcome.refused(ArtifactRefusalCode.NOT_FOUND);
    }
    ArtifactBytes bytes = source.read(mission, path, ArtifactText.MAX_CONTENT_BYTES);
    return switch (bytes) {
      case ArtifactBytes.Unreadable unreadable -> Outcome.refused(ArtifactRefusalCode.ARTIFACT_UNREADABLE);
      case ArtifactBytes.TooLarge tooLarge -> Outcome.refused(ArtifactRefusalCode.ARTIFACT_TOO_LARGE);
      case ArtifactBytes.Content content -> {
        ArtifactText.Decision decision = text.decide(content.data());
        yield decision.served() ? new Outcome(null, content.sizeBytes(), decision) : Outcome.refused(decision.refusal());
      }
    };
  }

  private Optional<ArtifactEntry> entry(MissionRef mission, String path) {
    Optional<ArtifactFile> file = source.stat(mission, path);
    if (file.isEmpty()) {
      return Optional.empty();
    }
    long size = file.get().sizeBytes();
    boolean readable = size <= ArtifactText.MAX_CONTENT_BYTES && readFile(mission, path).refusal() == null;
    return Optional.of(new ArtifactEntry(path, ArtifactKind.classify(path), size, ArtifactTimestamp.format(file.get().modifiedEpochSecond()), readable));
  }

  private record Outcome(ArtifactRefusalCode refusal, long sizeBytes, ArtifactText.Decision decision) {

    static Outcome refused(ArtifactRefusalCode code) {
      return new Outcome(code, 0, null);
    }
  }
}
