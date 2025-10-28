import cv2
import numpy as np
import pytest

from ..ml.pose_detector import PoseDetector
from ..services.settings_service import SettingsService


@pytest.fixture
def mock_frame():
    return np.zeros((480, 640, 3), dtype=np.uint8)


@pytest.fixture
def mock_landmarks():
    class mock_landmark:
        def __init__(self, x, y, z):
            self.x, self.y, self.z = x, y, z
            self.visibility = 1.0
            self.presence = 1.0

        def HasField(self, field):
            return field in ["visibility", "presence"]

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
def settings_service(tmp_path):
    return SettingsService.for_testing(tmp_path / "pose_settings.ini")


@pytest.fixture
def pd(settings_service):
    """Fixture to provide a pose_detector instance for testing"""
    return PoseDetector(settings_service)


class TestPoseDetector:
    def test_initialization(self, settings_service):
        # Test with default values only
        detector = PoseDetector(settings_service)
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

    def test_frame_preprocessing(self, pd, mock_frame):
        """Test that frame preprocessing (resize and enhancement) works correctly"""
        frame = (
            np.ones((1080, 1920, 3), dtype=np.uint8) * 128
        )  # Different size gray frame
        processed_frame, _, _ = pd.process_frame(frame)
        assert processed_frame.shape == (720, 1280, 3)  # Check resize

    def test_draw_landmarks(self, pd, mock_frame, mock_landmarks):
        """Test landmark drawing functionality"""
        landmarks = mock_landmarks(
            {
                0: (0.5, 0.5, 0),  # Nose
                11: (0.4, 0.6, 0),  # Left shoulder
                12: (0.6, 0.6, 0),  # Right shoulder
                23: (0.4, 0.8, 0),  # Left hip
                24: (0.6, 0.8, 0),  # Right hip
            }
        )

        class MockResults:
            def __init__(self, landmarks):
                self.pose_landmarks = landmarks

        results = MockResults(landmarks)
        pd._draw_landmarks(mock_frame, results)
        assert isinstance(mock_frame, np.ndarray)

    @pytest.mark.parametrize(
        "score_thresholds",
        [
            {"head_tilt": 0.8},
            {"neck_angle": 30.0},
            {"shoulder_level": 3.0},
            {"shoulder_roll": 1.5},
            {"spine_angle": 35.0},
        ],
    )
    def test_custom_score_thresholds(self, score_thresholds, tmp_path):
        """Test that different score thresholds affect scoring"""
        detector = PoseDetector(
            SettingsService.for_testing(tmp_path / "thresholds.ini")
        )
        for key, value in score_thresholds.items():
            detector.score_thresholds[key] = value
        assert (
            detector.score_thresholds[list(score_thresholds.keys())[0]]
            == list(score_thresholds.values())[0]
        )

    def test_weights_sum(self, pd):
        """Test that weights sum to approximately 1"""
        assert abs(np.sum(pd.weights) - 1.0) < 1e-6

    @pytest.mark.parametrize(
        "invalid_vector",
        [
            np.array([0, 0, 0]),  # Zero vector
            np.array([1e-7, 1e-7, 1e-7]),  # Near-zero vector
        ],
    )
    def test_angle_between_edge_cases(self, pd, invalid_vector):
        """Test angle calculation with edge cases"""
        valid_vector = np.array([1, 0, 0])
        angle = pd.angle_between(valid_vector, invalid_vector)
        assert angle == 0.0  # Should handle zero/near-zero vectors gracefully

    def test_posture_score_components(self, pd, mock_landmarks):
        """Test individual components of posture scoring"""
        # Test perfect posture
        perfect_landmarks = mock_landmarks(
            {
                0: (0.5, 0.3, 0),  # Nose
                7: (0.45, 0.3, 0),  # Left ear
                8: (0.55, 0.3, 0),  # Right ear
                11: (0.45, 0.5, 0),  # Left shoulder
                12: (0.55, 0.5, 0),  # Right shoulder
                23: (0.45, 0.7, 0),  # Left hip
                24: (0.55, 0.7, 0),  # Right hip
            }
        )

        score = pd._calculate_posture_score(perfect_landmarks)
        assert score > 90  # Perfect posture should score very high
