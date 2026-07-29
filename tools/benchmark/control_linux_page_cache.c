#define _GNU_SOURCE
#define _POSIX_C_SOURCE 200809L

#include <errno.h>
#include <fcntl.h>
#include <inttypes.h>
#include <signal.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

typedef struct {
    char *path;
    uint64_t expected_size;
    uint64_t pages;
    uint64_t after_warm;
    uint64_t after_evict;
    uint64_t after_run;
    uint64_t device;
    uint64_t inode;
} file_record;

static void fail_errno(const char *operation, const char *path)
{
    fprintf(stderr, "%s failed for %s: %s\n", operation, path,
            strerror(errno));
    exit(2);
}

static void fail_message(const char *message)
{
    fprintf(stderr, "%s\n", message);
    exit(2);
}

static uint64_t parse_u64(const char *text)
{
    char *end = NULL;
    errno = 0;
    unsigned long long value = strtoull(text, &end, 10);
    if (errno != 0 || end == text || *end != '\0') {
        fail_message("manifest contains an invalid size");
    }
    return (uint64_t)value;
}

static file_record *load_manifest(const char *path, size_t *count_out)
{
    FILE *stream = fopen(path, "rb");
    if (stream == NULL) {
        fail_errno("fopen", path);
    }
    file_record *records = NULL;
    size_t count = 0;
    size_t capacity = 0;
    char *line = NULL;
    size_t line_capacity = 0;
    ssize_t length;
    while ((length = getline(&line, &line_capacity, stream)) >= 0) {
        if (length == 0 || line[length - 1] != '\n') {
            fail_message("manifest line is not newline terminated");
        }
        line[--length] = '\0';
        char *separator = strrchr(line, '\t');
        if (separator == NULL || separator == line) {
            fail_message("manifest line must be PATH<TAB>SIZE");
        }
        *separator = '\0';
        if (line[0] != '/' || strchr(line, '\n') != NULL ||
            strchr(line, '\r') != NULL) {
            fail_message("manifest path must be a clean absolute path");
        }
        if (count == capacity) {
            size_t next = capacity == 0 ? 64 : capacity * 2;
            if (next < capacity ||
                next > SIZE_MAX / sizeof(file_record)) {
                fail_message("manifest is too large");
            }
            file_record *grown =
                realloc(records, next * sizeof(file_record));
            if (grown == NULL) {
                fail_message("cannot allocate manifest records");
            }
            records = grown;
            capacity = next;
        }
        records[count] = (file_record){
            .path = strdup(line),
            .expected_size = parse_u64(separator + 1),
        };
        if (records[count].path == NULL) {
            fail_message("cannot allocate manifest path");
        }
        count++;
    }
    if (ferror(stream)) {
        fail_errno("getline", path);
    }
    free(line);
    if (fclose(stream) != 0) {
        fail_errno("fclose", path);
    }
    if (count == 0) {
        fail_message("manifest must contain at least one file");
    }
    *count_out = count;
    return records;
}

static int open_and_validate(file_record *record, struct stat *status)
{
    int descriptor = open(record->path, O_RDONLY | O_CLOEXEC);
    if (descriptor < 0) {
        fail_errno("open", record->path);
    }
    if (fstat(descriptor, status) != 0) {
        fail_errno("fstat", record->path);
    }
    if (!S_ISREG(status->st_mode) || status->st_size < 0 ||
        (uint64_t)status->st_size != record->expected_size) {
        fail_message("manifest file identity mismatch");
    }
    record->device = (uint64_t)status->st_dev;
    record->inode = (uint64_t)status->st_ino;
    return descriptor;
}

static uint64_t resident_pages(file_record *record, long page_size)
{
    struct stat status;
    int descriptor = open_and_validate(record, &status);
    if (record->expected_size == 0) {
        if (close(descriptor) != 0) {
            fail_errno("close", record->path);
        }
        record->pages = 0;
        return 0;
    }
    uint64_t pages =
        (record->expected_size + (uint64_t)page_size - 1) /
        (uint64_t)page_size;
    if (pages > SIZE_MAX) {
        fail_message("file has too many pages");
    }
    void *mapping = mmap(NULL, (size_t)record->expected_size, PROT_NONE,
                         MAP_PRIVATE, descriptor, 0);
    if (mapping == MAP_FAILED) {
        fail_errno("mmap", record->path);
    }
    unsigned char *vector = calloc((size_t)pages, 1);
    if (vector == NULL) {
        fail_message("cannot allocate mincore vector");
    }
    if (mincore(mapping, (size_t)record->expected_size, vector) != 0) {
        fail_errno("mincore", record->path);
    }
    uint64_t resident = 0;
    for (uint64_t index = 0; index < pages; index++) {
        resident += (vector[index] & 1U) != 0U ? 1U : 0U;
    }
    free(vector);
    if (munmap(mapping, (size_t)record->expected_size) != 0) {
        fail_errno("munmap", record->path);
    }
    if (close(descriptor) != 0) {
        fail_errno("close", record->path);
    }
    record->pages = pages;
    return resident;
}

static void warm_file(file_record *record)
{
    struct stat status;
    int descriptor = open_and_validate(record, &status);
    unsigned char buffer[1024 * 1024];
    uint64_t offset = 0;
    while (offset < record->expected_size) {
        size_t wanted = sizeof(buffer);
        if (record->expected_size - offset < wanted) {
            wanted = (size_t)(record->expected_size - offset);
        }
        ssize_t read_count = pread(descriptor, buffer, wanted,
                                   (off_t)offset);
        if (read_count < 0) {
            fail_errno("pread", record->path);
        }
        if (read_count == 0) {
            fail_message("file ended while warming");
        }
        offset += (uint64_t)read_count;
    }
    if (close(descriptor) != 0) {
        fail_errno("close", record->path);
    }
}

static void evict_file(file_record *record)
{
    struct stat status;
    int descriptor = open_and_validate(record, &status);
    int result =
        posix_fadvise(descriptor, 0, 0, POSIX_FADV_DONTNEED);
    if (result != 0) {
        errno = result;
        fail_errno("posix_fadvise", record->path);
    }
    if (close(descriptor) != 0) {
        fail_errno("close", record->path);
    }
}

static int64_t monotonic_milliseconds(void)
{
    struct timespec now;
    if (clock_gettime(CLOCK_MONOTONIC, &now) != 0) {
        fail_errno("clock_gettime", "CLOCK_MONOTONIC");
    }
    return (int64_t)now.tv_sec * 1000 + now.tv_nsec / 1000000;
}

static int run_command(char **arguments, const char *stdout_path,
                       const char *stderr_path, uint64_t timeout_ms)
{
    pid_t child = fork();
    if (child < 0) {
        fail_errno("fork", arguments[0]);
    }
    if (child == 0) {
        int stdout_fd =
            open(stdout_path, O_WRONLY | O_CREAT | O_TRUNC | O_CLOEXEC,
                 0600);
        int stderr_fd =
            open(stderr_path, O_WRONLY | O_CREAT | O_TRUNC | O_CLOEXEC,
                 0600);
        if (stdout_fd < 0 || stderr_fd < 0 ||
            dup2(stdout_fd, STDOUT_FILENO) < 0 ||
            dup2(stderr_fd, STDERR_FILENO) < 0) {
            _exit(126);
        }
        close(stdout_fd);
        close(stderr_fd);
        if (chdir("/bench") != 0) {
            _exit(126);
        }
        execv(arguments[0], arguments);
        _exit(127);
    }
    int64_t deadline =
        monotonic_milliseconds() + (int64_t)timeout_ms;
    int status = 0;
    for (;;) {
        pid_t result = waitpid(child, &status, WNOHANG);
        if (result == child) {
            break;
        }
        if (result < 0) {
            fail_errno("waitpid", arguments[0]);
        }
        if (monotonic_milliseconds() >= deadline) {
            if (kill(child, SIGKILL) != 0 && errno != ESRCH) {
                fail_errno("kill", arguments[0]);
            }
            if (waitpid(child, &status, 0) < 0) {
                fail_errno("waitpid", arguments[0]);
            }
            return 124;
        }
        struct timespec pause = {.tv_sec = 0, .tv_nsec = 10000000};
        while (nanosleep(&pause, &pause) != 0 && errno == EINTR) {
        }
    }
    if (WIFEXITED(status)) {
        return WEXITSTATUS(status);
    }
    if (WIFSIGNALED(status)) {
        return 128 + WTERMSIG(status);
    }
    return 125;
}

static void observe_all(file_record *records, size_t count,
                        long page_size, unsigned stage)
{
    for (size_t index = 0; index < count; index++) {
        uint64_t resident =
            resident_pages(&records[index], page_size);
        if (stage == 0) {
            records[index].after_warm = resident;
        } else if (stage == 1) {
            records[index].after_evict = resident;
        } else {
            records[index].after_run = resident;
        }
    }
}

static void write_report(const char *path, file_record *records,
                         size_t count, long page_size, int exit_code)
{
    FILE *stream = fopen(path, "wb");
    if (stream == NULL) {
        fail_errno("fopen", path);
    }
    if (fprintf(stream, "page_size\t%ld\nexit_code\t%d\n",
                page_size, exit_code) < 0) {
        fail_errno("fprintf", path);
    }
    for (size_t index = 0; index < count; index++) {
        file_record *record = &records[index];
        if (fprintf(stream,
                    "file\t%s\t%" PRIu64 "\t%" PRIu64 "\t%" PRIu64
                    "\t%" PRIu64 "\t%" PRIu64 "\t%" PRIu64 "\t%" PRIu64
                    "\n",
                    record->path, record->expected_size, record->pages,
                    record->after_warm, record->after_evict,
                    record->after_run, record->device,
                    record->inode) < 0) {
            fail_errno("fprintf", path);
        }
    }
    if (fclose(stream) != 0) {
        fail_errno("fclose", path);
    }
}

int main(int argc, char **argv)
{
    if (argc < 11 || strcmp(argv[1], "--manifest") != 0 ||
        strcmp(argv[3], "--output") != 0 ||
        strcmp(argv[5], "--stdout") != 0 ||
        strcmp(argv[7], "--stderr") != 0) {
        fail_message("usage: controller --manifest PATH --output PATH "
                     "--stdout PATH --stderr PATH -- COMMAND [ARG...]");
    }
    int command_index = 10;
    if (strcmp(argv[9], "--") != 0) {
        fail_message("missing command separator");
    }
    long page_size = sysconf(_SC_PAGESIZE);
    if (page_size <= 0) {
        fail_message("cannot determine page size");
    }
    size_t count = 0;
    file_record *records = load_manifest(argv[2], &count);
    for (size_t index = 0; index < count; index++) {
        warm_file(&records[index]);
    }
    observe_all(records, count, page_size, 0);
    for (size_t index = 0; index < count; index++) {
        evict_file(&records[index]);
    }
    observe_all(records, count, page_size, 1);
    int exit_code =
        run_command(&argv[command_index], argv[6], argv[8], 120000);
    observe_all(records, count, page_size, 2);
    write_report(argv[4], records, count, page_size, exit_code);
    for (size_t index = 0; index < count; index++) {
        free(records[index].path);
    }
    free(records);
    return exit_code == 0 ? 0 : 2;
}
