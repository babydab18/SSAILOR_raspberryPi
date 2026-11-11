# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "paramiko",
# ]
# ///
import paramiko
import socket
import threading
import time
import sys
import select

# Configuration - customize these
PI_IP = '10.140.80.249'  # Raspberry Pi's IP address
PI_USERNAME = 'pizero1'       # Default username
PI_PASSWORD = 'emssl_lab'  # Replace with your password (or use key-based auth)
SERIAL_DEVICE = '/dev/serial0'  # Serial port on Pi
BAUD_RATE = 115200         # Baud rate for your sensors
LOCAL_HOST = '127.0.0.1'  # Localhost for security
LOCAL_PORT = 12345       # Port for local TCP server (change if needed)


def configure_serial(ssh):
    config_cmd = f'stty -F {SERIAL_DEVICE} {BAUD_RATE} raw -echo'
    stdin, stdout, stderr = ssh.exec_command(config_cmd)
    error = stderr.read().decode()
    if error:
        print(f"Error configuring serial: {error}")
        sys.exit(1)
    print("Serial port configured.")

def start_pi_channels(ssh):
    # Reader channel: cat from serial
    read_cmd = f'cat {SERIAL_DEVICE}'
    read_stdin, read_stdout, read_stderr = ssh.exec_command(read_cmd)
    
    # Writer channel: cat to serial
    write_cmd = f'cat > {SERIAL_DEVICE}'
    write_stdin, write_stdout, write_stderr = ssh.exec_command(write_cmd)
    
    return read_stdout, write_stdin

def forward_to_client(read_stdout, client_sock, stop_event):
    while not stop_event.is_set():
        if read_stdout.channel.recv_ready():
            data = read_stdout.read(1024)
            if data:
                try:
                    client_sock.sendall(data)
                except:
                    stop_event.set()
                    break
        time.sleep(0.01)

def forward_from_client(write_stdin, client_sock, stop_event):
    while not stop_event.is_set():
        r, _, _ = select.select([client_sock], [], [], 0.1)
        if r:
            data = client_sock.recv(1024)
            print(f"Received {data!r} from pygpsclient, forwarding to Pi.")
            if not data:
                stop_event.set()
                break
            write_stdin.write(data)
            write_stdin.flush()

def proxy_serial_to_tcp():
    global stop_event
    stop_event = threading.Event()
    
    # SSH connection to Pi
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(PI_IP, username=PI_USERNAME, password=PI_PASSWORD)
    print("Connected to Raspberry Pi via SSH.")
    
    configure_serial(ssh)
    read_stdout, write_stdin = start_pi_channels(ssh)
    
    # Start local TCP server
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.bind((LOCAL_HOST, LOCAL_PORT))
    server_sock.listen(2)  # Accept one client
    print(f"Local TCP server listening on {LOCAL_HOST}:{LOCAL_PORT}. Connect with PyGPSClient...")
    
    try:
        client_sock, addr = server_sock.accept()
        print(f"Client connected from {addr}. Proxying bidirectional data...")
        
        # Start forwarding threads
        to_client_thread = threading.Thread(target=forward_to_client, args=(read_stdout, client_sock, stop_event))
        from_client_thread = threading.Thread(target=forward_from_client, args=(write_stdin, client_sock, stop_event))
        
        to_client_thread.start()
        from_client_thread.start()
        
        # Wait for stop
        to_client_thread.join()
        from_client_thread.join()
        
    except KeyboardInterrupt:
        stop_event.set()
        print("\nStopping...")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        stop_event.set()
        client_sock.close() if 'client_sock' in locals() else None
        server_sock.close()
        read_stdout.channel.close()
        write_stdin.channel.close()
        ssh.close()
        print("Connections closed.")

if __name__ == "__main__":
    proxy_serial_to_tcp()