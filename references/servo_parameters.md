# 飞特 ST-3215 舵机默认参数恢复指南

> 适用于 ST-3215-C018 / ST-3215-C047 (12V, 齿轮比 1:345)  
> 适用于 RO-101 / SO-101 机械臂

---

## 一、你误修改的参数 vs 正确值

| 参数 | 你误设的值 | ✅ 出厂默认值 | ✅ LeRobot SO-101 推荐值 | 说明 |
|------|-----------|-------------|------------------------|------|
| **Goal_Velocity** | 300 | **0** | **0**（未设置，使用出厂默认） | 0 = 不限速（最大速度运行） |
| **Max_Torque_Limit** | 1000 (普通关节) / 500 (夹爪) | **1000** | **1000**（普通关节）/ **500**（夹爪） | 出厂1000=100%扭矩；LeRobot对夹爪设500=50%防烧 |
| **P_Coefficient** | 16 | **32** | **16** | 出厂32；LeRobot降至16避免抖动 |

### 结论

| 参数 | 普通关节(1-5)应恢复为 | 夹爪应恢复为 |
|------|---------------------|------------|
| **Goal_Velocity** | **0** | **0** |
| **Max_Torque_Limit** | **1000** | **500** |
| **P_Coefficient** | **16** (LeRobot推荐) 或 **32** (出厂) | **16** (LeRobot推荐) 或 **32** (出厂) |

> ⚠️ **如果你的机械臂跑的是 LeRobot 框架**：`P_Coefficient = 16` 和夹爪 `Max_Torque_Limit = 500` 本身就是 LeRobot 的正确配置值，**不需要改回出厂值 32 和 1000**。你主要需要修复的是 `Goal_Velocity`。

---

## 二、参数详细说明

### 1. Goal_Velocity（目标速度）
- **寄存器地址**: 46-47 (SRAM, 可读写)
- **出厂默认值**: **0**
- **范围**: -1000 ~ 1000
- **单位**: RPM（近似），bit 15 为方向位
- **含义**: 值为 0 表示**无速度限制**，舵机以最大速度运行
- **你设的 300**: 表示限速到约 300 RPM，会导致动作变慢

### 2. Max_Torque_Limit（最大扭矩限制）
- **寄存器地址**: 16-17 (EPROM, 可读写)
- **出厂默认值**: **1000**（= 100% 最大扭矩）
- **范围**: 0-1000
- **单位**: 0.1% 最大扭矩
- **LeRobot 配置**: 夹爪设为 **500**（= 50% 最大扭矩），防止持续夹持烧毁舵机
- **你设的 1000/500**: 和 LeRobot 默认配置一致，**如果没有跑 LeRobot 则普通关节也应该是 1000**

### 3. P_Coefficient（PID 比例系数）
- **寄存器地址**: 约 18 (EPROM, 可读写)
- **出厂默认值**: **32**
- **LeRobot 推荐值**: **16**（降低以避免机械臂抖动）
- **说明**: 值越大→响应越快，但过大导致振荡/抖动
- **你设的 16**: 正好是 LeRobot 的推荐值，**如果你的机械臂跑 LeRobot，这个值是正确的**

---

## 三、恢复参数的方法

### 方法一：使用 LeRobot 框架自动恢复（推荐）

如果你有 LeRobot 环境和 SO-101/RO-101 配置，运行校准或连接命令时会自动设置正确的参数：

```python
from lerobot.common.robots.so_follower import SoFollowerFollower

# 连接机械臂，configure() 会自动设置正确的 PID 和扭矩参数
robot = SoFollowerFollower(port="/dev/ttyUSB0", motors=...)
robot.connect()
```

`configure()` 方法会自动执行：
- `P_Coefficient` → 16（所有关节）
- `I_Coefficient` → 0（所有关节）
- `D_Coefficient` → 32（所有关节）
- `Max_Torque_Limit` → 500（仅夹爪）
- `Operating_Mode` → POSITION（所有关节）

但注意：**`Goal_Velocity` 在 LeRobot 源码中没有被显式设置**，所以如果它被你改了，需要手动恢复。

### 方法二：使用 Python SCServo SDK 手动写入

```python
from scs.servo_sdk import SmsStsSdk

# 初始化
sdk = SmsStsSdk(port="/dev/ttyUSB0", baudrate=1000000)

# 恢复每个电机的参数
for motor_id in range(1, 7):  # 假设电机 ID 1-6
    # Goal_Velocity 恢复为 0（地址 46-47）
    sdk.write(46, motor_id, 0, 2)  # 2 bytes
    
    # P_Coefficient 恢复为出厂 32 或 LeRobot 推荐 16（地址 18）
    sdk.write(18, motor_id, 16, 1)  # 1 byte，用 16 (LeRobot推荐)
    
    # Max_Torque_Limit 恢复为 1000（地址 16-17）
    if motor_id == 6:  # 夹爪
        sdk.write(16, motor_id, 500, 2)  # 夹爪 50%
    else:
        sdk.write(16, motor_id, 1000, 2)  # 普通关节 100%
```

### 方法三：使用飞特上位机调试软件

1. 下载飞特官方调试软件 **FD (FEETECH Debug)**  
   仓库地址：https://gitee.com/ftservo/fddebug  
   最新版本：FD1.9.8.5

2. 连接舵机总线到电脑

3. 在软件中：
   - 选择对应电机 ID
   - 找到 `Goal_Velocity` → 改为 **0**
   - 找到 `Max_Torque_Limit` → 普通关节改为 **1000**，夹爪改为 **500**
   - 找到 `P_Coefficient` → 改为 **16**（LeRobot推荐）或 **32**（出厂默认）

4. 写入后断电重启确认

### 方法四：硬件 RESET（最后手段）

如果参数完全混乱无法通信：
1. 找到舵机上的 **RESET 引脚**
2. 将 **RESET 引脚与 GND 短接** 2 秒
3. 断开短接，舵机恢复出厂设置
4. ⚠️ **注意**：恢复出厂后所有参数都会回到默认值（P_Coefficient=32, Max_Torque_Limit=1000, Goal_Velocity=0, ID=1），需要重新配置电机 ID 和 LeRobot 推荐参数

---

## 四、完整 PID 默认参数参考

| 参数 | 出厂默认 | LeRobot SO-101 | 寄存器地址 |
|------|---------|---------------|-----------|
| P_Coefficient | 32 | **16** | ~18 |
| I_Coefficient | 0 | **0** | ~19 |
| D_Coefficient | 0 或 32 | **32** | ~20 |

---

## 五、官方资料下载

| 资源 | 链接 |
|------|------|
| 飞特舵机协议手册（磁编码版） | https://www.feetech.cn/Data/feetechrc/upload/file/20240702/舵机协议手册-磁编码码版本.pdf |
| ST-3215-C018 产品规格书 | https://files.seeedstudio.com/wiki/reComputer-Jetson/lerobot/ST-3215-C018-20230720.pdf |
| STS3215-C001 产品规格书 | https://files.seeedstudio.com/wiki/reComputer-Jetson/lerobot/STS3215-C001-20230624.pdf |
| 飞特上位机调试软件 | https://gitee.com/ftservo/fddebug |
| ST3215 协议文档 (Perseus V2) | https://roar-qutrc.github.io/systems/st3215-protocol.html |
| Seeed Studio 飞特舵机维基 | https://wiki.seeedstudio.com/cn/feetech_servo/ |
| LeRobot SO-101 源码 | https://github.com/huggingface/lerobot/blob/main/src/lerobot/robots/so_follower/so_follower.py |

---

*文档生成时间: 2026-04-22*
