import time
import os
import lgpio
import socketio

# ── Pin-Konfiguration (BCM-Nummerierung) ──────────────────────────────────────
LED_BLUE  = 17
LED_GREEN = 27
LED_RED   = 22
BTN_PIN   = 21
BTN_LED   = 12

# ── lgpio — LEDs + Button ─────────────────────────────────────────────────────
_h = lgpio.gpiochip_open(0)
for _p in (LED_BLUE, LED_GREEN, LED_RED, BTN_LED):
    lgpio.gpio_claim_output(_h, _p, 0)
lgpio.gpio_claim_input(_h, BTN_PIN, lgpio.SET_PULL_UP)

def leds(blue=False, green=False, red=False):
    lgpio.gpio_write(_h, LED_BLUE,  1 if blue  else 0)
    lgpio.gpio_write(_h, LED_GREEN, 1 if green else 0)
    lgpio.gpio_write(_h, LED_RED,   1 if red   else 0)

# ── Display-Modus ─────────────────────────────────────────────────────────────
_mode = 0          # 0 = Gesichtserkennung, 1 = System-Stats
_last_btn   = 0.0
_last_state = {}
_stats_index = 0   # welche Stat gerade angezeigt wird (0-3)
_stats_names = ["CPU", "RAM", "Disk", "CPU-Temp"]

def _btn_callback(chip, gpio, level, tick):
    global _mode, _last_btn, _stats_index
    now = time.time()
    if level == 0 and (now - _last_btn) > 0.3:  # debounce 300ms
        _last_btn = now
        _mode = 1 - _mode
        _stats_index = 0
        led_val = 1 if _mode else 0
        ret = lgpio.gpio_write(_h, BTN_LED, led_val)
        label = "SYSTEM STATS" if _mode else "GESICHT"
        print(f"[BTN] Modus: {label}  LED={led_val}  ret={ret}", flush=True)
        _force_display()

lgpio.gpio_claim_alert(_h, BTN_PIN, lgpio.FALLING_EDGE, lgpio.SET_PULL_UP)
_btn_cb = lgpio.callback(_h, BTN_PIN, lgpio.FALLING_EDGE, _btn_callback)

# ── LCD via Kernel-Treiber /dev/lcd ──────────────────────────────────────────
LCD_DEV = "/dev/lcd"

if os.path.exists(LCD_DEV):
    print(f"[GPIO] LCD Kernel-Treiber: {LCD_DEV}")
else:
    print("[GPIO] /dev/lcd nicht gefunden — warte auf Treiber...")

_lcd_cache = ["", ""]

def display(line1: str, line2: str, temp=None, hum=None):
    if not os.path.exists(LCD_DEV):
        return
    t_str = f"{temp:.0f}C".rjust(3) if temp is not None else "   "
    h_str = f"{hum:.0f}%".rjust(3)  if hum  is not None else "   "
    l1 = line1[:13].ljust(13) + t_str
    l2 = line2[:13].ljust(13) + h_str
    if l1 == _lcd_cache[0] and l2 == _lcd_cache[1]:
        return
    _lcd_cache[0] = l1
    _lcd_cache[1] = l2
    for attempt in range(3):
        try:
            with open(LCD_DEV, "w") as f:
                f.write(f"\x0c{l1}\n{l2}")
            print(f"[LCD] '{l1}' | '{l2}'")
            return
        except OSError:
            time.sleep(0.05)
    print(f"[LCD] FEHLER: /dev/lcd busy")

def display_stats(data):
    cpu  = data.get("cpu_load")
    ram  = data.get("ram")
    disk = data.get("disk")
    ctmp = data.get("cpu_temp")

    c = f"{cpu:.0f}%" if cpu  is not None else "--"
    r = f"{ram:.0f}%" if ram  is not None else "--"
    d = f"{disk:.0f}%" if disk is not None else "--"
    t = f"{ctmp:.1f}C" if ctmp is not None else "---"

    l1 = f"CPU{c:>4}  RAM{r:>4}"
    l2 = f"DSK{d:>4}  T{t:>6}"

    if not os.path.exists(LCD_DEV):
        return
    if l1 == _lcd_cache[0] and l2 == _lcd_cache[1]:
        return
    _lcd_cache[0] = l1
    _lcd_cache[1] = l2
    for attempt in range(3):
        try:
            with open(LCD_DEV, "w") as f:
                f.write(f"\x0c{l1}\n{l2}")
            print(f"[LCD] '{l1}' | '{l2}'")
            return
        except OSError:
            time.sleep(0.05)

def _force_display():
    """Leert den Cache damit nächstes display() sofort schreibt."""
    _lcd_cache[0] = ""
    _lcd_cache[1] = ""

display("VAULT-OS", "Bereit...")

# ── Socket.IO Client ──────────────────────────────────────────────────────────
sio = socketio.Client(reconnection=True, reconnection_attempts=0,
                      reconnection_delay=2)

@sio.on("connect")
def on_connect():
    print("[GPIO] Verbunden mit VaultOS")
    display("VAULT-OS", "Verbunden!")

@sio.on("disconnect")
def on_disconnect():
    print("[GPIO] Verbindung verloren — warte...")
    leds(False, False, False)
    display("VAULT-OS", "Getrennt...")

@sio.on("state_update")
def on_state(data):
    global _last_state
    _last_state = data
    temp     = data.get("temperature")
    hum      = data.get("humidity")

    if _mode == 1:
        display_stats(data)
        return

    fd       = data.get("face_detection") or {}
    ac       = data.get("access")         or {}
    name     = fd.get("name", "---")
    conf     = float(fd.get("confidence", 0))
    faces    = int(fd.get("faces", 0))
    decision = (ac.get("decision") or "IDLE").upper()

    if faces == 0 or name in ("---", ""):
        leds(False, False, False)
        display("Kein Gesicht", "IDLE", temp, hum)
    elif decision == "ERLAUBT":
        leds(blue=True, green=True, red=False)
        display(name, f"{conf:.0f}% ERLAUBT", temp, hum)
    elif decision == "VERWEIGERT":
        leds(blue=True, green=False, red=True)
        display(name, f"{conf:.0f}% VERWGRT", temp, hum)
    elif decision == "UNBEKANNT":
        leds(blue=True, green=False, red=True)
        display("Unbekannt", "UNBEKANNT", temp, hum)
    else:
        leds(False, False, False)
        display("VAULT-OS", "IDLE", temp, hum)

# ── Start ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("[GPIO] Starte GPIO-Controller...")
    print(f"[GPIO] LEDs: Blau=GPIO{LED_BLUE}  Grün=GPIO{LED_GREEN}  Rot=GPIO{LED_RED}")
    print(f"[GPIO] Button: GPIO{BTN_PIN}")
    try:
        sio.connect("http://127.0.0.1:5000")
        sio.wait()
    except KeyboardInterrupt:
        print("\n[GPIO] Beende...")
    finally:
        leds(False, False, False)
        if os.path.exists(LCD_DEV):
            with open(LCD_DEV, "w") as f:
                f.write("\x0cAusgeschaltet")
            time.sleep(1)
            with open(LCD_DEV, "w") as f:
                f.write("\x0c")
        for _p in (LED_BLUE, LED_GREEN, LED_RED, BTN_LED):
            lgpio.gpio_write(_h, _p, 0)
        lgpio.gpiochip_close(_h)
