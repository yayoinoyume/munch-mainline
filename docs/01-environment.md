# 环境记录

## 主机（WSL2 Ubuntu 26.04）

| 项目 | 值 |
|---|---|
| 内核源码 | Linux 7.3（kernel.org，155 MB tar.xz） |
| 源码位置 | `../munch-mainline-work/src/linux-7.3` |
| CPU / 内存 | 32 核 / 46 GB |
| 磁盘 | 923 GB 可用 |
| Docker | 29.8.2 |
| gcc | 15.2.0 |
| clang | 未安装（候选 21.1.6） |
| 交叉编译器 | 未安装（候选 gcc-aarch64-linux-gnu 15.2） |

## 设备（通过 Windows 侧 adb）

| 项目 | 值 |
|---|---|
| adb 路径 | `/mnt/d/Android/sdk/platform-tools/adb.exe` |
| 设备序列号 | `4fd6a99` |
| slot | `_a` |
| boot 分区大小 | 192 MB |
| vendor_boot | 96 MB |
| dtbo | 32 MB |
| super 剩余 | 约 4.5 GB（slot B 未分配） |
| userdata | 225 GB（已用 41 GB） |
| pstore | 可用，`/sys/fs/pstore/console-ramoops-0` |
| USB gadget | dwc3 dual-role + NCM + configfs |

## 备份

| 文件 | 大小 | sha256 |
|---|---|---|
| `../munch-mainline-work/assets/backup/boot_a.img` | 192 MB | `cb8fae0edeaf246256f9cf965ced8e52e3d86f8abf762a0b0755fd720626aa1d` |

## 待安装（需用户同意）

- `clang-21` + `lld`（编译内核）
- `gcc-aarch64-linux-gnu`（交叉工具链备用）
