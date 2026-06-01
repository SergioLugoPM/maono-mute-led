"""
Maono PD100X - Mute LED Mod v2.0
=================================
Cambia el LED del microfono segun el boton fisico de mute.

CONFIGURACION (edita esta seccion):
"""

# ── Color cuando MUTEADO ─────────────────────────────────────────────────────
#   0=naranja  1=verde  2=teal  3=morado  4=rainbow
#   5=naranja-pulse  6=verde-pulse  7=teal-pulse  8=morado-pulse  9=rainbow-pulse
#   No hay rojo en el firmware — naranja es lo mas cercano.
COLOR_MUTED = 0   # naranja

# ── Modo cuando ACTIVO ───────────────────────────────────────────────────────
#   Mismos colores 0-9 de arriba, O uno de los modos dinamicos:
#   10=Dynamic I  11=Dynamic II  12=Level Meter (reacciona al audio!)
COLOR_ACTIVE = 12  # Level Meter — reacciona al audio cuando no estas muteado

# ─────────────────────────────────────────────────────────────────────────────

import sys
import os

_LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "maono_mute_led.log")
if sys.stdout is None or not hasattr(sys.stdout, 'reconfigure'):
    sys.stdout = open(_LOG, 'w', encoding='utf-8', buffering=1)
    sys.stderr = sys.stdout
else:
    sys.stdout.reconfigure(encoding='utf-8')

import ctypes
import ctypes.wintypes as wt
import time
import hid

VID = 0x352F
PID = 0x0108
CMD_LED   = 0x38
CMD_POWER = 0x36
STATUS_REPORT_TYPE = 34   # b6=0x22


def _make_cmd(cmd: int, param: int) -> bytes:
    checksum = (270 - cmd - param) % 256
    return bytes([0x4B, 0xC4, 0x0B, 0x00, 0x00, 0x03,
                  cmd, 0x20, param, 0x00, checksum, 0xFE]) + bytes(52)


def open_device():
    k32 = ctypes.WinDLL('kernel32', use_last_error=True)
    k32.CreateFileA.restype  = wt.HANDLE
    k32.CreateFileA.argtypes = [ctypes.c_char_p, wt.DWORD, wt.DWORD,
                                 ctypes.c_void_p, wt.DWORD, wt.DWORD, wt.HANDLE]
    k32.CreateEventW.restype = wt.HANDLE

    devs = hid.enumerate(VID, PID)
    if not devs:
        print("ERROR: PD100X no encontrado.")
        sys.exit(1)

    path = devs[0]['path']

    reader = hid.device()
    reader.open_path(path)
    reader.set_nonblocking(False)

    writer = k32.CreateFileA(path, 0xC0000000, 0x3, None, 3, 0x40000000, None)
    if ctypes.get_last_error() != 0:
        print(f"ERROR abriendo HID: {ctypes.get_last_error()} — cierra Maono Link.")
        sys.exit(1)

    return k32, writer, reader


def send_led(k32, handle, cmd: int, param: int):
    data = _make_cmd(cmd, param)
    buf  = (ctypes.c_ubyte * 64)(*data)
    evt  = k32.CreateEventW(None, True, False, None)

    class OVERLAPPED(ctypes.Structure):
        _fields_ = [('Internal',     ctypes.c_size_t),
                    ('InternalHigh', ctypes.c_size_t),
                    ('Offset',       wt.DWORD),
                    ('OffsetHigh',   wt.DWORD),
                    ('hEvent',       wt.HANDLE)]
    ov = OVERLAPPED()
    ov.hEvent = evt
    written = wt.DWORD(0)
    r = k32.WriteFile(handle, buf, 64, ctypes.byref(written), ctypes.byref(ov))
    if r == 0 and ctypes.get_last_error() == 997:
        k32.WaitForSingleObject(evt, 2000)
        k32.GetOverlappedResult(handle, ctypes.byref(ov), ctypes.byref(written), True)
    k32.CloseHandle(evt)


def read_mute_state(reader: hid.device):
    """Lee el reporte de estado (b6=0x22). Retorna True/False/None."""
    deadline = time.time() + 1.5
    while time.time() < deadline:
        data = reader.read(64, 800)
        if data and len(data) >= 12 and data[6] == STATUS_REPORT_TYPE:
            return bool(data[8])
    return None


def main():
    labels = {
        0: 'naranja', 1: 'verde', 2: 'teal', 3: 'morado', 4: 'rainbow',
        5: 'naranja-pulse', 6: 'verde-pulse', 7: 'teal-pulse',
        8: 'morado-pulse', 9: 'rainbow-pulse',
        10: 'Dynamic I', 11: 'Dynamic II', 12: 'Level Meter',
    }
    active_label = labels.get(COLOR_ACTIVE, str(COLOR_ACTIVE))
    muted_label  = labels.get(COLOR_MUTED,  str(COLOR_MUTED))

    print("=" * 48)
    print("  Maono PD100X - Mute LED Mod v2.0")
    print("=" * 48)
    print(f"  Muteado  -> {muted_label} (idx={COLOR_MUTED})")
    print(f"  Activo   -> {active_label} (idx={COLOR_ACTIVE})")
    print("  Ctrl+C para salir")
    print()

    k32, writer, reader = open_device()
    print("Microfono abierto OK")

    send_led(k32, writer, CMD_POWER, 1)
    time.sleep(0.15)

    last_muted = None
    try:
        while True:
            muted = read_mute_state(reader)
            if muted is None:
                continue
            if muted != last_muted:
                last_muted = muted
                color = COLOR_MUTED if muted else COLOR_ACTIVE
                send_led(k32, writer, CMD_LED, color)
                label = muted_label if muted else active_label
                print(f"[{time.strftime('%H:%M:%S')}] {'MUTEADO' if muted else 'ACTIVO '} -> {label}")

    except KeyboardInterrupt:
        print("\nSaliendo - restaurando LED...")
        send_led(k32, writer, CMD_LED, COLOR_ACTIVE)

    finally:
        reader.close()
        ctypes.windll.kernel32.CloseHandle(writer)
        print("Listo.")


if __name__ == "__main__":
    main()
