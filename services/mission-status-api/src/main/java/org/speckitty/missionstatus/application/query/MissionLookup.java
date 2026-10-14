package org.speckitty.missionstatus.application.query;

import java.util.List;
import java.util.Objects;
import org.speckitty.missionstatus.application.query.port.out.MissionEventSource;
import org.speckitty.missionstatus.application.query.port.out.dto.MissionRef;
import org.speckitty.missionstatus.application.query.port.out.exceptions.SourceFault;
import org.speckitty.missionstatus.domain.model.MissionId;
import org.speckitty.missionstatus.domain.model.MissionMeta;

/**
 * The probe-free lookup of a Mission by its id: the scan that {@code MissionStatusQueryService#resolve} used to own. It lists the
 * Missions and reads each {@code meta.json} in listing order until one carries the id; it never stamps a ledger. A directory whose
 * {@code meta.json} cannot be read has no id to compare, so the first such fault is remembered: when nothing matches, it decides the
 * answer instead of a plain "unknown". A faulted sibling before the match does not stop the scan (D-39). {@link #hasDuplicate}
 * continues past the match only to find a second readable directory with the same id (D-58).
 */
final class MissionLookup {

  /** The Mission that was found: its directory reference, its {@code meta.json} and its short id. */
  record Found(MissionRef ref, MissionMeta meta, String mid8) {}

  /**
   * The outcome of {@link #find}: the match (or null), the kind of the first unreadable directory seen before the scan ended, and the
   * references the scan has not reached.
   */
  record Scan(Found found, SourceFault.Kind firstFault, List<MissionRef> unscanned) {}

  private final MissionEventSource source;

  MissionLookup(MissionEventSource source) {
    this.source = Objects.requireNonNull(source, "source");
  }

  /**
   * Lists the Missions and scans them until the first one that carries {@code id}. A vanished directory is not a fault worth remembering.
   *
   * @throws SourceFault when the Missions cannot be listed
   */
  Scan find(MissionId id) {
    List<MissionRef> refs = source.listMissions();
    SourceFault.Kind firstFault = null;
    for (int index = 0; index < refs.size(); index++) {
      MissionRef ref = refs.get(index);
      try {
        MissionMeta meta = source.readMeta(ref);
        if (meta.missionId().equals(id)) {
          return new Scan(new Found(ref, meta, meta.missionId().mid8()), firstFault, refs.subList(index + 1, refs.size()));
        }
      } catch (SourceFault fault) {
        if (fault.kind() != SourceFault.Kind.VANISHED && firstFault == null) {
          firstFault = fault.kind();
        }
      }
    }
    return new Scan(null, firstFault, List.of());
  }

  /** Continues the scan past a match: true when a second readable directory carries the same id. Reads each later {@code meta.json} once. */
  boolean hasDuplicate(Scan scan) {
    if (scan.found() == null) {
      return false;
    }
    for (MissionRef ref : scan.unscanned()) {
      try {
        if (source.readMeta(ref).missionId().equals(scan.found().meta().missionId())) {
          return true;
        }
      } catch (SourceFault ignored) {
        // a faulted sibling after the match neither hides nor creates a duplicate; the match is already decided
      }
    }
    return false;
  }
}
