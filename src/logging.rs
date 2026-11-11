use csv::Writer;
use nmea::Nmea;
use serde::Serialize;
use std::fs::File;
use std::io;
use std::path::Path;
use std::time::{SystemTime, UNIX_EPOCH};

#[derive(Debug, Clone, Serialize)]
pub struct GpsLogData {
    pub timestamp_ns: u64,
    pub fix_time: Option<String>,
    pub fix_date: Option<String>,
    pub gga_fix_quality: Option<String>,
    pub avg_snr: Option<f32>,
    pub latitude: Option<f64>,
    pub longitude: Option<f64>,
    pub altitude_m: Option<f32>,
    pub speed_over_ground: Option<f32>,
    pub true_course: Option<f32>,
    pub num_of_fix_satellites: Option<u32>,
    pub hdop: Option<f32>,
    pub vdop: Option<f32>,
    pub pdop: Option<f32>,
    pub geoid_separation: Option<f32>,
}

impl GpsLogData {
    fn from_nmea(nmea: Nmea, gga_fix_quality: Option<String>, timestamp_ns: u64) -> Self {
        let sats = nmea.satellites();
        let mut avg_snr = 0.0;
        let mut count = 0;
        for sat in &sats {
            if let Some(snr) = sat.snr() {
                avg_snr += snr;
                count += 1;
            }
        }
        let avg_snr_opt = if count > 0 {
            Some(avg_snr / count as f32)
        } else {
            None
        };

        let fix_quality_str = match gga_fix_quality.as_deref() {
            Some("0") => Some("Invalid".to_string()),
            Some("1") => Some("GPS Fix".to_string()),
            Some("2") => Some("DGPS".to_string()),
            Some("3") => Some("PPS".to_string()),
            Some("4") => Some("Fixed".to_string()),
            Some("5") => Some("Float".to_string()),
            Some("6") => Some("Estimated (dead reckoning)".to_string()),
            Some("7") => Some("Manual input mode".to_string()),
            Some("8") => Some("Simulation mode".to_string()),
            Some(other) => Some(format!("Unknown ({})", other)),
            None => None,
        };

        GpsLogData {
            timestamp_ns,
            fix_time: nmea.fix_time.map(|t| format!("{:?}", t)),
            fix_date: nmea.fix_date.map(|d| format!("{:?}", d)),
            gga_fix_quality: fix_quality_str,
            avg_snr: avg_snr_opt,
            latitude: nmea.latitude,
            longitude: nmea.longitude,
            altitude_m: nmea.altitude,
            speed_over_ground: nmea.speed_over_ground,
            true_course: nmea.true_course,
            num_of_fix_satellites: nmea.num_of_fix_satellites,
            hdop: nmea.hdop,
            vdop: nmea.vdop,
            pdop: nmea.pdop,
            geoid_separation: nmea.geoid_separation,
        }
    }
}

#[derive(Serialize)]
struct RtcmData {
    timestamp_ns: u64,
    message_type: u16,
    data_length: usize,
    data_hex: String,
}

pub struct Logger {
    gps: Writer<File>,
    rtcm: Writer<File>,
}

impl Logger {
    /// Open synchronously: permission/path errors must reach the caller.
    /// Refuse overwrites so repeated test names cannot destroy earlier logs.
    pub fn new(base: &Path) -> io::Result<Self> {
        let parent = base
            .parent()
            .filter(|p| !p.as_os_str().is_empty())
            .unwrap_or(Path::new("."));
        std::fs::create_dir_all(parent)?;
        let stem = base.file_stem().unwrap_or_default().to_string_lossy();
        let gps_path = parent.join(format!("{stem}_gps.csv"));
        let rtcm_path = parent.join(format!("{stem}_rtcm.csv"));
        // Check both names before creating either file.
        if gps_path.exists() || rtcm_path.exists() {
            return Err(io::Error::new(
                io::ErrorKind::AlreadyExists,
                "Log basename already exists; choose another --log-file",
            ));
        }
        let gps = Writer::from_writer(
            File::options()
                .write(true)
                .create_new(true)
                .open(gps_path)?,
        );
        let rtcm = Writer::from_writer(
            File::options()
                .write(true)
                .create_new(true)
                .open(rtcm_path)?,
        );
        Ok(Self { gps, rtcm })
    }

    pub fn log_nmea(&mut self, nmea: Nmea, quality: Option<String>) -> io::Result<()> {
        self.gps
            .serialize(GpsLogData::from_nmea(nmea, quality, timestamp_ns()))?;
        self.gps.flush()
    }

    pub fn log_rtcm(&mut self, frame: &[u8]) -> io::Result<()> {
        let message_type = crate::rtcm::message_type(frame).ok_or_else(|| {
            io::Error::new(
                io::ErrorKind::InvalidData,
                "Not a complete valid RTCM frame",
            )
        })?;
        self.rtcm.serialize(RtcmData {
            timestamp_ns: timestamp_ns(),
            message_type,
            data_length: frame.len(),
            data_hex: frame.iter().map(|byte| format!("{byte:02x}")).collect(),
        })?;
        self.rtcm.flush()
    }
}

fn timestamp_ns() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_nanos() as u64
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn creates_nested_logs_and_keeps_existing_recordings() {
        let root = std::env::temp_dir().join(format!(
            "ssailor-logger-{}-{}",
            std::process::id(),
            timestamp_ns()
        ));
        let base = root.join("nested/test.csv");
        let mut logger = Logger::new(&base).unwrap();
        let mut gps = Nmea::default();
        gps.latitude = Some(35.0);
        gps.altitude = Some(123.5);
        logger.log_nmea(gps, Some("4".into())).unwrap();
        logger.log_rtcm(&crate::rtcm::tests::FRAME_1005).unwrap();
        drop(logger);
        let csv = std::fs::read_to_string(root.join("nested/test_gps.csv")).unwrap();
        assert!(csv.contains("altitude_m"));
        assert!(csv.contains("Fixed"));
        assert!(csv.contains("123.5"));
        let rtcm = std::fs::read_to_string(root.join("nested/test_rtcm.csv")).unwrap();
        assert!(rtcm.contains(",1005,25,"));
        assert!(Logger::new(&base).is_err());
        assert!(!root.join("nested/test_sensor.csv").exists());
        std::fs::remove_dir_all(root).unwrap();
    }
}
