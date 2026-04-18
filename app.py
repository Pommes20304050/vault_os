import gc
import os
import cv2
import json
import time
import shutil
import platform
import threading
import urllib.request
import numpy as np
import psutil
from datetime import datetime
from flask import Flask, render_template, jsonify, request, Response
from flask_socketio import SocketIO
import paho.mqtt.client as mqtt

BROKER_HOST      = "127.0.0.1"
VAULT_NAME       = "vault111"
FACES_DIR        = "faces"
MODELS_DIR       = "models"
ALLOWED_PATH     = os.path.join(MODELS_DIR, "allowed.json")
DETECTOR_PATH    = os.path.join(MODELS_DIR, "face_detection_yunet_2023mar.onnx")
RECOGNIZER_PATH  = os.path.join(MODELS_DIR, "face_recognition_sface_2021dec.onnx")
DETECTOR_URL     = "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx"
RECOGNIZER_URL   = "https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx"
COSINE_THRESHOLD = 0.363   # min score to call someone known
ALLOW_CONFIDENCE = 50.0    # min % to grant ERLAUBT
CAM_W, CAM_H     = 640, 480
CAM_REINIT_AFTER = 20  # consecutive read failures before reinit

os.makedirs(FACES_DIR,  exist_ok=True)
os.makedirs(MODELS_DIR, exist_ok=True)

app = Flask(__name__)
app.config["SECRET_KEY"] = "vault-tec-secret"
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

state = {
    "temperature":    None,
    "humidity":       None,
    "cpu_temp":       None,
    "cpu_load":       None,
    "ram":            None,
    "disk":           None,
    "face_detection": {"name": "---", "confidence": 0, "faces": 0},
    "access":         {"decision": "IDLE", "name": "", "confidence": 0},
}

logs: list[str] = []
MAX_LOGS = 200
training_status = {"active": False, "progress": 0, "message": "BEREIT"}

# Camera — all access must hold _cam_lock
_cam      = None
_cam_lock = threading.Lock()

# YuNet + SFace
_detector      = None
_sf_recognizer = None
_embeddings    = []
_emb_names     = []
_emb_lock      = threading.Lock()

# Allowed persons
_allowed    = set()
_allow_lock = threading.Lock()

# Active video generators (for leak detection / single-stream enforcement)
_active_streams = 0
_stream_lock    = threading.Lock()

# Shared frame buffers — written by _face_worker_loop, read by gen_frames / capture
_latest_raw_frame        = None   # unmodified camera frame
_latest_annotated_frame  = None   # frame with face boxes drawn
_frame_lock              = threading.Lock()
_new_frame_event         = threading.Event()


# ── Camera helpers ────────────────────────────────────────────────────────────
_IS_WINDOWS = platform.system() == "Windows"


def _make_camera() -> cv2.VideoCapture:
    """Create a fresh VideoCapture. Caller responsible for releasing old one."""
    backend = cv2.CAP_DSHOW if _IS_WINDOWS else cv2.CAP_V4L2
    cap = cv2.VideoCapture(0, backend)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  CAM_W)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAM_H)
    cap.set(cv2.CAP_PROP_FPS, 30)
    return cap


def get_camera() -> cv2.VideoCapture:
    """Return (and if needed reinitialize) the shared camera. Thread-safe."""
    global _cam
    with _cam_lock:
        if _cam is None or not _cam.isOpened():
            if _cam is not None:
                _cam.release()
            _cam = _make_camera()
        return _cam


def reinit_camera() -> cv2.VideoCapture:
    """Force-release and reinitialize camera. Returns new instance."""
    global _cam
    with _cam_lock:
        if _cam is not None:
            try:
                _cam.release()
            except Exception:
                pass
        _cam = _make_camera()
        return _cam


# ── Allowed helpers ───────────────────────────────────────────────────────────
def load_allowed():
    global _allowed
    if os.path.exists(ALLOWED_PATH):
        try:
            with open(ALLOWED_PATH) as f:
                data = json.load(f)
            with _allow_lock:
                _allowed = set(data)
        except Exception:
            pass


def save_allowed():
    with _allow_lock:
        data = list(_allowed)
    with open(ALLOWED_PATH, "w") as f:
        json.dump(data, f, ensure_ascii=False)


load_allowed()


# ── Model helpers ─────────────────────────────────────────────────────────────
def _ensure_models():
    sibling = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "..", "GesichtsErkennung", "models")
    for fname, url in [
        ("face_detection_yunet_2023mar.onnx",   DETECTOR_URL),
        ("face_recognition_sface_2021dec.onnx", RECOGNIZER_URL),
    ]:
        dst = os.path.join(MODELS_DIR, fname)
        if os.path.exists(dst):
            continue
        src = os.path.join(sibling, fname)
        if os.path.exists(src):
            shutil.copy2(src, dst)
            add_log(f"Modell kopiert: {fname}")
        else:
            add_log(f"Lade {fname} herunter...")
            urllib.request.urlretrieve(url, dst)
            add_log(f"{fname} heruntergeladen")


def _compute_embeddings(det, rec):
    embeddings, names = [], []
    skipped = 0
    persons = [d for d in os.listdir(FACES_DIR)
               if os.path.isdir(os.path.join(FACES_DIR, d))]
    for person in persons:
        person_dir = os.path.join(FACES_DIR, person)
        for fname in sorted(os.listdir(person_dir)):
            if not fname.lower().endswith((".jpg", ".jpeg", ".png")):
                continue
            img = cv2.imread(os.path.join(person_dir, fname))
            if img is None:
                skipped += 1
                continue
            if len(img.shape) == 2 or img.shape[2] == 1:
                img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
            h, w = img.shape[:2]
            det.setInputSize((w, h))
            _, faces = det.detect(img)
            if faces is None or len(faces) == 0:
                skipped += 1
                del img
                continue
            try:
                aligned = rec.alignCrop(img, faces[0])
                feature = rec.feature(aligned)
                embeddings.append(feature)
                names.append(person)
                del aligned
            except Exception:
                skipped += 1
            del img
    return embeddings, names, skipped


def load_recognizer():
    global _detector, _sf_recognizer, _embeddings, _emb_names
    try:
        _ensure_models()
        det = cv2.FaceDetectorYN.create(DETECTOR_PATH, "", (CAM_W, CAM_H), 0.5, 0.3, 5000)
        rec = cv2.FaceRecognizerSF.create(RECOGNIZER_PATH, "")
        embeddings, names, skipped = _compute_embeddings(det, rec)
        with _emb_lock:
            _detector      = det
            _sf_recognizer = rec
            _embeddings    = embeddings
            _emb_names     = names
        msg = f"YuNet+SFace — {len(names)} Bilder / {len(set(names))} Person(en)"
        if skipped:
            msg += f" ({skipped} übersprungen)"
        add_log(msg)
        return True
    except Exception as e:
        add_log(f"Modell-Ladefehler: {e}")
        return False


# ── Video stream ──────────────────────────────────────────────────────────────
def gen_frames():
    global _active_streams
    with _stream_lock:
        _active_streams += 1
        if _active_streams > 1:
            add_log(f"Warnung: {_active_streams} aktive Streams")

    fail_count  = 0
    frame_count = 0
    last_face_state = None
    last_emit       = 0.0

    try:
        while True:
            # Read frame — reinitialize camera if consistently failing
            with _cam_lock:
                global _cam
                if _cam is None or not _cam.isOpened():
                    if _cam is not None:
                        _cam.release()
                    _cam = _make_camera()
                ret, frame = _cam.read()

            if not ret:
                fail_count += 1
                if fail_count >= CAM_REINIT_AFTER:
                    add_log("Kamera antwortet nicht — reinitalisiere...")
                    reinit_camera()
                    fail_count = 0
                frame = np.zeros((CAM_H, CAM_W, 3), dtype=np.uint8)
                cv2.putText(frame, "KAMERA NICHT VERFUEGBAR", (60, 240),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 200, 0), 2)
                time.sleep(0.1)
                ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 60])
                del frame
                if ok:
                    yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n"
                           + buf.tobytes() + b"\r\n")
                del buf
                continue

            fail_count   = 0
            frame_count += 1

            # Snapshot embeddings once per frame (lightweight list-ref copy)
            with _emb_lock:
                det  = _detector
                rec  = _sf_recognizer
                embs = _embeddings   # reference, not copy — read-only below
                nms  = _emb_names

            h, w = frame.shape[:2]
            face_count = 0
            best = {"name": "---", "confidence": 0.0, "faces": 0}

            if det is not None:
                det.setInputSize((w, h))
                _, faces = det.detect(frame)

                if faces is not None:
                    face_count = len(faces)
                    for face in faces:
                        x  = int(face[0]);  y  = int(face[1])
                        x2 = x + int(face[2]); y2 = y + int(face[3])
                        x,  y  = max(0, x),    max(0, y)
                        x2, y2 = min(w-1, x2), min(h-1, y2)

                        name      = "Unbekannt"
                        conf_pct  = 0.0
                        box_color = (220, 80, 0)

                        if rec is not None and embs:
                            try:
                                aligned = rec.alignCrop(frame, face)
                                feature = rec.feature(aligned)
                                del aligned  # free 112×112 BGR immediately

                                best_score = -1.0
                                best_name  = "Unbekannt"
                                for emb, n in zip(embs, nms):
                                    score = float(rec.match(
                                        feature, emb, cv2.FaceRecognizerSF_FR_COSINE
                                    ))
                                    if score > best_score:
                                        best_score = score
                                        best_name  = n
                                del feature

                                if best_score >= COSINE_THRESHOLD:
                                    name      = best_name
                                    conf_pct  = round(best_score * 100, 1)
                                    box_color = (0, 255, 0)
                                else:
                                    conf_pct = round(max(0.0, best_score * 100), 1)
                            except Exception:
                                pass

                        cv2.rectangle(frame, (x, y), (x2, y2), box_color, 2)

                        (lw, lh), _ = cv2.getTextSize(
                            name, cv2.FONT_HERSHEY_SIMPLEX, 0.65, 2)
                        cv2.rectangle(frame,
                                      (x, y - lh - 10), (x + lw + 6, y),
                                      box_color, -1)
                        cv2.putText(frame, name, (x + 3, y - 4),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 0, 0), 2)

                        conf_text = f"{conf_pct:.0f}% Konfidenz"
                        cv2.putText(frame, conf_text, (x, y2 + 22),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, box_color, 1)

                        if conf_pct > best["confidence"]:
                            best["name"]       = name
                            best["confidence"] = conf_pct

            best["faces"] = face_count

            if (face_count > 0
                    and best["name"] not in ("Unbekannt", "---")
                    and best["confidence"] >= ALLOW_CONFIDENCE):
                with _allow_lock:
                    allowed = best["name"] in _allowed
                decision = "ERLAUBT" if allowed else "VERWEIGERT"
            elif face_count > 0:
                decision = "UNBEKANNT"
            else:
                decision = "IDLE"

            access = {
                "decision":   decision,
                "name":       best["name"],
                "confidence": best["confidence"],
            }

            now = time.time()
            if ((best != last_face_state or access != state.get("access"))
                    and (now - last_emit) > 0.5):
                state["face_detection"] = best
                state["access"]         = access
                socketio.emit("state_update", state)
                last_face_state = best.copy()
                last_emit       = now

            ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 75])
            del frame  # free 920 KB immediately after encoding

            if ok:
                yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n"
                       + buf.tobytes() + b"\r\n")
            del buf

            # Periodic GC hint — every ~10 s at 30 fps
            if frame_count % 300 == 0:
                gc.collect()

            time.sleep(1 / 30)

    finally:
        with _stream_lock:
            _active_streams -= 1


# ── Logging ───────────────────────────────────────────────────────────────────
def add_log(msg: str):
    ts    = datetime.now().strftime("%H:%M:%S")
    entry = f"[{ts}] {msg}"
    logs.append(entry)
    if len(logs) > MAX_LOGS:
        logs.pop(0)
    socketio.emit("log", {"message": entry})


load_recognizer()


# ── Local stats publisher (CPU / RAM / disk every 5 s) ────────────────────────
def _stats_loop():
    while True:
        try:
            cpu_temp = None
            if not _IS_WINDOWS:
                try:
                    temps = psutil.sensors_temperatures()
                    for key in ("cpu_thermal", "coretemp", "k10temp", "acpitz"):
                        if key in temps and temps[key]:
                            cpu_temp = round(temps[key][0].current, 1)
                            break
                except Exception:
                    pass
            updates = {
                "cpu_load": round(psutil.cpu_percent(interval=1), 1),
                "ram":      round(psutil.virtual_memory().percent, 1),
                "disk":     round(psutil.disk_usage("C:\\" if _IS_WINDOWS else "/").percent, 1),
            }
            if cpu_temp is not None:
                updates["cpu_temp"] = cpu_temp
            state.update(updates)
            socketio.emit("state_update", state)
        except Exception:
            pass
        time.sleep(1)


# ── MQTT ──────────────────────────────────────────────────────────────────────
def on_connect(client, userdata, flags, reason_code, properties):
    client.subscribe(f"vault/{VAULT_NAME}/#")
    add_log(f"MQTT verbunden → {BROKER_HOST}")


def on_message(client, userdata, msg):
    topic   = msg.topic
    payload = msg.payload.decode("utf-8", errors="replace")
    key     = topic.split("/")[-1]

    if key == "all":
        try:
            data = json.loads(payload)
            state.update({k: v for k, v in data.items() if k in state})
            socketio.emit("state_update", state)
        except Exception as e:
            add_log(f"FEHLER /all: {e}")
    elif key == "face_detection":
        try:
            state["face_detection"] = json.loads(payload)
            socketio.emit("state_update", state)
        except Exception:
            pass
    elif key in state and key != "face_detection":
        try:
            state[key] = float(payload)
        except ValueError:
            state[key] = payload
        socketio.emit("state_update", state)

    add_log(f"{topic}: {payload[:80]}")


def start_mqtt():
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.on_connect = on_connect
    client.on_message = on_message
    try:
        client.connect(BROKER_HOST, 1883, 60)
        client.loop_forever()
    except Exception as e:
        add_log(f"MQTT FEHLER: {e}")


# ── Flask routes ──────────────────────────────────────────────────────────────
@app.route("/")
def index():
    path = os.path.join(os.path.dirname(__file__), "templates", "dashboard.html")
    with open(path, encoding="utf-8") as f:
        html = f.read()
    return Response(html, mimetype="text/html")


@app.route("/manage")
def manage():
    persons = [d for d in os.listdir(FACES_DIR)
               if os.path.isdir(os.path.join(FACES_DIR, d))]
    counts = {p: len(os.listdir(os.path.join(FACES_DIR, p))) for p in persons}
    return render_template("manage.html", vault_name=VAULT_NAME,
                           persons=persons, counts=counts)


@app.route("/api/state")
def api_state():
    return jsonify(state)


@app.route("/api/logs")
def api_logs():
    return jsonify(logs[-50:])


@app.route("/api/persons")
def api_persons_list():
    with _allow_lock:
        allowed_set = set(_allowed)
    result = []
    for d in os.listdir(FACES_DIR):
        path = os.path.join(FACES_DIR, d)
        if os.path.isdir(path):
            result.append({
                "name":    d,
                "count":   len(os.listdir(path)),
                "allowed": d in allowed_set,
            })
    return jsonify(result)


@app.route("/api/persons", methods=["POST"])
def add_person():
    data = request.json or {}
    name = data.get("name", "").strip()
    if not name or "/" in name or ".." in name:
        return jsonify({"error": "Ungültiger Name"}), 400
    os.makedirs(os.path.join(FACES_DIR, name), exist_ok=True)
    add_log(f"Person registriert: {name}")
    return jsonify({"ok": True, "name": name})


@app.route("/api/persons/<name>", methods=["DELETE"])
def delete_person(name):
    global _embeddings, _emb_names
    path = os.path.join(FACES_DIR, name)
    if not os.path.isdir(path):
        return jsonify({"error": "Nicht gefunden"}), 404
    shutil.rmtree(path)
    with _allow_lock:
        _allowed.discard(name)
    save_allowed()
    # Purge embeddings from memory immediately — no restart needed
    with _emb_lock:
        pairs       = [(e, n) for e, n in zip(_embeddings, _emb_names) if n != name]
        _embeddings = [e for e, _ in pairs]
        _emb_names  = [n for _, n in pairs]
    add_log(f"Person gelöscht: {name}")
    return jsonify({"ok": True})


@app.route("/api/allowed")
def get_allowed():
    with _allow_lock:
        return jsonify(list(_allowed))


@app.route("/api/persons/<name>/allow", methods=["POST"])
def allow_person(name):
    path = os.path.join(FACES_DIR, name)
    if not os.path.isdir(path):
        return jsonify({"error": "Person nicht gefunden"}), 404
    with _allow_lock:
        _allowed.add(name)
    save_allowed()
    add_log(f"Zugang erteilt: {name}")
    return jsonify({"ok": True, "allowed": True})


@app.route("/api/persons/<name>/allow", methods=["DELETE"])
def revoke_person(name):
    with _allow_lock:
        _allowed.discard(name)
    save_allowed()
    add_log(f"Zugang entzogen: {name}")
    return jsonify({"ok": True, "allowed": False})


@app.route("/api/capture", methods=["POST"])
def capture_photo():
    data = request.json or {}
    name = data.get("name", "").strip()
    if not name:
        return jsonify({"error": "Kein Name angegeben"}), 400

    person_dir = os.path.join(FACES_DIR, name)
    os.makedirs(person_dir, exist_ok=True)

    with _cam_lock:
        global _cam
        if _cam is None or not _cam.isOpened():
            if _cam is not None:
                _cam.release()
            _cam = _make_camera()
        ret, frame = _cam.read()

    if not ret:
        return jsonify({"error": "Kamerafehler"}), 500

    with _emb_lock:
        det = _detector
    if det is not None:
        h, w = frame.shape[:2]
        det.setInputSize((w, h))
        _, faces = det.detect(frame)
        if faces is None or len(faces) == 0:
            del frame
            return jsonify({"error": "Kein Gesicht erkannt"}), 400

    count = len([f for f in os.listdir(person_dir) if f.lower().endswith(".jpg")])
    cv2.imwrite(os.path.join(person_dir, f"{count:04d}.jpg"), frame)
    del frame

    total = len([f for f in os.listdir(person_dir) if f.lower().endswith(".jpg")])
    add_log(f"Foto aufgenommen: {name} ({total} gesamt)")
    return jsonify({"ok": True, "count": total})


@app.route("/api/train", methods=["POST"])
def train_model():
    if training_status["active"]:
        return jsonify({"error": "Training läuft bereits"}), 409
    threading.Thread(target=_do_training, daemon=True).start()
    return jsonify({"ok": True})


@app.route("/api/training_status")
def api_training_status():
    return jsonify(training_status)


def _do_training():
    global _embeddings, _emb_names
    training_status["active"]   = True
    training_status["progress"] = 0
    training_status["message"]  = "Embeddings werden berechnet..."
    socketio.emit("training_status", training_status)
    add_log("Embedding-Berechnung gestartet")

    try:
        # Own detector instance — avoids setInputSize() race with gen_frames
        det_t = cv2.FaceDetectorYN.create(DETECTOR_PATH, "", (CAM_W, CAM_H), 0.5, 0.3, 5000)
        rec_t = cv2.FaceRecognizerSF.create(RECOGNIZER_PATH, "")

        persons = [d for d in os.listdir(FACES_DIR)
                   if os.path.isdir(os.path.join(FACES_DIR, d))]
        embeddings, names = [], []
        total_imgs = 0
        skipped    = 0

        for i, person in enumerate(persons):
            training_status["progress"] = int((i / max(len(persons), 1)) * 90)
            training_status["message"]  = f"Berechne {person}..."
            socketio.emit("training_status", training_status)

            person_dir = os.path.join(FACES_DIR, person)
            images = sorted([f for f in os.listdir(person_dir)
                             if f.lower().endswith((".jpg", ".jpeg", ".png"))])
            for fname in images:
                img = cv2.imread(os.path.join(person_dir, fname))
                if img is None:
                    skipped += 1
                    continue
                if len(img.shape) == 2 or img.shape[2] == 1:
                    img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
                h, w = img.shape[:2]
                det_t.setInputSize((w, h))
                _, faces = det_t.detect(img)
                if faces is None or len(faces) == 0:
                    skipped += 1
                    del img
                    continue
                try:
                    aligned = rec_t.alignCrop(img, faces[0])
                    feature = rec_t.feature(aligned)
                    embeddings.append(feature)
                    names.append(person)
                    total_imgs += 1
                    del aligned
                except Exception:
                    skipped += 1
                del img

        if not embeddings:
            raise ValueError("Keine Gesichter gefunden — bitte neue Fotos aufnehmen")

        with _emb_lock:
            _embeddings = embeddings
            _emb_names  = names

        gc.collect()
        training_status["progress"] = 100
        training_status["message"]  = (
            f"Fertig — {total_imgs} Bilder / {len(set(names))} Person(en)"
            + (f" ({skipped} übersprungen)" if skipped else "")
        )
        add_log(f"Embeddings: {len(set(names))} Personen, {total_imgs} Bilder"
                + (f", {skipped} übersprungen" if skipped else ""))

    except Exception as e:
        training_status["message"] = f"FEHLER: {e}"
        add_log(f"Embedding FEHLER: {e}")
    finally:
        training_status["active"] = False
        socketio.emit("training_status", training_status)


@app.route("/video_feed")
def video_feed():
    return Response(gen_frames(), mimetype="multipart/x-mixed-replace; boundary=frame")


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Kill any stale instance on port 5000 before binding
    for proc in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            conns = proc.net_connections() if hasattr(proc, "net_connections") else proc.connections(kind="inet")
            for c in conns:
                if c.laddr.port == 5000 and proc.pid != os.getpid():
                    proc.kill()
                    break
        except Exception:
            pass

    threading.Thread(target=start_mqtt,  daemon=True).start()
    threading.Thread(target=_stats_loop, daemon=True).start()
    add_log(f"Vault-OS gestartet — {VAULT_NAME}")
    socketio.run(app, host="0.0.0.0", port=5000, debug=False, allow_unsafe_werkzeug=True)
