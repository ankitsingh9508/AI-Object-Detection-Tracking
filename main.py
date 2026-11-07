from ultralytics import YOLO
import cv2
from collections import Counter
import time
import os

model = YOLO("yolov8n.pt")

cap = cv2.VideoCapture(0)

if not cap.isOpened():
    print("Webcam not found!")
    exit()

os.makedirs("screenshots", exist_ok=True)
os.makedirs("recordings", exist_ok=True)

# Video recording setup
fourcc = cv2.VideoWriter_fourcc(*"mp4v")
video_writer = None
recording = False

print("AI Object Detection & Tracking Started")
print("S = Screenshot")
print("R = Start/Stop Recording")
print("Q = Quit")

prev_time = time.time()

while True:
    ret, frame = cap.read()

    if not ret:
        break

    results = model.track(
        frame,
        persist=True,
        tracker="bytetrack.yaml",
        conf=0.4,
        verbose=False
    )

    annotated_frame = results[0].plot()

    # Calculate FPS
    current_time = time.time()
    fps = 1 / max(current_time - prev_time, 0.000001)
    prev_time = current_time

    # Count objects
    object_counts = Counter()

    if results[0].boxes is not None:
        for cls in results[0].boxes.cls:
            class_id = int(cls.item())
            object_name = model.names[class_id]
            object_counts[object_name] += 1

    # Display FPS
    cv2.putText(
        annotated_frame,
        f"FPS: {fps:.2f}",
        (10, 30),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (0, 255, 0),
        2
    )

    # Display object count
    y_position = 65

    for name, count in object_counts.items():
        cv2.putText(
            annotated_frame,
            f"{name}: {count}",
            (10, y_position),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 255, 255),
            2
        )
        y_position += 25

    # Recording indicator
    if recording:
        cv2.circle(annotated_frame, (30, 140), 10, (0, 0, 255), -1)
        cv2.putText(
            annotated_frame,
            "RECORDING",
            (50, 147),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 0, 255),
            2
        )

        video_writer.write(annotated_frame)

    cv2.imshow("AI Object Detection & Tracking", annotated_frame)

    key = cv2.waitKey(1) & 0xFF

    # Screenshot
    if key == ord("s"):
        filename = f"screenshots/screenshot_{int(time.time())}.jpg"
        cv2.imwrite(filename, annotated_frame)
        print("Screenshot saved:", filename)

    # Start/Stop recording
    elif key == ord("r"):

        if not recording:
            height, width = annotated_frame.shape[:2]
            filename = f"recordings/video_{int(time.time())}.mp4"

            video_writer = cv2.VideoWriter(
                filename,
                fourcc,
                20.0,
                (width, height)
            )

            if video_writer.isOpened():
                recording = True
                print("Recording started:", filename)
            else:
                video_writer.release()
                video_writer = None
                print("Error: Video recording could not start!")

        else:
            recording = False
            video_writer.release()
            video_writer = None
            print("Recording saved successfully!")

    # Quit
    elif key == ord("q"):
        break

if recording and video_writer is not None:
    video_writer.release()

cap.release()
cv2.destroyAllWindows()

print("Project stopped successfully!")