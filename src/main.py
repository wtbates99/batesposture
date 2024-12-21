import cv2
import pose_detector
import score_history


def main():
    cap = cv2.VideoCapture(0)
    detector = pose_detector.pose_detector()
    s_history = score_history.score_history()
    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frame, score = detector.process_frame(frame)

        s_history.add_score(score)
        avg_score = s_history.get_average_score()
        print(
            f"Average score over last {s_history.WINDOW_SIZE} seconds: {avg_score:.2f}"
        )

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
