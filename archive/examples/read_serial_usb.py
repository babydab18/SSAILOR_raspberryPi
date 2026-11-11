import serial
import time
# -------------------- CONFIG --------------------
SERIAL_PORT = '/dev/ttyACM0'       # Change to your port (e.g., '/dev/ttyUSB0' on Linux)
BAUD_RATE = 115200
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
                # Arduino sends: dir,rotations,rpm,status,distance_mm,signal
                parts = line.split(',')
                if len(parts) == 6:
                    motor_dir = int(parts[0])
                    rotations = float(parts[1])
                    rpm = float(parts[2])
                    tof_status = int(parts[3])
                    distance_mm = int(parts[4])
                    signal = int(parts[5])
                    print(f"Dir: {motor_dir}, Rot: {rotations:.2f}, RPM: {rpm:.2f}, "
                          f"ToF Status: {tof_status}, Distance: {distance_mm} mm, Signal: {signal}")
            except ValueError:
                print(f"Bad data: {line}")  # handle parse errors
except KeyboardInterrupt:
    print("Exiting...")
finally:
    ser.close()
