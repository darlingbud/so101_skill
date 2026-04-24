---
name: robot-agent
description: >
  SO-101/RO-101 机械臂控制与轨迹生成 Skill。适用于以下场景：控制机械臂运动、录制/回放动作轨迹、
  自动生成舞蹈/摆动等轨迹、拼接编排多段动作、恢复飞特 ST-3215 舵机参数。
  触发词：机械臂控制、机器人动作、录制轨迹、回放轨迹、生成轨迹、跳舞动作、摆动动作、
  舵机参数恢复、ST-3215、SO-101、RO-101、LeRobot、轨迹编排、关键帧插值。
---

# Robot Agent Skill

控制 SO-101/RO-101 机械臂（飞特 ST-3215 舵机，LeRobot 框架），提供录制→生成→回放的完整轨迹工作流。

## 核心能力

1. **机械臂控制** — 通过 client-server 架构（tmux + socket）连接/断开/操作机械臂
2. **轨迹录制与回放** — 以固定频率录制关节数据，支持变速/插值回放
3. **轨迹生成** — 关键帧插值、数学函数（正弦波）、跳舞动作自动编排
4. **轨迹编排** — 多段轨迹拼接、过渡帧插入、镜像/缩放
5. **舵机参数管理** — 飞特 ST-3215 默认参数查询与恢复

## 架构

```
CLI / Python API → RobotAgent → RobotClient → RobotServer → 机械臂
                                            (单次连接)    (tmux 常驻)
```

## 工作流

### 连接与操作

```bash
# 连接机械臂
python -m robot_agent connect --port-name /dev/ttyACM0

# 解锁扭矩 → 手动移动
python -m robot_agent free

# 查看状态/获取关节数据
python -m robot_agent status
python -m robot_agent get

# 设置关节位置
python -m robot_agent set shoulder_pan.pos=30 elbow_flex.pos=-50

# 回零/安全位置
python -m robot_agent home
python -m robot_agent safe

# 断开
python -m robot_agent disconnect
```

### 录制与回放

```bash
# 录制（按 Enter 停止）
python -m robot_agent record --freq 10 --out my_action

# 回放
python -m robot_agent replay --file my_action --speed 1.0
```

录制文件格式：`recordings/*.json`
```json
{
  "frequency": 10,
  "actions": [
    {"timestamp": 0.0, "shoulder_pan.pos": 0, "shoulder_lift.pos": -50, ...}
  ]
}
```

### 轨迹生成

三种方法，按复杂度递增：

| 方法 | 适用场景 | 参考 |
|------|---------|------|
| 关键帧插值 | 简单周期动作 | `references/trajectory_generation.md` 第三章 |
| 数学函数 | 规律性摆动（正弦） | `references/trajectory_generation.md` 第四章 |
| 录制→编辑→回放 | 复杂动作 | 录制后用 Python 编辑 |

生成轨迹后，保存为 JSON 到 `recordings/` 目录，用 `replay` 命令播放。

### 轨迹编排

将多段轨迹拼接成完整动作序列（过渡帧自动插入）。详见 `references/trajectory_generation.md` 第六章。

### 舵机参数恢复

飞特 ST-3215 关键参数与恢复方法。详见 `references/servo_parameters.md`。

## 关节对照表

| 关节 | ID | 归一化范围 | 正值含义 | 负值含义 |
|------|---|-----------|---------|---------|
| `shoulder_pan` | 1 | -100 ~ +100 | 左转 | 右转 |
| `shoulder_lift` | 2 | -100 ~ 0 | — | 抬起 |
| `elbow_flex` | 3 | -100 ~ +100 | 弯曲 | 伸直 |
| `wrist_flex` | 4 | 0 ~ +100 | 向下弯 | — |
| `wrist_roll` | 5 | -100 ~ +100 | 顺时针 | 逆时针 |
| `gripper` | 6 | 0 ~ +100 | 闭合 | — |

## 安全注意事项

| 风险 | 防护 |
|------|------|
| 关节超限 | 生成轨迹前检查值域 [-100, 100]，gripper [0, 100] |
| 速度过快 | 先用 `--speed 0.5` 半速测试 |
| 碰撞 | 首次回放新手持急停位置 |
| 舵机参数异常 | 确保 Goal_Velocity=0, Max_Torque_Limit=1000(关节)/500(夹爪), P_Coefficient=16 |

## 目录结构

```
agent_skill/
├── SKILL.md                          # 本文件
├── robot_agent.py                    # 入口包装
├── recordings/                       # 录制/生成的轨迹 JSON
│   ├── nod.json                      # 手动录制：点头
│   ├── shake.json                    # 手动录制：摇头
│   ├── wave.json                     # 手动录制：摆手
│   ├── dance.json                    # 生成：6 阶段跳舞
│   ├── wave_hello.json               # 生成：招手
│   ├── thinking.json                 # 生成：托腮思考
│   ├── bow.json                      # 生成：鞠躬
│   ├── pick_place.json               # 生成：夹爪抓放
│   ├── spin_show.json                # 生成：展示旋转
│   ├── stretch.json                  # 生成：伸展运动
│   ├── high_five.json                # 生成：击掌
│   └── combo.json                    # 生成：三段组合
├── scripts/                          # 生成脚本
│   └── generate_demo_trajectories.py # 批量生成示例轨迹
├── references/                       # 参考文档（按需加载）
│   ├── trajectory_generation.md      # 轨迹生成完整指南（含示例详解）
│   └── servo_parameters.md           # 舵机参数恢复指南
└── robot_agent/                      # Python 包
    ├── __init__.py
    ├── __main__.py
    ├── commands.py
    ├── config.py
    ├── core.py
    ├── recordings.py
    ├── robot_client.py
    ├── robot_server.py
    └── robot_utils.py
```
