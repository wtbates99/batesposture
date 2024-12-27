from webcam import webcam
from pose_detector import pose_detector
from score_history import score_history
import time
import cv2


def main():
    frame_reader = webcam()
    detector = pose_detector()
    s_history = score_history()

    frame_reader.start(callback=detector.process_frame)

    while frame_reader.is_running.is_set():
        frame, score = frame_reader.get_latest_frame()
        if frame is not None:
            s_history.add_score(score)
            avg_score = s_history.get_average_score()
            print(
                f"Average score over last {s_history.WINDOW_SIZE} seconds: {avg_score:.2f}"
            )
            cv2.imshow(
                "Posture Detection", frame
            )  # window display must be on the main thread
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
        time.sleep(0.1)  # Prevent CPU overuse

    frame_reader.stop()


if __name__ == "__main__":
    main()
