use serde::Serialize;
use serialport::Error;
use serialport::TTYPort;
use std::io::{self, BufReader, Read, Write};
use std::path::PathBuf;
use std::time::Duration;

#[derive(Debug, Clone, Serialize)]
#[derive(Default)]
pub struct SensorData {
    #[serde(skip_deserializing)]
    pub timestamp_ns: u64,
    pub time_ms: Option<u32>,
    pub voltage_left: Option<f32>,
    pub current_left_ma: Option<f32>,
    pub voltage_right: Option<f32>,
    pub current_right_ma: Option<f32>,
    pub motor_current_left: Option<f32>,
    pub motor_current_right: Option<f32>,
    pub euler_x: Option<f32>,
    pub euler_y: Option<f32>,
    pub euler_z: Option<f32>,
    pub acc_lin_x: Option<f32>,
    pub acc_lin_y: Option<f32>,
    pub acc_lin_z: Option<f32>,
    pub sonar_mm: Option<f32>,
    pub tof_mm: Option<f32>,
    pub rpm_left: Option<f32>,
    pub rpm_right: Option<f32>,
    pub rotations_left: Option<f32>,
    pub rotations_right: Option<f32>,
}


#[derive(Debug)]
pub struct ArduinoSerialPort {
    reader: BufReader<TTYPort>, // Buffered reader for line-based reads
    buffer: String,
}

pub fn open_port(port: PathBuf) -> Result<ArduinoSerialPort, Error> {
    const BAUD_RATE: u32 = 115200;

    match serialport::new(port.to_string_lossy(), BAUD_RATE)
        .timeout(Duration::from_secs(1)) // 1s timeout for reads
        .open_native()
    {
        Ok(arduino_port) => {
            println!(
                "Successfully opened port {} at {} baud.",
                port.to_string_lossy(),
                BAUD_RATE
            );
            let reader = BufReader::new(arduino_port); // Wrap for buffered line reads
            Ok(ArduinoSerialPort {
                reader,
                buffer: String::new(),
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

impl ArduinoSerialPort {
    pub fn read_data(&mut self) -> Result<Option<SensorData>, Error> {
        // Read available data into buffer
        let mut buf = [0u8; 1024];
        match self.reader.read(&mut buf) {
            Ok(n) if n > 0 => {
                let s = String::from_utf8_lossy(&buf[..n]);
                self.buffer.push_str(&s);
            }
            Ok(_) => {} // EOF or 0 bytes
            Err(ref e) if e.kind() == io::ErrorKind::TimedOut => {}
            Err(e) => return Err(Error::from(e)),
        }

        // Prevent buffer from growing indefinitely if no "Ard" is found
        if self.buffer.len() > 4096 {
            if let Some(idx) = self.buffer.find("Ard") {
                if idx > 0 {
                    self.buffer.drain(..idx);
                }
            } else {
                // Keep last few bytes in case "Ard" is split
                let len = self.buffer.len();
                if len > 3 {
                    self.buffer.drain(..len - 3);
                }
            }
        }

        // Look for "Ard" delimiter
        if let Some(start_idx) = self.buffer.find("Ard") {
            // Discard garbage before first "Ard"
            if start_idx > 0 {
                self.buffer.drain(..start_idx);
            }

            // Now buffer starts with "Ard". Look for the next "Ard".
            // We search from index 3 to skip the first "Ard"
            if let Some(end_idx) = self.buffer[3..].find("Ard") {
                let end_idx = end_idx + 3; // Adjust index relative to buffer start

                // Extract the packet content (between the two "Ard"s)
                let packet_str = self.buffer[3..end_idx].to_string();

                // Remove the processed packet from buffer.
                // We drain up to end_idx, so the next "Ard" becomes the start of the buffer.
                self.buffer.drain(..end_idx);

                // Parse the packet
                return Ok(Some(self.parse_sensor_data(&packet_str)));
            }
        }

        Ok(None)
    }

    fn parse_sensor_data(&self, data: &str) -> SensorData {
        let mut sensor_data = SensorData {
            timestamp_ns: std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .expect("Time went backwards")
                .as_nanos() as u64,
            ..SensorData::default()
        };

        // Remove leading comma if present (common if format is "Ard,val1,val2...")
        let clean_data = data.trim().trim_start_matches(',');

        // Split by comma, trim whitespace, but KEEP empty strings to preserve position
        let parts: Vec<&str> = clean_data.split(',').map(|s| s.trim()).collect();

        // Order: time_ms, voltage_left, current_left_a, voltage_right_a, current_right_a,
        // motor_current_left, motor_current_right, euler_x, euler_y, euler_z, acc_lin_x,
        // acc_lin_y, acc_lin_z, sonar_mm, tof_mm, rpm_left, rpm_right, rotations_left,
        // rotations_right

        if !parts.is_empty() {
            sensor_data.time_ms = parts[0].parse().ok();
        }
        if parts.len() >= 2 {
            sensor_data.voltage_left = parts[1].parse().ok();
        }
        if parts.len() >= 3 {
            sensor_data.current_left_ma = parts[2].parse().ok();
        }
        if parts.len() >= 4 {
            sensor_data.voltage_right = parts[3].parse().ok();
        }
        if parts.len() >= 5 {
            sensor_data.current_right_ma = parts[4].parse().ok();
        }
        if parts.len() >= 6 {
            sensor_data.motor_current_left = parts[5].parse().ok();
        }
        if parts.len() >= 7 {
            sensor_data.motor_current_right = parts[6].parse().ok();
        }
        if parts.len() >= 8 {
            sensor_data.euler_x = parts[7].parse().ok();
        }
        if parts.len() >= 9 {
            sensor_data.euler_y = parts[8].parse().ok();
        }
        if parts.len() >= 10 {
            sensor_data.euler_z = parts[9].parse().ok();
        }
        if parts.len() >= 11 {
            sensor_data.acc_lin_x = parts[10].parse().ok();
        }
        if parts.len() >= 12 {
            sensor_data.acc_lin_y = parts[11].parse().ok();
        }
        if parts.len() >= 13 {
            sensor_data.acc_lin_z = parts[12].parse().ok();
        }
        if parts.len() >= 14 {
            sensor_data.sonar_mm = parts[13].parse().ok();
        }
        if parts.len() >= 15 {
            sensor_data.tof_mm = parts[14].parse().ok();
        }
        if parts.len() >= 16 {
            sensor_data.rpm_left = parts[15].parse().ok();
        }
        if parts.len() >= 17 {
            sensor_data.rpm_right = parts[16].parse().ok();
        }
        if parts.len() >= 18 {
            sensor_data.rotations_left = parts[17].parse().ok();
        }
        if parts.len() >= 19 {
            sensor_data.rotations_right = parts[18].parse().ok();
        }

        sensor_data
    }

    pub fn get_port_mut(&mut self) -> &mut TTYPort {
        self.reader.get_mut()
    }
}

impl Write for ArduinoSerialPort {
    fn write(&mut self, buf: &[u8]) -> io::Result<usize> {
        self.get_port_mut().write(buf)
    }

    fn flush(&mut self) -> io::Result<()> {
        self.get_port_mut().flush()
    }
}
