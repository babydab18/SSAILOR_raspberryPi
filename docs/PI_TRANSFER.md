# Copy the trimmed GPS project to the Pi

The package contains source, not a Windows executable or a Pi binary.
It installs alongside `~/MAARCO` so the current working installation remains available.
The package intentionally omits `.git`, `archive/`, recordings, build artifacts,
credentials, and virtual environments. It does not update GitHub automatically.

## 1. On the laptop, in PowerShell

```powershell
cd C:\Users\ranvi\SSAILOR_raspberryPi
python scripts/package_pi.py
scp .\dist\ssailor-gps-pi.tar.gz .\dist\ssailor-gps-pi.tar.gz.sha256 ssailor@PI_IP:~/
ssh ssailor@PI_IP
```

Replace `PI_IP` with the Pi's current address (`hostname -I` on the Pi).
Use the Pi account password for SCP/SSH, not a GitHub token.

## 2. On the Pi, in that SSH session

Run one command at a time. If a command fails, stop and inspect the error.

```bash
cd ~
sha256sum -c ssailor-gps-pi.tar.gz.sha256
```

The checksum should say `OK`. This is a new destination; if `~/SSAILOR_gps`
already exists, keep it or rename it before extracting. The following command
refuses to overlay an existing directory:

```bash
if [ -e "$HOME/SSAILOR_gps" ]; then echo 'SSAILOR_gps already exists; stop here.'; else tar -xzf ssailor-gps-pi.tar.gz; fi
```

After successful extraction:

```bash
cd ~/SSAILOR_gps
source "$HOME/.cargo/env"
cargo test --locked --all-targets
cargo build --release --locked
./target/release/maarco --help
```

Only after stopping any other program using the GPS port:

```bash
./target/release/maarco --gps-port /dev/ttyUSB0 --gps-baud 115200 --duration 30
```

Expect no Arduino-port error. A rover that emits NMEA should populate coordinates;
an LC29H(BS) binary correction stream can leave the position UI waiting. See the
README for raw capture and desktop GPS inspection. The application does not
configure base survey-in or turn a base-only receiver into a rover.

## Return to the previous application

Stop the new application, then use the existing binary in `~/MAARCO/target/release/maarco`.
The transfer does not change that directory, the receiver settings, system services,
or the Pi's network configuration.
