"""
Wire protocol for the CHV badge slcan serial interface.

Frame formats (all terminated with \\r):
  Classical CAN standard:  t<3-hex-ID><1-DLC><data-hex>
  Classical CAN extended:  T<8-hex-ID><1-DLC><data-hex>
  CAN FD standard:         d<3-hex-ID><2-hex-len><data-hex>
  CAN FD extended:         D<8-hex-ID><2-hex-len><data-hex>

Control commands:
  S6\\r  — set bitrate to 500 kbit/s (S0–S8, see BITRATES)
  O\\r   — open channel
  C\\r   — close channel
  V\\r   — version query
"""

import time
import serial
from serial.tools import list_ports

BITRATES = {
    10_000:  "S0",
    20_000:  "S1",
    50_000:  "S2",
    100_000: "S3",
    125_000: "S4",
    250_000: "S5",
    500_000: "S6",
    750_000: "S7",
    1_000_000: "S8",
}

# RP2040 USB vendor ID used by MicroPython and the CHV badge
_BADGE_VID = 0x2E8A


def find_port():
    """Return the first serial port that looks like a CHV badge, or None."""
    for p in list_ports.comports():
        if p.vid == _BADGE_VID:
            return p.device
    return None


class CHVProtocol:
    def __init__(self, port: str, bitrate: int = 500_000):
        code = BITRATES.get(bitrate, "S6")
        self._ser = serial.Serial(port, 115200, timeout=0.02)
        self._buf = ""
        # Configure and open the CAN channel
        self._ser.write(f"{code}\rO\r".encode())
        self._ser.flush()

    # ------------------------------------------------------------------

    def send(self, arb_id: int, data: bytes, is_fd: bool = False,
             is_extended: bool = None):
        if is_extended is None:
            is_extended = arb_id > 0x7FF
        if is_fd:
            if is_extended:
                frame = f"D{arb_id:08X}{len(data):02X}{data.hex().upper()}"
            else:
                frame = f"d{arb_id:03X}{len(data):02X}{data.hex().upper()}"
        else:
            dlc = min(len(data), 8)
            if is_extended:
                frame = f"T{arb_id:08X}{dlc}{data[:dlc].hex().upper()}"
            else:
                frame = f"t{arb_id:03X}{dlc}{data[:dlc].hex().upper()}"
        self._ser.write(f"{frame}\r".encode())

    def recv(self, timeout: float = 0.1):
        """
        Block up to *timeout* seconds for the next data frame.
        Returns (arb_id, data, is_fd, is_extended) or None on timeout.
        """
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            raw = self._ser.read(128)
            if raw:
                self._buf += raw.decode("ascii", errors="ignore")
            while "\r" in self._buf:
                line, _, self._buf = self._buf.partition("\r")
                line = line.strip()
                if line and line[0] in "TtDd":
                    try:
                        return self._parse(line)
                    except (ValueError, IndexError):
                        pass
        return None

    def close(self):
        try:
            self._ser.write(b"C\r")
            self._ser.flush()
        finally:
            self._ser.close()

    # ------------------------------------------------------------------

    def _parse(self, line: str):
        typ = line[0]
        is_fd  = typ in "Dd"
        is_ext = typ in "TD"
        if is_ext:
            arb_id = int(line[1:9], 16)
            rest   = line[9:]
        else:
            arb_id = int(line[1:4], 16)
            rest   = line[4:]
        if is_fd:
            length = int(rest[:2], 16)
            data   = bytes.fromhex(rest[2:2 + length * 2])
        else:
            dlc  = int(rest[0])
            data = bytes.fromhex(rest[1:1 + dlc * 2])
        return arb_id, data, is_fd, is_ext
