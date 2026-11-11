use base64::{Engine as _, engine::general_purpose};
use std::io::{Read, Write};
use std::net::TcpStream;

fn connect_rtk2go_ntrip(
    server: &str,
    port: u16,
    mountpoint: &str,
    username: &str,
    password: &str,
) -> std::io::Result<()> {
    // Connect to the RTK2GO NTRIP caster
    let mut stream = TcpStream::connect((server, port))?;

    // Prepare the auth header
    let auth = format!("{}:{}", username, password);
    let auth_b64 = general_purpose::STANDARD.encode(auth);

    // Construct NTRIP request header
    let request = format!(
        "GET /{} HTTP/1.0\r\n\
        User-Agent: NTRIP RustClient\r\n\
        Accept: */*\r\n\
        Authorization: Basic {}\r\n\
        Connection: close\r\n\r\n",
        mountpoint, auth_b64
    );

    stream.write_all(request.as_bytes())?;

    // Read and print incoming RTCM data chunks
    let mut buf = [0u8; 4096];
    loop {
        let n = stream.read(&mut buf)?;
        if n == 0 {
            break;
        }
        // Here you can process or forward the data. We'll just print length for this example:
        println!("Received {} bytes of RTCM data", n);
    }

    Ok(())
}

fn main() {
    // Replace with your RTK2go settings
    let server = "rtk2go.com";
    let port = 2101;
    let mountpoint = "VMAX-LAND-1";
    let username = "hoppingturtles@proton.me";
    let password = "none"; // typically 'none' for RTK2GO

    if let Err(e) = connect_rtk2go_ntrip(server, port, mountpoint, username, password) {
        eprintln!("NTRIP connection failed: {}", e);
    }
}
