from webcam import webcam
from pose_detector import pose_detector
from score_history import score_history
from notifications import notification_manager
import time
import cv2


def main():
    frame_reader = webcam()
    detector = pose_detector()
    scores = score_history()
    notifier = notification_manager()
    show_video = (
        False  # when this runs as a background process, we don't want to show the video
    )

    frame_reader.start(callback=detector.process_frame)

    while frame_reader.is_running.is_set():
        frame, score = frame_reader.get_latest_frame()
        if frame is not None:
            scores.add_score(score)
            average_score = scores.get_average_score()

            # Check posture and notify if needed
            notifier.check_and_notify(average_score)

            if show_video:
                cv2.imshow("Posture Detection", frame)

            # Handle key presses
            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
            elif key == ord("v"):  # 'v' key toggles video display
                show_video = not show_video
                if not show_video:
                    cv2.destroyWindow("Posture Detection")

        time.sleep(0.1)  # Prevent CPU overuse

    frame_reader.stop()


if __name__ == "__main__":
    main()
