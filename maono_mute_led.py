"""
Maono PD100X - Mute LED Mod
============================
Cambia el LED del microfono segun el boton fisico de mute.
No requiere Maono Link.

CONFIGURACION:
"""

# ── Color cuando MUTEADO ─────────────────────────────────────────────────────
#   0=naranja  1=verde  2=teal  3=morado  4=rainbow
#   5=naranja-pulse  6=verde-pulse  7=teal-pulse  8=morado-pulse  9=rainbow-pulse
COLOR_MUTED = 0   # naranja

# ── Modo cuando ACTIVO ───────────────────────────────────────────────────────
#   Colores estaticos: 0-4  |  Pulse: 5-9
#   Dinamicos: 10=Dynamic I  11=Dynamic II  12=Level Meter (reacciona al audio)
COLOR_ACTIVE = 1  # verde

# ─────────────────────────────────────────────────────────────────────────────

import sys
import os
import time
import hid

_LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "maono_mute_led.log")
if sys.stdout is None or not hasattr(sys.stdout, 'reconfigure'):
    sys.stdout = open(_LOG, 'w', encoding='utf-8', buffering=1)
    sys.stderr = sys.stdout
else:
    sys.stdout.reconfigure(encoding='utf-8')

VID = 0x352F
PID = 0x0108
STATUS_BYTE = 0x22  # b6 del reporte de estado

# Secuencia de init del firmware (capturada de Maono Link)
# Activa los status reports del boton fisico
INIT_SEQUENCE = [
    [75, 196, 11, 0, 0, 6,  0,  0,  3, 0,  40, 255],
    [75, 196,  9, 0, 0, 4,  8, 16, 23, 255,  0,   0],
    [75, 196, 11, 0, 0, 3, 11, 16,  1, 0,  18, 255],
    [75, 196, 11, 0, 0, 6,  3,  0, 26, 0,  14, 255],
    [75, 196, 11, 0, 0, 6, 29,  0, 26, 0, 244, 254],
    [75, 196, 11, 0, 0, 6, 34, 32, 23, 0, 210, 254],
    [75, 196, 11, 0, 0, 3, 11, 16,  0, 0,  19, 255],
]


def make_led_report(cmd, param):
    ck = (270 - cmd - param) % 256
    return [0x4B, 0xC4, 0x0B, 0, 0, 3, cmd, 0x20, param, 0, ck, 0xFE] + [0] * 52


def main():
    labels = {
        0: 'naranja', 1: 'verde', 2: 'teal', 3: 'morado', 4: 'rainbow',
        5: 'naranja-pulse', 6: 'verde-pulse', 7: 'teal-pulse',
        8: 'morado-pulse', 9: 'rainbow-pulse',
        10: 'Dynamic I', 11: 'Dynamic II', 12: 'Level Meter',
    }

    print("=" * 48)
    print("  Maono PD100X - Mute LED Mod")
    print("=" * 48)
    print(f"  Muteado -> {labels.get(COLOR_MUTED)} (idx={COLOR_MUTED})")
    print(f"  Activo  -> {labels.get(COLOR_ACTIVE)} (idx={COLOR_ACTIVE})")
    print("  Ctrl+C para salir")
    print()

    # Abrir dispositivo
    devs = hid.enumerate(VID, PID)
    if not devs:
        print("ERROR: PD100X no encontrado.")
        sys.exit(1)

    dev = hid.device()
    dev.open_path(devs[0]['path'])
    dev.set_nonblocking(True)

    # Enviar init sequence para activar status reports
    print("Inicializando firmware...")
    for cmd in INIT_SEQUENCE:
        dev.write(cmd + [0] * (64 - len(cmd)))
        time.sleep(0.05)

    # Descartar primer status report (contiene basura del init)
    time.sleep(0.3)
    while True:
        data = dev.read(64)
        if not data:
            break

    # RGB ON + color activo
    dev.write(make_led_report(0x36, 1))
    time.sleep(0.03)
    dev.write(make_led_report(0x38, COLOR_ACTIVE))
    print("Microfono conectado OK")

    last_muted = None
    try:
        while True:
            data = dev.read(64)
            if not data or len(data) < 12 or data[6] != STATUS_BYTE:
                time.sleep(0.01)
                continue

            muted = bool(data[8])
            if muted == last_muted:
                continue

            last_muted = muted
            color = COLOR_MUTED if muted else COLOR_ACTIVE

            dev.write(make_led_report(0x36, 1))
            time.sleep(0.03)
            dev.write(make_led_report(0x38, color))

            label = labels.get(color, str(color))
            print(f"[{time.strftime('%H:%M:%S')}] {'MUTEADO' if muted else 'ACTIVO '} -> {label}")

    except KeyboardInterrupt:
        print("\nSaliendo...")
        dev.write(make_led_report(0x36, 1))
        time.sleep(0.03)
        dev.write(make_led_report(0x38, COLOR_ACTIVE))

    finally:
        dev.close()
        print("Listo.")


if __name__ == "__main__":
    main()
