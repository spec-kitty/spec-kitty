package org.speckitty.missionstatus.adapter.out.filesystem.codec;

import java.math.BigInteger;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.regex.Pattern;
import org.speckitty.missionstatus.domain.model.Actor;
import org.speckitty.missionstatus.domain.model.HistoryRow;
import org.speckitty.missionstatus.domain.model.Lane;
import org.speckitty.missionstatus.domain.model.LifecycleEvent;
import org.speckitty.missionstatus.domain.model.LineKind;
import org.speckitty.missionstatus.domain.model.MalformedReason;
import org.speckitty.missionstatus.domain.model.PyText;
import org.speckitty.missionstatus.domain.model.ReviewOverrideRecord;
import org.speckitty.missionstatus.domain.model.ReviewResultRecord;
import org.speckitty.missionstatus.domain.model.StatusEvent;

/**
 * Which kind of row a parsed JSON object is, in the order the Python readers decide it
 * ({@code specify_cli.status.store._partition_event_stream_from_text}, which calls {@code spec_kitty_events.diary}'s
 * {@code StatusEvent.from_dict} and {@code InnerStateChanged.from_dict}, and {@code parse_diary}):
 *
 * <ol>
 *   <li>a {@code kind} that is not null: {@code "annotation"} is an annotation row (validated like {@code InnerStateChanged.from_dict});
 *       any other value, of any type, is an unknown kind and malformed;
 *   <li>a non-lane row is skipped in place: an {@code event_name} starting {@code retrospective.}, a {@code type} of one of the three
 *       retrospective lifecycle events, or any row that has an {@code event_type} key. Of those, a row whose {@code event_type} is one of
 *       the seven forwarded types, with a text {@code event_id} and {@code timestamp}, is a lifecycle row; the rest are ignored;
 *   <li>everything else must decode as a lane transition ({@code StatusEvent.from_dict}); a missing key, an unknown lane or a bad
 *       nested value makes the row malformed. An object that is no row at all (for example {@code {}}) is therefore malformed, not ignored.
 * </ol>
 *
 * A JSON value that is not an object is {@link MalformedReason#NOT_OBJECT}. An object that is no usable row (the third case above, and an
 * unknown {@code kind}) is {@link MalformedReason#UNUSABLE_ROW}: Python's {@code poll_once} raises only on invalid JSON and on a non-object
 * and hands every other object on, so a stream skips such a row and a request route refuses it like any malformed line. Nothing here
 * keeps text of the row in a diagnostic.
 */
final class RowClassifier {

  private static final LineKind.Malformed UNUSABLE_ROW = new LineKind.Malformed(MalformedReason.UNUSABLE_ROW);
  private static final String ANNOTATION_KIND = "annotation";
  private static final Pattern ULID = Pattern.compile("^[0-9A-HJKMNP-TV-Z]{26}$", Pattern.UNIX_LINES);
  private static final Pattern PYTHON_INT = Pattern.compile("^[+-]?\\d+(?:_\\d+)*$", Pattern.UNICODE_CHARACTER_CLASS);
  private static final Set<String> RETROSPECTIVE_TYPES = Set.of("RetrospectiveCaptured", "RetrospectiveCaptureFailed", "RetrospectiveSkipped");
  private static final List<String> STATUS_REQUIRED = List.of("event_id", "wp_id", "from_lane", "to_lane", "at", "actor", "force", "execution_mode");
  private static final Set<String> ACTOR_FIELDS = Set.of("role", "profile", "tool", "model");
  /** The replace slots of {@code _REPLACE_SLOTS} that are served (the two shell slots are not). */
  private static final List<String> SERVED_REPLACE_SLOTS = List.of("agent", "assignee", "role", "agent_profile", "agent_profile_version", "model", "provider");

  private RowClassifier() {}

  /** The kind of a parsed document: not an object, or the kind of the row. */
  static LineKind classify(Object document) {
    if (!(document instanceof Map<?, ?> map)) {
      return new LineKind.Malformed(MalformedReason.NOT_OBJECT);
    }
    @SuppressWarnings("unchecked")
    Map<String, Object> row = (Map<String, Object>) map;
    Object kind = row.get("kind");
    if (kind != null) {
      return ANNOTATION_KIND.equals(kind) ? annotation(row) : UNUSABLE_ROW;
    }
    if (isNonLane(row)) {
      return lifecycleOrIgnored(row);
    }
    return status(row);
  }

  // ---- row facts independent of the classification (D-98, history) -----------------------------------------------------------

  /** The row's own {@code event_type} when it is a string: the oracle's {@code _lifecycle_types} counts it whatever else the row lacks. */
  static String eventType(Object document) {
    return document instanceof Map<?, ?> row && row.get("event_type") instanceof String type ? type : null;
  }

  /**
   * The oracle's {@code history_entries} reading of a row: a row with a {@code to_lane} key and a string {@code wp_id} (the oracle compares
   * the {@code wp_id} for equality with a string). Nothing else about the row is checked, so a non-lane row that carries those keys is read.
   * Each member is the stored text (a non-text value its Python {@code str()} when Java reproduces it, else null); the lane texts are not
   * validated here, the route mapper shows or refuses them.
   */
  static HistoryRow historyRow(Object document, long lineNumber) {
    if (!(document instanceof Map<?, ?> row) || !row.containsKey("to_lane") || !(row.get("wp_id") instanceof String wpId)) {
      return null;
    }
    String verdict = row.get("review_result") instanceof Map<?, ?> result ? storedText(result.get("verdict")) : null;
    String reference = row.get("review_result") instanceof Map<?, ?> result && result.get("reference") instanceof String text ? text : null;
    return new HistoryRow(
        wpId,
        storedText(row.get("event_id")),
        storedText(row.get("at")),
        storedText(row.get("from_lane")),
        storedText(row.get("to_lane")),
        actor(row.get("actor")),
        Boolean.TRUE.equals(row.get("force")),
        storedText(row.get("reason")),
        verdict,
        reference,
        lineNumber);
  }

  /** The stored value as text: null stays null (the oracle shows none), a string is itself, the rest its Python {@code str()} or null. */
  private static String storedText(Object value) {
    return value == null ? null : pythonStr(value);
  }

  // ---- non-lane rows --------------------------------------------------------------------------------------------------------

  private static boolean isNonLane(Map<String, Object> row) {
    return (row.get("event_name") instanceof String name && name.startsWith("retrospective."))
        || (row.get("type") instanceof String type && RETROSPECTIVE_TYPES.contains(type))
        || row.containsKey("event_type");
  }

  private static LineKind lifecycleOrIgnored(Map<String, Object> row) {
    if (row.get("event_type") instanceof String type
        && LifecycleEvent.isForwarded(type)
        && row.get("event_id") instanceof String eventId
        && row.get("timestamp") instanceof String timestamp) {
      return new LineKind.Lifecycle(new LifecycleEvent(eventId, type, timestamp));
    }
    return new LineKind.Ignored();
  }

  // ---- lane transitions -----------------------------------------------------------------------------------------------------

  private static LineKind status(Map<String, Object> row) {
    for (String key : STATUS_REQUIRED) {
      if (!row.containsKey(key)) {
        return UNUSABLE_ROW;
      }
    }
    if (!(row.get("event_id") instanceof String eventId) || !(row.get("at") instanceof String at) || !(row.get("wp_id") instanceof String wpId)) {
      return UNUSABLE_ROW;
    }
    Lane from = lane(row.get("from_lane"));
    Lane to = lane(row.get("to_lane"));
    if (from == null || to == null || !validActor(row.get("actor")) || !validEvidence(row.get("evidence")) || !validReviewResult(row.get("review_result"))) {
      return UNUSABLE_ROW;
    }
    String seedKey = SeedKey.isSeed(row.get("actor")) ? SeedKey.key(row) : null;
    return new LineKind.Status(
        new StatusEvent(
            eventId,
            at,
            wpId,
            from,
            to,
            truthy(row.get("force")),
            presence(row.get("review_ref")),
            text(row.get("reason")),
            text(row.get("reason_source")),
            claimAgent(row.get("policy_metadata")),
            actor(row.get("actor")),
            seedKey,
            claimAgentSlot(row.get("policy_metadata")),
            actorIdentity(row.get("actor")),
            reviewResult(row.get("review_result"))));
  }

  /**
   * {@code decode_actor} and the contract's {@code Actor}: a string is the tool, a validated record is copied field by field (the model
   * is dropped), anything else is no actor. Python {@code str()}-coerces a number, a boolean or a null into text; the contract reads
   * such a value as no actor, and so does this (a null actor must not become a tool called "None").
   */
  private static Actor actor(Object value) {
    return switch (value) {
      case String text -> Actor.ofText(text);
      case Map<?, ?> record -> new Actor(text(record.get("tool")), text(record.get("role")), text(record.get("profile")));
      case null, default -> Actor.NONE;
    };
  }

  private static Lane lane(Object value) {
    if (!(value instanceof String wire)) {
      return null;
    }
    try {
      return Lane.fromWire(wire);
    } catch (IllegalArgumentException unknown) {
      return null;
    }
  }

  private static String text(Object value) {
    return value instanceof String string ? string : null;
  }

  /** Python only asks {@code review_ref is not None}: a non-text value keeps its presence. */
  private static String presence(Object value) {
    if (value == null) {
      return null;
    }
    return value instanceof String string ? string : "";
  }

  private static String claimAgent(Object policyMetadata) {
    return policyMetadata instanceof Map<?, ?> metadata && metadata.get("agent") instanceof String agent ? agent : null;
  }

  /** {@code _claim_sidecar_writes}: the {@code agent} slot is written only when {@code policy_metadata["agent"]} is truthy, stored as it is. */
  private static StatusEvent.SlotText claimAgentSlot(Object policyMetadata) {
    if (!(policyMetadata instanceof Map<?, ?> metadata) || !truthy(metadata.get("agent"))) {
      return null;
    }
    return slotText(metadata.get("agent"));
  }

  /** A written scalar slot as {@code str()} shows it; a float, list or object has a Python text Java does not reproduce. */
  private static StatusEvent.SlotText slotText(Object value) {
    String text = pythonStr(value);
    return text == null ? StatusEvent.SlotText.UNSHOWN : StatusEvent.SlotText.of(text);
  }

  /**
   * {@code actor_identity_str(decode_actor(value))}: a string verbatim, a structured actor its {@code tool}, else its {@code role}, else the
   * empty text; a null, a boolean or an integer its {@code str()}. A float or a list has a Python text Java does not reproduce, and the
   * handle shape reads the text of a list as no handle, so those give the empty text (a float that would fit a handle is a recorded divergence).
   */
  static String actorIdentity(Object value) {
    return switch (value) {
      case String text -> text;
      case Map<?, ?> record -> record.get("tool") instanceof String tool && !tool.isEmpty() ? tool : record.get("role") instanceof String role ? role : "";
      case null, default -> {
        String text = pythonStr(value);
        yield text == null ? "" : text;
      }
    };
  }

  /** {@code ReviewResult.from_dict}, applied only to a truthy value; the verdict stays unread unless it is text, as the contract allows nothing else. */
  private static ReviewResultRecord reviewResult(Object value) {
    if (!truthy(value) || !(value instanceof Map<?, ?> map)) {
      return null;
    }
    return new ReviewResultRecord(text(map.get("reviewer")), text(map.get("verdict")), map.get("reference") == null ? null : pythonStr(map.get("reference")));
  }

  // ---- annotations ----------------------------------------------------------------------------------------------------------

  private static LineKind annotation(Map<String, Object> row) {
    for (String key : List.of("event_id", "delta", "wp_id", "at", "actor")) {
      if (!row.containsKey(key)) {
        return UNUSABLE_ROW;
      }
    }
    if (!(row.get("event_id") instanceof String eventId) || !ULID.matcher(eventId).find()) {
      return UNUSABLE_ROW;
    }
    String wpId = pythonStr(row.get("wp_id"));
    String at = pythonStr(row.get("at"));
    if (wpId == null || at == null || !validActor(row.get("actor")) || !validDelta(row.get("delta"))) {
      return UNUSABLE_ROW;
    }
    LineKind.Annotation.Delta delta = delta((Map<?, ?>) row.get("delta"));
    return delta == null ? UNUSABLE_ROW : new LineKind.Annotation(wpId, at, eventId, actorIdentity(row.get("actor")), delta);
  }

  /**
   * The served part of {@code WPInnerStateDelta.from_dict} (the delta is already validated). Null when a {@code review} member has a Python
   * text Java does not reproduce (a float, a list or an object): the row is then unusable, as a float {@code wp_id} already is.
   */
  private static LineKind.Annotation.Delta delta(Map<?, ?> raw) {
    Map<String, StatusEvent.SlotText> replace = new LinkedHashMap<>();
    for (String slot : SERVED_REPLACE_SLOTS) {
      Object value = raw.get(slot);
      if (value != null && !"".equals(value)) {
        replace.put(slot, slotText(value));
      }
    }
    Map<String, Lane> subtasks = null;
    if (raw.get("subtasks") instanceof Map<?, ?> stored) {
      subtasks = new LinkedHashMap<>();
      for (Map.Entry<?, ?> entry : stored.entrySet()) {
        subtasks.put((String) entry.getKey(), lane(entry.getValue()));
      }
    }
    ReviewOverrideRecord review = null;
    if (raw.get("review") instanceof Map<?, ?> stored) {
      String[] fields = new String[4];
      String[] keys = {"at", "actor", "wp_id", "reason"};
      for (int i = 0; i < keys.length; i++) {
        fields[i] = pythonStr(stored.get(keys[i]));
        if (fields[i] == null) {
          return null;
        }
      }
      review = new ReviewOverrideRecord(fields[0], fields[1], fields[2], fields[3]);
    }
    return new LineKind.Annotation.Delta(truthy(raw.get("release_runtime_claim")), replace, subtasks, review);
  }

  /** {@code str(value)} for the values whose Python text is simple; null for a float, list or object (their repr is not reproduced). */
  private static String pythonStr(Object value) {
    return switch (value) {
      case null -> "None";
      case String string -> string;
      case BigInteger integer -> integer.toString();
      case Boolean flag -> flag ? "True" : "False";
      default -> null;
    };
  }

  private static boolean validDelta(Object delta) {
    if (!(delta instanceof Map<?, ?> map)) {
      return false;
    }
    return validSubtasks(map.get("subtasks"))
        && validOverride(map.get("review"))
        && validPythonInt(map.get("shell_pid"))
        && validList(map.get("tracker_refs"))
        && validList(map.get("tracker_refs_replace"));
  }

  private static boolean validSubtasks(Object subtasks) {
    if (subtasks == null) {
      return true;
    }
    if (!(subtasks instanceof Map<?, ?> map)) {
      return false;
    }
    return map.values().stream().allMatch(value -> lane(value) != null);
  }

  private static boolean validOverride(Object review) {
    if (review == null) {
      return true;
    }
    return review instanceof Map<?, ?> map && hasKeys(map, "at", "actor", "wp_id", "reason");
  }

  /** {@code int(value)} must not raise (Python's {@code ValueError}, {@code TypeError}, and the {@code OverflowError} of infinity). */
  private static boolean validPythonInt(Object value) {
    return switch (value) {
      case null -> true;
      case Boolean flag -> true;
      case BigInteger integer -> true;
      case Double number -> !number.isNaN() && !number.isInfinite();
      case String string -> PYTHON_INT.matcher(PyText.strip(string)).matches();
      default -> false;
    };
  }

  /** {@code list(value)} must not raise: a list, a string and an object can be iterated. */
  private static boolean validList(Object value) {
    return value == null || value instanceof List<?> || value instanceof String || value instanceof Map<?, ?>;
  }

  // ---- shared validators ----------------------------------------------------------------------------------------------------

  /** {@code decode_actor}: a structured binding must have exactly four keys with text or null values; any other value is str()-coerced. */
  private static boolean validActor(Object actor) {
    if (!(actor instanceof Map<?, ?> map)) {
      return true;
    }
    if (!map.keySet().equals(ACTOR_FIELDS)) {
      return false;
    }
    return map.values().stream().allMatch(value -> value == null || value instanceof String);
  }

  /** {@code DoneEvidence.from_dict}, applied only to a truthy value. */
  private static boolean validEvidence(Object evidence) {
    if (!truthy(evidence)) {
      return true;
    }
    if (!(evidence instanceof Map<?, ?> map) || !(map.get("review") instanceof Map<?, ?> review) || !hasKeys(review, "reviewer", "verdict", "reference")) {
      return false;
    }
    return validElements(map, "repos", "repo", "branch", "commit") && validElements(map, "verification", "command", "result", "summary");
  }

  /**
   * {@code [Item.from_dict(x) for x in data.get(key, [])]}: absent is an empty list; a list is checked element by element; an empty
   * object or string iterates nothing; anything else raises.
   */
  private static boolean validElements(Map<?, ?> evidence, String key, String... required) {
    if (!evidence.containsKey(key)) {
      return true;
    }
    return switch (evidence.get(key)) {
      case List<?> list -> list.stream().allMatch(element -> element instanceof Map<?, ?> map && hasKeys(map, required));
      case Map<?, ?> map -> map.isEmpty();
      case String string -> string.isEmpty();
      case null, default -> false;
    };
  }

  /** {@code ReviewResult.from_dict}, applied only to a truthy value. */
  private static boolean validReviewResult(Object reviewResult) {
    return !truthy(reviewResult) || (reviewResult instanceof Map<?, ?> map && hasKeys(map, "reviewer", "verdict", "reference"));
  }

  private static boolean hasKeys(Map<?, ?> map, String... keys) {
    for (String key : keys) {
      if (!map.containsKey(key)) {
        return false;
      }
    }
    return true;
  }

  /** Python truthiness of a parsed JSON value. */
  static boolean truthy(Object value) {
    return switch (value) {
      case null -> false;
      case Boolean flag -> flag;
      case BigInteger integer -> integer.signum() != 0;
      case Double number -> number != 0.0;
      case String string -> !string.isEmpty();
      case List<?> list -> !list.isEmpty();
      case Map<?, ?> map -> !map.isEmpty();
      default -> true;
    };
  }
}
