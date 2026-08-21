#!/usr/bin/env python3
"""Non-disruptive live-rate profiler for the LIBERO Quest telemetry paths."""

from __future__ import annotations

import argparse
import json
import os
import time

import zmq


STREAMS = {
    10505: "main_video",
    10506: "hand_video",
    10009: "actual_eef",
    10010: "command_eef",
    11111: "robot_pose",
    10011: "joints",
    10012: "hud",
}


def percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[int(fraction * (len(ordered) - 1))]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=os.environ.get("OPENTEACH_HOST", "127.0.0.1"))
    parser.add_argument("--seconds", type=float, default=60.0)
    parser.add_argument("--report-every", type=float, default=5.0)
    args = parser.parse_args()

    context = zmq.Context()
    poller = zmq.Poller()
    metrics: dict[zmq.Socket, dict[str, object]] = {}
    for port, name in STREAMS.items():
        socket = context.socket(zmq.SUB)
        socket.setsockopt(zmq.SUBSCRIBE, b"")
        socket.setsockopt(zmq.CONFLATE, 1)
        socket.setsockopt(zmq.RCVHWM, 1)
        socket.connect(f"tcp://{args.host}:{port}")
        poller.register(socket, zmq.POLLIN)
        metrics[socket] = {
            "name": name,
            "port": port,
            "count": 0,
            "bucket": 0,
            "bytes": 0,
            "last": None,
            "gaps": [],
        }

    started = time.monotonic()
    next_report = started + args.report_every
    print(f"PROFILE_READY host={args.host} duration={args.seconds:.1f}s", flush=True)
    try:
        while time.monotonic() - started < args.seconds:
            for socket, _ in poller.poll(100):
                now = time.monotonic()
                parts = socket.recv_multipart()
                metric = metrics[socket]
                metric["count"] += 1
                metric["bucket"] += 1
                metric["bytes"] += sum(len(part) for part in parts)
                if metric["last"] is not None:
                    metric["gaps"].append(now - metric["last"])
                metric["last"] = now
            if time.monotonic() >= next_report:
                rates = " ".join(
                    f"{metric['name']}={metric['bucket'] / args.report_every:.1f}Hz"
                    for metric in metrics.values()
                )
                print(rates, flush=True)
                for metric in metrics.values():
                    metric["bucket"] = 0
                next_report += args.report_every
    finally:
        elapsed = max(time.monotonic() - started, 1e-9)
        print("PROFILE_SUMMARY", flush=True)
        for socket, metric in metrics.items():
            gaps = metric["gaps"]
            count = metric["count"]
            print(json.dumps({
                "stream": metric["name"],
                "port": metric["port"],
                "count": count,
                "hz": round(count / elapsed, 2),
                "avg_kb": round(metric["bytes"] / max(count, 1) / 1024, 2),
                "p95_gap_s": round(percentile(gaps, 0.95), 3) if gaps else None,
                "max_gap_s": round(max(gaps), 3) if gaps else None,
            }, separators=(",", ":")), flush=True)
            socket.close(0)
        context.term()


if __name__ == "__main__":
    main()
