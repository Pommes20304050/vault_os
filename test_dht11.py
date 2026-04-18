import glob
import time

def _iio_path(name):
    paths = glob.glob(f"/sys/bus/iio/devices/iio:device*/{name}")
    return paths[0] if paths else None

TEMP_PATH = _iio_path("in_temp_input")
HUM_PATH  = _iio_path("in_humidityrelative_input")

if not TEMP_PATH or not HUM_PATH:
    print("FEHLER: IIO-Treiber nicht gefunden!")
    print("  dtoverlay=dht11,gpiopin=4 in /boot/firmware/config.txt prüfen")
    exit(1)

print(f"Sensor gefunden: {TEMP_PATH}")
print("Lese DHT11... (Strg+C zum Beenden)\n")

while True:
    temp, hum = None, None
    for _ in range(5):
        try:
            temp = int(open(TEMP_PATH).read().strip()) / 1000
            hum  = int(open(HUM_PATH).read().strip())  / 1000
            break
        except OSError:
            time.sleep(0.5)
    if temp is not None:
        print(f"Temp: {temp:.1f}°C   Humidity: {hum:.0f}% RH")
    else:
        print("Kein Signal — Sensor antwortet nicht")
    time.sleep(2)
