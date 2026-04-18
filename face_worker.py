import cv2
import json
import time
import numpy as np
import paho.mqtt.client as mqtt

BROKER_HOST          = "192.168.1.100"
VAULT_NAME           = "vault111"
MODEL_PATH           = "models/lbph_model.yml"
LABELS_PATH          = "models/labels.json"
CONFIDENCE_THRESHOLD = 70   # LBPH: lower value = better match
PUBLISH_INTERVAL     = 0.5  # seconds between publishes (2 fps)
MODEL_RELOAD_INTERVAL = 60  # reload model every N seconds

face_cascade = cv2.CascadeClassifier(
    cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
)


def load_model():
    try:
        recognizer = cv2.face.LBPHFaceRecognizer_create()
        recognizer.read(MODEL_PATH)
        with open(LABELS_PATH) as f:
            labels = {int(k): v for k, v in json.load(f).items()}
        print(f"[INFO] Model loaded — {len(labels)} persons: {list(labels.values())}")
        return recognizer, labels
    except Exception as e:
        print(f"[WARN] Model not loaded: {e}")
        return None, {}


def main():
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)
    client.connect(BROKER_HOST, 1883, 60)
    client.loop_start()

    cam = cv2.VideoCapture(0)
    cam.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cam.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    recognizer, labels = load_model()
    last_reload = time.time()
    topic = f"vault/{VAULT_NAME}/face_detection"

    print(f"[INFO] Face Worker started — {VAULT_NAME} → {BROKER_HOST}")

    while True:
        ret, frame = cam.read()
        if not ret:
            time.sleep(1)
            continue

        # Periodically reload model (in case training updated it)
        if time.time() - last_reload > MODEL_RELOAD_INTERVAL:
            recognizer, labels = load_model()
            last_reload = time.time()

        gray  = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, 1.3, 5, minSize=(80, 80))

        result = {"name": "---", "confidence": 0, "faces": len(faces)}

        if recognizer is not None and len(faces) > 0:
            (x, y, w, h) = max(faces, key=lambda r: r[2] * r[3])
            face_roi = cv2.resize(gray[y : y + h, x : x + w], (200, 200))
            label_id, confidence = recognizer.predict(face_roi)

            if confidence < CONFIDENCE_THRESHOLD:
                result["name"]       = labels.get(label_id, "Unknown")
                result["confidence"] = int(100 - confidence)
            else:
                result["name"]       = "Unknown"
                result["confidence"] = 0

        client.publish(topic, json.dumps(result))
        time.sleep(PUBLISH_INTERVAL)


if __name__ == "__main__":
    main()
