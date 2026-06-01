"""
Maono PD100X - Mute LED Mod
El LED cambia de color segun el estado de mute del boton fisico.

  Muteado  -> naranja
  Activo   -> verde

Uso:
  1. Cierra Maono Link
  2. python maono_mute_led.py

Para detener: Ctrl+C  (restaura LED verde)
"""

import sys
import os

# Cuando corre sin terminal (pythonw / autostart), redirigir a log
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

COLOR_MUTED  = 0  # naranja
COLOR_ACTIVE = 1  # verde

CMD_LED   = 0x38
CMD_POWER = 0x36

STATUS_REPORT_TYPE = 34  # b6=0x22 = reporte de estado de mute del hardware


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
        print("ERROR: PD100X no encontrado. Conecta el microfono.")
        sys.exit(1)

    path = devs[0]['path']

    # Leer input reports primero para despertar la comunicacion USB
    reader = hid.device()
    reader.open_path(path)
    reader.set_nonblocking(False)  # blocking para leer el estado facilmente

    # Abrir handle de escritura
    writer = k32.CreateFileA(path, 0xC0000000, 0x3, None, 3, 0x40000000, None)
    err = ctypes.get_last_error()
    if err != 0:
        print(f"ERROR abriendo dispositivo HID: {err}")
        print("Cierra Maono Link e intenta de nuevo.")
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


def read_mute_state(reader: hid.device) -> bool | None:
    """
    Lee input reports buscando el reporte de estado (b6=34).
    Retorna True si muteado, False si activo, None si no hay dato aun.
    Timeout de 1.5 segundos (el mic manda el reporte cada ~650ms).
    """
    deadline = time.time() + 1.5
    while time.time() < deadline:
        data = reader.read(64, 800)  # 800ms timeout
        if not data or len(data) < 12:
            continue
        if data[6] == STATUS_REPORT_TYPE:  # b6=0x22 = status report
            return bool(data[8])           # b8: 1=muted, 0=active
    return None


def main():
    print("=" * 45)
    print("  Maono PD100X - Mute LED Mod")
    print("=" * 45)
    print(f"  Boton fisico muteado -> naranja (idx={COLOR_MUTED})")
    print(f"  Boton fisico activo  -> verde   (idx={COLOR_ACTIVE})")
    print("  Ctrl+C para salir")
    print()

    k32, writer, reader = open_device()
    print(f"Microfono abierto OK")

    # Encender RGB
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
                estado = "MUTEADO  (naranja)" if muted else "ACTIVO   (verde)"
                print(f"[{time.strftime('%H:%M:%S')}] {estado}")

    except KeyboardInterrupt:
        print("\nSaliendo - restaurando LED verde...")
        send_led(k32, writer, CMD_LED, COLOR_ACTIVE)

    finally:
        reader.close()
        ctypes.windll.kernel32.CloseHandle(writer)
        print("Listo.")


if __name__ == "__main__":
    main()
