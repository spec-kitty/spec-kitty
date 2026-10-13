package org.speckitty.missionstatus.application.query.port.out.dto;

import java.util.List;
import java.util.Objects;
import org.speckitty.missionstatus.domain.model.LedgerLine;
import org.speckitty.missionstatus.domain.model.TailClassification;

/**
 * The part of a ledger from a byte offset on. {@code lines} are the terminated lines from the offset (numbered from 1 inside the
 * window), {@code precedingLineSha256} is the digest of the physical line that ends at the offset (the digest of nothing at offset 0),
 * {@code size} is the current size in bytes, and {@code aligned} says whether the offset follows a newline (or is 0).
 */
public record LedgerWindow(long size, boolean aligned, String precedingLineSha256, List<LedgerLine> lines, TailClassification tail) {

  public LedgerWindow {
    Objects.requireNonNull(precedingLineSha256, "precedingLineSha256");
    lines = List.copyOf(Objects.requireNonNull(lines, "lines"));
    Objects.requireNonNull(tail, "tail");
  }
}
