#!/usr/bin/env python
"""Robot server - maintains persistent connection to robot arm."""

import json
import logging
import socket
import sys
import threading
import time

from lerobot.robots.so_follower import SO100Follower, SO100FollowerConfig

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
    stream=sys.stdout,
)
logger = logging.getLogger("robot_server")


class RobotServer:
    def __init__(
        self, host="127.0.0.1", port=8765, port_name="/dev/ttyACM0", robot_id="my_awesome_follower_arm"
    ):
        self.host = host
        self.port = port
        self.port_name = port_name
        self.robot_id = robot_id
        self.robot = None
        self.server_socket = None
        self.running = False
        self.client_socket = None
        self.torque_locked = True
        self.connected = False
        self.connect_failed = False
        self.connect_error = None

    def start(self):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(1)
        logger.info(f"Server listening on {self.host}:{self.port}")

        self.running = True

        logger.info("Connecting to robot...")
        robot_thread = threading.Thread(target=self.connect_robot, daemon=True)
        robot_thread.start()
        robot_thread.join()

        if self.connect_failed:
            logger.error(f"Robot connection failed: {self.connect_error}")
            self._report_connect_error()
            self.running = False
            self.server_socket.close()
            return

        monitor_thread = threading.Thread(target=self.monitor_connection, daemon=True)
        monitor_thread.start()

        self.accept_loop()

    def _report_connect_error(self):
        try:
            self.server_socket.settimeout(5)
            client_sock, addr = self.server_socket.accept()
            logger.info(f"Reporting error to client {addr}")
            resp = json.dumps({
                "status": "error",
                "message": f"Robot connection failed: {self.connect_error}",
                "connected": False,
            }) + "\n"
            client_sock.sendall(resp.encode())
            client_sock.close()
        except Exception as e:
            logger.debug(f"Failed to report error to client: {e}")

    def connect_robot(self):
        logger.info(f"Connecting to robot at {self.port_name}...")
        try:
            self.config = SO100FollowerConfig(
                port=self.port_name,
            )
            self.config.id = self.robot_id
            self.robot = SO100Follower(self.config)
            self.robot.connect(calibrate=False)
            self.connected = True
            logger.info("Robot connected!")
        except Exception as e:
            self.connect_failed = True
            self.connect_error = str(e)
            logger.error(f"Failed to connect robot: {e}")
            raise

    def monitor_connection(self):
        while self.running:
            time.sleep(5)
            if not self.connected:
                continue
            try:
                self.robot.get_observation()
            except Exception as e:
                logger.warning(f"Arm disconnected! {e}")
                self.connected = False

    def _get_torque_status(self):
        if not self.robot or not self.connected:
            return self.torque_locked
        try:
            motors = list(self.robot.bus.motors.keys())
            if not motors:
                return self.torque_locked
            first_motor = motors[0]
            torque_enable = self.robot.bus.read("Torque_Enable", first_motor)
            actual_locked = bool(torque_enable)
            self.torque_locked = actual_locked
            return actual_locked
        except Exception:
            return self.torque_locked

    def accept_loop(self):
        while self.running:
            try:
                self.server_socket.settimeout(1.0)
                try:
                    self.client_socket, addr = self.server_socket.accept()
                except socket.timeout:
                    continue
                logger.info(f"Client connected: {addr}")
                self.handle_client()
            except Exception as e:
                if self.running:
                    logger.error(f"Accept error: {e}")

    def handle_client(self):
        client_sock = self.client_socket
        buffer = ""
        while self.running and client_sock:
            try:
                client_sock.settimeout(0.5)
                data = client_sock.recv(1024)
                if not data:
                    break

                buffer += data.decode("utf-8")

                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    if line.strip():
                        self.process_command(line.strip(), client_sock)

            except socket.timeout:
                continue
            except (AttributeError, OSError):
                break
            except Exception as e:
                logger.error(f"Client error: {e}")
                break

        logger.info("Client disconnected")

    def process_command(self, cmd, client_sock=None):
        if client_sock is None:
            client_sock = self.client_socket
        logger.info(f"Executing: {cmd}")

        def send_resp(data):
            try:
                if client_sock:
                    client_sock.sendall((json.dumps(data) + "\n").encode("utf-8"))
            except Exception as e:
                logger.error(f"Failed to send response: {e}")

        try:
            parts = cmd.split()
            command = parts[0].lower()

            if command == "ping":
                send_resp({"status": "ok", "connected": self.connected, "pong": True})
                return

            if not self.connected:
                send_resp({"status": "error", "message": "Arm disconnected", "connected": False})
                return

            if command == "get":
                obs = self.robot.get_observation()
                send_resp({"status": "ok", "connected": self.connected, "observation": obs})

            elif command == "status":
                actual_locked = self._get_torque_status()
                send_resp({"status": "ok", "connected": self.connected, "locked": actual_locked})

            elif command == "set":
                if len(parts) < 2:
                    send_resp({"status": "error", "message": "Usage: set motor.pos=value ..."})
                    return

                action = {}
                for part in parts[1:]:
                    if "=" in part:
                        key, val = part.split("=", 1)
                        action[key] = float(val)

                self.robot.send_action(action)
                send_resp({"status": "ok", "connected": self.connected, "action": action})

            elif command == "home":
                action = {f"{m}.pos": 0.0 for m in self.robot.bus.motors}
                self.robot.send_action(action)
                send_resp({"status": "ok", "connected": self.connected, "action": action})

            elif command == "free":
                logger.info("Disabling torque...")
                self.robot.bus.disable_torque()
                self.torque_locked = False
                send_resp({"status": "ok", "connected": self.connected, "message": "Torque disabled", "locked": False})

            elif command == "lock":
                self.robot.bus.enable_torque()
                self.torque_locked = True
                send_resp({"status": "ok", "connected": self.connected, "message": "Torque enabled", "locked": True})

            elif command == "quit":
                self.running = False
                send_resp({"status": "ok", "message": "Server shutting down"})
                import os
                os._exit(0)

            else:
                send_resp({"status": "error", "message": f"Unknown command: {command}"})

        except Exception as e:
            send_resp({"status": "error", "message": str(e)})

    def stop(self):
        self.running = False
        if self.robot:
            try:
                self.robot.disconnect()
            except Exception:
                pass
        if self.server_socket:
            self.server_socket.close()
        logger.info("Server stopped")


def main():
    host = "127.0.0.1"
    port = 8765
    port_name = "/dev/ttyACM0"
    robot_id = "my_awesome_follower_arm"

    for i, arg in enumerate(sys.argv):
        if arg == "--port" and i + 1 < len(sys.argv):
            port_name = sys.argv[i + 1]
        elif arg == "--host" and i + 1 < len(sys.argv):
            host = sys.argv[i + 1]
        elif arg == "--port-num" and i + 1 < len(sys.argv):
            port = int(sys.argv[i + 1])
        elif arg == "--id" and i + 1 < len(sys.argv):
            robot_id = sys.argv[i + 1]

    server = RobotServer(host, port, port_name, robot_id)

    try:
        server.start()
    except KeyboardInterrupt:
        server.stop()


if __name__ == "__main__":
    main()
