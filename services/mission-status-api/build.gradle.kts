import org.gradle.api.tasks.testing.logging.TestExceptionFormat
import org.graalvm.buildtools.gradle.tasks.BuildNativeImageTask
import org.graalvm.buildtools.gradle.tasks.NativeRunTask
import org.openapitools.generator.gradle.plugin.tasks.GenerateTask
import java.security.MessageDigest
import java.util.Properties
import javax.xml.parsers.DocumentBuilderFactory

// The COMPLETE build script of the Mission Status API service. Every later work package adds source files only; a need for a
// task, a source set or a dependency that is missing here is a reviewed amendment to THIS file, never a parallel edit.
//
// Decisions recorded in research.md (WP02 spike record) that this script applies:
//   - generated mode (openapi-generator 7.25.0, `spring` generator) limited to getProject and listMissions by a FILTER normalizer
//     PLUS an explicit models list (the filter alone still generates all 58 schemas);
//   - bundling mechanism B: the contract document is built once by contracts/tools/bundle.py OUTSIDE the repository and handed to
//     `bundleContract` (-PcontractBundle=<file> -PcontractBundleSha256=<digest>, or the CONTRACT_BUNDLE and CONTRACT_BUNDLE_SHA256
//     environment variables); the task accepts the file only when its SHA-256 equals the digest;
//   - native tests: `test` stays UNFILTERED, `nativeTagJvmTest` is the @Tag("native") twin that writes the JUnit unique-id list the
//     native test binary reads (Review cycle 2 F1);
//   - gradleTestKit() lives in its own `kit` source set (it breaks processTestAot on the test classpath);
//   - jakarta.validation-api only, never spring-boot-starter-validation; no springdoc anywhere.

plugins {
    java
    jacoco
    alias(libs.plugins.spring.boot)
    alias(libs.plugins.spring.dependency.management)
    alias(libs.plugins.openapi.generator)
    alias(libs.plugins.graalvm.native)
}

// processTestAot fails with "'groupId' must not be empty" without a group (spike record, T004 item 1).
group = "org.speckitty.missionstatus"
version = "0.0.0-dev"

java {
    toolchain {
        languageVersion = JavaLanguageVersion.of(25)
    }
}

// ---------------------------------------------------------------------------------------------------------------------------
// Dependencies (every dependency any later work package needs is declared here)
// ---------------------------------------------------------------------------------------------------------------------------

dependencies {
    implementation(libs.spring.boot.starter.web)
    // The generated interfaces and models need the annotations only; no validator runtime (a Hibernate Validator on the classpath
    // breaks the native test image, and performBeanValidation is off, so the application owns the pageSize clamp).
    implementation(libs.jakarta.validation.api)
    // The YAML reader of adapter.out.filesystem (.kittify/config.yaml, metadata.yaml); version managed by the Boot BOM.
    implementation(libs.snakeyaml)

    testImplementation(libs.spring.boot.starter.test)
    testImplementation(libs.archunit.junit5)
    testImplementation(libs.networknt.json.schema)
    testRuntimeOnly(libs.junit.platform.launcher)
}

// ---------------------------------------------------------------------------------------------------------------------------
// Contract consumption: generated interfaces and models for getProject and listMissions only
// ---------------------------------------------------------------------------------------------------------------------------

// The contract root. The default is the repository's contracts/ directory; the nested-build tests override it with -PcontractRoot.
val contractRoot: String = providers.gradleProperty("contractRoot").orElse(file("../../contracts").path).get()

tasks.named<GenerateTask>("openApiGenerate") {
    // The plugin tracks only the root document. The contract is split across schemas/, paths/, parameters/ and responses/ via
    // $ref, so the whole contract root is a task input: an edit to a referenced file, or a different -PcontractRoot, re-runs it.
    inputs.dir(contractRoot).withPropertyName("contractRoot")
    generatorName.set("spring")
    inputSpec.set("$contractRoot/mission-status/openapi.yaml")
    outputDir.set(layout.buildDirectory.dir("generated/openapi").get().asFile.path)
    apiPackage.set("org.speckitty.missionstatus.adapter.in.http.api")
    modelPackage.set("org.speckitty.missionstatus.adapter.in.http.model")
    // The contract tags six operations `Missions`; an unrestricted run yields five more live routes answering 501. The FILTER
    // removes every operation but the two in scope (the five detail operations get hand-written controllers and no generated
    // interface), and the explicit models list keeps the model package to the closure of the seven operations: the two above plus
    // getMission, getWorkPackage, getWorkPackageDetail, listArtifacts and getArtifactContent (the filter alone still generates all
    // schemas). `Problem_1`, `Actor_1`, `Readiness_1` and `SubtaskProgress_1` are the generator's inline duplicates; a missing name is
    // a compile error where it is referenced, an extra name is harmless.
    openapiNormalizer.set(mapOf("FILTER" to "operationId:getProject|listMissions"))
    // The contract types every timestamp `date-time`; the service serves each one as the text it holds (a Mission's own createdAt, or an
    // event time exactly as written), which an OffsetDateTime cannot reproduce byte for byte (`+00:00` against `Z`, fraction widths).
    typeMappings.set(mapOf("OffsetDateTime" to "String"))
    importMappings.set(mapOf("OffsetDateTime" to "java.lang.String"))
    globalProperties.set(
        mapOf(
            "apis" to "",
            "supportingFiles" to "false",
            "models" to "Actor,Actor_1,ActorHandle,ArtifactContent,ArtifactEntry,ArtifactKind,ArtifactListing,ArtifactPath,ArtifactReference,ArtifactReferences,ArtifactRefusal,ArtifactRefusalCode,Assignment,Authored,Cancellation,ChangeState,DependencyRef,HistoryEntry,LifecycleStatus,MissionDetail,MissionHead,MissionId,MissionOverview,MissionOverviewPage,MissionPhase,MissionProgress,OwnedFile,PageCursorRefusal,PageInfo,Problem,Problem_1,Project,Readiness,Readiness_1,RelativeReference,Review,ReviewCycle,ReviewOverride,ReviewResult,ReviewVerdict,Staleness,StatusLane,StatusLaneCounts,StreamCursor,Subtask,SubtaskProgress,SubtaskProgress_1,Topology,WorkPackage,WorkPackageDetail,WorkPackageDetailRefusal,WorkPackageDetailRefusalCode,WorkPackageSummary,Workspace,WpId",
        ),
    )
    configOptions.set(
        mapOf(
            "interfaceOnly" to "true",
            "useSpringBoot3" to "true",
            "useTags" to "true",
            "documentationProvider" to "none",
            // Jackson 3 only: JsonNullable (a Jackson 2 type) must never appear.
            "openApiNullable" to "false",
            "defaultInterfaces" to "false",
            "skipDefaultInterface" to "true",
            "useBeanValidation" to "true",
            "performBeanValidation" to "false",
            "hideGenerationTimestamp" to "true",
            // Stated explicitly to pin the 7.23-equivalent output and silence the generator's "is not set" warnings.
            "generateJsonIncludeAnnotations" to "false",
            "generateJsonSetterNullsAnnotations" to "false",
        ),
    )
}

sourceSets.main {
    java.srcDir(layout.buildDirectory.dir("generated/openapi/src/main/java"))
}

tasks.compileJava {
    dependsOn("openApiGenerate")
}

// ---------------------------------------------------------------------------------------------------------------------------
// bundleContract (mechanism B): the served contract document, verified against a digest, placed in the main resources
// ---------------------------------------------------------------------------------------------------------------------------

val contractBundleOutput = layout.buildDirectory.dir("generated/contract-resources")
val contractBundleFile: Provider<String> =
    providers.gradleProperty("contractBundle").orElse(providers.environmentVariable("CONTRACT_BUNDLE"))
val contractBundleSha256: Provider<String> =
    providers.gradleProperty("contractBundleSha256").orElse(providers.environmentVariable("CONTRACT_BUNDLE_SHA256"))

val bundleContract = tasks.register("bundleContract") {
    group = "build"
    description = "Places the pre-built contract document in the main resources as contract/openapi.yaml after a SHA-256 check."
    inputs.property("contractBundleSha256", contractBundleSha256.orElse(""))
    inputs.files(providers.provider { contractBundleFile.orNull?.let { listOf(file(it)) } ?: emptyList() })
    outputs.dir(contractBundleOutput)
    doLast {
        val path = contractBundleFile.orNull
            ?: throw GradleException(
                "bundleContract: no contract document given. Build it once with contracts/tools/bundle.py into a directory " +
                    "outside the repository and pass -PcontractBundle=<file> -PcontractBundleSha256=<digest> " +
                    "(or set CONTRACT_BUNDLE and CONTRACT_BUNDLE_SHA256).",
            )
        val expected = contractBundleSha256.orNull?.trim()?.lowercase()
            ?: throw GradleException("bundleContract: no digest given (-PcontractBundleSha256 or CONTRACT_BUNDLE_SHA256).")
        val source = file(path)
        if (!source.isFile) {
            throw GradleException("bundleContract: the contract document is not a file: $path")
        }
        val bytes = source.readBytes()
        val actual = MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) }
        if (actual != expected) {
            throw GradleException("bundleContract: SHA-256 mismatch, expected $expected but the file hashes to $actual")
        }
        val target = contractBundleOutput.get().file("contract/openapi.yaml").asFile
        target.parentFile.mkdirs()
        target.writeBytes(bytes)
    }
}

tasks.processResources {
    dependsOn("bundleContract")
    from(contractBundleOutput)
}

tasks.bootJar {
    archiveFileName.set("mission-status-api.jar")
}

// ---------------------------------------------------------------------------------------------------------------------------
// Test partition (decided here; no later work package edits this script).
//   Tags:   native        runs on the JVM in `test` AND natively through nativeTest (list written by nativeTagJvmTest)
//           native-binary needs a built binary (NativeSmokeTest, NativePerfTest): only nativeSmoke / nativePerf run them
//           perf          perf-ratio classes: only perfTest runs them
//   Tasks:  test (unfiltered except for the two exclusions), nativeTagJvmTest, nativeSmoke, nativePerf, perfTest, kitTest.
//   `check` depends on perfTest, nativeTagJvmTest, kitTest, the JaCoCo rule and jacocoScopeCheck; it never runs the binary tests.
//   Empty tag-filtered tasks: Gradle 9.7.1 passes a Test task whose tag filter matches nothing (research.md T004 item 3), so no
//   failOnNoDiscoveredTests switch is set. Zero-test cases are caught by the floor guards instead.
// ---------------------------------------------------------------------------------------------------------------------------

val testSourceSet = sourceSets.test

tasks.named<Test>("test") {
    useJUnitPlatform {
        excludeTags("native-binary", "perf")
    }
    // The nested-build (TestKit) classes live in the kit source set; see below.
    finalizedBy("jacocoTestReport")
    // BEGIN not-run report hook
    // A JUnit skip is green in `check`. A test whose precondition is unmet appends `not run: precondition unmet: <test id>` to
    // build/reports/not-run.txt (the test of a later work package does; this script writes nothing there). After the task the file is
    // appended to the job summary named by GITHUB_STEP_SUMMARY, or printed to standard output when there is none; no file, no output.
    doLast {
        val notRun = layout.buildDirectory.file("reports/not-run.txt").get().asFile
        if (notRun.isFile && notRun.length() > 0L) {
            val text = notRun.readText(Charsets.UTF_8).let { if (it.endsWith("\n")) it else it + "\n" }
            val summary = System.getenv("GITHUB_STEP_SUMMARY")
            if (summary.isNullOrBlank()) {
                print(text)
            } else {
                File(summary).appendText(text, Charsets.UTF_8)
            }
        }
    }
    // END not-run report hook
}

tasks.withType<Test>().configureEach {
    testLogging {
        exceptionFormat = TestExceptionFormat.FULL
    }
}

val nativeTestListDirectory = layout.buildDirectory.dir("test-results/nativeTagJvmTest/testlist")

// The JVM twin of the native test run: the same classes and classpath as `test`, restricted to @Tag("native"). It writes the JUnit
// unique-id list through JUnit's own tracking listener (the Native Build Tools plugin injects those properties into `test` only),
// and the native test image is compiled from, and run against, that list (Review cycle 2 F1).
val nativeTagJvmTest = tasks.register<Test>("nativeTagJvmTest") {
    group = "verification"
    description = "Runs the @Tag(\"native\") tests on the JVM and writes the unique-id list the native test binary executes."
    testClassesDirs = testSourceSet.get().output.classesDirs
    classpath = testSourceSet.get().runtimeClasspath
    useJUnitPlatform {
        includeTags("native")
    }
    systemProperty("junit.platform.listeners.uid.tracking.enabled", "true")
    systemProperty("junit.platform.listeners.uid.tracking.output.dir", nativeTestListDirectory.get().asFile.path)
    outputs.dir(nativeTestListDirectory)
}

fun Test.requireNativeBinary() {
    val binary = providers.gradleProperty("nativeBinary")
    // One invocation may build and replay (`nativeCompile nativeSmoke -PnativeBinary=...`): replay only after the build.
    mustRunAfter("nativeCompile")
    doFirst {
        if (!binary.isPresent) {
            throw GradleException("$name needs the built binary: pass -PnativeBinary=<path to the native executable>")
        }
    }
    binary.orNull?.let { systemProperty("nativeBinary", it) }
}

val nativeSmoke = tasks.register<Test>("nativeSmoke") {
    group = "verification"
    description = "Starts the built native binary and replays the smoke requests (needs -PnativeBinary=<path>)."
    testClassesDirs = testSourceSet.get().output.classesDirs
    classpath = testSourceSet.get().runtimeClasspath
    useJUnitPlatform {
        includeTags("native-binary")
    }
    filter {
        includeTestsMatching("*NativeSmokeTest")
    }
    requireNativeBinary()
}

val nativePerf = tasks.register<Test>("nativePerf") {
    group = "verification"
    description = "Runs the performance probe against the built native binary (needs -PnativeBinary=<path>)."
    testClassesDirs = testSourceSet.get().output.classesDirs
    classpath = testSourceSet.get().runtimeClasspath
    useJUnitPlatform {
        includeTags("native-binary")
    }
    filter {
        includeTestsMatching("*NativePerfTest")
    }
    requireNativeBinary()
}

val perfTest = tasks.register<Test>("perfTest") {
    group = "verification"
    description = "Runs the @Tag(\"perf\") ratio tests (part of check: the NFR-004 hold is fixed by the spec)."
    testClassesDirs = testSourceSet.get().output.classesDirs
    classpath = testSourceSet.get().runtimeClasspath
    useJUnitPlatform {
        includeTags("perf")
    }
}

// ---------------------------------------------------------------------------------------------------------------------------
// Nested-build tests (TestKit): the verification tamper test and, later, the contract drift test. gradleTestKit() breaks
// processTestAot when it shares the test classpath (slf4j binding collides with Logback), so these classes compile and run in
// their own source set. Selection: everything under a `build` package and every class named *NestedBuildTest.
// ---------------------------------------------------------------------------------------------------------------------------

val kitClasses = listOf("**/org/speckitty/missionstatus/build/**", "**/*NestedBuildTest.java")

val kit: SourceSet = sourceSets.create("kit") {
    java.srcDir("src/test/java")
    java.include(kitClasses)
    resources.setSrcDirs(emptyList<String>())
}
testSourceSet.get().java.exclude(kitClasses)

dependencies {
    "kitImplementation"(gradleTestKit())
    "kitImplementation"(libs.junit.jupiter)
    "kitImplementation"(libs.assertj.core)
    "kitRuntimeOnly"(libs.junit.platform.launcher)
}

val kitTest = tasks.register<Test>("kitTest") {
    group = "verification"
    description = "Runs the TestKit nested-build tests (verification tamper, contract drift) offline against the real Gradle user home."
    testClassesDirs = kit.output.classesDirs
    classpath = kit.runtimeClasspath
    useJUnitPlatform()
    // The nested builds resolve offline from the cache the outer build populated, so the outer compile classpath is resolved first.
    dependsOn(tasks.compileJava)
    systemProperty("kit.projectDir", projectDir.absolutePath)
    systemProperty("kit.contractRoot", contractRoot)
    systemProperty("kit.gradleUserHome", gradle.gradleUserHomeDir.absolutePath)
}

// ---------------------------------------------------------------------------------------------------------------------------
// Native image (GraalVM Native Build Tools through the Spring Boot plugin)
// ---------------------------------------------------------------------------------------------------------------------------

graalvmNative {
    // The image comes from JAVA_HOME (graalvm/setup-graalvm in CI), never from toolchain detection.
    toolchainDetection.set(false)
}

tasks.named<BuildNativeImageTask>("nativeTestCompile") {
    dependsOn(nativeTagJvmTest)
    testListDirectory.set(nativeTestListDirectory)
}

tasks.named<NativeRunTask>("nativeTest") {
    dependsOn(nativeTagJvmTest)
    environment.put("JUNIT_PLATFORM_LISTENERS_UID_TRACKING_OUTPUT_DIR", nativeTestListDirectory.get().asFile.path)
    // The -D argument must come FIRST: set after the plugin's default argument it displaced the XML output directory.
    runtimeArgs.set(
        listOf(
            "-Djunit.platform.listeners.uid.tracking.output.dir=${nativeTestListDirectory.get().asFile.path}",
            "--xml-output-dir",
            layout.buildDirectory.dir("test-results/test-native").get().asFile.path,
        ),
    )
}

// ---------------------------------------------------------------------------------------------------------------------------
// JaCoCo: three rules (NFR-006) and the scope guard that keeps them from passing vacuously
// ---------------------------------------------------------------------------------------------------------------------------

jacoco {
    toolVersion = libs.versions.jacoco.get()
}

// Generated sources, config and the adapters are outside the coverage scope; domain.* and application.* are the scope.
val coverageClassDirectories = sourceSets.main.get().output.classesDirs.asFileTree.matching {
    exclude(
        "org/speckitty/missionstatus/adapter/**",
        "org/speckitty/missionstatus/config/**",
    )
}

tasks.named<JacocoReport>("jacocoTestReport") {
    dependsOn(tasks.test)
    classDirectories.setFrom(coverageClassDirectories)
    reports {
        xml.required.set(true)
        html.required.set(true)
    }
}

tasks.named<JacocoCoverageVerification>("jacocoTestCoverageVerification") {
    dependsOn(tasks.test)
    classDirectories.setFrom(coverageClassDirectories)
    violationRules {
        rule {
            element = "CLASS"
            includes = listOf("org.speckitty.missionstatus.domain.*")
            limit {
                counter = "LINE"
                minimum = "0.90".toBigDecimal()
            }
        }
        rule {
            element = "CLASS"
            includes = listOf("org.speckitty.missionstatus.application.*")
            limit {
                counter = "LINE"
                minimum = "0.90".toBigDecimal()
            }
        }
        rule {
            element = "CLASS"
            includes = listOf("org.speckitty.missionstatus.domain.*")
            limit {
                counter = "BRANCH"
                minimum = "0.80".toBigDecimal()
            }
        }
    }
}

/** One scope pattern per verification rule; the key names the line of jacoco-class-floor.properties. */
val jacocoScopePatterns = mapOf(
    "domain" to "org.speckitty.missionstatus.domain.*",
    "application" to "org.speckitty.missionstatus.application.*",
)

/** JaCoCo pattern semantics: `*` matches any run of characters (it crosses package separators), `?` one character. */
fun jacocoPatternRegex(pattern: String): Regex =
    Regex(pattern.split("*").joinToString(".*") { part -> part.split("?").joinToString(".") { Regex.escape(it) } })

/**
 * The pure core of jacocoScopeCheck: the failures (empty list = pass) for the class names the report holds, the floors file (null
 * when absent) and the patterns. The tolerance is PER PATTERN: a pattern's floor line (and the whole file) may be absent only while
 * the report holds no class matching THAT pattern; as soon as one class matches, an absent file, an absent line, a zero floor or a
 * count below the floor fails.
 */
fun jacocoScopeFailures(classNames: List<String>, floors: Properties?, patterns: Map<String, String>): List<String> {
    val failures = mutableListOf<String>()
    for ((key, pattern) in patterns) {
        val matched = classNames.count { jacocoPatternRegex(pattern).matches(it) }
        val floor = floors?.getProperty(key)?.trim()?.toIntOrNull()
        if (matched == 0) {
            if (floor != null && floor > 0) {
                failures += "scope $key ($pattern) matched 0 classes but the floor is $floor"
            }
            continue
        }
        when {
            floors == null -> failures += "scope $key ($pattern) matched $matched classes but jacoco-class-floor.properties is absent"
            floor == null -> failures += "scope $key ($pattern) matched $matched classes but the floor file has no '$key' line"
            floor <= 0 -> failures += "scope $key ($pattern) matched $matched classes but its floor is $floor (must be positive)"
            matched < floor -> failures += "scope $key ($pattern) matched $matched classes, below the floor $floor"
        }
    }
    return failures
}

fun jacocoReportClassNames(report: File): List<String> {
    val factory = DocumentBuilderFactory.newInstance()
    // The report carries a DOCTYPE that names report.dtd; never load it.
    factory.setFeature("http://apache.org/xml/features/nonvalidating/load-external-dtd", false)
    factory.setFeature("http://apache.org/xml/features/disallow-doctype-decl", false)
    val document = factory.newDocumentBuilder().parse(report)
    val nodes = document.getElementsByTagName("class")
    return (0 until nodes.length).map { nodes.item(it).attributes.getNamedItem("name").nodeValue.replace('/', '.') }
}

val jacocoScopeCheck = tasks.register("jacocoScopeCheck") {
    group = "verification"
    description = "Fails unless each JaCoCo rule pattern matched at least the class count in jacoco-class-floor.properties."
    dependsOn("jacocoTestReport")
    val report = layout.buildDirectory.file("reports/jacoco/test/jacocoTestReport.xml")
    val floorFile = layout.projectDirectory.file("src/test/resources/jacoco-class-floor.properties")
    inputs.file(report)
    inputs.files(providers.provider { if (floorFile.asFile.isFile) listOf(floorFile.asFile) else emptyList() })
    doLast {
        val reportFile = report.get().asFile
        if (!reportFile.isFile) {
            throw GradleException("jacocoScopeCheck: the JaCoCo XML report is missing: $reportFile")
        }
        val floors = if (floorFile.asFile.isFile) Properties().apply { floorFile.asFile.inputStream().use { load(it) } } else null
        val failures = jacocoScopeFailures(jacocoReportClassNames(reportFile), floors, jacocoScopePatterns)
        if (failures.isNotEmpty()) {
            throw GradleException("jacocoScopeCheck failed:\n" + failures.joinToString("\n") { "  - $it" })
        }
    }
}

tasks.named("check") {
    dependsOn("perfTest", "nativeTagJvmTest", "kitTest", "jacocoTestCoverageVerification", "jacocoScopeCheck")
}
