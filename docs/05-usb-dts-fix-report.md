# USB 2.0 gadget + 看门狗修复报告

> 生成时间：2026-10-30
> 分支：`usb-dts-fix`（从 `main` 起，本工作区）
> 本轮**没有连接设备**：没有 `fastboot`、没有 `adb`、没有写任何分区，全部是本机编译与校验。

## 0. 一句话结论

**DTS 里 USB 2.0 的三个节点早就在镜像里了，不是根因。** 上一轮 `boot-munch-v3-appended-usb.img`
里追加的 dtb 反编译出来就有 `dr_mode = "peripheral"`、`phys = <&usb_1_hsphy>` 和 HS PHY 的三路
regulator。本轮真正改的是**内核配置**：dwc3 从 Dual Role 切成 gadget-only，并把 APSS 看门狗
编进内核（`CONFIG_QCOM_WDT=y`），另加一条 initramfs 诊断行。新镜像已产出：
`out/boot-munch-v3-appended-usb2.img`（46,555,136 字节，sha256 `2c0fe82e…`）。

## 1. 关键更正：DTS 不是空的（附证据）

任务书说「当前 DTS 只有 `&usb_1 { qcom,select-utmi-as-pipe-clk; status = "okay"; };`」。
核对结果与此不符，逐层验证如下。

### 1.1 仓库里的 DTS（`dts/sm8250-xiaomi-munch.dts`，sha256 `1256d2d4…`）

```dts
&usb_1 {
	qcom,select-utmi-as-pipe-clk;
	status = "okay";
};

&usb_1_dwc3 {
	dr_mode = "peripheral";
	maximum-speed = "high-speed";
	phys = <&usb_1_hsphy>;
	phy-names = "usb2-phy";
};

&usb_1_hsphy {
	vdda-pll-supply = <&vreg_l5a_0p88>;
	vdda18-supply = <&vreg_l12a_1p8>;
	vdda33-supply = <&vreg_l2a_3p1>;
	status = "okay";
};
```

### 1.2 上一轮镜像里**真正被引导的** dtb

把 `out/boot-munch-v3-appended-usb.img` 按 `kernel_offset(4096) + kernel_appended_dtb_offset(42387968)`
切出 119,812 字节，sha256 = `601e7290adab6937c2791b7246de73878d8de81952a555ddfc9934a02b7dc2b0`，
与 `out/arch/arm64/boot/dts/qcom/sm8250-xiaomi-munch.dtb` **逐字节相同**。反编译后：

```dts
usb@a600000 {                       /* = &usb_1_dwc3 */
	compatible = "snps,dwc3";
	reg = <0x00 0xa600000 0x00 0xcd00>;
	...
	phys = <0xb4>;                  /* = &usb_1_hsphy */
	phy-names = "usb2-phy";
	dr_mode = "peripheral";
	maximum-speed = "high-speed";
	...
};

phy@88e3000 {                       /* = &usb_1_hsphy */
	compatible = "qcom,sm8250-usb-hs-phy", "qcom,usb-snps-hs-7nm-phy";
	status = "okay";
	#phy-cells = <0x00>;
	clocks = <0x2e 0x00>;
	resets = <0x30 0x1b>;
	vdda-pll-supply = <0x62>;       /* vreg_l5a_0p88 */
	vdda18-supply = <0xad>;         /* vreg_l12a_1p8 */
	vdda33-supply = <0xae>;         /* vreg_l2a_3p1 */
	phandle = <0xb4>;
};
```

所以「USB 不枚举」不能归因于 DTS 缺节点。**本轮没有改 DTS**（`dts/` 与上一轮 sha256 一致），
新镜像的 dtb 仍是 `601e7290…`，与上一轮相同。

### 1.3 关于「三个节点」的验收口径

`usb_1_dwc3` / `usb_1_hsphy` / `usb_1_dwc3_hs_out` 都是 **label**，label 不会写进 dtb 二进制，
`dtc -I dtb -O dts` 反编译只能看到节点名。对应关系：

| DTS label | 反编译后的节点路径 |
|---|---|
| `usb_1` | `/soc@0/usb@a6f8800` |
| `usb_1_dwc3` | `/soc@0/usb@a6f8800/usb@a600000` |
| `usb_1_hsphy` | `/soc@0/phy@88e3000` |
| `usb_1_dwc3_hs_out` | `/soc@0/usb@a6f8800/usb@a600000/ports/port@0/endpoint` |

`usb_1_dwc3_hs_out` 这个 endpoint 在 `sm8250.dtsi:4248` 就存在，但**是空的**（没有
`remote-endpoint`）：elish 把它接到 `pm8150b_hs_in`（PM8150B 的 Type-C/USB 角色切换端点），
而 munch 的 DTS 没有引入 `pm8150b` 的 USB/Type-C 节点，接不上。**本轮没有补**，理由：
`dr_mode = "peripheral"` 且不写 `usb-role-switch` 时，dwc3 走的是固定 peripheral 路径，
不读这个 graph endpoint；补它需要同时引入 pm8150b 的 typec + vbus regulator 一整串节点，
属于新决策，不在本轮范围。

## 2. 本轮实际改动（3 个文件）

文件来源：本工作区（`session/6bff05f6` → 已改名 `usb-dts-fix`）原本只有 `docs/`。
`dts/` 取自 `munch-linux73-build` 工作区，`scripts/` 取自 `usb-rndis-observability` 工作区
（那两处的内容都是未提交的工作区文件），复制后未改 `dts/`。

| 文件 | 改动 | 备份 |
|---|---|---|
| `scripts/munch_defconfig.fragment` | 追加 dwc3 模式 + 看门狗两段（见 §2.1） | `scripts/.backups/munch_defconfig.fragment.20261030-2348.bak` |
| `scripts/initramfs-init` | 在 `log "udc: …"` 后加一行 `log "watchdog: …"` | `scripts/.backups/initramfs-init.20261030-2348.bak` |
| `docs/05-usb-dts-fix-report.md` | 本文件（新建） | 新建文件，无需备份 |

### 2.1 defconfig 片段新增内容

```
# dwc3 模式：本镜像只做 USB 2.0 外设（DTS 里 dr_mode = "peripheral"），
# 所以从 Dual Role 切成 gadget-only。defconfig 里选的是 USB_DWC3_DUAL_ROLE，
# 它和 USB_DWC3_GADGET 是 Kconfig 的同一个 choice，两个都 =y 时 kconfig 只会
# 保留先出现的那个，所以必须显式 unset，否则这行不生效。
# 代价：dwc3 不再注册 xHCI 主机控制器（本探针不需要主机模式）。
# CONFIG_USB_DWC3_DUAL_ROLE is not set
CONFIG_USB_DWC3_GADGET=y

# APSS 看门狗：bootloader 留下的狗默认在跑（实测约 135 秒咬）。
# qcom_wdt probe 时发现计时器在跑就会用 wdd->timeout（30 秒）重新计时并置
# WDOG_HW_RUNNING，配合 defconfig 里已有的 CONFIG_WATCHDOG_HANDLE_BOOT_ENABLED=y，
# 内核核心会在没有用户态打开时持续喂狗。必须是 =y：initramfs 里没有 modprobe。
CONFIG_QCOM_WDT=y
```

**为什么必须写 `# CONFIG_USB_DWC3_DUAL_ROLE is not set`**：7.3 的
`drivers/usb/dwc3/Kconfig` 里 `USB_DWC3_HOST` / `USB_DWC3_GADGET` / `USB_DWC3_DUAL_ROLE`
是同一个 `choice`。defconfig 里选的是 DUAL_ROLE（`CONFIG_USB_DWC3_DUAL_ROLE=y`），
只在片段里写 `GADGET=y` 会和它冲突，kconfig 解析 choice 时不会稳定地选 GADGET。
显式 unset 之后才是确定的 gadget-only。

### 2.2 initramfs 新增的诊断行

```sh
log "udc: $(ls /sys/class/udc 2>/dev/null | tr '\n' ' ')"
log "watchdog: $(ls /sys/class/watchdog 2>/dev/null | tr '\n' ' ')state=$(cat /sys/class/watchdog/watchdog0/state 2>/dev/null) timeout=$(cat /sys/class/watchdog/watchdog0/timeout 2>/dev/null)"
```

它同时写 `/dev/kmsg`（console-ramoops）和 `/dev/pmsg0`（pmsg-ramoops）。下次上机后
无论 USB 通不通，重启回 Android 读 pstore 就能确认两件事：`/sys/class/udc` 是否为空
（dwc3 有没有 probe 成功）、看门狗有没有被内核接管（`state=active` + `timeout=30`）。

## 3. 产物与哈希

| 产物 | 字节 | sha256 |
|---|---|---|
| `out/arch/arm64/boot/Image`（重编） | 42,387,968 | `a1d6e0e051314436b9564fd00034e0f492f281daea7bf38eb0be9df537895f55` |
| `out/arch/arm64/boot/dts/qcom/sm8250-xiaomi-munch.dtb`（未变） | 119,812 | `601e7290adab6937c2791b7246de73878d8de81952a555ddfc9934a02b7dc2b0` |
| `out/initramfs.cpio.gz`（新 init） | 4,038,669 | `af673c967b7d45ae8f868d17e3e4b5d16162c709832209156735bafa3036e075` |
| `out/Image-dtb-usb2`（= Image + dtb） | 42,507,780 | `ce841e2fd3b12d2d635bca9d60f3eb442c4212a77deeb6718a44823db2a0a90b` |
| **`out/boot-munch-v3-appended-usb2.img`** | **46,555,136** | **`2c0fe82e1e60614140fd8f44e45f7e7d25fe2ed9ab74dcd2047dfa587237c086`** |

- 46,555,136 < 201,326,592（boot 分区上限 192 MiB）✅
- 编译耗时 22.9 秒（增量，配置改动触发的重编），日志 `logs/build-usb2-20261030-2349.log`
- `Image` 字节数与上一轮相同（42,387,968），但内容不同（sha 变了）：dwc3 去掉主机侧代码、
  加入 qcom_wdt，尺寸刚好抵消。

**旧产物一个字节都没动**（与 `docs/03`/`docs/04` 记录的哈希一致）：

| 产物 | sha256 |
|---|---|
| `boot-munch-v2-dtb.img` | `267aa4457d7563f79dca5cb387b2198056e198dadbba8009e364ea476866ed91` |
| `boot-munch-v3.img` | `82ebc003497ceb2a614e3de5a00094606971145b35dc869c6a044b8d2682e89f` |
| `boot-munch-v3-appended.img` | `a072beb5bdc7a0b6a065a5bd6508ecb003fe80572d61552176b77fd95d97ca53` |
| `boot-munch-v3-appended-usb.img` | `54476037c8d55cf0c003e633166cb096a209fb033ff54b68ef80eb57b6f09309` |
| `boot-munch-v3-usb.img` | `b64ed4d45c78b38190b97fbb14c76fa0245cbff6bc21c37f294451c37b0090ae` |
| `Image-dtb-usb` | `20654832a47b51234b707338359b2d75c07379c9e630a4bcf24fc32a88c3c722` |

本轮**没有**打 `v3-usb2` 对照组（任务书只要求 appended 版本）。

## 4. 验收输出

### 4.1 `parse_bootimg.py`

```
$ python3 scripts/parse_bootimg.py out/boot-munch-v3-appended-usb2.img
file=…/boot-munch-v3-appended-usb2.img
size=46555136
sha256=2c0fe82e1e60614140fd8f44e45f7e7d25fe2ed9ab74dcd2047dfa587237c086
magic=ANDROID!
header_version=3
page_size=4096
header_size=1580
os_version=0x00000000
kernel_size=42507780
ramdisk_size=4038669
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

### 4.2 新镜像里 dtb 的 USB 片段（`dtc -I dtb -O dts`）

```dts
usb@a6f8800 {                                   /* &usb_1 */
	compatible = "qcom,sm8250-dwc3", "qcom,dwc3";
	status = "okay";
	clock-names = "cfg_noc", "core", "iface", "sleep", "mock_utmi", "xo";
	interrupt-names = "pwr_event", "hs_phy_irq", "dp_hs_phy_irq", "dm_hs_phy_irq", "ss_phy_irq";
	power-domains = <0x30 0x05>;            /* GCC USB30_PRIM_GDSC */
	resets = <0x30 0x22>;
	qcom,select-utmi-as-pipe-clk;

	usb@a600000 {                           /* &usb_1_dwc3 */
		compatible = "snps,dwc3";
		reg = <0x00 0xa600000 0x00 0xcd00>;
		interrupts = <0x00 0x85 0x04>;
		iommus = <0x31 0x00 0x00>;
		snps,dis_u2_susphy_quirk;
		snps,dis_enblslpm_quirk;
		snps,dis-u1-entry-quirk;
		snps,dis-u2-entry-quirk;
		phys = <0xb4>;                  /* &usb_1_hsphy */
		phy-names = "usb2-phy";
		dr_mode = "peripheral";
		maximum-speed = "high-speed";

		ports {
			#address-cells = <0x01>;
			#size-cells = <0x00>;

			port@0 {
				reg = <0x00>;

				endpoint {              /* &usb_1_dwc3_hs_out，未接 pm8150b_hs_in */
				};
			};

			port@1 {
				reg = <0x01>;

				endpoint {
					remote-endpoint = <0xb5>;
					phandle = <0xaf>;
				};
			};
		};
	};
};

phy@88e3000 {                                   /* &usb_1_hsphy */
	compatible = "qcom,sm8250-usb-hs-phy", "qcom,usb-snps-hs-7nm-phy";
	reg = <0x00 0x88e3000 0x00 0x400>;
	status = "okay";
	#phy-cells = <0x00>;
	clocks = <0x2e 0x00>;
	clock-names = "ref";
	resets = <0x30 0x1b>;
	vdda-pll-supply = <0x62>;               /* vreg_l5a_0p88 */
	vdda18-supply = <0xad>;                 /* vreg_l12a_1p8 */
	vdda33-supply = <0xae>;                 /* vreg_l2a_3p1 */
	phandle = <0xb4>;
};
```

反编译共 33 条 warning，全部是 `unique_unit_address` 一类（`sm8250.dtsi` 里
`geniqup` 下 i2c/spi/serial 同址），与本次改动无关，上一轮反编译同样存在。

### 4.3 看门狗节点（dtb 里默认启用，无 `status` 属性即 okay）

```dts
watchdog@17c10000 {
	compatible = "qcom,apss-wdt-sm8250", "qcom,kpss-wdt";
	reg = <0x00 0x17c10000 0x00 0x1000>;
	clocks = <0x2f>;
	interrupts = <0x00 0x00 0x01>;
};
```

### 4.4 `.config`

```
$ grep -E 'USB_DWC3|USB_GADGET=|QCOM_WDT|WATCHDOG' out/.config
CONFIG_WATCHDOG=y
CONFIG_WATCHDOG_CORE=y
CONFIG_WATCHDOG_HANDLE_BOOT_ENABLED=y
CONFIG_WATCHDOG_OPEN_TIMEOUT=0
CONFIG_QCOM_WDT=y
CONFIG_USB_DWC3=y
CONFIG_USB_DWC3_GADGET=y
# CONFIG_USB_DWC3_DUAL_ROLE is not set
CONFIG_USB_GADGET=y
CONFIG_USB_ROLE_SWITCH=y
CONFIG_USB_CONFIGFS_RNDIS=y
```

符号确实进了 Image（`out/System.map`）：

```
ffff800080db197c t qcom_wdt_probe
ffff800080c646e4 T dwc3_gadget_init
ffff800080c5ef80 T dwc3_core_init
```

（`grep -c qcom_wdt System.map` = 15 条。）

### 4.5 initramfs 里的 `/init`

归档里的 `init` 与仓库 `scripts/initramfs-init` 同哈希：`4cbb8f0d…`，4,025 字节，
`sh -n` 通过，含新增的 `watchdog:` 行（见 §2.2）。

## 5. 看门狗为什么这样就够（已核对驱动源码）

`drivers/watchdog/qcom-wdt.c:348`（7.3）：

```c
if (qcom_wdt_is_running(&wdt->wdd)) {
	qcom_wdt_start(&wdt->wdd);
	set_bit(WDOG_HW_RUNNING, &wdt->wdd.status);
}
```

- `wdt->wdd.timeout = min(max_timeout, 30U)`（第 339 行）：probe 时把计时器按 30 秒重装。
- `CONFIG_WATCHDOG_HANDLE_BOOT_ENABLED=y`（defconfig 里本来就有）：watchdog 核心在没有
  用户态打开设备时，会替 `WDOG_HW_RUNNING` 的狗持续喂。
- 节点 `watchdog@17c10000` 没有 `status` 属性 → 默认 okay，驱动会 probe。

所以 `=m` 改 `=y` 之后，**不需要 initramfs 里做任何事**，狗就有人喂了。这也解释了
「135 秒自动重启」：上一轮 `CONFIG_QCOM_WDT=m`，initramfs 里没有 `modprobe`，
bootloader 留下的狗一直没人喂。

> 前提假设：135 秒复位确实是 APSS 看门狗。本轮无法在设备上确认（禁止设备操作）。
> 如果 `=y` 之后仍然 135 秒复位，说明是别的机制（例如 ABL 自己的超时），
> 那时看 `/sys/class/watchdog/watchdog0/state` 是不是 `active`。

## 6. 仍未解决的问题（下一轮上机要看的）

DTS 和 gadget 配置都齐了，USB 仍不枚举的可能原因按嫌疑排序：

| # | 嫌疑 | 上机怎么判 |
|---|---|---|
| 1 | dwc3 probe 失败 / 一直 defer：`iommus = <&apps_smmu 0x0 0x0>` 配合 `CONFIG_ARM_SMMU_DISABLE_BYPASS_BY_DEFAULT=y`，fastboot 引导时 SMMU 的 stream mapping 是 XBL 按 Android 内核配的，未必覆盖我们 | pstore 里看 `MUNCH-INIT: udc:` 是否为空；有 telnet 时 `dmesg \| grep -i -E "dwc3\|smmu\|iommu"` |
| 2 | 时钟/电源域没起来（GCC USB30_PRIM_GDSC） | 同上，dmesg 里会有 `failed to get clock` / `-EPROBE_DEFER` |
| 3 | initramfs 根本没跑（内核在 init 之前就卡住），135 秒是看门狗收尾 | pstore 里**完全没有** `MUNCH-INIT-REACHED` |
| 4 | 内核 panic 后挂住（`CONFIG_PANIC_TIMEOUT=0`），USB 来不及枚举 | pstore 里有 panic/oops 记录 |
| 5 | 主机侧（Windows/usbipd）没认 RNDIS 的 1d6b:0104 | 换 Linux 主机或看 `lsusb` 有没有设备出现 |

## 7. 复现命令

```bash
cd <本仓库>
scripts/build.sh          # dts + defconfig + Image + dtb（增量 ~23 秒）
scripts/mkinitramfs.sh    # out/initramfs.cpio.gz（用 build/ 里已缓存的 Alpine 包，不联网）

OUT=/home/yayoi/projects/munch-mainline-work/out
cat $OUT/arch/arm64/boot/Image \
    $OUT/arch/arm64/boot/dts/qcom/sm8250-xiaomi-munch.dtb > $OUT/Image-dtb-usb2
python3 scripts/mkbootimg_v2.py --kernel $OUT/Image-dtb-usb2 \
  --ramdisk $OUT/initramfs.cpio.gz --header-version 3 \
  -o $OUT/boot-munch-v3-appended-usb2.img

python3 scripts/parse_bootimg.py $OUT/boot-munch-v3-appended-usb2.img
```

## 8. 无设备操作声明

本轮全程只在本机做：`docker` 里编译内核、`dtc` 反编译、Python 读写镜像字节。
**没有执行 `fastboot`、`adb`、`usbipd`，没有连接 K40S，没有读写任何分区。**
