#!/usr/bin/env python3
"""Create the configured LIBERO task, render, and step a zero action."""

from __future__ import annotations

import os

import numpy as np
from libero.libero import benchmark, get_libero_path
from libero.libero.envs import OffScreenRenderEnv


SUITE = os.environ.get("OPENTEACH_LIBERO_SUITE", "libero_90")
TASK = os.environ.get(
    "OPENTEACH_LIBERO_TASK",
    "LIVING_ROOM_SCENE2_pick_up_the_alphabet_soup_and_put_it_in_the_basket",
)


def main() -> None:
    suite_cls = benchmark.get_benchmark_dict()[SUITE]
    suite = suite_cls()
    names = suite.get_task_names()
    if TASK not in names:
        raise SystemExit(f"Task {TASK!r} is not in suite {SUITE!r}")
    task = suite.get_task(names.index(TASK))
    bddl = os.path.join(
        get_libero_path("bddl_files"), task.problem_folder, task.bddl_file
    )
    env = OffScreenRenderEnv(
        bddl_file_name=bddl,
        ignore_done=True,
        use_camera_obs=True,
        camera_names=["agentview", "robot0_eye_in_hand"],
        camera_heights=160,
        camera_widths=160,
        control_freq=20,
    )
    try:
        obs = env.reset()
        state = env.env.get_robot_state_vector(obs)
        frame = env.sim.render(width=160, height=160, camera_name="agentview")
        next_obs, reward, done, info = env.step(np.zeros(7, dtype=np.float32))
        next_state = env.env.get_robot_state_vector(next_obs)
        print(f"suite={SUITE}")
        print(f"task={TASK}")
        print(f"state_shape={state.shape} action_shape=(7,)")
        print(f"frame_shape={frame.shape} frame_dtype={frame.dtype}")
        print(
            f"step_ok reward={float(reward):.6f} done={bool(done)} "
            f"state_finite={bool(np.isfinite(next_state).all())} info={info}"
        )
    finally:
        env.close()


if __name__ == "__main__":
    main()
