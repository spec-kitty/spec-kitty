package org.speckitty.missionstatus.application.query.port.out.dto;

import java.util.List;
import java.util.Objects;
import org.speckitty.missionstatus.domain.model.LedgerLine;
import org.speckitty.missionstatus.domain.model.TailClassification;

/** The whole ledger of one Mission: its terminated lines, already decoded, and what follows the last newline. */
public record LedgerRead(List<LedgerLine> lines, TailClassification tail) {

  public LedgerRead {
    lines = List.copyOf(Objects.requireNonNull(lines, "lines"));
    Objects.requireNonNull(tail, "tail");
  }
}
