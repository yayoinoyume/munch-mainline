# HANDOFF — munch 主线内核移植

> 交接时间：2026-10-30
> 交接原因：用户要在新会话继续，当前会话停止施工

## 0. 一句话现状

调查已完成，方案已定，物料已备齐；**内核还没编译，设备一个字节都没动**。
下一步从"构建 Docker 编译镜像"开始，按第 5 节顺序推进。

## 1. 用户目标与硬约束

- 目标：把 Redmi K40S（`munch` / SM8250）的内核升级到 6.x / 7.x
- 硬约束：**不破坏现有 Android 23.2、Magisk、Rungic Plasma 容器，以及容器内 Ubuntu 的数据和配置**
- 已确认的结论：Android 侧换内核不可行，走"整机主线系统"路线（详见 `docs/00-plan.md`）
- 用户接受：通话、相机、指纹可能废掉；Android 应用会丢失

## 2. 关键事实（新会话必须先读）

### 设备

| 项目 | 值 |
|---|---|
| 型号 | Redmi K40S `munch` / 22021211RC，SM8250 |
| 系统 | LineageOS 23.2（Android 16），`23-20260928-NIGHTLY` |
| 内核 | `4.19.325-cip131-st15-perf-g71b13e62f057`（用户自编译） |
| slot | `_a`（A/B，slot B 空） |
| 加密 | FBE 文件级加密 |
| Root | Magisk 31.0 |
| 容器 | `com.rungic.plasma` 2.24 → LXC `plasma`（Ubuntu 26.04 + KDE） |
| 容器镜像 | `/data/adb/rungic-lxc/images/rootfs.img`（29 GB 实际占用） |

### 分区（实机读数）

| 分区 | 大小 |
|---|---|
| boot_a / boot_b | 192 MB |
| vendor_boot_a / _b | 96 MB |
| dtbo_a / _b | 32 MB |
| super | 8.7 GB（slot A 用 4.2 GB，**剩约 4.5 GB**） |
| userdata | 225 GB（已用 41 GB） |
| GPT | 无空闲分区，userdata 到盘尾 |

### 已实测可用的兜底

- `pstore/ramoops`：`/sys/fs/pstore/console-ramoops-0` 有 223 KB 日志
- USB gadget：`dwc3 dual-role`、`NCM`、`configfs` 都在
- `fastboot boot`：不写 flash，失败重启即回 Android

### 网络与工具

| 项目 | 值 |
|---|---|
| adb | `/mnt/d/Android/sdk/platform-tools/adb.exe`（Windows 侧，WSL 可直连 127.0.0.1:5037） |
| fastboot | `/mnt/d/Android/sdk/platform-tools/fastboot.exe` |
| 设备序列号 | `4fd6a99` |
| kernel.org | 实测 6.5 MB/s，可直连 |
| GitHub raw | 0.67 s，可直连（ghfast 反而慢） |

### 主机

- WSL2 Ubuntu 26.04，32 核 / 46 GB 内存 / 923 GB 空闲
- **无 clang、无 sudo 密码** → 编译走 Docker
- Docker 29.8.2，用户在 docker 组

## 3. 已完成

| 项 | 状态 |
|---|---|
| GitHub 仓库 | https://github.com/yayoinoyume/munch-mainline（public，main 分支） |
| 本地 git 仓库 | `/home/yayoi/projects/munch-mainline` |
| 本地工作区 | `/home/yayoi/projects/munch-mainline-work` |
| Linux 7.3 源码 | 已下载并解压：`work/src/linux-7.3`（2.0 GB） |
| boot_a 备份 | `work/assets/backup/boot_a.img`（192 MB）<br>sha256 `cb8fae0edeaf246256f9cf965ced8e52e3d86f8abf762a0b0755fd720626aa1d` |
| 方案文档 | `docs/00-plan.md`（完整方案 + 调查结论） |
| 环境记录 | `docs/01-environment.md` |
| Dockerfile | `work/Dockerfile.kbuild`（已写，构建被中断，**镜像未完成**） |
| 设备诊断脚本 | `/data/local/tmp/kprobe*.sh`（只读，可删） |

~~**未完成**：Docker 镜像、DTS、defconfig、编译、initramfs、boot.img、任何设备操作。~~

**更新（2026-10-30，构建会话）**：Docker 镜像、DTS、defconfig、Image、dtb、initramfs、
两个 boot.img 全部完成并通过校验，产物在 `../munch-mainline-work/out/`，
细节见 [`docs/03-build-report.md`](03-build-report.md)。
**仍然没做的**：任何设备操作（`fastboot boot` 还没跑过）。

## 4. 目录约定

```
/home/yayoi/projects/
├── munch-mainline/              ← git 仓库，只放可公开内容
│   ├── README.md
│   ├── docs/00-plan.md          完整方案
│   ├── docs/01-environment.md   环境与设备参数
│   ├── docs/02-handoff.md       本文档
│   ├── dts/                     munch 设备树（待写）
│   └── scripts/                 构建/打包脚本（待写）
│
└── munch-mainline-work/         ← 本地工作区，不进 git
    ├── src/linux-7.3/           内核源码
    ├── src/linux-7.3.tar.xz
    ├── out/                     编译产物
    ├── assets/backup/boot_a.img
    ├── logs/
    └── Dockerfile.kbuild
```

## 5. 下一步任务（按顺序，带命令）

### 5.1 完成 Docker 编译镜像

```bash
cd /home/yayoi/projects/munch-mainline-work
timeout 280 docker build -f Dockerfile.kbuild -t munch-kbuild:26.04 .
# 上次在 apt 阶段超时，若再失败：
# 1) 检查 ubuntu:26.04 是否已拉下来：docker images
# 2) 把 Dockerfile 里的 aliyun 源换成 mirrors.tuna.tsinghua.edu.cn
# 3) 或分两步：先 docker run 手动 apt，再 docker commit
```

验证：
```bash
docker run --rm munch-kbuild:26.04 clang --version
docker run --rm munch-kbuild:26.04 ld.lld --version
```

### 5.2 写最小 DTS

- 参考：`work/src/linux-7.3/arch/arm64/boot/dts/qcom/sm8250-xiaomi-elish-common.dtsi`
- 新建：`dts/sm8250-xiaomi-munch.dts` + `dts/sm8250-xiaomi-munch-common.dtsi`
- 第一版只保留：`chosen`、`memory`、`reserved-memory`（含 ramoops）、`ufs_mem_hc`、`usb_1`、`pm8150/pm8150b/pm8150l`、`uart`、`tlmm`
- **不要**写 panel、touch、camera、wifi
- 加入 `Makefile` 条目：`dtb-$(CONFIG_ARCH_QCOM) += sm8250-xiaomi-munch.dtb`
- 关键：`qcom,msm-id` / `qcom,board-id` 必须与 munch 的 bootloader 匹配，从 4.19 的 munch DTS 抄：
  `/home/yayoi/projects/rungic-munch-build-kit/02-kernel/kernel-src/arch/arm64/boot/dts/vendor/qcom/` 下找 `munch*.dts*`

### 5.3 写 defconfig

- 以 `arch/arm64/configs/defconfig` 为底，或参考 elish 的 `pmos.config`
- 必须开：`CONFIG_ARCH_QCOM`、`CONFIG_SERIAL_QCOM_GENI`、`CONFIG_PINCTRL_SM8250`、`CONFIG_CLK_QCOM`、`CONFIG_QCOM_GDSC`、`CONFIG_PHY_QCOM_UFS`、`CONFIG_SCSI_UFS_QCOM`、`CONFIG_USB_DWC3_QCOM`、`CONFIG_PSTORE_RAM`、`CONFIG_DEBUG_LL`（可选）
- 先做成 `arch/arm64/configs/munch_defconfig`

### 5.4 编译

```bash
cd /home/yayoi/projects/munch-mainline-work
docker run --rm \
  -v $PWD/src/linux-7.3:/src \
  -v $PWD/out:/out \
  -w /src munch-kbuild:26.04 \
  bash -lc 'make ARCH=arm64 LLVM=1 O=/out munch_defconfig && make ARCH=arm64 LLVM=1 O=/out -j32 Image dtbs'
```

产物：`out/arch/arm64/boot/Image`、`out/arch/arm64/boot/dts/qcom/sm8250-xiaomi-munch.dtb`

### 5.5 initramfs

- 素材：Alpine minirootfs（`https://dl-cdn.alpinelinux.org/alpine/v3.22/releases/aarch64/`）或静态 busybox
- `init` 脚本要做的三件事：
  1. 挂 `proc/sys/dev`
  2. 往 `/dev/pmsg0` 写 `MUNCH-INIT-REACHED`（pstore 回读用）
  3. 配 `usb0`（RNDIS，172.16.42.1/24）+ 起 `telnetd -l /bin/sh`
- 打包：`find . | cpio -o -H newc | gzip > initramfs.cpio.gz`

### 5.6 打包 boot.img

- 优先用 `magiskboot`（在 `/home/yayoi/projects/rungic-munch-build-kit/06-boot/` 或 Magisk 安装包内）
- 或 `mkbootimg`（Android 工具，header v3）
- ~~结构：kernel = `Image` + dtb（追加），ramdisk = initramfs~~
  **更正（2026-10-30）**：v3 头没有 dtb 字段，追加在后面的 dtb **不会被 ABL 使用**；
  要自带 dtb 必须打 **v2 头**（header 里有 `dtb_size` / `dtb_addr`）。
  实测与产物见 [`docs/03-build-report.md`](03-build-report.md)。
- 校验大小 < 192 MB

### 5.7 `fastboot boot` 验证（**必须用户在场**）

```bash
A=/mnt/d/Android/sdk/platform-tools/adb.exe
F=/mnt/d/Android/sdk/platform-tools/fastboot.exe
$A reboot bootloader
$F devices
$F boot /home/yayoi/projects/munch-mainline-work/out/boot-munch-7.3.img
# 观察 30~60 秒；失败就长按电源键重启
```

成功标志（任一）：
- 主机出现 USB 网卡（RNDIS）
- `telnet 172.16.42.1` 能连
- 重启回 Android 后 `/sys/fs/pstore/console-ramoops-0` 里有 `MUNCH-INIT-REACHED`

## 6. 已知的坑

| 坑 | 说明 |
|---|---|
| sudo 需要密码 | 不要试图 `apt install`，全部走 Docker |
| gh token 无 createRepository | 仓库已由用户手动创建，不要再调创建 API |
| Docker 构建超时 | apt 源慢；换 tuna/aliyun，或分步 commit |
| 编译产物属主 root | 加 `--user $(id -u):$(id -g)` 或在容器里 chown |
| munch 无 UART | 首次启动只能靠 pstore + USB 网络 |
| l11r 面板无驱动 | 这是最可能卡住的点，先跳过 |
| Windows 侧 RNDIS | WSL mirrored 模式可访问 Windows 网卡；若不行，改用 `usbipd` 或 Windows 侧 telnet |
| `fastboot boot` 后 hang | 长按电源键 10 秒强制重启 |
| 不要 `fastboot flash` | 脚本里硬编码禁止 |

## 7. 交接检查清单

新会话开始时请确认：

- [ ] `git -C /home/yayoi/projects/munch-mainline log --oneline` 能看到 4 个 commit
- [ ] `ls /home/yayoi/projects/munch-mainline-work/src/linux-7.3/Makefile` 存在，且 `head -4` 显示 VERSION=7 PATCHLEVEL=3
- [ ] `sha256sum /home/yayoi/projects/munch-mainline-work/assets/backup/boot_a.img` 匹配
- [ ] `/mnt/d/Android/sdk/platform-tools/adb.exe devices` 能看到 `4fd6a99`
- [ ] `docker images` 里还没有 `munch-kbuild:26.04`（需要先构建）
- [ ] 用户确认：继续用 `fastboot boot`，不写分区

## 8. 给新会话的第一句话

> 读 `docs/00-plan.md` 和 `docs/02-handoff.md`，从第 5.1 节继续；所有设备操作只用 `fastboot boot`，绝不 `fastboot flash`。
