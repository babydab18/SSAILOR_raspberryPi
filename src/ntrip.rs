use base64::{Engine as _, engine::general_purpose};
use std::io::{self, BufRead, BufReader, Read, Write};
use std::net::{TcpStream, ToSocketAddrs};
use std::sync::mpsc::SyncSender;
use std::time::Duration;

pub struct Config {
    pub host: String,
    pub port: u16,
    pub mountpoint: String,
    pub username: String,
    pub password: String,
}

impl Config {
    pub fn validate(&self) -> io::Result<()> {
        if self.host.is_empty()
            || self.mountpoint.is_empty()
            || self.host.chars().any(char::is_whitespace)
            || self.host.contains("://")
            || self
                .mountpoint
                .chars()
                .any(|c| c.is_whitespace() || c.is_control())
            || self.username.contains(':')
        {
            return Err(io::Error::new(
                io::ErrorKind::InvalidInput,
                "Use a hostname, a nonempty mountpoint without spaces, and a username without ':'",
            ));
        }
        Ok(())
    }
}

pub enum Message {
    Status(String),
    Rtcm(Vec<u8>),
}

// Bound the response header; malformed servers cannot grow memory without limit.
fn line<R: BufRead>(reader: &mut R) -> io::Result<String> {
    let mut bytes = Vec::new();
    let count = reader.take(8193).read_until(b'\n', &mut bytes)?;
    if count == 0 || count > 8192 || !bytes.ends_with(b"\n") {
        return Err(io::Error::new(
            io::ErrorKind::InvalidData,
            "Invalid NTRIP response header",
        ));
    }
    String::from_utf8(bytes)
        .map_err(|_| io::Error::new(io::ErrorKind::InvalidData, "Non-text NTRIP header"))
}

fn read_response<R: BufRead>(reader: &mut R) -> io::Result<()> {
    let status = line(reader)?;
    let parts: Vec<_> = status.split_whitespace().collect();
    let protocol = parts.first().copied().unwrap_or("");
    let code = parts.get(1).copied().unwrap_or("");
    if protocol == "SOURCETABLE" {
        return Err(io::Error::other(
            "Mountpoint not found (sourcetable returned)",
        ));
    }
    if code == "401" || code == "403" {
        return Err(io::Error::other(
            "NTRIP authentication denied; check NTRIP_USER and NTRIP_PASSWORD",
        ));
    }
    if code == "404" {
        return Err(io::Error::other("NTRIP mountpoint not found"));
    }
    if code != "200" || !(protocol == "ICY" || protocol.starts_with("HTTP/1.")) {
        return Err(io::Error::other("Unsupported NTRIP response"));
    }
    // NTRIP v1 ICY is followed directly by binary data. HTTP has a header block.
    if protocol != "ICY" {
        let mut total = status.len();
        loop {
            let header = line(reader)?;
            total += header.len();
            if total > 32_768 {
                return Err(io::Error::other("NTRIP response headers too large"));
            }
            if header.trim().is_empty() {
                break;
            }
            let lower = header.to_ascii_lowercase();
            if lower.starts_with("transfer-encoding:") && !lower.trim_end().ends_with("identity") {
                return Err(io::Error::other(
                    "Chunked/compressed NTRIP transport is not supported",
                ));
            }
            if lower.starts_with("content-type:") && lower.contains("sourcetable") {
                return Err(io::Error::other(
                    "Mountpoint not found (sourcetable returned)",
                ));
            }
        }
    }
    Ok(())
}

fn session(config: &Config, tx: &SyncSender<Message>) -> io::Result<()> {
    let mut connection = None;
    for address in (config.host.as_str(), config.port).to_socket_addrs()? {
        if let Ok(stream) = TcpStream::connect_timeout(&address, Duration::from_secs(10)) {
            connection = Some(stream);
            break;
        }
    }
    let mut stream =
        connection.ok_or_else(|| io::Error::other("Cannot connect to NTRIP caster"))?;
    stream.set_read_timeout(Some(Duration::from_secs(15)))?;
    stream.set_write_timeout(Some(Duration::from_secs(10)))?;
    let auth = if config.username.is_empty() && config.password.is_empty() {
        String::new()
    } else {
        format!(
            "Authorization: Basic {}\r\n",
            general_purpose::STANDARD.encode(format!("{}:{}", config.username, config.password))
        )
    };
    write!(
        stream,
        "GET /{} HTTP/1.0\r\nHost: {}:{}\r\nUser-Agent: NTRIP SSAILOR/0.1\r\nAccept: */*\r\n{}Connection: close\r\n\r\n",
        config.mountpoint.trim_start_matches('/'),
        config.host,
        config.port,
        auth
    )?;
    let mut reader = BufReader::new(stream);
    read_response(&mut reader)?;
    let mut decoder = crate::rtcm::Decoder::default();
    let mut buffer = [0; 4096];
    loop {
        let count = reader.read(&mut buffer)?;
        if count == 0 {
            return Err(io::Error::new(
                io::ErrorKind::UnexpectedEof,
                "Correction stream closed",
            ));
        }
        for frame in decoder.push(&buffer[..count]) {
            tx.send(Message::Rtcm(frame))
                .map_err(|_| io::Error::new(io::ErrorKind::BrokenPipe, "Application stopped"))?;
        }
    }
}

pub fn run(config: Config, tx: SyncSender<Message>) {
    loop {
        if tx
            .send(Message::Status("Connecting to correction service".into()))
            .is_err()
        {
            return;
        }
        if let Err(error) = session(&config, &tx) {
            if tx
                .send(Message::Status(format!("{error}; retrying in 5 seconds")))
                .is_err()
            {
                return;
            }
        }
        std::thread::sleep(Duration::from_secs(5));
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::Cursor;
    #[test]
    fn preserves_binary_body_after_http_and_icy_headers() {
        for header in [
            b"ICY 200 OK\r\n".as_slice(),
            b"HTTP/1.1 200 OK\r\nContent-Type: gnss/data\r\n\r\n".as_slice(),
        ] {
            let mut response = header.to_vec();
            response.extend(crate::rtcm::tests::FRAME_1005);
            let mut reader = BufReader::new(Cursor::new(response));
            read_response(&mut reader).unwrap();
            let mut body = Vec::new();
            reader.read_to_end(&mut body).unwrap();
            assert_eq!(body, crate::rtcm::tests::FRAME_1005);
        }
    }
    #[test]
    fn rejects_auth_errors_sourcetables_and_unsupported_encoding() {
        for response in [
            "HTTP/1.1 401 Unauthorized\r\n",
            "SOURCETABLE 200 OK\r\n",
            "HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n",
            "HTTP/1.1 200 OK\r\nContent-Type: gnss/sourcetable\r\n\r\n",
        ] {
            assert!(read_response(&mut Cursor::new(response)).is_err());
        }
    }
    #[test]
    fn local_caster_delivers_split_frames_and_reports_eof() {
        use std::net::TcpListener;
        let listener = TcpListener::bind("127.0.0.1:0").unwrap();
        let port = listener.local_addr().unwrap().port();
        let server = std::thread::spawn(move || {
            let (mut socket, _) = listener.accept().unwrap();
            socket
                .set_read_timeout(Some(Duration::from_secs(3)))
                .unwrap();
            let mut request = BufReader::new(socket.try_clone().unwrap());
            assert!(
                line(&mut request)
                    .unwrap()
                    .starts_with("GET /TEST HTTP/1.0")
            );
            while !line(&mut request).unwrap().trim().is_empty() {}
            socket.write_all(b"HTTP/1.0 200 OK\r\n\r\n").unwrap();
            socket
                .write_all(&crate::rtcm::tests::FRAME_1005[..10])
                .unwrap();
            socket
                .write_all(&crate::rtcm::tests::FRAME_1005[10..])
                .unwrap();
        });
        let config = Config {
            host: "127.0.0.1".into(),
            port,
            mountpoint: "TEST".into(),
            username: String::new(),
            password: String::new(),
        };
        let (tx, rx) = std::sync::mpsc::sync_channel(8);
        assert_eq!(
            session(&config, &tx).unwrap_err().kind(),
            io::ErrorKind::UnexpectedEof
        );
        match rx.recv_timeout(Duration::from_secs(1)).unwrap() {
            Message::Rtcm(frame) => assert_eq!(frame, crate::rtcm::tests::FRAME_1005),
            _ => panic!("Expected a correction frame"),
        }
        server.join().unwrap();
    }
}
