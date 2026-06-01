"""
Maono PD100X - Mute LED Mod v3.0
=================================
Cambia el LED del microfono segun el boton fisico de mute.
Puede correr con o sin Maono Link abierto.

CONFIGURACION (edita esta seccion):
"""

# ── Color cuando MUTEADO ─────────────────────────────────────────────────────
#   0=naranja  1=verde  2=teal  3=morado  4=rainbow
#   5=naranja-pulse  6=verde-pulse  7=teal-pulse  8=morado-pulse  9=rainbow-pulse
#   No hay rojo solido en el firmware — naranja es lo mas cercano.
COLOR_MUTED = 0   # naranja

# ── Modo cuando ACTIVO ───────────────────────────────────────────────────────
#   Colores estaticos: 0-4  |  Pulse: 5-9
#   Dinamicos: 10=Dynamic I  11=Dynamic II  12=Level Meter (reacciona al audio)
COLOR_ACTIVE = 12  # Level Meter

# ── Esquema RGB para modos dinamicos (0-9) ───────────────────────────────────
#   Solo aplica cuando COLOR_ACTIVE >= 10 (Dynamic/Level Meter).
#   Todos los esquemas muestran el espectro RGB completo con distintos patrones.
#   Solo funciona si Maono Link esta corriendo (el necesita inicializar el device).
#   Si Maono Link no esta activo, se ignora este parametro.
COLOR_SCHEME = 0   # 0-9, prueba distintos para ver la diferencia

# ─────────────────────────────────────────────────────────────────────────────

import sys
import os
import ctypes
import ctypes.wintypes as wt
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
CMD_LED    = 0x38
CMD_SCHEME = 0x39
CMD_POWER  = 0x36
STATUS_REPORT_TYPE = 34   # b6=0x22


def _make_cmd(cmd: int, param: int) -> bytes:
    checksum = (270 - cmd - param) % 256
    return bytes([0x4B, 0xC4, 0x0B, 0x00, 0x00, 0x03,
                  cmd, 0x20, param, 0x00, checksum, 0xFE]) + bytes(52)


def is_maono_link_running() -> bool:
    import subprocess
    result = subprocess.run(
        ['tasklist', '/FI', 'IMAGENAME eq Maono Link2.0.exe', '/NH'],
        capture_output=True, text=True
    )
    return 'Maono Link2.0.exe' in result.stdout


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
        print(f"ERROR abriendo HID: {ctypes.get_last_error()}")
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


def apply_active_mode(k32, handle, maono_running: bool):
    """Aplica el modo activo, con esquema RGB si Maono Link esta disponible."""
    if COLOR_ACTIVE >= 10 and maono_running:
        # Modo dinamico + esquema RGB (requiere inicializacion de Maono Link)
        send_led(k32, handle, CMD_SCHEME, COLOR_SCHEME)
        time.sleep(0.05)
    send_led(k32, handle, CMD_LED, COLOR_ACTIVE)


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

    maono_running = is_maono_link_running()

    print("=" * 50)
    print("  Maono PD100X - Mute LED Mod v3.0")
    print("=" * 50)
    print(f"  Muteado  -> {muted_label} (idx={COLOR_MUTED})")
    if COLOR_ACTIVE >= 10 and maono_running:
        print(f"  Activo   -> {active_label} + esquema RGB {COLOR_SCHEME}")
    else:
        print(f"  Activo   -> {active_label} (idx={COLOR_ACTIVE})")
    print(f"  Maono Link: {'corriendo' if maono_running else 'no detectado'}")
    print("  Ctrl+C para salir")
    print()

    k32, writer, reader = open_device()
    print("Microfono abierto OK")

    send_led(k32, writer, CMD_POWER, 1)
    time.sleep(0.15)

    last_muted = None
    # Re-check Maono Link status periodically
    maono_check_interval = 10
    last_maono_check = time.time()

    try:
        while True:
            # Periodically re-check if Maono Link started/stopped
            if time.time() - last_maono_check > maono_check_interval:
                new_status = is_maono_link_running()
                if new_status != maono_running:
                    maono_running = new_status
                    print(f"[{time.strftime('%H:%M:%S')}] Maono Link {'detectado' if maono_running else 'cerrado'}")
                    last_muted = None  # force LED refresh
                last_maono_check = time.time()

            muted = read_mute_state(reader)
            if muted is None:
                continue
            if muted != last_muted:
                last_muted = muted
                if muted:
                    send_led(k32, writer, CMD_LED, COLOR_MUTED)
                else:
                    apply_active_mode(k32, writer, maono_running)
                label = muted_label if muted else active_label
                print(f"[{time.strftime('%H:%M:%S')}] {'MUTEADO' if muted else 'ACTIVO '} -> {label}")

    except KeyboardInterrupt:
        print("\nSaliendo...")
        apply_active_mode(k32, writer, maono_running)

    finally:
        reader.close()
        ctypes.windll.kernel32.CloseHandle(writer)
        print("Listo.")


if __name__ == "__main__":
    main()
