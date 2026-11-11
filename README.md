# SSAILOR GPS / RTK

GPS terminal UI, rover correction forwarding, and recordings for SSAILOR.
Derived from [EMSSL-Lab/MAARCO](https://github.com/EMSSL-Lab/MAARCO);
the original MIT license and attribution are retained in `LICENSE`.

## What this application does

- Opens a GPS receiver and parses its NMEA position messages.
- Shows coordinates, satellite count, fix quality (including Fixed/Float RTK),
  dilution of precision, signal information, and correction connection status.
- Optionally receives RTCM3 corrections from an NTRIP caster and forwards complete,
  CRC-validated frames to a rover receiver.
- Writes GPS and correction CSVs. It no longer opens or logs an Arduino port.
- Supplies GPS plotting, raw byte capture, and a localhost serial bridge for a
  desktop GPS application such as PyGPSClient.

**The receiver computes the RTK solution.** This program does not compute it.
The LC29H(BS) is a base receiver and normally emits binary corrections, not the
rover NMEA positions this terminal UI expects. A waiting screen with a BS attached
is not proof that the receiver is broken. Use raw capture or a compatible desktop
GNSS tool to inspect it. This repository does not yet configure survey-in, establish
a base reference position, or publish a base correction stream to an NTRIP caster.

## Build on the Pi

The existing Pi already has Rust. Build in the directory containing this README:

```bash
source "$HOME/.cargo/env"
cargo build --release --locked
./target/release/maarco --help
```

For a fresh Pi, install Git, curl, build-essential, and pkg-config, then install
Rust using https://rustup.rs. The crate uses Rust edition 2024; use a current stable
toolchain compatible with `Cargo.lock`. Python is optional for the Rust application.

## GPS display and recording

Stop other programs using the same GPS serial port first.

```bash
./target/release/maarco --gps-port /dev/ttyUSB0 --gps-baud 115200 --duration 30
```

Omit `--duration` for continuous operation; Ctrl+C stops it. A timed run flushes
the final accumulated GPS epoch. During normal operation each completed epoch and
each correction frame is flushed as it is recorded. Abrupt termination can omit
the final in-progress epoch.

Logs default to `logs/TIMESTAMP_gps.csv` and `logs/TIMESTAMP_rtcm.csv`.
`--log-file logs/test.csv` produces `test_gps.csv` and `test_rtcm.csv`.
Existing log names are rejected rather than overwritten. No `_sensor.csv` is created.
GPS altitude is in `altitude_m`; speed is recorded/displayed in knots.
Missing values display as N/A, and displayed position values are the last received
values, not a guarantee of a fresh fix. No NMEA positions means no GPS rows.

## Rover corrections through NTRIP

Choose a compatible nearby base/mountpoint. The following values are placeholders;
use the caster credentials assigned to you. They are separate from GitHub credentials.

```bash
export NTRIP_USER='YOUR_CASTER_USERNAME'
read -rs -p 'NTRIP password: ' NTRIP_PASSWORD; echo
export NTRIP_PASSWORD
./target/release/maarco --gps-port /dev/ttyUSB0 --gps-baud 115200 \
  --ntrip-host YOUR_CASTER_HOST --ntrip-port 2101 --ntrip-mount YOUR_MOUNTPOINT
unset NTRIP_PASSWORD
```

`--ntrip-user` can replace `NTRIP_USER`. The password is read only from the
environment. Without `--ntrip-mount`, no correction connection is started.
The client retries failed/closed connections after five seconds and shows the
status even without GPS positions. It supports plain TCP NTRIP v1 / HTTP identity
responses; TLS, chunked transfer encoding, and sending rover GGA to VRS services
are not implemented. Use a compatible fixed-base stream. Plain TCP does not encrypt
caster credentials; use a trusted connection or an appropriate tunnel.

## Optional Python GPS tools

Python 3.11+ is supported. Install uv using https://docs.astral.sh/uv/, then:

```bash
uv sync --locked
uv run python examples/plot_gps_log.py logs/YOUR_RUN_gps.csv
uv run python examples/plot_gps_log.py logs/YOUR_RUN_gps.csv --kml exports/track.kml --no-show
uv run python tools/capture_serial.py --port /dev/ttyUSB0 --seconds 10 --output logs/base-sample.bin
```

The plotting script accepts both current `altitude_m` and historical `altitude`
columns. Plot windows require a graphical session; `--no-show` KML export, capture, and the bridge work over SSH.
Capture preserves all bytes, including RTCM and proprietary status text. Use a new
output filename for each recording.

For the optional desktop UI, `uv sync --locked --extra desktop`, then
`uv run --extra desktop pygpsclient`. On Raspberry Pi OS, the desktop UI may also
need the OS Tk package (`python3-tk`) and a graphical session.

## View the Pi's receiver from a laptop

1. On the Pi, stop MAARCO/capture/other GPS readers and run:
   `uv run python tools/serial_bridge.py --port /dev/ttyUSB0 --baud 115200`.
2. On the laptop, open an SSH tunnel and leave it running:
   `ssh -N -L 12345:127.0.0.1:12345 ssailor@PI_IP`.
3. Open PyGPSClient on the laptop and select a TCP socket connection to
   `127.0.0.1`, port `12345`.

The bridge binds only to Pi localhost, supports one client at a time, and transports
raw bytes in both directions. It does not store SSH passwords or configure the receiver.
While the bridge is running, do not start another program on the same serial device.

## Project layout

- `src/`: GPS-only Rust runtime, terminal UI, NTRIP, RTCM framing, and CSV logging.
- `examples/plot_gps_log.py`: GPS CSV plots and KML export.
- `tools/`: raw capture and SSH-tunnel-compatible serial bridge.
- `tests/`: Python regression tests; Rust tests live beside the code.
- `docs/PI_TRANSFER.md`: laptop-to-Pi copy and build instructions.
- `scripts/package_pi.py`: makes the source-only transfer archive.
- `archive/`: retired motor/Arduino examples, old experiments, and historical data.
  These are not compiled or included in the Pi transfer package.

## Validation

```bash
cargo test --locked --all-targets
uv run --locked python -m unittest discover -s tests -v
python scripts/package_pi.py
```

Tests cover a real captured RTCM frame, fragmentation/coalescing, bad checksums,
NTRIP headers/EOF with a local mock caster, GPS waiting display, log output,
altitude compatibility, recording preservation, and binary serial bridging.
Real receiver, antenna, and RTK Fixed validation must still be done on the Pi outdoors.
