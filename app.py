
from flask import Flask, render_template, Response, jsonify
from ultralytics import YOLO
from collections import Counter
import cv2
import time
import os
import threading
import csv
import io

app = Flask(__name__)

# Load YOLO Model
model = YOLO("yolov8n.pt")

# Create Folders
os.makedirs("screenshots", exist_ok=True)
os.makedirs("recordings", exist_ok=True)

# Global Variables
camera = None
latest_frame = None

detection_active = False
recording = False
video_writer = None

object_counts = {}
fps = 0

lock = threading.Lock()

# Analytics Data
detection_history = []
last_history_time = 0

total_objects_detected = 0
object_type_totals = Counter()
total_detection_sessions = 0

# Tracking Data
tracked_objects = {}


# ==============================
# CAMERA
# ==============================

def get_camera():
    global camera

    if camera is None or not camera.isOpened():
        camera = cv2.VideoCapture(0, cv2.CAP_DSHOW)

        if not camera.isOpened():
            camera.release()
            camera = cv2.VideoCapture(0)

    return camera


# ==============================
# GENERATE LIVE VIDEO
# ==============================

def generate_frames():

    global latest_frame, fps, object_counts
    global video_writer, recording
    global last_history_time, detection_history
    global total_objects_detected, object_type_totals
    global tracked_objects, camera

    cap = get_camera()
    previous_time = time.time()

    while True:

        success, frame = cap.read()

        if not success:

            print("Camera frame not received")

            time.sleep(0.1)

            if not cap.isOpened():
                cap.release()
                cap = get_camera()

            continue

        # Detection Active
        if detection_active:

            results = model.track(
                frame,
                persist=True,
                tracker="bytetrack.yaml",
                conf=0.4,
                verbose=False
            )

            output = results[0].plot()
            counts = Counter()

            boxes = results[0].boxes

            if boxes is not None:

                # Object Counting
                for cls in boxes.cls:

                    class_id = int(cls.item())
                    name = model.names[class_id]

                    counts[name] += 1

                # Tracking IDs
                if boxes.id is not None:

                    track_ids = boxes.id.int().cpu().tolist()
                    class_ids = boxes.cls.int().cpu().tolist()

                    for track_id, class_id in zip(track_ids, class_ids):

                        object_name = model.names[class_id]
                        current_clock = time.strftime("%H:%M:%S")

                        if track_id not in tracked_objects:

                            tracked_objects[track_id] = {
                                "id": track_id,
                                "name": object_name,
                                "first_seen": current_clock,
                                "last_seen": current_clock
                            }

                        else:

                            tracked_objects[track_id]["last_seen"] = current_clock

            # Update Object Counts
            object_counts = dict(counts)

            current_time = time.time()

            # Save Analytics Every 5 Seconds
            if current_time - last_history_time >= 5:

                detection_history.append({
                    "time": time.strftime("%H:%M:%S"),
                    "total": sum(counts.values()),
                    "objects": dict(counts)
                })

                total_objects_detected += sum(counts.values())

                object_type_totals.update(counts)

                if len(detection_history) > 50:
                    detection_history.pop(0)

                last_history_time = current_time

            # FPS Counter
            fps = 1 / max(current_time - previous_time, 0.000001)
            previous_time = current_time

            cv2.putText(
                output,
                f"FPS: {fps:.2f}",
                (15, 35),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 255, 0),
                2
            )

            # Recording Indicator
            if recording:

                cv2.circle(
                    output,
                    (25, 70),
                    9,
                    (0, 0, 255),
                    -1
                )

                cv2.putText(
                    output,
                    "RECORDING",
                    (45, 77),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (0, 0, 255),
                    2
                )

        else:

            output = frame.copy()

            cv2.putText(
                output,
                "AI DETECTION STOPPED",
                (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 0, 255),
                2
            )

        # Save Latest Frame
        with lock:
            latest_frame = output.copy()

        # Save Video Recording
        if recording and video_writer is not None:
            video_writer.write(output)

        # Convert Frame To JPEG
        success, buffer = cv2.imencode(".jpg", output)

        if not success:
            continue

        frame_bytes = buffer.tobytes()

        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n"
            + frame_bytes + b"\r\n"
        )


# ==============================
# DASHBOARD
# ==============================

@app.route("/")
def home():
    return render_template("index.html")


# ==============================
# VIDEO FEED
# ==============================

@app.route("/video_feed")
def video_feed():

    return Response(
        generate_frames(),
        mimetype="multipart/x-mixed-replace; boundary=frame"
    )


# ==============================
# START DETECTION
# ==============================

@app.route("/api/start", methods=["POST"])
def start_detection():

    global detection_active, total_detection_sessions

    if not detection_active:
        total_detection_sessions += 1

    detection_active = True

    return jsonify({
        "message": "Detection started"
    })


# ==============================
# STOP DETECTION
# ==============================

@app.route("/api/stop", methods=["POST"])
def stop_detection():

    global detection_active, recording, video_writer

    detection_active = False

    if recording and video_writer is not None:

        recording = False

        video_writer.release()
        video_writer = None

    return jsonify({
        "message": "Detection stopped"
    })


# ==============================
# SCREENSHOT
# ==============================

@app.route("/api/screenshot", methods=["POST"])
def take_screenshot():

    with lock:

        if latest_frame is None:

            return jsonify({
                "error": "Camera frame not available"
            }), 400

        frame = latest_frame.copy()

    filename = f"screenshots/screenshot_{int(time.time())}.jpg"

    cv2.imwrite(filename, frame)

    return jsonify({
        "message": "Screenshot saved",
        "filename": filename
    })


# ==============================
# VIDEO RECORDING
# ==============================

@app.route("/api/record", methods=["POST"])
def record_video():

    global recording, video_writer

    if not recording:

        with lock:

            if latest_frame is None:

                return jsonify({
                    "error": "Start camera first"
                }), 400

            height, width = latest_frame.shape[:2]

        filename = f"recordings/video_{int(time.time())}.mp4"

        fourcc = cv2.VideoWriter_fourcc(*"mp4v")

        writer = cv2.VideoWriter(
            filename,
            fourcc,
            20.0,
            (width, height)
        )

        if not writer.isOpened():

            writer.release()

            return jsonify({
                "error": "Recording could not start"
            }), 500

        video_writer = writer
        recording = True

        return jsonify({
            "message": "Recording started",
            "recording": True
        })

    else:

        recording = False

        if video_writer is not None:

            video_writer.release()
            video_writer = None

        return jsonify({
            "message": "Recording saved",
            "recording": False
        })


# ==============================
# DASHBOARD STATUS API
# ==============================

@app.route("/api/status")
def status():

    return jsonify({
        "fps": round(fps, 2),
        "objects": object_counts,
        "detection": detection_active,
        "recording": recording
    })


# ==============================
# ANALYTICS HISTORY API
# ==============================

@app.route("/api/analytics")
def analytics():

    return jsonify({
        "history": detection_history,
        "total_records": len(detection_history)
    })


# ==============================
# OBJECT SUMMARY API
# ==============================

@app.route("/api/summary")
def detection_summary():

    most_detected = "None"
    highest_count = 0

    if object_type_totals:

        most_detected = max(
            object_type_totals,
            key=object_type_totals.get
        )

        highest_count = object_type_totals[most_detected]

    return jsonify({

        "total_objects": total_objects_detected,

        "most_detected": most_detected,

        "most_detected_count": highest_count,

        "unique_object_types": len(object_type_totals),

        "total_sessions": total_detection_sessions

    })


# ==============================
# TRACKING HISTORY API
# ==============================

@app.route("/api/tracking")
def tracking_history():

    return jsonify({

        "tracked_objects": list(tracked_objects.values()),

        "total_tracked": len(tracked_objects)

    })


# ==============================
# CSV EXPORT
# ==============================

@app.route("/api/export")
def export_analytics():

    output = io.StringIO()

    writer = csv.writer(output)

    writer.writerow([
        "Time",
        "Total Objects",
        "Object Details"
    ])

    for item in detection_history:

        objects = item.get("objects", {})

        details = ", ".join(
            f"{name}: {count}"
            for name, count in objects.items()
        )

        writer.writerow([
            item.get("time", ""),
            item.get("total", 0),
            details
        ])

    csv_data = output.getvalue()

    output.close()

    return Response(
        csv_data,
        mimetype="text/csv",
        headers={
            "Content-Disposition":
            "attachment; filename=AI_Vision_Analytics.csv"
        }
    )


# ==============================
# RUN FLASK APP
# ==============================

if __name__ == "__main__":

    print("Starting AI Vision Dashboard...")

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=False,
        threaded=True
    )
