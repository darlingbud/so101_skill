# Robot Agent — SO-101/RO-101 Arm Control

> **Full documentation: [SKILL.md](SKILL.md)**

Client-server architecture robot arm controller with trajectory recording, generation, and replay.

## Quick Start

```bash
# Connect
python -m robot_agent connect --port-name /dev/ttyACM0

# Free → Record → Replay
python -m robot_agent free
python -m robot_agent record --freq 10 --out my_action
python -m robot_agent replay --file my_action --speed 1.0

# Disconnect
python -m robot_agent disconnect
```

## CLI Commands

| Command | Description |
|---------|-------------|
| `connect` | Connect to arm |
| `disconnect` | Disconnect |
| `status` | Check status |
| `get` | Get joint positions |
| `set key=value ...` | Set joint positions |
| `home` | Move to zero |
| `safe` | Move to safe position |
| `free` | Disable torque |
| `lock` | Enable torque |
| `record --freq 10` | Record trajectory |
| `replay --speed 1.0` | Replay trajectory |
| `test` | Hardware self-test |

## Reference Documents

- `references/trajectory_generation.md` — Trajectory generation guide (keyframe interpolation, math functions, choreography)
- `references/servo_parameters.md` — Feetech ST-3215 servo parameter recovery guide
