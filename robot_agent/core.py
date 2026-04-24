"""Core RobotAgent class - thin wrapper around RobotClient."""

import logging
import socket
import subprocess
from pathlib import Path
from typing import Optional

from robot_agent.robot_client import RobotClient
from robot_agent.config import DEFAULT_PORT_NAME, DEFAULT_ROBOT_ID, RECORDINGS_DIR

logger = logging.getLogger(__name__)


class RobotAgent:
    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8765,
        port_name: str = DEFAULT_PORT_NAME,
        robot_id: str = DEFAULT_ROBOT_ID,
    ):
        self.host = host
        self.port = port
        self.port_name = port_name
        self.robot_id = robot_id
        self._tmux_session = "robot_server"
        self._recorder = None
        self._replayer = None

    def is_server_online(self) -> bool:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            sock.connect((self.host, self.port))
            sock.sendall(b"ping\n")
            data = sock.recv(1024)
            sock.close()
            online = b"pong" in data
            logger.info(f"Server ping: {'online' if online else 'offline'}")
            return online
        except Exception as e:
            logger.debug(f"Server ping failed: {e}")
            return False

    def connect(self, timeout=30) -> bool:
        """Start robot_server in tmux and wait until connected to arm."""
        import time

        if self.is_server_online():
            logger.info(f"Server already running on {self.host}:{self.port}")
            return self._wait_connected(timeout)

        from pathlib import Path
        script_dir = Path(__file__).parent
        lerobot_src = "/home/donquixote/lerobot/src"
        env = f"PYTHONPATH={script_dir}:{lerobot_src}:$PYTHONPATH"
        cmd = [
            "tmux", "new-session", "-d", "-s", self._tmux_session,
            f"env {env} python {script_dir / 'robot_server.py'} "
            f"--port {self.port_name} --host {self.host} --port-num {self.port} --id {self.robot_id}"
        ]
        logger.info(f"Starting robot_server in tmux session '{self._tmux_session}'...")
        subprocess.run(cmd, check=True)
        return self._wait_connected(timeout)

    def _wait_connected(self, timeout=30) -> bool:
        import time
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.is_server_online():
                try:
                    with self._create_client() as client:
                        resp = client.send("status")
                        if resp.get("connected"):
                            logger.info("Robot arm connected")
                            return True
                except Exception:
                    pass
            time.sleep(0.5)
        logger.warning("Robot arm connection timeout")
        return False

    def disconnect(self) -> None:
        """Stop robot_server tmux session."""
        logger.info(f"Stopping robot_server tmux session '{self._tmux_session}'...")
        subprocess.run(["tmux", "kill-session", "-t", self._tmux_session], capture_output=True)
        logger.info("robot_server stopped")

    def _create_client(self) -> RobotClient:
        logger.debug(f"Creating new RobotClient connection to {self.host}:{self.port}")
        client = RobotClient(self.host, self.port)
        client.connect()
        return client

    def status(self):
        with self._create_client() as client:
            return client.send("status")

    def _check_connected(self):
        resp = self.status()
        if not resp.get("connected"):
            raise ConnectionError("Robot arm not connected")

    def home(self):
        self._check_connected()
        with self._create_client() as client:
            return client.send("home")

    def set_positions(self, **kwargs):
        self._check_connected()
        with self._create_client() as client:
            cmd = "set " + " ".join(f"{k}={v}" for k, v in kwargs.items())
            return client.send(cmd)

    def safe_pos(self):
        from robot_agent.config import SAFE_POSITIONS
        return self.set_positions(**SAFE_POSITIONS)

    def free(self):
        self.safe_pos()
        import time
        time.sleep(1)
        return self.send_command("free")

    def lock(self):
        return self.send_command("lock")

    def send_command(self, cmd):
        self._check_connected()
        with self._create_client() as client:
            resp = client.send(cmd)
            if resp.get("status") == "error" and "disconnected" in resp.get("message", "").lower():
                raise ConnectionError(resp.get("message"))
            return resp

    def get_observation(self):
        return self.send_command("get")

    def record(self, frequency: int = 10, filename: str = None):
        self._check_connected()
        from robot_agent.recordings import Recorder
        resp = self.status()
        if resp.get("locked"):
            logger.warning("Torque is locked. Run 'free' command first to enable movement recording.")
        if filename is None:
            filename = RECORDINGS_DIR / "last_recorded.json"
        else:
            filename = Path(filename)
        self._recorder = Recorder(self.host, self.port, frequency)
        self._recorder.start(filename)
        logger.info("Recording started. Press Enter to stop...")
        input()
        self._recorder.stop()
        logger.info("Recording stopped")

    def replay(self, speed: float = 1.0, filename: str = None):
        self._check_connected()
        from robot_agent.recordings import Replayer
        if filename is None:
            filename = RECORDINGS_DIR / "last_recorded.json"
        else:
            filename = Path(filename)
        self._replayer = Replayer(self.host, self.port, speed)
        return self._replayer.replay(filename)