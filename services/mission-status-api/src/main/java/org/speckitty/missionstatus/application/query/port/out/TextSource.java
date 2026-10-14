package org.speckitty.missionstatus.application.query.port.out;

import org.speckitty.missionstatus.application.query.port.out.dto.BytesRead;
import org.speckitty.missionstatus.application.query.port.out.dto.DirListing;
import org.speckitty.missionstatus.application.query.port.out.dto.EntryStat;
import org.speckitty.missionstatus.application.query.port.out.dto.FileRef;
import org.speckitty.missionstatus.application.query.port.out.dto.ReadScope;
import org.speckitty.missionstatus.application.query.port.out.dto.TextRead;

/**
 * The capped, allowlisted text-read port (FR-007): the one reader of every route that opens an authored file or an artifact, and, later,
 * of the governance routes of mission #5533. It names no path type, no {@code IOException} and no route vocabulary; the only
 * Mission-status word on it is {@code MissionRef} inside {@link FileRef.MissionFile}. Every call carries the {@link ReadScope} it is
 * made for: the fence class of an access depends on why it is made.
 *
 * <p>A result the caller can act on (absent, not regular, over the cap, not text) is a returned value. A fault of the operating system,
 * a link in any component and a Mission directory that has gone are thrown as a {@code TextFault}. Over-cap and an I/O failure are
 * distinct kinds on purpose (D-68).
 *
 * <p>This interface is a frozen seam of plan section 7.1 (row 1): a change after the commit that landed it needs a decision note in
 * both missions and the operator's word.
 */
public interface TextSource {

  /**
   * The names of a directory, at most {@code nameLimit} of them, in the order the file system gives them (the caller sorts). It says
   * whether more existed and whether the host's file-name decoding is trustworthy.
   */
  DirListing list(FileRef dir, int nameLimit, ReadScope scope);

  /** The entry at {@code path} without following a link: a link is reported as a link. */
  EntryStat stat(FileRef path, ReadScope scope);

  /** The raw bytes of a regular file of at most {@code cap} bytes. */
  BytesRead readBytes(FileRef file, int cap, ReadScope scope);

  /** A regular file of at most {@code cap} bytes, decoded as strict UTF-8 (a leading byte order mark stays in the text). */
  TextRead readText(FileRef file, int cap, ReadScope scope);
}
