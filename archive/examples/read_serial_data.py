import serial
import time

# -------------------- CONFIG --------------------
SERIAL_PORT = '/dev/ttyACM0'       # Change to your port (e.g., '/dev/ttyUSB0' on Linux)
BAUD_RATE = 9600
TIMEOUT = 1                # seconds
# -------------------- OPEN SERIAL --------------------
try:
    ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=TIMEOUT)
    print(f"Connected to {SERIAL_PORT} at {BAUD_RATE} baud.")
    time.sleep(2)  # wait for Arduino reset
except Exception as e:
    print(f"Error opening serial port: {e}")
    exit()
# -------------------- READ LOOP --------------------
try:
    while True:
        line = ser.readline().decode('utf-8').strip()  # Read a line from serial
        if line:
            try:
                print(line)
            except ValueError:
                print(f"Bad data: {line}")  # handle parse errors
except KeyboardInterrupt:
    print("Exiting...")
finally:
    ser.close()