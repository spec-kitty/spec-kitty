package kitty.acceptance.environment;

import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.HashMap;
import java.util.HexFormat;
import java.util.Map;
import java.util.TreeMap;
import java.util.stream.Stream;

/** Before/after SHA-256 snapshots of paths in the working tree, for the "unchanged" ratchet steps. */
public final class FileSnapshots {

    private final Path workDir;
    private final Map<String, String> recordedDigests = new HashMap<>();

    public FileSnapshots(Path workDir) {
        this.workDir = workDir;
    }

    public void recordState(String relative) {
        recordedDigests.put(relative, digest(workDir.resolve(relative)));
    }

    public boolean isUnchanged(String relative) {
        String recorded = recordedDigests.get(relative);
        if (recorded == null) {
            throw new IllegalStateException("No recorded state for '" + relative + "'");
        }
        return recorded.equals(digest(workDir.resolve(relative)));
    }

    // --- digest helpers --------------------------------------------------

    private static String digest(Path path) {
        if (!Files.exists(path)) {
            return "ABSENT";
        }
        MessageDigest md = newSha256();
        if (Files.isDirectory(path)) {
            Map<String, String> entries = new TreeMap<>();
            try (Stream<Path> tree = Files.walk(path)) {
                tree.forEach(p -> {
                    String rel = path.relativize(p).toString().replace('\\', '/');
                    if (Files.isDirectory(p)) {
                        entries.put("d:" + rel, "");
                    } else {
                        entries.put("f:" + rel, sha256(p));
                    }
                });
            } catch (IOException e) {
                throw new UncheckedIOException("Could not walk " + path, e);
            }
            for (Map.Entry<String, String> entry : entries.entrySet()) {
                md.update(entry.getKey().getBytes(StandardCharsets.UTF_8));
                md.update((byte) 0);
                md.update(entry.getValue().getBytes(StandardCharsets.UTF_8));
                md.update((byte) 0);
            }
        } else {
            md.update(readAllBytes(path));
        }
        return HexFormat.of().formatHex(md.digest());
    }

    private static String sha256(Path file) {
        MessageDigest md = newSha256();
        md.update(readAllBytes(file));
        return HexFormat.of().formatHex(md.digest());
    }

    private static byte[] readAllBytes(Path path) {
        try {
            return Files.readAllBytes(path);
        } catch (IOException e) {
            throw new UncheckedIOException("Could not read " + path, e);
        }
    }

    private static MessageDigest newSha256() {
        try {
            return MessageDigest.getInstance("SHA-256");
        } catch (NoSuchAlgorithmException e) {
            throw new IllegalStateException("SHA-256 is unavailable", e);
        }
    }
}
