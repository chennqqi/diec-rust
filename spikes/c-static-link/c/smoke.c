#include "../include/diec_spike.h"

#include <stdio.h>
#include <string.h>

#define CHECK(condition)                                                       \
    do {                                                                       \
        if (!(condition)) {                                                    \
            fprintf(stderr, "CHECK failed at %s:%d: %s\n", __FILE__, __LINE__, \
                    #condition);                                               \
            return 1;                                                          \
        }                                                                      \
    } while (0)

static int bytes_equal(const uint8_t *actual,
                       uint64_t actual_length,
                       const char *expected) {
    size_t expected_length = strlen(expected);
    return actual_length == (uint64_t)expected_length &&
           memcmp(actual, expected, expected_length) == 0;
}

int main(void) {
    const uint8_t input[] = {1, 2, 3, 4};
    const uint8_t *json_data = NULL;
    const uint8_t *message_data = NULL;
    uint64_t json_length = 0;
    uint64_t message_length = 0;
    uint32_t iteration = 0;
    diec_spike_result *result = NULL;
    uint8_t sentinel = 0;

    CHECK(diec_spike_abi_version() == DIEC_SPIKE_ABI_VERSION);

    CHECK(diec_spike_scan(input, sizeof(input), &result) ==
          DIEC_SPIKE_STATUS_OK);
    CHECK(result != NULL);
    CHECK(diec_spike_result_json(result, &json_data, &json_length) ==
          DIEC_SPIKE_STATUS_OK);
    CHECK(json_data != NULL);
    CHECK(bytes_equal(json_data, json_length,
                      "{\"schema_version\":1,\"size\":4,\"sum\":10}"));

    CHECK(diec_spike_result_free(&result) == DIEC_SPIKE_STATUS_OK);
    CHECK(result == NULL);
    CHECK(diec_spike_result_free(&result) == DIEC_SPIKE_STATUS_OK);
    CHECK(diec_spike_result_free(NULL) ==
          DIEC_SPIKE_STATUS_INVALID_ARGUMENT);

    for (iteration = 0; iteration < UINT32_C(1000); ++iteration) {
        CHECK(diec_spike_scan(input, sizeof(input), &result) ==
              DIEC_SPIKE_STATUS_OK);
        CHECK(diec_spike_result_free(&result) == DIEC_SPIKE_STATUS_OK);
        CHECK(result == NULL);
    }

    result = (diec_spike_result *)(uintptr_t)1;
    CHECK(diec_spike_scan(NULL, 1, &result) ==
          DIEC_SPIKE_STATUS_INVALID_ARGUMENT);
    CHECK(result == NULL);

    CHECK(diec_spike_scan(&sentinel, DIEC_SPIKE_MAX_INPUT_BYTES + UINT64_C(1),
                          &result) == DIEC_SPIKE_STATUS_INPUT_TOO_LARGE);
    CHECK(result == NULL);
    CHECK(diec_spike_scan(NULL, 0, NULL) ==
          DIEC_SPIKE_STATUS_INVALID_ARGUMENT);

    CHECK(diec_spike_scan(NULL, 0, &result) == DIEC_SPIKE_STATUS_OK);
    CHECK(diec_spike_result_json(result, &json_data, &json_length) ==
          DIEC_SPIKE_STATUS_OK);
    CHECK(bytes_equal(json_data, json_length,
                      "{\"schema_version\":1,\"size\":0,\"sum\":0}"));
    CHECK(diec_spike_result_free(&result) == DIEC_SPIKE_STATUS_OK);

    json_data = (const uint8_t *)(uintptr_t)1;
    json_length = UINT64_MAX;
    CHECK(diec_spike_result_json(NULL, &json_data, &json_length) ==
          DIEC_SPIKE_STATUS_INVALID_ARGUMENT);
    CHECK(json_data == NULL);
    CHECK(json_length == 0);

    CHECK(diec_spike_status_message(DIEC_SPIKE_STATUS_INPUT_TOO_LARGE,
                                    &message_data, &message_length) ==
          DIEC_SPIKE_STATUS_OK);
    CHECK(bytes_equal(message_data, message_length, "input too large"));
    message_data = (const uint8_t *)(uintptr_t)1;
    message_length = UINT64_MAX;
    CHECK(diec_spike_status_message(UINT32_MAX, &message_data,
                                    &message_length) ==
          DIEC_SPIKE_STATUS_INVALID_ARGUMENT);
    CHECK(message_data == NULL);
    CHECK(message_length == 0);

    CHECK(diec_spike_force_panic() == DIEC_SPIKE_STATUS_PANIC);
    CHECK(diec_spike_abi_version() == DIEC_SPIKE_ABI_VERSION);

    puts("PASS c-static-link-smoke");
    return 0;
}
