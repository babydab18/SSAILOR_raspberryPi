use clap::Parser;
use std::io::{self, Write};
use std::path::PathBuf;
use std::sync::mpsc;
use std::time::{Duration, Instant};

mod display;
mod gps;
mod gps_serial;
mod logging;
mod ntrip;
mod rtcm;

#[derive(Parser)]
#[command(version, about = "SSAILOR GPS/RTK terminal display and recorder")]
struct Args {
    /// GPS serial device, e.g. /dev/ttyUSB0 on a Pi or COM3 on Windows
    #[arg(long, default_value = "/dev/ttyUSB0")]
    gps_port: PathBuf,
    #[arg(long, default_value_t = 115_200, value_parser = clap::value_parser!(u32).range(1..))]
    gps_baud: u32,
    /// Enable rover corrections from this NTRIP mountpoint
    #[arg(long)]
    ntrip_mount: Option<String>,
    #[arg(long, default_value = "rtk2go.com")]
    ntrip_host: String,
    #[arg(long, default_value_t = 2101, value_parser = clap::value_parser!(u16).range(1..))]
    ntrip_port: u16,
    /// Caster username; alternatively set NTRIP_USER. Password comes from NTRIP_PASSWORD.
    #[arg(long)]
    ntrip_user: Option<String>,
    /// Log basename; produces NAME_gps.csv and NAME_rtcm.csv
    #[arg(long)]
    log_file: Option<PathBuf>,
    /// Stop cleanly after this many seconds, including flushing the last GPS epoch
    #[arg(long, value_parser = clap::value_parser!(u64).range(1..))]
    duration: Option<u64>,
}

fn main() -> io::Result<()> {
    let args = Args::parse();
    let config = args.ntrip_mount.map(|mountpoint| ntrip::Config {
        host: args.ntrip_host,
        port: args.ntrip_port,
        mountpoint,
        username: args
            .ntrip_user
            .or_else(|| std::env::var("NTRIP_USER").ok())
            .unwrap_or_default(),
        password: std::env::var("NTRIP_PASSWORD").unwrap_or_default(),
    });
    if let Some(config) = &config {
        config.validate()?;
    }
    let mut port = gps_serial::open_port(args.gps_port, args.gps_baud)
        .map_err(|error| io::Error::other(format!("Cannot open GPS port: {error}")))?;
    let log_file = args.log_file.unwrap_or_else(|| {
        PathBuf::from("logs").join(
            chrono::Local::now()
                .format("%Y-%m-%d_%H-%M-%S.csv")
                .to_string(),
        )
    });
    let mut logger = logging::Logger::new(&log_file)?;
    let (tx, rx) = mpsc::sync_channel(64);
    let mut status = if let Some(config) = config {
        std::thread::spawn(move || ntrip::run(config, tx));
        "Connecting to correction service".to_string()
    } else {
        drop(tx);
        "Disabled (no --ntrip-mount)".to_string()
    };
    let mut parser = gps::parser::build_parser();
    let mut quality = None;
    let mut display = display::Display::new();
    let mut stdout = io::stdout();
    display.update(&mut stdout, &parser, quality.as_deref(), &status)?;
    let started = Instant::now();
    let mut last_render = Instant::now();

    loop {
        if args
            .duration
            .is_some_and(|seconds| started.elapsed() >= Duration::from_secs(seconds))
        {
            break;
        }
        for sentence in port.read_sentences()? {
            let mut next = parser.clone();
            if !gps::parser::parse_nmea_sentence(&mut next, &sentence) {
                continue;
            }
            if next.fix_time != parser.fix_time && parser.fix_time.is_some() {
                logger.log_nmea(parser.clone(), quality.clone())?;
            }
            let mut fields = sentence.trim().split(',');
            if fields.next().is_some_and(|id| id.ends_with("GGA")) {
                quality = sentence.split(',').nth(6).map(str::to_string);
            }
            parser = next;
        }
        // Bound work per iteration so GPS reads remain responsive during corrections.
        for message in rx.try_iter().take(64) {
            match message {
                ntrip::Message::Status(message) => status = message,
                ntrip::Message::Rtcm(frame) => {
                    port.write_all(&frame)?;
                    port.flush()?;
                    logger.log_rtcm(&frame)?;
                    status = "Receiving RTCM corrections".to_string();
                }
            }
        }
        if last_render.elapsed() >= Duration::from_secs(1) {
            display.update(&mut stdout, &parser, quality.as_deref(), &status)?;
            last_render = Instant::now();
        }
    }
    if parser.fix_time.is_some() {
        logger.log_nmea(parser.clone(), quality.clone())?;
    }
    display.update(&mut stdout, &parser, quality.as_deref(), &status)?;
    Ok(())
}
