#!/usr/bin/env python
"""重置电机参数到默认值"""

import argparse

from lerobot.robots.so_follower.config_so_follower import SO100FollowerConfig
from lerobot.robots.so_follower.so_follower import SOFollower
from lerobot.motors.feetech import OperatingMode


def reset_motor_params(
    port: str = "/dev/ttyACM1",
    robot_id: str = "my_awesome_follower_arm",
):
    """重置电机参数"""
    config = SO100FollowerConfig(port=port)
    config.id = robot_id

    robot = SOFollower(config)
    robot.bus.connect()

    print("=== 重置电机参数 ===")

    with robot.bus.torque_disabled():
        for motor in robot.bus.motors:
            robot.bus.write("Operating_Mode", motor, OperatingMode.POSITION.value)
            robot.bus.write("P_Coefficient", motor, 16)
            robot.bus.write("I_Coefficient", motor, 0)
            robot.bus.write("D_Coefficient", motor, 32)
            robot.bus.write("Goal_Velocity", motor, 0)
            
            if motor == "gripper":
                robot.bus.write("Max_Torque_Limit", motor, 500)
                robot.bus.write("Protection_Current", motor, 250)
                robot.bus.write("Overload_Torque", motor, 25)
            else:
                robot.bus.write("Max_Torque_Limit", motor, 1000)
            
            print(f"  {motor}: P=16, I=0, D=32, Goal_Velocity=0")

    robot.disconnect()
    print("\n参数已重置!")


def main():
    parser = argparse.ArgumentParser(description="重置电机参数")
    parser.add_argument("--port", default="/dev/ttyACM1", help="串口名称")
    parser.add_argument("--id", default="my_awesome_follower_arm", help="机器人 ID")
    args = parser.parse_args()

    reset_motor_params(port=args.port, robot_id=args.id)


if __name__ == "__main__":
    main()