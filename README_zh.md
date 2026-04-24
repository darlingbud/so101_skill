# Robot Agent — SO-101/RO-101 机械臂控制

> **完整文档请查看 [SKILL.md](SKILL.md)**

基于 client-server 架构的机械臂控制工具，支持轨迹录制、生成与回放。

## 快速开始

```bash
# 连接
python -m robot_agent connect --port-name /dev/ttyACM0

# 解锁→录制→回放
python -m robot_agent free
python -m robot_agent record --freq 10 --out my_action
python -m robot_agent replay --file my_action --speed 1.0

# 断开
python -m robot_agent disconnect
```

## CLI 命令

| 命令 | 说明 |
|------|------|
| `connect` | 连接机械臂 |
| `disconnect` | 断开连接 |
| `status` | 查看状态 |
| `get` | 获取关节数据 |
| `set key=value ...` | 设置关节位置 |
| `home` | 回零 |
| `safe` | 安全位置 |
| `free` | 解锁扭矩 |
| `lock` | 锁定扭矩 |
| `record --freq 10` | 录制 |
| `replay --speed 1.0` | 回放 |
| `test` | 硬件自检 |

## 参考文档

- `references/trajectory_generation.md` — 轨迹生成完整指南（关键帧插值、数学函数、编排）
- `references/servo_parameters.md` — 飞特 ST-3215 舵机参数恢复指南
