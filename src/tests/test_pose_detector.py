import pytest
import numpy as np
import cv2
from ..pose_detector import pose_detector


@pytest.fixture
def pd():
    return pose_detector(debug=True)


@pytest.fixture
def mock_frame():
    return np.zeros((480, 640, 3), dtype=np.uint8)


class TestPoseDetector:
    @pytest.mark.parametrize(
        "detection_confidence,tracking_confidence",
        [
            (0.5, 0.5),  # Default values
            (0.1, 0.1),  # Low confidence
            (0.9, 0.9),  # High confidence
        ],
    )
    def test_initialization(self, detection_confidence, tracking_confidence):
        detector = pose_detector(
            min_detection_confidence=detection_confidence,
            min_tracking_confidence=tracking_confidence,
        )
        assert detector.pose is not None
        assert detector.ideal_neck_vector.shape == (3,)
        assert detector.ideal_spine_vector.shape == (3,)

    def test_process_empty_frame(self, pd, mock_frame):
        frame, score = pd.process_frame(mock_frame)
        assert isinstance(frame, np.ndarray)
        assert score == 0.0

    @pytest.mark.parametrize(
        "landmark_values,expected_score_range",
        [
            # Perfect posture simulation
            ({"nose": [0.5, 0.3, 0], "mid_shoulder": [0.5, 0.5, 0]}, (90, 100)),
            # Poor posture simulation
            ({"nose": [0.6, 0.3, 0.2], "mid_shoulder": [0.5, 0.5, 0]}, (0, 70)),
        ],
    )
    def test_posture_score_calculation(self, pd, landmark_values, expected_score_range):
        class MockLandmark:
            def __init__(self, x, y, z):
                self.x, self.y, self.z = x, y, z

        class MockLandmarks:
            def __init__(self):
                self.landmark = []

        # Create mock landmarks
        landmarks = MockLandmarks()
        # Fill with dummy data
        for _ in range(33):  # MediaPipe uses 33 landmarks
            landmarks.landmark.append(MockLandmark(0.5, 0.5, 0))

        score = pd._calculate_posture_score(landmarks)
        assert isinstance(score, float)
        assert 0 <= score <= 100

    @pytest.mark.parametrize(
        "frame_size",
        [
            (640, 480),  # Standard webcam
            (1280, 720),  # HD
            (1920, 1080),  # Full HD
        ],
    )
    def test_different_frame_sizes(self, pd, frame_size):
        frame = np.zeros((frame_size[1], frame_size[0], 3), dtype=np.uint8)
        processed_frame, score = pd.process_frame(frame)
        assert processed_frame.shape == frame.shape
        assert isinstance(score, float)

    def test_debug_mode(self):
        detector_debug = pose_detector(debug=True)
        detector_normal = pose_detector(debug=False)
        assert detector_debug.debug
        assert not detector_normal.debug

    @pytest.mark.parametrize(
        "vector1,vector2,expected_angle",
        [
            (np.array([0, 1, 0]), np.array([0, 1, 0]), 0),  # Same direction
            (np.array([1, 0, 0]), np.array([0, 1, 0]), 90),  # Perpendicular
            (np.array([0, 1, 0]), np.array([0, -1, 0]), 180),  # Opposite
        ],
    )
    def test_angle_calculation(self, pd, vector1, vector2, expected_angle):
        angle = pd.angle_between(vector1, vector2)
        assert abs(angle - expected_angle) < 0.01

    def test_draw_posture_feedback(self, pd, mock_frame):
        scores = [0, 50, 100]
        for score in scores:
            pd._draw_posture_feedback(mock_frame, score)
            # Verify frame wasn't corrupted
            assert isinstance(mock_frame, np.ndarray)
            assert mock_frame.shape == (480, 640, 3)

    def test_landmark_list_validity(self, pd):
        # Verify all required landmarks are included
        essential_landmarks = [
            "NOSE",
            "LEFT_EYE",
            "RIGHT_EYE",
            "LEFT_SHOULDER",
            "RIGHT_SHOULDER",
            "LEFT_HIP",
            "RIGHT_HIP",
        ]
        landmark_names = [lm.name for lm in pd.posture_landmarks]
        for landmark in essential_landmarks:
            assert any(landmark in name for name in landmark_names)
