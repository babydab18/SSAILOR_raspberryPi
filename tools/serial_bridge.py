"""Expose one GPS serial port on Pi localhost for access through an SSH tunnel.

Run this instead of MAARCO while using a desktop GPS client. Bytes travel unchanged
in both directions, so receiver commands/corrections can be sent by that client.
"""
import argparse
import os
import socket
import serial

def bridge(connection, receiver):
    connection.settimeout(0.1)
    while True:
        data = receiver.read(min(max(receiver.in_waiting, 1), 4096))
        if data:
            connection.sendall(data)
        try:
            data = connection.recv(4096)
        except socket.timeout:
            continue
        if not data:
            return
        receiver.write(data)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", default="/dev/ttyUSB0")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--tcp-port", type=int, default=12345)
    args = parser.parse_args()
    if args.baud <= 0 or not 1 <= args.tcp_port <= 65535:
        parser.error("Use a positive baud rate and TCP port 1-65535")
    options = {"exclusive": True} if os.name == "posix" else {}
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
            server.bind(("127.0.0.1", args.tcp_port))
            server.listen(1)
            print(f"Listening on 127.0.0.1:{args.tcp_port}; connect through SSH.", flush=True)
            while True:
                connection, _ = server.accept()
                with connection:
                    try:
                        with serial.serial_for_url(args.port, baudrate=args.baud, timeout=0.05, **options) as receiver:
                            print("GPS client connected.", flush=True)
                            bridge(connection, receiver)
                    except (OSError, serial.SerialException) as error:
                        print(f"GPS session ended: {error}", flush=True)
                    print("Waiting for another GPS client.", flush=True)
    except KeyboardInterrupt:
        print("Stopped.")
    except OSError as error:
        parser.exit(1, f"Bridge failed: {error}\n")

if __name__ == "__main__":
    main()
