import unittest

import numpy as np

from openteach.components.detector.keypoint_transform import TransformHandPositionCoords
from openteach.components.environment.libero_env import safe_control_action


class ControllerTransformTests(unittest.TestCase):
    def test_controller_mode_preserves_distances_and_builds_rigid_frame(self):
        transform = TransformHandPositionCoords.__new__(TransformHandPositionCoords)
        transform.controller_mode = True
        transform.knuckle_points = (6, 16)
        points = np.zeros((24, 3), dtype=np.float64)
        points[:] = [1.0, 2.0, 3.035]
        points[0] = [1.0, 2.0, 3.0]
        points[6] = [1.03, 2.0, 3.06]
        points[16] = [0.97, 2.0, 3.06]
        points[19] = [1.025, 1.99, 3.04]
        points[23] = points[19]

        transformed, frame = transform.transform_keypoints(points)

        np.testing.assert_allclose(frame[0], points[0])
        np.testing.assert_allclose(frame[1], [1.0, 0.0, 0.0], atol=1e-7)
        np.testing.assert_allclose(frame[2], [0.0, -1.0, 0.0], atol=1e-7)
        np.testing.assert_allclose(frame[3], [0.0, 0.0, 1.0], atol=1e-7)
        self.assertAlmostEqual(
            np.linalg.norm(transformed[23] - transformed[19]),
            0.0,
        )


class ActionWatchdogTests(unittest.TestCase):
    def test_fresh_action_is_unchanged(self):
        action = np.array([0.1, -0.2, 0.3, 0.1, 0.2, 0.3, 1.0])
        safe, timed_out = safe_control_action(action, 1.0, 1.1, 0.25, 1.0)
        np.testing.assert_allclose(safe, action)
        self.assertFalse(timed_out)

    def test_stale_delta_is_zeroed_but_gripper_is_held(self):
        action = np.ones(7)
        safe, timed_out = safe_control_action(action, 1.0, 1.3, 0.25, -1.0)
        np.testing.assert_allclose(safe[:6], np.zeros(6))
        self.assertEqual(float(safe[6]), -1.0)
        self.assertTrue(timed_out)


if __name__ == '__main__':
    unittest.main()
