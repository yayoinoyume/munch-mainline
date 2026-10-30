#!/usr/bin/env python3
"""反解析 Android boot image（header v2 / v3），用来校验 mkbootimg_v2.py 的产物。

打印 header 各字段，并检查每段是否真的落在文件里、是否按 page_size 对齐。
有任何不一致就以非 0 退出。
"""

import argparse
import hashlib
import struct
import sys
from pathlib import Path

MAGIC = b"ANDROID!"
FDT_MAGIC = b"\xd0\x0d\xfe\xed"


def align(value, page):
    rem = value % page
    return value + (page - rem) if rem else value


def scan_fdt(blob):
    """扫描 blob 里所有 FDT magic，返回 [(偏移, totalsize, 是否正好结束在 blob 末尾)]。

    注意：内核 Image 里本来就可能出现 0xd00dfeed 这种字节序列（纯属数据巧合），
    所以"搜到 magic"不能证明有 appended dtb。真正的判据是
    「偏移 + totalsize == blob 长度」，也就是这个 FDT 正好贴在 kernel 尾部。
    """
    hits = []
    pos = 0
    while True:
        i = blob.find(FDT_MAGIC, pos)
        if i < 0:
            return hits
        totalsize = struct.unpack_from(">I", blob, i + 4)[0] if i + 8 <= len(blob) else 0
        hits.append((i, totalsize, i + totalsize == len(blob)))
        pos = i + 1


def report_kernel_fdt(kernel):
    """打印 kernel 段里的 FDT 情况（appended dtb 的判据）。"""
    hits = scan_fdt(kernel)
    appended = [h for h in hits if h[2]]
    print(f"kernel_fdt_magic_count={len(hits)}")
    if appended:
        off, size, _ = appended[-1]
        print("kernel_appended_dtb=yes")
        print(f"kernel_appended_dtb_offset={off}")
        print(f"kernel_appended_dtb_size={size}")
    else:
        print("kernel_appended_dtb=no")
        if hits:
            print("  (kernel 里那些 0xd00dfeed 是内核数据里的巧合，都不是完整 FDT)")


def main():
    p = argparse.ArgumentParser(description="解析并校验 Android boot image（v2/v3）")
    p.add_argument("image")
    p.add_argument("--quiet", action="store_true", help="只打印关键字段")
    args = p.parse_args()

    data = Path(args.image).read_bytes()
    errors = []

    def check(cond, msg):
        if not cond:
            errors.append(msg)

    check(len(data) >= 4096, "文件不足一个 page")
    check(data[:8] == MAGIC, f"magic 不是 ANDROID!，实际是 {data[:8]!r}")
    if errors:
        print("\n".join(errors))
        sys.exit(1)

    header_version = struct.unpack_from("<I", data, 0x28)[0]
    print(f"file={args.image}")
    print(f"size={len(data)}")
    print(f"sha256={hashlib.sha256(data).hexdigest()}")
    print(f"magic={data[:8].decode()}")
    print(f"header_version={header_version}")

    if header_version == 3:
        kernel_size, ramdisk_size, os_version, header_size = struct.unpack_from("<IIII", data, 8)
        page_size = 4096
        cmdline = data[0x2C:0x2C + 1536].split(b"\x00")[0].decode("utf-8", "replace")
        print(f"page_size={page_size}")
        print(f"header_size={header_size}")
        print(f"os_version=0x{os_version:08x}")
        print(f"kernel_size={kernel_size}")
        print(f"ramdisk_size={ramdisk_size}")
        print(f"cmdline={cmdline!r}")

        check(header_size == 1580, f"v3 header_size 应为 1580，实际 {header_size}")
        kernel_off = page_size
        ramdisk_off = align(kernel_off + kernel_size, page_size)
        end = align(ramdisk_off + ramdisk_size, page_size)
        check(kernel_off + kernel_size <= len(data), "kernel 段超出文件")
        check(ramdisk_off + ramdisk_size <= len(data), "ramdisk 段超出文件")
        check(end == len(data), f"文件长度 {len(data)} 与按 header 计算的 {end} 不一致")
        print(f"kernel_offset={kernel_off}")
        print(f"ramdisk_offset={ramdisk_off}")
        print("dtb_size=0  (header v3 没有 dtb 字段，ABL 不会读 header 里的 dtb)")
        report_kernel_fdt(data[kernel_off:kernel_off + kernel_size])
    elif header_version in (1, 2):
        (kernel_size, kernel_addr, ramdisk_size, ramdisk_addr, second_size, second_addr,
         tags_addr, page_size, hv, os_version) = struct.unpack_from("<IIIIIIIIII", data, 8)
        name = data[0x30:0x40].split(b"\x00")[0].decode("utf-8", "replace")
        cmdline = data[0x40:0x240].split(b"\x00")[0].decode("utf-8", "replace")
        extra_cmdline = data[0x260:0x660].split(b"\x00")[0].decode("utf-8", "replace")
        recovery_dtbo_size, = struct.unpack_from("<I", data, 0x660)
        recovery_dtbo_offset, = struct.unpack_from("<Q", data, 0x664)
        header_size, = struct.unpack_from("<I", data, 0x66C)
        dtb_size, = struct.unpack_from("<I", data, 0x670)
        dtb_addr, = struct.unpack_from("<Q", data, 0x674)

        print(f"page_size={page_size}")
        print(f"header_size={header_size}")
        print(f"os_version=0x{os_version:08x}")
        print(f"name={name!r}")
        print(f"cmdline={cmdline!r}")
        print(f"extra_cmdline={extra_cmdline!r}")
        print(f"kernel_size={kernel_size}")
        print(f"kernel_addr=0x{kernel_addr:08x}")
        print(f"ramdisk_size={ramdisk_size}")
        print(f"ramdisk_addr=0x{ramdisk_addr:08x}")
        print(f"second_size={second_size}")
        print(f"tags_addr=0x{tags_addr:08x}")
        print(f"recovery_dtbo_size={recovery_dtbo_size}")
        print(f"recovery_dtbo_offset={recovery_dtbo_offset}")
        print(f"dtb_size={dtb_size}")
        print(f"dtb_addr=0x{dtb_addr:08x}")

        check(header_size == 1660, f"v2 header_size 应为 1660，实际 {header_size}")
        check(page_size in (2048, 4096, 8192, 16384), f"page_size 异常：{page_size}")
        off = align(page_size, page_size)
        kernel_off, off = off, align(off + kernel_size, page_size)
        ramdisk_off, off = off, align(off + ramdisk_size, page_size)
        second_off, off = off, align(off + second_size, page_size)
        dtbo_off, off = off, align(off + recovery_dtbo_size, page_size)
        dtb_off, off = off, align(off + dtb_size, page_size)
        print(f"kernel_offset={kernel_off}")
        print(f"ramdisk_offset={ramdisk_off}")
        print(f"second_offset={second_off}")
        print(f"recovery_dtbo_offset_actual={dtbo_off}")
        print(f"dtb_offset={dtb_off}")

        check(kernel_off + kernel_size <= len(data), "kernel 段超出文件")
        check(ramdisk_off + ramdisk_size <= len(data), "ramdisk 段超出文件")
        check(dtb_off + dtb_size <= len(data), "dtb 段超出文件")
        check(off == len(data), f"文件长度 {len(data)} 与按 header 计算的 {off} 不一致")
        if dtb_size:
            check(data[dtb_off:dtb_off + 4] == FDT_MAGIC,
                  f"dtb 段起始不是 FDT magic，实际 {data[dtb_off:dtb_off + 4]!r}")
        report_kernel_fdt(data[kernel_off:kernel_off + kernel_size])
    else:
        print(f"header_version={header_version}（本脚本只认 1/2/3）")
        errors.append(f"不支持的 header_version={header_version}")

    if errors:
        print("\n".join(f"校验失败：{e}" for e in errors))
        sys.exit(1)
    print("layout=OK")
    print("校验通过")


if __name__ == "__main__":
    main()
