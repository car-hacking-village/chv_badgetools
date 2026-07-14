"""
python-can BusABC interface for the CHV badge.

Registered as the 'chv' interface via the python_can.interface entry point,
so standard python-can tooling works unchanged:

    python3 -m can.viewer -i chv -c /dev/tty.usbmodem103 -b 500000
    bus = can.Bus(interface='chv', channel='/dev/tty.usbmodem103')
"""

import time
from typing import Optional, Tuple

import can

from .protocol import CHVProtocol, BITRATES, find_port


class CHVBus(can.BusABC):
    """
    python-can Bus backed by the CHV badge slcan serial protocol.

    Parameters
    ----------
    channel : str
        Serial port path, e.g. '/dev/tty.usbmodem103' or '/dev/ttyACM0'.
        Pass 'auto' to let the driver find the badge automatically.
    bitrate : int
        CAN bitrate in bits/s.  Supported: 10k, 20k, 50k, 100k, 125k,
        250k, 500k (default), 750k, 1M.
    """

    def __init__(self, channel: str, bitrate: int = 500_000, **kwargs):
        if channel == "auto":
            channel = find_port()
            if channel is None:
                raise can.CanInitializationError(
                    "CHV badge not found — connect the badge and try again, "
                    "or supply the port explicitly."
                )
        super().__init__(channel, bitrate=bitrate, **kwargs)
        self._proto = CHVProtocol(channel, bitrate)

    # ------------------------------------------------------------------
    # python-can BusABC interface
    # ------------------------------------------------------------------

    def send(self, msg: can.Message, timeout: Optional[float] = None):
        self._proto.send(
            msg.arbitration_id,
            bytes(msg.data),
            is_fd=msg.is_fd,
            is_extended=msg.is_extended_id,
        )

    def _recv_internal(
        self, timeout: Optional[float]
    ) -> Tuple[Optional[can.Message], bool]:
        frame = self._proto.recv(timeout if timeout is not None else 0.1)
        if frame is None:
            return None, False
        arb_id, data, is_fd, is_ext = frame
        msg = can.Message(
            timestamp=time.time(),
            arbitration_id=arb_id,
            is_extended_id=is_ext,
            is_fd=is_fd,
            data=data,
            check=False,
        )
        return msg, False

    def shutdown(self):
        self._proto.close()
