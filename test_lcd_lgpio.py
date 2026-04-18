"""Direct lgpio HD44780 LCD driver — bypasses RPLCD entirely."""
import lgpio
import time

# BCM pin numbers
RS  = 23
EN  = 24
D4  = 25
D5  = 5
D6  = 13
D7  = 19

PINS = [RS, EN, D4, D5, D6, D7]

h = lgpio.gpiochip_open(0)
for p in PINS:
    lgpio.gpio_claim_output(h, p, 0)

def _pulse_en():
    lgpio.gpio_write(h, EN, 1)
    time.sleep(0.001)          # >450 ns — 1 ms for safety
    lgpio.gpio_write(h, EN, 0)
    time.sleep(0.001)

def _write_nibble(nibble):
    lgpio.gpio_write(h, D4, (nibble >> 0) & 1)
    lgpio.gpio_write(h, D5, (nibble >> 1) & 1)
    lgpio.gpio_write(h, D6, (nibble >> 2) & 1)
    lgpio.gpio_write(h, D7, (nibble >> 3) & 1)
    _pulse_en()

def _send(byte, rs=0):
    lgpio.gpio_write(h, RS, rs)
    _write_nibble(byte >> 4)   # high nibble first
    _write_nibble(byte & 0x0F) # low nibble
    time.sleep(0.0002)         # typical command ~37 µs; we wait 200 µs

def _send_slow(byte, rs=0, delay=0.005):
    lgpio.gpio_write(h, RS, rs)
    _write_nibble(byte >> 4)
    _write_nibble(byte & 0x0F)
    time.sleep(delay)

def lcd_init():
    time.sleep(0.05)   # >40 ms after power-on

    # 8-bit init sequence (sent as nibbles in 4-bit mode entry)
    lgpio.gpio_write(h, RS, 0)
    _write_nibble(0x03); time.sleep(0.005)  # >4.1 ms
    _write_nibble(0x03); time.sleep(0.001)  # >100 µs
    _write_nibble(0x03); time.sleep(0.001)
    _write_nibble(0x02); time.sleep(0.001)  # switch to 4-bit

    # Now fully in 4-bit — send real commands
    _send(0x28)  # Function Set: 4-bit, 2 lines, 5x8
    _send(0x08)  # Display OFF
    _send_slow(0x01, delay=0.002)  # Clear Display (>1.52 ms)
    _send(0x06)  # Entry Mode: increment, no shift
    _send(0x0C)  # Display ON, cursor off, blink off
    print("[LCD] init done")

def lcd_clear():
    _send_slow(0x01, delay=0.002)

def lcd_pos(row, col):
    offsets = [0x00, 0x40]
    _send(0x80 | (offsets[row] + col))

def lcd_write(text):
    for ch in text[:16]:
        _send(ord(ch), rs=1)

def lcd_show(line1, line2=""):
    lcd_pos(0, 0); lcd_write(line1.ljust(16)[:16])
    lcd_pos(1, 0); lcd_write(line2.ljust(16)[:16])

try:
    lcd_init()
    lcd_show("VAULT-OS", "Direct lgpio OK!")
    print("[LCD] Text geschrieben")
    time.sleep(3)
    lcd_show("Hallo Welt", "LCD funktioniert")
    time.sleep(3)
    lcd_clear()
    lcd_show("Test OK", "Beende...")
    time.sleep(2)
finally:
    for p in PINS:
        lgpio.gpio_write(h, p, 0)
    lgpio.gpiochip_close(h)
    print("[LCD] GPIO freigegeben")
