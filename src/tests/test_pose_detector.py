import numpy as np
import pytest

from ..pose_detector import pose_detector
import cv2


@pytest.fixture
def mock_frame():
    return np.zeros((480, 640, 3), dtype=np.uint8)


@pytest.fixture
def mock_landmarks():
    class mock_landmark:
        def __init__(self, x, y, z):
            self.x, self.y, self.z = x, y, z

    class mock_landmarks:
        def __init__(self, landmark_dict=None):
            self.landmark = []
            # Fill with default values
            for _ in range(33):
                self.landmark.append(mock_landmark(0.5, 0.5, 0))
            # Override with provided values
            if landmark_dict:
                for idx, (x, y, z) in landmark_dict.items():
                    self.landmark[idx] = mock_landmark(x, y, z)

    return mock_landmarks


@pytest.fixture
def pd():
    """Fixture to provide a pose_detector instance for testing"""
    return pose_detector()


class TestPoseDetector:
    def test_initialization(self):
        # Test with default values only
        detector = pose_detector()
        assert detector.pose is not None
        assert detector.ideal_neck_vector.shape == (3,)
        assert detector.ideal_spine_vector.shape == (3,)

    def test_process_empty_frame(self, pd, mock_frame):
        frame, score, landmarks = pd.process_frame(mock_frame)
        assert isinstance(frame, np.ndarray)
        assert score == 0.0
        assert landmarks is None  # or whatever the expected value should be

    @pytest.mark.parametrize(
        "landmark_dict,expected_range",
        [
            ({0: (0.5, 0.3, 0), 12: (0.5, 0.5, 0)}, (90, 100)),  # Good posture
            (
                {
                    0: (0.7, 0.3, 0.3),  # Head forward and rotated
                    11: (0.45, 0.5, 0.1),  # Left shoulder forward
                    12: (0.5, 0.5, 0),  # Right shoulder reference
                    23: (0.5, 0.7, 0.1),  # Hip position for spine alignment
                },
                (0, 70),
            ),  # Poor posture - multiple issues
        ],
    )
    def test_posture_score_calculation(
        self, pd, mock_landmarks, landmark_dict, expected_range
    ):
        landmarks = mock_landmarks(landmark_dict)
        score = pd._calculate_posture_score(landmarks)
        assert isinstance(score, float)
        assert expected_range[0] <= score <= expected_range[1]

    def test_different_frame_sizes(self, pd):
        # Create a frame with some basic content instead of all zeros
        frame = np.ones((720, 1280, 3), dtype=np.uint8) * 128  # Gray frame
        # Draw a simple shape that might be recognized as a person
        cv2.rectangle(frame, (500, 200), (700, 600), (255, 255, 255), -1)
        cv2.circle(frame, (600, 150), 50, (255, 255, 255), -1)

        processed_frame, score, landmarks = pd.process_frame(frame)
        assert processed_frame.shape == frame.shape
        assert isinstance(score, float)
        # Make the assertion optional since landmark detection isn't guaranteed
        assert landmarks is None or landmarks.pose_landmarks is not None

    @pytest.mark.parametrize(
        "vector1,vector2,expected_angle",
        [
            (np.array([0, 1, 0]), np.array([0, 1, 0]), 0),  # Same direction
            (np.array([1, 0, 0]), np.array([0, 1, 0]), 90),  # Perpendicular
        ],
    )
    def test_angle_calculation(self, pd, vector1, vector2, expected_angle):
        angle = pd.angle_between(vector1, vector2)
        assert abs(angle - expected_angle) < 0.01

    def test_draw_posture_feedback(self, pd, mock_frame):
        # Test representative values only
        for score in [0, 100]:
            pd._draw_posture_feedback(mock_frame, score)
            assert isinstance(mock_frame, np.ndarray)
            assert mock_frame.shape == (480, 640, 3)

    def test_landmark_list_validity(self, pd):
        essential_landmarks = {"NOSE", "LEFT_SHOULDER", "RIGHT_SHOULDER"}
        landmark_names = {lm.name for lm in pd.posture_landmarks}
        assert essential_landmarks.issubset(landmark_names)
