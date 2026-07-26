#include "../include/diec_rquickjs_spike.h"

#include <assert.h>
#include <stddef.h>

int main(void)
{
    int32_t value = 0;

    assert(
        diec_rquickjs_spike_eval(NULL)
        == DIEC_RQUICKJS_SPIKE_STATUS_INVALID_ARGUMENT
    );
    for (int index = 0; index < 16; ++index) {
        value = 0;
        assert(
            diec_rquickjs_spike_eval(&value)
            == DIEC_RQUICKJS_SPIKE_STATUS_OK
        );
        assert(value == 42);
    }
    assert(
        diec_rquickjs_spike_force_panic()
        == DIEC_RQUICKJS_SPIKE_STATUS_PANIC
    );
    return 0;
}
