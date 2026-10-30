# 构建报告：Linux 7.3 for munch（Redmi K40S / SM8250）

> 生成时间：2026-10-30（已按 Lead 的设备实测数据修订，见第 2 节）
> 结论：**内核、设备树、initramfs、两个 boot 镜像全部产出并通过本机校验**，等待安排实机 `fastboot boot`。
> 全程**没有连接设备**：没有 `fastboot`、没有 `adb reboot`、没有 `adb flash`、没有 `adb push`。
> 设备只读实测数据由 Lead 提供，本报告只负责按数据改 DTS，没有自己连设备。

## 1. 产物一览

| 产物 | 大小（字节） | sha256 |
|---|---|---|
| `Image` | 42,183,168 | `6accbd7fa5a20ac2e68308f3600493d2aa9e757682db7d26b314bce81a3172ac` |
| `sm8250-xiaomi-munch.dtb` | 119,812 | `601e7290adab6937c2791b7246de73878d8de81952a555ddfc9934a02b7dc2b0` |
| `initramfs.cpio.gz` | 3,974,543 | `297618e76537242a301633ad1e610c59ff6ead0408feee98122cea01eb26e2c9` |
| `boot-munch-v2-dtb.img`（主实验品） | 46,288,896 | `267aa4457d7563f79dca5cb387b2198056e198dadbba8009e364ea476866ed91` |
| `boot-munch-v3.img`（对照组） | 46,166,016 | `82ebc003497ceb2a614e3de5a00094606971145b35dc869c6a044b8d2682e89f` |
| `Image-dtb`（Image + dtb 拼接） | 42,302,980 | `7f4f7738cdb2e0054cad65487c7c8a62aa3296eed314a1e259f787a46d144e17` |
| `boot-munch-v3-appended.img`（备选） | 46,284,800 | `a072beb5bdc7a0b6a065a5bd6508ecb003fe80572d61552176b77fd95d97ca53` |

内核：`Linux version 7.3.0 ... #4 SMP PREEMPT Fri Oct 30 14:59:23 UTC 2026`，Debian clang 19.1.7 + LLD 19.1.7。

> 改动 DTS 后重编过一次，内核内嵌了新的构建时间戳，所以 `Image` 的 sha256 与上一版不同（大小一样）。
> **以上表为准**，旧的 sha256 作废。

boot 分区 192 MiB（201,326,592 字节），三个镜像都远小于上限。
产物目录 `/home/yayoi/projects/munch-mainline-work/out/`，日志在 `.../logs/`。

### 1.1 三个 boot 镜像的对照表

三个镜像的 **kernel 都是同一个 `Image`**（v3-appended 用的是 `Image` + dtb 的拼接体），
唯一变量就是打包方式。

| 镜像 | header 版本 | dtb 在哪 | 预期 ABL 行为 |
|---|---|---|---|
| `boot-munch-v2-dtb.img` | v2 | header 的 `dtb_size`/`dtb_addr` 指向独立 dtb 段 | ABL 按 msm-id/board-id 从 dtb 段里挑 DT。**这是首选**：v2 头就是给「一个镜像自带 DT」设计的 |
| `boot-munch-v3.img` | v3 | 没有 dtb | ABL 用 vendor_boot + dtbo 里的厂商 DT 引导我们的内核。**对照组**：用来区分「内核起不来」和「ABL 没用我们的 dtb」 |
| `boot-munch-v3-appended.img` | v3 | 追加在 kernel 段末尾（`Image-dtb`） | 高通 LK/ABL 传统上会在 kernel 尾部找 FDT magic 直接用。**v2 被拒后的备选**，同样不写分区 |

> ⚠️ 关于「kernel 里能搜到 0xd00dfeed」：**原版 `Image` 里本来就有 2 处这个字节序列**
> （offset 0x17af760、0x1882dc0，是内核数据里的巧合，totalsize 分别只有 730/131 字节，
> 都不结束在 kernel 末尾）。所以「搜到 magic」不能当判据，`parse_bootimg.py` 用的是
> 「偏移 + totalsize == kernel 段长度」这个精确判据，输出 `kernel_appended_dtb=yes/no`。

## 2. 设备实测数据（Lead 只读实测，DTS 按此写）

### 2.1 内存：12 GB，三段不连续

`/proc/device-tree/memory/reg` 原始字节解析（#address-cells=2, #size-cells=2）：

| 段 | 物理范围 | 大小 |
|---|---|---|
| 1 | `0x80000000 - 0xb9900000` | 921.6 MB |
| — | `0xb9900000 - 0xc0000000` | **空洞，不能合并** |
| 2 | `0xc0000000 - 0x200000000` | 5 GB |
| 3 | `0x200000000 - 0x380000000` | 6 GB |

DTS 里用 **3 条 reg** 表达。注意第二段的 size 必须写成高低位 `<0x01 0x40000000>`（= 5 GB），
写成单个 `<0x140000000>` 会被 dtc **静默截断成 1 GB**：

```dts
memory@80000000 {
    device_type = "memory";
    reg = <0x00 0x80000000 0x00 0x39900000>,   /* 921.6 MB */
          <0x00 0xc0000000 0x01 0x40000000>,   /* 5 GB  */
          <0x02 0x00000000 0x01 0x80000000>;   /* 6 GB  */
};
```

设备 `/proc/iomem` 实读佐证——三段之间确实没有 System RAM：

```
92700000-b03fffff : System RAM
  b0000000-b03fffff : reserved        ← Android ramoops 的 4 MB，地址完全对上
b1400000-b98fffff : System RAM
c0000000-ffbfffff : System RAM
ffc20000-37fffffff : System RAM
```

- `0xb9900000-0xbfffffff` 不在任何 System RAM 段里 → **硬件空洞，绝不能合并进 memory**
- `0xb0000000-0xb0400000` 是 Android 的 ramoops → 我们的 ramoops 节点照抄这个地址
- `0xb0400000-0xb1400000` 是 disp_rdump 保留区 → 同样不在 System RAM 里

（Lead 原文写的是 `device-type`，是笔误；内核靠 `device_type = "memory"` 识别内存节点，已按正确写法落地。）

### 2.2 ramoops：0xb0000000，4 MB

Android 4.19 靠 cmdline `ramoops_memreserve=4M`，DT 里没有 ramoops 节点，所以主线要自己加：

```dts
ramoops@b0000000 {
    compatible = "ramoops";
    reg = <0x0 0xb0000000 0x0 0x400000>;
    record-size = <0x40000>;
    console-size = <0x200000>;
    pmsg-size = <0x200000>;
};
```

- 边界：`0xb0400000` 起是 Android 的 `disp_rdump_region`，ramoops 正好到 `0xb0400000`，不重叠。
- **`record-size` 实际不生效**（不是写错）：`console 0x200000 + pmsg 0x200000` 正好占满 4 MB，
  `fs/pstore/ram.c` 算出的 dmesg 区大小 `dump_mem_sz = 0`，驱动对 0 大小直接跳过。
  这不影响两条真正要用的通道：`console-ramoops`（内核日志）和 `pmsg-ramoops`（我们的标记）。
- 没加 `no-map`：默认 `mem_type` 是 `MEM_TYPE_NORMAL`，驱动走 `vmap` 逐页映射路径，不需要 no-map。

### 2.3 reserved-memory：一个都没删

`sm8250.dtsi` 里已有的 reserved-memory 节点（hyp / xbl_aop / cmd_db / smem / removed / camera /
wlan / ipa / gpu / npu / video / cvp / cdsp / slpi / adsp / spss / cdsp_secure_heap /
adsp_rpc_remote_heap）**全部保留**，只新增了 ramoops。那些是固件真正占用的内存，删了内核会踩进去。

### 2.4 board-id：实测确认

`/proc/device-tree/qcom,board-id` = `0000 0032 0000 0000` → `<0x32 0>`，与 DTS 里的 `<50 0>` 一致。
`qcom,msm-id` 也吻合：vendor 树里 munch 的 DT 就是 `kona.dtsi`（`356 0x10000`）+ `munch-sm8250-overlay.dts`（`50 0`）。

### 2.5 充电芯片（后续阶段用，本次 DTS 不含充电节点）

`/sys/class/power_supply/` 实读：`bq2597x-master`、`bq2597x-slave`、`bms`、`main`、`usb`、`dc`、`pc_port`。
**是 TI bq2597x（master + slave 双芯片），不是 ln8000。** 主线没有 bq2597x 驱动，后续要自己写或移植。

## 3. 镜像源清单

全部走国内源，**没有直连 Docker Hub、没有用官方 apt 源、没有用本地代理**。

| 用途 | 源 | URL | 说明 |
|---|---|---|---|
| Docker 基础镜像 | DaoCloud | `docker.m.daocloud.io/library/debian:trixie` | `dockerproxy.net` 拉取报 EOF，`docker.yayoi.uk` 返回 429（限流），改用 daocloud 成功 |
| apt 包 | 清华 | `http://mirrors.tuna.tsinghua.edu.cn/debian` | 测速：tuna 11.1 MB/s、aliyun 15.4 MB/s（`Packages.xz` 9.7 MB）；两者都可用，选 tuna |
| initramfs 基础 | 清华 | `https://mirrors.tuna.tsinghua.edu.cn/alpine/v3.22/releases/aarch64/alpine-minirootfs-3.22.7-aarch64.tar.gz` | 3,971,679 字节，sha256 `7e9b34ff3304381909e566e2c93de450664ccc724191261423974fc121c11623` |

两个坑（已解决，记下来免得重踩）：

1. **官方 `debian:trixie` 镜像里没有 `ca-certificates`**（`/etc/ssl/certs` 不存在），apt 走 https 会报
   `certificate verify failed`。所以 apt 源用 `http://`——apt 仍会做 GPG 签名校验，包完整性不受影响。
2. `docker.yayoi.uk` 对 `debian` 清单请求返回 `429 Too Many Requests`，是限流，不是配置问题。

## 4. Docker 编译镜像

- 镜像 tag：`munch-kbuild:trixie`
- 镜像 ID：`sha256:27741ee8f4b4bd2d1732c13b69d94e1c9966b43f4f139c73a07071597724ff3a`
- 大小：1.14 GB（压缩后 281 MB）
- 定义文件：[`scripts/Dockerfile.kbuild`](../scripts/Dockerfile.kbuild)
- 构建命令：`timeout 900 docker build -f scripts/Dockerfile.kbuild -t munch-kbuild:trixie .`

装进去的工具：clang / lld / llvm / make / bc / bison / flex / libssl-dev / libelf-dev /
python3 / perl / rsync / cpio / gzip / xz-utils / git / curl / device-tree-compiler / ca-certificates。

## 5. 源码树改动清单（重要，请审）

任务书里有两句话互相冲突：

- 「不许改 `src/linux-7.3` 里的源码文件」
- 但步骤 3 要求「在 `arch/arm64/boot/dts/qcom/Makefile` 加一行」、步骤 4 要求「生成 `arch/arm64/configs/munch_defconfig`」

处理方式：**只新增设备支持文件，一行驱动源码都没动**。

| 文件 | 动作 | 说明 |
|---|---|---|
| `arch/arm64/boot/dts/qcom/sm8250-xiaomi-munch.dts` | 新增 | 从仓库 `dts/` 复制，内容完全相同 |
| `arch/arm64/boot/dts/qcom/Makefile` | 追加 1 行 | `dtb-$(CONFIG_ARCH_QCOM) += sm8250-xiaomi-munch.dtb` |
| `arch/arm64/configs/munch_defconfig` | 新增 | `defconfig` + `scripts/munch_defconfig.fragment` 拼接 |

- 改动前的 `Makefile` 备份：`../munch-mainline-work/assets/backup/qcom-Makefile.20261030-2233.bak`
  （sha256 `b78adb4942092b1e0cd4ea4cf115b08becbc99d659d41ee97090fbb3d0030119`，与改动前一致）
- 编译产物全部在 `O=out`，源码树里没有 `.o` / `.config` 残留。

### 5.1 文档修正

| 文件 | 改了什么 |
|---|---|
| `docs/00-plan.md` | 2.4 表格「触摸」行：~~主线有 focaltech 通用驱动~~ → 主线只有 `edt-ft5x06`（FT5x06/FT6x06/FT3518），**不支持 ft3658u** |
| `docs/02-handoff.md` | 5.6：~~kernel = Image + dtb（追加）~~ → v3 头没有 dtb 字段，追加的 dtb 不会被 ABL 使用，要自带 dtb 必须打 v2 头 |
| `docs/02-handoff.md` | 3 节「未完成」：标注构建已全部完成、设备操作仍未做 |
| `README.md` | 阶段表状态更新，加一条指向本报告的链接 |

改前的原件备份在 `../munch-mainline-work/assets/backup/docs/*.bak`（带时间戳），
**故意没放进仓库**，免得被 `git add -A` 带进提交。

另外还有一处同类错误**没有改**（不在本次任务范围，留给 Lead 决定）：
`docs/00-plan.md` 3.2 阶段表第 4 行写「打包 boot.img | header v3，大小 < 192 MB」，
按本次实测，要带 dtb 就得用 v2 头。

## 6. 验收命令与实际输出

### 6.1 工具链（要求 clang ≥ 17）

```
$ docker run --rm munch-kbuild:trixie clang --version
Debian clang version 19.1.7 (3+b1)
Target: x86_64-pc-linux-gnu
Thread model: posix

$ docker run --rm munch-kbuild:trixie ld.lld --version
Debian LLD 19.1.7 (compatible with GNU linkers)
```

### 6.2 Image 架构

```
$ file out/arch/arm64/boot/Image
out/arch/arm64/boot/Image: Linux kernel ARM64 boot executable Image, little-endian, 4K pages
```

### 6.3 设备树内容（host 没有 dtc，用编译镜像里的 dtc）

```
$ docker run --rm -v $PWD/out:/out munch-kbuild:trixie \
    dtc -I dtb -O dts /out/arch/arm64/boot/dts/qcom/sm8250-xiaomi-munch.dtb
/dts-v1/;

/ {
        model = "Xiaomi Redmi K40S";
        compatible = "xiaomi,munch", "qcom,sm8250";
        chassis-type = "handset";
        qcom,msm-id = <0x164 0x10000>;
        qcom,board-id = <0x32 0x00>;

        memory@80000000 {
                device_type = "memory";
                reg = <0x00 0x80000000 0x00 0x39900000
                       0x00 0xc0000000 0x01 0x40000000
                       0x02 0x00000000 0x01 0x80000000>;
        };
        ...
        ramoops@b0000000 {
                compatible = "ramoops";
                reg = <0x00 0xb0000000 0x00 0x400000>;
                record-size = <0x40000>;
                console-size = <0x200000>;
                pmsg-size = <0x200000>;
        };
```

memory 节点原样输出（dtc 反编译是单行，这里照抄不改格式）：

```
	memory@80000000 {
		device_type = "memory";
		reg = <0x00 0x80000000 0x00 0x39900000 0x00 0xc0000000 0x01 0x40000000 0x02 0x00 0x01 0x80000000>;
	};
```

三段边界验算：

| 段 | 起始 + 长度 | 结束 |
|---|---|---|
| 1 | `0x80000000` + `0x39900000` | `0xb9900000` |
| 2 | `0xc0000000` + `0x140000000` | `0x200000000` |
| 3 | `0x200000000` + `0x180000000` | `0x380000000` |

`0xb9900000-0xbfffffff` 是空洞，三段之间没有任何一段覆盖它。

- `0x164` = 356（SM8250），`0x10000` 与 vendor `kona.dtsi:32` 一致
- `0x32` = 50，与设备实测 `/proc/device-tree/qcom,board-id` 一致

### 6.4 defconfig 必需项（全部 `=y`）

```
CONFIG_ARCH_QCOM                  =y OK
CONFIG_PINCTRL_SM8250             =y OK
CONFIG_QCOM_CLK_RPMH              =y OK
CONFIG_QCOM_RPMH                  =y OK
CONFIG_REGULATOR_QCOM_RPMH        =y OK
CONFIG_SERIAL_QCOM_GENI           =y OK
CONFIG_SERIAL_QCOM_GENI_CONSOLE   =y OK
CONFIG_SCSI_UFS_QCOM              =y OK
CONFIG_PHY_QCOM_QMP_UFS           =y OK
CONFIG_USB_DWC3                   =y OK
CONFIG_USB_DWC3_QCOM              =y OK
CONFIG_PHY_QCOM_USB_SNPS_FEMTO_V2 =y OK
CONFIG_PSTORE                     =y OK
CONFIG_PSTORE_CONSOLE             =y OK
CONFIG_PSTORE_RAM                 =y OK
CONFIG_PSTORE_PMSG                =y OK
```

为了让上面这些真的是 `=y`，fragment 里额外补了依赖（Kconfig 会静默降级，不补就变 `=m`）：

- `CONFIG_RESET_CONTROLLER=y`、`CONFIG_SCSI_UFSHCD=y`、`CONFIG_SCSI_UFSHCD_PLATFORM=y`（`SCSI_UFS_QCOM` 的前置）
- `CONFIG_PHY_QCOM_QMP=y`（`PHY_QCOM_QMP_UFS` 被 `if PHY_QCOM_QMP` 圈着）

### 6.5 initramfs

```
$ gzip -t out/initramfs.cpio.gz && echo OK
OK

$ gzip -dc out/initramfs.cpio.gz | cpio -t | grep -x './init'
./init

$ ls -l init（解包后）
-rwxr-xr-x 1 root root 576 init
```

### 6.6 boot 镜像 v2（主实验品：v2 头 + 自带 dtb）

```
$ python3 scripts/parse_bootimg.py out/boot-munch-v2-dtb.img
file=/home/yayoi/projects/munch-mainline-work/out/boot-munch-v2-dtb.img
size=46288896
sha256=267aa4457d7563f79dca5cb387b2198056e198dadbba8009e364ea476866ed91
magic=ANDROID!
header_version=2
page_size=4096
header_size=1660
os_version=0x00000000
name='munch-7.3'
cmdline='console=ttyMSM0,115200n8'
extra_cmdline=''
kernel_size=42183168
kernel_addr=0x10080000
ramdisk_size=3974543
ramdisk_addr=0x11000000
second_size=0
tags_addr=0x10000100
recovery_dtbo_size=0
recovery_dtbo_offset=0
dtb_size=119812
dtb_addr=0x11f00000
kernel_offset=4096
ramdisk_offset=42188800
second_offset=46166016
recovery_dtbo_offset_actual=46166016
dtb_offset=46166016
kernel_fdt_magic_count=2
kernel_appended_dtb=no
  (kernel 里那些 0xd00dfeed 是内核数据里的巧合，都不是完整 FDT)
layout=OK
校验通过
```

（`kernel_appended_dtb=no`：v2 的 kernel 段是纯 `Image`，dtb 在 header 指向的独立段里。）

### 6.7 boot 镜像 v3（对照组：没有 dtb 字段）

```
$ python3 scripts/parse_bootimg.py out/boot-munch-v3.img
file=/home/yayoi/projects/munch-mainline-work/out/boot-munch-v3.img
size=46166016
sha256=82ebc003497ceb2a614e3de5a00094606971145b35dc869c6a044b8d2682e89f
magic=ANDROID!
header_version=3
page_size=4096
header_size=1580
os_version=0x00000000
kernel_size=42183168
ramdisk_size=3974543
cmdline=''
kernel_offset=4096
ramdisk_offset=42188800
dtb_size=0  (header v3 没有 dtb 字段，ABL 不会读 header 里的 dtb)
kernel_fdt_magic_count=2
kernel_appended_dtb=no
  (kernel 里那些 0xd00dfeed 是内核数据里的巧合，都不是完整 FDT)
layout=OK
校验通过
```

### 6.8 boot 镜像 v3 + appended dtb（备选）

```
$ cat out/arch/arm64/boot/Image \
      out/arch/arm64/boot/dts/qcom/sm8250-xiaomi-munch.dtb > out/Image-dtb
$ python3 scripts/mkbootimg_v2.py --kernel out/Image-dtb \
    --ramdisk out/initramfs.cpio.gz --header-version 3 \
    -o out/boot-munch-v3-appended.img

$ python3 scripts/parse_bootimg.py out/boot-munch-v3-appended.img
file=/home/yayoi/projects/munch-mainline-work/out/boot-munch-v3-appended.img
size=46284800
sha256=a072beb5bdc7a0b6a065a5bd6508ecb003fe80572d61552176b77fd95d97ca53
magic=ANDROID!
header_version=3
page_size=4096
header_size=1580
os_version=0x00000000
kernel_size=42302980
ramdisk_size=3974543
cmdline=''
kernel_offset=4096
ramdisk_offset=42307584
dtb_size=0  (header v3 没有 dtb 字段，ABL 不会读 header 里的 dtb)
kernel_fdt_magic_count=3
kernel_appended_dtb=yes
kernel_appended_dtb_offset=42183168
kernel_appended_dtb_size=119812
layout=OK
校验通过
```

- `kernel_fdt_magic_count=3` = Image 里原有的 2 处巧合 + 1 个真正的 appended dtb
- `kernel_appended_dtb_offset=42183168` 正好等于 `Image` 的字节数，`size=119812` 正好等于 dtb 大小
- `Image-dtb` 已验证逐字节等于 `Image + dtb`（42,302,980 = 42,183,168 + 119,812）

### 6.9 大小上限

```
46,288,896 < 201,326,592   # v2
46,166,016 < 201,326,592   # v3
46,284,800 < 201,326,592   # v3-appended
```

## 7. 已知偏差与风险（实机试 boot 前请过一眼）

| # | 项 | 现状 | 风险 / 处理 |
|---|---|---|---|
| 1 | 内存 | ✅ 已按 `/proc/device-tree/memory/reg` + `/proc/iomem` 改成 12 GB 三段（3 条 reg） | 无。空洞 `0xb9900000-0xc0000000` 没有被合并，第二段 size 用高低位避开 32 位截断 |
| 2 | ramoops 地址 | ✅ 已按实测：`0xb0000000`，4 MB，不碰 `0xb0400000` 的 disp_rdump | 无 |
| 3 | `record-size` 不生效 | `console + pmsg` 正好占满 4 MB，dmesg 区大小为 0 | 不影响 `console-ramoops` 和 `pmsg-ramoops`；若以后要 oops 记录，得把 region 加大或缩小 console/pmsg |
| 4 | **reserved-memory 仍是平台默认值** | 保留了 `sm8250.dtsi` 的全部默认节点，但**没有**和 munch 实测的 `/proc/device-tree/reserved-memory/` 逐项对齐 | Lead 只给了 ramoops 与 disp_rdump 的边界，没有给完整 reg 表。要精确对齐需要那张表（见第 9 节） |
| 5 | `disp_rdump_region` 未在 DTS 声明 | 该区域 `0xb0400000-0xb1400000` 不在任何 reserved 节点里，内核会当普通内存用 | 可能被内核分配走、显示 dump 失效；不影响启动验证。下一版建议补一个 reserved 节点 |
| 6 | **v2 + dtb 能否被 ABL 采用** | 未知 | 本次实验的核心问题。当前 boot 分区是 v3 且没有 dtb，DT 来自 vendor_boot + dtbo。v3 镜像是对照组，v3-appended 是备选 |
| 6b | Image 自带 2 处假 FDT magic | `0xd00dfeed` 在 offset 0x17af760、0x1882dc0 | 若 ABL 是「从 kernel 尾部往前盲搜 magic」，可能先撞到这两个假货。这是 v3-appended 方案固有的不确定性，只能实机验证 |
| 7 | 稳压器映射 | 抄 elish/pipa | UFS（L17/L6/S4 + L5/L9）和 USB HS PHY（L5/L12/L2）已用 vendor 树 `xiaomi-sm8250-common.dtsi`、`kona-usb.dtsi` 核对一致；其余 rail 未核实 |
| 8 | `&tlmm` | 没有覆盖 | vendor 树里 munch 既没有 `gpio-reserved-ranges`，也没有需要覆盖的 pinmux（UART pinmux 在 `sm8250.dtsi` 的 `&uart6` 里自带） |
| 9 | 没有可用 UART | 已知 | 唯一证据链：`console-ramoops`（内核日志）+ `pmsg-ramoops`（`MUNCH-INIT-REACHED`），重启回 Android 后读 `/sys/fs/pstore/` |
| 10 | 未覆盖外设 | 按计划 | 屏幕（l11r）、触摸（ft3658u）、WiFi（QCA6391）、音频、摄像头、充电（bq2597x）都不在本次范围 |

## 8. 复现命令

```bash
cd /home/yayoi/.lody/repos/github---yayoinoyume---munch-mainline   # 仓库根
docker build -f scripts/Dockerfile.kbuild -t munch-kbuild:trixie .  # 编译镜像
scripts/build.sh                                                    # dts + defconfig + Image + dtb
scripts/mkinitramfs.sh                                              # out/initramfs.cpio.gz

OUT=/home/yayoi/projects/munch-mainline-work/out
python3 scripts/mkbootimg_v2.py \
  --kernel $OUT/arch/arm64/boot/Image \
  --ramdisk $OUT/initramfs.cpio.gz \
  --dtb $OUT/arch/arm64/boot/dts/qcom/sm8250-xiaomi-munch.dtb \
  --header-version 2 --cmdline "console=ttyMSM0,115200n8" --name "munch-7.3" \
  -o $OUT/boot-munch-v2-dtb.img
python3 scripts/mkbootimg_v2.py \
  --kernel $OUT/arch/arm64/boot/Image --ramdisk $OUT/initramfs.cpio.gz \
  --header-version 3 -o $OUT/boot-munch-v3.img

# 备选：v3 头 + dtb 拼在 kernel 末尾
cat $OUT/arch/arm64/boot/Image \
    $OUT/arch/arm64/boot/dts/qcom/sm8250-xiaomi-munch.dtb > $OUT/Image-dtb
python3 scripts/mkbootimg_v2.py \
  --kernel $OUT/Image-dtb --ramdisk $OUT/initramfs.cpio.gz \
  --header-version 3 -o $OUT/boot-munch-v3-appended.img

python3 scripts/parse_bootimg.py $OUT/boot-munch-v2-dtb.img
python3 scripts/parse_bootimg.py $OUT/boot-munch-v3.img
python3 scripts/parse_bootimg.py $OUT/boot-munch-v3-appended.img
```

首次全量编译约 4 分钟（32 核，arm64 defconfig 全平台），只改 DTS 的增量重编约 20 秒。

## 9. 下一步

1. 用户在场时执行 `fastboot boot out/boot-munch-v2-dtb.img`（只 boot，不 flash）。
2. 失败重启回 Android 后立刻读 `/sys/fs/pstore/console-ramoops-0` 和 `pmsg-ramoops-0`，
   把内容带回来——那是判断卡在哪个阶段的唯一线索。
3. 若 v2 没反应，按这个顺序试备选：
   - **v3-appended**（`boot-munch-v3-appended.img`）：赌 ABL 会读 kernel 尾部的 FDT
   - **v3**（`boot-munch-v3.img`）：对照组，用来区分「内核起不来」和「ABL 没用我们的 dtb」
4. 需要 Lead 补一份 `/proc/device-tree/reserved-memory/` 的完整 reg 表（每个子节点的名字 + 地址 + 大小），
   下一版 DTS 就能把 reserved-memory 从「平台默认值」换成 munch 的真实布局（风险 4、5）。
