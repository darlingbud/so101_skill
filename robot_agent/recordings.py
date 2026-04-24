"""RobotAgent record/replay functionality."""

import json
import threading
import time
from pathlib import Path

from robot_agent.robot_client import RobotClient


class Recorder:
    def __init__(self, host: str, port: int, frequency: int = 10):
        self.host = host
        self.port = port
        self.frequency = frequency
        self._recording = False
        self._record_data = None
        self._record_thread = None
        self._start_time = None

    def start(self, filename: Path):
        self._record_data = {"frequency": self.frequency, "actions": []}
        self._recording = True
        self._start_time = time.time()
        self._record_thread = threading.Thread(target=self._record_loop, args=(filename,), daemon=True)
        self._record_thread.start()

    def _record_loop(self, filename: Path):
        import logging
        logger = logging.getLogger(__name__)
        try:
            client = RobotClient(self.host, self.port)
            client.connect()
            while self._recording:
                try:
                    resp = client.send("get")
                    if resp.get("status") == "ok":
                        obs = resp.get("observation", {})
                        action = {"timestamp": time.time() - self._start_time, **obs}
                        self._record_data["actions"].append(action)
                except Exception as e:
                    logger.warning(f"Record error: {e}")
                time.sleep(1.0 / self.frequency)
            client.close()
        except Exception as e:
            logger.error(f"Record loop failed: {e}")
        finally:
            with open(filename, "w") as f:
                json.dump(self._record_data, f, indent=2)
            logger.info(f"Recording saved to {filename}")

    def stop(self):
        self._recording = False
        if self._record_thread:
            self._record_thread.join(timeout=5)


class Replayer:
    REPLAY_FREQ = 10
    INTERVAL = 1.0 / REPLAY_FREQ

    def __init__(self, host: str, port: int, speed: float = 1.0):
        self.host = host
        self.port = port
        self.speed = speed

    def replay(self, filename: Path) -> bool:
        import logging
        logger = logging.getLogger(__name__)
        try:
            with open(filename) as f:
                data = json.load(f)
        except Exception as e:
            logger.error(f"Failed to load recording: {e}")
            return False

        actions = data.get("actions", [])
        if not actions:
            logger.warning("No actions to replay")
            return False

        record_freq = data.get("frequency", 10)
        try:
            client = RobotClient(self.host, self.port)
            client.connect()
            total = len(actions)
            total_duration = actions[-1]["timestamp"]
            target_duration = total_duration / self.speed
            steps = int(target_duration * self.REPLAY_FREQ)
            logger.info(f"Replaying {total} actions at {self.speed}x speed ({steps} steps, {self.REPLAY_FREQ}Hz control)")

            idx = 0
            for step in range(steps):
                try:
                    t = step * self.INTERVAL
                    while idx < total - 1 and actions[idx + 1]["timestamp"] <= t:
                        idx += 1
                    if idx >= total - 1:
                        idx = total - 2
                    a1, a2 = actions[idx], actions[idx + 1]
                    t1, t2 = a1["timestamp"], a2["timestamp"]
                    if t2 == t1:
                        interpolated = a1
                    else:
                        alpha = (t - t1) / (t2 - t1)
                        interpolated = {
                            k: a1[k] + (a2[k] - a1[k]) * alpha if k != "timestamp" else t
                            for k in a1
                        }
                    positions = {k: v for k, v in interpolated.items() if k != "timestamp"}
                    cmd = "set " + " ".join(f"{k}={v}" for k, v in positions.items())
                    resp = client.send(cmd)
                    logger.debug(f"step {step+1}/{steps}: {resp.get('status')}")
                except (ConnectionError, OSError) as e:
                    logger.warning(f"Connection lost, reconnecting: {e}")
                    try:
                        client.close()
                        client.connect()
                        continue
                    except Exception:
                        logger.error("Failed to reconnect")
                        return False
                time.sleep(self.INTERVAL)

            client.close()
            logger.info("Replay complete")
            return True
        except Exception as e:
            logger.error(f"Replay failed: {e}")
            return False