# SO-101/RO-101 轨迹生成指南

> 适用于飞特 ST-3215 系列舵机 + Robot Agent Skill
> 基于录制轨迹分析 + Robot Agent CLI/Python API

---

## 一、轨迹数据格式

### 1.1 数据结构

所有轨迹文件（`recordings/*.json`）使用统一格式：

```json
{
  "frequency": 10,
  "actions": [
    {
      "timestamp": 0.0,
      "shoulder_pan.pos": 0,
      "shoulder_lift.pos": -50,
      "elbow_flex.pos": 30,
      "wrist_flex.pos": 40,
      "wrist_roll.pos": 0,
      "gripper.pos": 50
    }
  ]
}
```

### 1.2 关节值域

| 关节 | 范围 | 正值 | 负值 |
|------|------|------|------|
| `shoulder_pan.pos` | -100 ~ +100 | 左转 | 右转 |
| `shoulder_lift.pos` | -100 ~ 0 | — | 抬起 |
| `elbow_flex.pos` | -100 ~ +100 | 弯曲 | 伸直 |
| `wrist_flex.pos` | 0 ~ +100 | 向下弯 | — |
| `wrist_roll.pos` | -100 ~ +100 | 顺时针 | 逆时针 |
| `gripper.pos` | 0 ~ +100 | 闭合 | — |

> ⚠️ 实际值域取决于校准时的机械限位，以上为录制轨迹中观察到的范围。

### 1.3 已有录制轨迹

**手动录制的轨迹：**

| 文件 | 时长 | 主要运动关节 | 描述 |
|------|------|-------------|------|
| `nod.json` | ~9s | shoulder_lift, elbow_flex, wrist_flex | 低头→抬头 |
| `shake.json` | ~8s | shoulder_lift, wrist_roll | 腕旋转+肩俯仰 |
| `wave.json` | ~12s | shoulder_lift, elbow_flex, shoulder_pan | 伸展后水平摆动 |

**自动生成的轨迹：**

| 文件 | 时长 | 主要运动关节 | 描述 |
|------|------|-------------|------|
| `dance.json` | ~19s | 全关节 | 6 阶段跳舞动作（举臂→摆动→泵动→花式→画圈→归位） |
| `wave_hello.json` | ~9s | shoulder_lift, wrist_roll, gripper | 招手 — 手臂举起，gripper 张开，wrist_roll 左右摆 |
| `thinking.json` | ~10s | shoulder_pan, shoulder_lift, elbow_flex, wrist_flex | 托腮思考 — 手臂弯曲到头部附近，微倾来回 |
| `bow.json` | ~7s | shoulder_lift, elbow_flex, wrist_flex | 鞠躬 — 肩部前倾+肘部弯曲 |
| `pick_place.json` | ~10s | shoulder_lift, elbow_flex, wrist_flex, gripper | 夹爪抓放 — 伸手→闭合→抬起→放下→松开 |
| `spin_show.json` | ~11s | shoulder_pan, shoulder_lift, elbow_flex | 展示旋转 — 底座大范围旋转 ±50°+手臂伸展 |
| `stretch.json` | ~12s | 全关节 | 伸展运动 — 全关节大范围热身运动 |
| `high_five.json` | ~7s | shoulder_lift, elbow_flex, wrist_flex, gripper | 击掌 — 伸手停顿→快速击下→弹回 |
| `combo.json` | ~22s | 全关节 | 组合 — 招手→思考→鞠躬三段拼接+过渡 |

> 所有自动生成轨迹由 `scripts/generate_demo_trajectories.py` 生成，使用关键帧插值 + cosine smooth step 缓动。

---

## 二、轨迹生成方法总览

| 方法 | 适用场景 | 难度 | 输出 |
|------|---------|------|------|
| **A. 关键帧插值** | 简单周期动作 | ⭐ | JSON 轨迹 |
| **B. 数学函数** | 规律性摆动 | ⭐⭐ | JSON 轨迹 |
| **C. 录制→编辑→回放** | 复杂动作 | ⭐⭐⭐ | recordings/*.json |

所有方法最终都生成同样格式的 JSON 文件，保存到 `recordings/` 目录后即可用 `replay` 命令播放。

---

## 三、方法 A：关键帧插值

### 3.1 原理

定义关键姿态（keyframe），在它们之间用 cosine smooth step 或三次样条插值，生成平滑轨迹。

### 3.2 生成脚本

```python
#!/usr/bin/env python
"""关键帧插值生成轨迹（纯 Python，无 scipy 依赖）"""

import json
import math

FREQUENCY = 10  # Hz
JOINTS = [
    "shoulder_pan.pos", "shoulder_lift.pos", "elbow_flex.pos",
    "wrist_flex.pos", "wrist_roll.pos", "gripper.pos",
]


def lerp(a, b, t):
    return a + (b - a) * t


def smooth_step(t):
    """Cosine 缓动插值，比线性更自然"""
    return 0.5 * (1 - math.cos(math.pi * t))


def clamp(val, joint_name):
    """归一化值域约束"""
    if joint_name == "gripper.pos":
        return max(0, min(100, round(val)))
    return max(-100, min(100, round(val)))


def generate_from_keyframes(keyframes, fps=FREQUENCY):
    """
    从关键帧生成轨迹

    Args:
        keyframes: [(time, shoulder_pan, shoulder_lift, elbow_flex,
                      wrist_flex, wrist_roll, gripper), ...]
        fps: 采样频率
    Returns:
        标准轨迹字典
    """
    dt = 1.0 / fps
    total_duration = keyframes[-1][0]
    actions = []
    kf_idx = 0

    t = 0.0
    while t <= total_duration + dt / 2:
        while kf_idx < len(keyframes) - 1 and keyframes[kf_idx + 1][0] < t - 1e-9:
            kf_idx += 1

        if kf_idx >= len(keyframes) - 1:
            kf = keyframes[-1]
            action = {"timestamp": round(t, 4)}
            for j, joint in enumerate(JOINTS):
                action[joint] = clamp(kf[j + 1], joint)
            actions.append(action)
        else:
            kf0, kf1 = keyframes[kf_idx], keyframes[kf_idx + 1]
            seg = kf1[0] - kf0[0]
            frac = max(0.0, min(1.0, (t - kf0[0]) / seg)) if seg > 1e-9 else 0.0
            s = smooth_step(frac)
            action = {"timestamp": round(t, 4)}
            for j, joint in enumerate(JOINTS):
                action[joint] = clamp(lerp(kf0[j + 1], kf1[j + 1], s), joint)
            actions.append(action)

        t += dt

    return {"frequency": fps, "actions": actions}
```

### 3.3 示例：生成"打招呼"动作

```python
# 关键帧格式: (时间, shoulder_pan, shoulder_lift, elbow_flex, wrist_flex, wrist_roll, gripper)
REST = (0, 0, 0, 0, 0, 0, 50)         # 初始位置
UP   = (0, -55, -30, 0, 0, 50)        # 举臂

greeting_keyframes = [
    (0.0,  0,    0,    0,    0,    0,   50),   # 静止
    (1.0,  0,    0,    0,    0,    0,   50),   # 停顿
    (2.5,  0,  -55,  -30,    0,    0,   80),   # 举臂+张爪
    (3.5, 30,  -50,  -25,   10,   20,   80),   # 摆右
    (4.5,-30,  -50,  -25,  -10,  -20,   80),   # 摆左
    (5.5, 30,  -50,  -25,   10,   20,   80),   # 摆右
    (6.5,-30,  -50,  -25,  -10,  -20,   80),   # 摆左
    (8.0,  0,  -25,  -10,    0,    0,   50),   # 降臂
    (9.0,  0,    0,    0,    0,    0,   50),   # 归位
]

traj = generate_from_keyframes(greeting_keyframes, fps=10)

# 保存到 recordings 目录
with open("recordings/greeting.json", "w") as f:
    json.dump(traj, f, indent=2)
```

### 3.4 从录制轨迹中提取关键帧

```python
def extract_keyframes(trajectory, threshold=5.0):
    """从录制轨迹中提取关键帧（关节变化超过阈值时保留）"""
    actions = trajectory["actions"]
    joints = [k for k in actions[0].keys() if k != "timestamp"]

    keyframes = [actions[0]]
    for i in range(1, len(actions)):
        prev = keyframes[-1]
        curr = actions[i]
        max_change = max(abs(curr[j] - prev[j]) for j in joints)
        if max_change >= threshold:
            keyframes.append(curr)
    return keyframes
```

---

## 四、方法 B：数学函数生成

### 4.1 原理

用正弦/余弦函数描述关节运动，适合规律性周期动作。公式：`x(t) = base + A × sin(2πft + φ)`

### 4.2 生成函数

```python
#!/usr/bin/env python
"""数学函数生成轨迹"""

import json
import numpy as np


def generate_wave_trajectory(
    base_pose,          # 基准姿态 {"joint.pos": value, ...}
    wave_joints,        # 摆动参数 {"joint.pos": {"amplitude": A, "frequency": f, "phase": φ}}
    duration=8.0,       # 总时长（秒）
    fps=10,             # 采样频率
    ramp_up=0.5,        # 缓入时间
    ramp_down=0.5,      # 缓出时间
):
    """用正弦函数生成轨迹，支持缓入缓出"""
    times = np.arange(0, duration, 1.0 / fps)
    actions = []

    for t in times:
        # 包络：缓入 → 稳定 → 缓出
        if t < ramp_up:
            envelope = t / ramp_up
        elif t > duration - ramp_down:
            envelope = (duration - t) / ramp_down
        else:
            envelope = 1.0
        envelope = max(0, min(1, envelope))

        action = {"timestamp": round(float(t), 4)}
        for joint, value in base_pose.items():
            if joint in wave_joints:
                p = wave_joints[joint]
                wave = value + envelope * p["amplitude"] * np.sin(
                    2 * np.pi * p["frequency"] * t + p.get("phase", 0)
                )
                action[joint] = round(float(wave), 4)
            else:
                action[joint] = value
        actions.append(action)

    return {"frequency": fps, "actions": actions}
```

### 4.3 示例

```python
# ====== 摆手 ======
wave_traj = generate_wave_trajectory(
    base_pose={
        "shoulder_pan.pos": 0.0, "shoulder_lift.pos": -7.0,
        "elbow_flex.pos": -40.0, "wrist_flex.pos": 71.0,
        "wrist_roll.pos": 0.0, "gripper.pos": 1.0,
    },
    wave_joints={
        "shoulder_pan.pos": {"amplitude": 25.0, "frequency": 0.5, "phase": 0},
    },
    duration=8.0,
)

# ====== 点头 ======
nod_traj = generate_wave_trajectory(
    base_pose={
        "shoulder_pan.pos": -10.0, "shoulder_lift.pos": -100.0,
        "elbow_flex.pos": 99.0, "wrist_flex.pos": 71.0,
        "wrist_roll.pos": 0.0, "gripper.pos": 1.0,
    },
    wave_joints={
        "shoulder_lift.pos": {"amplitude": 60.0, "frequency": 0.25, "phase": 0},
        "elbow_flex.pos": {"amplitude": -80.0, "frequency": 0.25, "phase": 0},
        "wrist_flex.pos": {"amplitude": -50.0, "frequency": 0.25, "phase": np.pi/4},
    },
    duration=8.0,
)

# 保存到 recordings
with open("recordings/wave_auto.json", "w") as f:
    json.dump(wave_traj, f, indent=2)
```

---

## 五、方法 C：录制→编辑→回放

### 5.1 流程

```
robot_agent record → Python 编辑 → robot_agent replay
```

### 5.2 使用 Robot Agent 录制

```bash
# 连接 + 解锁
python -m robot_agent connect --port-name /dev/ttyACM0
python -m robot_agent free

# 录制（手动移动机械臂，按 Enter 停止）
python -m robot_agent record --freq 10 --out my_action

# 保存到 recordings/my_action.json
```

或使用 Python API：

```python
from robot_agent import RobotAgent

agent = RobotAgent(host="127.0.0.1", port=8765)
agent.connect(port_name="/dev/ttyACM0")
agent.free()
agent.record(frequency=10, filename="recordings/my_action")
# ... 手动移动机械臂 ...
# 按 Enter 停止
```

### 5.3 使用 Robot Agent 回放

```bash
# 原速回放
python -m robot_agent replay --file my_action --speed 1.0

# 半速（安全测试）
python -m robot_agent replay --file my_action --speed 0.5

# 加速
python -m robot_agent replay --file my_action --speed 2.0
```

或使用 Python API：

```python
agent.replay(speed=1.0, filename="my_action")
```

### 5.4 编辑录制轨迹

录制后的 JSON 可以用第六章的工具函数编辑（平滑、裁剪、缩放等），修改后重新保存即可回放。

---

## 六、轨迹拼接与编排

### 6.1 拼接函数

```python
import json


def concatenate_trajectories(trajectories, transitions=None):
    """
    拼接多个轨迹，自动插入线性过渡帧

    Args:
        trajectories: 轨迹字典列表（帧率必须一致）
        transitions: 轨迹间过渡时间列表（秒），默认 1.0
    Returns:
        拼接后的轨迹字典
    """
    if transitions is None:
        transitions = [1.0] * (len(trajectories) - 1)
    if len(transitions) < len(trajectories) - 1:
        transitions += [1.0] * (len(trajectories) - 1 - len(transitions))

    fps = trajectories[0]["frequency"]
    dt = 1.0 / fps
    all_actions = []
    current_time = 0.0

    for i, traj in enumerate(trajectories):
        assert traj["frequency"] == fps, "所有轨迹帧率必须一致"

        if i > 0:
            prev_end = all_actions[-1]
            curr_start = traj["actions"][0]
            joints = [k for k in prev_end.keys() if k != "timestamp"]
            transition_frames = int(transitions[i - 1] * fps)

            for f in range(transition_frames):
                alpha = f / transition_frames
                action = {"timestamp": round(current_time, 4)}
                for joint in joints:
                    action[joint] = round(
                        prev_end[joint] * (1 - alpha) + curr_start[joint] * alpha, 4
                    )
                all_actions.append(action)
                current_time += dt

        for action in traj["actions"]:
            new_action = dict(action)
            new_action["timestamp"] = round(current_time + action["timestamp"], 4)
            all_actions.append(new_action)

        current_time = all_actions[-1]["timestamp"] + dt

    return {"frequency": fps, "actions": all_actions}
```

### 6.2 示例：编排"问候"动作序列

```python
# 加载已有轨迹
with open("recordings/nod.json") as f:
    nod = json.load(f)
with open("recordings/wave.json") as f:
    wave = json.load(f)
with open("recordings/shake.json") as f:
    shake = json.load(f)

# 拼接：点头 → 过渡1s → 摆手 → 过渡1.5s → 摆头
greeting = concatenate_trajectories(
    [nod, wave, shake],
    transitions=[1.0, 1.5]
)

# 保存
with open("recordings/greeting.json", "w") as f:
    json.dump(greeting, f, indent=2)

# 用 robot_agent 回放
# python -m robot_agent replay --file greeting --speed 1.0
```

---

## 七、轨迹编辑工具函数

### 7.1 低通滤波去噪

```python
from scipy.signal import butter, filtfilt


def smooth_trajectory(trajectory, cutoff_freq=2.0):
    """低通滤波平滑轨迹（消除录制抖动）"""
    fps = trajectory["frequency"]
    actions = trajectory["actions"]
    joints = [k for k in actions[0].keys() if k != "timestamp"]

    nyquist = fps / 2.0
    b, a = butter(4, cutoff_freq / nyquist, btype="low")

    for joint in joints:
        values = [act[joint] for act in actions]
        smoothed = filtfilt(b, a, values)
        for i, act in enumerate(actions):
            act[joint] = round(float(smoothed[i]), 4)

    return trajectory
```

### 7.2 降采样

```python
def downsample_trajectory(trajectory, target_fps=5):
    """从 10Hz 降到 5Hz 以减少帧数"""
    fps = trajectory["frequency"]
    ratio = fps // target_fps
    new_actions = trajectory["actions"][::ratio]
    for i, action in enumerate(new_actions):
        action["timestamp"] = round(i / target_fps, 4)
    return {"frequency": target_fps, "actions": new_actions}
```

### 7.3 反转（倒放）

```python
def reverse_trajectory(trajectory):
    """反转轨迹"""
    actions = list(reversed(trajectory["actions"]))
    fps = trajectory["frequency"]
    dt = 1.0 / fps
    for i, action in enumerate(actions):
        action["timestamp"] = round(i * dt, 4)
    return {"frequency": fps, "actions": actions}
```

### 7.4 幅度缩放

```python
def scale_trajectory(trajectory, scale=1.0, center=None):
    """
    缩放轨迹幅度
    scale=0.5 → 动作幅度减半，scale=1.5 → 幅度放大 50%
    """
    actions = trajectory["actions"]
    joints = [k for k in actions[0].keys() if k != "timestamp"]

    if center is None:
        center = {}
        for joint in joints:
            values = [a[joint] for a in actions]
            center[joint] = (min(values) + max(values)) / 2

    for action in actions:
        for joint in joints:
            action[joint] = round(
                center[joint] + (action[joint] - center[joint]) * scale, 4
            )
    return trajectory
```

### 7.5 镜像（左右翻转）

```python
def mirror_trajectory(trajectory, mirror_joints=None):
    """镜像轨迹（取反 shoulder_pan 和 wrist_roll）"""
    if mirror_joints is None:
        mirror_joints = ["shoulder_pan.pos", "wrist_roll.pos"]

    for action in trajectory["actions"]:
        for joint in mirror_joints:
            if joint in action:
                action[joint] = -action[joint]
    return trajectory
```

### 7.6 重定时（变速曲线）

```python
def retime_trajectory(trajectory, speed_curve=None):
    """
    重定时轨迹，speed_curve(t) → speed_factor
    factor>1 加速，factor<1 减速
    """
    if speed_curve is None:
        return trajectory

    actions = trajectory["actions"]
    fps = trajectory["frequency"]
    dt = 1.0 / fps

    new_actions = []
    current_time, src_time = 0.0, 0.0

    while src_time <= actions[-1]["timestamp"]:
        idx = min(int(src_time * fps), len(actions) - 1)
        action = dict(actions[idx])
        action["timestamp"] = round(current_time, 4)
        new_actions.append(action)
        src_time += dt * speed_curve(current_time)
        current_time += dt

    return {"frequency": fps, "actions": new_actions}


# 示例：缓入缓出
def ease_in_out(t, ramp=1.0, total=8.0):
    if t < ramp:
        return 0.5 + 0.5 * t / ramp
    elif t > total - ramp:
        return 0.5 + 0.5 * (total - t) / ramp
    return 1.0

# retimed = retime_trajectory(traj, speed_curve=lambda t: ease_in_out(t, 1.0, 8.0))
```

---

## 八、完整工作流：从生成到回放

### 8.1 生成轨迹 JSON

```python
import json

# 用关键帧方法生成（第三章），或数学函数（第四章）
traj = generate_from_keyframes(dance_keyframes, fps=10)

# 保存到 recordings 目录
with open("recordings/my_dance.json", "w") as f:
    json.dump(traj, f, indent=2)
```

### 8.2 CLI 回放

```bash
# 连接
python -m robot_agent connect --port-name /dev/ttyACM0

# 半速测试（推荐首次使用）
python -m robot_agent replay --file my_dance --speed 0.5

# 确认安全后原速播放
python -m robot_agent replay --file my_dance --speed 1.0

# 断开
python -m robot_agent disconnect
```

### 8.3 Python API 回放

```python
from robot_agent import RobotAgent

agent = RobotAgent()
agent.connect(port_name="/dev/ttyACM0")

# 半速测试
agent.replay(speed=0.5, filename="my_dance")

# 原速
agent.replay(speed=1.0, filename="my_dance")

agent.disconnect()
```

---

## 九、示例轨迹详解

> 以下轨迹均由 `scripts/generate_demo_trajectories.py` 生成，可直接回放验证。
> 首次回放建议半速：`python -m robot_agent replay --file <名称> --speed 0.5`

### 9.1 wave_hello — 招手

**时长**：9s | **验证重点**：wrist_roll 摆动是否自然

手臂举起，gripper 张开模拟手掌，wrist_roll 左右交替摆动，模拟"打招呼"。

| 时间段 | 动作 | 关节变化 |
|--------|------|---------|
| 0~1.5s | 举起手臂 | shoulder_lift 0→-50，elbow_flex 0→-30，gripper 50→90 |
| 1.5~7.5s | 左右摆手 | wrist_roll ±30° 来回 3 次 |
| 7.5~9.0s | 归位 | 所有关节回到 0，gripper 回到 50 |

```bash
python -m robot_agent replay --file wave_hello --speed 1.0
```

---

### 9.2 thinking — 托腮思考

**时长**：10s | **验证重点**：shoulder_pan 微倾 + elbow_flex 保持弯曲

手臂弯曲到头部附近（夹爪微闭模拟托腮），shoulder_pan 缓缓左右微倾 2 次，模拟"思考"姿态。

| 时间段 | 动作 | 关节变化 |
|--------|------|---------|
| 0~2.0s | 弯曲到头部 | shoulder_pan 0→15，shoulder_lift 0→-40，elbow_flex 0→-60，wrist_flex 0→40，gripper 50→20 |
| 2.0~8.0s | 微倾思考 | shoulder_pan 10~20 来回 2 次，其余关节微调 |
| 8.0~10.0s | 归位 | 所有关节回到 0 |

```bash
python -m robot_agent replay --file thinking --speed 1.0
```

---

### 9.3 bow — 鞠躬

**时长**：7s | **验证重点**：shoulder_lift / elbow_flex 协调

肩部前倾 + 肘部弯曲，模拟鞠躬姿态。保持 1.5s 后起身归位。

| 时间段 | 动作 | 关节变化 |
|--------|------|---------|
| 0~1.5s | 前倾准备 | shoulder_lift 0→-30，elbow_flex 0→-50，wrist_flex 0→20，gripper 50→30 |
| 1.5~3.0s | 深鞠躬 | shoulder_lift -30→-15，elbow_flex -50→-70，wrist_flex 20→40，gripper 30→10 |
| 3.0~4.5s | 保持 | 所有关节不变 |
| 4.5~6.0s | 起身 | 与深鞠躬反向 |
| 6.0~7.5s | 归位 | 所有关节回到 0 |

```bash
python -m robot_agent replay --file bow --speed 1.0
```

---

### 9.4 pick_place — 夹爪抓放

**时长**：10s | **验证重点**：gripper 开合时序 + 位置移动协调

完整的抓取→搬运→放下流程：伸手到目标位置 → 闭合夹爪抓取 → 抬起 → 移到另一位置 → 放下 → 松开夹爪。

| 时间段 | 动作 | 关节变化 |
|--------|------|---------|
| 0~1.5s | 伸向目标 | shoulder_lift 0→-20，elbow_flex 0→-50，wrist_flex 0→30，gripper 90 保持 |
| 1.5~2.5s | 到达位置 | 进一步弯曲 elbow_flex -50→-55，wrist_flex 30→35 |
| 2.5~3.5s | **闭合夹爪** | gripper 90→5（抓住物体） |
| 3.5~5.0s | 抬起 | shoulder_lift -25→-50，elbow_flex -55→-25 |
| 5.0~6.5s | 搬运 | shoulder_pan 0→20（移到另一位置） |
| 6.5~7.5s | 放下 | shoulder_lift -50→-30，elbow_flex -25→-50 |
| 7.5~8.5s | **松开夹爪** | gripper 5→90（释放物体） |
| 8.5~10.0s | 归位 | 所有关节回到 0 |

```bash
python -m robot_agent replay --file pick_place --speed 1.0
```

---

### 9.5 spin_show — 展示旋转

**时长**：11s | **验证重点**：shoulder_pan 大范围旋转 ±50°

手臂举起后，底座大范围左右旋转，模拟"展示/呈现"姿态。wrist_roll 随旋转方向微转。

| 时间段 | 动作 | 关节变化 |
|--------|------|---------|
| 0~1.5s | 举起 | shoulder_lift 0→-55，elbow_flex 0→-20，gripper 50→80 |
| 1.5~3.5s | 转右 | shoulder_pan 0→50，wrist_roll 0→10 |
| 3.5~5.5s | 转左 | shoulder_pan 50→-50，wrist_roll 10→-10 |
| 5.5~7.5s | 转右 | shoulder_pan -50→50，wrist_roll -10→10 |
| 7.5~9.5s | 回中 | shoulder_pan 50→0，wrist_roll 10→0 |
| 9.5~11.0s | 归位 | 所有关节回到 0 |

```bash
python -m robot_agent replay --file spin_show --speed 1.0
```

---

### 9.6 stretch — 伸展运动

**时长**：12s | **验证重点**：全关节联动，活动范围最大

全关节大范围热身运动：举手向上 → 右侧伸展 → 左侧伸展 → 回上 → 弯曲收缩 → 再上 → 归位。

| 时间段 | 动作 | 关节变化 |
|--------|------|---------|
| 0~2.0s | 举手向上 | shoulder_lift 0→-70，gripper 50→80 |
| 2.0~3.0s | 保持 | — |
| 3.0~4.5s | 右伸 | shoulder_pan 0→30，shoulder_lift -70→-55，wrist_roll 0→20 |
| 4.5~6.0s | 左伸 | shoulder_pan 30→-30，wrist_roll 20→-20 |
| 6.0~7.5s | 回上 | shoulder_pan -30→0，shoulder_lift -55→-60 |
| 7.5~9.0s | 弯曲收缩 | shoulder_lift -60→-30，elbow_flex -15→-60，wrist_flex -15→30，gripper 80→20 |
| 9.0~10.5s | 再上 | 反向弯曲 |
| 10.5~12.0s | 归位 | 所有关节回到 0 |

```bash
python -m robot_agent replay --file stretch --speed 1.0
```

---

### 9.7 high_five — 击掌

**时长**：7s | **验证重点**：2.5→2.8s 的快速击下动作

手臂举起（gripper 全张模拟手掌），等待击掌 → 快速击下（0.3s 内完成）→ 弹回。

| 时间段 | 动作 | 关节变化 |
|--------|------|---------|
| 0~1.5s | 举手 | shoulder_lift 0→-55，elbow_flex 0→-15，gripper 50→95 |
| 1.5~2.5s | 等待击掌 | 保持高举，gripper 全张 |
| **2.5~2.8s** | **快速击下！** | shoulder_lift -55→-20，elbow_flex -15→-50，wrist_flex 0→25，gripper 95→10 |
| 2.8~3.3s | 保持 | — |
| 3.3~4.5s | 弹回 | 反向运动回高举 |
| 4.5~5.5s | 展示 | 保持高举 |
| 5.5~7.0s | 归位 | 所有关节回到 0 |

> ⚠️ 击下动作仅 0.3s，速度较快。建议首次用 `--speed 0.5` 测试。

```bash
python -m robot_agent replay --file high_five --speed 0.5   # 先半速
python -m robot_agent replay --file high_five --speed 1.0   # 确认安全后原速
```

---

### 9.8 combo — 三段组合

**时长**：~22s | **验证重点**：三段轨迹拼接 + 过渡帧是否平滑

招手 → 过渡 1s → 思考 → 过渡 1s → 鞠躬，使用 `concatenate_trajectories()` 拼接，过渡帧自动插值。

| 时间段 | 子动作 | 描述 |
|--------|--------|------|
| 0~7.0s | wave_hello | 招手（见 9.1） |
| 7.0~8.0s | 过渡帧 | 平滑插值从招手结束态到思考起始态 |
| 8.0~14.0s | thinking | 思考（见 9.2） |
| 14.0~15.0s | 过渡帧 | 平滑插值从思考结束态到鞠躬起始态 |
| 15.0~22.0s | bow | 鞠躬（见 9.3） |

> 此轨迹演示了 `concatenate_trajectories()` 函数的拼接能力，可在 `scripts/generate_demo_trajectories.py` 中查看生成代码。

```bash
python -m robot_agent replay --file combo --speed 0.5   # 22s 较长，建议先半速
```

---

### 9.9 dance — 6 阶段跳舞

**时长**：~19s | **验证重点**：全关节协调，多阶段过渡

最复杂的预设轨迹，包含 6 个阶段：起始→举臂→左右摆动+手腕翻转→举拳泵动→手腕花式扫臂→大臂画圈→回归原位。

| 阶段 | 时间 | 动作 | 关键关节 |
|------|------|------|---------|
| 1. 起始 | 0~1s | 静止在初始位置 | — |
| 2. 举臂 | 1~2.5s | 手臂抬起 | shoulder_lift→-55，elbow_flex→-30 |
| 3. 摆动 | 2.5~7s | shoulder_pan ±30° + wrist_roll 交替翻转 + gripper 开合 | shoulder_pan, wrist_roll, gripper |
| 4. 泵动 | 7~10s | 肘部反复弯曲-伸展 | elbow_flex, gripper |
| 5. 花式 | 10~14s | wrist_roll ±80° + shoulder_pan ±40° | wrist_roll, shoulder_pan |
| 6. 画圈 | 14~17s | shoulder_lift/elbow_flex/wrist_flex 圆形运动 | shoulder_lift, elbow_flex, wrist_flex |
| 7. 归位 | 17~19s | 平滑回到初始位置 | — |

> 此轨迹由早期独立脚本 `generate_dance_trajectory.py` 生成，关键帧定义较长，建议直接回放验证。

```bash
python -m robot_agent replay --file dance --speed 0.5   # 建议半速
```

---

### 验证顺序建议

从简单到复杂逐步验证：

```
bow → wave_hello → high_five → thinking → pick_place → spin_show → stretch → combo → dance
```

| 顺序 | 轨迹 | 难度 | 理由 |
|------|------|------|------|
| 1 | bow | ⭐ | 关节少、速度慢、安全 |
| 2 | wave_hello | ⭐ | 关节少、摆动规律 |
| 3 | high_five | ⭐⭐ | 有快速击下动作，需确认安全性 |
| 4 | thinking | ⭐⭐ | 微倾动作，需验证精度 |
| 5 | pick_place | ⭐⭐⭐ | gripper 时序关键 |
| 6 | spin_show | ⭐⭐⭐ | shoulder_pan 大范围旋转 |
| 7 | stretch | ⭐⭐⭐ | 全关节最大范围运动 |
| 8 | combo | ⭐⭐⭐⭐ | 多段拼接，验证过渡帧 |
| 9 | dance | ⭐⭐⭐⭐⭐ | 最复杂，全关节协调+6 阶段 |

---

## 十、安全注意事项

| ⚠️ 风险 | 防护措施 |
|---------|---------|
| **关节超限** | 生成轨迹前检查值域 [-100, 100]（gripper [0, 100]），用 `clamp()` 函数约束 |
| **速度过快** | 先 `--speed 0.5` 半速测试，确认安全后恢复 1.0 |
| **碰撞** | 首次回放新手持急停位置 |
| **力矩异常** | 确保 Max_Torque_Limit 正确（关节 1000，夹爪 500） |
| **Goal_Velocity** | 确保已恢复为 0（出厂默认），否则动作受限变慢 |
| **P_Coefficient** | 确保已恢复为 16（LeRobot 推荐），否则定位精度差 |

> 舵机参数恢复详见 `references/servo_parameters.md`

---

*文档版本: 2.1 | 更新时间: 2026-04-23*
