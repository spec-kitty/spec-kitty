import org.gradle.api.tasks.testing.logging.TestExceptionFormat
import org.springframework.boot.gradle.plugin.SpringBootPlugin

// event-log: the reader of a Mission's status.events.jsonl (the line decoder and its byte rules, DD-85 and DD-92) and the event
// ordering and fold (StatusReducer). A library of #6117 decision 12, extracted from the query service by #6192. Among project
// modules it depends on domain-model only; its one external dependency is the Jackson streaming parser, which the decoder uses
// without data binding or reflection. EventLogBoundaryTest holds its classes to that set.
// The Spring Boot BOM is imported for versions only (no version literal in this script, as in the root).

plugins {
    `java-library`
    jacoco
    id("io.spring.dependency-management")
}

java {
    toolchain {
        languageVersion = JavaLanguageVersion.of(25)
    }
}

dependencyManagement {
    imports {
        mavenBom(SpringBootPlugin.BOM_COORDINATES)
    }
}

dependencies {
    // The decoder's public API returns domain-model types.
    api(project(":domain-model"))
    implementation(libs.jackson.core)

    testImplementation(libs.junit.jupiter)
    testImplementation(libs.assertj.core)
    testImplementation(libs.archunit.junit5)
    // Test-only: the boundary test plants a data-binding dependency to prove the codec rule refuses it.
    testImplementation(libs.jackson.databind)
    testRuntimeOnly(libs.junit.platform.launcher)
}

jacoco {
    toolVersion = libs.versions.jacoco.get()
}

// The compiler settings the Spring Boot plugin gives the root project, kept for the moved sources (non-ASCII literals in the tests).
tasks.withType<JavaCompile>().configureEach {
    options.encoding = "UTF-8"
    options.compilerArgs.add("-parameters")
}

tasks.named<Test>("test") {
    useJUnitPlatform()
    testLogging {
        exceptionFormat = TestExceptionFormat.FULL
    }
    // A root-level `./gradlew test --tests <pattern>` selects this task too; a pattern that names a root test must not fail it.
    filter.isFailOnNoMatchingTests = false
    // The boundary test imports exactly this module's production classes.
    systemProperty("module.mainClasses", sourceSets.main.get().output.classesDirs.asPath)
}
