package org.speckitty.missionstatus.application.query;

import static org.assertj.core.api.Assertions.assertThat;

import java.lang.reflect.Method;
import java.lang.reflect.ParameterizedType;
import java.lang.reflect.RecordComponent;
import java.lang.reflect.Type;
import java.time.Duration;
import java.util.ArrayList;
import java.util.IdentityHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.Set;
import java.util.TreeSet;
import org.junit.jupiter.api.Test;
import org.speckitty.missionstatus.application.query.port.in.MissionStatusQuery;
import org.speckitty.missionstatus.application.query.port.in.Subscription;
import org.speckitty.missionstatus.application.query.port.in.dto.StreamScope;
import org.speckitty.missionstatus.domain.model.MissionId;
import org.speckitty.missionstatus.domain.readmodel.cursor.StreamCursor;
import org.speckitty.missionstatus.testsupport.FixtureSpec;
import org.speckitty.missionstatus.testsupport.Rows;

/**
 * Operator ruling A3 (plan 15.6): the inbound port hands out projected values only. A ledger whose status rows carry a credential-shaped
 * {@code reason}, a path-shaped {@code reviewRef} and an address in {@code reasonSource} and {@code claimAgent} is read through the port
 * alone ({@code changesSince} and a live subscription), and nothing the port returns may hold a canary or name a raw ledger member.
 *
 * <p>The test uses reflection and {@code Object}-typed locals only, so it compiles on the phase base (where the port returns raw rows) as
 * well as on the tip; it is red on the base and green once the port projects. All canaries are synthetic.
 */
class PortLeakCanaryTest {

  private static final String REASON = "CANARYREASON-ghp_" + "a".repeat(36);
  private static final String REVIEW_REF = "/srv/CANARYREVIEW/review-ref";
  private static final String REASON_SOURCE = "CANARYSOURCE@canary-example.test";
  private static final String CLAIM_AGENT = "CANARYAGENT@canary-example.test";
  private static final List<String> CANARIES = List.of("CANARYREASON", "CANARYREVIEW", "CANARYSOURCE", "CANARYAGENT");
  private static final Set<String> RAW_MEMBERS = Set.of("reason", "reviewRef", "reasonSource", "claimAgent");

  private static String plantedStatusRow(String eventId, String from, String to) {
    return "{\"actor\":\"claude\",\"at\":\"2026-09-01T10:00:00Z\",\"event_id\":\"" + eventId + "\",\"evidence\":null,\"execution_mode\":\"worktree\",\"force\":false,"
        + "\"from_lane\":\"" + from + "\",\"policy_metadata\":{\"agent\":\"" + CLAIM_AGENT + "\"},\"reason\":\"" + REASON + "\",\"reason_source\":\"" + REASON_SOURCE + "\","
        + "\"review_ref\":\"" + REVIEW_REF + "\",\"to_lane\":\"" + to + "\",\"wp_id\":\"WP01\"}\n";
  }

  private static Fx plantedLedger() {
    String ledger = Rows.lifecycle(Rows.id(1), "MissionCreated", Fx.T0) + plantedStatusRow(Rows.id(2), "planned", "claimed") + plantedStatusRow(Rows.id(3), "claimed", "in_progress");
    return new Fx(FixtureSpec.of(Fx.mission("alpha", Rows.ALPHA_ID, StreamFx.CREATED, ledger)));
  }

  /** Every value the port hands out for the planted Mission: the batch of {@code changesSince} and every signal of a replaying subscription. */
  private static List<Object> returned(MissionStatusQuery query) throws Exception {
    StreamScope scope = new StreamScope.OneMission(new MissionId(Rows.ALPHA_ID));
    List<Object> values = new ArrayList<>();
    Object batch = query.changesSince(scope, Optional.of(StreamCursor.start()));
    values.add(batch);
    try (Subscription subscription = query.subscribe(scope, Optional.of(StreamCursor.start()))) {
      for (int i = 0; i < 50; i++) {
        Object signal = subscription.next(Duration.ZERO);
        values.add(signal);
        String kind = signal.getClass().getSimpleName();
        if (kind.equals("Idle") || kind.equals("Closed")) {
          break;
        }
      }
    }
    return values;
  }

  @Test
  void nothingThePortReturnsHoldsACanary() throws Exception {
    List<Object> values = returned(plantedLedger().service);
    assertThat(values).hasSizeGreaterThan(1);

    List<String> strings = new ArrayList<>();
    for (Object value : values) {
      collectStrings(value, strings, new IdentityHashMap<>());
      strings.add(String.valueOf(value));
    }

    assertThat(strings).as("the strings and toString of everything the port returned").isNotEmpty();
    for (String canary : CANARIES) {
      assertThat(strings).as("canary " + canary).noneMatch(text -> text.contains(canary));
    }
  }

  @Test
  void noTypeThePortReturnsHasAMemberNamedLikeARawLedgerField() {
    Set<Class<?>> reached = new TreeSetOfClasses();
    for (Method method : MissionStatusQuery.class.getMethods()) {
      if (method.getName().equals("changesSince") || method.getName().equals("subscribe")) {
        reach(method.getGenericReturnType(), reached);
      }
    }
    reach(Subscription.class, reached);
    for (Method method : Subscription.class.getMethods()) {
      if (method.getName().equals("next")) {
        reach(method.getGenericReturnType(), reached);
      }
    }

    Set<String> names = new TreeSet<>();
    for (Class<?> type : reached) {
      if (type.isRecord()) {
        for (RecordComponent component : type.getRecordComponents()) {
          names.add(type.getSimpleName() + "." + component.getName());
        }
      }
      for (var field : type.getDeclaredFields()) {
        names.add(type.getSimpleName() + "." + field.getName());
      }
    }
    assertThat(reached).as("the walk reached the port's own types").isNotEmpty();
    assertThat(names).as("members named like a raw ledger field").noneMatch(name -> RAW_MEMBERS.contains(name.substring(name.indexOf('.') + 1)));
  }

  // ---- reflection walks --------------------------------------------------------------------------------------------------------

  private static void collectStrings(Object value, List<String> out, Map<Object, Boolean> seen) throws Exception {
    if (value == null || seen.put(value, Boolean.TRUE) != null) {
      return;
    }
    if (value instanceof String text) {
      out.add(text);
    } else if (value instanceof Iterable<?> items) {
      for (Object item : items) {
        collectStrings(item, out, seen);
      }
    } else if (value instanceof Optional<?> optional) {
      if (optional.isPresent()) {
        collectStrings(optional.get(), out, seen);
      }
    } else if (value.getClass().isRecord()) {
      for (RecordComponent component : value.getClass().getRecordComponents()) {
        Method accessor = component.getAccessor();
        accessor.setAccessible(true);
        collectStrings(accessor.invoke(value), out, seen);
      }
    }
  }

  /** The classes reachable from a type: record component types, generic arguments, and the permitted subclasses of a sealed type. */
  private static void reach(Type type, Set<Class<?>> reached) {
    if (type instanceof ParameterizedType parameterized) {
      for (Type argument : parameterized.getActualTypeArguments()) {
        reach(argument, reached);
      }
      reach(parameterized.getRawType(), reached);
      return;
    }
    if (!(type instanceof Class<?> type1) || type1.isPrimitive() || type1.getName().startsWith("java.") || type1.isArray() && !type1.getComponentType().isRecord()) {
      return;
    }
    if (type1.isArray()) {
      reach(type1.getComponentType(), reached);
      return;
    }
    if (!reached.add(type1)) {
      return;
    }
    if (type1.isSealed()) {
      for (Class<?> permitted : type1.getPermittedSubclasses()) {
        reach(permitted, reached);
      }
    }
    if (type1.isRecord()) {
      for (RecordComponent component : type1.getRecordComponents()) {
        reach(component.getGenericType(), reached);
      }
    }
  }

  /** A set of classes ordered by name (a Class is not Comparable). */
  private static final class TreeSetOfClasses extends java.util.TreeSet<Class<?>> {
    private static final long serialVersionUID = 1L;

    TreeSetOfClasses() {
      super(java.util.Comparator.comparing(Class::getName));
    }
  }
}
