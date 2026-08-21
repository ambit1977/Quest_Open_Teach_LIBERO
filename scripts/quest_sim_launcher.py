#!/usr/bin/env python3
"""Small UDP launcher that lets the Quest start and stop LIBERO teleoperation."""

from __future__ import annotations

import argparse
import json
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent.parent
RUN_SCRIPT = PROJECT_DIR / "scripts" / "run_teleop_stage_macos.sh"
STAGE_COUNT = 8


class TeleopLauncher:
    def __init__(self) -> None:
        self.process: subprocess.Popen[str] | None = None
        self.stage = 3
        self.recent_request_ids: dict[str, float] = {}

    def _process_running(self) -> bool:
        return self.process is not None and self.process.poll() is None

    def start(self, stage: int) -> None:
        self.stage = stage
        if self._process_running():
            print(
                f"LAUNCHER already_running pid={self.process.pid} stage={self.stage}",
                flush=True,
            )
            return

        child_environment = os.environ.copy()
        child_environment["PYTHONWARNINGS"] = "ignore"
        self.process = subprocess.Popen(
            [str(RUN_SCRIPT), str(stage)],
            cwd=PROJECT_DIR,
            text=True,
            start_new_session=True,
            env=child_environment,
        )
        print(f"LAUNCHER started pid={self.process.pid} stage={stage}", flush=True)

    def stop(self) -> None:
        if not self._process_running():
            self.process = None
            print("LAUNCHER already_stopped", flush=True)
            return

        assert self.process is not None
        pid = self.process.pid
        print(f"LAUNCHER stopping pid={pid}", flush=True)
        try:
            os.killpg(pid, signal.SIGINT)
            self.process.wait(timeout=8)
        except subprocess.TimeoutExpired:
            os.killpg(pid, signal.SIGTERM)
            try:
                self.process.wait(timeout=4)
            except subprocess.TimeoutExpired:
                os.killpg(pid, signal.SIGKILL)
                self.process.wait(timeout=2)
        except ProcessLookupError:
            pass
        self.process = None
        print(f"LAUNCHER stopped pid={pid}", flush=True)

    def restart(self, stage: int) -> None:
        self.stop()
        self.start(stage)

    def handle(
        self,
        payload: bytes,
        address: tuple[str, int],
        server: socket.socket,
    ) -> None:
        try:
            request = json.loads(payload.decode("utf-8"))
            request_id = str(request["id"])
            command = str(request["command"]).lower()
            stage = int(request.get("stage", self.stage))
        except (UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError, ValueError):
            print(f"LAUNCHER invalid_request from={address[0]}", flush=True)
            return

        if command == "discover":
            response = json.dumps(
                {
                    "id": request_id,
                    "status": "discovered",
                    "stage": self.stage,
                },
                separators=(",", ":"),
            ).encode("utf-8")
            server.sendto(response, address)
            print(f"LAUNCHER discovered_by={address[0]}", flush=True)
            return

        now = time.monotonic()
        self.recent_request_ids = {
            key: timestamp
            for key, timestamp in self.recent_request_ids.items()
            if now - timestamp < 10
        }
        if request_id in self.recent_request_ids:
            return
        self.recent_request_ids[request_id] = now

        if not 1 <= stage <= STAGE_COUNT:
            print(f"LAUNCHER invalid_stage stage={stage}", flush=True)
            return

        print(
            f"LAUNCHER command={command} stage={stage} from={address[0]}",
            flush=True,
        )
        if command == "start":
            self.start(stage)
        elif command == "restart":
            self.restart(stage)
        elif command == "stop":
            self.stop()
        else:
            print(f"LAUNCHER invalid_command command={command}", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8125)
    args = parser.parse_args()

    launcher = TeleopLauncher()
    stopping = False

    def request_shutdown(_signum: int, _frame: object) -> None:
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGINT, request_shutdown)
    signal.signal(signal.SIGTERM, request_shutdown)

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as server:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((args.host, args.port))
        server.settimeout(0.5)
        print(f"LAUNCHER listening udp://{args.host}:{args.port}", flush=True)
        while not stopping:
            try:
                payload, address = server.recvfrom(4096)
            except socket.timeout:
                continue
            launcher.handle(payload, address, server)

    launcher.stop()
    print("LAUNCHER exiting", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
