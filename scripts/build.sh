#!/usr/bin/env bash
# 构建 munch（Redmi K40S / SM8250）Linux 7.3 内核
#
# 做四件事：把 dts 装进内核树、给 dts Makefile 加一行、生成 munch_defconfig、
# 在 Docker 镜像里编译出 Image + sm8250-xiaomi-munch.dtb。
#
# 用法：scripts/build.sh
# 可覆盖的环境变量：SRC（内核源码）、OUT（输出目录）、IMAGE（编译镜像）
set -euo pipefail

REPO=$(cd "$(dirname "$0")/.." && pwd)
SRC=${SRC:-/home/yayoi/projects/munch-mainline-work/src/linux-7.3}
OUT=${OUT:-/home/yayoi/projects/munch-mainline-work/out}
IMAGE=${IMAGE:-munch-kbuild:trixie}
DTS_QCOM="$SRC/arch/arm64/boot/dts/qcom"

install -m 644 "$REPO/dts/sm8250-xiaomi-munch.dts" "$DTS_QCOM/sm8250-xiaomi-munch.dts"

grep -q 'sm8250-xiaomi-munch\.dtb' "$DTS_QCOM/Makefile" \
  || printf 'dtb-$(CONFIG_ARCH_QCOM)\t+= sm8250-xiaomi-munch.dtb\n' >> "$DTS_QCOM/Makefile"

cat "$SRC/arch/arm64/configs/defconfig" "$REPO/scripts/munch_defconfig.fragment" \
  > "$SRC/arch/arm64/configs/munch_defconfig"

mkdir -p "$OUT"
docker run --rm --user "$(id -u):$(id -g)" -e HOME=/tmp \
  -v "$SRC:/src" -v "$OUT:/out" -w /src "$IMAGE" bash -lc '
    set -e
    make ARCH=arm64 LLVM=1 O=/out munch_defconfig
    make ARCH=arm64 LLVM=1 O=/out -j"$(nproc)" Image dtbs
  '

ls -l "$OUT/arch/arm64/boot/Image" \
      "$OUT/arch/arm64/boot/dts/qcom/sm8250-xiaomi-munch.dtb"
