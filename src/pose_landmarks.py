import mediapipe as mp

mp_pose = mp.solutions.pose

POSTURE_LANDMARKS = [
    mp_pose.PoseLandmark.NOSE,
    mp_pose.PoseLandmark.LEFT_EYE_INNER,
    mp_pose.PoseLandmark.LEFT_EYE,
    mp_pose.PoseLandmark.LEFT_EYE_OUTER,
    mp_pose.PoseLandmark.RIGHT_EYE_INNER,
    mp_pose.PoseLandmark.RIGHT_EYE,
    mp_pose.PoseLandmark.RIGHT_EYE_OUTER,
    mp_pose.PoseLandmark.LEFT_EAR,
    mp_pose.PoseLandmark.RIGHT_EAR,
    mp_pose.PoseLandmark.MOUTH_LEFT,
    mp_pose.PoseLandmark.MOUTH_RIGHT,
    mp_pose.PoseLandmark.LEFT_SHOULDER,
    mp_pose.PoseLandmark.RIGHT_SHOULDER,
    mp_pose.PoseLandmark.LEFT_ELBOW,
    mp_pose.PoseLandmark.RIGHT_ELBOW,
    mp_pose.PoseLandmark.LEFT_WRIST,
    mp_pose.PoseLandmark.RIGHT_WRIST,
    mp_pose.PoseLandmark.LEFT_HIP,
    mp_pose.PoseLandmark.RIGHT_HIP,
]
