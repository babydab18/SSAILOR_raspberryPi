import socket
import base64

def connect_rtk2go_ntrip(server: str, port: int, mountpoint: str, username: str, password: str):
    """
    Connects to RTK2Go NTRIP caster and yields RTCM data chunks.

    Args:
        server (str): NTRIP caster (e.g., 'rtk2go.com')
        port (int): Caster port (usually 2101)
        mountpoint (str): RTK2Go mountpoint name (case-sensitive)
        username (str): Your RTK2Go email
        password (str): Password (typically 'none')

    Yields:
        bytes: Received RTCM data chunks
    """
    # Prepare HTTP Basic Auth header
    auth_str = f"{username}:{password}"
    auth_b64 = base64.standard_b64encode(auth_str.encode('utf-8')).decode('utf-8')

    # Construct NTRIP GET header
    request_header = (
        f"GET /{mountpoint} HTTP/1.0\r\n"
        "User-Agent: NTRIP PythonClient\r\n"
        "Accept: */*\r\n"
        f"Authorization: Basic {auth_b64}\r\n"
        "Connection: close\r\n\r\n"
    )

    # Create the TCP socket and connect
    sock = socket.create_connection((server, port))
    sock.sendall(request_header.encode('utf-8'))

    # Read and yield RTCM data
    try:
        while True:
            data = sock.recv(4096)  # Adjust buffer size as needed
            if not data:
                break
            yield data
    finally:
        sock.close()

for chunk in connect_rtk2go_ntrip('rtk2go.com', 2101, 'VMAX-LAND-1', 'hoppingturtles@proton.me', 'none'):
    # Do something with RTCM chunk, e.g., send to GNSS receiver
    print(chunk)