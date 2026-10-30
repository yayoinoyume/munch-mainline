# 完整方案

## 一、总体思路

不是"把 Android 4.19 的驱动搬到 7.x"（150 万行，不可行），而是"给 7.x 写 munch 的支持"：

- 平台层（SoC、PMIC、UFS、USB、PCIe/WiFi、GPU、显示控制器）直接参考主线已有的 `sm8250-xiaomi-elish`（小米平板 5 Pro，同 SoC）。
- 真正要新写的只有面板驱动（`l11r` OLED）和少量设备树节点。

## 二、为什么不会破坏现有系统

- 所有验证都用 `fastboot boot`：把镜像加载到内存试跑，不写任何分区。
- 失败 → 强制重启 → 还是原来的 Android，Rungic 容器不受影响。
- 启动日志通过 ramoops 回读（`/sys/fs/pstore`），不需要屏幕。

## 三、阶段拆解

### 阶段 0：物料与备份
- 下载 Linux 7.3 源码、解压。
- 工具链：clang 21 + lld + gcc-aarch64-linux-gnu。
- 备份 `boot_a`、`dtbo_a` 到 `assets/backup/`，记录 sha256。

### 阶段 1：最小 DTS
- 基于 `sm8250-xiaomi-elish-common.dtsi` 裁剪。
- 只保留：UFS、USB（dwc3）、ramoops、PMIC（pm8150/pm8150b/pm8150l）、uart。
- 不写 panel / touch / camera，先让内核能启动。

### 阶段 2：编译
- `make ARCH=arm64 LLVM=1 munch_defconfig`（自建 defconfig）。
- 产物：`Image`、`sm8250-xiaomi-munch.dtb`。

### 阶段 3：initramfs
- Alpine minirootfs 或 busybox 静态包。
- 启动后：写标记到 ramoops → 起 USB RNDIS + telnetd。
- 目的：第一次验证不依赖屏幕，第二次起可以热调试。

### 阶段 4：打包
- 用 `magiskboot` 或 `mkbootimg` 打包成 boot.img（header v3）。
- 校验大小 < boot 分区（192 MB）。

### 阶段 5：验证
- `adb reboot bootloader` → `fastboot boot boot.img`。
- 成功：USB 网卡出现 / telnet 可连 / pstore 有标记。
- 失败：重启回 Android，读 `/sys/fs/pstore/console-ramoops-0`。

### 阶段 6+：外设
- 显示控制器 → 面板驱动 → 触摸 → WiFi → 音频 → 充电 → 摄像头。
- 驱动全部编成模块，SSH/telnet 热插拔调试，不重启。

## 四、风险与回滚

| 风险 | 缓解 |
|---|---|
| fastboot boot 失败 | 强制重启回 Android；分区未改 |
| 内核 hang | 长按电源键重启；pstore 有日志 |
| 误操作写分区 | 只执行 `fastboot boot`，脚本里禁止 `flash` |
| 面板驱动卡住 | 先不碰显示，USB/网络先通 |

## 五、不做什么

- 不刷 boot / vbmeta / dtbo / super / userdata。
- 不动 Rungic 容器与 `/data`。
- 不追求通话/相机/指纹（主线驱动缺失，后续单独评估）。
