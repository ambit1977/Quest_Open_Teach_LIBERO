from openteach.constants import VR_FREQ,  ARM_LOW_RESOLUTION, ARM_HIGH_RESOLUTION, ARM_TELEOP_CONT, ARM_TELEOP_STOP , GRIPPER_CLOSE, GRIPPER_OPEN
from openteach.components import Component
from openteach.utils.timer import FrequencyTimer
from openteach.utils.network import create_pull_socket, ZMQKeypointPublisher
import zmq

# This class is used to detect the hand keypoints from the VR and publish them.            
class OculusVRTwoHandDetector(Component):
    def __init__(self, 
                 host, 
                 oculus_right_port,
                 oculus_left_port,
                 keypoint_pub_port, 
                 button_port, 
                 button_publish_port,
                 teleop_reset_port,
                 teleop_reset_publish_port,
                 single_controller=False,
                 frequency=VR_FREQ,
    ):
        self.notify_component_start('vr detector')
        # Initializing the network socket for getting the raw keypoints
        self.raw_keypoint_right_socket = create_pull_socket(host, oculus_right_port)
        # Initializing the network socket for resolution button feedback
        self.single_controller = single_controller
        self.button_keypoint_socket = (
            None if single_controller else create_pull_socket(host, button_port)
        )
        self.teleop_reset_socket = create_pull_socket(host, teleop_reset_port)
        self.raw_keypoint_left_socket = (
            None if single_controller else create_pull_socket(host, oculus_left_port)
        )

        # ZMQ Keypoint publisher
        self.hand_keypoint_publisher = ZMQKeypointPublisher(
            host = host,
            port = keypoint_pub_port
        )

        # Publisher socket for button feedback
        self.button_socket_publisher = ZMQKeypointPublisher(
            host = host,
            port = button_publish_port
        ) 
        self.teleop_reset_publisher = ZMQKeypointPublisher(
            host=host,
            port=teleop_reset_publish_port,
        )
        self.timer = FrequencyTimer(frequency)


    # Function to process the data token received from the VR
    def _process_data_token(self, data_token):
        return data_token.decode().strip()

    # Function to Extract the Keypoints from the String Token sent by the VR
    def _extract_data_from_token(self, token):        
        data = self._process_data_token(token)
        information = dict()
        keypoint_vals = [0] if data.startswith('absolute') else [1]

        # Data is in the format <hand>:x,y,z|x,y,z|x,y,z
        vector_strings = data.split(':')[1].strip().split('|')
        for vector_str in vector_strings:
            vector_vals = vector_str.split(',')
            for float_str in vector_vals[:3]:
                keypoint_vals.append(float(float_str))
            
        information['keypoints'] = keypoint_vals
        return information

    # Function to Publish the right hand transformed Keypoints
    def _publish_right_data(self, keypoint_dict):
        self.hand_keypoint_publisher.pub_keypoints(
            keypoint_array = keypoint_dict['keypoints'], 
            topic_name = 'right'
        )

    # Function to Publish the left hand transformed Keypoints
    def _publish_left_data(self, keypoint_dict):
        self.hand_keypoint_publisher.pub_keypoints(
            keypoint_array= keypoint_dict['keypoints'],
            topic_name= 'left'
        )

    # Function to Publish the Resolution Button Feedback
    def _publish_button_data(self,button_feedback):
        self.button_socket_publisher.pub_keypoints(
            keypoint_array = button_feedback, 
            topic_name = 'button'
        )

    def _publish_reset_data(self, reset_requested):
        self.teleop_reset_publisher.pub_keypoints(
            keypoint_array=reset_requested,
            topic_name='reset',
        )

    # Function to publish the left/right hand keypoints and button Feedback 
    def stream(self):

        while True:
            try:
                self.timer.start_loop()

                # Getting the raw keypoints
                raw_right_keypoints = self.raw_keypoint_right_socket.recv()
                keypoint_right_dict = self._extract_data_from_token(raw_right_keypoints)
                self._publish_right_data(keypoint_right_dict)

                if self.single_controller:
                    # B is sent as an edge event. Poll it without making the
                    # The pose path must not wait for a separate status packet.
                    try:
                        reset_feedback = self.teleop_reset_socket.recv(zmq.NOBLOCK)
                    except zmq.Again:
                        reset_feedback = None
                    if reset_feedback == b'Reset':
                        print('QUEST_RESET_BUTTON_RECEIVED', flush=True)
                        self._publish_reset_data(1)
                else:
                    raw_left_keypoints = self.raw_keypoint_left_socket.recv()
                    button_feedback = self.button_keypoint_socket.recv()
                    reset_feedback = self.teleop_reset_socket.recv()
                    button_feedback_num = (
                        ARM_LOW_RESOLUTION
                        if button_feedback == b'Low'
                        else ARM_HIGH_RESOLUTION
                    )
                    keypoint_left_dict = self._extract_data_from_token(raw_left_keypoints)
                    self._publish_left_data(keypoint_left_dict)
                    self._publish_button_data(button_feedback_num)
                    if reset_feedback == b'Reset':
                        print('QUEST_RESET_BUTTON_RECEIVED', flush=True)
                        self._publish_reset_data(1)

                self.timer.end_loop()

            except KeyboardInterrupt:
                break

        self.raw_keypoint_right_socket.close()
        if self.raw_keypoint_left_socket is not None:
            self.raw_keypoint_left_socket.close()
        if self.button_keypoint_socket is not None:
            self.button_keypoint_socket.close()
        self.teleop_reset_socket.close()
        self.hand_keypoint_publisher.stop()
        self.teleop_reset_publisher.stop()
        print('Stopping the oculus keypoint extraction process.')
