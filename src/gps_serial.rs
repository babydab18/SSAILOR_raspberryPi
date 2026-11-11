use serialport::Error;
use serialport::SerialPort;
use std::io::Read;
use std::io::{self, Write};
use std::path::PathBuf;

#[derive(Debug)]
pub struct SerialReader {
    gps_port: Box<dyn SerialPort>,
    gps_buffer: String,
}

pub fn open_port(port: PathBuf, baud_rate: u32) -> Result<SerialReader, Error> {
    match serialport::new(port.to_string_lossy(), baud_rate)
        .timeout(std::time::Duration::from_millis(100))
        .open()
    {
        Ok(gps_port) => {
            println!("Successfully opened port {}", port.to_string_lossy());
            Ok(SerialReader {
                gps_port,
                gps_buffer: String::new(),
            })
        }
        Err(e) => {
            eprintln!(
                "Failed to open \"{}\". Error: {}",
                port.to_string_lossy(),
                e
            );
            Err(e)
        }
    }
}

impl SerialReader {
    pub fn read_sentences(&mut self) -> io::Result<Vec<String>> {
        let mut serial_buf: Vec<u8> = vec![0; 1024];
        let mut sentences = Vec::new();

        match self.gps_port.read(serial_buf.as_mut_slice()) {
            Ok(t) if t > 0 => {
                let text = String::from_utf8_lossy(&serial_buf[..t]).into_owned();
                self.gps_buffer.push_str(&text);
                // Bound incomplete/noisy input, including base-station binary streams.
                if self.gps_buffer.len() > 16_384 {
                    self.gps_buffer.clear();
                }

                loop {
                    if let Some(start) = self.gps_buffer.find('$') {
                        if let Some(end_pos) = self.gps_buffer[start..].find("\r\n") {
                            let end = start + end_pos + 2;
                            let sentence = self.gps_buffer[start..end].to_string();
                            sentences.push(sentence.clone());

                            // Remove the processed sentence from the buffer
                            self.gps_buffer = self.gps_buffer[end..].to_string();
                        } else {
                            // Partial sentence starting with $, keep from $ onward
                            self.gps_buffer = self.gps_buffer[start..].to_string();
                            break;
                        }
                    } else {
                        // No sentence start found, discard garbage
                        self.gps_buffer.clear();
                        break;
                    }
                }
                Ok(sentences)
            }
            Ok(_) => {
                // No data read
                Ok(sentences)
            }
            Err(ref e) if e.kind() == io::ErrorKind::TimedOut => Ok(sentences),
            Err(e) => {
                // eprintln!("Error reading from port: {:?}", e);
                Err(e)
            }
        }
    }
}

impl Write for SerialReader {
    fn write(&mut self, buf: &[u8]) -> io::Result<usize> {
        self.gps_port.write(buf)
    }

    fn flush(&mut self) -> io::Result<()> {
        self.gps_port.flush()
    }
}
