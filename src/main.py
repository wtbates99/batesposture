import cv2
import pose_detector


def main():
    cap = cv2.VideoCapture(0)
    detector = pose_detector.pose_detector()

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frame, detected, posture_score = detector.process_frame(frame)

        if detected:
            if posture_score < 60:
                cv2.putText(
                    frame,
                    "Please sit up straight!",
                    (10, 60),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (0, 0, 255),
                    2,
                )

        cv2.imshow("Posture Detection", frame)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
