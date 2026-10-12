package kitty.acceptance.driver;

/** Process-tree helpers shared by the CLI driver and the environment provisioning code. */
public final class ProcessTree {

    private ProcessTree() {
    }

    /** Force-kills the process and every descendant (the part that matters most on Windows). */
    public static void kill(Process process) {
        process.descendants().forEach(ProcessHandle::destroyForcibly);
        process.toHandle().destroyForcibly();
    }
}
