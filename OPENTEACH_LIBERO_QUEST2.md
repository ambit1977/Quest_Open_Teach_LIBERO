# Meta Quest 2 × Open Teach × LIBERO-plus

## Current status (2026-08-19)

The Mac side is implemented and verified through the hardware boundary.

- Existing PARC2026 LIBERO environment remains unchanged.
- A separate Python 3.10 `.venv` contains only `pyzmq` and `blosc`.
- Open Teach configuration composes successfully for `libero_sim`.
- LIBERO-plus `libero_90` creates the configured Panda task, renders a camera
  frame, and accepts a 7D action.
- All five Open Teach processes start on macOS using the `spawn` start method.
- Quest receive ports 8087 and 8110 and internal transport ports were observed
  in LISTEN/ESTABLISHED state on `192.168.1.18`.
- The four demonstration recorder processes start successfully.
- Android platform tools 37.0.1 are installed.
- No Quest was attached to ADB during this work, so APK install, real packet
  reception, Panda motion, and a non-empty demonstration remain hardware tests.

The supplied Unity project explicitly enables both `TargetQuest` and
`TargetQuest2`; its Android minimum SDK is 23 and target architecture is ARM64.
No device-model rejection was found in the application scripts.

## Files and versions

- Open Teach commit: `32a7d44b33953066ff27312a7b2b4c294f4f52c5`
- LIBERO-plus commit: `4976dc30028e805ff8094b55501d532c48fec182`
- Bimanual APK: `VR/APK/BimanualArm.apk`
- APK SHA256: `13e4a6c0fefd218195b62f9c3024d2a84fab690f42c24a6a572ef7d5a9e2c2d5`
- Installed Android package: `com.NYU.Bimanual`
- Unity source bundle identifier: `com.Xigbee.Bimanual` (the supplied APK was
  built with the different package name above)

## One-time Mac setup

```bash
cd "/Users/ambit/Documents/キャリアデザイン/東大松尾研究室/Open-Teach-LIBERO"
./scripts/setup_macos_libero.sh
```

Do not run the upstream `conda env create -f environment.yml` on this Mac. It
would introduce PyTorch 1.12, RealSense, ROS, and real-robot dependencies that
are not part of the LIBERO simulation path.

## Install the Quest APK

1. Enable Developer Mode for Quest 2.
2. Enable Hand Tracking.
3. Connect Quest 2 to the Mac with a data-capable USB cable.
4. Unlock the headset and approve the USB debugging prompt.
5. Run:

```bash
adb devices -l
./scripts/install_quest_apk.sh
```

The app appears under unknown sources / developer applications as Bimanual.

## Verify Quest network packets first

Quest and Mac must be on the same non-guest Wi-Fi. The current Mac address is
`192.168.1.18`; the launcher detects it from the default interface each time.
The macOS application firewall is currently disabled.

Before LIBERO, run the receiver probe:

```bash
source scripts/macos_env.sh
python scripts/quest_packet_probe.py --host "$OPENTEACH_HOST" --seconds 20
```

In the Quest app:

1. Open Menu.
2. Select Change IP.
3. Enter the address printed by `macos_env.sh` (currently `192.168.1.18`).
4. Select Stream.
5. Move both hands while the probe is running.

Success requires non-zero packet counts on the right (8087) and left (8110)
ports. Stop the probe before starting teleoperation because both use the same
ports.

## Run teleoperation

```bash
./scripts/run_teleop_macos.sh
```

To override automatic LAN detection:

```bash
OPENTEACH_HOST=192.168.1.18 ./scripts/run_teleop_macos.sh
```

Quest Bimanual controls from the upstream application:

- Index pinch: start arm teleoperation.
- Middle or ring pinch: pause/resume (clutch).
- Pinky pinch: open/close gripper.
- Low/High resolution in the app changes translation scale.

### Touch controller pose control

The Quest 2 Touch controller is used as a single virtual hand for the LIBERO
Panda arm. Move the controller to control the end-effector XYZ position and
rotate the controller to control the end-effector orientation:

- controller left/right turn: Panda yaw
- controller up/down tilt: Panda pitch
- controller twist around its handle axis: Panda roll

The pose at the moment teleoperation starts (or resumes after a clutch) is the
neutral pose. The Python operator receives the existing 3x3 hand frame produced
by Unity, computes the relative rotation, and sends LIBERO's 7D OSC action
`[dx, dy, dz, dRx, dRy, dRz, gripper]`. Translation and rotation are filtered
and the per-frame rotation step is limited for safety. If orientation feels
too slow or too fast, adjust `controller_orientation_gain` and
`max_orientation_step` in `openteach/components/operators/libero_sim.py`.

The A button is the controller clutch/pause. Release the clutch and resume from
a comfortable neutral pose before reaching for a new object. The B button
requests a stage reset through the existing reset path.

The repository already contains calibration bounds. To recalibrate using Quest
2 hand geometry, start streaming first and then run:

```bash
OPENTEACH_RECALIBRATE=1 ./scripts/run_teleop_macos.sh
```

Follow each terminal prompt while holding the requested thumb pose. A normal
launch reuses the saved calibration without prompting.

## Collect one demonstration

Keep teleoperation running. In a second terminal:

```bash
cd "/Users/ambit/Documents/キャリアデザイン/東大松尾研究室/Open-Teach-LIBERO"
./scripts/run_data_collect_macos.sh 1
```

Perform the task, then press Ctrl-C in the collector terminal first. Press
Ctrl-C in the teleoperation terminal afterward. Data is written under:

```text
extracted_data/demonstration_1/
```

Validate that the episode is non-empty and readable:

```bash
source scripts/macos_env.sh
python scripts/validate_demonstration.py extracted_data/demonstration_1
```

The validator checks HDF5 dataset lengths and finite numeric values, plus AVI
frame count, dimensions, and first-frame readability. A generated filename by
itself is not considered success.

Open Teach stores actual and commanded Cartesian state, RGB, depth, and
timestamps. Reward, success, and an explicit `(observation_t, action_t,
observation_t+1)` training table are not added automatically. A later LeRobot
converter must align timestamps, derive 7D actions, attach the language task,
and annotate episode success.

## Diagnostics

Run the offline LIBERO test:

```bash
source scripts/macos_env.sh
python scripts/smoke_test_libero.py
```

Expected essentials:

```text
state_shape=(9,) action_shape=(7,)
frame_shape=(160, 160, 3) frame_dtype=uint8
step_ok ... state_finite=True
```

Inspect sockets while teleoperation is running:

```bash
lsof -nP -iTCP | grep Python
```

Important ports:

| Port | Purpose |
| ---: | --- |
| 8087 | Quest right-hand input |
| 8110 | Quest left-hand input |
| 8088 | decoded keypoints |
| 8089 | transformed right-hand keypoints |
| 8093 | resolution mode |
| 10005/10006 | RGB streams |
| 11005/11006 | depth streams |
| 10008 | timestamps |
| 10009/10010 | actual/commanded end-effector state |
| 11111 | robot pose |

If the Quest border does not turn green or packet counts stay zero, check the
entered Mac IP, headset and Mac Wi-Fi SSIDs, VPN, guest-network client
isolation, and USB-installed app permissions. The transport is TCP ZeroMQ.

## Source changes

- `configs/network.yaml`: runtime host address via `OPENTEACH_HOST`.
- `openteach/components/initializers.py`: macOS spawn-safe process targets and
  lazy physical-camera imports.
- `openteach/components/environment/libero_env.py`: LIBERO-plus wrapper and
  explicit 9D robot state construction; actions are clipped to `[-1, 1]`.
- `openteach/components/operators/libero_sim.py`: initialize gripper debounce
  state and apply Low/High resolution as 0.5x/1.0x translation scaling.
- `openteach/components/operators/calibrators/allegro.py`: non-interactive
  saved-calibration reuse.
- `openteach/components/recorders/sim_state.py`: commanded-state recording fix.
- `teleop.py`, `data_collect.py`: graceful child-process shutdown.

## Remaining hardware gates

1. Authorize Quest 2 in `adb devices -l` and install the Bimanual APK.
2. Confirm menu, hand tracking, IP entry, and green Stream border.
3. Obtain non-zero real packet rates with `quest_packet_probe.py`.
4. Verify translation, rotation, pause/resume, and gripper against the rendered
   Panda—not just socket activity.
5. Record and validate one real episode.
6. Only after the hand-tracking path works, evaluate the Touch-controller fork.

Upstream references:

- https://github.com/aadhithya14/Open-Teach
- https://github.com/aadhithya14/Open-Teach/blob/main/docs/simulation.md
- https://github.com/aadhithya14/Open-Teach/blob/main/docs/vr.md
