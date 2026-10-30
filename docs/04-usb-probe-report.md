# USB 可观测性改造报告：RNDIS 网卡 + telnet

> 生成时间：2026-10-30
> 结论：**7.3 内核已编入 USB gadget（configfs + RNDIS）能力，initramfs 的 init 改成
> 「配好 usb0 网卡 + 起 telnetd + 保持运行不重启」，两个新镜像已产出并通过本机校验。**
> 本轮**完全没有连接设备**：没有 `fastboot`、没有 `adb`、没有写任何分区。
> 设备只读实测数据沿用上一轮 Lead 提供的结果。

## 0. 本分支的文件来源（先看这个）

本分支（`usb-rndis-observability`，从 `main` 的 `0ede9f2` 起）**原本没有 `scripts/` 和 `dts/`**：
上一轮的脚本和产物留在 `munch-linux73-build` 分支的工作区里，没有提交。所以：

| 文件 | 处理 |
|---|---|
| `scripts/*`（7 个） | 从上一轮工作区复制进本分支，本次改了其中 3 个（见下），原件备份在 `scripts/.backups/` |
| `dts/sm8250-xiaomi-munch.dts` | **只为跑 `scripts/build.sh` 临时创建，构建完已删除**。内容与内核树里已有的文件逐字节相同（sha256 `1256d2d4…`），本轮没有改 DTS |

本轮改的 3 个脚本：

- `scripts/munch_defconfig.fragment`：追加 USB gadget / RNDIS 配置
- `scripts/initramfs-init`：整篇重写（探针不再重启，改成 RNDIS + telnetd + 保持运行）
- `scripts/mkinitramfs.sh`：加 busybox-extras（telnetd 在它里面），并把清空目录的动作挪进容器

上一轮的构建报告在 `munch-linux73-build` 分支的 `docs/03-build-report.md`（本分支没有这个文件），
本文档的 sha256 与它不冲突：那里面 `Image`/`initramfs.cpio.gz` 的哈希已被本轮产物取代，
三个旧 boot 镜像（v2 / v3 / v3-appended）**原样保留、哈希未变**。

## 1. 产物一览

| 产物 | 大小（字节） | sha256 |
|---|---|---|
| `arch/arm64/boot/Image`（重编，带 gadget） | 42,387,968 | `f7b92d91ef14a90f1eab503227579c573a6c947e5ca5a07c2f36eefa47926510` |
| `arch/arm64/boot/dts/qcom/sm8250-xiaomi-munch.dtb`（未变） | 119,812 | `601e7290adab6937c2791b7246de73878d8de81952a555ddfc9934a02b7dc2b0` |
| `initramfs.cpio.gz`（新 init + telnetd） | 4,038,645 | `a33b35edfb56aee234c9863189a0291e2817550e25df2f48d00e3403f9cdfa77` |
| `Image-dtb-usb`（= Image + dtb） | 42,507,780 | `20654832a47b51234b707338359b2d75c07379c9e630a4bcf24fc32a88c3c722` |
| **`boot-munch-v3-appended-usb.img`**（主推） | 46,551,040 | `54476037c8d55cf0c003e633166cb096a209fb033ff54b68ef80eb57b6f09309` |
| **`boot-munch-v3-usb.img`**（对照组） | 46,432,256 | `b64ed4d45c78b38190b97fbb14c76fa0245cbff6bc21c37f294451c37b0090ae` |

- 全部在 `/home/yayoi/projects/munch-mainline-work/out/`，两个镜像都远小于 boot 分区上限 201,326,592 字节（192 MiB）。
- `Image-dtb-usb` 是新名字，没有覆盖上一轮的 `Image-dtb`；`boot-munch-v2-dtb.img` / `boot-munch-v3.img` /
  `boot-munch-v3-appended.img` 三个旧镜像一个字节都没动（哈希与上一轮报告一致）。
- 本轮**不再打 v2 镜像**：ABL 已经拒绝过 v2 头，v2 只剩记录价值。
- 编译耗时：增量 22.7 秒（只重编了 gadget 相关对象），日志
  `logs/build-usb-20261030-2332.log`。

## 2. defconfig 改动与 .config 验收

`scripts/munch_defconfig.fragment` 的 USB 段追加了这些（都要求最终 `.config` 里是 `=y`，
因为 initramfs 里没有 `modprobe`，`=m` 等于没有）：

```
CONFIG_USB_GADGET=y
CONFIG_USB_CONFIGFS=y
CONFIG_USB_CONFIGFS_RNDIS=y
CONFIG_USB_CONFIGFS_NCM=y
CONFIG_USB_CONFIGFS_F_FS=y
CONFIG_USB_F_RNDIS=y
CONFIG_USB_F_NCM=y
CONFIG_USB_U_ETHER=y
CONFIG_PHY_QCOM_QMP_USB=y
CONFIG_CONFIGFS_FS=y
```

**跳过 1 个符号：`CONFIG_USB_GADGET_TARGET`。** 它在 7.3 里存在（`drivers/usb/gadget/legacy/Kconfig:279`），
但 `depends on TARGET_CORE`，而 defconfig 里 `# CONFIG_TARGET_CORE is not set`；它是 USB target
fabric（TCM/UAS），和 RNDIS 无关，强行打开只会白拉一整棵 SCSI target 代码。已在 fragment 里写了注释说明。

从 `out/.config` 里 grep 出来的相关行（全部 `=y`；复现：`docker run --rm -v $OUT:/out munch-kbuild:trixie grep -E '^CONFIG_(USB|PHY_QCOM_QMP_USB|CONFIGFS_FS)' /out/.config`）：

```
CONFIG_USB_GADGET=y
CONFIG_USB_LIBCOMPOSITE=y
CONFIG_USB_U_ETHER=y
CONFIG_USB_F_NCM=y
CONFIG_USB_F_RNDIS=y
CONFIG_USB_F_FS=y
CONFIG_USB_CONFIGFS=y
CONFIG_USB_CONFIGFS_NCM=y
CONFIG_USB_CONFIGFS_RNDIS=y
CONFIG_USB_CONFIGFS_F_FS=y
CONFIG_USB_DWC3=y
CONFIG_USB_DWC3_QCOM=y
CONFIG_PHY_QCOM_QMP_USB=y
CONFIG_PHY_QCOM_USB_SNPS_FEMTO_V2=y
CONFIG_CONFIGFS_FS=y
```

三项硬性验收：`CONFIG_USB_CONFIGFS_RNDIS=y` ✅、`CONFIG_USB_F_RNDIS=y` ✅、`CONFIG_CONFIGFS_FS=y` ✅。

内核里确实编进去了（`out/System.map`，共 98 个 rndis 符号）：

```
ffff800080d19110 T rndis_borrow_net
ffff800080d19160 t rndis_alloc_inst
ffff800080d19464 t rndis_opts_dev_addr_show
ffff80008046317c T configfs_register_subsystem
ffff80008201320c t configfs_init
```

## 3. initramfs 的 init：每一步都留痕

`scripts/initramfs-init`（3,832 字节，`-rwxr-xr-x`）按顺序做这些事，**任何一步失败都不中断**：

1. `mount proc / sysfs / devtmpfs`，再 `mkdir -p /dev/pts /sys/kernel/config`，
   `mount devpts`、`mount -t configfs`。
2. 往 `/dev/kmsg` 和 `/dev/pmsg0` 写 `MUNCH-INIT-REACHED`（老判据还能用）、内核版本、
   `/proc/device-tree/model`、`/proc/device-tree/compatible`、`/proc/cmdline`、`/sys/class/udc`。
3. 在 configfs 里搭 gadget `g1`：`idVendor=0x1d6b`、`idProduct=0x0104`（Linux Foundation
   Multifunction Composite Gadget）、`bcdUSB/bcdDevice=0x0100`、三组字符串、
   配置 `c.1`（`MaxPower=250`）、函数 `rndis.usb0`，再把 `rndis.usb0` 链进 `c.1`。
4. 绑定 UDC：`ls /sys/class/udc | head -1 > /sys/kernel/config/usb_gadget/g1/UDC`。
5. `ifconfig usb0 192.168.42.129/24 netmask 255.255.255.0 up`。
6. 起 `telnetd -l /bin/sh -p 23`。
7. **不 reboot**：`while true; do sleep 5; …; done`，每轮重试 UDC 绑定和 usb0 配置，
   并把 `dmesg | tail -5` 追加进 `/dev/kmsg`。

关键片段（原文）：

```sh
# 跑一条命令并记录成败；失败不中断——探针必须活到主机能连上来
try() {
	what=$1
	shift
	if "$@" >/dev/null 2>&1; then
		log "$what: ok"
	else
		log "$what: FAILED ($*)"
	fi
}

mkdir -p /proc /sys /dev
try "mount /proc" mount -t proc proc /proc
try "mount /sys" mount -t sysfs sysfs /sys
try "mount /dev" mount -t devtmpfs devtmpfs /dev
mkdir -p /dev/pts /sys/kernel/config
try "mount /dev/pts" mount -t devpts devpts /dev/pts
try "mount configfs" mount -t configfs configfs /sys/kernel/config
```

```sh
	mkdir -p "$GADGET/functions/rndis.usb0"
	ln -sf "$GADGET/functions/rndis.usb0" "$GADGET/configs/c.1/rndis.usb0"
	log "gadget: configfs 节点就绪（1d6b:0104，rndis.usb0 链进 c.1）"
}

# UDC 只有 dwc3 probe 完才出现，所以这个函数在启动时和主循环里都会调
bind_udc() {
	# 不能用 -s/-f 判断：sysfs/configfs 属性的 st_size 恒为 4096，-s 永远为真
	[ -n "$(cat "$GADGET/UDC" 2>/dev/null)" ] && return 0
	udc=$(ls /sys/class/udc 2>/dev/null | head -1)
	…
	if echo "$udc" >"$GADGET/UDC" 2>/dev/null; then
		log "udc: 已绑定 $udc"
	…
}
```

```sh
try "net: $IFACE $ADDR netmask $MASK up" ifconfig "$IFACE" "$ADDR" netmask "$MASK" up

if command -v telnetd >/dev/null 2>&1; then
	try "telnetd: 23 端口 /bin/sh" telnetd -l /bin/sh -p 23
elif [ -x /bin/busybox-extras ]; then
	try "telnetd: 23 端口 /bin/sh（busybox-extras）" /bin/busybox-extras telnetd -l /bin/sh -p 23
…
log "init: 保持运行（不重启），等主机连 $ADDR:23"
while true; do
	sleep 5
	bind_udc
	ifconfig "$IFACE" >/dev/null 2>&1 || \
		ifconfig "$IFACE" "$ADDR" netmask "$MASK" up 2>/dev/null
	{
		echo "MUNCH-INIT: tick"
		dmesg 2>/dev/null | tail -5
	} >>"$KMSG" 2>/dev/null
done
```

两处**偏离任务书原文**的地方，都是有原因的：

| 任务书写法 | 实际写法 | 原因 |
|---|---|---|
| `busybox ip` 配 IP | `ifconfig` | Alpine 3.22 的 busybox **没有编 `ip` applet**（`busybox --list` 里没有 `ip`），也没有 `nc`。`ifconfig` 是同一个 busybox 里现成的 applet，做的是同一件事 |
| `telnetd`（busybox 自带） | `telnetd` 来自 **busybox-extras** 包 | 同上：Alpine 主 busybox 里没有 `telnetd`（`strings bin/busybox \| grep telnet` 为 0）。见下一节 |

另外补了 `PATH=/sbin:/usr/sbin:/bin:/usr/bin`：PID 1 的环境是空的，不显式设 PATH 的话
下面所有 applet 都可能找不到，探针会静默变哑巴。

## 4. mkinitramfs.sh 的两处改动

1. **加 busybox-extras**（提供 `telnetd`）：
   `https://mirrors.tuna.tsinghua.edu.cn/alpine/v3.22/main/aarch64/busybox-extras-1.37.0-r20.apk`（66,738 字节，清华源），
   解包出 `/bin/busybox-extras`，再按包自带的 `etc/busybox-paths.d/busybox-extras` 建符号链接
   （`/usr/sbin/telnetd`、`/usr/bin/telnet` 等 15 个）。它是动态链接 musl，rootfs 里的
   `/lib/ld-musl-aarch64.so.1` 已经存在，能跑。
2. **`rm -rf` 挪进容器**：上一轮的 `initramfs-root` 是容器里 root 解包出来的，宿主机的
   `rm -rf "$ROOT"` 会 `Permission denied`，脚本第二次跑就挂。现在清空+重建都在容器里做。

## 5. 验收输出

### 5.1 两个新镜像

```
$ python3 scripts/parse_bootimg.py out/boot-munch-v3-appended-usb.img
file=…/boot-munch-v3-appended-usb.img
size=46551040
sha256=54476037c8d55cf0c003e633166cb096a209fb033ff54b68ef80eb57b6f09309
magic=ANDROID!
header_version=3
page_size=4096
header_size=1580
os_version=0x00000000
kernel_size=42507780
ramdisk_size=4038645
cmdline=''
kernel_offset=4096
ramdisk_offset=42512384
dtb_size=0  (header v3 没有 dtb 字段，ABL 不会读 header 里的 dtb)
kernel_fdt_magic_count=3
kernel_appended_dtb=yes
kernel_appended_dtb_offset=42387968
kernel_appended_dtb_size=119812
layout=OK
校验通过
```

`kernel_appended_dtb_offset=42387968` 正好等于新 `Image` 的字节数，`size=119812` 正好等于 dtb 大小
（`42,387,968 + 119,812 = 42,507,780` = `Image-dtb-usb`）。`kernel_fdt_magic_count=3` = Image 里原有的
2 处假 magic + 1 个真 dtb。

```
$ python3 scripts/parse_bootimg.py out/boot-munch-v3-usb.img
size=46432256
sha256=b64ed4d45c78b38190b97fbb14c76fa0245cbff6bc21c37f294451c37b0090ae
header_version=3
kernel_size=42387968
ramdisk_size=4038645
kernel_fdt_magic_count=2
kernel_appended_dtb=no
layout=OK
校验通过
```

### 5.2 initramfs 里的 /init

```
$ gzip -dc out/initramfs.cpio.gz | cpio -tv | grep -E "(init$|telnetd|busybox-extras)"   # 中间 13 个 busybox-extras 符号链接省略
-rwxr-xr-x   1 root     root       132840 Oct 30 15:35 bin/busybox-extras
lrwxrwxrwx   1 root     root           19 Oct 30 15:35 usr/sbin/telnetd -> /bin/busybox-extras
-rwxr-xr-x   1 root     root         3832 Oct 30 15:35 init
```

（归档里的 `init` 与仓库里的 `scripts/initramfs-init` sha256 完全一致：
`af5e8478db204af0bb3b41a0049565204e9619fbbfd725584d0a22f22c9f2c3b`。）

解包后对 `init` 做字符串检查（验收要求 `rndis` / `telnetd` / `while true` 都在）：

```
configfs     4
rndis        5
telnetd      5
while true   1
usb_gadget   1
ifconfig     3
kmsg         2
pmsg0        2
```

`sh -n init` 在宿主机和容器里都通过。

### 5.3 大小上限

```
46,551,040 < 201,326,592   # boot-munch-v3-appended-usb.img
46,432,256 < 201,326,592   # boot-munch-v3-usb.img
```

## 6. 已知风险与未验证项

| # | 项 | 说明 |
|---|---|---|
| 1 | **135 秒自动重启很可能不是内核 panic，是 bootloader 装的看门狗** | `.config` 里 `CONFIG_QCOM_WDT=m`（模块），initramfs 不加载模块，APSS 看门狗没人喂；`sm8250.dtsi` 里 `watchdog@17c10000`（`qcom,apss-wdt-sm8250`）是 enabled 的。**如果确实是它，设备仍会在 ~135 秒后复位**，telnet 窗口只有两分钟（够抓 dmesg）。修法是一行 `CONFIG_QCOM_WDT=y`，但那是任务书没批准的新决定，本轮没加 |
| 2 | `CONFIG_PANIC_TIMEOUT=0` | 内核 panic 默认不重启（挂着），和「保持运行」的目标一致；不会因为 panic 自己重启 |
| 3 | USB gadget 能不能真的起来 | 完全未验证。DTS 里 `usb_1_dwc3` 已经是 `dr_mode = "peripheral"`、只用 `usb_1_hsphy`，理论上 gadget 能绑上；但 PHY/regulator/UTMI 时钟任何一环没配对，`/sys/class/udc` 就是空的——这时 init 会每 5 秒往 kmsg 写一条「/sys/class/udc 为空」 |
| 4 | 主机侧驱动 | `1d6b:0104` 在 **Linux 主机**上由 `rndis_host` 直接认；**Windows** 侧没有 MS OS descriptor 时可能显示成未知设备（不影响 usbipd-win 把设备转进 WSL，但 Windows 自己不会自动配 RNDIS 网卡）。本轮没加 `os_desc` |
| 5 | pstore 仍会被 Android 覆盖 | init 现在每一步都写 kmsg + pmsg0，但那是**兜底**；真正的证据链是 telnet。设备一重启回 Android，pstore 里的东西可能又没了 |
| 6 | usb0 的 IP 是固定的 | `192.168.42.129/24`（netmask `255.255.255.0`），主机侧要自己配同网段地址（如 `203.0.113.60`）。没有 DHCP |
| 7 | telnet 无认证 | `telnetd -l /bin/sh` 直接给 root shell，任何能连上 23 端口的人都能进。只在临时 `fastboot boot` 的探针里用，别拿去日常跑 |
| 8 | PID 1 不回收子进程 | 没有 `wait`，telnetd 的子进程退出后会留僵尸。探针场景无所谓，跑久了会堆 |
| 9 | 只打了 v3 / v3-appended | v2 头被 ABL 拒绝过，本轮不打；如果两个新镜像都没反应，说明问题不在 dtb 打包方式 |

## 7. 复现命令

```bash
cd <本仓库>
scripts/build.sh          # dts + defconfig + Image + dtb（增量 ~23 秒，全量 ~4 分钟）
scripts/mkinitramfs.sh    # out/initramfs.cpio.gz（Alpine + busybox-extras + 新 init）

OUT=/home/yayoi/projects/munch-mainline-work/out
cat $OUT/arch/arm64/boot/Image \
    $OUT/arch/arm64/boot/dts/qcom/sm8250-xiaomi-munch.dtb > $OUT/Image-dtb-usb
python3 scripts/mkbootimg_v2.py --kernel $OUT/Image-dtb-usb \
  --ramdisk $OUT/initramfs.cpio.gz --header-version 3 \
  -o $OUT/boot-munch-v3-appended-usb.img
python3 scripts/mkbootimg_v2.py --kernel $OUT/arch/arm64/boot/Image \
  --ramdisk $OUT/initramfs.cpio.gz --header-version 3 \
  -o $OUT/boot-munch-v3-usb.img

python3 scripts/parse_bootimg.py $OUT/boot-munch-v3-appended-usb.img
python3 scripts/parse_bootimg.py $OUT/boot-munch-v3-usb.img
```

## 8. 下一步（设备侧，需用户在场）

1. `fastboot boot out/boot-munch-v3-appended-usb.img`（只 boot，不 flash）。
2. 主机侧盯着 USB：Linux 上应出现 `usb 1-1: new high-speed USB device … idVendor=1d6b, idProduct=0104`
   和多一个网卡（`ip link` 里能看到 `usb0`/`enx…`）。
3. 主机配同网段地址后 `telnet 192.168.42.129/24`，进去先看三样：
   `dmesg | head -100`、`cat /proc/device-tree/model`、`dmesg | grep -i -E "udc|dwc3|gadget|rndis"`。
4. 如果 30 秒内主机看不到 USB 设备，就说明 gadget 没起来：重启回 Android 后读
   `/sys/fs/pstore/console-ramoops-0`，搜 `MUNCH-INIT:` 开头的行，能看出卡在 mount、configfs、
   还是 UDC 绑定哪一步。
