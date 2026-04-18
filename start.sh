#!/bin/bash
# VAULT-OS Starter

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PI_IP=$(hostname -I 2>/dev/null | awk '{print $1}')

echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║   VAULT-TEC INDUSTRIES :: VAULT-OS START            ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""

# LCD-Kernel-Overlay sicherstellen
if [ ! -e /dev/lcd ]; then
  echo "  /dev/lcd fehlt — lade hd44780-lcd Overlay..."
  sudo dtoverlay hd44780-lcd pin_d4=25 pin_d5=5 pin_d6=13 pin_d7=19 pin_en=24 pin_rs=23 2>/dev/null
  # Warten bis /dev/lcd erscheint (max 5s)
  for i in $(seq 1 10); do
    [ -e /dev/lcd ] && break
    sleep 0.5
  done
  sudo chmod a+rw /dev/lcd 2>/dev/null
  echo "  LCD Overlay geladen"
else
  sudo chmod a+rw /dev/lcd 2>/dev/null
fi

# Button-LED (GPIO12) kurz blinken als Startindikator
python3 -c "
import lgpio, time
h = lgpio.gpiochip_open(0)
lgpio.gpio_claim_output(h, 12, 0)
for _ in range(3):
    lgpio.gpio_write(h, 12, 1); time.sleep(0.15)
    lgpio.gpio_write(h, 12, 0); time.sleep(0.15)
lgpio.gpiochip_close(h)
" 2>/dev/null

# Mosquitto sicherstellen
sudo systemctl start mosquitto 2>/dev/null

# Dienste starten
echo "  Starte Dienste..."
sudo systemctl start vault-app vault-publisher vault-gpio
sleep 8

# Status prüfen
ALL_OK=true
for svc in vault-app vault-publisher vault-gpio; do
    STATUS=$(systemctl is-active "$svc")
    if [ "$STATUS" = "active" ]; then
        echo "  ✓ $svc"
    else
        echo "  ✗ $svc ($STATUS)"
        ALL_OK=false
    fi
done

echo ""
if $ALL_OK; then
    echo "  Dashboard: http://${PI_IP:-<Pi-IP>}:5000"
    echo "  Öffne Browser..."
    # Warten bis Flask wirklich bereit ist
    for i in $(seq 1 10); do
        if curl -s -o /dev/null "http://127.0.0.1:5000"; then
            break
        fi
        sleep 1
    done
    chromium --new-window \
             --disable-features=HttpsUpgrades \
             --allow-insecure-localhost \
             "http://127.0.0.1:5000" 2>/dev/null &
else
    echo "  Fehler! Logs prüfen:"
    echo "    journalctl -u vault-app -f"
    echo "    journalctl -u vault-gpio -f"
fi
echo ""
