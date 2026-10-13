package org.speckitty.missionstatus.testsupport;

import java.nio.ByteBuffer;
import java.nio.charset.CharacterCodingException;
import java.nio.charset.CodingErrorAction;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.TreeSet;

/**
 * The one comparator of the golden suite, shared by the filesystem golden run and the native smoke test (NFR-005, AC-8a, AC-15b,
 * post-analyze ruling ANL-003). It is independent of the production mapper: it has its own small JSON reader and writer.
 *
 * <p>The comparison is on RAW bytes. {@link #assertBodyEqualsGolden} compares the body exactly as received with the golden file's bytes
 * (the golden is the canonical form: sorted keys, {@code ,} and {@code :} separators, UTF-8 without ASCII escaping, one trailing
 * newline, written by Python). A body that is equal as a document but not as bytes FAILS. The parsed tree is built only AFTER a byte
 * mismatch, to name the first differing member in the failure message; it decides nothing.
 */
public final class CanonicalJson {

  /** The comparison ignore-list: one named constant, and empty. Nothing is excluded from a comparison. */
  public static final List<String> IGNORED_MEMBERS = List.of();

  /** A JSON number kept as the text it was written with, so a fractional value renders exactly as Python wrote it. */
  public record Num(String text) {}

  private CanonicalJson() {}

  // ---- the comparison --------------------------------------------------------------------------------------------------------

  /**
   * Requires the two byte arrays to be identical. On a mismatch, throws an {@link AssertionError} that says which member differs (when
   * both bodies are JSON) or that the bytes differ although the documents are equal.
   */
  public static void assertBodyEqualsGolden(byte[] actualRawBody, byte[] goldenBytes) {
    if (Arrays.equals(actualRawBody, goldenBytes)) {
      return;
    }
    throw new AssertionError(describeMismatch(actualRawBody, goldenBytes));
  }

  /** The failure message of a byte mismatch. Parsing happens here and nowhere else. */
  static String describeMismatch(byte[] actual, byte[] golden) {
    Object actualTree;
    Object goldenTree;
    try {
      actualTree = parse(actual);
    } catch (IllegalArgumentException notJson) {
      return "the actual body is not JSON (" + notJson.getMessage() + "); " + sizes(actual, golden);
    }
    try {
      goldenTree = parse(golden);
    } catch (IllegalArgumentException notJson) {
      return "the golden is not JSON (" + notJson.getMessage() + "); " + sizes(actual, golden);
    }
    String difference = firstDifference("", null, actualTree, goldenTree);
    if (difference == null) {
      return "the documents are equal but the bytes differ (key order, whitespace, escapes or the trailing newline); " + sizes(actual, golden)
          + "; first differing byte at " + firstByteDifference(actual, golden);
    }
    return difference + "; " + sizes(actual, golden);
  }

  private static String sizes(byte[] actual, byte[] golden) {
    return "actual " + actual.length + " bytes, golden " + golden.length + " bytes";
  }

  private static int firstByteDifference(byte[] a, byte[] b) {
    int limit = Math.min(a.length, b.length);
    for (int i = 0; i < limit; i++) {
      if (a[i] != b[i]) {
        return i;
      }
    }
    return limit;
  }

  /** The first difference between two trees, as text naming the path and the member, or null when the trees are equal. */
  static String firstDifference(String path, String member, Object actual, Object golden) {
    if (actual instanceof Map<?, ?> actualMap && golden instanceof Map<?, ?> goldenMap) {
      for (Object key : new TreeSet<>(goldenMap.keySet().stream().map(Object::toString).toList())) {
        String name = key.toString();
        String child = path.isEmpty() ? name : path + "." + name;
        if (!actualMap.containsKey(name)) {
          return "difference at " + child + " (member " + name + "): missing in the actual body";
        }
        String nested = firstDifference(child, name, actualMap.get(name), goldenMap.get(name));
        if (nested != null) {
          return nested;
        }
      }
      for (Object key : new TreeSet<>(actualMap.keySet().stream().map(Object::toString).toList())) {
        if (!goldenMap.containsKey(key.toString())) {
          String name = key.toString();
          return "difference at " + (path.isEmpty() ? name : path + "." + name) + " (member " + name + "): extra in the actual body";
        }
      }
      return null;
    }
    if (actual instanceof List<?> actualList && golden instanceof List<?> goldenList) {
      if (actualList.size() != goldenList.size()) {
        return "difference at " + path + " (member " + member + "): " + actualList.size() + " elements, golden " + goldenList.size();
      }
      for (int i = 0; i < actualList.size(); i++) {
        String nested = firstDifference(path + "[" + i + "]", member, actualList.get(i), goldenList.get(i));
        if (nested != null) {
          return nested;
        }
      }
      return null;
    }
    if (java.util.Objects.equals(actual, golden)) {
      return null;
    }
    return "difference at " + (path.isEmpty() ? "(root)" : path) + " (member " + member + "): actual " + show(actual) + ", golden " + show(golden);
  }

  private static String show(Object value) {
    return value instanceof Num number ? number.text() : value instanceof String text ? "\"" + text + "\"" : String.valueOf(value);
  }

  // ---- the writer ------------------------------------------------------------------------------------------------------------

  /** The canonical bytes of a tree (maps, lists, strings, {@link Num}, booleans, null): the compact form plus one newline. */
  public static byte[] toBytes(Object tree) {
    StringBuilder out = new StringBuilder();
    write(tree, out);
    out.append('\n');
    return out.toString().getBytes(StandardCharsets.UTF_8);
  }

  private static void write(Object value, StringBuilder out) {
    switch (value) {
      case null -> out.append("null");
      case Boolean flag -> out.append(flag ? "true" : "false");
      case Num number -> out.append(number.text());
      case Number number -> out.append(number);
      case String text -> writeString(text, out);
      case Map<?, ?> map -> {
        List<String> keys = new ArrayList<>(map.keySet().stream().map(Object::toString).toList());
        keys.sort(CanonicalJson::compareByCodePoint);
        out.append('{');
        boolean first = true;
        for (String key : keys) {
          if (!first) {
            out.append(',');
          }
          first = false;
          writeString(key, out);
          out.append(':');
          write(map.get(key), out);
        }
        out.append('}');
      }
      case List<?> list -> {
        out.append('[');
        for (int i = 0; i < list.size(); i++) {
          if (i > 0) {
            out.append(',');
          }
          write(list.get(i), out);
        }
        out.append(']');
      }
      default -> throw new IllegalArgumentException("not a JSON value: " + value.getClass());
    }
  }

  /** Python sorts keys by code point; Java's {@code compareTo} sorts by UTF-16 unit, which differs for supplementary characters. */
  private static int compareByCodePoint(String a, String b) {
    int i = 0;
    int j = 0;
    while (i < a.length() && j < b.length()) {
      int x = a.codePointAt(i);
      int y = b.codePointAt(j);
      if (x != y) {
        return Integer.compare(x, y);
      }
      i += Character.charCount(x);
      j += Character.charCount(y);
    }
    return Integer.compare(a.length() - i, b.length() - j);
  }

  /** {@code json.dumps(..., ensure_ascii=False)}: quote, backslash and the C0 controls are escaped, everything else is written as is. */
  private static void writeString(String text, StringBuilder out) {
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
          if (c < 0x20) {
            out.append(String.format("\\u%04x", (int) c));
          } else {
            out.append(c);
          }
        }
      }
    }
    out.append('"');
  }

  // ---- the reader ------------------------------------------------------------------------------------------------------------

  /** Parses a document: objects keep their member order, numbers keep their text. Throws {@link IllegalArgumentException} when it is not JSON. */
  public static Object parse(byte[] bytes) {
    String text;
    try {
      text = StandardCharsets.UTF_8.newDecoder().onMalformedInput(CodingErrorAction.REPORT).onUnmappableCharacter(CodingErrorAction.REPORT).decode(ByteBuffer.wrap(bytes)).toString();
    } catch (CharacterCodingException notUtf8) {
      throw new IllegalArgumentException("not UTF-8", notUtf8);
    }
    Reader reader = new Reader(text);
    Object value = reader.value();
    reader.skipWhitespace();
    if (!reader.atEnd()) {
      throw new IllegalArgumentException("trailing content at " + reader.position());
    }
    return value;
  }

  private static final class Reader {
    private final String text;
    private int index;

    Reader(String text) {
      this.text = text;
    }

    int position() {
      return index;
    }

    boolean atEnd() {
      return index >= text.length();
    }

    void skipWhitespace() {
      while (index < text.length() && " \t\n\r".indexOf(text.charAt(index)) >= 0) {
        index++;
      }
    }

    Object value() {
      skipWhitespace();
      if (atEnd()) {
        throw new IllegalArgumentException("unexpected end");
      }
      char c = text.charAt(index);
      return switch (c) {
        case '{' -> object();
        case '[' -> array();
        case '"' -> string();
        case 't' -> literal("true", Boolean.TRUE);
        case 'f' -> literal("false", Boolean.FALSE);
        case 'n' -> literal("null", null);
        default -> number();
      };
    }

    private Object literal(String word, Object result) {
      if (!text.startsWith(word, index)) {
        throw new IllegalArgumentException("bad literal at " + index);
      }
      index += word.length();
      return result;
    }

    private Object number() {
      int start = index;
      while (index < text.length() && "+-0123456789.eE".indexOf(text.charAt(index)) >= 0) {
        index++;
      }
      if (start == index) {
        throw new IllegalArgumentException("unexpected character at " + index);
      }
      return new Num(text.substring(start, index));
    }

    private Map<String, Object> object() {
      Map<String, Object> members = new LinkedHashMap<>();
      index++;
      skipWhitespace();
      if (peek() == '}') {
        index++;
        return members;
      }
      while (true) {
        skipWhitespace();
        if (peek() != '"') {
          throw new IllegalArgumentException("member name expected at " + index);
        }
        String name = string();
        skipWhitespace();
        expect(':');
        members.put(name, value());
        skipWhitespace();
        if (peek() == ',') {
          index++;
        } else {
          expect('}');
          return members;
        }
      }
    }

    private List<Object> array() {
      List<Object> elements = new ArrayList<>();
      index++;
      skipWhitespace();
      if (peek() == ']') {
        index++;
        return elements;
      }
      while (true) {
        elements.add(value());
        skipWhitespace();
        if (peek() == ',') {
          index++;
        } else {
          expect(']');
          return elements;
        }
      }
    }

    private String string() {
      StringBuilder out = new StringBuilder();
      index++;
      while (true) {
        if (atEnd()) {
          throw new IllegalArgumentException("unterminated string");
        }
        char c = text.charAt(index++);
        if (c == '"') {
          return out.toString();
        }
        if (c != '\\') {
          out.append(c);
          continue;
        }
        if (atEnd()) {
          throw new IllegalArgumentException("unterminated escape");
        }
        char escape = text.charAt(index++);
        switch (escape) {
          case '"', '\\', '/' -> out.append(escape);
          case 'n' -> out.append('\n');
          case 'r' -> out.append('\r');
          case 't' -> out.append('\t');
          case 'b' -> out.append('\b');
          case 'f' -> out.append('\f');
          case 'u' -> {
            if (index + 4 > text.length()) {
              throw new IllegalArgumentException("short unicode escape");
            }
            out.append((char) Integer.parseInt(text.substring(index, index + 4), 16));
            index += 4;
          }
          default -> throw new IllegalArgumentException("bad escape at " + index);
        }
      }
    }

    private char peek() {
      if (atEnd()) {
        throw new IllegalArgumentException("unexpected end");
      }
      return text.charAt(index);
    }

    private void expect(char c) {
      if (peek() != c) {
        throw new IllegalArgumentException("'" + c + "' expected at " + index);
      }
      index++;
    }
  }
}
