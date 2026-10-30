# munch-mainline

给 Redmi K40S（munch / SM8250）做 Linux 主线内核移植的工作区。

## 目标

在**不破坏现有 Android 23.2 + Magisk + Rungic 容器**的前提下，构建一个能启动的 Linux 7.x 主线内核，用 `fastboot boot` 临时验证，最终逐步补齐屏幕、触摸、WiFi、音频等外设。

## 安全铁律

1. **绝不 `fastboot flash`**，只用 `fastboot boot`（临时加载到内存，不写分区）。
2. **绝不碰** `userdata` / `super` / `metadata` / `boot` / `vbmeta` / `dtbo` 分区。
3. 每次设备操作前，备份对应分区到本地工作区并校验 sha256。
4. Rungic 容器（`com.rungic.plasma`）全程不停机、不改配置、不动 `/data/adb/rungic-lxc`。
5. 失败即重启回 Android，零损失。

## 目录分工

```
munch-mainline/           ← 本仓库（只放可公开的代码、文档、脚本）
├── README.md
├── docs/                 方案与记录
├── dts/                  munch 设备树
└── scripts/              构建、打包、验证脚本

../munch-mainline-work/   ← 本地工作区（不进 git）
├── src/                  Linux 7.3 源码（2.0 GB）
├── out/                  编译产物
├── assets/backup/        分区备份（boot_a.img 等）
└── logs/                 运行日志
```

## 交接

新会话从这里开始：[`docs/02-handoff.md`](docs/02-handoff.md)

## 阶段

| 阶段 | 内容 | 状态 |
|---|---|---|
| 0 | 源码、工具链、boot 分区备份 | 进行中 |
| 1 | munch 最小 DTS（UFS/USB/ramoops/PMIC） | 待开始 |
| 2 | 编译 7.3 内核 + DTB | 待开始 |
| 3 | initramfs（启动标记 + telnet） | 待开始 |
| 4 | 打包 boot.img（不写 flash） | 待开始 |
| 5 | `fastboot boot` 验证（需用户在场） | 待开始 |
| 6+ | 逐个加外设（屏幕/触摸/WiFi/音频） | 待开始 |

## 设备信息

- 设备：Redmi K40S `munch`，SM8250 / 骁龙 870
- 系统：LineageOS 23.2（Android 16），A/B，slot A
- 内核：4.19.325-cip131-st15-perf（自编译）
- 容器：Rungic Plasma（LXC + Ubuntu 26.04 + KDE）
