"""Configuration for RobotAgent."""

from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.parent
RECORDINGS_DIR = SCRIPT_DIR / "recordings"
RECORDINGS_DIR.mkdir(exist_ok=True)

SAFE_POSITIONS = {
    "shoulder_pan.pos": 1.126972201352359,
    "shoulder_lift.pos": -97.32999582811848,
    "elbow_flex.pos": 100.0,
    "wrist_flex.pos": 71.68443496801706,
    "wrist_roll.pos": 0.024420024420024333,
    "gripper.pos": 0.9946949602122015,
}

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
DEFAULT_PORT_NAME = "/dev/robot_follower"
DEFAULT_ROBOT_ID = "my_awesome_follower_arm"