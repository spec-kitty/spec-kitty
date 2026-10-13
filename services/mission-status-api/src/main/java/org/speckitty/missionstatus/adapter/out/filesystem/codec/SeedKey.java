package org.speckitty.missionstatus.adapter.out.filesystem.codec;

import java.math.BigDecimal;
import java.math.BigInteger;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.speckitty.missionstatus.domain.model.CodePoints;

/**
 * The two facts the reducer needs about a reconstruction seed, read off the raw row (spec-kitty-events 10.4.4, {@code diary.py}).
 *
 * <p>{@link #isSeed} is {@code _is_reconstruction_seed}: the actor identity ({@code actor_identity_str}: a string verbatim, a structured
 * actor its {@code tool}, else its {@code role}, else empty) starts with {@code migration:}. It reads the raw value because the served
 * {@code Actor} drops a handle that does not fit the contract's shape.
 *
 * <p>{@link #key} is {@code _canonical_key}: {@code json.dumps(event.to_dict(), sort_keys=True, default=str)}, the key by which the
 * canonical-minimum of same-id seeds is chosen. The {@code to_dict} of the decoded event is rebuilt from the raw row, with the
 * normalisation of {@code DoneEvidence} and {@code ReviewResult} ({@code to_dict} drops empty lists and a null {@code feedback_path}).
 * It is built for a seed only.
 */
final class SeedKey {

  private static final String SEED_PREFIX = "migration:";

  private SeedKey() {}

  static boolean isSeed(Object actor) {
    return identity(actor).startsWith(SEED_PREFIX);
  }

  private static String identity(Object actor) {
    if (actor instanceof String text) {
      return text;
    }
    if (actor instanceof Map<?, ?> record) {
      if (record.get("tool") instanceof String tool && !tool.isEmpty()) {
        return tool;
      }
      if (record.get("role") instanceof String role && !role.isEmpty()) {
        return role;
      }
    }
    return "";
  }

  static String key(Map<String, Object> row) {
    Map<String, Object> dict = new LinkedHashMap<>();
    dict.put("event_id", row.get("event_id"));
    Object slug = row.get("mission_slug");
    dict.put("mission_slug", RowClassifier.truthy(slug) ? slug : row.containsKey("feature_slug") ? row.get("feature_slug") : "");
    dict.put("wp_id", row.get("wp_id"));
    dict.put("from_lane", row.get("from_lane"));
    dict.put("to_lane", row.get("to_lane"));
    dict.put("at", row.get("at"));
    dict.put("actor", actor(row.get("actor")));
    dict.put("force", row.get("force"));
    dict.put("execution_mode", row.get("execution_mode"));
    dict.put("reason", row.get("reason"));
    dict.put("review_ref", row.get("review_ref"));
    dict.put("evidence", RowClassifier.truthy(row.get("evidence")) ? evidence((Map<?, ?>) row.get("evidence")) : null);
    dict.put("policy_metadata", row.get("policy_metadata"));
    if (RowClassifier.truthy(row.get("review_result"))) {
      dict.put("review_result", reviewResult((Map<?, ?>) row.get("review_result")));
    }
    if (row.get("mission_id") != null) {
      dict.put("mission_id", row.get("mission_id"));
    }
    StringBuilder out = new StringBuilder();
    dump(dict, out);
    return out.toString();
  }

  private static Object actor(Object value) {
    if (value instanceof Map<?, ?> record) {
      Map<String, Object> decoded = new LinkedHashMap<>();
      for (String field : List.of("role", "profile", "tool", "model")) {
        decoded.put(field, record.get(field));
      }
      return decoded;
    }
    return value;
  }

  private static Map<String, Object> evidence(Map<?, ?> evidence) {
    Map<String, Object> out = new LinkedHashMap<>();
    Map<?, ?> review = (Map<?, ?>) evidence.get("review");
    out.put("review", fields(review, "reviewer", "verdict", "reference"));
    List<Object> repos = elements(evidence.get("repos"));
    if (!repos.isEmpty()) {
      List<Object> normalised = new ArrayList<>();
      for (Object element : repos) {
        Map<?, ?> repo = (Map<?, ?>) element;
        Map<String, Object> entry = fields(repo, "repo", "branch", "commit");
        List<Object> files = elements(repo.get("files_touched"));
        if (!files.isEmpty()) {
          entry.put("files_touched", files);
        }
        normalised.add(entry);
      }
      out.put("repos", normalised);
    }
    List<Object> verification = elements(evidence.get("verification"));
    if (!verification.isEmpty()) {
      List<Object> normalised = new ArrayList<>();
      for (Object element : verification) {
        normalised.add(fields((Map<?, ?>) element, "command", "result", "summary"));
      }
      out.put("verification", normalised);
    }
    return out;
  }

  private static Map<String, Object> reviewResult(Map<?, ?> result) {
    Map<String, Object> out = fields(result, "reviewer", "verdict", "reference");
    if (result.get("feedback_path") != null) {
      out.put("feedback_path", result.get("feedback_path"));
    }
    return out;
  }

  private static Map<String, Object> fields(Map<?, ?> source, String... names) {
    Map<String, Object> out = new LinkedHashMap<>();
    for (String name : names) {
      out.put(name, source.get(name));
    }
    return out;
  }

  /** {@code list(value)} of an absent, list, string or object value, as the decoders iterate it. */
  private static List<Object> elements(Object value) {
    List<Object> out = new ArrayList<>();
    switch (value) {
      case List<?> list -> out.addAll(list);
      case String string -> string.codePoints().forEach(cp -> out.add(new String(Character.toChars(cp))));
      case Map<?, ?> map -> out.addAll(map.keySet());
      case null, default -> {}
    }
    return out;
  }

  // ---- json.dumps(sort_keys=True), default separators, ensure_ascii ----------------------------------------------------------

  @SuppressWarnings("unchecked")
  private static void dump(Object value, StringBuilder out) {
    switch (value) {
      case null -> out.append("null");
      case Boolean flag -> out.append(flag ? "true" : "false");
      case BigInteger integer -> out.append(integer);
      case Double number -> out.append(pyFloat(number));
      case String string -> quote(string, out);
      case List<?> list -> {
        out.append('[');
        for (int i = 0; i < list.size(); i++) {
          if (i > 0) {
            out.append(", ");
          }
          dump(list.get(i), out);
        }
        out.append(']');
      }
      case Map<?, ?> map -> {
        List<String> keys = new ArrayList<>((java.util.Set<String>) map.keySet());
        keys.sort(CodePoints::compare);
        out.append('{');
        for (int i = 0; i < keys.size(); i++) {
          if (i > 0) {
            out.append(", ");
          }
          quote(keys.get(i), out);
          out.append(": ");
          dump(map.get(keys.get(i)), out);
        }
        out.append('}');
      }
      default -> quote(String.valueOf(value), out);
    }
  }

  private static void quote(String text, StringBuilder out) {
    out.append('"');
    for (int i = 0; i < text.length(); i++) {
      char c = text.charAt(i);
      switch (c) {
        case '"' -> out.append("\\\"");
        case '\\' -> out.append("\\\\");
        case '\n' -> out.append("\\n");
        case '\r' -> out.append("\\r");
        case '\t' -> out.append("\\t");
        case '\b' -> out.append("\\b");
        case '\f' -> out.append("\\f");
        default -> {
          if (c >= ' ' && c <= '~') {
            out.append(c);
          } else {
            out.append(String.format("\\u%04x", (int) c));
          }
        }
      }
    }
    out.append('"');
  }

  /** Python's {@code float.__repr__}: the shortest digits, scientific below 1e-4 and from 1e16. */
  static String pyFloat(double number) {
    if (Double.isNaN(number)) {
      return "NaN";
    }
    if (Double.isInfinite(number)) {
      return number > 0 ? "Infinity" : "-Infinity";
    }
    if (number == 0.0) {
      return 1 / number < 0 ? "-0.0" : "0.0";
    }
    BigDecimal decimal = new BigDecimal(Double.toString(Math.abs(number))).stripTrailingZeros();
    String digits = decimal.unscaledValue().toString();
    int exponent = digits.length() - decimal.scale() - 1;
    String sign = number < 0 ? "-" : "";
    if (exponent < -4 || exponent >= 16) {
      String mantissa = digits.length() == 1 ? digits : digits.charAt(0) + "." + digits.substring(1);
      return sign + mantissa + "e" + (exponent < 0 ? "-" : "+") + String.format("%02d", Math.abs(exponent));
    }
    String plain = decimal.toPlainString();
    return sign + (plain.contains(".") ? plain : plain + ".0");
  }
}
