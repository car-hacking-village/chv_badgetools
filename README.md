# CHV Badge Tools

Host-side CAN utilities for the **DEF CON 34 Car Hacking Village CTF** badge.

Provides `chv-candump`, `chv-cansend`, and a `python-can` interface plugin (`-i chv`) so you can use standard CAN tools and scripts with the badge over USB — on both **macOS and Linux**, with full **CAN FD** support.

---

## Requirements

- Python 3.8 or newer
- The CHV badge connected via USB

---

## Installation

```bash
git clone https://github.com/CarHackingVillage/chv-badgetools.git
cd chv-badgetools
pip install .
```

> **Tip:** Use a virtual environment to keep your system Python clean:
> ```bash
> python3 -m venv .venv && source .venv/bin/activate
> pip install .
> ```

### Linux — serial port permissions

On Linux the badge enumerates as `/dev/ttyACM0`. Add yourself to the `dialout` group so you can open it without `sudo`:

```bash
sudo usermod -a -G dialout $USER
```

Log out and back in (or run `newgrp dialout` in the current shell) for the change to take effect.

---

## Finding your badge

Plug in the badge and run:

```bash
chv-find
```

This prints the serial port path (`/dev/tty.usbmodem103` on macOS, `/dev/ttyACM0` on Linux). All other commands accept this path as the first argument, or find it automatically when omitted.

---

## Quick start

```bash
# Monitor all CAN traffic
chv-candump

# Monitor traffic on a specific port
chv-candump /dev/tty.usbmodem103

# Send a frame
chv-cansend 7E0#2701000000000000

# Send a frame (explicit port)
chv-cansend /dev/tty.usbmodem103 7E0#2701000000000000
```

---

## Commands

### `chv-candump`

Prints all CAN traffic from the badge in real time.

```
usage: chv-candump [-h] [-b BPS] [--id HEX_ID] [port]

positional arguments:
  port               Serial port (e.g. /dev/tty.usbmodem103). Omit to auto-
                     detect.

options:
  -h, --help         show this help message and exit
  -b, --bitrate BPS  CAN bitrate in bits/s (default: 500000)
  --id HEX_ID        Only show frames from this arbitration ID (hex, e.g. 7E8)
```

**Example output:**

```
  /dev/tty.usbmodem103  [500k]  — Ctrl+C to stop

  1720123456.789012       7E8  [ 4]  67 01 AB CD
  1720123456.792001       7FF  [40]  66 6C 61 67 7B ...
  1720123456.795330 FD  0ACCE55  [19]  4D 41 47 49 43 78 46 0D 38 ...
```

Frames marked `FD` are CAN FD frames (payload > 8 bytes or transmitted in FD mode).

---

### `chv-cansend`

Sends a single CAN frame. The frame format is `ID#DATA` in hex, matching the `cansend` convention from Linux `can-utils`.

```
usage: chv-cansend [-h] [-b BPS] [--fd] [port] frame

positional arguments:
  port               Serial port (e.g. /dev/tty.usbmodem103). Omit to auto-
                     detect.
  frame              Frame in ID#DATA format (hex). E.g. 7E0#2701000000000000

options:
  -h, --help         show this help message and exit
  -b, --bitrate BPS  CAN bitrate in bits/s (default: 500000)
  --fd               Send as CAN FD frame
```

**Examples:**

```bash
# UDS Security Access — request seed
chv-cansend 7E0#2701000000000000

# UDS Read Data By Identifier — read VIN
chv-cansend 7E0#22F190000000000

# Extended CAN ID (automatically detected when ID > 0x7FF)
chv-cansend 0005EED#00

# Send a CAN FD frame
chv-cansend 7E0#27360200AABBCCDD --fd
```

---

## python-can integration

`chv-badgetools` registers itself as a `python-can` interface plugin. After installation, any tool that uses `python-can` works with the badge by passing `-i chv`.

### `can.viewer`

```bash
python3 -m can.viewer -i chv -c /dev/tty.usbmodem103 -b 500000

# Auto-detect port
python3 -m can.viewer -i chv -c auto -b 500000
```

### `can.logger`

```bash
python3 -m can.logger -i chv -c /dev/tty.usbmodem103 -b 500000 session.asc
```

### Scripts

Any script written against the `python-can` `Bus` API works with the badge:

```python
import can

bus = can.Bus(interface='chv', channel='/dev/tty.usbmodem103', bitrate=500_000)

# Receive a frame
msg = bus.recv(timeout=2.0)
if msg:
    print(f"{msg.arbitration_id:X}  {msg.data.hex()}")

# Send a frame
bus.send(can.Message(
    arbitration_id=0x7E0,
    data=bytes.fromhex('2701000000000000'),
    is_extended_id=False,
))

bus.shutdown()
```

#### Using `with` / context manager

```python
with can.Bus(interface='chv', channel='auto', bitrate=500_000) as bus:
    for msg in bus:
        print(msg)
```

#### Filters

```python
bus = can.Bus(interface='chv', channel='auto', bitrate=500_000)
bus.set_filters([{"can_id": 0x7E8, "can_mask": 0xFFF, "extended": False}])
```

---

## CAN FD

The badge supports CAN FD frames (payloads up to 64 bytes). CAN FD is handled transparently:

- `chv-candump` marks FD frames with `FD` in the output
- `chv-cansend` accepts `--fd` to transmit an FD frame
- python-can `can.Message` objects with `is_fd=True` are sent as FD frames

```python
bus.send(can.Message(
    arbitration_id=0x7E0,
    data=b'\x36\x01' + shellcode,
    is_fd=True,
    is_extended_id=False,
))
```

---

## Bitrates

The default is **500 kbit/s** (`-b 500000`), which matches the badge.  
Other supported rates: 10k, 20k, 50k, 100k, 125k, 250k, 750k, 1M.

---

## Troubleshooting

**`No CHV badge found`**  
The auto-detection looks for the RP2040 USB vendor ID. Try passing the port explicitly:
```bash
# macOS
chv-candump /dev/tty.usbmodem*

# Linux
chv-candump /dev/ttyACM0
```

**`Permission denied` on Linux**  
You need to be in the `dialout` group — see [Linux permissions](#linux--serial-port-permissions) above.

**No frames appearing in `chv-candump`**  
The badge only mirrors traffic that passes through its CAN bus. Make sure a lesson is active on the badge and that you are sending frames to trigger responses.

**`can.viewer` exits immediately**  
Ensure python-can 4.0 or newer is installed: `pip install --upgrade python-can`.

**Frames appear but data looks wrong**  
Confirm the bitrate matches the badge configuration (default 500k). A mismatch causes garbage data.
