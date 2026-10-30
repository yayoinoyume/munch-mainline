#!/usr/bin/env bash
# 构建最小 initramfs：Alpine minirootfs（aarch64，清华镜像）+ 探针 init 脚本
#
# 产物：out/initramfs.cpio.gz（newc + gzip -9）
# 可覆盖的环境变量：WORK（工作区）、IMAGE（含 cpio 的镜像）、VERSION（Alpine 版本）、
#                   ALPINE_BRANCH（Alpine 分支）、BBX_VERSION（busybox-extras 版本）、
#                   MIRROR（镜像站根地址）
#
# 为什么要 busybox-extras：Alpine 的主 busybox 没编 telnetd（`busybox --list` 里没有），
# telnetd 只在 busybox-extras 包里。两个包都从同一个镜像站拿，版本对齐 Alpine 分支。
set -euo pipefail

REPO=$(cd "$(dirname "$0")/.." && pwd)
WORK=${WORK:-/home/yayoi/projects/munch-mainline-work}
IMAGE=${IMAGE:-munch-kbuild:trixie}
VERSION=${VERSION:-3.22.7}
ALPINE_BRANCH=${ALPINE_BRANCH:-3.22}
BBX_VERSION=${BBX_VERSION:-1.37.0-r20}
MIRROR=${MIRROR:-https://mirrors.tuna.tsinghua.edu.cn/alpine}

ROOTFS_URL="$MIRROR/v$ALPINE_BRANCH/releases/aarch64/alpine-minirootfs-${VERSION}-aarch64.tar.gz"
ROOTFS_TARBALL="$WORK/build/alpine-minirootfs-${VERSION}-aarch64.tar.gz"
BBX_URL="$MIRROR/v$ALPINE_BRANCH/main/aarch64/busybox-extras-${BBX_VERSION}.apk"
BBX_APK="$WORK/build/busybox-extras-${BBX_VERSION}.apk"
OUT="$WORK/out/initramfs.cpio.gz"

mkdir -p "$WORK/build" "$WORK/out"
if [ ! -f "$ROOTFS_TARBALL" ]; then
  echo "下载 $ROOTFS_URL"
  timeout 300 curl -fL --retry 2 -o "$ROOTFS_TARBALL" "$ROOTFS_URL"
fi
if [ ! -f "$BBX_APK" ]; then
  echo "下载 $BBX_URL"
  timeout 120 curl -fL --retry 2 -o "$BBX_APK" "$BBX_URL"
fi

# 清空和重建都在容器里做（root）：上一次解包出来的文件属主是 root，宿主机 rm 不掉
docker run --rm -e "ALPINE_VERSION=$VERSION" -e "BBX_VERSION=$BBX_VERSION" \
  -v "$WORK:/work" -v "$REPO:/repo:ro" -w /work "$IMAGE" bash -lc '
  set -e
  rm -rf /work/build/initramfs-root /work/build/busybox-extras
  mkdir -p /work/build/initramfs-root /work/build/busybox-extras
  tar -xzf "/work/build/alpine-minirootfs-$ALPINE_VERSION-aarch64.tar.gz" -C /work/build/initramfs-root
  # busybox-extras 的 .apk 就是 tar.gz（签名+控制段+数据段连在一起），直接解
  tar -xzf "/work/build/busybox-extras-$BBX_VERSION.apk" -C /work/build/busybox-extras 2>/dev/null
  install -m 755 /work/build/busybox-extras/bin/busybox-extras /work/build/initramfs-root/bin/busybox-extras
  # 按包自带的 applet 路径表建符号链接（usr/sbin/telnetd 等）
  while read -r p; do
    [ -n "$p" ] || continue
    mkdir -p "/work/build/initramfs-root/${p%/*}"
    ln -sf /bin/busybox-extras "/work/build/initramfs-root/$p"
  done < /work/build/busybox-extras/etc/busybox-paths.d/busybox-extras
  install -m 755 /repo/scripts/initramfs-init /work/build/initramfs-root/init
  cd /work/build/initramfs-root
  find . -print0 | cpio --null -o -H newc 2>/dev/null | gzip -9 > /work/out/initramfs.cpio.gz
'

gzip -t "$OUT"
echo "--- 产物"
ls -l "$OUT"
echo "--- 关键内容（init / telnetd / busybox-extras，含权限位）"
docker run --rm -v "$WORK:/work" "$IMAGE" bash -lc '
  gzip -dc /work/out/initramfs.cpio.gz | cpio -tv 2>/dev/null | grep -E "(init$|telnetd|busybox-extras)"
'
