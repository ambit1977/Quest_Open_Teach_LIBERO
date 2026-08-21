import os
import time
import threading
import numpy as np
import zmq
import json
from openteach.utils.timer import FrequencyTimer
from openteach.utils.network import ZMQCameraPublisher, ZMQCompressedImageTransmitter,ZMQKeypointPublisher,ZMQKeypointSubscriber
from openteach.components.environment.arm_env import Arm_Env
from openteach.constants import *

import robosuite.utils.transform_utils as T
from libero.libero import benchmark, get_libero_path

from libero.libero.envs import OffScreenRenderEnv


def safe_control_action(last_action, last_action_time, now, timeout, last_gripper):
	timed_out = now - last_action_time > timeout
	if timed_out:
		# OSC_POSE uses pose deltas, so a stale pose command must never repeat.
		action = np.concatenate([
			np.zeros(6, dtype=np.float32), [last_gripper],
		]).astype(np.float32)
		return action, True
	return np.asarray(last_action, dtype=np.float32), False


# Libero Environment class 
class LiberoEnv(Arm_Env):
	def __init__(self,
			 host,
			 camport,
			 timestamppublisherport,
			 endeff_publish_port,
			 endeffpossubscribeport,
				 robotposepublishport,
				 actualjointanglespublishport,
			 teleop_reset_port,
			 stream_oculus,
			 suite_name,
			 task_name,
			 control_freq=20,
			 camera_fps=15,
			 telemetry_fps=10,
			 action_timeout=0.25,
			 main_camera_resolution=256,
			 hand_camera_resolution=128,
			 low_quality_rendering=True,
			 publish_recording_streams=False,
			 publish_depth=False,
	):
		  
		self.control_freq = control_freq
		self.camera_fps = camera_fps
		self.telemetry_fps = telemetry_fps
		self.action_timeout = action_timeout
		self.main_camera_resolution = main_camera_resolution
		self.hand_camera_resolution = hand_camera_resolution
		self.low_quality_rendering = low_quality_rendering
		self.publish_recording_streams = publish_recording_streams
		self.publish_depth = publish_depth
		self._timer = FrequencyTimer(control_freq)
		self._sim_lock = threading.Lock()
		self._stop_event = threading.Event()
		self._frame_condition = threading.Condition()
		self._latest_camera_frame = None
		self._camera_sequence = 0
		self.host=host
		self.camport=camport
		self.stream_oculus=stream_oculus

		self._stream_oculus = stream_oculus

		# Camera sockets are created and used exclusively by the camera thread.
		# ZeroMQ sockets must not cross threads.
		self.rgb_publisher = None
		self.rgb_publisher_ego = None
		self.rgb_viz_publisher = None
		self.rgb_viz_publisher_ego = None
		self.depth_publisher = None
		self.depth_publisher_ego = None
		self.timestamp_publisher = None

		#Publisher for endeffector Positions 
		self.endeff_publisher = ZMQKeypointPublisher(
			host = host,
			port = endeff_publish_port
		)

		#Publisher for endeffector Velocities
		self.endeff_pos_subscriber = ZMQKeypointSubscriber(
			host = host,
			port = endeffpossubscribeport,
			topic='endeff_coords'
		)

		# Robot pose publisher
		self.robot_pose_publisher = ZMQKeypointPublisher(
			host = host,
			port = robotposepublishport
		)
		self.joint_angles_publisher = ZMQKeypointPublisher(
			host=host,
			port=actualjointanglespublishport,
		)
		self.joint_angles_json_socket = zmq.Context.instance().socket(zmq.PUB)
		self.joint_angles_json_socket.bind(f'tcp://{host}:10012')
		self.teleop_reset_subscriber = ZMQKeypointSubscriber(
			host=host,
			port=teleop_reset_port,
			topic='reset',
		)

		self.timestamppublisherport = timestamppublisherport

		self.name="Libero_Sim"

		# initialize env
		print("Initializing Environment")
		benchmark_dict = benchmark.get_benchmark_dict()
		task_suite = benchmark_dict[suite_name]()
		# get task id from list of task names
		task_id = task_suite.get_task_names().index(task_name)
		# create environment
		task = task_suite.get_task(task_id)
		task_name = task.name
		task_bddl_file = os.path.join(get_libero_path("bddl_files"), task.problem_folder, task.bddl_file)

		# LIBERO-plus adds view / robot-init parameters to its task classes.
		# Its ControlEnv wrapper supplies compatible defaults while retaining the
		# standard 7D OSC_POSE action interface expected by Open Teach.
		self.env = OffScreenRenderEnv(
			bddl_file_name=task_bddl_file,
			ignore_done=True,
			# Camera observations would render both cameras inside every env.step.
			# Quest video is rendered separately at camera_fps below.
			use_camera_obs=False,
			camera_names=["agentview", "robot0_eye_in_hand"],
			camera_heights=main_camera_resolution,
			camera_widths=main_camera_resolution,
			control_freq=control_freq,
		)
		if self.low_quality_rendering:
			# Quest teleoperation only needs a coarse operator preview. These
			# settings affect off-screen pixels, never physics, IK, or collision.
			quality = self.env.sim.model.vis.quality
			quality.shadowsize = 0
			quality.offsamples = 1
			quality.numslices = 12
			quality.numstacks = 8
			quality.numquads = 1
			self.env.sim.model.vis.global_.offwidth = main_camera_resolution
			self.env.sim.model.vis.global_.offheight = main_camera_resolution
		seed = np.random.randint(0, 100000)
		self.env.seed(seed)
		position = self.reset()
		self.robot_pose_publisher.pub_keypoints(position, 'robot_pose')
		self.publish_joint_angles()
		
	# Reset the environment
	def reset(self):
		with self._sim_lock:
			self.obs = self.env.reset()
			return self.get_endeff_position().copy()

	# Get the RGB and Depth Images
	def get_rgb_depth_images(self, camera_name=None, resolution=None):
		if camera_name is None:
			camera_name = 'agentview'
		if resolution is None:
			resolution = self.main_camera_resolution
		result = self.env.sim.render(
			width=resolution,
			height=resolution,
			camera_name=camera_name,
			depth=self.publish_depth,
		)
		if self.publish_depth:
			rgb, depth = result
			depth = depth[::-1, :].astype(np.float32)
		else:
			rgb, depth = result, None
		rgb = rgb[::-1, :, ::-1].astype(np.uint8)
		time = self.get_time()
		return rgb, depth, time
	
	# Get the time
	def get_time(self):
		return time.time()
	
	# Get the endeffector position
	def get_endeff_position(self):
		return np.concatenate([
			self.obs["robot0_gripper_qpos"],
			self.obs["robot0_eef_pos"],
			self.obs["robot0_eef_quat"],
		]) # [gripper_pos, eef_pos, eef_quat]

	def publish_joint_angles(self, joint_angles=None, publish_hud=True):
		if joint_angles is None:
			with self._sim_lock:
				joint_angles = np.asarray(self.env.sim.data.qpos[:7], dtype=np.float32).copy()
		self.joint_angles_publisher.pub_keypoints(joint_angles, 'joint_angles')
		if publish_hud:
			self.joint_angles_json_socket.send_string(
				'joint_angles ' + json.dumps(joint_angles.tolist())
			)
			
	@property              
	def timer(self):
		return self._timer
	   			
	def _create_camera_publishers(self):
		if self.publish_recording_streams:
			self.rgb_publisher = ZMQCameraPublisher(self.host, self.camport)
			self.rgb_publisher_ego = ZMQCameraPublisher(self.host, self.camport + 1)
		if self._stream_oculus:
			self.rgb_viz_publisher = ZMQCompressedImageTransmitter(
				self.host, self.camport + VIZ_PORT_OFFSET, jpeg_quality=45,
			)
			self.rgb_viz_publisher_ego = ZMQCompressedImageTransmitter(
				self.host, self.camport + VIZ_PORT_OFFSET + 1, jpeg_quality=40,
			)
		if self.publish_depth:
			self.depth_publisher = ZMQCameraPublisher(
				self.host, self.camport + DEPTH_PORT_OFFSET,
			)
			self.depth_publisher_ego = ZMQCameraPublisher(
				self.host, self.camport + DEPTH_PORT_OFFSET + 1,
			)
		self.timestamp_publisher = ZMQKeypointPublisher(
			self.host, self.timestamppublisherport,
		)

	def _stop_camera_publishers(self):
		for publisher in (
			self.rgb_publisher,
			self.rgb_publisher_ego,
			self.rgb_viz_publisher,
			self.rgb_viz_publisher_ego,
			self.depth_publisher,
			self.depth_publisher_ego,
			self.timestamp_publisher,
		):
			if publisher is not None:
				publisher.stop()

	def _camera_loop(self):
		self._create_camera_publishers()
		last_sequence = -1
		try:
			while not self._stop_event.is_set():
				with self._frame_condition:
					frame_changed = self._frame_condition.wait_for(
						lambda: self._stop_event.is_set()
						or self._camera_sequence != last_sequence,
						timeout=0.1,
					)
					if self._stop_event.is_set():
						break
					# A timeout is not a new frame. Re-sending the cached JPEG
					# doubled low-rate streams (6 Hz producer became ~12 Hz).
					if not frame_changed or self._latest_camera_frame is None:
						continue
					frame = self._latest_camera_frame
					last_sequence = self._camera_sequence
				(
					color_image,
					depth_image,
					timestamp,
					color_image_ego,
					depth_image_ego,
					timestamp_ego,
				) = frame

				if self.publish_recording_streams:
					self.rgb_publisher.pub_rgb_image(color_image, timestamp)
					self.rgb_publisher_ego.pub_rgb_image(color_image_ego, timestamp_ego)
				if self._stream_oculus:
					self.rgb_viz_publisher.send_image(color_image)
					self.rgb_viz_publisher_ego.send_image(color_image_ego)
				if self.publish_depth:
					self.depth_publisher.pub_depth_image(depth_image, timestamp)
					self.depth_publisher_ego.pub_depth_image(depth_image_ego, timestamp_ego)
				self.timestamp_publisher.pub_keypoints(timestamp, 'timestamps')
		finally:
			self._stop_camera_publishers()

	# Stream the environment
	def stream(self):
		self.notify_component_start('{} environment'.format(self.name))
		camera_thread = threading.Thread(
			target=self._camera_loop,
			name='libero-camera-stream',
			daemon=True,
		)
		camera_thread.start()
		last_action = np.zeros(7, dtype=np.float32)
		last_action_time = 0.0
		last_gripper = 0.0
		was_timed_out = True
		telemetry_interval = 1.0 / max(float(self.telemetry_fps), 1.0)
		next_hud_time = time.monotonic()
		camera_interval = 1.0 / max(float(self.camera_fps), 1.0)
		next_camera_time = time.monotonic()

		try:
			while True:
				self.timer.start_loop()
				reset_request = self.teleop_reset_subscriber.recv_keypoints(flags=zmq.NOBLOCK)
				if reset_request is not None and int(np.asanyarray(reset_request).reshape(1)[0]) == 1:
					print('QUEST_STAGE_RESET environment', flush=True)
					self.reset()
					last_action_time = 0.0

				now = time.monotonic()
				action = self.endeff_pos_subscriber.recv_keypoints(flags=zmq.NOBLOCK)
				if action is not None:
					last_action = np.clip(
						np.asarray(action, dtype=np.float32), -1.0, 1.0,
					)
					last_gripper = float(last_action[-1])
					last_action_time = now

				control_action, timed_out = safe_control_action(
					last_action,
					last_action_time,
					now,
					self.action_timeout,
					last_gripper,
				)
				if timed_out != was_timed_out:
					print(
						'QUEST_ACTION_TIMEOUT hold' if timed_out else 'QUEST_ACTION_RESUMED',
						flush=True,
					)
				was_timed_out = timed_out

				with self._sim_lock:
					self.obs, _, _, _ = self.env.step(control_action)
					position = self.get_endeff_position().copy()
					joint_angles = np.asarray(
						self.env.sim.data.qpos[:7], dtype=np.float32,
					).copy()

				self.endeff_publisher.pub_keypoints(position, 'endeff_coords')
				self.robot_pose_publisher.pub_keypoints(position, 'robot_pose')
				publish_hud = now >= next_hud_time
				self.publish_joint_angles(joint_angles, publish_hud=publish_hud)
				if publish_hud:
					next_hud_time = now + telemetry_interval

				# MuJoCo's macOS OpenGL context must render on the thread that
				# created the environment. Only JPEG encoding and ZeroMQ publishing
				# are delegated to the camera worker.
				if now >= next_camera_time:
					with self._sim_lock:
						color_image, depth_image, timestamp = self.get_rgb_depth_images(
							resolution=self.main_camera_resolution,
						)
						color_image_ego, depth_image_ego, timestamp_ego = self.get_rgb_depth_images(
							camera_name='robot0_eye_in_hand',
							resolution=self.hand_camera_resolution,
						)
					with self._frame_condition:
						self._latest_camera_frame = (
							color_image,
							depth_image,
							timestamp,
							color_image_ego,
							depth_image_ego,
							timestamp_ego,
						)
						self._camera_sequence += 1
						self._frame_condition.notify()
					next_camera_time = now + camera_interval
				self.timer.end_loop()
		finally:
			self._stop_event.set()
			with self._frame_condition:
				self._frame_condition.notify_all()
			camera_thread.join(timeout=2.0)

	

			
