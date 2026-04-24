"""Robot Agent - CLI tool for robot arm control."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from robot_agent.core import RobotAgent
from robot_agent.commands import app

__all__ = ["RobotAgent", "app"]
__version__ = "2.0.0"