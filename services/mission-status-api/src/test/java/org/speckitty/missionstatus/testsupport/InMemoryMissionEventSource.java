package org.speckitty.missionstatus.testsupport;

import java.nio.ByteBuffer;
import java.nio.charset.CharacterCodingException;
import java.nio.charset.CodingErrorAction;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.EnumMap;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;
import java.util.concurrent.atomic.AtomicInteger;
import org.speckitty.missionstatus.adapter.out.filesystem.codec.LedgerLineDecoder;
import org.speckitty.missionstatus.application.query.port.out.dto.LedgerRead;
import org.speckitty.missionstatus.application.query.port.out.dto.LedgerStamp;
import org.speckitty.missionstatus.application.query.port.out.dto.LedgerWindow;
import org.speckitty.missionstatus.application.query.port.out.MissionEventSource;
import org.speckitty.missionstatus.application.query.port.out.dto.MissionRef;
import org.speckitty.missionstatus.application.query.port.out.dto.ProjectInputs;
import org.speckitty.missionstatus.application.query.port.out.exceptions.SourceFault;
import org.speckitty.missionstatus.domain.readmodel.cursor.StreamCursor;
import org.speckitty.missionstatus.domain.model.MissionId;
import org.speckitty.missionstatus.domain.model.MissionMeta;
import org.speckitty.missionstatus.domain.model.TailClassification;
import org.speckitty.missionstatus.domain.model.Topology;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.json.JsonMapper;

/**
 * The second source of FR-013: a {@link MissionEventSource} built from RAW bytes, never from {@code LedgerLine} values. Ledger bytes are
 * decoded through the production {@link LedgerLineDecoder}; {@code meta.json} bytes are read here (test code may use a JSON library).
 * It also carries the instrumentation and the fault injection that the application tests need.
 */
public final class InMemoryMissionEventSource implements MissionEventSource {

  /** The operation a fault is injected into. */
  public enum Op {
    META,
    STAMP,
    LEDGER,
    WINDOW
  }

  private static final JsonMapper JSON = JsonMapper.builder().build();
  private static final String EMPTY_DIGEST = StreamCursor.start().invariant();

  private static final class State {
    byte[] meta;
    byte[] ledger;
    long version;
    final Map<Op, SourceFault.Kind> faults = new EnumMap<>(Op.class);
    final java.util.Set<Op> unexpected = java.util.EnumSet.noneOf(Op.class);

    State(byte[] meta, byte[] ledger) {
      this.meta = meta;
      this.ledger = ledger;
    }
  }

  private final Map<String, State> missions = new TreeMap<>();
  private ProjectInputs project;
  private SourceFault.Kind listingFault;
  private SourceFault.Kind projectFault;
  private Runnable beforeWindowRead;
  private final Map<String, AtomicInteger> calls = new HashMap<>();

  private InMemoryMissionEventSource(ProjectInputs project) {
    this.project = project;
  }

  /** Realises a fixture description in memory. */
  public static InMemoryMissionEventSource from(FixtureSpec spec) {
    FixtureSpec.Project p = spec.project();
    InMemoryMissionEventSource source = new InMemoryMissionEventSource(new ProjectInputs(p.name(), p.specKittyVersion(), p.schemaVersion(), p.branchName()));
    spec.missions().forEach(source::addMission);
    return source;
  }

  // ---- instrumentation -----------------------------------------------------------------------------------------------------

  public int calls(String operation) {
    return calls.computeIfAbsent(operation, key -> new AtomicInteger()).get();
  }

  public void resetCalls() {
    calls.clear();
  }

  private void count(String operation) {
    calls.computeIfAbsent(operation, key -> new AtomicInteger()).incrementAndGet();
  }

  // ---- mutation and fault injection ----------------------------------------------------------------------------------------

  public synchronized void addMission(FixtureSpec.Mission mission) {
    missions.put(mission.name(), new State(mission.metaJson(), mission.ledger()));
  }

  /** The Mission directory disappears: the listing drops it and every later operation reports a vanish. */
  public synchronized void removeMission(String name) {
    missions.remove(name);
  }

  public synchronized void appendLedger(String name, String text) {
    appendLedger(name, text.getBytes(StandardCharsets.UTF_8));
  }

  public synchronized void appendLedger(String name, byte[] bytes) {
    State state = state(name);
    byte[] current = state.ledger == null ? new byte[0] : state.ledger;
    byte[] joined = Arrays.copyOf(current, current.length + bytes.length);
    System.arraycopy(bytes, 0, joined, current.length, bytes.length);
    state.ledger = joined;
    state.version++;
  }

  /** Replaces the whole ledger (a rewrite, shorter or the same length). */
  public synchronized void replaceLedger(String name, byte[] bytes) {
    State state = state(name);
    state.ledger = bytes;
    state.version++;
  }

  public synchronized void deleteLedger(String name) {
    State state = state(name);
    state.ledger = null;
    state.version++;
  }

  public synchronized void replaceMeta(String name, byte[] metaJson) {
    state(name).meta = metaJson;
  }

  public synchronized void inject(String name, Op op, SourceFault.Kind kind) {
    state(name).faults.put(op, kind);
  }

  /** The operation fails with a runtime exception that is not a {@link SourceFault} (a bug in the source). */
  public synchronized void injectUnexpected(String name, Op op) {
    state(name).unexpected.add(op);
  }

  public synchronized void clear(String name, Op op) {
    state(name).faults.remove(op);
  }

  /** Runs the action once, just before the next windowed read is served (a write that lands between two readers). */
  public synchronized void beforeNextWindowRead(Runnable action) {
    this.beforeWindowRead = action;
  }

  /** {@code kitty-specs/} cannot be listed (null repairs it). */
  public synchronized void failListing(SourceFault.Kind kind) {
    this.listingFault = kind;
  }

  public synchronized void setProject(ProjectInputs replacement) {
    this.project = replacement;
  }

  /** The project-header inputs cannot be read (null repairs it). */
  public synchronized void failProject(SourceFault.Kind kind) {
    this.projectFault = kind;
  }

  private State state(String name) {
    State state = missions.get(name);
    if (state == null) {
      throw new IllegalArgumentException("no Mission directory " + name);
    }
    return state;
  }

  private State resolve(MissionRef ref, Op op) {
    State state = missions.get(ref.name());
    if (state == null) {
      throw new SourceFault(SourceFault.Kind.VANISHED);
    }
    if (state.unexpected.contains(op)) {
      throw new IllegalStateException("injected failure");
    }
    SourceFault.Kind kind = state.faults.get(op);
    if (kind != null) {
      throw new SourceFault(kind);
    }
    return state;
  }

  // ---- the outbound port ---------------------------------------------------------------------------------------------------

  @Override
  public synchronized ProjectInputs projectInputs() {
    count("projectInputs");
    if (projectFault != null) {
      throw new SourceFault(projectFault);
    }
    return project;
  }

  @Override
  public synchronized List<MissionRef> listMissions() {
    count("listMissions");
    if (listingFault != null) {
      throw new SourceFault(listingFault);
    }
    List<MissionRef> refs = new ArrayList<>();
    missions.keySet().forEach(name -> refs.add(new MissionRef(name)));
    return refs;
  }

  @Override
  public synchronized MissionMeta readMeta(MissionRef ref) {
    count("readMeta");
    return decodeMeta(resolve(ref, Op.META).meta);
  }

  @Override
  public synchronized LedgerStamp stampLedger(MissionRef ref) {
    count("stampLedger");
    State state = resolve(ref, Op.STAMP);
    byte[] ledger = state.ledger;
    if (ledger == null) {
      return LedgerStamp.of("absent", state.version);
    }
    int end = terminatedLength(ledger);
    return LedgerStamp.of(ledger.length, state.version, end, digestOfLastLine(ledger, end));
  }

  @Override
  public synchronized LedgerRead readLedger(MissionRef ref, LedgerStamp stamp) {
    count("readLedger");
    State state = resolve(ref, Op.LEDGER);
    if (state.ledger == null) {
      return new LedgerRead(List.of(), TailClassification.NONE);
    }
    LedgerLineDecoder.Decoded decoded = LedgerLineDecoder.decode(state.ledger);
    return new LedgerRead(decoded.lines(), decoded.tail());
  }

  @Override
  public synchronized LedgerWindow readLedgerFrom(MissionRef ref, long offset) {
    count("readLedgerFrom");
    if (beforeWindowRead != null) {
      Runnable action = beforeWindowRead;
      beforeWindowRead = null;
      action.run();
    }
    State state = resolve(ref, Op.WINDOW);
    byte[] ledger = state.ledger == null ? new byte[0] : state.ledger;
    if (offset > ledger.length) {
      return new LedgerWindow(ledger.length, false, EMPTY_DIGEST, List.of(), TailClassification.NONE);
    }
    int at = (int) offset;
    boolean aligned = at == 0 || ledger[at - 1] == '\n';
    String preceding = !aligned ? EMPTY_DIGEST : at == 0 ? EMPTY_DIGEST : digestOfLastLine(ledger, at);
    LedgerLineDecoder.Decoded decoded = LedgerLineDecoder.decode(Arrays.copyOfRange(ledger, at, ledger.length));
    return new LedgerWindow(ledger.length, aligned, preceding, decoded.lines(), decoded.tail());
  }

  // ---- helpers -------------------------------------------------------------------------------------------------------------

  private static int terminatedLength(byte[] ledger) {
    for (int i = ledger.length - 1; i >= 0; i--) {
      if (ledger[i] == '\n') {
        return i + 1;
      }
    }
    return 0;
  }

  /** The digest of the physical line that ends at {@code end} (an offset just after a newline). */
  private static String digestOfLastLine(byte[] ledger, int end) {
    if (end == 0) {
      return EMPTY_DIGEST;
    }
    int start = end - 1;
    while (start > 0 && ledger[start - 1] != '\n') {
      start--;
    }
    return StreamCursor.digestOf(Arrays.copyOfRange(ledger, start, end));
  }

  private static MissionMeta decodeMeta(byte[] bytes) {
    try {
      String text =
          StandardCharsets.UTF_8
              .newDecoder()
              .onMalformedInput(CodingErrorAction.REPORT)
              .onUnmappableCharacter(CodingErrorAction.REPORT)
              .decode(ByteBuffer.wrap(bytes))
              .toString();
      JsonNode meta = JSON.readTree(text);
      if (!meta.isObject()) {
        throw new SourceFault(SourceFault.Kind.META_UNPARSEABLE);
      }
      return new MissionMeta(
          new MissionId(text(meta, "mission_id")),
          text(meta, "slug"),
          text(meta, "friendly_name"),
          meta.get("mission_number") == null || meta.get("mission_number").isNull() ? null : meta.get("mission_number").asInt(),
          text(meta, "mission_type"),
          text(meta, "target_branch"),
          Topology.fromStored(text(meta, "topology")),
          text(meta, "created_at"),
          text(meta, "accepted_at"),
          text(meta, "merged_at"),
          text(meta, "discarded_at"),
          meta.get("baseline_merge_commit") != null && !meta.get("baseline_merge_commit").isNull() && !meta.get("baseline_merge_commit").asString().isEmpty());
    } catch (CharacterCodingException | RuntimeException unusable) {
      if (unusable instanceof SourceFault fault) {
        throw fault;
      }
      throw new SourceFault(SourceFault.Kind.META_UNPARSEABLE);
    }
  }

  private static String text(JsonNode node, String key) {
    JsonNode value = node.get(key);
    return value == null || value.isNull() ? null : value.asString();
  }
}
