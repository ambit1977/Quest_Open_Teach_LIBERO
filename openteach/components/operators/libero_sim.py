import numpy as np
import matplotlib.pyplot as plt
import zmq

from tqdm import tqdm

from copy import deepcopy as copy
from openteach.constants import *
from openteach.utils.timer import FrequencyTimer
from openteach.utils.network import ZMQKeypointSubscriber, ZMQKeypointPublisher
from openteach.utils.vectorops import *
from openteach.utils.files import *
from scipy.spatial.transform import Rotation, Slerp
from .operator import Operator
from .calibrators.allegro import OculusThumbBoundCalibrator

import robosuite.utils.transform_utils as T
from scipy.spatial.transform import Rotation as R

np.set_printoptions(precision=2, suppress=True)


# Rotation should be filtered when it's being sent
class Filter:
	def __init__(self, state, comp_ratio=0.6):
		self.pos_state = state[:3]
		self.ori_state = state[3:7]
		self.comp_ratio = comp_ratio

	def __call__(self, next_state):
		self.pos_state = self.pos_state[:3] * self.comp_ratio + next_state[:3] * (1 - self.comp_ratio)
		ori_interp = Slerp([0, 1], Rotation.from_quat(
			np.stack([self.ori_state, next_state[3:7]], axis=0)),)
		self.ori_state = ori_interp([1 - self.comp_ratio])[0].as_quat()
		return np.concatenate([self.pos_state, self.ori_state])
	
class LiberoSimOperator(Operator):
	def __init__(
		self,
		host,
		transformed_keypoints_port,
		stream_configs,
		stream_oculus,
		endeff_publish_port,
		endeffpossubscribeport,
		robotposesubscribeport,
		moving_average_limit,
		arm_resolution_port = None,
		teleop_reset_port = None,
	):
		self.notify_component_start('libero operator')
		self._host, self._port = host, transformed_keypoints_port
		self._hand_transformed_keypoint_subscriber = ZMQKeypointSubscriber(
			host = self._host,
			port = self._port,
			topic = 'transformed_hand_coords'
		)
		self._arm_transformed_keypoint_subscriber = ZMQKeypointSubscriber(
			host=host,
			port=transformed_keypoints_port,
			topic='transformed_hand_frame'
		)


		# Initalizing the robot controller
		self.resolution_scale = 1 # NOTE: Get this from a socket
		self.arm_teleop_state = ARM_TELEOP_STOP # We will start as the cont
		self.gripper_correct_state =0
		self.pause_flag=0
		self.gripper_flag=1
		self.prev_gripper_flag=0
		self.prev_pause_flag=0
		self.pause_cnt=0
		self.gripper_cnt=0


		self._arm_resolution_subscriber = ZMQKeypointSubscriber(
			host = host,
			port = arm_resolution_port,
			topic = 'button'
		)

		self.end_eff_position_subscriber = ZMQKeypointSubscriber(
			host = host,
			port =  endeffpossubscribeport,
			topic = 'endeff_coords'

		)

		self.end_eff_position_publisher = ZMQKeypointPublisher(
			host = host,
			port = endeff_publish_port
		)

		# robot pose subscriber
		self.robot_pose_subscriber = ZMQKeypointSubscriber(
			host = host,
			port = robotposesubscribeport,
			topic = 'robot_pose'
		)
		self.teleop_reset_subscriber = ZMQKeypointSubscriber(
			host=host,
			port=teleop_reset_port,
			topic='reset',
		)

		# Calibrating to get the thumb bounds
		self._calibrate_bounds()

		self._stream_oculus=stream_oculus
		self.stream_configs=stream_configs
		self._timer = FrequencyTimer(VR_FREQ)
		self._robot='Libero_Sim'
		self.is_first_frame = True
		
		# Frequency timer
		self._timer = FrequencyTimer(VR_FREQ)
		self.direction_counter = 0
		self.current_direction = 0
		# Moving average queues
		self.moving_Average_queue = []
		self.moving_average_limit = moving_average_limit
		self.hand_frames = []
		self.count = 0
		# Controller position and orientation are mapped to the single LIBERO
		# arm's end-effector target. The Quest controller rotation is already
		# represented by the 3x3 hand frame received from Unity.
		self.controller_position_gain = 1.8
		self.position_servo_gain = 10.0
		self.controller_orientation_gain = 1.0
		self.max_orientation_step = 0.12
		# The received hand-frame axes are ordered differently from the
		# Panda yaw/pitch/roll convention observed in the Quest view. Remap
		# [current roll, current pitch, current yaw] to [yaw, pitch, roll].
		self.controller_rotation_axis_order = (2, 0, 1)

	@property
	def timer(self):
		return self._timer

	@property
	def robot(self):
		return self._robot
	
	@property
	def transformed_hand_keypoint_subscriber(self):
		return self._hand_transformed_keypoint_subscriber
	
	@property
	def transformed_arm_keypoint_subscriber(self):
		return self._arm_transformed_keypoint_subscriber
	
	#Calibrate the bounds
	def _calibrate_bounds(self):
		self.notify_component_start('calibration')
		calibrator = OculusThumbBoundCalibrator(self._host, self._port)
		self.hand_thumb_bounds = calibrator.get_bounds()
		print(f'THUMB BOUNDS IN THE OPERATOR: {self.hand_thumb_bounds}')

	# Get the hand frame
	def _get_hand_frame(self):
		for i in range(10):
			data = self.transformed_arm_keypoint_subscriber.recv_keypoints(flags=zmq.NOBLOCK)
			if not data is None: break 
		if data is None: return None
		return np.asanyarray(data).reshape(4, 3)
	
	# Get the resolution scale mode
	def _get_resolution_scale_mode(self):
		data = self._arm_resolution_subscriber.recv_keypoints(flags=zmq.NOBLOCK)
		if data is None:
			return self.resolution_scale
		mode = np.asanyarray(data).reshape(1)[0]
		return 0.5 if mode == ARM_LOW_RESOLUTION else 1.0
	
	# Get Homogenous matrix from the frame
	def _turn_frame_to_homo_mat(self, frame):
		t = frame[0]
		R = frame[1:]

		homo_mat = np.zeros((4, 4))
		homo_mat[:3, :3] = np.transpose(R)
		homo_mat[:3, 3] = t
		homo_mat[3, 3] = 1

		return homo_mat

	# Convert Homogenous matrix to cartesian vector 
	def _homo2cart(self, homo_mat):
		# Here we will use the resolution scale to set the translation resolution
		t = homo_mat[:3, 3]
		R = Rotation.from_matrix(
			homo_mat[:3, :3]).as_quat()

		cart = np.concatenate(
			[t, R], axis=0
		)
		return cart
	
	# convert cartesian vector to homogenous matrix
	def cart2homo(self, cart):
		homo=np.zeros((4,4))
		t = cart[0:3]
		R = Rotation.from_quat(cart[3:]).as_matrix()

		homo[0:3,3] = t
		homo[:3,:3] = R
		homo[3,:] = np.array([0,0,0,1])
		return homo

	# Get the scaled cartesian pose	
	def _get_scaled_cart_pose(self, moving_robot_homo_mat):
		# Get the cart pose without the scaling
		unscaled_cart_pose = self._homo2cart(moving_robot_homo_mat)

		# Get the current cart pose
		current_homo_mat = copy(self.robot.get_pose()['position'])
		current_cart_pose = self._homo2cart(current_homo_mat)

		# Get the difference in translation between these two cart poses
		diff_in_translation = unscaled_cart_pose[:3] - current_cart_pose[:3]
		scaled_diff_in_translation = diff_in_translation * self.resolution_scale
		
		scaled_cart_pose = np.zeros(7)
		scaled_cart_pose[3:] = unscaled_cart_pose[3:] # Get the rotation directly
		scaled_cart_pose[:3] = current_cart_pose[:3] + scaled_diff_in_translation # Get the scaled translation only

		return scaled_cart_pose
	 
	# Check if it is real robot or simulation
	def return_real(self):
		return False
			
	# Reset Teleoperation
	def _reset_teleop(self):
		# Just updates the beginning position of the arm
		print('****** RESETTING TELEOP ****** ')
		self.robot_frame=self.end_eff_position_subscriber.recv_keypoints()
		self.robot_init_H=self.cart2homo(self.robot_frame[2:])
		self.robot_moving_H = copy(self.robot_init_H)

		first_hand_frame = self._get_hand_frame()
		while first_hand_frame is None:
			first_hand_frame = self._get_hand_frame()
		self.controller_init_position = copy(first_hand_frame[0])
		self.controller_init_rotation = copy(
			self._turn_frame_to_homo_mat(first_hand_frame)[:3, :3]
		)

		self.is_first_frame = False

		return first_hand_frame
	
	# Get ARm Teleop state from Hand keypoints 
	def _get_arm_teleop_state_from_hand_keypoints(self):
		pause_state ,pause_status,pause_right =self.get_pause_state_from_hand_keypoints()
		pause_status =np.asanyarray(pause_status).reshape(1)[0] 
		return pause_state,pause_status,pause_right
	
	# Get Pause State from Hand Keypoints 
	def get_pause_state_from_hand_keypoints(self):
		transformed_hand_coords= self.transformed_hand_keypoint_subscriber.recv_keypoints()
		ring_distance = np.linalg.norm(transformed_hand_coords[OCULUS_JOINTS['ring'][-1]]- transformed_hand_coords[OCULUS_JOINTS['thumb'][-1]])
		middle_distance = np.linalg.norm(transformed_hand_coords[OCULUS_JOINTS['middle'][-1]]- transformed_hand_coords[OCULUS_JOINTS['thumb'][-1]])
		thresh = 0.04 
		pause_right= True
		if ring_distance < thresh or middle_distance < thresh:
			self.pause_cnt+=1
			if self.pause_cnt==1:
				self.prev_pause_flag=self.pause_flag
				self.pause_flag = not self.pause_flag       
		else:
			self.pause_cnt=0
		pause_state = np.asanyarray(self.pause_flag).reshape(1)[0]
		pause_status= False  
		if pause_state!= self.prev_pause_flag:
			pause_status= True 
		return pause_state , pause_status , pause_right
	
	# Get Gripper State from Hand Keypoints 
	def get_gripper_state_from_hand_keypoints(self):
		transformed_hand_coords= self.transformed_hand_keypoint_subscriber.recv_keypoints()
		pinky_distance = np.linalg.norm(transformed_hand_coords[OCULUS_JOINTS['pinky'][-1]]- transformed_hand_coords[OCULUS_JOINTS['thumb'][-1]])
		thresh = 0.03
		gripper_fr =False
		if pinky_distance < thresh:
			self.gripper_cnt+=1
			if self.gripper_cnt==1:
				self.prev_gripper_flag = self.gripper_flag
				self.gripper_flag = not self.gripper_flag 
				gripper_fl=True
		else: 
			self.gripper_cnt=0

		gripper_state = np.asanyarray(self.gripper_flag).reshape(1)[0]
		status= False  
		if gripper_state!= self.prev_gripper_flag:
			status= True
		return gripper_state , status , gripper_fr

	# Apply retargeted angles
	def _apply_retargeted_angles(self, log=False):
		reset_request = self.teleop_reset_subscriber.recv_keypoints(flags=zmq.NOBLOCK)
		if reset_request is not None and int(np.asanyarray(reset_request).reshape(1)[0]) == 1:
			print('QUEST_STAGE_RESET operator', flush=True)
			self.pause_flag = 0
			self.prev_pause_flag = 0
			self.arm_teleop_state = ARM_TELEOP_STOP
			self.is_first_frame = True
			self.moving_Average_queue.clear()
			self.end_eff_position_publisher.pub_keypoints(
				np.zeros(7),
				"endeff_coords",
			)
			return
		self.resolution_scale = self._get_resolution_scale_mode()

		# See if there is a reset in the teleop
		new_arm_teleop_state,pause_status,pause_right = self._get_arm_teleop_state_from_hand_keypoints()
		if self.is_first_frame or (self.arm_teleop_state == ARM_TELEOP_STOP and new_arm_teleop_state == ARM_TELEOP_CONT):
			moving_hand_frame = self._reset_teleop() # Should get the moving hand frame only once
		else:
			moving_hand_frame = self._get_hand_frame()
		self.arm_teleop_state = new_arm_teleop_state

		# gripper
		gripper_state,status_change, gripper_flag = self.get_gripper_state_from_hand_keypoints()
		if self.gripper_cnt==1 and status_change is True:
			self.gripper_correct_state= gripper_state
        # if status_change is True:
		if self.gripper_correct_state == GRIPPER_OPEN:
			gripper_state = -1
		elif self.gripper_correct_state == GRIPPER_CLOSE:
			gripper_state = 1

		if moving_hand_frame is None: 
			return # It means we are not on the arm mode yet instead of blocking it is directly returning
		
		# Map the controller to what the operator sees in LIBERO's fixed
		# `agentview` camera, rather than to the robot-base axes. The columns
		# are camera screen-right, screen-up, and forward-into-screen vectors
		# expressed in the robot world frame. They come from MuJoCo's live
		# agentview camera matrix for this task:
		#   right = camera +X, up = camera +Y, into screen = camera -Z.
		quest_to_robot = np.array([
			[0.0, -0.52881497, -0.84873714],
			[1.0, 0.0, 0.0],
			[0.0, 0.84873714, -0.52881497],
		])
		controller_delta = moving_hand_frame[0] - self.controller_init_position
		target_position = (
			self.robot_init_H[:3, 3]
			+ self.controller_position_gain * (quest_to_robot @ controller_delta)
		)

		# LIBERO accepts relative OSC actions. Servo toward the absolute target
		# using the actual current end-effector pose, rather than the previous
		# controller target. This makes holding the controller still hold the
		# arm at the corresponding XYZ point.
		current_robot_frame = self.robot_pose_subscriber.recv_keypoints()
		current_robot_frame = np.asanyarray(current_robot_frame)
		current_robot_H = self.cart2homo(current_robot_frame[2:])
		current_position = current_robot_H[:3, 3]
		rel_pos = (
			(target_position - current_position)
			* self.position_servo_gain
			* self.resolution_scale
		)
		# Convert controller rotation relative to the clutch/start pose into a
		# target Panda orientation. The relative rotation is applied in the
		# robot's initial end-effector frame, so yaw/pitch/roll all remain
		# anchored to the pose seen when teleoperation starts.
		current_hand_rotation = self._turn_frame_to_homo_mat(moving_hand_frame)[:3, :3]
		hand_delta_rotation = current_hand_rotation @ self.controller_init_rotation.T
		# Apply the Quest/Panda axis permutation to the delta before building
		# the target rotation. Permuting the final servo error instead would
		# leave a persistent error on the wrong Panda axis and cause drift even
		# while the controller is motionless.
		hand_delta_rotvec = Rotation.from_matrix(hand_delta_rotation).as_rotvec()
		mapped_delta_rotvec = hand_delta_rotvec[list(self.controller_rotation_axis_order)]
		mapped_delta_rotation = Rotation.from_rotvec(mapped_delta_rotvec).as_matrix()
		target_rotation = self.robot_init_H[:3, :3] @ mapped_delta_rotation
		rel_rotation = target_rotation @ current_robot_H[:3, :3].T
		rel_axis_angle = Rotation.from_matrix(rel_rotation).as_rotvec()
		rel_axis_angle *= self.controller_orientation_gain
		angle = np.linalg.norm(rel_axis_angle)
		if angle > self.max_orientation_step:
			rel_axis_angle *= self.max_orientation_step / angle
		action = np.concatenate([rel_pos, rel_axis_angle, [gripper_state]])

		self.count += 1
		if self.count % 30 == 0:
			print(
				"CONTROLLER_POSE "
				f"delta={controller_delta.round(3)} "
				f"rotvec={rel_axis_angle.round(3)} "
				f"target={target_position.round(3)} "
				f"current={current_position.round(3)} "
				f"action={rel_pos.round(3)}",
				flush=True,
			)

		averaged_action = moving_average(
			action,
			self.moving_Average_queue,
			self.moving_average_limit,
		)

		if self.arm_teleop_state == ARM_TELEOP_CONT and gripper_flag == False:
			self.end_eff_position_publisher.pub_keypoints(averaged_action,"endeff_coords")
		else:
			self.end_eff_position_publisher.pub_keypoints(np.concatenate([np.zeros(6),[gripper_state]]),"endeff_coords")
