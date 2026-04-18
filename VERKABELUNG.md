# Verkabelung — VaultOS GPIO

---

## Dein GPIO Extension Board (Draufsicht)

```
OBEN (Richtung Pi USB-Ports)
┌─────────────────────────────────────────┐
│ 3.3V │ 5V   │←── LCD VCC (5V, Pin 2)   │
│ SDA  │ 5V   │←── LCD SDA (Pin 3)       │
│ SCL  │ GND  │←── LCD SCL+GND (Pin 5,6) │
│ GP4  │      │←── DHT11 DATA            │
│ GND  │      │←── DHT11 GND             │
│      │      │                           │
│      │      │                           │
│      │      │                           │
│      │      │                           │
│      │      │                           │
│      │      │                           │
│      │      │                           │
│ GP16 │ GP26 │                           │
│ GP19 │ GP20 │                           │
│ GND  │ GP21 │←── hier bist du           │
└─────────────────────────────────────────┘
UNTEN RECHTS = GP21
```

---

## Benutze diese 3 Pins für die LEDs

> Alle 3 sind unten rechts — kurze Kabel reichen!

```
  GP16  →  LED BLAU   (blaues Kabel)
  GP20  →  LED GRÜN   (grünes Kabel)
  GP21  →  LED ROT    (rotes Kabel)
  GND   →  Minus-Schiene Breadboard (schwarzes Kabel)
```

---

## LEDs auf dem Breadboard

```
Extension Board          Breadboard
─────────────────────────────────────────────────────────

  GP16 ──────────────►  Reihe 1a
                         Reihe 1b ──[220Ω]── 1d ──► 🔵(+)  🔵(─)──► Minus(─)

  GP20 ──────────────►  Reihe 5a
                         Reihe 5b ──[220Ω]── 5d ──► 🟢(+)  🟢(─)──► Minus(─)

  GP21 ──────────────►  Reihe 9a
                         Reihe 9b ──[220Ω]── 9d ──► 🔴(+)  🔴(─)──► Minus(─)

  GND  ──────────────────────────────────────────────── Minus(─)

```

---

## LCD direkt am Extension Board

```
LCD Kabel    Extension Board Pin
─────────────────────────────────
  GND    ──►  GND  (neben SCL)
  VCC    ──►  5V   (ganz oben)
  SDA    ──►  SDA  (Pin 3)
  SCL    ──►  SCL  (Pin 5)
```

---

## DHT11 direkt am Extension Board

```
DHT11        Extension Board Pin
─────────────────────────────────
  VCC    ──►  3.3V (ganz oben links)
  DATA   ──►  GP4
  GND    ──►  GND  (neben GP4)
```

---

## LED — welcher Pin ist was?

```
      ┌──┐
      │  │
      └┬─┘
       │  langer Pin (+) → zum Widerstand
       │  kurzer Pin (−) → zur Minus-Schiene (─)
```

---

## gpio_controller.py — Pins anpassen

Da du GP16, GP20, GP21 benutzt, ändere oben in der Datei:

```python
LED_BLUE  = 16   # war 17
LED_GREEN = 20   # war 27
LED_RED   = 21   # war 22
```
