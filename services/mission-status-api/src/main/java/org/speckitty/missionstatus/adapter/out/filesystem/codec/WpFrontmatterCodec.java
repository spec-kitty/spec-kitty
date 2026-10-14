package org.speckitty.missionstatus.adapter.out.filesystem.codec;

import java.io.StringReader;
import java.math.BigInteger;
import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Deque;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.regex.Pattern;
import org.speckitty.missionstatus.domain.model.FrontmatterResult;
import org.speckitty.missionstatus.domain.model.FrontmatterResult.RejectionClass;
import org.speckitty.missionstatus.domain.model.Lane;
import org.speckitty.missionstatus.domain.model.PyText;
import org.speckitty.missionstatus.domain.model.WpMetadata;
import org.yaml.snakeyaml.DumperOptions.ScalarStyle;
import org.yaml.snakeyaml.LoaderOptions;
import org.yaml.snakeyaml.Yaml;
import org.yaml.snakeyaml.constructor.SafeConstructor;
import org.yaml.snakeyaml.error.YAMLException;
import org.yaml.snakeyaml.events.AliasEvent;
import org.yaml.snakeyaml.events.CollectionStartEvent;
import org.yaml.snakeyaml.events.DocumentStartEvent;
import org.yaml.snakeyaml.events.Event;
import org.yaml.snakeyaml.events.MappingEndEvent;
import org.yaml.snakeyaml.events.MappingStartEvent;
import org.yaml.snakeyaml.events.ScalarEvent;
import org.yaml.snakeyaml.events.SequenceEndEvent;
import org.yaml.snakeyaml.events.SequenceStartEvent;

/**
 * The pure decoder of a Work Package file (FR-006, items 3 and 4): bytes to a {@link FrontmatterResult}, as the oracle's
 * {@code FrontmatterManager.read} followed by {@code WPMetadata.model_validate(..., strict=False)} reads a file, or a rejection. No file
 * access; it depends among project packages only on {@code domain}.
 *
 * <p><b>The YAML policy (R-15, S-19, decision recorded in {@code research.md}).</b> The oracle reads YAML 1.2 with ruamel; snakeyaml
 * resolves plain scalars as YAML 1.1 ({@code yes}, {@code on}, octal-looking integers, sexagesimal numbers). This class therefore uses
 * snakeyaml only for what the two dialects share, the syntax: it takes snakeyaml's <em>events</em> and never lets snakeyaml resolve or
 * construct a value. A plain scalar is resolved by {@link Yaml12}, a port of ruamel's YAML 1.2 implicit resolvers. Anything the decoder
 * cannot decode identically is refused with {@link RejectionClass#UNSUPPORTED_YAML}: an anchor, an alias, an explicit tag, a merge key,
 * a directive, a second document, a key that is not a scalar. A refusal skips the file, as the oracle skips a file it cannot read.
 */
public final class WpFrontmatterCodec {

  private static final Set<String> STRING_FIELDS =
      Set.of(
          "title", "base_branch", "created_at", "planning_base_branch", "merge_target_branch", "branch_strategy", "priority",
          "execution_mode", "authoritative_surface", "scope", "task_type", "phases", "assignee", "model", "agent_profile", "role",
          "shell_pid_created_at", LanesCodec.LEGACY_SLUG_KEY, "activity_log", "review_status", "reviewed_by", "approved_by", "reviewer_agent",
          "reviewer_shell_pid", "review_feedback", "review_feedback_file", "subtitle", "description", "estimated_duration", "mission_id",
          "mission_number", "mission_slug", "status", "wp_code", "work_package_title");
  private static final Set<String> STRING_LIST_FIELDS =
      Set.of("dependencies", "requirement_refs", "tracker_refs", "owned_files", "create_intent", "tags");
  private static final Set<String> ANY_LIST_FIELDS = Set.of("subtasks", "history");
  private static final Set<String> ANY_FIELDS = Set.of("agent", "reviewer");
  private static final Set<String> SPECIAL_FIELDS = Set.of("work_package_id", "base_commit", "phase", "shell_pid", "lane");

  private static final Pattern WP_ID = Pattern.compile("WP\\p{Nd}{2,}\\n?");
  private static final Pattern BASE_COMMIT = Pattern.compile("[0-9a-f]{7,40}\\n?");
  private static final String UNKNOWN = "unknown";
  private static final String DELIMITER = "---";
  private static final char BOM = '\ufeff';

  private WpFrontmatterCodec() {}

  /** Decodes the bytes of one Work Package file. */
  public static FrontmatterResult decode(byte[] bytes) {
    StrictUtf8.Decoded decoded = StrictUtf8.decode(bytes);
    if (!(decoded instanceof StrictUtf8.Decoded.Text text)) {
      return rejected(RejectionClass.NOT_UTF8);
    }
    String content = translateNewlines(dropBom(text.text()));
    if (!content.startsWith(DELIMITER)) {
      return rejected(RejectionClass.NO_FRONTMATTER);
    }
    List<String> lines = splitLines(content);
    int closing = closingDelimiter(lines);
    if (closing < 0) {
      return rejected(RejectionClass.NO_CLOSING_DELIMITER);
    }
    String yamlText = String.join("\n", lines.subList(1, closing));
    String body = String.join("\n", lines.subList(closing + 1, lines.size()));
    try {
      Yaml12.Node root = Yaml12.parse(yamlText);
      if (root instanceof Yaml12.Scalar scalar && scalar.type() == Yaml12.Type.NULL) {
        root = new Yaml12.Mapping(List.of());
      }
      if (!(root instanceof Yaml12.Mapping mapping)) {
        return rejected(RejectionClass.NOT_A_MAPPING);
      }
      return new FrontmatterResult.Parsed(validate(mapping), body);
    } catch (Yaml12.Refusal refusal) {
      return rejected(refusal.kind());
    }
  }

  // ---- the file: BOM, newlines, delimiters -------------------------------------------------------------------------------------

  /** {@code utf-8-sig}: one leading byte order mark is dropped, and only one. */
  static String dropBom(String text) {
    return !text.isEmpty() && text.charAt(0) == BOM ? text.substring(1) : text;
  }

  /** Python's universal newlines: {@code \r\n} and a lone {@code \r} become {@code \n}. */
  static String translateNewlines(String text) {
    return text.indexOf('\r') < 0 ? text : text.replace("\r\n", "\n").replace('\r', '\n');
  }

  /** {@code str.split("\n")}: a trailing empty piece is kept. */
  private static List<String> splitLines(String text) {
    List<String> lines = new ArrayList<>();
    int start = 0;
    while (true) {
      int end = text.indexOf('\n', start);
      if (end < 0) {
        lines.add(text.substring(start));
        return lines;
      }
      lines.add(text.substring(start, end));
      start = end + 1;
    }
  }

  /** The first line after the first whose Python-stripped text is {@code ---}, or -1. */
  private static int closingDelimiter(List<String> lines) {
    for (int i = 1; i < lines.size(); i++) {
      if (PyText.strip(lines.get(i)).equals(DELIMITER)) {
        return i;
      }
    }
    return -1;
  }

  private static FrontmatterResult.Rejected rejected(RejectionClass kind) {
    return new FrontmatterResult.Rejected(kind);
  }

  // ---- WPMetadata validation ---------------------------------------------------------------------------------------------------

  /** The oracle's pre-validator and field validators, over the decoded mapping; a failure is a {@link RejectionClass#VALIDATION}. */
  private static WpMetadata validate(Yaml12.Mapping mapping) {
    Map<String, Yaml12.Node> fields = new LinkedHashMap<>();
    for (Yaml12.Entry entry : mapping.entries()) {
      if (!(entry.key() instanceof Yaml12.Scalar key) || key.type() != Yaml12.Type.STR || !known(key.text())) {
        throw new Yaml12.Refusal(RejectionClass.VALIDATION);
      }
      fields.put(key.text(), entry.value());
    }
    if (!fields.containsKey("title") && fields.containsKey("work_package_title")) {
      fields.put("title", fields.get("work_package_title"));
    }
    for (Map.Entry<String, Yaml12.Node> field : fields.entrySet()) {
      checkField(field.getKey(), field.getValue());
    }
    require(fields.get("work_package_id") instanceof Yaml12.Scalar id && id.type() == Yaml12.Type.STR && WP_ID.matcher(id.text()).matches());
    Yaml12.Node title = fields.get("title");
    require(!(title instanceof Yaml12.Scalar t && t.type() == Yaml12.Type.STR && PyText.isBlank(t.text())));
    SubtaskText subtasks = subtasks(fields.get("subtasks"));
    return new WpMetadata(
        text(fields, "work_package_id"),
        text(fields, "title"),
        phase(fields.get("phase")),
        text(fields, "task_type"),
        text(fields, "priority"),
        text(fields, "execution_mode"),
        text(fields, "merge_target_branch"),
        text(fields, "planning_base_branch"),
        text(fields, "role"),
        text(fields, "agent_profile"),
        text(fields, "model"),
        stringList(fields, "dependencies"),
        stringList(fields, "requirement_refs"),
        stringList(fields, "tracker_refs"),
        stringList(fields, "owned_files"),
        subtasks.texts(),
        subtasks.refused());
  }

  private static boolean known(String name) {
    return STRING_FIELDS.contains(name)
        || STRING_LIST_FIELDS.contains(name)
        || ANY_LIST_FIELDS.contains(name)
        || ANY_FIELDS.contains(name)
        || SPECIAL_FIELDS.contains(name);
  }

  private static void checkField(String name, Yaml12.Node value) {
    if (STRING_FIELDS.contains(name)) {
      require(isStringOrNull(value));
    } else if (STRING_LIST_FIELDS.contains(name)) {
      require(coerceList(name, value) != null);
    } else if (ANY_LIST_FIELDS.contains(name)) {
      require(value instanceof Yaml12.Sequence);
    } else if (name.equals("base_commit")) {
      require(isBaseCommit(value));
    } else if (name.equals("shell_pid")) {
      require(isShellPid(value));
    } else if (name.equals("lane")) {
      require(isLane(value));
    } else if (name.equals("phase")) {
      require(value instanceof Yaml12.Scalar && (phase(value) != null || isNull(value)));
    }
  }

  private static void require(boolean valid) {
    if (!valid) {
      throw new Yaml12.Refusal(RejectionClass.VALIDATION);
    }
  }

  private static boolean isNull(Yaml12.Node node) {
    return node instanceof Yaml12.Scalar scalar && scalar.type() == Yaml12.Type.NULL;
  }

  private static boolean isStringOrNull(Yaml12.Node node) {
    return node instanceof Yaml12.Scalar scalar && (scalar.type() == Yaml12.Type.STR || scalar.type() == Yaml12.Type.NULL);
  }

  private static boolean isBaseCommit(Yaml12.Node node) {
    if (isNull(node)) {
      return true;
    }
    return node instanceof Yaml12.Scalar scalar
        && scalar.type() == Yaml12.Type.STR
        && (scalar.text().equals(UNKNOWN) || BASE_COMMIT.matcher(scalar.text()).matches());
  }

  /** {@code coerce_lane}: empty is null, {@code doing} is {@code in_progress}, the two read sentinels and unknown values are refused. */
  private static boolean isLane(Yaml12.Node node) {
    if (isNull(node)) {
      return true;
    }
    if (!(node instanceof Yaml12.Scalar scalar) || scalar.type() != Yaml12.Type.STR) {
      return false;
    }
    String canonical = scalar.text().equals("doing") ? "in_progress" : scalar.text();
    return scalar.text().isEmpty() || Lane.displayLanes().stream().anyMatch(lane -> lane.wire().equals(canonical));
  }

  /** {@code coerce_shell_pid}: null and the empty string are null, anything else goes through Python's {@code int()}. */
  private static boolean isShellPid(Yaml12.Node node) {
    if (!(node instanceof Yaml12.Scalar scalar)) {
      return false;
    }
    return switch (scalar.type()) {
      case NULL, BOOL, INT -> true;
      case STR -> scalar.text().isEmpty() || Yaml12.pyInt(scalar.text()) != null;
      case FLOAT -> !((Double) scalar.value()).isNaN() && !((Double) scalar.value()).isInfinite();
      case TIMESTAMP, UNSUPPORTED -> false;
    };
  }

  /** The list a {@code list[str]} field validates, after the oracle's string coercions; null when the field is invalid. */
  private static List<String> coerceList(String name, Yaml12.Node value) {
    if (value instanceof Yaml12.Scalar scalar && scalar.type() == Yaml12.Type.STR) {
      return switch (name) {
        case "dependencies" -> legacyDependencies(scalar.text());
        case "requirement_refs" -> splitRefs(scalar.text());
        case "tracker_refs" -> splitTrackerRefs(scalar.text());
        default -> null;
      };
    }
    if (!(value instanceof Yaml12.Sequence sequence)) {
      return null;
    }
    List<String> items = new ArrayList<>();
    for (Yaml12.Node item : sequence.items()) {
      if (!(item instanceof Yaml12.Scalar scalar) || scalar.type() != Yaml12.Type.STR) {
        return null;
      }
      items.add(scalar.text());
    }
    return items;
  }

  private static List<String> stringList(Map<String, Yaml12.Node> fields, String name) {
    Yaml12.Node value = fields.get(name);
    return value == null ? List.of() : coerceList(name, value);
  }

  private static String text(Map<String, Yaml12.Node> fields, String name) {
    return fields.get(name) instanceof Yaml12.Scalar scalar && scalar.type() == Yaml12.Type.STR ? scalar.text() : null;
  }

  /** {@code coerce_phase}: {@code str(v)} of a scalar, null for null; null too for a value whose {@code str()} is not reproduced. */
  private static String phase(Yaml12.Node node) {
    return node instanceof Yaml12.Scalar scalar && scalar.type() != Yaml12.Type.NULL ? scalar.pyStr() : null;
  }

  /** {@code coerce_legacy_dependencies} for a string: {@code "[]"} is empty, anything else is split on commas. */
  static List<String> legacyDependencies(String raw) {
    String stripped = PyText.strip(raw);
    return stripped.equals("[]") ? List.of() : splitTrackerRefs(stripped);
  }

  /** {@code [s.strip() for s in value.split(",") if s.strip()]}. */
  static List<String> splitTrackerRefs(String value) {
    List<String> items = new ArrayList<>();
    int start = 0;
    while (start <= value.length()) {
      int end = value.indexOf(',', start);
      String piece = PyText.strip(value.substring(start, end < 0 ? value.length() : end));
      if (!piece.isEmpty()) {
        items.add(piece);
      }
      if (end < 0) {
        break;
      }
      start = end + 1;
    }
    return items;
  }

  /**
   * {@code grammar.tokenize_refs} of a string: split on {@code [,\s]+}, then drop the pieces that are blank. The oracle compiles the
   * pattern with RE2, whose {@code \s} is only the ASCII space, tab, line feed, form feed and carriage return (not a vertical tab, not
   * a no-break space), while the blank test is Python's {@code str.strip}.
   */
  static List<String> splitRefs(String value) {
    List<String> tokens = new ArrayList<>();
    StringBuilder token = new StringBuilder();
    for (int i = 0; i < value.length(); i++) {
      char c = value.charAt(i);
      if (c == ',' || c == ' ' || c == '\t' || c == '\n' || c == '\f' || c == '\r') {
        flush(token, tokens);
      } else {
        token.append(c);
      }
    }
    flush(token, tokens);
    return tokens;
  }

  private static void flush(StringBuilder token, List<String> tokens) {
    if (!token.isEmpty() && !PyText.isBlank(token.toString())) {
      tokens.add(token.toString());
    }
    token.setLength(0);
  }

  private record SubtaskText(List<String> texts, boolean refused) {}

  /** The Python {@code str} of each subtask; an entry whose {@code str} is not reproduced (a mapping, a sequence) refuses the roster (D-97). */
  private static SubtaskText subtasks(Yaml12.Node node) {
    if (!(node instanceof Yaml12.Sequence sequence)) {
      return new SubtaskText(List.of(), false);
    }
    List<String> texts = new ArrayList<>();
    boolean refused = false;
    for (Yaml12.Node item : sequence.items()) {
      String text = item instanceof Yaml12.Scalar scalar ? scalar.pyStr() : null;
      if (text == null) {
        refused = true;
      } else {
        texts.add(text);
      }
    }
    return new SubtaskText(texts, refused);
  }

  // ---- YAML 1.2, the way ruamel reads it ---------------------------------------------------------------------------------------

  /**
   * A YAML 1.2 reader built on snakeyaml's parser events. It yields a small tree whose scalars carry the type ruamel's YAML 1.2
   * resolver gives them (and the value, when the oracle's constructor can build one). Package-private: {@link ReviewCycleCodec} reads
   * its frontmatter the same way.
   */
  static final class Yaml12 {

    /** A refusal or a failure to read; it carries the class of the rejection. */
    static final class Refusal extends RuntimeException {
      private static final long serialVersionUID = 1L;
      private final transient RejectionClass kind;

      Refusal(RejectionClass kind) {
        super(kind.name(), null, false, false);
        this.kind = kind;
      }

      RejectionClass kind() {
        return kind;
      }
    }

    /** What a plain scalar is, to the YAML 1.2 implicit resolvers; a quoted or block scalar is always {@code STR}. */
    enum Type {
      STR,
      NULL,
      BOOL,
      INT,
      FLOAT,
      TIMESTAMP,
      /** The merge and value tags, which the decoder does not construct. */
      UNSUPPORTED
    }

    sealed interface Node permits Scalar, Sequence, Mapping {}

    /** A scalar: its text, its resolved type and the constructed value (Boolean, BigInteger, Double) where there is one. */
    record Scalar(Type type, String text, Object value) implements Node {

      /**
       * Python's {@code str()} of the constructed value, or null where this service does not reproduce it: a float outside the range where
       * Python and Java print alike, and a timestamp other than a plain date.
       */
      String pyStr() {
        return switch (type) {
          case STR, UNSUPPORTED -> text;
          case NULL -> "None";
          case BOOL -> ((Boolean) value) ? "True" : "False";
          case INT -> value.toString();
          case FLOAT -> pyFloat((Double) value);
          case TIMESTAMP -> DATE_ONLY.matcher(text).matches() ? text : null;
        };
      }

      /** The identity of a mapping key, for the duplicate-key check. */
      String keyId() {
        return type + ":" + (type == Type.INT || type == Type.BOOL || type == Type.FLOAT ? value : text);
      }
    }

    record Sequence(List<Node> items) implements Node {}

    record Entry(Node key, Node value) {}

    record Mapping(List<Entry> entries) implements Node {}

    private static final Pattern BOOL = Pattern.compile("true|True|TRUE|false|False|FALSE");
    private static final Pattern FLOAT =
        Pattern.compile(
            "[-+]?(?:[0-9][0-9_]*)\\.[0-9_]*(?:[eE][-+]?[0-9]+)?"
                + "|[-+]?(?:[0-9][0-9_]*)(?:[eE][-+]?[0-9]+)"
                + "|[-+]?\\.[0-9_]+(?:[eE][-+][0-9]+)?"
                + "|[-+]?\\.(?:inf|Inf|INF)"
                + "|\\.(?:nan|NaN|NAN)");
    private static final Pattern INT = Pattern.compile("[-+]?0b[0-1_]+|[-+]?0o?[0-7_]+|[-+]?[0-9_]+|[-+]?0x[0-9a-fA-F_]+");
    private static final Pattern NULL = Pattern.compile("~|null|Null|NULL");
    private static final Pattern TIMESTAMP =
        Pattern.compile(
            "(?<y>[0-9]{4})-(?<mo>[0-9]{2})-(?<d>[0-9]{2})"
                + "|(?<y2>[0-9]{4})-(?<mo2>[0-9]{1,2})-(?<d2>[0-9]{1,2})(?:[Tt]|[ \\t]+)(?<h>[0-9]{1,2}):(?<mi>[0-9]{2}):(?<s>[0-9]{2})"
                + "(?:\\.[0-9]*)?(?:[ \\t]*(?:Z|(?<tzs>[-+])(?<tzh>[0-9]{1,2})(?::(?<tzm>[0-9]{2}))?))?");
    private static final Pattern DATE_ONLY = Pattern.compile("[0-9]{4}-[0-9]{2}-[0-9]{2}");
    /** CPython's {@code sys.int_info.default_max_str_digits}: a decimal int of more digits raises ValueError (3.11+). */
    static final int MAX_INT_STR_DIGITS = 4300;

    private Yaml12() {}

    /** Reads one document; an empty text is a null scalar. */
    static Node parse(String text) {
      if (text.indexOf('\u0085') >= 0 || text.indexOf('\u2028') >= 0 || text.indexOf('\u2029') >= 0) {
        // YAML 1.1 (snakeyaml) folds these three as line breaks; YAML 1.2 (the oracle) keeps them as characters.
        throw new Refusal(RejectionClass.UNSUPPORTED_YAML);
      }
      Deque<List<Node>> stack = new ArrayDeque<>();
      Deque<Boolean> isMapping = new ArrayDeque<>();
      Node root = null;
      int documents = 0;
      try {
        Yaml yaml = new Yaml(new SafeConstructor(new LoaderOptions()));
        for (Event event : yaml.parse(new StringReader(text))) {
          Node finished = null;
          if (event instanceof DocumentStartEvent start) {
            documents++;
            if (documents > 1) {
              throw new Refusal(RejectionClass.YAML_SYNTAX);
            }
            if (start.getVersion() != null || customTagHandles(start.getTags())) {
              throw new Refusal(RejectionClass.UNSUPPORTED_YAML);
            }
          } else if (event instanceof AliasEvent) {
            throw new Refusal(RejectionClass.UNSUPPORTED_YAML);
          } else if (event instanceof ScalarEvent scalar) {
            finished = scalar(scalar);
          } else if (event instanceof MappingStartEvent || event instanceof SequenceStartEvent) {
            refuseProperties((CollectionStartEvent) event);
            stack.push(new ArrayList<>());
            isMapping.push(event instanceof MappingStartEvent);
          } else if (event instanceof MappingEndEvent || event instanceof SequenceEndEvent) {
            List<Node> items = stack.pop();
            finished = isMapping.pop() ? mapping(items) : new Sequence(items);
          }
          if (finished != null) {
            if (stack.isEmpty()) {
              root = finished;
            } else {
              stack.peek().add(finished);
            }
          }
        }
      } catch (YAMLException | IllegalArgumentException syntax) {
        throw new Refusal(RejectionClass.YAML_SYNTAX);
      }
      return root == null ? new Scalar(Type.NULL, "", null) : root;
    }

    /** Whether a document declares a tag handle other than the two the YAML specification predefines. */
    private static boolean customTagHandles(Map<String, String> handles) {
      if (handles == null) {
        return false;
      }
      for (Map.Entry<String, String> handle : handles.entrySet()) {
        boolean predefined =
            (handle.getKey().equals("!") && handle.getValue().equals("!")) || (handle.getKey().equals("!!") && handle.getValue().equals("tag:yaml.org,2002:"));
        if (!predefined) {
          return true;
        }
      }
      return false;
    }

    private static void refuseProperties(CollectionStartEvent start) {
      if (start.getAnchor() != null || start.getTag() != null) {
        throw new Refusal(RejectionClass.UNSUPPORTED_YAML);
      }
    }

    private static Node mapping(List<Node> flat) {
      List<Entry> entries = new ArrayList<>();
      Set<String> seen = new HashSet<>();
      for (int i = 0; i < flat.size(); i += 2) {
        if (!(flat.get(i) instanceof Scalar key) || key.type() == Type.UNSUPPORTED) {
          throw new Refusal(RejectionClass.UNSUPPORTED_YAML);
        }
        if (!seen.add(key.keyId())) {
          throw new Refusal(RejectionClass.DUPLICATE_KEY);
        }
        entries.add(new Entry(key, flat.get(i + 1)));
      }
      return new Mapping(entries);
    }

    private static Scalar scalar(ScalarEvent event) {
      if (event.getAnchor() != null || event.getTag() != null) {
        throw new Refusal(RejectionClass.UNSUPPORTED_YAML);
      }
      if (event.getScalarStyle() != ScalarStyle.PLAIN) {
        return new Scalar(Type.STR, event.getValue(), null);
      }
      return resolve(event.getValue());
    }

    /** {@code repr(float)} where it equals Java's {@code Double.toString} (positional notation, 1e-3 up to 1e7), the infinities and not-a-number. */
    static String pyFloat(double number) {
      if (Double.isNaN(number)) {
        return "nan";
      }
      if (Double.isInfinite(number)) {
        return number > 0 ? "inf" : "-inf";
      }
      double magnitude = Math.abs(number);
      return magnitude == 0 || (magnitude >= 1e-3 && magnitude < 1e7) ? Double.toString(number) : null;
    }

    /** ruamel's YAML 1.2 implicit resolution of a plain scalar, then its constructor; a value the constructor would fail on is refused. */
    static Scalar resolve(String value) {
      if (value.isEmpty()) {
        return new Scalar(Type.NULL, value, null);
      }
      char first = value.charAt(0);
      if ("tTfF".indexOf(first) >= 0 && BOOL.matcher(value).matches()) {
        return new Scalar(Type.BOOL, value, value.startsWith("t") || value.startsWith("T"));
      }
      if ("-+0123456789.".indexOf(first) >= 0 && FLOAT.matcher(value).matches()) {
        return new Scalar(Type.FLOAT, value, floatValue(value));
      }
      if ("-+0123456789".indexOf(first) >= 0 && INT.matcher(value).matches()) {
        return new Scalar(Type.INT, value, intValue(value));
      }
      if (value.equals("<<") || value.equals("=")) {
        return new Scalar(Type.UNSUPPORTED, value, null);
      }
      if ("~nN".indexOf(first) >= 0 && NULL.matcher(value).matches()) {
        return new Scalar(Type.NULL, value, null);
      }
      if (first >= '0' && first <= '9' && TIMESTAMP.matcher(value).matches()) {
        requireTimestamp(value);
        return new Scalar(Type.TIMESTAMP, value, null);
      }
      return new Scalar(Type.STR, value, null);
    }

    private static Double floatValue(String value) {
      String cleaned = value.replace("_", "").toLowerCase(java.util.Locale.ROOT);
      boolean negative = cleaned.startsWith("-");
      String unsigned = cleaned.startsWith("-") || cleaned.startsWith("+") ? cleaned.substring(1) : cleaned;
      if (unsigned.equals(".inf")) {
        return negative ? Double.NEGATIVE_INFINITY : Double.POSITIVE_INFINITY;
      }
      if (unsigned.equals(".nan")) {
        return Double.NaN;
      }
      try {
        return Double.valueOf(cleaned);
      } catch (NumberFormatException failure) {
        throw new Refusal(RejectionClass.UNSUPPORTED_YAML);
      }
    }

    /** ruamel's {@code construct_yaml_int} for YAML 1.2: prefixes {@code 0b 0o 0x}, otherwise decimal even with leading zeros. */
    private static BigInteger intValue(String value) {
      String digits = value.replace("_", "");
      boolean negative = digits.startsWith("-");
      if (negative || digits.startsWith("+")) {
        digits = digits.substring(1);
      }
      int radix = 10;
      if (digits.startsWith("0b") || digits.startsWith("0x") || digits.startsWith("0o")) {
        radix = digits.charAt(1) == 'b' ? 2 : digits.charAt(1) == 'x' ? 16 : 8;
        digits = digits.substring(2);
      }
      if (digits.isEmpty()) {
        throw new Refusal(RejectionClass.UNSUPPORTED_YAML);
      }
      if (radix == 10 && digits.length() > MAX_INT_STR_DIGITS) {
        // ruamel's int() raises ValueError, and the oracle skips the file; the power-of-two bases have no limit.
        throw new Refusal(RejectionClass.UNSUPPORTED_YAML);
      }
      BigInteger magnitude = new BigInteger(digits, radix);
      return negative ? magnitude.negate() : magnitude;
    }

    /** The checks of Python's {@code datetime.date} and {@code datetime.datetime} that ruamel's timestamp constructor runs. */
    private static void requireTimestamp(String value) {
      var matcher = TIMESTAMP.matcher(value);
      if (!matcher.matches()) {
        throw new Refusal(RejectionClass.UNSUPPORTED_YAML);
      }
      boolean dateOnly = matcher.group("y") != null;
      int year = Integer.parseInt(dateOnly ? matcher.group("y") : matcher.group("y2"));
      int month = Integer.parseInt(dateOnly ? matcher.group("mo") : matcher.group("mo2"));
      int day = Integer.parseInt(dateOnly ? matcher.group("d") : matcher.group("d2"));
      boolean valid = year >= 1 && month >= 1 && month <= 12 && day >= 1 && day <= java.time.YearMonth.of(year, month).lengthOfMonth();
      if (valid && !dateOnly) {
        valid = Integer.parseInt(matcher.group("h")) < 24 && Integer.parseInt(matcher.group("mi")) < 60 && Integer.parseInt(matcher.group("s")) < 60;
        if (valid && matcher.group("tzh") != null) {
          int minutes = matcher.group("tzm") == null ? 0 : Integer.parseInt(matcher.group("tzm"));
          valid = Integer.parseInt(matcher.group("tzh")) * 60 + minutes < 24 * 60;
        }
      }
      if (!valid) {
        throw new Refusal(RejectionClass.UNSUPPORTED_YAML);
      }
    }

    /** Python's {@code int(str)}: surrounding whitespace, a sign, Unicode decimal digits, single underscores between digits; null if it raises. */
    static BigInteger pyInt(String text) {
      String stripped = PyText.strip(text);
      // A scan, not a regex: a group loop recurses once per underscore group and overflows the stack on a few KB.
      StringBuilder ascii = new StringBuilder();
      int index = 0;
      if (!stripped.isEmpty() && (stripped.charAt(0) == '+' || stripped.charAt(0) == '-')) {
        ascii.append(stripped.charAt(0));
        index = 1;
      }
      int digits = 0;
      boolean afterDigit = false;
      while (index < stripped.length()) {
        int c = stripped.codePointAt(index);
        index += Character.charCount(c);
        if (c == '_') {
          if (!afterDigit) {
            return null;
          }
          afterDigit = false;
        } else if (Character.getType(c) == Character.DECIMAL_DIGIT_NUMBER) {
          ascii.append((char) ('0' + Character.digit(c, 10)));
          digits++;
          afterDigit = true;
        } else {
          return null;
        }
      }
      if (!afterDigit || digits > MAX_INT_STR_DIGITS) {
        return null;
      }
      return new BigInteger(ascii.toString());
    }
  }
}
