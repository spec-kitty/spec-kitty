package org.speckitty.missionstatus.adapter.out.filesystem;

import java.io.IOException;
import java.nio.file.InvalidPathException;
import java.nio.file.Path;
import java.nio.file.attribute.BasicFileAttributes;
import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Deque;
import java.util.List;
import java.util.Objects;
import java.util.Optional;
import org.speckitty.missionstatus.application.query.port.out.MissionArtifactSource;
import org.speckitty.missionstatus.application.query.port.out.dto.ArtifactBytes;
import org.speckitty.missionstatus.application.query.port.out.dto.ArtifactFile;
import org.speckitty.missionstatus.application.query.port.out.dto.MissionRef;
import org.speckitty.missionstatus.application.query.port.out.exceptions.SourceFault;
import org.speckitty.missionstatus.application.query.port.out.exceptions.SourceFault.Kind;
import org.speckitty.missionstatus.domain.model.CodePoints;
import org.speckitty.missionstatus.domain.readmodel.artifact.ArtifactPathRule;
import tools.jackson.databind.JsonNode;

/**
 * The production {@link MissionArtifactSource}: the primary directory {@code kitty-specs/<name>/} of a Mission, read the way the
 * reference reader ({@code tests/contract/_mission_status_artifacts.py}) reads it. It opens only what {@link ArtifactAllowlist} lists,
 * through the {@link AllowlistAccess} seam: it never follows a link while walking, checks every component of a path with an lstat
 * before it opens anything, and opens a file only through {@link SafeFiles#readCapped}, which refuses a final-component link.
 *
 * <p>It is a separate source from {@link FilesystemMissionEventSource} on purpose: the event source still never opens an artifact,
 * and its allowlist ({@link Allowlist}) is unchanged.
 */
public final class FilesystemMissionArtifactSource implements MissionArtifactSource {

  private static final String MISSION_ID = "mission_id";

  private final SafeFiles files;
  private final AllowlistAccess access;

  /** The recording seam is settable so that a test can observe every access. */
  public FilesystemMissionArtifactSource(Path root, AllowlistAccess access) {
    Objects.requireNonNull(root, "root");
    this.access = Objects.requireNonNull(access, "access");
    this.files = new SafeFiles(root, access);
  }

  /** The production source over a project root given as text (for {@code config}, which may not name a file API). */
  public static FilesystemMissionArtifactSource forRoot(String root) {
    return new FilesystemMissionArtifactSource(Path.of(root), AllowlistAccess.passThrough());
  }

  @Override
  public Optional<MissionRef> findMission(String missionId) {
    Path specs = files.root().resolve(Listing.SPECS);
    List<String> names;
    try {
      names = new ArrayList<>(access.listNames(specs));
    } catch (IOException unlistable) {
      // the reference's index is empty when kitty-specs/ cannot be listed: every Mission is unknown
      return Optional.empty();
    }
    names.sort(CodePoints::compare);
    for (String name : names) {
      if (missionId.equals(missionIdOf(specs, name))) {
        return Optional.of(new MissionRef(name));
      }
    }
    return Optional.empty();
  }

  /** The {@code mission_id} of one directory's {@code meta.json}, or null when it has none the reference would take. */
  private String missionIdOf(Path specs, String name) {
    Optional<byte[]> bytes;
    try {
      bytes = files.readRegular(specs.resolve(name).resolve(Listing.META), SafeFiles.SMALL_FILE_MAX, Kind.PATH_REFUSED, Kind.META_UNPARSEABLE);
    } catch (SourceFault | InvalidPathException unusable) {
      return null;
    }
    Optional<JsonNode> meta = bytes.flatMap(ReadDirResolverJson::object);
    JsonNode id = meta.map(object -> object.get(MISSION_ID)).orElse(null);
    return id != null && id.isString() ? id.stringValue() : null;
  }

  @Override
  public boolean missionDirPresent(MissionRef ref) {
    try {
      files.requireContainedDir(missionDir(ref));
      return true;
    } catch (SourceFault fault) {
      if (fault.kind() == Kind.DIR_UNREADABLE) {
        throw fault;
      }
      return false;
    } catch (InvalidPathException unusable) {
      return false;
    }
  }

  @Override
  public List<String> walk(MissionRef ref) {
    Path mission = missionDir(ref);
    List<String> found = new ArrayList<>();
    Deque<String> pending = new ArrayDeque<>();
    pending.push("");
    while (!pending.isEmpty()) {
      String current = pending.pop();
      List<String> names = listOrEmpty(current.isEmpty() ? mission : mission.resolve(current));
      for (String name : names) {
        String relative = current.isEmpty() ? name : current + "/" + name;
        Optional<BasicFileAttributes> attributes = lstat(mission, relative);
        if (attributes.isEmpty()) {
          continue;
        }
        if (attributes.get().isDirectory()) {
          // a directory whose own path already has the maximum length holds no path the rule accepts
          if (ArtifactPathRule.length(relative) < ArtifactPathRule.MAX_LENGTH) {
            pending.push(relative);
          }
        } else if (attributes.get().isRegularFile()) {
          found.add(relative);
        }
      }
    }
    return found;
  }

  private List<String> listOrEmpty(Path directory) {
    try {
      List<String> names = new ArrayList<>(access.listNames(directory));
      names.sort(CodePoints::compare);
      return names;
    } catch (IOException failure) {
      if (SafeFiles.isAbsent(failure)) {
        return List.of();
      }
      throw new SourceFault(Kind.DIR_UNREADABLE);
    }
  }

  @Override
  public boolean isRegularFileWithoutLinks(MissionRef ref, String path) {
    Path current = missionDir(ref);
    String[] segments = path.split("/", -1);
    for (int index = 0; index < segments.length; index++) {
      Optional<BasicFileAttributes> attributes;
      try {
        current = current.resolve(segments[index]);
      } catch (InvalidPathException unusable) {
        return false;
      }
      attributes = files.statNoFollow(current);
      if (attributes.isEmpty() || attributes.get().isSymbolicLink()) {
        return false;
      }
      if (index == segments.length - 1) {
        return attributes.get().isRegularFile();
      }
      if (!attributes.get().isDirectory()) {
        return false;
      }
    }
    return false;
  }

  @Override
  public Optional<ArtifactFile> stat(MissionRef ref, String path) {
    return lstat(missionDir(ref), path).map(attributes -> new ArtifactFile(attributes.size(), attributes.lastModifiedTime().toInstant().getEpochSecond()));
  }

  @Override
  public ArtifactBytes read(MissionRef ref, String path, int cap) {
    try {
      return files.readCapped(missionDir(ref).resolve(path), cap);
    } catch (InvalidPathException unusable) {
      return new ArtifactBytes.Unreadable();
    }
  }

  private Path missionDir(MissionRef ref) {
    return files.root().resolve(Listing.SPECS).resolve(ref.name());
  }

  /** The lstat of {@code relative} below {@code mission}: empty when nothing is there or the name cannot be a path here. */
  private Optional<BasicFileAttributes> lstat(Path mission, String relative) {
    try {
      return files.statNoFollow(mission.resolve(relative));
    } catch (InvalidPathException unusable) {
      return Optional.empty();
    }
  }
}
