/// RTCM3 framing: 3-byte header, payload, then CRC-24Q.
/// TCP reads are arbitrary chunks; only complete, validated frames are forwarded/logged.
#[derive(Default)]
pub struct Decoder {
    buffer: Vec<u8>,
}

pub fn crc24q(data: &[u8]) -> u32 {
    let mut crc = 0u32;
    for byte in data {
        crc ^= (*byte as u32) << 16;
        for _ in 0..8 {
            crc <<= 1;
            if crc & 0x1000000 != 0 {
                crc ^= 0x1864cfb;
            }
        }
    }
    crc & 0xffffff
}

pub fn message_type(frame: &[u8]) -> Option<u16> {
    if frame.len() < 8 || frame[0] != 0xd3 || frame[1] & 0xfc != 0 {
        return None;
    }
    let length = (((frame[1] & 3) as usize) << 8) | frame[2] as usize;
    if length < 2 || frame.len() != length + 6 {
        return None;
    }
    let end = frame.len() - 3;
    let expected =
        ((frame[end] as u32) << 16) | ((frame[end + 1] as u32) << 8) | frame[end + 2] as u32;
    if crc24q(&frame[..end]) != expected {
        return None;
    }
    Some(((frame[3] as u16) << 4) | ((frame[4] as u16) >> 4))
}

impl Decoder {
    pub fn push(&mut self, bytes: &[u8]) -> Vec<Vec<u8>> {
        self.buffer.extend_from_slice(bytes);
        let mut frames = Vec::new();
        loop {
            let Some(start) = self.buffer.iter().position(|&byte| byte == 0xd3) else {
                self.buffer.clear();
                break;
            };
            self.buffer.drain(..start);
            if self.buffer.len() < 3 {
                break;
            }
            if self.buffer[1] & 0xfc != 0 {
                self.buffer.remove(0);
                continue;
            }
            let length = (((self.buffer[1] & 3) as usize) << 8) | self.buffer[2] as usize;
            if length < 2 {
                self.buffer.remove(0);
                continue;
            }
            let total = length + 6;
            if self.buffer.len() < total {
                break;
            }
            if message_type(&self.buffer[..total]).is_some() {
                frames.push(self.buffer.drain(..total).collect());
            } else {
                self.buffer.remove(0);
            }
        }
        frames
    }
}

#[cfg(test)]
pub(crate) mod tests {
    use super::*;
    // Real 1005 captured from the user's LC29H(BS), including its transmitted CRC.
    pub const FRAME_1005: [u8; 25] = [
        0xd3, 0x00, 0x13, 0x3e, 0xdd, 0x07, 0x03, 0xc2, 0x54, 0x41, 0x1b, 0x47, 0x34, 0x25, 0xc7,
        0x03, 0x97, 0x08, 0x9c, 0x21, 0x68, 0x4b, 0x72, 0xcd, 0x6e,
    ];
    #[test]
    fn decodes_captured_frame_and_rejects_bad_crc() {
        assert_eq!(message_type(&FRAME_1005), Some(1005));
        assert_eq!(message_type(&FRAME_1005[..24]), None);
        let mut bad = FRAME_1005;
        bad[10] ^= 1;
        assert_eq!(message_type(&bad), None);
    }
    #[test]
    fn accepts_every_split_point_and_multiple_frames_per_read() {
        for split in 0..FRAME_1005.len() {
            let mut decoder = Decoder::default();
            assert!(decoder.push(&FRAME_1005[..split]).is_empty());
            assert_eq!(
                decoder.push(&FRAME_1005[split..]),
                vec![FRAME_1005.to_vec()]
            );
        }
        let mut decoder = Decoder::default();
        let mut stream = b"noise\r\n".to_vec();
        stream.extend(FRAME_1005);
        stream.extend(FRAME_1005);
        assert_eq!(decoder.push(&stream).len(), 2);
    }
    #[test]
    fn recovers_after_corrupt_frame() {
        let mut stream = FRAME_1005.to_vec();
        stream[24] ^= 1;
        stream.extend(FRAME_1005);
        assert_eq!(Decoder::default().push(&stream), vec![FRAME_1005.to_vec()]);
    }
}
