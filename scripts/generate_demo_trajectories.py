#!/usr/bin/env python3
"""批量生成多个示例轨迹，用于 SO-101 机械臂验证"""

import json
import math
import os

FREQUENCY = 10
JOINTS = [
    "shoulder_pan.pos", "shoulder_lift.pos", "elbow_flex.pos",
    "wrist_flex.pos", "wrist_roll.pos", "gripper.pos",
]


def lerp(a, b, t):
    return a + (b - a) * t


def smooth_step(t):
    return 0.5 * (1 - math.cos(math.pi * t))


def clamp(val, joint_name):
    if joint_name == "gripper.pos":
        return max(0, min(100, round(val)))
    return max(-100, min(100, round(val)))


def generate_from_keyframes(keyframes, fps=FREQUENCY):
    """从关键帧生成轨迹 (cosine smooth step 缓动)"""
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


def concatenate(trajectories, transitions=None):
    """拼接多段轨迹"""
    if transitions is None:
        transitions = [1.0] * (len(trajectories) - 1)
    fps = trajectories[0]["frequency"]
    dt = 1.0 / fps
    all_actions = []
    current_time = 0.0

    for i, traj in enumerate(trajectories):
        if i > 0:
            prev_end = all_actions[-1]
            curr_start = traj["actions"][0]
            joints = [k for k in prev_end.keys() if k != "timestamp"]
            transition_frames = int(transitions[i - 1] * fps)
            for f in range(transition_frames):
                alpha = smooth_step(f / transition_frames)
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


# ============================================================
# 关键帧格式: (time, shoulder_pan, shoulder_lift, elbow_flex, wrist_flex, wrist_roll, gripper)
# ============================================================

# 1. 招手 (wave_hello) — 手臂举起，gripper 张开，wrist_roll 左右摆动
wave_hello = generate_from_keyframes([
    (0.0,   0,    0,    0,    0,    0,   50),
    (1.5,   0,  -50,  -30,   10,    0,   90),
    (2.5,  10,  -50,  -25,    5,   30,   90),
    (3.5, -10,  -50,  -25,    5,  -30,   90),
    (4.5,  10,  -50,  -25,    5,   30,   90),
    (5.5, -10,  -50,  -25,    5,  -30,   90),
    (6.5,  10,  -50,  -25,    5,   30,   90),
    (7.5,   0,  -50,  -30,   10,    0,   90),
    (9.0,   0,    0,    0,    0,    0,   50),
])

# 2. 思考 (thinking) — 手托下巴，头部微倾，缓缓来回
thinking = generate_from_keyframes([
    (0.0,   0,    0,    0,    0,    0,   50),
    (2.0,  15,  -40,  -60,   40,   10,   20),
    (3.5,  20,  -42,  -58,   42,   15,   20),
    (5.0,  10,  -38,  -62,   38,    5,   20),
    (6.5,  20,  -42,  -58,   42,   15,   20),
    (8.0,  10,  -38,  -62,   38,    5,   20),
    (10.0,  0,    0,    0,    0,    0,   50),
])

# 3. 鞠躬 (bow) — 肩部前倾+肘部弯曲
bow = generate_from_keyframes([
    (0.0,   0,    0,    0,    0,    0,   50),
    (1.5,   0,  -30,  -50,   20,    0,   30),
    (3.0,   0,  -15,  -70,   40,    0,   10),
    (4.0,   0,  -15,  -70,   40,    0,   10),
    (5.5,   0,  -30,  -50,   20,    0,   30),
    (7.0,   0,    0,    0,    0,    0,   50),
])

# 4. 夹爪抓放 (pick_place) — 伸手→闭合→抬起→放下→松开
pick_place = generate_from_keyframes([
    (0.0,   0,    0,    0,    0,    0,   90),
    (1.5,   0,  -20,  -50,   30,    0,   90),
    (2.5,   0,  -25,  -55,   35,    0,   90),
    (3.5,   0,  -25,  -55,   35,    0,    5),
    (5.0,   0,  -50,  -25,    0,    0,    5),
    (6.5,  20,  -50,  -25,    0,    0,    5),
    (7.5,  20,  -30,  -50,   20,    0,    5),
    (8.5,  20,  -30,  -50,   20,    0,   90),
    (10.0,  0,    0,    0,    0,    0,   50),
])

# 5. 展示旋转 (spin_show) — 底座旋转 + 手臂伸展
spin_show = generate_from_keyframes([
    (0.0,   0,    0,    0,    0,    0,   50),
    (1.5,   0,  -55,  -20,    0,    0,   80),
    (3.5,  50,  -50,  -25,    5,   10,   80),
    (5.5, -50,  -50,  -25,    5,  -10,   80),
    (7.5,  50,  -50,  -25,    5,   10,   80),
    (9.5,   0,  -55,  -20,    0,    0,   80),
    (11.0,  0,    0,    0,    0,    0,   50),
])

# 6. 伸展运动 (stretch) — 全关节大范围运动，热身伸展
stretch = generate_from_keyframes([
    (0.0,   0,    0,    0,    0,    0,   50),
    (2.0,   0,  -70,  -10,  -10,    0,   80),
    (3.0,   0,  -70,  -10,  -10,    0,   80),
    (4.5,  30,  -55,  -30,    0,   20,   80),
    (6.0, -30,  -55,  -30,    0,  -20,   80),
    (7.5,   0,  -60,  -15,  -15,    0,   80),
    (9.0,   0,  -30,  -60,   30,    0,   20),
    (10.5,  0,  -60,  -15,  -15,    0,   80),
    (12.0,  0,    0,    0,    0,    0,   50),
])

# 7. 击掌 (high_five) — 伸手→停顿→快速击下→弹回
high_five = generate_from_keyframes([
    (0.0,   0,    0,    0,    0,    0,   50),
    (1.5,   0,  -55,  -15,    0,    0,   95),
    (2.5,   0,  -55,  -15,    0,    0,   95),
    (2.8,   0,  -20,  -50,   25,    0,   10),
    (3.3,   0,  -20,  -50,   25,    0,   10),
    (4.5,   0,  -55,  -15,    0,    0,   95),
    (5.5,   0,  -55,  -15,    0,    0,   95),
    (7.0,   0,    0,    0,    0,    0,   50),
])

# 8. 组合动作 (combo) — 招手 → 过渡 → 思考 → 过渡 → 鞠躬
wave_part = generate_from_keyframes([
    (0.0,   0,    0,    0,    0,    0,   50),
    (1.5,   0,  -50,  -30,   10,    0,   90),
    (2.5,  10,  -50,  -25,    5,   30,   90),
    (3.5, -10,  -50,  -25,    5,  -30,   90),
    (4.5,  10,  -50,  -25,    5,   30,   90),
    (5.5,   0,  -50,  -30,   10,    0,   90),
    (7.0,   0,    0,    0,    0,    0,   50),
])

think_part = generate_from_keyframes([
    (0.0,   0,    0,    0,    0,    0,   50),
    (1.5,  15,  -40,  -60,   40,   10,   20),
    (3.0,  20,  -42,  -58,   42,   15,   20),
    (4.5,  10,  -38,  -62,   38,    5,   20),
    (6.0,   0,    0,    0,    0,    0,   50),
])

bow_part = generate_from_keyframes([
    (0.0,   0,    0,    0,    0,    0,   50),
    (1.5,   0,  -30,  -50,   20,    0,   30),
    (3.0,   0,  -15,  -70,   40,    0,   10),
    (4.0,   0,  -15,  -70,   40,    0,   10),
    (5.5,   0,  -30,  -50,   20,    0,   30),
    (7.0,   0,    0,    0,    0,    0,   50),
])

combo = concatenate([wave_part, think_part, bow_part], transitions=[1.0, 1.0])


# ============================================================
# 保存
# ============================================================
OUTPUT_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "recordings",
)
os.makedirs(OUTPUT_DIR, exist_ok=True)

trajectories = {
    "wave_hello": wave_hello,
    "thinking": thinking,
    "bow": bow,
    "pick_place": pick_place,
    "spin_show": spin_show,
    "stretch": stretch,
    "high_five": high_five,
    "combo": combo,
}

for name, traj in trajectories.items():
    path = os.path.join(OUTPUT_DIR, f"{name}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(traj, f, indent=2, ensure_ascii=False)
    duration = traj["actions"][-1]["timestamp"]
    frames = len(traj["actions"])
    print(f"  {name:12s} | {frames:4d} frames | {duration:5.1f}s | -> {path}")

print(f"\nAll {len(trajectories)} trajectories saved to {OUTPUT_DIR}/")
