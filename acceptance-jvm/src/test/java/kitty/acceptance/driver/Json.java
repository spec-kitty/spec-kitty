package kitty.acceptance.driver;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * Minimal, dependency-free JSON reader for {@code --json} CLI output.
 *
 * <p>The acceptance harness stays black-box and self-contained (constraint C-001), so it does not
 * pull a JSON library onto the classpath. This parser covers the JSON grammar the CLI emits:
 * objects, arrays, strings (with escapes), numbers, booleans and {@code null}. It is deliberately
 * strict — malformed input or trailing content raises {@link JsonParseException}. Numbers are
 * returned as {@link Double} (the driver only needs structural access, not exact numerics).
 */
public final class Json {

    private final String src;
    private int pos;

    private Json(String src) {
        this.src = src;
    }

    /** Parse {@code text} into a tree of {@code Map}/{@code List}/{@code String}/{@code Double}/{@code Boolean}/{@code null}. */
    public static Object parse(String text) {
        Json parser = new Json(text);
        parser.skipWhitespace();
        Object value = parser.readValue();
        parser.skipWhitespace();
        if (parser.pos != parser.src.length()) {
            throw new JsonParseException("Unexpected trailing content at index " + parser.pos);
        }
        return value;
    }

    private Object readValue() {
        char c = peek();
        return switch (c) {
            case '{' -> readObject();
            case '[' -> readArray();
            case '"' -> readString();
            case 't', 'f' -> readBoolean();
            case 'n' -> readNull();
            default -> readNumber();
        };
    }

    private Map<String, Object> readObject() {
        expect('{');
        Map<String, Object> out = new LinkedHashMap<>();
        skipWhitespace();
        if (peek() == '}') {
            pos++;
            return out;
        }
        while (true) {
            skipWhitespace();
            String key = readString();
            skipWhitespace();
            expect(':');
            skipWhitespace();
            out.put(key, readValue());
            skipWhitespace();
            char c = next();
            if (c == '}') {
                return out;
            }
            if (c != ',') {
                throw new JsonParseException("Expected ',' or '}' at index " + (pos - 1));
            }
        }
    }

    private List<Object> readArray() {
        expect('[');
        List<Object> out = new ArrayList<>();
        skipWhitespace();
        if (peek() == ']') {
            pos++;
            return out;
        }
        while (true) {
            skipWhitespace();
            out.add(readValue());
            skipWhitespace();
            char c = next();
            if (c == ']') {
                return out;
            }
            if (c != ',') {
                throw new JsonParseException("Expected ',' or ']' at index " + (pos - 1));
            }
        }
    }

    private String readString() {
        expect('"');
        StringBuilder sb = new StringBuilder();
        while (true) {
            char c = next();
            if (c == '"') {
                return sb.toString();
            }
            if (c == '\\') {
                sb.append(readEscape());
            } else {
                sb.append(c);
            }
        }
    }

    private char readEscape() {
        char e = next();
        return switch (e) {
            case '"' -> '"';
            case '\\' -> '\\';
            case '/' -> '/';
            case 'b' -> '\b';
            case 'f' -> '\f';
            case 'n' -> '\n';
            case 'r' -> '\r';
            case 't' -> '\t';
            case 'u' -> readUnicodeEscape();
            default -> throw new JsonParseException("Invalid escape '\\" + e + "'");
        };
    }

    private char readUnicodeEscape() {
        if (pos + 4 > src.length()) {
            throw new JsonParseException("Truncated \\u escape at index " + pos);
        }
        String hex = src.substring(pos, pos + 4);
        pos += 4;
        try {
            return (char) Integer.parseInt(hex, 16);
        } catch (NumberFormatException ex) {
            throw new JsonParseException("Invalid \\u escape '" + hex + "'");
        }
    }

    private Boolean readBoolean() {
        if (src.startsWith("true", pos)) {
            pos += 4;
            return Boolean.TRUE;
        }
        if (src.startsWith("false", pos)) {
            pos += 5;
            return Boolean.FALSE;
        }
        throw new JsonParseException("Invalid literal at index " + pos);
    }

    private Object readNull() {
        if (src.startsWith("null", pos)) {
            pos += 4;
            return null;
        }
        throw new JsonParseException("Invalid literal at index " + pos);
    }

    private Double readNumber() {
        int start = pos;
        while (pos < src.length() && "+-0123456789.eE".indexOf(src.charAt(pos)) >= 0) {
            pos++;
        }
        if (pos == start) {
            throw new JsonParseException("Expected a value at index " + pos);
        }
        try {
            return Double.valueOf(src.substring(start, pos));
        } catch (NumberFormatException ex) {
            throw new JsonParseException("Invalid number '" + src.substring(start, pos) + "'");
        }
    }

    private void skipWhitespace() {
        while (pos < src.length() && Character.isWhitespace(src.charAt(pos))) {
            pos++;
        }
    }

    private char peek() {
        if (pos >= src.length()) {
            throw new JsonParseException("Unexpected end of input");
        }
        return src.charAt(pos);
    }

    private char next() {
        if (pos >= src.length()) {
            throw new JsonParseException("Unexpected end of input");
        }
        return src.charAt(pos++);
    }

    private void expect(char c) {
        char got = next();
        if (got != c) {
            throw new JsonParseException("Expected '" + c + "' but found '" + got + "' at index " + (pos - 1));
        }
    }

    /** Thrown when the text is not well-formed JSON. */
    public static final class JsonParseException extends RuntimeException {
        public JsonParseException(String message) {
            super(message);
        }
    }
}
