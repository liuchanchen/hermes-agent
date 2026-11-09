#!/usr/bin/env bash
# Build CUDA-enabled linux-rdma/perftest without installing system packages.
set -Eeuo pipefail

PERFTEST_REPO="${PERFTEST_REPO:-https://github.com/linux-rdma/perftest.git}"
PERFTEST_REF="${PERFTEST_REF:-4c260cb26f8c2d990863e71b3a9382893e9562ea}"
SOURCE_DIR="${SOURCE_DIR:-/tmp/perftest-gdr-src}"
OUTPUT_DIR="${OUTPUT_DIR:-/tmp/perftest-gdr}"
DEPS_DIR="${DEPS_DIR:-/tmp/perftest-gdr-deps}"
CUDA_HOME="${CUDA_HOME:-/usr/local/cuda}"
JOBS="${JOBS:-16}"

log() { printf '[cuda-perftest-build] %s\n' "$*"; }
die() { printf '[cuda-perftest-build] ERROR: %s\n' "$*" >&2; exit 1; }
require_command() { command -v "$1" >/dev/null 2>&1 || die "Missing command: $1"; }

for cmd in git make gcc g++ dpkg-deb apt-get ldconfig awk; do require_command "$cmd"; done
[[ -r "$CUDA_HOME/include/cuda.h" ]] || die "Missing $CUDA_HOME/include/cuda.h"
[[ -x "$CUDA_HOME/bin/nvcc" ]] || die "Missing $CUDA_HOME/bin/nvcc"

mkdir -p "$DEPS_DIR" "$OUTPUT_DIR"
if [[ ! -d "$SOURCE_DIR/.git" ]]; then
  git clone --filter=blob:none "$PERFTEST_REPO" "$SOURCE_DIR"
fi
git -C "$SOURCE_DIR" fetch --depth 1 origin "$PERFTEST_REF"
git -C "$SOURCE_DIR" checkout --detach FETCH_HEAD

cppflags=""; ldflags=""
if [[ ! -r /usr/include/x86_64-linux-gnu/pci/pci.h && ! -r /usr/include/pci/pci.h ]]; then
  compgen -G "$DEPS_DIR/libpci-dev_*_amd64.deb" >/dev/null ||
    (cd "$DEPS_DIR" && apt-get download libpci-dev)
  deb_path="$(compgen -G "$DEPS_DIR/libpci-dev_*_amd64.deb" | head -1)"
  dpkg-deb -x "$deb_path" "$DEPS_DIR/root"
  runtime_libpci="$(ldconfig -p | awk '$1 == "libpci.so.3" {print $NF; exit}')"
  ln -sfn "$runtime_libpci" "$DEPS_DIR/root/usr/lib/x86_64-linux-gnu/libpci.so.3"
  cppflags="-I$DEPS_DIR/root/usr/include/x86_64-linux-gnu"
  ldflags="-L$DEPS_DIR/root/usr/lib/x86_64-linux-gnu"
fi

cd "$SOURCE_DIR" && ./autogen.sh
env CPPFLAGS="$cppflags" LDFLAGS="$ldflags" ./configure --enable-cudart CUDA_H_PATH="$CUDA_HOME/include/cuda.h"
make -j"$JOBS"

for binary in ib_write_bw ib_write_lat ib_read_bw ib_read_lat ib_send_bw ib_send_lat; do
  install -m 0755 "$SOURCE_DIR/$binary" "$OUTPUT_DIR/$binary"
done
install -m 0644 "$SOURCE_DIR/libperftest_kernels.so" "$OUTPUT_DIR/libperftest_kernels.so"

log "Build complete: $OUTPUT_DIR"
sha256sum "$OUTPUT_DIR"/ib_* "$OUTPUT_DIR/libperftest_kernels.so"
