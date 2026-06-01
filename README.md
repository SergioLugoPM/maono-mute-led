# Maono PD100X — Mute LED Mod

Cambia el color del LED del microfono Maono PD100X segun el estado de mute del **boton fisico**.

- Muteado  → 🟠 Naranja
- Activo   → 🟢 Verde

## Requisitos

```
pip install hidapi pycaw comtypes
```

Python 3.11+ recomendado.

## Uso

1. Cierra **Maono Link** (necesita acceso exclusivo al HID)
2. Ejecuta:
   ```
   python maono_mute_led.py
   ```
3. Presiona `Ctrl+C` para salir (restaura LED verde)

## Autostart en Windows

Se puede configurar con el Programador de tareas:

```powershell
$pythonw = "C:\Users\serch\AppData\Local\Programs\Python\Python311\pythonw.exe"
$action   = New-ScheduledTaskAction -Execute $pythonw -Argument '"C:\ruta\maono_mute_led.py"'
$trigger  = New-ScheduledTaskTrigger -AtLogOn
$trigger.Delay = "PT8S"
$settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit 0
Register-ScheduledTask -TaskName "Maono Mute LED Mod" -Action $action -Trigger $trigger -Settings $settings
```

El log se guarda en `maono_mute_led.log` junto al script.

## Protocolo HID (PD100X)

Descubierto por ingenieria inversa de Maono Link 3.8.12.

**VID:** `0x352F` | **PID:** `0x0108` | **Interface:** MI_03 (HID Consumer Controls)

### Comando LED (Output Report ID 0x4B)

```
[0x4B, 0xC4, 0x0B, 0x00, 0x00, 0x03, CMD, 0x20, PARAM, 0x00, (270-CMD-PARAM)%256, 0xFE, ...zeros x52]
```

| CMD | Funcion | PARAM |
|-----|---------|-------|
| `0x38` | Color / modo LED | ver tabla abajo |
| `0x36` | RGB ON/OFF | 0=off, 1=on |

**Colores (CMD=0x38):**

| PARAM | Color (Static) | PARAM | Color (Pulse) |
|-------|---------------|-------|--------------|
| 0 | Naranja | 5 | Naranja pulse |
| 1 | Verde | 6 | Verde pulse |
| 2 | Teal/Cyan | 7 | Teal pulse |
| 3 | Morado | 8 | Morado pulse |
| 4 | Rainbow | 9 | Rainbow pulse |

### Estado de mute (Input Report)

El mic envia un reporte de estado cada ~650ms:

```
[0x4B, 0xC4, 0x0B, 0, 0, 3, 0x22, 0x20, MUTE, 0, ...]
```

`MUTE = 1` → muteado, `MUTE = 0` → activo.

### Apertura del dispositivo

Requiere leer algunos input reports antes de enviar comandos (para despertar la comunicacion USB):

```python
reader = hid.device()
reader.open_path(path)  # lee en background

writer = k32.CreateFileA(path, GENERIC_READ|GENERIC_WRITE,
                          FILE_SHARE_READ|FILE_SHARE_WRITE,
                          None, OPEN_EXISTING, FILE_FLAG_OVERLAPPED, None)
```

Los writes usan overlapped I/O (OVERLAPPED structure con evento).
