package org.speckitty.missionstatus.adapter.out.filesystem;

import java.nio.file.Path;
import java.util.List;
import java.util.Objects;
import org.speckitty.missionstatus.adapter.out.filesystem.ReadDirResolver.Resolution;
import org.speckitty.missionstatus.application.query.port.out.dto.LedgerRead;
import org.speckitty.missionstatus.application.query.port.out.dto.LedgerStamp;
import org.speckitty.missionstatus.application.query.port.out.dto.LedgerWindow;
import org.speckitty.missionstatus.application.query.port.out.MissionEventSource;
import org.speckitty.missionstatus.application.query.port.out.dto.MissionRef;
import org.speckitty.missionstatus.application.query.port.out.dto.ProjectInputs;
import org.speckitty.missionstatus.application.query.port.out.exceptions.SourceFault;
import org.speckitty.missionstatus.application.query.port.out.exceptions.SourceFault.Kind;
import org.speckitty.missionstatus.domain.model.MissionMeta;

/**
 * The production {@link MissionEventSource}: a project root on disk, read through the primitives of the filesystem adapter
 * ({@link SafeFiles}, {@link Listing}, {@link ReadDirResolver}) and decoded by the codec. It reads only what {@link Allowlist} lists,
 * opens nothing for writing, takes no lock, starts no process and reads no git state beyond the one {@code HEAD} file. Every fault
 * crosses the port as a {@link SourceFault} that names its kind and never a path.
 *
 * <p>Every operation on a Mission resolves its read directory first (the stored topology and directory existence decide, FR-006), so
 * the cost of a {@link #stampLedger stamp} is that resolution plus one stat and a backward scan of the final physical lines (bounded by
 * the length of the last line, not by the size of the ledger; a ledger that is one enormous line is scanned whole). A
 * {@code meta.json} that cannot be used makes every ledger operation row L7, because the read directory cannot be decided.
 *
 * <p>The stamp handed to {@link #readLedger} is not consulted: the read is of whatever the file holds now, and the application
 * derives the cursor facts from the lines it gets (a file that changed after the stamp shows as a tail or as a new prefix).
 */
public final class FilesystemMissionEventSource implements MissionEventSource {

  private final SafeFiles files;
  private final Listing listing;
  private final ReadDirResolver resolver;
  private final FilesystemMissionEventSourceProject project;
  private final FilesystemMissionEventSourceLedger ledger;

  /** The recording seam is settable so that a test can observe every access; production wiring uses {@link #FilesystemMissionEventSource(Path)}. */
  public FilesystemMissionEventSource(Path root, AllowlistAccess access) {
    Objects.requireNonNull(root, "root");
    Objects.requireNonNull(access, "access");
    this.files = new SafeFiles(root, access);
    this.listing = new Listing(files, access);
    this.resolver = new ReadDirResolver(files);
    this.project = new FilesystemMissionEventSourceProject(files, access);
    this.ledger = new FilesystemMissionEventSourceLedger(access);
  }

  /** The production source: every file operation passes straight through. */
  public FilesystemMissionEventSource(Path root) {
    this(root, AllowlistAccess.passThrough());
  }

  @Override
  public ProjectInputs projectInputs() {
    return project.read();
  }

  @Override
  public List<MissionRef> listMissions() {
    return listing.missionNames().stream().map(MissionRef::new).toList();
  }

  @Override
  public MissionMeta readMeta(MissionRef ref) {
    Path own = listing.ownDir(ref.name());
    byte[] bytes = FilesystemMissionEventSourceMeta.read(files, own.resolve(Listing.META));
    return FilesystemMissionEventSourceMeta.decode(bytes, ref.name());
  }

  @Override
  public LedgerStamp stampLedger(MissionRef ref) {
    return ledger.stamp(ledgerPath(ref));
  }

  @Override
  public LedgerRead readLedger(MissionRef ref, LedgerStamp stamp) {
    return ledger.read(ledgerPath(ref));
  }

  @Override
  public LedgerWindow readLedgerFrom(MissionRef ref, long offset) {
    return ledger.window(ledgerPath(ref), offset);
  }

  /** The ledger of the Mission's resolved read directory. An unclassifiable {@code meta.json} is row L7. */
  private Path ledgerPath(MissionRef ref) {
    Resolution resolution = resolver.resolve(ref.name());
    if (!resolution.classified()) {
      throw new SourceFault(Kind.META_UNPARSEABLE);
    }
    return resolution.dir().resolve(FilesystemMissionEventSourceLedger.FILE);
  }
}
