# SSAILOR_raspberryPi
GpS/Raspberry PI code

# MAARCO

This is the code for the MAARCO project. It involves reading GPS RTK data from a serial port, displaying it in a terminal UI, and optionally connecting to an NTRIP server for real-time corrections.

We are using a Raspberry Pi 4B as the main hardware platform.

All data is also logged to a file. The file is a CSV, which you can find under `logs/`.

## Project structure

- `src/`: Contains the Rust source code for the project.
- `examples/`: Contains example Python scripts for decoding log files and streaming NMEA data. Also includes some Rust code.
- `logs/`: Directory where CSV log files are stored.
- `field_tests/`: This is where the data from field tests is stored. The data can be decoded using the scripts in `examples/plot_gps_log.py`.

## Support

This guide is written assuming that you are running Linux, or at least [WSL](https://learn.microsoft.com/en-us/windows/wsl/install) (you should get the Ubuntu distribution). 

## How to ssh into the Pi:

First, you should be familiar with `ssh`. See [this guide](https://www.geeksforgeeks.org/linux-unix/ssh-command-in-linux-with-examples/) for a short introduction. Next, you need to make a WiFi hotspot so the Raspberry Pi can connect to it. The Wifi name should be `Witcher`, and the password should be `harshil1234`. Now switch on this WiFi hotspot, and make sure your computer and/or your phone is also connected to it. You should shortly see the IP address of the raspberry pi on the list of connected devices.

So to ssh into the Pi, you would do:

```bash
ssh pi4b@<IP ADDRESS>
```
It will ask you for the password. Enter `emssl_lab`.

## How to run on your computer

Since this project uses both Rust and Python, ensure you have both installed. For python, you need to install [`uv`](https://docs.astral.sh/uv/getting-started/installation/) to manage dependencies.

To install Rust, follow the instructions at [rustup.rs](https://rustup.rs/).

1. Clone the repository:
   ```bash
   git clone https://github.com/harshil21/MAARCO.git && cd MAARCO
   ```

2. Install Python dependencies (this is for the post-processing scripts):
   ```bash
   uv sync
   ```

3. Build the Rust project:
   ```bash
   cargo build --release
   ``` 

## How to run on the Pi:

We want to compile this project and execute that on the Raspberry Pi. So we will actually compile the code on our computer, and then make the Pi use that binary, because compiling directly on the Raspberry Pi can be *very* slow.

So now let's set up a cross-compilation environment on our computer.

You can cross compile via `cargo`:

1. First, install the ARM target. This is the CPU architecture the Raspberry Pi uses:
    ```bash
    rustup target add aarch64-unknown-linux-gnu
    ```
   
2. Next, install the necessary linker (i.e. `gcc`). For Ubuntu based distributions, you can do this via:
    ```bash
    sudo apt-get install build-essential gcc-aarch64-linux-gnu
    ```
3. Now, you can build the project for the Raspberry Pi:
    ```bash
    cargo build --target aarch64-unknown-linux-gnu --release
    ```
4. You should now have a binary located at `target/aarch64-unknown-linux-gnu/release/maarco`. You should copy this binary to the Raspberry Pi, e.g. via
`scp`:
   ```bash
   scp target/aarch64-unknown-linux-gnu/release/maarco pi4b@<RASPBERRY_PI_IP_ADDRESS>:~/
   ```

5. Finally, run the application on the Raspberry Pi:
    ```bash
    ./maarco --ntrip-mount MOUNTPOINT --log-file logs/test_1.csv
    ```

Replace `MOUNTPOINT` with your actual NTRIP mount point
(the list of all NTRIP mount points can be found [here](http://rtk2go.com:2101/SNIP::STATUS)).

You should typically use the `VMAX-LAND-1` mount point. This is located in [Baybrook, NC](http://rtk2go.com:2101/SNIP::BASEandUSERMAP?baseName=VMAX-LAND-1&tk=nFghcsAw9xJ3rpf6qwPE) and is good for testing if you are within 10 miles of that location.

For locations further away, you should choose a mount point closer to your location, otherwise the RTK corrections will not be effective. You can browse the list of mount points in the link above to find one near you. If there are none, you should
set up your own RTK base station (see [Base station setup](#base-station-setup) below).

If you don't have one, you can omit the `--ntrip-mount` argument, and the application will run
without NTRIP support (so you will not get RTK corrections).

### Running without the Pi:

You can also run the application on your computer if you have a GPS device connected via USB or serial port. Just make sure to specify the correct serial port as a command line argument (`--gps-port`) (currently set to `/dev/ttyUSB0`). 

The list of all command line arguments can be checked by running `./maarco --help`.

## Post processing the gps data:

You can run the example Python scripts to post process the GPS data. For example, to plot the 2D, and 3D deviation map from the GPS run:

```bash
uv run --script examples/plot_gps_log.py field_tests/volleyball/12_5_25/perimeter_long_rtk_fixed_gps.csv
```

Or to run a Rust example:

```bash
cargo run --example file_name[no .rs]
```

## Base station setup

TODO!
