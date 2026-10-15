from __future__ import annotations

from ..ml import mediapipe_compat


def test_pose_landmark_indices_match_blazepose_topology():
    landmark = mediapipe_compat.PoseLandmark

    assert landmark.NOSE == 0
    assert landmark.LEFT_EAR == 7
    assert landmark.LEFT_SHOULDER == 11
    assert landmark.RIGHT_HIP == 24
    assert len(landmark) == 33


def test_pose_connections_reference_valid_landmarks():
    assert mediapipe_compat.POSE_CONNECTIONS
    for connection in mediapipe_compat.POSE_CONNECTIONS:
        assert 0 <= connection.start < 33
        assert 0 <= connection.end < 33
