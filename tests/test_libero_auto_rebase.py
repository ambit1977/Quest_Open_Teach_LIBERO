import unittest

import numpy as np

from openteach.components.operators.libero_sim import LiberoSimOperator


class LiberoAutoRebaseTests(unittest.TestCase):
	def make_operator(self):
		op = LiberoSimOperator.__new__(LiberoSimOperator)
		op.panda_joint_lower = np.array([
			-2.8973, -1.7628, -2.8973, -3.0718, -2.8973, -0.0175, -2.8973,
		])
		op.panda_joint_upper = np.array([
			2.8973, 1.7628, 2.8973, -0.0698, 2.8973, 3.7525, 2.8973,
		])
		op.joint_limit_margin = 0.05
		op.rebase_position_error = 0.04
		op.rebase_rotation_error = np.deg2rad(15.0)
		op.rebase_motion_epsilon = 0.0007
		op.rebase_rotation_motion_epsilon = np.deg2rad(0.25)
		op.rebase_required_frames = 3
		op.rebase_cooldown_frames = 60
		op.constraint_frames = 0
		op.rebase_cooldown = 0
		op.moving_Average_queue = [np.ones(7)]
		op.auto_rebase_count = 0
		return op

	def test_joint_limit_detection_handles_asymmetric_joints(self):
		op = self.make_operator()
		center = (op.panda_joint_lower + op.panda_joint_upper) / 2
		self.assertFalse(op._joint_near_limit(center))
		near_j6_upper = center.copy()
		near_j6_upper[5] = op.panda_joint_upper[5] - 0.01
		self.assertTrue(op._joint_near_limit(near_j6_upper))

	def test_constraint_requires_persistent_stall(self):
		op = self.make_operator()
		for _ in range(op.rebase_required_frames - 1):
			self.assertFalse(op._update_constraint_detector(
				0.06, 0.0, 0.0, 0.0, False, True,
			))
		self.assertTrue(op._update_constraint_detector(
			0.06, 0.0, 0.0, 0.0, False, True,
		))

	def test_motion_prevents_auto_rebase(self):
		op = self.make_operator()
		for _ in range(op.rebase_required_frames + 2):
			self.assertFalse(op._update_constraint_detector(
				0.06, 0.0, 0.002, 0.0, True, True,
			))

	def test_auto_rebase_aligns_controller_and_robot_anchors(self):
		op = self.make_operator()
		robot = np.eye(4)
		robot[:3, 3] = [0.42, -0.11, 0.27]
		hand = np.zeros((4, 3))
		hand[0] = [1.2, 0.4, -0.3]
		hand_rotation = np.eye(3)
		op._auto_rebase(robot, hand, hand_rotation)
		np.testing.assert_allclose(op.robot_init_H, robot)
		np.testing.assert_allclose(op.controller_init_position, hand[0])
		np.testing.assert_allclose(op.controller_init_rotation, hand_rotation)
		self.assertEqual(op.moving_Average_queue, [])
		self.assertEqual(op.auto_rebase_count, 1)


if __name__ == '__main__':
	unittest.main()
