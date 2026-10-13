package org.speckitty.missionstatus.application.query.port.out;

import java.util.List;
import org.speckitty.missionstatus.application.query.port.out.dto.LedgerRead;
import org.speckitty.missionstatus.application.query.port.out.dto.LedgerStamp;
import org.speckitty.missionstatus.application.query.port.out.dto.LedgerWindow;
import org.speckitty.missionstatus.application.query.port.out.dto.MissionRef;
import org.speckitty.missionstatus.application.query.port.out.dto.ProjectInputs;
import org.speckitty.missionstatus.application.query.port.out.exceptions.SourceFault;
import org.speckitty.missionstatus.domain.model.MissionMeta;

/**
 * The outbound seam: everything the application cannot compute. Path resolution, symbolic-link and containment checks, listing and
 * operating-system faults stay behind it; so does the decoding of ledger lines. A fault is a {@link SourceFault}, never an
 * {@code IOException}.
 */
public interface MissionEventSource {

  /** The project-header inputs. */
  ProjectInputs projectInputs();

  /** Every Mission directory that holds a {@code meta.json}, sorted by the source in name order. */
  List<MissionRef> listMissions();

  /** The Mission's {@code meta.json}, decoded. */
  MissionMeta readMeta(MissionRef ref);

  /** A cheap identity of the ledger (a stat and a bounded read of the last line); an absent ledger has a stamp too. */
  LedgerStamp stampLedger(MissionRef ref);

  /** The whole ledger, decoded. Called only on a cache miss, with the stamp that missed. */
  LedgerRead readLedger(MissionRef ref, LedgerStamp stamp);

  /** The ledger from a byte offset on. */
  LedgerWindow readLedgerFrom(MissionRef ref, long offset);
}
