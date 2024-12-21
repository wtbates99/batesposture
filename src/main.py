import cv2
import pose_detector


def main():
    cap = cv2.VideoCapture(0)
    detector = pose_detector.pose_detector()

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frame, score = detector.process_frame(frame)
        print(score)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
