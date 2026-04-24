#!/usr/bin/env python
"""Robot hardware test utilities."""

import os
import subprocess


def test_arm_port(port_name=None, verbose=True):
    """测试机械臂端口是否存在.

    Args:
        port_name: 指定端口，None 则测试默认端口
        verbose: 是否打印结果

    Returns:
        dict: {port: {"exists": bool, "readable": bool}}
    """
    ports = ["/dev/ttyACM0", "/dev/ttyACM1"] if port_name is None else [port_name]

    results = {}
    for port in ports:
        exists = os.path.exists(port)
        try:
            fd = os.open(port, os.O_RDONLY | os.O_NONBLOCK)
            os.close(fd)
            readable = True
        except Exception:
            readable = False

        results[port] = {"exists": exists, "readable": readable}
        if verbose:
            status = "OK" if exists and readable else "FAIL"
            print(f"[{status}] {port}: exists={exists}, readable={readable}")

    return results


def test_camera(camera_type=None, verbose=True):
    """测试相机端口.

    Args:
        camera_type: "opencv" 或 "realsense"，None 测试所有
        verbose: 是否打印结果

    Returns:
        list: 检测到的相机信息
    """
    cmd = ["lerobot-find-cameras"]
    if camera_type:
        cmd.append(camera_type)

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        output = result.stdout
    except subprocess.TimeoutExpired:
        output = ""
    except Exception as e:
        output = f"Error: {e}"

    cameras = []
    for line in output.split("\n"):
        if "Camera #" in line:
            cameras.append(line.strip())

    if verbose:
        if cameras:
            print(f"[OK] Found {len(cameras)} camera(s):")
            for cam in cameras:
                print(f"  {cam}")
        else:
            print(f"[FAIL] No {camera_type or 'any'} cameras found")

    return cameras