"""Capture receiver bytes unchanged, including binary RTCM and NMEA text."""
import argparse
from pathlib import Path
import time
import serial

def capture(port, baud, seconds, output):
    if seconds <= 0 or baud <= 0:
        raise ValueError("Duration and baud rate must be positive")
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive on POSIX; Windows serial handles are already exclusive.
    import os
    options = {"exclusive": True} if os.name == "posix" else {}
    with serial.serial_for_url(port, baudrate=baud, timeout=0.1, **options) as receiver:
        with output.open("xb") as recording:
            end = time.monotonic() + seconds
            total = 0
            while time.monotonic() < end:
                data = receiver.read(min(max(receiver.in_waiting, 1), 4096))
                recording.write(data)
                total += len(data)
    return total

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", default="/dev/ttyUSB0")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--seconds", type=float, default=10)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        total = capture(args.port, args.baud, args.seconds, args.output)
    except (OSError, ValueError, serial.SerialException) as error:
        parser.exit(1, f"Capture failed: {error}\n")
    print(f"Saved {total} bytes to {args.output}")

if __name__ == "__main__":
    main()
