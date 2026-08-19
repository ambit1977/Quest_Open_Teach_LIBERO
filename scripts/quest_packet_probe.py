#!/usr/bin/env python3
"""Receive Quest packets without starting LIBERO and report packet rates."""

from __future__ import annotations

import argparse
import time

import zmq


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--right-port", type=int, default=8087)
    parser.add_argument("--left-port", type=int, default=8110)
    parser.add_argument("--seconds", type=float, default=15.0)
    args = parser.parse_args()

    context = zmq.Context()
    poller = zmq.Poller()
    sockets: dict[zmq.Socket, str] = {}
    for label, port in (("right", args.right_port), ("left", args.left_port)):
        socket = context.socket(zmq.PULL)
        socket.setsockopt(zmq.LINGER, 0)
        socket.bind(f"tcp://{args.host}:{port}")
        poller.register(socket, zmq.POLLIN)
        sockets[socket] = label

    counts = {"right": 0, "left": 0}
    sizes = {"right": 0, "left": 0}
    started = time.monotonic()
    print(
        f"Listening for Quest packets on {args.host}:"
        f"{args.right_port}/{args.left_port} for {args.seconds:.1f}s"
    )
    try:
        while time.monotonic() - started < args.seconds:
            for socket, _ in poller.poll(250):
                payload = socket.recv()
                label = sockets[socket]
                counts[label] += 1
                sizes[label] = len(payload)
    finally:
        elapsed = max(time.monotonic() - started, 1e-9)
        for socket in sockets:
            socket.close()
        context.term()

    for label in ("right", "left"):
        print(
            f"{label}: packets={counts[label]} rate={counts[label] / elapsed:.1f}Hz "
            f"last_bytes={sizes[label]}"
        )
    if not any(counts.values()):
        raise SystemExit("No Quest packets received")


if __name__ == "__main__":
    main()
