#!/bin/bash
# ╔══════════════════════════════════════════════════════════╗
# ║   VAULT-TEC INDUSTRIES :: VAULT-OS AUTO-SETUP           ║
# ║   Raspberry Pi 5 — führe aus mit: bash setup.sh         ║
# ╚══════════════════════════════════════════════════════════╝
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$SCRIPT_DIR/venv"

echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║   VAULT-TEC INDUSTRIES :: VAULT-OS SETUP            ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""
echo "  Installationsverzeichnis: $SCRIPT_DIR"
echo ""

# ── [1/7] System-Pakete ────────────────────────────────────────────────────
echo "[1/7] Installiere System-Pakete..."
sudo apt-get update -qq
sudo apt-get install -y \
  mosquitto mosquitto-clients \
  python3-pip python3-venv python3-dev \
  libopenblas-dev \
  libhdf5-dev libopenjp2-7 \
  libgpiod3 liblgpio-dev \
  v4l-utils \
  git curl wget \
  2>/dev/null
echo "  System-Pakete OK"

# ── [2/7] Kamera aktivieren ────────────────────────────────────────────────
echo "[2/7] Aktiviere Kamera-Interface..."
if command -v raspi-config &>/dev/null; then
  sudo raspi-config nonint do_camera 0 2>/dev/null || true
  echo "  Kamera aktiviert (raspi-config)"
else
  echo "  raspi-config nicht gefunden — Legacy-Kamera ggf. manuell aktivieren"
fi

# ── [2b] DTOverlay für DHT11 (Kernel IIO-Treiber, Pi 5 kompatibel) ────────
echo "[2b] Konfiguriere DHT11 Kernel-Overlay..."
CONFIG=/boot/firmware/config.txt
if ! grep -q "dtoverlay=dht11" "$CONFIG" 2>/dev/null; then
  echo "dtoverlay=dht11,gpiopin=4" | sudo tee -a "$CONFIG" > /dev/null
  echo "  DHT11-Overlay eingetragen (GPIO4) — Neustart erforderlich"
else
  echo "  DHT11-Overlay bereits eingetragen"
fi

# ── [3/7] Mosquitto konfigurieren ─────────────────────────────────────────
echo "[3/7] Konfiguriere Mosquitto MQTT-Broker..."
sudo tee /etc/mosquitto/conf.d/vault.conf > /dev/null <<'MQTTCONF'
listener 1883 127.0.0.1
allow_anonymous true
MQTTCONF
sudo systemctl enable mosquitto
sudo systemctl restart mosquitto
echo "  Mosquitto läuft auf Port 1883 (localhost)"

# ── [4/7] Python-Virtualenv + Abhängigkeiten ──────────────────────────────
echo "[4/7] Erstelle Python-Umgebung..."
python3 -m venv "$VENV"
source "$VENV/bin/activate"

pip install --upgrade pip --quiet

echo "  Installiere Python-Pakete (dauert einige Minuten)..."
pip install \
  flask>=3.0.0 \
  flask-socketio>=5.3.6 \
  paho-mqtt>=1.6.1 \
  psutil>=5.9.8 \
  requests>=2.31.0 \
  numpy>=1.26.0 \
  RPLCD>=1.3.0 \
  "python-socketio[client]>=5.8.0" \
  lgpio \
  rpi-lgpio \
  --quiet

# OpenCV contrib (groß — separat damit Fehler klar sichtbar)
echo "  Installiere OpenCV contrib (kann 5-10 min dauern)..."
pip install "opencv-contrib-python>=4.9.0.80" --quiet

echo "  Python-Pakete OK"

# ── [5/7] Verzeichnisse + ONNX-Modelle ────────────────────────────────────
echo "[5/7] Erstelle Verzeichnisse + lade ONNX-Modelle..."
mkdir -p "$SCRIPT_DIR/faces"
mkdir -p "$SCRIPT_DIR/models"

DET_MODEL="$SCRIPT_DIR/models/face_detection_yunet_2023mar.onnx"
REC_MODEL="$SCRIPT_DIR/models/face_recognition_sface_2021dec.onnx"

if [ ! -f "$DET_MODEL" ]; then
  echo "  Lade YuNet-Detektionsmodell..."
  wget -q -O "$DET_MODEL" \
    "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx" \
    || echo "  [WARN] Download fehlgeschlagen — manuell in models/ kopieren"
fi

if [ ! -f "$REC_MODEL" ]; then
  echo "  Lade SFace-Erkennungsmodell..."
  wget -q -O "$REC_MODEL" \
    "https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx" \
    || echo "  [WARN] Download fehlgeschlagen — manuell in models/ kopieren"
fi

echo "  Modelle OK"

# ── [6/7] Systemd-Dienste installieren ────────────────────────────────────
echo "[6/7] Installiere systemd-Dienste..."

install_service() {
  local name="$1"
  local src="$SCRIPT_DIR/services/${name}.service"
  if [ ! -f "$src" ]; then
    echo "  [WARN] $src nicht gefunden — übersprungen"
    return
  fi
  sed "s|/home/pi/vault_os|${SCRIPT_DIR}|g" "$src" \
    | sudo tee "/etc/systemd/system/${name}.service" > /dev/null
  echo "  Dienst installiert: $name"
}

install_service vault-app
install_service vault-publisher
install_service vault-gpio

# Alten vault-face Dienst entfernen falls vorhanden
if [ -f /etc/systemd/system/vault-face.service ]; then
  sudo systemctl disable vault-face 2>/dev/null || true
  sudo rm /etc/systemd/system/vault-face.service
  echo "  Veralteter vault-face Dienst entfernt"
fi

sudo systemctl daemon-reload
sudo systemctl enable vault-app vault-publisher vault-gpio
echo "  Alle Dienste aktiviert"

# ── [7/7] Fertig ───────────────────────────────────────────────────────────
PI_IP=$(hostname -I 2>/dev/null | awk '{print $1}')

echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║   SETUP ABGESCHLOSSEN                               ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""
echo "  Dienste starten:"
echo "    sudo systemctl start vault-app"
echo "    sudo systemctl start vault-publisher"
echo "    sudo systemctl start vault-gpio"
echo ""
echo "  Oder alle auf einmal:"
echo "    sudo systemctl start vault-app vault-publisher vault-gpio"
echo ""
echo "  Dashboard öffnen:"
echo "    http://${PI_IP:-<Pi-IP>}:5000"
echo ""
echo "  Logs überwachen:"
echo "    journalctl -u vault-app -f"
echo "    journalctl -u vault-gpio -f"
echo "    journalctl -u vault-publisher -f"
echo ""
echo "  Hardware-Test:"
echo "    source venv/bin/activate && python3 test_hardware.py"
echo ""
if [ -n "$PI_IP" ]; then
  echo "  Pi-IP-Adresse: $PI_IP"
  echo ""
fi
echo "  HINWEIS: Nach erstem Start im Browser anmelden,"
echo "  dann Gesichter über das Dashboard hinzufügen."
echo ""
