use crossterm::{
    cursor::MoveUp,
    queue,
    style::{Color, ResetColor, SetForegroundColor},
    terminal::{Clear, ClearType},
};
use nmea::Nmea;
use std::fmt::Display as FormatValue;
use std::io::Write;

pub struct Display {
    prev_lines: u16,
}

fn optional(value: Option<impl FormatValue>) -> String {
    value
        .map(|value| value.to_string())
        .unwrap_or_else(|| "N/A".to_string())
}

impl Display {
    pub fn new() -> Self {
        Self { prev_lines: 0 }
    }

    pub fn update<W: Write>(
        &mut self,
        out: &mut W,
        gps: &Nmea,
        quality: Option<&str>,
        status: &str,
    ) -> std::io::Result<()> {
        let fix = match quality {
            Some("0") => "Invalid",
            Some("1") => "GPS Fix",
            Some("2") => "DGPS",
            Some("3") => "PPS",
            Some("4") => "Fixed RTK",
            Some("5") => "Float RTK",
            Some("6") => "Estimated",
            Some("7") => "Manual",
            Some("8") => "Simulation",
            Some(_) => "Unknown",
            None => "N/A",
        };
        let snr: Vec<f32> = gps
            .satellites()
            .iter()
            .filter_map(|sat| sat.snr())
            .collect();
        let avg_snr = if snr.is_empty() {
            None
        } else {
            Some(snr.iter().sum::<f32>() / snr.len() as f32)
        };
        let lines = [
            "=== SSAILOR GPS / RTK ===".to_string(),
            format!("Corrections : {status}"),
            if gps.fix_time.is_none() {
                "GPS input   : Waiting for valid NMEA position messages".to_string()
            } else {
                "GPS input   : Last received position (values may be stale if data stops)"
                    .to_string()
            },
            format!("GPS time    : {}", optional(gps.fix_time)),
            format!("Latitude    : {}", optional(gps.latitude)),
            format!("Longitude   : {}", optional(gps.longitude)),
            format!("Altitude    : {} m", optional(gps.altitude)),
            format!("Fix type    : {fix}"),
            format!("Speed       : {} knots", optional(gps.speed_over_ground)),
            format!("Satellites  : {}", optional(gps.num_of_fix_satellites)),
            format!("HDOP        : {}", optional(gps.hdop)),
            format!("VDOP        : {}", optional(gps.vdop)),
            format!("PDOP        : {}", optional(gps.pdop)),
            format!("Average SNR : {} dB-Hz", optional(avg_snr)),
        ];
        if self.prev_lines > 0 {
            queue!(
                out,
                MoveUp(self.prev_lines),
                Clear(ClearType::FromCursorDown)
            )?;
        }
        for (index, line) in lines.iter().enumerate() {
            let color = if index == 0 {
                Color::Yellow
            } else {
                Color::Green
            };
            queue!(out, SetForegroundColor(color))?;
            writeln!(out, "{line}")?;
            queue!(out, ResetColor)?;
        }
        out.flush()?;
        self.prev_lines = lines.len() as u16;
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn waiting_screen_shows_connection_status_without_fabricating_coordinates() {
        let mut output = Vec::new();
        Display::new()
            .update(&mut output, &Nmea::default(), None, "Authentication failed")
            .unwrap();
        let text = String::from_utf8(output).unwrap();
        assert!(text.contains("Authentication failed"));
        assert!(text.contains("Latitude    : N/A"));
        assert!(text.contains("Waiting for valid NMEA"));
        assert!(!text.contains("Arduino"));
    }
}
