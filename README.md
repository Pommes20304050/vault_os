<div align="center">

```
██╗   ██╗ █████╗ ██╗   ██╗██╗  ████████╗      ██████╗ ███████╗
██║   ██║██╔══██╗██║   ██║██║  ╚══██╔══╝     ██╔═══██╗██╔════╝
██║   ██║███████║██║   ██║██║     ██║        ██║   ██║███████╗
╚██╗ ██╔╝██╔══██║██║   ██║██║     ██║        ██║   ██║╚════██║
 ╚████╔╝ ██║  ██║╚██████╔╝███████╗██║        ╚██████╔╝███████║
  ╚═══╝  ╚═╝  ╚═╝ ╚═════╝ ╚══════╝╚═╝         ╚═════╝ ╚══════╝
```

**KI-gestützte Zutrittskontrolle · Raspberry Pi 5 · Fallout-Edition**

[![Python](https://img.shields.io/badge/Python-3.11%2B-blue?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![OpenCV](https://img.shields.io/badge/OpenCV-4.9%2B-green?style=for-the-badge&logo=opencv&logoColor=white)](https://opencv.org)
[![Flask](https://img.shields.io/badge/Flask-3.0%2B-black?style=for-the-badge&logo=flask&logoColor=white)](https://flask.palletsprojects.com)
[![MQTT](https://img.shields.io/badge/MQTT-Mosquitto-orange?style=for-the-badge&logo=eclipsemosquitto&logoColor=white)](https://mosquitto.org)
[![Platform](https://img.shields.io/badge/Platform-Raspberry%20Pi%205-red?style=for-the-badge&logo=raspberrypi&logoColor=white)](https://raspberrypi.org)

*„War. War never changes."*

</div>

---

## Überblick

VaultOS ist ein Fallout-inspiriertes Sicherheits- und Überwachungssystem auf dem **Raspberry Pi 5**. Es kombiniert KI-gestützte Gesichtserkennung mit Echtzeit-Hardware-Feedback: LEDs signalisieren den Zutrittstatus, ein HD44780 LCD zeigt Sensordaten und Systeminfo an, und ein Web-Dashboard liefert alles auf einen Blick im Browser.

```
┌────────────────────────────────────────────────────────────────────┐
│                                                                    │
│   Kamera  ──→  Gesichtserkennung  ──→  Flask + Socket.IO          │
│                                              │                     │
│                                        MQTT Broker (lokal)        │
│                                              │                     │
│              DHT11 ──→  Publisher  ──────────┤                     │
│              psutil ──→ (CPU/RAM/Disk/Temp) ─┤                     │
│                                              │                     │
│   Browser-Dashboard ←──── WebSocket ─────────┘                    │
│                                                                    │
│   GPIO-Controller ←── Socket.IO ── Flask                          │
│   (LEDs · LCD · Button)                                           │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
```

---

## Features

| Modul | Beschreibung |
|---|---|
| 🎥 **Live-Kamera** | MJPEG-Stream mit YuNet-Gesichtsdetektion direkt im Browser |
| 🧠 **KI-Erkennung** | YuNet + SFace (OpenCV ONNX) · Cosinus-Ähnlichkeit · lokal, kein Cloud-Zwang |
| 🔐 **Zutrittskontrolle** | `ERLAUBT` / `VERWEIGERT` / `UNBEKANNT` mit konfigurierbarem Schwellwert |
| 💡 **LED-Feedback** | Blau = Gesicht erkannt · Grün = Erlaubt · Rot = Verweigert/Unbekannt |
| 📟 **LCD 16×2** | Zeigt Name, Konfidenz, Temperatur, Luftfeuchte in Echtzeit |
| 🔘 **Modus-Button** | Wechsel zwischen Gesichtserkennung und System-Stats per Knopfdruck |
| 📊 **System-Stats** | CPU-Last, RAM, Disk, CPU-Temperatur — live via Socket.IO |
| 🌡️ **DHT11-Sensor** | Temperatur + Luftfeuchte via lgpio (kein Kernel-Treiber nötig) |
| 👥 **Personalverwaltung** | Fotos aufnehmen, Personen anlegen/löschen, Zutritt erteilen |
| 🔄 **Echtzeit** | Socket.IO WebSocket — Dashboard aktualisiert sich automatisch |

---

## Hardware

### Komponenten

| Komponente | Details |
|---|---|
| **Raspberry Pi 5** | Hauptrechner · RP1-GPIO-Controller |
| **USB-Kamera** | Gesichtserkennung · Index 0 |
| **HD44780 LCD 16×2** | Anzeige via Kernel-Overlay `/dev/lcd` |
| **DHT11** | Temperatur + Luftfeuchte · GPIO 4 |
| **LED Blau** | Gesicht im Bild · GPIO 17 |
| **LED Grün** | Zutritt erlaubt · GPIO 27 |
| **LED Rot** | Verweigert / Unbekannt · GPIO 22 |
| **Taster** | Modus-Wechsel · GPIO 21 (intern Pull-Up) |
| **Taster-LED** | Leuchtet in Modus 2 (Stats) · GPIO 12 |

### GPIO-Belegung

```
GPIO  4  → DHT11 DATA          (10kΩ Pull-Up zu 5V)
GPIO 12  → Taster-LED          (330Ω)
GPIO 17  → LED Blau            (330Ω)
GPIO 21  → Taster              (auf GND)
GPIO 22  → LED Rot             (330Ω)
GPIO 23  → LCD RS
GPIO 24  → LCD EN
GPIO 25  → LCD D4
GPIO  5  → LCD D5
GPIO 13  → LCD D6
GPIO 19  → LCD D7
GPIO 27  → LED Grün            (330Ω)
```

### LCD-Modus-Wechsel

Der Taster schaltet zwischen zwei Modi um:

| Modus | Anzeige | Taster-LED |
|---|---|---|
| **0 — Gesichtserkennung** | Name · Konfidenz · Temp · Humidity | Aus |
| **1 — System-Stats** | CPU · RAM · Disk · CPU-Temp | An |

---

## Software-Architektur

VaultOS läuft als **3 systemd-Services** die automatisch beim Boot starten:

| Service | Datei | Aufgabe |
|---|---|---|
| `vault-app` | `app.py` | Flask-Server · Kamera · Gesichtserkennung · MQTT-Empfang |
| `vault-publisher` | `publisher.py` | DHT11 + System-Stats → MQTT |
| `vault-gpio` | `gpio_controller.py` | LEDs · LCD · Button · Socket.IO-Client |

---

## Schnellstart

```bash
# Repository klonen
git clone https://github.com/Pommes20304050/vault_os.git
cd vault_os

# Abhängigkeiten installieren
pip install -r requirements_pi.txt

# Services einrichten
sudo cp services/*.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable vault-app vault-publisher vault-gpio

# Starten
bash start.sh
```

`start.sh` lädt automatisch den LCD-Kernel-Overlay, startet alle Services, wartet bis Flask bereit ist und öffnet Chromium mit dem Dashboard.

---

## Projektstruktur

```
vault_os/
├── app.py                    ← Flask · Kamera · Gesichtserkennung · MQTT
├── publisher.py              ← DHT11 + psutil → MQTT
├── gpio_controller.py        ← LEDs · HD44780 LCD · Button · Socket.IO
├── face_worker.py            ← Gesichtserkennung Worker-Prozess
├── scrape_and_train.py       ← Trainings-Skript
├── start.sh                  ← Ein-Befehl-Start
├── setup.sh                  ← Ersteinrichtung
│
├── templates/
│   ├── dashboard.html        ← Fallout-Dashboard
│   └── manage.html           ← Personalverwaltung
│
├── faces/                    ← Gesichtsfotos pro Person
│   ├── Louis/
│   └── Viktor/
│
├── models/                   ← KI-Modelle (ONNX)
│   ├── face_detection_yunet_2023mar.onnx
│   ├── face_recognition_sface_2021dec.onnx
│   ├── lbph_model.yml
│   ├── labels.json
│   └── allowed.json
│
├── services/                 ← systemd-Units
│   ├── vault-app.service
│   ├── vault-publisher.service
│   └── vault-gpio.service
│
├── requirements.txt          ← Python-Abhängigkeiten
├── requirements_pi.txt       ← Pi-spezifische Abhängigkeiten
├── VERKABELUNG.md            ← Detaillierter Verkabelungsplan
└── test_*.py                 ← Hardware-Testsripte
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
  Name   UNBEKANNT → LED Rot
    │
  ≥ 50% Konfidenz?
  ┌──┴──┐
 JA    NEIN
  │      │
ERLAUBT  VERWEIGERT
LED Grün  LED Rot
```

### Neue Person registrieren

1. `http://<Pi-IP>:5000/manage` im Browser öffnen
2. Person anlegen → **20–30 Fotos** aufnehmen (`SPACE`)
3. **Trainieren** klicken
4. Person auf **ERLAUBT** setzen

> **Tipp:** Fotos bei verschiedener Beleuchtung und aus leicht unterschiedlichen Winkeln aufnehmen für bessere Erkennungsrate.

---

## Konfiguration

### app.py

```python
BROKER_HOST      = "127.0.0.1"   # MQTT-Broker (lokal)
VAULT_NAME       = "vault111"    # MQTT-Topic-Prefix
COSINE_THRESHOLD = 0.363         # Min. Score für bekannte Person
ALLOW_CONFIDENCE = 50.0          # Min. % für Zutritt ERLAUBT
CAM_W, CAM_H     = 640, 480     # Kameraauflösung
```

### publisher.py

```python
DHT_GPIO         = 4             # DHT11 GPIO-Pin
PUBLISH_INTERVAL = 5             # Sekunden zwischen Messungen
BIT_THRESHOLD_NS = 100_000       # DHT11 Bit-Dekodierung (100µs)
```

---

## API-Routen

| Route | Methode | Beschreibung |
|---|---|---|
| `/` | GET | Fallout-Dashboard |
| `/manage` | GET | Personalverwaltung |
| `/video_feed` | GET | MJPEG-Kamerastream |
| `/api/state` | GET | Aktueller Systemstatus (JSON) |
| `/api/persons` | GET / POST | Personen auflisten / anlegen |
| `/api/persons/<name>` | DELETE | Person löschen |
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
| GPIO | lgpio (Pi 5 / RP1 kompatibel) |
| Kommunikation | Socket.IO WebSocket · MQTT (paho) |
| Telemetrie | psutil |
| LCD | HD44780 via Kernel-Overlay `/dev/lcd` |
| Frontend | Vanilla JS · Socket.IO Client · MJPEG |

---

## Troubleshooting

| Problem | Lösung |
|---|---|
| Kamera nicht gefunden | USB prüfen · `v4l2-ctl --list-devices` |
| LCD zeigt nichts | `/dev/lcd` vorhanden? `start.sh` lädt Overlay automatisch |
| DHT11 kein Signal | 10kΩ Pull-Up zwischen 5V und DATA · Wiring prüfen |
| Button reagiert nicht | GPIO 21 auf GND? `gpio_claim_input` vor `gpio_claim_alert` nötig |
| Service startet nicht | `journalctl -u vault-app -f` für Logs |
| Person wird nicht erkannt | Mehr Fotos aufnehmen · danach Trainieren klicken |
| MQTT keine Daten | `sudo systemctl status mosquitto` |

---

## Services verwalten

```bash
# Status prüfen
sudo systemctl status vault-app vault-publisher vault-gpio

# Logs anzeigen
journalctl -u vault-app -f
journalctl -u vault-gpio -f

# Neustart
sudo systemctl restart vault-app vault-publisher vault-gpio

# Alle stoppen
sudo systemctl stop vault-app vault-publisher vault-gpio
```

---

<div align="center">

```
╔══════════════════════════════════════════╗
║         VAULT-TEC INDUSTRIES            ║
║                                         ║
║   VaultOS wird initialisiert...         ║
║   ████████████████████░░░  87%          ║
║                                         ║
║   Please stand by.                      ║
╚══════════════════════════════════════════╝
```

*In 2 Tagen gebaut. Auf einem Pi 5. Mit echter Hardware.*

</div>
