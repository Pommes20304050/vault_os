<div align="center">

```
██╗   ██╗ █████╗ ██╗   ██╗██╗  ████████╗      ██████╗ ███████╗
██║   ██║██╔══██╗██║   ██║██║  ╚══██╔══╝     ██╔═══██╗██╔════╝
██║   ██║███████║██║   ██║██║     ██║        ██║   ██║███████╗
╚██╗ ██╔╝██╔══██║██║   ██║██║     ██║        ██║   ██║╚════██║
 ╚████╔╝ ██║  ██║╚██████╔╝███████╗██║        ╚██████╔╝███████║
  ╚═══╝  ╚═╝  ╚═╝ ╚═════╝ ╚══════╝╚═╝         ╚═════╝ ╚══════╝
```

**Smart Home Sicherheitssystem · Fallout-Edition**

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![OpenCV](https://img.shields.io/badge/OpenCV-4.9%2B-green?style=for-the-badge&logo=opencv&logoColor=white)](https://opencv.org)
[![Flask](https://img.shields.io/badge/Flask-3.0%2B-black?style=for-the-badge&logo=flask&logoColor=white)](https://flask.palletsprojects.com)
[![MQTT](https://img.shields.io/badge/MQTT-Mosquitto-orange?style=for-the-badge&logo=eclipsemosquitto&logoColor=white)](https://mosquitto.org)
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Raspberry%20Pi-red?style=for-the-badge&logo=raspberrypi&logoColor=white)](https://raspberrypi.org)

*„War. War never changes."*

</div>

---

## Überblick

VaultOS ist ein Fallout-inspiriertes Smart-Home-Dashboard mit KI-gestützter Gesichtserkennung. Es verbindet Echtzeit-Kameraüberwachung, Zutrittskontrolle, Systemtelemetrie und MQTT-Sensor­daten in einem einzigen Browser-Interface.

```
┌─────────────────────────────────────────────────────────────┐
│  Browser  ←──WebSocket──→  Flask + SocketIO  ←──→  Kamera  │
│                                    │                         │
│                              MQTT Broker                     │
│                                    │                         │
│                         Raspberry Pi Sensoren               │
│                        (DHT22 · psutil · GPIO)              │
└─────────────────────────────────────────────────────────────┘
```

---

## Features

| Modul | Beschreibung |
|---|---|
| 🎥 **Live-Kamera** | MJPEG-Stream mit YuNet-Gesichtserkennung direkt ins Dashboard |
| 🧠 **KI-Erkennung** | YuNet + SFace (OpenCV ONNX) · Cosinus-Ähnlichkeit · kein Cloud-Zwang |
| 🔐 **Zutrittskontrolle** | `ERLAUBT` / `VERWEIGERT` / `UNBEKANNT` · konfigurierbarer Schwellwert |
| 📊 **Telemetrie** | CPU-Last, RAM, Disk, CPU-Temperatur — live via Socket.IO |
| 🌡️ **Sensoren** | DHT22 Temperatur + Luftfeuchte (Raspberry Pi) via MQTT |
| 👥 **Personalverwaltung** | Fotos aufnehmen, Personen anlegen/löschen, Zutritt erteilen |
| 🔄 **Echtzeit** | Socket.IO WebSocket — kein F5 nötig |
| 🧹 **RAM-Cleaner** | Working-Set-Bereinigung per Doppelklick |

---

## Schnellstart

### Voraussetzungen

- Python **3.10+**
- USB-Kamera (Index 0)
- *(optional)* MQTT-Broker (Mosquitto) für Pi-Sensoren

### Installation

```bat
:: 1. Repository klonen / Ordner entpacken
cd C:\Users\...\VaultOS

:: 2. Abhängigkeiten installieren
install.bat

:: 3. Starten
start.bat
```

`start.bat` killt automatisch alte Instanzen, wartet bis der Server bereit ist und öffnet Chrome (oder Edge als Fallback).

### Raspberry Pi

```bash
pip install -r requirements_pi.txt
python publisher.py   # sendet Sensordaten per MQTT
python app.py         # startet den Server
```

---

## Projektstruktur

```
VaultOS/
├── app.py                  ← Flask-Server · Kamera · Gesichtserkennung · API
├── publisher.py            ← MQTT-Publisher für Pi-Sensoren
├── start.bat               ← Ein-Klick-Start mit Browser-Öffner
├── install.bat             ← Abhängigkeiten installieren
├── clean_ram.bat           ← RAM-Bereinigung (Working Sets + FS-Cache)
│
├── templates/
│   ├── dashboard.html      ← Fallout-Dashboard (kompiliertes Bundle)
│   └── manage.html         ← Personalverwaltung
│
├── faces/                  ← Gesichtsfotos pro Person
│   ├── Louis/
│   │   ├── 0000.jpg
│   │   └── ...
│   └── Viktor/
│
├── models/                 ← KI-Modelle (automatisch heruntergeladen)
│   ├── face_detection_yunet_2023mar.onnx    (390 KB)
│   └── face_recognition_sface_2021dec.onnx  (37 MB)
│
├── requirements.txt        ← Windows
├── requirements_pi.txt     ← Raspberry Pi (+ DHT22)
└── services/               ← systemd-Units für Pi-Autostart
```

---

## Konfiguration

Alle wichtigen Werte stehen am Anfang von `app.py`:

```python
BROKER_HOST      = "192.168.1.100"  # MQTT-Broker IP (Raspberry Pi)
VAULT_NAME       = "vault111"       # MQTT-Topic-Prefix
COSINE_THRESHOLD = 0.363            # Min. Score für „bekannte Person"
ALLOW_CONFIDENCE = 50.0             # Min. % für Zugang ERLAUBT
CAM_W, CAM_H     = 640, 480        # Kameraauflösung
CAM_REINIT_AFTER = 20              # Kamera-Neustart nach N Fehlern
```

---

## Gesichtserkennung

```
Kamerabild (640×480)
       │
       ▼
  YuNet Detektor  ──→  Bounding Box + Landmarks
       │
       ▼
  SFace Recognizer  ──→  128-dim Embedding
       │
       ▼
  Cosinus-Ähnlichkeit gegen alle bekannten Embeddings
       │
     ≥ 0.363?
    ┌──┴──┐
   JA    NEIN
    │      │
  Name   Unbekannt
    │
  ≥ 50%?
    │
  ERLAUBT / VERWEIGERT
```

### Neue Person registrieren

1. `http://localhost:5000/manage` öffnen
2. Person anlegen → **20–30 Fotos** mit `SPACE` aufnehmen (verschiedene Winkel!)
3. **Trainieren** klicken → Embeddings werden sofort berechnet
4. Person in der Liste auf **ERLAUBT** setzen

> **Tipp:** Mehr Fotos = bessere Erkennungsrate. Fotos bei unterschiedlicher Beleuchtung und leicht variierten Winkeln aufnehmen.

---

## Routen & API

| Route | Methode | Beschreibung |
|---|---|---|
| `/` | GET | Fallout-Dashboard |
| `/manage` | GET | Personalverwaltung |
| `/video_feed` | GET | MJPEG-Kamerastream |
| `/api/state` | GET | Aktueller Systemstatus (JSON) |
| `/api/persons` | GET / POST | Personen auflisten / anlegen |
| `/api/persons/<name>` | DELETE | Person + Fotos löschen (sofort aus RAM) |
| `/api/persons/<name>/allow` | POST / DELETE | Zutritt erteilen / entziehen |
| `/api/capture` | POST | Foto aufnehmen |
| `/api/train` | POST | Embeddings neu berechnen |
| `/api/logs` | GET | Letzte 50 Log-Einträge |

---

## Tech Stack

| Komponente | Technologie |
|---|---|
| Backend | Python · Flask 3 · Flask-SocketIO |
| KI / CV | OpenCV 4.9 · YuNet · SFace (ONNX) |
| Kommunikation | Socket.IO WebSocket · MQTT (paho) |
| Telemetrie | psutil |
| Sensoren (Pi) | adafruit-circuitpython-dht · DHT22 |
| Frontend | Vanilla JS · Socket.IO Client · MJPEG |

---

## Raspberry Pi Deployment

```bash
# MQTT-Broker installieren
sudo apt install mosquitto mosquitto-clients -y
sudo systemctl enable mosquitto

# VaultOS Autostart einrichten
sudo cp services/vaultos.service    /etc/systemd/system/
sudo cp services/publisher.service  /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable vaultos publisher
sudo systemctl start  vaultos publisher
```

**MQTT-Broker IP** in `app.py` und `publisher.py` anpassen:
```python
BROKER_HOST = "192.168.1.100"   # ← Pi-IP hier eintragen
```

---

## Troubleshooting

| Problem | Lösung |
|---|---|
| Kamera nicht gefunden | USB-Kabel prüfen · `CAP_DSHOW` (Win) vs `CAP_V4L2` (Pi) |
| Hoher RAM-Verbrauch | `clean_ram.bat` ausführen · nur eine Instanz starten (`start.bat`) |
| Person wird nicht erkannt | Neue Fotos aufnehmen (640×480 Vollbild) · danach Trainieren |
| MQTT keine Verbindung | Pi erreichbar? `ping 192.168.1.100` · Mosquitto läuft? |
| `opencv-contrib` Fehler | `install.bat` neu ausführen (entfernt Konflikte automatisch) |
| Mehrere Instanzen | `start.bat` benutzen — killt Port 5000 automatisch |

---

<div align="center">

```
╔══════════════════════════════════════╗
║   Please stand by                   ║
║                                     ║
║   VaultOS wird initialisiert...     ║
║   ████████████████████░░  87%       ║
╚══════════════════════════════════════╝
```

*Gebaut mit Python, OpenCV und Pip-Boy-Energie.*

</div>
