# 完整方案

> 最后更新：2026-10-30
> 状态：阶段 0（环境准备）部分完成，等待新会话继续

## 一、背景与目标

- 设备：Redmi K40S（`munch`，SM8250 / 骁龙 870）
- 现状：LineageOS 23.2（Android 16）+ Magisk 31.0 + Rungic Plasma 容器（LXC + Ubuntu 26.04 + KDE）
- 用户目标：把内核升级到 6.x / 7.x
- 硬约束：**不破坏现有系统、内核、数据、Rungic 容器及容器内 Ubuntu 的数据和配置**

## 二、调查结论（已核实，不要重复踩坑）

### 2.1 Android 侧换 6.x/7.x：不可行

| 证据 | 内容 |
|---|---|
| LineageOS 自己没升 | `lineage-24.0` 的 `Makefile` 仍是 `VERSION=4 PATCHLEVEL=19 SUBLEVEL=325`，从 18.1 到 24.0 全部 4.19 |
| 无 GKI 基线 | GKI 从 5.4 开始，所有骁龙 870 机型出厂都是 4.19 vendor 内核 |
| vendor HAL 绑定 | `/vendor/lib64/hw/` 里 `camera.qcom.so`、`audio.primary.kona.so`、`vulkan.adreno.so` 都按 4.19 的 vendor 内核接口编译 |
| 驱动量级 | 内核树里 vendor 驱动约 150 万行（audio 54.8 万、camera 19.8 万、platform/msm 21.8 万、clk 14.6 万、soc/qcom 11.8 万、kgsl 7.4 万、qcacld 8.8 万） |

**结论**：forward-port 到 7.x 是"重写驱动 + 重定义 HAL 边界"，全球无先例。

### 2.2 主线侧现状

- Linux 主线当前版本：**7.3**（2026-10-18 发布）
- `arch/arm64/boot/dts/qcom/` 已有：`sm8250.dtsi`、`sm8250-xiaomi-elish-*.dts`（小米平板 5 Pro）、`sm8250-xiaomi-pipa.dts`、Sony、三星
- **没有 munch 的设备树**
- postmarketOS 没有 munch 设备包
- 但 elish 与 munch 同为 SM8250 + pm8150/pm8150b/pm8150l/pm8009 PMIC，**平台层可直接参考**

### 2.3 三条路线对比

| | A：4.19 补特性 | B：双系统 | C：整机主线 |
|---|---|---|---|
| 新内核 | ❌ 仍是 4.19 | ✅ 7.x（另一系统） | ✅ 7.x |
| Android 应用 | ✅ | ✅ | ❌ |
| Rungic 容器 | ✅ 原样 | ⚠️ 需迁移，桥接失效 | ⚠️ 需迁移，桥接失效 |
| 数据 | ✅ 零风险 | ✅ Android 不动，但不共享 | ❌ 需备份导出 |
| 工作量 | 几小时 | 1~3 个月 | 同左 |
| 空间 | 不涉及 | super 剩 4.5 GB / 需缩 userdata | 充足（225 GB） |

**用户选择**：走路线 C（整机主线），因为"就是想用新内核"。

### 2.4 munch 硬件与主线驱动对照

| 外设 | munch 实际 | 主线状态 | 备注 |
|---|---|---|---|
| SoC / PMIC / UFS / USB | SM8250 + pm8150 系 | ✅ elish 已验证 | 抄 DTS |
| GPU | Adreno 650 | ✅ freedreno | 可用 |
| 显示控制器 | msm/dpu | ✅ 主线有 | 可用 |
| **屏幕面板** | `l11r` OLED（DSI） | ❌ 无驱动 | **必须新写，最卡** |
| 触摸 | focaltech ft3658u | ~~⚠️ 主线有 focaltech 通用驱动~~ **❌ 更正（2026-10-30）：主线只有 `edt-ft5x06`，支持 FT5x06/FT6x06/FT3518 系列，不支持 ft3658u** | ~~配 DTS~~ **需要新写驱动或移植 focaltech fts 驱动** |
| WiFi | QCA6391（Android 用 qcacld-3.0） | ⚠️ 主线 ath11k | 换驱动 + 固件 |
| 音频 | WCD9385 + ADSP | ⚠️ 主线 wcd938x + q6apm | 需 ADSP 固件 |
| 充电 | pm8150b + 小米私有 | ⚠️ 主线 pm8150b | 快充协议要调 |
| 摄像头 | IMX582 + 超广/微距 | ⚠️ CAMSS 有，sensor 驱动不确定 | 质量差 |
| 通话 / 5G | X55 modem | ⚠️ remoteproc + qmi | 数据可能通，通话基本废 |
| 指纹 | FPC / Goodix | ❌ 无主线驱动 | 废 |
| NFC | NXP | ⚠️ nxp-nci | 可能可用 |

### 2.5 4.19 内核缺什么（如果回头走路线 A）

`nf_tables`、`cgroup2 devices`、`vxlan/macvlan/ipvlan`、`binfmt_misc`、`KVM`、`io_uring`（4.19 无）、`FUSE passthrough`（6.9 才有）。
除 `io_uring` 和 `FUSE passthrough` 外，其余在 4.19 源码里都有，只是 LineageOS defconfig 没开。

## 三、技术方案（路线 C）

### 3.1 安全边界（铁律）

1. **只用 `fastboot boot`**，绝不 `fastboot flash`
2. 不碰 `userdata` / `super` / `metadata` / `boot` / `vbmeta` / `dtbo`
3. 设备操作前备份分区，校验 sha256
4. Rungic 容器全程不停机、不改配置
5. 失败即重启回 Android

### 3.2 阶段拆解

| 阶段 | 内容 | 验收标准 | 状态 |
|---|---|---|---|
| 0 | 源码、工具链、备份 | 7.3 源码解压、Docker 镜像可编译、boot_a 备份 | 部分完成 |
| 1 | 最小 DTS | UFS/USB/ramoops/PMIC/uart，不写 panel | 未开始 |
| 2 | 编译 | 产出 `Image` + `sm8250-xiaomi-munch.dtb` | 未开始 |
| 3 | initramfs | 启动标记写 ramoops；USB RNDIS + telnetd | 未开始 |
| 4 | 打包 boot.img | header v3，大小 < 192 MB | 未开始 |
| 5 | `fastboot boot` 验证 | USB 网卡出现 / telnet 可连 / pstore 有标记 | 未开始 |
| 6+ | 外设 | 显示 → 触摸 → WiFi → 音频 → 充电 → 摄像头 | 未开始 |

### 3.3 测试策略（关键）

不用每改一个驱动就重启：

| 改动类型 | 是否重启 | 迭代时间 | 手段 |
|---|---|---|---|
| 驱动代码（.ko 模块） | ❌ | 几十秒 | scp + insmod/rmmod + dmesg |
| DTS / 内核核心 | ✅ | 1~3 分钟 | `fastboot boot` |
| 首次 bring-up | ✅ | 1~3 分钟 | `fastboot boot` + pstore 回读 |

**转折点**：内核能起来 + USB 网络 + telnet/SSH 通。之后 90% 调试不用重启。

### 3.4 盲启动兜底

- `pstore/ramoops` 已启用：`/sys/fs/pstore/console-ramoops-0`（实测有 223 KB 上次启动日志）
- USB gadget：dwc3 dual-role + NCM + configfs 全支持
- `fastboot boot` 不写 flash，失败重启即回 Android

## 四、风险

| 风险 | 缓解 |
|---|---|
| `fastboot boot` 失败 | 强制重启回 Android；分区未改 |
| 内核 hang | 长按电源键重启；pstore 有日志 |
| 误写分区 | 脚本里禁止 `flash` 子命令 |
| 面板驱动卡住 | 先不碰显示，USB/网络先通 |
| 编译产物权限 | Docker 用 `--user` 或编译后 chown |

## 五、不做什么

- 不刷 boot / vbmeta / dtbo / super / userdata
- 不动 Rungic 容器与 `/data`
- 不追求通话 / 相机 / 指纹（主线驱动缺失）
