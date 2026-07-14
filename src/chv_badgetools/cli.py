"""
Command-line tools:
  chv-candump  — print all traffic from the badge CAN bus
  chv-cansend  — transmit a single CAN frame
  chv-find     — print the auto-detected badge serial port
"""

import argparse
import sys
import time

from .protocol import CHVProtocol, BITRATES, find_port


# ── shared argument helpers ────────────────────────────────────────────────────

def _add_port(p: argparse.ArgumentParser):
    p.add_argument(
        "port",
        nargs="?",
        default="auto",
        help="Serial port (e.g. /dev/tty.usbmodem103).  Omit to auto-detect.",
    )

def _add_bitrate(p: argparse.ArgumentParser):
    p.add_argument(
        "-b", "--bitrate",
        type=int,
        default=500_000,
        metavar="BPS",
        help="CAN bitrate in bits/s (default: 500000)",
    )

def _resolve_port(args) -> str:
    if args.port == "auto":
        port = find_port()
        if port is None:
            print("error: CHV badge not found — connect the badge or pass the port explicitly.", file=sys.stderr)
            sys.exit(1)
        print(f"[*] Badge found at {port}")
        return port
    return args.port


# ── chv-candump ────────────────────────────────────────────────────────────────

def candump():
    p = argparse.ArgumentParser(
        prog="chv-candump",
        description="Print all CAN traffic from the CHV badge.",
    )
    _add_port(p)
    _add_bitrate(p)
    p.add_argument(
        "--id", dest="filter_id", type=lambda x: int(x, 16), default=None,
        metavar="HEX_ID",
        help="Only show frames from this arbitration ID (hex, e.g. 7E8)",
    )
    args = p.parse_args()
    port = _resolve_port(args)

    proto = CHVProtocol(port, args.bitrate)
    print(f"  {port}  [{args.bitrate // 1000}k]  — Ctrl+C to stop\n")

    try:
        while True:
            frame = proto.recv(timeout=0.05)
            if frame is None:
                continue
            arb_id, data, is_fd, is_ext = frame
            if args.filter_id is not None and arb_id != args.filter_id:
                continue
            ts     = time.time()
            fd_tag = " FD" if is_fd else "   "
            id_str = f"{arb_id:08X}" if is_ext else f"     {arb_id:03X}"
            print(f"  {ts:.6f}{fd_tag}  {id_str}  [{len(data):2d}]  {data.hex(' ').upper()}")
    except KeyboardInterrupt:
        print("\n[*] Stopped.")
        proto.close()


# ── chv-cansend ────────────────────────────────────────────────────────────────

def cansend():
    p = argparse.ArgumentParser(
        prog="chv-cansend",
        description="Send a single CAN frame to the badge.",
        epilog="Examples:\n"
               "  chv-cansend 7E0#2701000000000000\n"
               "  chv-cansend /dev/ttyACM0 7E0#2701000000000000\n"
               "  chv-cansend 0ACCE55#01\n",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    _add_port(p)
    _add_bitrate(p)
    p.add_argument(
        "frame",
        help="Frame in ID#DATA format (hex).  E.g. 7E0#2701000000000000",
    )
    p.add_argument(
        "--fd", action="store_true",
        help="Send as CAN FD frame",
    )
    args = p.parse_args()

    # Allow 'chv-cansend FRAME' (no port) by detecting if the first positional
    # looks like a frame rather than a port path.
    if "#" in args.port:
        args.frame = args.port
        args.port  = "auto"

    port = _resolve_port(args)

    id_str, _, data_str = args.frame.partition("#")
    arb_id = int(id_str, 16)
    data   = bytes.fromhex(data_str) if data_str else b""

    proto = CHVProtocol(port, args.bitrate)
    proto.send(arb_id, data, is_fd=args.fd)
    proto.close()
    print(f"[+] Sent  {arb_id:X}#{data.hex().upper()}")


# ── chv-find ───────────────────────────────────────────────────────────────────

def find_badge():
    port = find_port()
    if port:
        print(port)
    else:
        print("No CHV badge found.", file=sys.stderr)
        sys.exit(1)
