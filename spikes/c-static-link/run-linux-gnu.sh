#!/bin/sh
set -eu

build_dir=${CARGO_TARGET_DIR:-target/linux-gnu}
export CARGO_TARGET_DIR=$build_dir

cargo +1.88.0 build --release --locked

mkdir -p "$build_dir/c-smoke"
cc -std=c11 -Wall -Wextra -Werror \
    c/smoke.c \
    "$build_dir/release/libdiec_c_static_link_spike.a" \
    -lgcc_s -lutil -lrt -lpthread -lm -ldl -lc \
    -o "$build_dir/c-smoke/smoke"

"$build_dir/c-smoke/smoke"
