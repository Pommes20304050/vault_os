"""
VaultOS Hardware-Test (Pi 5 kompatibel)
Testet: LEDs · LCD 1602 (4-Bit) · DHT11 (IIO-Kernel-Treiber)
"""
import time
import glob
import lgpio
import RPi.GPIO as GPIO
from RPLCD.gpio import CharLCD

# ── Pins ──────────────────────────────────────────────────────────────────────
LED_BLUE  = 17
LED_GREEN = 27
LED_RED   = 22
LCD_RS, LCD_EN = 23, 24
LCD_PINS = [25, 5, 13, 19]   # D4 D5 D6 D7

# ── Fix: LCD-Pins via lgpio auf LOW setzen bevor RPLCD initialisiert ──────────
# rpi-lgpio liest unklamierte Pins als HIGH → EN startet HIGH → HD44780 latcht
# beim ersten GPIO.output(EN,0) Datenmüll. Vorher explizit LOW claimen.
_h = lgpio.gpiochip_open(0)
for _p in [LED_BLUE, LED_GREEN, LED_RED, LCD_RS, LCD_EN] + LCD_PINS:
    lgpio.gpio_claim_output(_h, _p, 0)
lgpio.gpiochip_close(_h)
time.sleep(0.1)

# ── GPIO / LED Setup ──────────────────────────────────────────────────────────
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
for pin in (LED_BLUE, LED_GREEN, LED_RED):
    GPIO.setup(pin, GPIO.OUT, initial=GPIO.LOW)

def leds(blue=False, green=False, red=False):
    GPIO.output(LED_BLUE,  GPIO.HIGH if blue  else GPIO.LOW)
    GPIO.output(LED_GREEN, GPIO.HIGH if green else GPIO.LOW)
    GPIO.output(LED_RED,   GPIO.HIGH if red   else GPIO.LOW)

# ── LCD Setup ─────────────────────────────────────────────────────────────────
print("Initialisiere LCD...")
lcd = CharLCD(numbering_mode=GPIO.BCM, cols=16, rows=2,
              pin_rs=LCD_RS, pin_e=LCD_EN, pins_data=LCD_PINS)
time.sleep(0.1)
lcd.clear()
time.sleep(0.05)

def lcd_line(row, text):
    lcd.cursor_pos = (row, 0)
    lcd.write_string(text[:16].ljust(16))

# ── DHT11 via Linux IIO-Kernel-Treiber ────────────────────────────────────────
def _iio_path(name):
    paths = glob.glob(f"/sys/bus/iio/devices/iio:device*/{name}")
    return paths[0] if paths else None

_TEMP_PATH = _iio_path("in_temp_input")
_HUM_PATH  = _iio_path("in_humidityrelative_input")
DHT_OK = bool(_TEMP_PATH and _HUM_PATH)

def read_dht():
    if not DHT_OK:
        return None, None
    try:
        temp = int(open(_TEMP_PATH).read().strip()) / 1000
        hum  = int(open(_HUM_PATH).read().strip())  / 1000
        return round(temp, 1), round(hum, 1)
    except Exception:
        return None, None

if not DHT_OK:
    print("DHT11: IIO-Treiber nicht gefunden — dtoverlay=dht11,gpiopin=4 in config.txt prüfen")

# ── TEST 1: LEDs ──────────────────────────────────────────────────────────────
print("\n[TEST 1] LEDs...")
lcd.clear()
lcd_line(0, "LED TEST")

for pin, name, color in [
    (LED_BLUE,  "Blau",  (True,  False, False)),
    (LED_GREEN, "Gruen", (False, True,  False)),
    (LED_RED,   "Rot",   (False, False, True )),
]:
    lcd_line(1, f">> {name}")
    leds(*color)
    print(f"  {name} AN")
    time.sleep(0.6)
    leds()
    time.sleep(0.2)

lcd_line(1, ">> ALLE AN")
leds(True, True, True)
print("  Alle AN")
time.sleep(1)
leds()
time.sleep(0.3)

# ── TEST 2: LCD ───────────────────────────────────────────────────────────────
print("\n[TEST 2] LCD...")
lcd.clear()
lcd_line(0, "VAULT-OS READY")
lcd_line(1, "LCD OK :)")
time.sleep(2)

# ── TEST 3: DHT11 (läuft bis Strg+C) ─────────────────────────────────────────
print("\n[TEST 3] DHT11 (Strg+C zum Beenden)...")
print(f"{'Temp':>8}  {'Humidity':>8}")
print("-" * 22)

try:
    while True:
        temp, hum = read_dht()
        if temp is not None:
            line2 = f"{temp:.1f}C  {hum:.0f}%RH"
            print(f"  {temp:.1f}°C   {hum:.0f}% RH")
        else:
            line2 = "Sensor liest..."
            print("  Sensor liest...")
        lcd_line(0, "VAULT-OS READY")
        lcd_line(1, line2)
        time.sleep(2)

except KeyboardInterrupt:
    print("\nTest beendet.")

finally:
    leds()
    lcd.clear()
    lcd_line(0, "Test beendet.")
    time.sleep(1)
    lcd.clear()
    GPIO.cleanup()
    print("GPIO bereinigt.")
