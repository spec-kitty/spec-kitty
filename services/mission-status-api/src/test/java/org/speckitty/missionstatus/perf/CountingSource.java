package org.speckitty.missionstatus.perf;

import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicInteger;
import org.speckitty.missionstatus.application.query.port.out.dto.LedgerRead;
import org.speckitty.missionstatus.application.query.port.out.dto.LedgerStamp;
import org.speckitty.missionstatus.application.query.port.out.dto.LedgerWindow;
import org.speckitty.missionstatus.application.query.port.out.MissionEventSource;
import org.speckitty.missionstatus.application.query.port.out.dto.MissionRef;
import org.speckitty.missionstatus.application.query.port.out.dto.ProjectInputs;
import org.speckitty.missionstatus.domain.model.MissionMeta;

/** The real source behind a call counter per method: the cache design (one stat per Mission, one whole-ledger read per changed Mission) is asserted from it. */
public final class CountingSource implements MissionEventSource {

  private final MissionEventSource delegate;
  private final Map<String, AtomicInteger> calls = new ConcurrentHashMap<>();

  public CountingSource(MissionEventSource delegate) {
    this.delegate = delegate;
  }

  public int calls(String method) {
    AtomicInteger count = calls.get(method);
    return count == null ? 0 : count.get();
  }

  private void count(String method) {
    calls.computeIfAbsent(method, key -> new AtomicInteger()).incrementAndGet();
  }

  @Override
  public ProjectInputs projectInputs() {
    count("projectInputs");
    return delegate.projectInputs();
  }

  @Override
  public List<MissionRef> listMissions() {
    count("listMissions");
    return delegate.listMissions();
  }

  @Override
  public MissionMeta readMeta(MissionRef ref) {
    count("readMeta");
    return delegate.readMeta(ref);
  }

  @Override
  public LedgerStamp stampLedger(MissionRef ref) {
    count("stampLedger");
    return delegate.stampLedger(ref);
  }

  @Override
  public LedgerRead readLedger(MissionRef ref, LedgerStamp stamp) {
    count("readLedger");
    return delegate.readLedger(ref, stamp);
  }

  @Override
  public LedgerWindow readLedgerFrom(MissionRef ref, long offset) {
    count("readLedgerFrom");
    return delegate.readLedgerFrom(ref, offset);
  }
}
