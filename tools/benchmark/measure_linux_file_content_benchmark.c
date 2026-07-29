#define main page_cache_controller_main_unused
#include "control_linux_page_cache.c"
#undef main

#include <sys/resource.h>

#define COMMAND_TIMEOUT_SECONDS 120U
#define MAX_CAPTURE_BYTES (64U * 1024U * 1024U)
#define CACHE_STATE_WARM "warm"
#define CACHE_STATE_FILE_CONTENT \
    "file-content-nonresident-metadata-warm"

static volatile sig_atomic_t measured_child = -1;
static volatile sig_atomic_t measured_timed_out = 0;

static void timeout_handler(int signal_number)
{
    (void)signal_number;
    measured_timed_out = 1;
    if (measured_child > 0) {
        kill((pid_t)measured_child, SIGKILL);
    }
}

static uint64_t monotonic_nanoseconds(void)
{
    struct timespec now;
    if (clock_gettime(CLOCK_MONOTONIC, &now) != 0) {
        fail_errno("clock_gettime", "CLOCK_MONOTONIC");
    }
    return (uint64_t)now.tv_sec * 1000000000U +
           (uint64_t)now.tv_nsec;
}

static int open_capture(const char *path)
{
    int descriptor =
        open(path, O_WRONLY | O_CREAT | O_TRUNC | O_CLOEXEC, 0600);
    if (descriptor < 0) {
        fail_errno("open", path);
    }
    return descriptor;
}

static int run_measured_command(char **arguments,
                                const char *stdout_path,
                                const char *stderr_path,
                                uint64_t *duration_ns,
                                uint64_t *peak_rss_bytes)
{
    struct sigaction action = {
        .sa_handler = timeout_handler,
    };
    if (sigemptyset(&action.sa_mask) != 0 ||
        sigaction(SIGALRM, &action, NULL) != 0) {
        fail_errno("sigaction", "SIGALRM");
    }
    uint64_t started = monotonic_nanoseconds();
    pid_t child = fork();
    if (child < 0) {
        fail_errno("fork", arguments[0]);
    }
    if (child == 0) {
        int stdout_fd = open_capture(stdout_path);
        int stderr_fd = open_capture(stderr_path);
        int stdin_fd = open("/dev/null", O_RDONLY | O_CLOEXEC);
        struct rlimit output_limit = {
            .rlim_cur = MAX_CAPTURE_BYTES,
            .rlim_max = MAX_CAPTURE_BYTES,
        };
        if (stdin_fd < 0 ||
            setrlimit(RLIMIT_FSIZE, &output_limit) != 0 ||
            dup2(stdin_fd, STDIN_FILENO) < 0 ||
            dup2(stdout_fd, STDOUT_FILENO) < 0 ||
            dup2(stderr_fd, STDERR_FILENO) < 0) {
            _exit(126);
        }
        close(stdin_fd);
        close(stdout_fd);
        close(stderr_fd);
        if (chdir("/bench") != 0) {
            _exit(126);
        }
        execv(arguments[0], arguments);
        _exit(127);
    }
    measured_child = (sig_atomic_t)child;
    measured_timed_out = 0;
    alarm(COMMAND_TIMEOUT_SECONDS);
    int status = 0;
    struct rusage usage;
    pid_t waited;
    do {
        waited = wait4(child, &status, 0, &usage);
    } while (waited < 0 && errno == EINTR);
    alarm(0);
    measured_child = -1;
    uint64_t finished = monotonic_nanoseconds();
    if (waited < 0) {
        fail_errno("wait4", arguments[0]);
    }
    if (measured_timed_out != 0) {
        return 124;
    }
    *duration_ns = finished - started;
    if (usage.ru_maxrss < 0 ||
        (uint64_t)usage.ru_maxrss > UINT64_MAX / 1024U) {
        fail_message("child peak RSS is out of range");
    }
    *peak_rss_bytes = (uint64_t)usage.ru_maxrss * 1024U;
    if (WIFEXITED(status)) {
        return WEXITSTATUS(status);
    }
    if (WIFSIGNALED(status)) {
        return 128 + WTERMSIG(status);
    }
    return 125;
}

static void require_page_state(file_record *records, size_t count,
                               bool evicted)
{
    for (size_t index = 0; index < count; index++) {
        if (records[index].after_warm != records[index].pages) {
            fail_message("not every candidate page became resident");
        }
        uint64_t expected = evicted ? 0 : records[index].pages;
        if (records[index].after_evict != expected) {
            fail_message("candidate before-run page state mismatch");
        }
    }
}

static void write_measurement(const char *path, file_record *records,
                              size_t count, long page_size,
                              const char *cache_state,
                              bool fadvise_executed,
                              int exit_code, uint64_t duration_ns,
                              uint64_t peak_rss_bytes)
{
    uint64_t logical_pages = 0;
    uint64_t warm_pages = 0;
    uint64_t evicted_pages = 0;
    for (size_t index = 0; index < count; index++) {
        logical_pages += records[index].pages;
        warm_pages += records[index].after_warm;
        evicted_pages += records[index].after_evict;
    }
    FILE *stream = fopen(path, "wb");
    if (stream == NULL) {
        fail_errno("fopen", path);
    }
    if (fprintf(
            stream,
            "schema_version\t1\n"
            "cache_state\t%s\n"
            "fadvise_executed\t%d\n"
            "page_size\t%ld\n"
            "file_count\t%zu\n"
            "logical_pages\t%" PRIu64 "\n"
            "resident_pages_after_warm\t%" PRIu64 "\n"
            "resident_pages_before_run\t%" PRIu64 "\n"
            "before_run_page_state_verified\t1\n"
            "duration_ns\t%" PRIu64 "\n"
            "peak_rss_bytes\t%" PRIu64 "\n"
            "exit_code\t%d\n"
            "timed_out\t%d\n",
            cache_state, fadvise_executed ? 1 : 0,
            page_size, count, logical_pages, warm_pages,
            evicted_pages, duration_ns, peak_rss_bytes, exit_code,
            measured_timed_out != 0 ? 1 : 0) < 0) {
        fail_errno("fprintf", path);
    }
    if (fclose(stream) != 0) {
        fail_errno("fclose", path);
    }
}

int main(int argc, char **argv)
{
    if (argc < 25 || strcmp(argv[1], "--cache-state") != 0 ||
        strcmp(argv[3], "--manifest") != 0 ||
        strcmp(argv[5], "--output") != 0 ||
        strcmp(argv[7], "--stdout") != 0 ||
        strcmp(argv[9], "--stderr") != 0 ||
        strcmp(argv[11], "--finalizer-python") != 0 ||
        strcmp(argv[13], "--finalizer-script") != 0 ||
        strcmp(argv[15], "--final-report") != 0 ||
        strcmp(argv[17], "--plan") != 0 ||
        strcmp(argv[19], "--preflight") != 0 ||
        strcmp(argv[21], "--repo-root") != 0 ||
        strcmp(argv[23], "--") != 0) {
        fail_message("usage: measure --cache-state STATE "
                     "--manifest PATH --output PATH "
                     "--stdout PATH --stderr PATH "
                     "--finalizer-python PATH "
                     "--finalizer-script PATH "
                     "--final-report PATH --plan PATH "
                     "--preflight PATH --repo-root PATH "
                     "-- COMMAND [ARG...]");
    }
    bool evicted;
    if (strcmp(argv[2], CACHE_STATE_WARM) == 0) {
        evicted = false;
    } else if (strcmp(argv[2], CACHE_STATE_FILE_CONTENT) == 0) {
        evicted = true;
    } else {
        fail_message("unsupported cache state");
    }
    long page_size = sysconf(_SC_PAGESIZE);
    if (page_size <= 0) {
        fail_message("cannot determine page size");
    }
    size_t count = 0;
    file_record *records = load_manifest(argv[4], &count);
    for (size_t index = 0; index < count; index++) {
        warm_file(&records[index]);
    }
    observe_all(records, count, page_size, 0);
    if (evicted) {
        for (size_t index = 0; index < count; index++) {
            evict_file(&records[index]);
        }
        observe_all(records, count, page_size, 1);
    } else {
        for (size_t index = 0; index < count; index++) {
            records[index].after_evict =
                records[index].after_warm;
        }
    }
    require_page_state(records, count, evicted);
    uint64_t duration_ns = 0;
    uint64_t peak_rss_bytes = 0;
    int exit_code = run_measured_command(
        &argv[24], argv[8], argv[10], &duration_ns, &peak_rss_bytes);
    write_measurement(argv[6], records, count, page_size, argv[2],
                      evicted, exit_code, duration_ns, peak_rss_bytes);
    for (size_t index = 0; index < count; index++) {
        free(records[index].path);
    }
    free(records);
    char *finalizer_arguments[] = {
        argv[12],
        argv[14],
        "--finalize-controlled",
        "--plan",
        argv[18],
        "--measurement",
        argv[6],
        "--stdout",
        argv[8],
        "--stderr",
        argv[10],
        "--output",
        argv[16],
        "--preflight",
        argv[20],
        "--repo-root",
        argv[22],
        NULL,
    };
    execv(argv[12], finalizer_arguments);
    fail_errno("execv", argv[12]);
}
