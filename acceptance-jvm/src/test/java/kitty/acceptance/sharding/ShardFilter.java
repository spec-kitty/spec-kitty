package kitty.acceptance.sharding;

import io.cucumber.tagexpressions.Expression;
import io.cucumber.tagexpressions.TagExpressionParser;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.Set;
import java.util.stream.Collectors;
import org.junit.platform.engine.FilterResult;
import org.junit.platform.engine.TestDescriptor;
import org.junit.platform.engine.TestSource;
import org.junit.platform.engine.TestTag;
import org.junit.platform.engine.UniqueId;
import org.junit.platform.engine.support.descriptor.FilePosition;
import org.junit.platform.engine.support.descriptor.FileSource;
import org.junit.platform.launcher.PostDiscoveryFilter;

/**
 * Splits the discovered scenarios into {@code N} disjoint shards so the nightly can run one pass on
 * several runners at once (#7492 follow-up: the Windows gating pass took ~47 minutes on one runner).
 *
 * <p>{@code -Dacceptance.shard=K/N} (1-based; set by {@code build.gradle} from {@code -Pacceptance.shard})
 * keeps the scenarios of shard {@code K}. Without the property every scenario is kept. The split:
 *
 * <ol>
 *   <li>takes every scenario the run's {@code cucumber.filter.tags} would execute (the engine keeps
 *       tag-excluded scenarios in discovery and only skips them, so they must not take shard slots);
 *   <li>orders them by feature path relative to {@code cucumber.features}, then by line, so every OS and
 *       every shard of one commit computes the same order;
 *   <li>deals them out round-robin: position {@code i} goes to shard {@code (i mod N) + 1}. The heavy
 *       scenarios sit together in a few feature files, so round-robin spreads each file over all shards.
 * </ol>
 *
 * <p>Every executable scenario lands in exactly one shard, because shard membership is a pure function
 * of the scenario's position in one shared order. Tag-excluded scenarios are kept in every shard, where
 * the engine skips them as before. Registered through {@code META-INF/services}.
 *
 * <p>Only the system properties {@code build.gradle} sets are read ({@code cucumber.filter.tags},
 * {@code cucumber.features}); a tag filter moved into {@code junit-platform.properties}, or a
 * {@code cucumber.filter.name}, is not seen here. The shards then stay disjoint and complete, but
 * filtered-out scenarios take shard slots and the split is less even. Without a shard nothing is parsed,
 * so an unsharded run can never fail in this filter. Each shard logs one line naming its share.
 */
public final class ShardFilter implements PostDiscoveryFilter {

    static final String SHARD_PROPERTY = "acceptance.shard";
    static final String FEATURES_PROPERTY = "cucumber.features";
    static final String TAGS_PROPERTY = "cucumber.filter.tags";

    private final Optional<Shard> shard;
    private final Optional<Expression> tagFilter;
    private final Optional<Path> featuresRoot;
    private final Map<UniqueId, Integer> assignment = new HashMap<>();
    private UniqueId assignedRoot;

    /** Configured from the system properties the Gradle build sets. */
    public ShardFilter() {
        this(System.getProperty(SHARD_PROPERTY), System.getProperty(TAGS_PROPERTY), System.getProperty(FEATURES_PROPERTY));
    }

    ShardFilter(String shardSpec, String tagExpression, String features) {
        this.shard = Shard.parse(shardSpec);
        if (shard.isEmpty()) {
            this.tagFilter = Optional.empty();
            this.featuresRoot = Optional.empty();
            return;
        }
        this.tagFilter = tagExpression == null || tagExpression.isBlank()
                ? Optional.empty()
                : Optional.of(TagExpressionParser.parse(tagExpression));
        this.featuresRoot = features == null || features.isBlank() || features.contains(",")
                ? Optional.empty()
                : Optional.of(Path.of(features).toAbsolutePath().normalize());
    }

    @Override
    public FilterResult apply(TestDescriptor descriptor) {
        if (shard.isEmpty() || !descriptor.isTest() || !isExecuted(descriptor)) {
            return FilterResult.included("not sharded");
        }
        int owner = ownerOf(descriptor);
        Shard mine = shard.get();
        return owner == mine.index()
                ? FilterResult.included("in shard " + mine)
                : FilterResult.excluded("in shard " + owner + "/" + mine.count() + ", not " + mine);
    }

    private synchronized int ownerOf(TestDescriptor descriptor) {
        TestDescriptor root = rootOf(descriptor);
        if (!root.getUniqueId().equals(assignedRoot)) {
            assign(root);
        }
        return assignment.get(descriptor.getUniqueId());
    }

    private void assign(TestDescriptor root) {
        List<TestDescriptor> executed = new ArrayList<>();
        collectExecutedTests(root, executed);
        executed.sort(Comparator.comparing(this::orderKey).thenComparing(d -> d.getUniqueId().toString()));
        assignment.clear();
        int count = shard.orElseThrow().count();
        for (int position = 0; position < executed.size(); position++) {
            assignment.put(executed.get(position).getUniqueId(), position % count + 1);
        }
        assignedRoot = root.getUniqueId();
        long mine = assignment.values().stream().filter(owner -> owner == shard.orElseThrow().index()).count();
        System.out.println("acceptance shard " + shard.orElseThrow() + ": " + mine + " of " + executed.size()
                + " executable scenarios");
    }

    private void collectExecutedTests(TestDescriptor node, List<TestDescriptor> into) {
        if (node.isTest() && isExecuted(node)) {
            into.add(node);
        }
        for (TestDescriptor child : node.getChildren()) {
            collectExecutedTests(child, into);
        }
    }

    private boolean isExecuted(TestDescriptor descriptor) {
        return tagFilter.map(expression -> expression.evaluate(cucumberTags(descriptor.getTags()))).orElse(true);
    }

    static List<String> cucumberTags(Set<TestTag> tags) {
        // The engine strips the leading '@' from a Cucumber tag; the tag expression needs it back.
        return tags.stream()
                .map(TestTag::getName)
                .map(name -> name.startsWith("@") ? name : "@" + name)
                .collect(Collectors.toList());
    }

    /** Relative feature path (forward slashes) and zero-padded line, so the order is the same on every OS. */
    String orderKey(TestDescriptor descriptor) {
        Optional<TestSource> source = descriptor.getSource();
        if (source.isPresent() && source.get() instanceof FileSource file) {
            Path path = file.getFile().toPath().toAbsolutePath().normalize();
            String relative = featuresRoot.filter(path::startsWith).map(root -> root.relativize(path)).orElse(path).toString();
            int line = file.getPosition().map(FilePosition::getLine).orElse(0);
            return relative.replace('\\', '/') + ":" + String.format("%08d", line);
        }
        return descriptor.getUniqueId().toString();
    }

    private static TestDescriptor rootOf(TestDescriptor descriptor) {
        TestDescriptor node = descriptor;
        while (node.getParent().isPresent()) {
            node = node.getParent().get();
        }
        return node;
    }

    /** One shard, {@code index} of {@code count}, both 1-based. */
    record Shard(int index, int count) {

        Shard {
            if (count < 1 || index < 1 || index > count) {
                throw new IllegalArgumentException("acceptance.shard must be K/N with 1 <= K <= N, got " + index + "/" + count);
            }
        }

        static Optional<Shard> parse(String spec) {
            if (spec == null || spec.isBlank()) {
                return Optional.empty();
            }
            String[] parts = spec.trim().split("/", -1);
            if (parts.length != 2) {
                throw new IllegalArgumentException("acceptance.shard must be K/N, got '" + spec + "'");
            }
            try {
                return Optional.of(new Shard(Integer.parseInt(parts[0].trim()), Integer.parseInt(parts[1].trim())));
            } catch (NumberFormatException e) {
                throw new IllegalArgumentException("acceptance.shard must be K/N with integers, got '" + spec + "'", e);
            }
        }

        @Override
        public String toString() {
            return index + "/" + count;
        }
    }
}
