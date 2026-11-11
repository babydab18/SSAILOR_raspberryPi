use nmea::Nmea;

pub fn build_parser() -> Nmea {
    Nmea::default()
}

/// Only accept sentences successfully validated by the NMEA parser.
pub fn parse_nmea_sentence(parser: &mut Nmea, input: &str) -> bool {
    parser.parse(input.trim()).is_ok()
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn parses_valid_positions_and_rejects_bad_checksums() {
        let sentence = "$GPGGA,092750.000,5321.6802,N,00630.3372,W,1,8,1.03,61.7,M,55.2,M,,*76\r\n";
        let mut gps = build_parser();
        assert!(parse_nmea_sentence(&mut gps, sentence));
        assert!((gps.latitude.unwrap() - 53.3613366667).abs() < 0.000001);
        assert_eq!(gps.num_of_fix_satellites, Some(8));
        assert!(!parse_nmea_sentence(
            &mut gps,
            &sentence.replace("*76", "*00")
        ));
    }
}
