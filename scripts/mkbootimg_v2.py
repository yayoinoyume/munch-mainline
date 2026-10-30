#!/usr/bin/env python3
"""打包 Android boot image（header v2 带 dtb / header v3 无 dtb），只用标准库。

结构参考 AOSP system/tools/mkbootimg 的 boot_img_hdr：
  v2：header | kernel | ramdisk | second | recovery_dtbo | dtb（每段按 page_size 对齐）
  v3：header | kernel | ramdisk（cmdline 由 vendor_boot bootconfig 提供，这里留空）

用法：
  python3 mkbootimg_v2.py --kernel Image --ramdisk initramfs.cpio.gz \
      --dtb sm8250-xiaomi-munch.dtb --header-version 2 -o boot-v2.img
  python3 mkbootimg_v2.py --kernel Image --ramdisk initramfs.cpio.gz \
      --header-version 3 -o boot-v3.img
"""

import argparse
import hashlib
import struct
import sys
from pathlib import Path

MAGIC = b"ANDROID!"
V2_HEADER_SIZE = 1660
V3_HEADER_SIZE = 1580

# AOSP mkbootimg 的 arm64 默认值（base 0x10000000 + 各段 offset）。
# 这些地址只是 header 字段，Qualcomm ABL 会自行决定加载地址。
ARM64_ADDR = {
    "kernel_addr": 0x10080000,
    "ramdisk_addr": 0x11000000,
    "second_addr": 0x10F00000,
    "tags_addr": 0x10000100,
    "dtb_addr": 0x11F00000,
}


def read(path):
    return Path(path).read_bytes() if path else b""


def pad(data, page_size):
    """补齐到 page_size 的整数倍（已对齐则原样返回）。"""
    rem = len(data) % page_size
    return data + b"\x00" * (page_size - rem) if rem else data


def sha1_id(kernel, ramdisk, second):
    """v2 的 id[32]：sha1(kernel+size) 全 20 字节 + sha1(ramdisk+size+second+size) 前 12 字节。"""
    h = hashlib.sha1()
    h.update(kernel)
    h.update(struct.pack("<I", len(kernel)))
    first = h.digest()

    h = hashlib.sha1()
    h.update(ramdisk)
    h.update(struct.pack("<I", len(ramdisk)))
    h.update(second)
    h.update(struct.pack("<I", len(second)))
    return first + h.digest()[:12]


def build_v2(args, kernel, ramdisk, second, dtb):
    hdr = bytearray()
    hdr += MAGIC
    hdr += struct.pack("<I", len(kernel))
    hdr += struct.pack("<I", args.kernel_addr)
    hdr += struct.pack("<I", len(ramdisk))
    hdr += struct.pack("<I", args.ramdisk_addr)
    hdr += struct.pack("<I", len(second))
    hdr += struct.pack("<I", args.second_addr)
    hdr += struct.pack("<I", args.tags_addr)
    hdr += struct.pack("<I", args.page_size)
    hdr += struct.pack("<I", 2)  # header_version
    hdr += struct.pack("<I", args.os_version)
    hdr += args.name.encode()[:16].ljust(16, b"\x00")
    hdr += args.cmdline.encode()[:512].ljust(512, b"\x00")
    hdr += sha1_id(kernel, ramdisk, second)
    hdr += args.extra_cmdline.encode()[:1024].ljust(1024, b"\x00")
    hdr += struct.pack("<I", 0)  # recovery_dtbo_size：不用 recovery，留 0
    hdr += struct.pack("<Q", 0)  # recovery_dtbo_offset
    hdr += struct.pack("<I", V2_HEADER_SIZE)
    hdr += struct.pack("<I", len(dtb))
    hdr += struct.pack("<Q", args.dtb_addr)
    assert len(hdr) == V2_HEADER_SIZE, len(hdr)

    out = pad(bytes(hdr), args.page_size)
    out += pad(kernel, args.page_size)
    out += pad(ramdisk, args.page_size)
    out += pad(second, args.page_size)
    out += pad(dtb, args.page_size)
    return out


def build_v3(args, kernel, ramdisk):
    hdr = bytearray()
    hdr += MAGIC
    hdr += struct.pack("<I", len(kernel))
    hdr += struct.pack("<I", len(ramdisk))
    hdr += struct.pack("<I", args.os_version)
    hdr += struct.pack("<I", V3_HEADER_SIZE)
    hdr += b"\x00" * 16  # reserved[4]
    hdr += struct.pack("<I", 3)  # header_version
    # v3 的 cmdline 字段按 AOSP 规范留空：真正参数来自 vendor_boot 的 bootconfig
    hdr += b"\x00" * 1536
    assert len(hdr) == V3_HEADER_SIZE, len(hdr)

    out = pad(bytes(hdr), args.page_size)
    out += pad(kernel, args.page_size)
    out += pad(ramdisk, args.page_size)
    return out


def main():
    p = argparse.ArgumentParser(description="打包 Android boot image（v2 带 dtb / v3 无 dtb）")
    p.add_argument("--kernel", required=True)
    p.add_argument("--ramdisk", required=True)
    p.add_argument("--second", default=None)
    p.add_argument("--dtb", default=None, help="仅 header v2 使用")
    p.add_argument("--header-version", type=int, choices=(2, 3), default=2)
    p.add_argument("--page-size", type=int, default=4096)
    p.add_argument("--os-version", type=lambda x: int(x, 0), default=0)
    p.add_argument("--name", default="")
    p.add_argument("--cmdline", default="")
    p.add_argument("--extra-cmdline", default="")
    p.add_argument("--kernel-addr", type=lambda x: int(x, 0), default=ARM64_ADDR["kernel_addr"])
    p.add_argument("--ramdisk-addr", type=lambda x: int(x, 0), default=ARM64_ADDR["ramdisk_addr"])
    p.add_argument("--second-addr", type=lambda x: int(x, 0), default=ARM64_ADDR["second_addr"])
    p.add_argument("--tags-addr", type=lambda x: int(x, 0), default=ARM64_ADDR["tags_addr"])
    p.add_argument("--dtb-addr", type=lambda x: int(x, 0), default=ARM64_ADDR["dtb_addr"])
    p.add_argument("-o", "--output", required=True)
    args = p.parse_args()

    kernel = read(args.kernel)
    ramdisk = read(args.ramdisk)
    second = read(args.second)
    dtb = read(args.dtb)
    if not kernel:
        sys.exit(f"错误：kernel 为空或不存在：{args.kernel}")
    if not ramdisk:
        sys.exit(f"错误：ramdisk 为空或不存在：{args.ramdisk}")
    if args.header_version == 2 and not dtb:
        sys.exit("错误：header v2 需要 --dtb（v2 的价值就在于把 dtb 塞进 boot 镜像）")
    if args.header_version == 3 and (dtb or second):
        sys.exit("错误：header v3 没有 dtb/second 字段，ABL 也不会读；请去掉 --dtb/--second")

    if args.header_version == 2:
        image = build_v2(args, kernel, ramdisk, second, dtb)
    else:
        image = build_v3(args, kernel, ramdisk)

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_bytes(image)
    print(f"写出 {args.output}：{len(image)} 字节 "
          f"(header v{args.header_version}, page {args.page_size})")
    print(f"  kernel {len(kernel)} / ramdisk {len(ramdisk)} / "
          f"second {len(second)} / dtb {len(dtb)}")


if __name__ == "__main__":
    main()
