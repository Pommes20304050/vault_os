import time
import json
import psutil
import lgpio
import paho.mqtt.client as mqtt

BROKER_HOST      = "127.0.0.1"
VAULT_NAME       = "vault111"
PUBLISH_INTERVAL = 5
DHT_GPIO         = 4
BIT_THRESHOLD_NS = 100_000   # 100µs in ns: below=0, above=1


def read_dht11():
    """Read DHT11 via lgpio falling-edge callbacks. Returns (temp, hum) or (None, None)."""
    h = lgpio.gpiochip_open(0)
    edges = []

    def cbf(chip, gpio, level, tick):
        edges.append(tick)

    try:
        lgpio.gpio_claim_output(h, DHT_GPIO, 0)
        time.sleep(0.02)
        lgpio.gpio_claim_alert(h, DHT_GPIO, lgpio.FALLING_EDGE, lgpio.SET_PULL_UP)
        cb = lgpio.callback(h, DHT_GPIO, lgpio.FALLING_EDGE, cbf)
        time.sleep(0.3)
        cb.cancel()
    finally:
        lgpio.gpiochip_close(h)

    if len(edges) < 41:
        return None, None

    dts = [edges[i+1] - edges[i] for i in range(len(edges)-1)]
    bits = [1 if dt > BIT_THRESHOLD_NS else 0 for dt in dts[:40]]

    val = 0
    for b in bits:
        val = (val << 1) | b

    rh_i = (val >> 32) & 0xFF
    rh_d = (val >> 24) & 0xFF
    tp_i = (val >> 16) & 0xFF
    tp_d = (val >> 8)  & 0xFF
    chk  =  val        & 0xFF

    if (rh_i + rh_d + tp_i + tp_d) & 0xFF != chk:
        return None, None

    return round(tp_i + tp_d / 10.0, 1), round(rh_i + rh_d / 10.0, 1)


def read_dht11_retry(attempts=5):
    for _ in range(attempts):
        temp, hum = read_dht11()
        if temp is not None:
            return temp, hum
        time.sleep(0.5)
    return None, None


def read_system():
    cpu_temp = None
    try:
        temps = psutil.sensors_temperatures()
        for key in ("cpu_thermal", "coretemp", "k10temp", "acpitz"):
            if key in temps and temps[key]:
                cpu_temp = temps[key][0].current
                break
    except Exception:
        pass
    return {
        "cpu_temp": round(cpu_temp, 1) if cpu_temp is not None else None,
        "cpu_load": round(psutil.cpu_percent(interval=1), 1),
        "ram":      round(psutil.virtual_memory().percent, 1),
        "disk":     round(psutil.disk_usage("/").percent, 1),
    }


def main():
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.connect(BROKER_HOST, 1883, 60)
    client.loop_start()
    print(f"[INFO] Vault Publisher läuft — {VAULT_NAME} → {BROKER_HOST}")

    while True:
        temp, humidity = read_dht11_retry()
        sys_data = read_system()
        base = f"vault/{VAULT_NAME}"

        if temp is not None:
            print(f"[DHT11] {temp}°C  {humidity}% RH")
            client.publish(f"{base}/temperature", str(temp))
            client.publish(f"{base}/humidity",    str(humidity))
        else:
            print("[DHT11] kein Signal")

        for key, val in sys_data.items():
            if val is not None:
                client.publish(f"{base}/{key}", str(val))

        all_data = {"temperature": temp, "humidity": humidity, **sys_data}
        client.publish(f"{base}/all", json.dumps(all_data))

        time.sleep(PUBLISH_INTERVAL)


if __name__ == "__main__":
    main()
