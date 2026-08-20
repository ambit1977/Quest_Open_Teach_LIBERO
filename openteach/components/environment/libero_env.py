import os
import time
import numpy as np
import zmq
import json
from openteach.utils.timer import FrequencyTimer
from openteach.utils.network import ZMQCameraPublisher, ZMQCompressedImageTransmitter,ZMQKeypointPublisher,ZMQKeypointSubscriber
from openteach.components.environment.arm_env import Arm_Env
from openteach.constants import *
from openteach.utils.images import rescale_image

import robosuite.utils.transform_utils as T
from libero.libero import benchmark, get_libero_path

from libero.libero.envs import OffScreenRenderEnv

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
	):
		  
		self._timer=FrequencyTimer(VR_FREQ)
		self.host=host
		self.camport=camport
		self.stream_oculus=stream_oculus

		self._stream_oculus = stream_oculus

		#Define ZMQ pub/sub
		#Port for publishing rgb images.
		self.rgb_publisher = ZMQCameraPublisher(
			host = host,
			port = camport
		)
		# for ego-centric view
		self.rgb_publisher_ego = ZMQCameraPublisher(
			host = host,
			port = camport + 1
		)
		
		#Publishing the stream into the oculus.
		if self._stream_oculus:
			self.rgb_viz_publisher = ZMQCompressedImageTransmitter(
				host = host,
				port = camport + VIZ_PORT_OFFSET
			)
			self.rgb_viz_publisher_ego = ZMQCompressedImageTransmitter(
				host = host,
				port = camport + VIZ_PORT_OFFSET + 1
			)
		#Publisher for Depth data
		self.depth_publisher = ZMQCameraPublisher(
			host = host,
			port = camport + DEPTH_PORT_OFFSET 
		)
		# for ego-centric view
		self.depth_publisher_ego = ZMQCameraPublisher(
			host = host,
			port = camport + 1 + DEPTH_PORT_OFFSET 
		)

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

		#Publisher for timestamps
		self.timestamp_publisher = ZMQKeypointPublisher(
			host=host,
			port=timestamppublisherport
		)

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
			use_camera_obs=True,
			camera_names=["agentview", "robot0_eye_in_hand"],
			camera_heights=480,
			camera_widths=480,
			control_freq=20,
		)
		seed = np.random.randint(0, 100000)
		self.env.seed(seed)
		position = self.reset()
		self.robot_pose_publisher.pub_keypoints(position, 'robot_pose')
		self.publish_joint_angles()
		
	# Reset the environment
	def reset(self):
		self.obs = self.env.reset()
		return self.get_endeff_position()

	# Get the RGB and Depth Images
	def get_rgb_depth_images(self, camera_name=None):
		if camera_name is None:
			camera_name = 'agentview'
		rgb, depth = self.env.sim.render(width=480, height=480, camera_name=camera_name, depth=True)
		rgb = rgb[::-1, :, ::-1].astype(np.uint8)
		depth = depth[::-1, :].astype(np.uint8)
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

	def publish_joint_angles(self):
		joint_angles = np.asarray(self.env.sim.data.qpos[:7], dtype=np.float32)
		self.joint_angles_publisher.pub_keypoints(joint_angles, 'joint_angles')
		self.joint_angles_json_socket.send_string(
			'joint_angles ' + json.dumps(joint_angles.tolist())
		)
			
	@property              
	def timer(self):
		return self._timer
	   			
	# Take action
	def take_action(self):
		action = None
		while action is None:
			action = self.endeff_pos_subscriber.recv_keypoints(flags=zmq.NOBLOCK)
			if action is None:
				# Keep the Quest HUD alive while waiting for the first controller action.
				self.publish_joint_angles()
				time.sleep(0.05)
		action = np.clip(np.asarray(action, dtype=np.float32), -1.0, 1.0)
		self.obs, _, _, _ = self.env.step(action)                   

	# Stream the environment
	def stream(self):
		self.notify_component_start('{} environment'.format(self.name))
		
		while True:
			#try:
			self.timer.start_loop() 
			reset_request = self.teleop_reset_subscriber.recv_keypoints(flags=zmq.NOBLOCK)
			if reset_request is not None and int(np.asanyarray(reset_request).reshape(1)[0]) == 1:
				print('QUEST_STAGE_RESET environment', flush=True)
				self.reset()
			#Get RGB Images and Depth Images
			color_image,depth_image,timestamp=self.get_rgb_depth_images()
			color_image_ego, depth_image_ego, timestamp_ego=self.get_rgb_depth_images(camera_name='robot0_eye_in_hand')
			#Publishes RGB images
			self.rgb_publisher.pub_rgb_image(color_image, timestamp)
			self.rgb_publisher_ego.pub_rgb_image(color_image_ego, timestamp_ego)
			self.timestamp_publisher.pub_keypoints(timestamp,'timestamps')
			#Set this to True        
			if self._stream_oculus:
				self.rgb_viz_publisher.send_image(rescale_image(color_image, 2)) # 128 * 128
				self.rgb_viz_publisher_ego.send_image(rescale_image(color_image_ego, 2))

			# Publishing the depth images
			self.depth_publisher.pub_depth_image(depth_image, timestamp)
			self.depth_publisher_ego.pub_depth_image(depth_image_ego, timestamp_ego)
			
			#Gets the endeffector position       
			position=self.get_endeff_position()
			#Publishes the endeffector position so that Operator can use.
			self.endeff_publisher.pub_keypoints(position,'endeff_coords')


			# Publish joint telemetry before waiting for the next Quest action.
			self.publish_joint_angles()

			#Takes Action
			self.take_action()

			# Publish robot pose
			position = self.get_endeff_position()
			self.robot_pose_publisher.pub_keypoints(position, 'robot_pose')

			self.timer.end_loop()

	

			
